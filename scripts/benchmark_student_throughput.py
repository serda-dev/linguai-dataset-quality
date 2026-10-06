"""Measure full forward throughput and prediction parity at larger GPU batches."""

import argparse
import json
import sys
import time
from itertools import islice
from pathlib import Path

import numpy as np
import torch
from datasets import load_dataset
from safetensors.torch import load_file
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from classify_student_pilot import encode_text_for_inference  # noqa: E402
from train_student import Student  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", default="bella-akademik")
    parser.add_argument("--records", type=int, default=4096)
    args = parser.parse_args()
    torch.set_num_threads(6)
    plan = json.loads((ROOT / "deploy/source_plan_2026-10-02.json").read_text())
    source = next(item for item in plan["sources"] if item["id"] == args.source_id)
    model_dir = Path.home() / ".local/share/linguai-training/run-20261003"
    base_dir = Path.home() / ".local/share/linguai-training/base-model"
    manifest = json.loads((model_dir / "manifest.json").read_text())
    length = manifest["max_length"]
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    stream = load_dataset(source["repo"], name=source["config"] or None,
                          split=source["split"], revision=source["revision"], streaming=True)
    texts = [row[source["text_field"]] for row in islice(stream, args.records)]
    ids = np.full((len(texts), length), tokenizer.pad_token_id, dtype=np.int64)
    masks = np.zeros_like(ids)
    started = time.monotonic()
    for index, text in enumerate(texts):
        tokens, _ = encode_text_for_inference(tokenizer, text, length)
        ids[index, :len(tokens)] = tokens
        masks[index, :len(tokens)] = 1
    print(json.dumps({"tokenized": len(texts), "seconds": round(time.monotonic() - started, 2)}), flush=True)
    model = Student(base_dir, manifest["unfreeze_layers"])
    model.load_state_dict(load_file(model_dir / "student_model.safetensors"))
    model.cuda().eval()
    baseline = None
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.float16):
        for batch_size in (64, 128, 256, 512):
            try:
                predictions = []
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
                start = time.monotonic()
                for offset in range(0, len(texts), batch_size):
                    batch_ids = torch.from_numpy(ids[offset:offset + batch_size]).cuda()
                    batch_masks = torch.from_numpy(masks[offset:offset + batch_size]).cuda()
                    logits = model(batch_ids, batch_masks)
                    predictions.extend(logits[0].argmax(-1).cpu().tolist())
                torch.cuda.synchronize()
                elapsed = time.monotonic() - start
                if baseline is None:
                    baseline = predictions
                print(json.dumps({"batch_size": batch_size, "records": len(texts),
                                  "seconds": round(elapsed, 3),
                                  "docs_per_second": round(len(texts) / elapsed, 1),
                                  "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                                  "type_agreement_with_batch64": sum(a == b for a, b in zip(baseline, predictions))}),
                      flush=True)
            except torch.cuda.OutOfMemoryError:
                print(json.dumps({"batch_size": batch_size, "error": "CUDA OOM"}), flush=True)
                torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
