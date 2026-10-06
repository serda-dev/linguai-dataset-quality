"""Train a local multi-task MoganBERT student on the completed Teacher campaign.

The validation fold is an internal development holdout, not a published benchmark.
"""

import argparse
import hashlib
import json
import os
import random
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import torch
from safetensors.torch import save_file
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error
from sklearn.model_selection import StratifiedGroupKFold
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, Subset, TensorDataset
from transformers import AutoModel, AutoTokenizer


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/teacher_label_v1.schema.json").read_text())
TYPES = SCHEMA["properties"]["type"]["enum"]
NOISE = SCHEMA["properties"]["noise"]["items"]["enum"]
SCORES = SCHEMA["properties"]["q"]["required"]
MODEL_REVISION = "6b4ecd5d04196649e5460cc52fc096a44ed6d894"
EXPECTED_ROWS = 39_696
SEED = 20261003


class Student(nn.Module):
    def __init__(self, model_dir: Path, unfreeze_layers: int):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_dir, attn_implementation="sdpa")
        if not 0 <= unfreeze_layers <= len(self.encoder.layers):
            raise ValueError("invalid unfreeze_layers")
        for parameter in self.encoder.parameters():
            parameter.requires_grad = False
        for layer in self.encoder.layers[-unfreeze_layers:] if unfreeze_layers else []:
            for parameter in layer.parameters():
                parameter.requires_grad = True
        for parameter in self.encoder.final_norm.parameters():
            parameter.requires_grad = True
        width = self.encoder.config.hidden_size
        self.type_head = nn.Linear(width, len(TYPES))
        self.score_head = nn.Linear(width, len(SCORES) * 5)
        self.noise_head = nn.Linear(width, len(NOISE))

    def forward(self, input_ids, attention_mask):
        hidden = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        mask = attention_mask.unsqueeze(-1)
        pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1)
        return (self.type_head(pooled),
                self.score_head(pooled).reshape(-1, len(SCORES), 5),
                self.noise_head(pooled))


def load_rows(path: Path):
    columns = ["doc_id", "original_text", "content_family", "teacher_label_json",
               "document_hash", "source_dataset", "labeling_run_id"]
    table = pq.read_table(path, columns=columns)
    rows = [row for row in table.to_pylist()
            if row["labeling_run_id"].startswith("20261002-")
            and not row["labeling_run_id"].startswith("20261002-probe-")]
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} campaign labels, found {len(rows)}")
    families = defaultdict(list)
    for row in rows:
        if hashlib.sha256(row["original_text"].encode()).hexdigest() != row["document_hash"]:
            raise ValueError("export document hash mismatch")
        label = json.loads(row["teacher_label_json"])
        if label["id"] != row["doc_id"] or label["type"] not in TYPES:
            raise ValueError("export label identity or type mismatch")
        if set(label["q"]) != set(SCORES) or any(
                value not in range(5) and not (key == "language" and value is None)
                for key, value in label["q"].items()):
            raise ValueError("export quality score mismatch")
        if any(value not in NOISE for value in label["noise"]):
            raise ValueError("export noise label mismatch")
        row["label"] = label
        families[row["content_family"]].append(row)
    selected = []
    conflicts = 0
    for family in sorted(families):
        group = families[family]
        # The JSON includes doc_id, so compare observations without identity.
        observations = {(item["label"]["type"],
                         tuple(item["label"]["q"][key] for key in SCORES),
                         tuple(sorted(item["label"]["noise"]))) for item in group}
        if len(observations) > 1:
            conflicts += 1
            continue
        selected.append(min(group, key=lambda item: item["doc_id"]))
    selected.sort(key=lambda item: item["doc_id"])
    return selected, {"export_rows": len(rows), "unique_families": len(families),
                      "conflicting_families_removed": conflicts,
                      "training_candidates": len(selected)}


def split_rows(rows):
    labels = [row["label"]["type"] for row in rows]
    families = [row["content_family"] for row in rows]
    splitter = StratifiedGroupKFold(n_splits=10, shuffle=True, random_state=SEED)
    train, valid = next(splitter.split(np.zeros(len(rows)), labels, families))
    if set(families[i] for i in train) & set(families[i] for i in valid):
        raise ValueError("family leakage across train and validation")
    return train, valid


def encode_text(tokenizer, text, max_length):
    tokens = tokenizer(text, add_special_tokens=False)["input_ids"]
    truncated = len(tokens) > max_length - 2
    if truncated:
        head = (max_length - 2) // 2
        tokens = tokens[:head] + tokens[-(max_length - 2 - head):]
    return tokenizer.build_inputs_with_special_tokens(tokens), truncated


