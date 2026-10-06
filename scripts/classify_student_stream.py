"""Classify a pinned HF source into restartable, text-free Parquet parts."""

import argparse
import hashlib
import json
import os
import queue
import re
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch
from datasets import load_dataset
from safetensors.torch import load_file
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from classify_student_pilot import encode_text_for_inference  # noqa: E402
from train_student import NOISE, SCORES, TYPES, Student  # noqa: E402
from linguai_quality.contracts import document_id, route, validate_label  # noqa: E402

PART_RE = re.compile(r"part-(\d{12})-(\d{12})\.parquet$")


def existing_position(directory, initial_position=0):
    position = initial_position
    count = 0
    for part in sorted(directory.glob("part-*.parquet")):
        match = PART_RE.fullmatch(part.name)
        if not match or int(match[1]) != position or int(match[2]) <= position:
            raise RuntimeError(f"non-contiguous output: {part}")
        position = int(match[2])
        count += pq.read_metadata(part).num_rows
    return position, count


def write_part(directory, start, end, rows):
    target = directory / f"part-{start:012d}-{end:012d}.parquet"
    if target.exists():
        raise FileExistsError(target)
    temporary = target.with_suffix(".parquet.tmp")
    try:
        pq.write_table(pa.Table.from_pylist(rows), temporary, compression="zstd")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def prepare_batch(pending, tokenizer, source, length):
    ids = np.full((len(pending), length), tokenizer.pad_token_id, dtype=np.int64)
    masks = np.zeros_like(ids)
    metadata = []
    for index, (ordinal, text) in enumerate(pending):
        tokens, truncated = encode_text_for_inference(tokenizer, text, length)
        ids[index, :len(tokens)] = tokens
        masks[index, :len(tokens)] = 1
        encoded = text.encode()
        metadata.append({"source_id": source["id"], "row_ordinal": ordinal,
                         "doc_id": document_id(source["repo"], source["revision"],
                                               source["config"], source["split"], ordinal, text),
                         "document_hash": hashlib.sha256(encoded).hexdigest(),
                         "input_bytes": len(encoded), "input_truncated": truncated})
    return ids, masks, metadata


