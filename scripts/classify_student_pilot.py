"""Run a bounded, text-free inference pilot from a pinned HF source."""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from contextlib import nullcontext
from itertools import islice
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

from apply_source_plan import requests_from_plan  # noqa: E402
from train_student import NOISE, SCORES, TYPES, Student, encode_text  # noqa: E402
from linguai_quality.contracts import document_id, route, validate_label  # noqa: E402


def encode_text_for_inference(tokenizer, text, max_length):
    """Avoid tokenizing unused middle text in very long documents."""
    if len(text) <= 16_384:
        return encode_text(tokenizer, text, max_length)
    head_size = (max_length - 2) // 2
    tail_size = max_length - 2 - head_size
    head = tokenizer(text[:8192], add_special_tokens=False)["input_ids"]
    tail = tokenizer(text[-8192:], add_special_tokens=False)["input_ids"]
    if len(head) < head_size or len(tail) < tail_size:
        return encode_text(tokenizer, text, max_length)
    return tokenizer.build_inputs_with_special_tokens(head[:head_size] + tail[-tail_size:]), True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 < args.limit <= 10000 or not 0 < args.batch_size <= 128:
        raise ValueError("pilot limit or batch size outside safe bounds")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    if args.output.exists():
        raise FileExistsError(args.output)
    plan = json.loads((ROOT / "deploy/source_plan_2026-10-02.json").read_text())
    matches = [item for item in requests_from_plan(plan) if item["run_id"] == args.run_id]
    if len(matches) != 1:
        raise ValueError("unknown pinned source run")
    source = matches[0]
    model_dir = Path.home() / ".local/share/linguai-training/run-20261003"
    base_dir = Path.home() / ".local/share/linguai-training/base-model"
    manifest = json.loads((model_dir / "manifest.json").read_text())
    if manifest["base_model_revision"] != "6b4ecd5d04196649e5460cc52fc096a44ed6d894":
        raise ValueError("unexpected base model revision")
    artifact = model_dir / "student_model.safetensors"
    model_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    torch.set_num_threads(6)
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = Student(base_dir, manifest["unfreeze_layers"])
    model.load_state_dict(load_file(artifact))
    model.to(args.device).eval()
    stream = load_dataset(source["source"], name=source["config"] or None,
                          split=source["split"], revision=source["revision"], streaming=True)
    started = time.monotonic()
    records = []
    for ordinal, row in enumerate(islice(stream, args.limit)):
        text = row.get(source["text_field"])
        if isinstance(text, str) and text.strip():
            records.append((ordinal, text))
    if not records:
        raise ValueError("no usable records in pilot window")
    outputs = []
    inference_seconds = 0.0
    with torch.inference_mode():
        for start in range(0, len(records), args.batch_size):
            batch = records[start:start + args.batch_size]
            ids = np.full((len(batch), manifest["max_length"]), tokenizer.pad_token_id, dtype=np.int64)
            masks = np.zeros_like(ids)
            flags = []
            for index, (_, text) in enumerate(batch):
                tokens, truncated = encode_text_for_inference(tokenizer, text, manifest["max_length"])
                ids[index, :len(tokens)] = tokens
                masks[index, :len(tokens)] = 1
                flags.append(truncated)
            began = time.monotonic()
            input_ids = torch.from_numpy(ids).to(args.device)
            attention_mask = torch.from_numpy(masks).to(args.device)
            context = torch.autocast("cuda", dtype=torch.float16) if args.device == "cuda" else nullcontext()
            with context:
                type_logits, score_logits, noise_logits = model(input_ids, attention_mask)
            type_logits = type_logits.cpu()
            score_logits = score_logits.cpu()
            noise_logits = noise_logits.cpu()
            if args.device == "cuda":
                torch.cuda.synchronize()
            inference_seconds += time.monotonic() - began
            pred_types = type_logits.argmax(-1).tolist()
            pred_scores = score_logits.argmax(-1).tolist()
            pred_noise = (noise_logits.sigmoid() >= 0.5).tolist()
            for index, (ordinal, text) in enumerate(batch):
                doc_id = document_id(source["source"], source["revision"], source["config"],
                                     source["split"], ordinal, text)
                label = {"id": doc_id, "type": TYPES[pred_types[index]],
                         "q": dict(zip(SCORES, pred_scores[index])),
                         "noise": [name for name, chosen in zip(NOISE, pred_noise[index]) if chosen]}
                validate_label(label, doc_id)
                outputs.append({"run_id": args.run_id, "source_dataset": source["source"],
                                "source_revision": source["revision"],
                                "source_config": source["config"], "source_split": source["split"],
                                "row_ordinal": ordinal, "doc_id": doc_id,
                                "document_hash": hashlib.sha256(text.encode()).hexdigest(),
                                "input_bytes": len(text.encode()), "input_truncated": flags[index],
                                "predicted_label_json": json.dumps(label, ensure_ascii=False, sort_keys=True),
                                "predicted_route": route(label),
                                "student_artifact_sha256": model_hash})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    try:
        pq.write_table(pa.Table.from_pylist(outputs), temporary, compression="zstd")
        os.replace(temporary, args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"source": args.run_id, "records": len(outputs),
                      "elapsed_seconds": round(time.monotonic() - started, 2),
                      "inference_seconds": round(inference_seconds, 2),
                      "route_counts": dict(Counter(item["predicted_route"] for item in outputs)),
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