def encode_rows(rows, tokenizer, max_length):
    ids = np.full((len(rows), max_length), tokenizer.pad_token_id, dtype=np.int64)
    masks = np.zeros((len(rows), max_length), dtype=np.int64)
    types = np.empty(len(rows), dtype=np.int64)
    scores = np.full((len(rows), len(SCORES)), -100, dtype=np.int64)
    noises = np.zeros((len(rows), len(NOISE)), dtype=np.float32)
    truncated = 0
    for index, row in enumerate(rows):
        tokens, was_truncated = encode_text(tokenizer, row["original_text"], max_length)
        truncated += was_truncated
        ids[index, :len(tokens)] = tokens
        masks[index, :len(tokens)] = 1
        label = row["label"]
        types[index] = TYPES.index(label["type"])
        for column, name in enumerate(SCORES):
            if label["q"][name] is not None:
                scores[index, column] = label["q"][name]
        for name in label["noise"]:
            noises[index, NOISE.index(name)] = 1
        if (index + 1) % 5000 == 0:
            print(f"tokenized={index + 1}/{len(rows)}", flush=True)
    dataset = TensorDataset(torch.from_numpy(ids), torch.from_numpy(masks),
                            torch.from_numpy(types), torch.from_numpy(scores),
                            torch.from_numpy(noises))
    return dataset, truncated


def class_weights(dataset, train_indices):
    types = dataset.tensors[2][train_indices]
    scores = dataset.tensors[3][train_indices]
    noises = dataset.tensors[4][train_indices]

    def weights(values, classes):
        counts = torch.bincount(values, minlength=classes).float().clamp_min(1)
        result = (counts.sum() / (classes * counts)).sqrt().clamp(max=5)
        return result / result.mean()

    type_weight = weights(types, len(TYPES))
    score_weights = [weights(scores[:, index][scores[:, index] >= 0], 5)
                     for index in range(len(SCORES))]
    positives = noises.sum(dim=0).clamp_min(1)
    noise_weight = ((len(train_indices) - positives) / positives).sqrt().clamp(max=8)
    return type_weight, score_weights, noise_weight


def loss_for(outputs, batch, weights):
    type_logits, score_logits, noise_logits = outputs
    type_weight, score_weights, noise_weight = weights
    type_loss = F.cross_entropy(type_logits, batch[2], weight=type_weight)
    score_losses = [F.cross_entropy(score_logits[:, i], batch[3][:, i],
                                    weight=score_weights[i], ignore_index=-100)
                    for i in range(len(SCORES))]
    noise_loss = F.binary_cross_entropy_with_logits(noise_logits, batch[4],
                                                     pos_weight=noise_weight)
    return type_loss + sum(score_losses) / len(score_losses) + noise_loss


@torch.no_grad()
def evaluate(model, dataset, indices, weights, batch_size):
    model.eval()
    truth_type, pred_type, truth_score, pred_score, truth_noise, pred_noise = [], [], [], [], [], []
    losses = []
    for batch in DataLoader(Subset(dataset, indices), batch_size=batch_size):
        outputs = model(batch[0], batch[1])
        losses.append(loss_for(outputs, batch, weights).item())
        truth_type.extend(batch[2].tolist())
        pred_type.extend(outputs[0].argmax(-1).tolist())
        truth_score.extend(batch[3].tolist())
        pred_score.extend(outputs[1].argmax(-1).tolist())
        truth_noise.extend(batch[4].int().tolist())
        pred_noise.extend((outputs[2].sigmoid() >= 0.5).int().tolist())
    truth_score, pred_score = np.asarray(truth_score), np.asarray(pred_score)
    mask = truth_score >= 0
    return {"loss": float(np.mean(losses)),
            "type_accuracy": accuracy_score(truth_type, pred_type),
            "type_macro_f1": f1_score(truth_type, pred_type, average="macro", zero_division=0),
            "score_mae": mean_absolute_error(truth_score[mask], pred_score[mask]),
            "noise_micro_f1": f1_score(truth_noise, pred_noise, average="micro", zero_division=0)}