def produce_part(iterator, tokenizer, source, length, start, end, batch_size,
                 batches, stop, state):
    pending = []
    scanned = start

    def publish(item):
        while not stop.is_set():
            try:
                batches.put(item, timeout=0.5)
                return
            except queue.Full:
                pass

    try:
        for ordinal in range(start, end):
            if stop.is_set():
                break
            try:
                row = next(iterator)
            except StopIteration:
                state["exhausted"] = True
                break
            scanned = ordinal + 1
            text = row.get(source["text_field"])
            if isinstance(text, str) and text.strip():
                pending.append((ordinal, text))
                if len(pending) == batch_size:
                    publish(prepare_batch(pending, tokenizer, source, length))
                    pending.clear()
        if pending and not stop.is_set():
            publish(prepare_batch(pending, tokenizer, source, length))
    except BaseException as error:
        state["error"] = error
    finally:
        state["scanned"] = scanned
        publish(None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--prefetch-batches", type=int, default=3)
    parser.add_argument("--part-rows", type=int, default=10_000)
    parser.add_argument("--max-rows", type=int, default=0, help="Additional source rows to scan; zero means all")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--file-start", type=int, default=None,
                        help="First pinned FineWeb2 Turkish file, inclusive")
    parser.add_argument("--file-end", type=int, default=None,
                        help="Last pinned FineWeb2 Turkish file, exclusive")
    args = parser.parse_args()
    if (not 0 < args.batch_size <= 512 or not 0 < args.prefetch_batches <= 8
            or not 0 < args.part_rows <= 100_000 or args.max_rows < 0):
        raise ValueError("invalid work size")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    plan = json.loads((ROOT / "deploy/source_plan_2026-10-02.json").read_text())
    sources = [source for source in plan["sources"] if source["id"] == args.source_id]
    if len(sources) != 1:
        raise ValueError("unknown pinned source")
    source = sources[0]
    selected_files = None
    initial_position = 0
    end_position = None
    if args.file_start is not None or args.file_end is not None:
        if args.source_id != "fineweb2-tur" or args.file_start is None or args.file_end is None:
            raise ValueError("file selection requires FineWeb2 Turkish and both boundaries")
        file_plan = json.loads((ROOT / "deploy/fineweb2_tur_files.json").read_text())
        files = file_plan["files"]
        if (file_plan["repo"] != source["repo"] or file_plan["revision"] != source["revision"]
                or not 0 <= args.file_start < args.file_end <= len(files)):
            raise ValueError("invalid pinned file selection")
        selected_files = files[args.file_start:args.file_end]
        initial_position = selected_files[0]["start_ordinal"]
        end_position = selected_files[-1]["start_ordinal"] + selected_files[-1]["rows"]
    model_dir = Path.home() / ".local/share/linguai-training/run-20261003"
    base_dir = Path.home() / ".local/share/linguai-training/base-model"
    manifest = json.loads((model_dir / "manifest.json").read_text())
    model_hash = hashlib.sha256((model_dir / "student_model.safetensors").read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    identity = {"source_id": source["id"], "source_repo": source["repo"],
                "source_revision": source["revision"], "source_config": source["config"],
                "source_split": source["split"], "student_artifact_sha256": model_hash,
                "max_length": manifest["max_length"]}
    if selected_files is not None:
        identity.update({"file_start": args.file_start, "file_end": args.file_end,
                         "initial_ordinal": initial_position, "end_ordinal": end_position})
    identity_path = args.output_dir / "identity.json"
    if identity_path.exists():
        if json.loads(identity_path.read_text()) != identity:
            raise RuntimeError("output identity differs from current source or model")
    else:
        if list(args.output_dir.glob("part-*.parquet")):
            raise RuntimeError("parts exist without source identity")
        identity_path.write_text(json.dumps(identity, indent=2) + "\n")
    position, prior_count = existing_position(args.output_dir, initial_position)
    if (args.output_dir / "DONE.json").exists():
        print(json.dumps({"source_id": source["id"], "already_done": True,
                          "rows_scanned": position, "classified": prior_count}), flush=True)
        return
    torch.set_num_threads(6)
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = Student(base_dir, manifest["unfreeze_layers"])
    model.load_state_dict(load_file(model_dir / "student_model.safetensors"))
    model.to(args.device).eval()
    if selected_files is None:
        stream = load_dataset(source["repo"], name=source["config"] or None,
                              split=source["split"], revision=source["revision"], streaming=True)
    else:
        stream = load_dataset("parquet", data_files={"train": [item["url"] for item in selected_files]},
                              split="train", streaming=True)
    iterator = iter(stream.skip(position - initial_position))
    started = time.monotonic()
    limit = position + args.max_rows if args.max_rows else None
    if end_position is not None:
        limit = min(limit, end_position) if limit is not None else end_position
    scanned = position
    total_classified = prior_count
    exhausted = False
    with torch.inference_mode():
        while limit is None or scanned < limit:
            part_start = scanned
            part_end = min(part_start + args.part_rows, limit) if limit is not None else part_start + args.part_rows
            outputs = []
            inference_seconds = 0.0
            batches = queue.Queue(maxsize=args.prefetch_batches)
            stop = threading.Event()
            state = {"scanned": part_start, "exhausted": False, "error": None}
            producer = threading.Thread(target=produce_part,
                                        args=(iterator, tokenizer, source, manifest["max_length"],
                                              part_start, part_end, args.batch_size, batches, stop, state),
                                        daemon=True)
            producer.start()
            try:
                while True:
                    batch = batches.get()
                    if batch is None:
                        break
                    ids, masks, metadata = batch
                    input_ids = torch.from_numpy(ids).to(args.device)
                    attention_mask = torch.from_numpy(masks).to(args.device)
                    began = time.monotonic()
                    if args.device == "cuda":
                        with torch.autocast("cuda", dtype=torch.float16):
                            logits = model(input_ids, attention_mask)
                        torch.cuda.synchronize()
                    else:
                        logits = model(input_ids, attention_mask)
                    inference_seconds += time.monotonic() - began
                    pred_types = logits[0].argmax(-1).cpu().tolist()
                    pred_scores = logits[1].argmax(-1).cpu().tolist()
                    pred_noise = (logits[2].sigmoid() >= 0.5).cpu().tolist()
                    for index, item in enumerate(metadata):
                        doc_id = item["doc_id"]
                        label = {"id": doc_id, "type": TYPES[pred_types[index]],
                                 "q": dict(zip(SCORES, pred_scores[index])),
                                 "noise": [name for name, selected in zip(NOISE, pred_noise[index]) if selected]}
                        validate_label(label, doc_id)
                        item["predicted_label_json"] = json.dumps(label, ensure_ascii=False, sort_keys=True)
                        item["predicted_route"] = route(label)
                        outputs.append(item)
            finally:
                stop.set()
                producer.join()
            if state["error"] is not None:
                raise state["error"]
            scanned = state["scanned"]
            exhausted = state["exhausted"]
            if scanned > part_start:
                part = write_part(args.output_dir, part_start, scanned, outputs)
                total_classified += len(outputs)
                print(json.dumps({"source_id": source["id"], "part": str(part),
                                  "rows_scanned": scanned, "classified": total_classified,
                                  "part_classified": len(outputs),
                                  "inference_seconds": round(inference_seconds, 2),
                                  "elapsed_seconds": round(time.monotonic() - started, 2)}), flush=True)
            if exhausted:
                break
    if end_position is not None and scanned == end_position:
        exhausted = True
    if end_position is not None and exhausted and scanned != end_position:
        raise RuntimeError(f"pinned file range ended at {scanned}, expected {end_position}")
    if exhausted:
        done = {"source_id": source["id"], "rows_scanned": scanned,
                "classified": total_classified, "student_artifact_sha256": model_hash}
        temporary = args.output_dir / "DONE.json.tmp"
        temporary.write_text(json.dumps(done, indent=2) + "\n")
        os.replace(temporary, args.output_dir / "DONE.json")
        print(json.dumps({"done": done}), flush=True)


if __name__ == "__main__":
    main()
