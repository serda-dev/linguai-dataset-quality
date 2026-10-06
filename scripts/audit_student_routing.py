"""Audit student decisions against the held-out Teacher labels."""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from safetensors.torch import load_file
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from classify_student_pilot import encode_text_for_inference  # noqa: E402
from train_student import NOISE, SCORES, TYPES, Student, load_rows, split_rows  # noqa: E402
from linguai_quality.contracts import route  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--student", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 128:
        raise ValueError("invalid batch size")
    rows, _ = load_rows(args.data)
    _, valid = split_rows(rows)
    manifest = json.loads((args.student / "manifest.json").read_text())
    tokenizer = AutoTokenizer.from_pretrained(args.student)
    model = Student(args.base_model, manifest["unfreeze_layers"])
    model.load_state_dict(load_file(args.student / "student_model.safetensors"))
    model.cuda().eval()

    routes = Counter()
    score_errors = Counter()
    document_large_errors = 0
    type_correct = 0
    per_source = defaultdict(Counter)
    per_source_routes = defaultdict(Counter)
    accepted = {"KEEP", "PREMIUM"}
    for offset in range(0, len(valid), args.batch_size):
        batch = [rows[index] for index in valid[offset:offset + args.batch_size]]
        ids = np.full((len(batch), manifest["max_length"]), tokenizer.pad_token_id, dtype=np.int64)
        masks = np.zeros_like(ids)
        for index, row in enumerate(batch):
            tokens, _ = encode_text_for_inference(tokenizer, row["original_text"], manifest["max_length"])
            ids[index, :len(tokens)] = tokens
            masks[index, :len(tokens)] = 1
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.float16):
            logits = model(torch.from_numpy(ids).cuda(), torch.from_numpy(masks).cuda())
        types = logits[0].argmax(-1).cpu().tolist()
        scores = logits[1].argmax(-1).cpu().tolist()
        noises = (logits[2].sigmoid() >= 0.5).cpu().tolist()
        for index, row in enumerate(batch):
            truth = row["label"]
            prediction = {"id": row["doc_id"], "type": TYPES[types[index]],
                          "q": dict(zip(SCORES, scores[index])),
                          "noise": [name for name, yes in zip(NOISE, noises[index]) if yes]}
            truth_route, pred_route = route(truth), route(prediction)
            routes[(truth_route, pred_route)] += 1
            source = row["source_dataset"]
            per_source_routes[source][(truth_route, pred_route)] += 1
            per_source[source]["total"] += 1
            per_source[source]["route_agreement"] += truth_route == pred_route
            per_source[source]["false_drop"] += truth_route in accepted and pred_route == "DROP"
            per_source[source]["drop_accepted"] += truth_route == "DROP" and pred_route in accepted
            type_correct += prediction["type"] == truth["type"]
            large = False
            for key in SCORES:
                if truth["q"][key] is None:
                    continue
                error = abs(prediction["q"][key] - truth["q"][key])
                score_errors[error] += 1
                large |= error >= 2
            document_large_errors += large
        if offset % (args.batch_size * 10) == 0:
            print(f"audited {offset + len(batch)}/{len(valid)}", flush=True)
    total = len(valid)
    matrix = {truth: {pred: routes[(truth, pred)] for pred in
                      ("PREMIUM", "KEEP", "DETERMINISTIC_REPAIR", "MODEL_REPAIR", "DROP", "REVIEW")}
              for truth in ("PREMIUM", "KEEP", "DETERMINISTIC_REPAIR", "MODEL_REPAIR", "DROP", "REVIEW")}
    result = {"holdout_rows": total, "type_accuracy": type_correct / total,
              "route_agreement": sum(routes[(r, r)] for r in matrix) / total,
              "score_abs_error_counts": dict(sorted(score_errors.items())),
              "documents_with_any_score_error_at_least_2": document_large_errors,
              "route_confusion": matrix,
              "per_source": {k: dict(v) for k, v in per_source.items()},
              "per_source_route_confusion": {
                  source: {truth: {pred: counts[(truth, pred)] for pred in matrix[truth]}
                           for truth in matrix}
                  for source, counts in per_source_routes.items()}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