def save_checkpoint(path, model, optimizer, epoch, next_batch, steps):
    temporary = path.with_suffix(".tmp")
    torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                "epoch": epoch, "next_batch": next_batch, "steps": steps}, temporary)
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--unfreeze-layers", type=int, default=2)
    parser.add_argument("--checkpoint-every", type=int, default=300)
    parser.add_argument("--smoke-steps", type=int, default=0)
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.max_length < 32:
        raise ValueError("invalid training dimensions")
    torch.set_num_threads(6)
    torch.set_num_interop_threads(1)
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    random.seed(SEED)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print("loading_export", flush=True)
    rows, quality = load_rows(args.data)
    train_indices, valid_indices = split_rows(rows)
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir)
    dataset, truncated = encode_rows(rows, tokenizer, args.max_length)
    manifest = {**quality, "train_rows": len(train_indices), "valid_rows": len(valid_indices),
                "truncated_rows": truncated, "base_model": "moganai/MoganBERT-TR",
                "base_model_revision": MODEL_REVISION, "max_length": args.max_length,
                "base_model_sha256": hashlib.sha256((args.model_dir / "model.safetensors").read_bytes()).hexdigest(),
                "unfreeze_layers": args.unfreeze_layers, "types": TYPES, "scores": SCORES,
                "noise": NOISE, "validation_policy": "internal_stratified_exact_family_group_10pct",
                "data_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest()}
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("prepared", json.dumps({key: manifest[key] for key in
          ("training_candidates", "conflicting_families_removed", "train_rows", "valid_rows",
           "truncated_rows")}), flush=True)
    model = Student(args.model_dir, args.unfreeze_layers)
    print("trainable_parameters", sum(p.numel() for p in model.parameters() if p.requires_grad), flush=True)
    head_params = list(model.type_head.parameters()) + list(model.score_head.parameters()) + list(model.noise_head.parameters())
    head_ids = {id(p) for p in head_params}
    backbone_params = [p for p in model.parameters() if p.requires_grad and id(p) not in head_ids]
    optimizer = torch.optim.AdamW([{"params": backbone_params, "lr": 3e-5},
                                   {"params": head_params, "lr": 3e-4}], weight_decay=0.01)
    weights = class_weights(dataset, train_indices)
    checkpoint = args.output_dir / "checkpoint.pt"
    start_epoch = start_batch = steps = 0
    if checkpoint.exists() and not args.smoke_steps:
        saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
        model.load_state_dict(saved["model"])
        optimizer.load_state_dict(saved["optimizer"])
        start_epoch, start_batch, steps = saved["epoch"], saved["next_batch"], saved["steps"]
        print(f"resumed epoch={start_epoch} batch={start_batch} steps={steps}", flush=True)
    for epoch in range(start_epoch, args.epochs):
        generator = torch.Generator().manual_seed(SEED + epoch)
        loader = DataLoader(Subset(dataset, train_indices), batch_size=args.batch_size,
                            shuffle=True, generator=generator)
        model.train()
        for batch_index, batch in enumerate(loader):
            if epoch == start_epoch and batch_index < start_batch:
                continue
            start = time.monotonic()
            optimizer.zero_grad(set_to_none=True)
            loss = loss_for(model(batch[0], batch[1]), batch, weights)
            loss.backward()
            torch.nn.utils.clip_grad_norm_((p for p in model.parameters() if p.requires_grad), 1.0)
            optimizer.step()
            steps += 1
            if steps == 1 or steps % 20 == 0:
                print(f"step={steps} epoch={epoch + 1} batch={batch_index + 1}/{len(loader)} "
                      f"loss={loss.item():.4f} seconds={time.monotonic() - start:.2f}", flush=True)
            if args.smoke_steps and steps >= args.smoke_steps:
                sample_metrics = evaluate(model, dataset, valid_indices[:args.batch_size * 2],
                                          weights, args.batch_size)
                print("smoke_validation", json.dumps(sample_metrics), flush=True)
                print("smoke_complete", flush=True)
                return
            if steps % args.checkpoint_every == 0:
                save_checkpoint(checkpoint, model, optimizer, epoch, batch_index + 1, steps)
                print(f"checkpoint_saved step={steps}", flush=True)
        metrics = evaluate(model, dataset, valid_indices, weights, args.batch_size)
        print("validation", json.dumps(metrics), flush=True)
        (args.output_dir / f"validation-epoch-{epoch + 1}.json").write_text(json.dumps(metrics, indent=2) + "\n")
        save_checkpoint(checkpoint, model, optimizer, epoch + 1, 0, steps)
    temporary = args.output_dir / "student_model.safetensors.tmp"
    save_file({key: value.contiguous() for key, value in model.state_dict().items()}, temporary)
    os.replace(temporary, args.output_dir / "student_model.safetensors")
    tokenizer.save_pretrained(args.output_dir)
    print("TRAINING_DONE", flush=True)


if __name__ == "__main__":
    main()
