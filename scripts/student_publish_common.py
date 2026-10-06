"""Shared checks for the Hugging Face student result archive."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path("/home/serda/.local/share/linguai-classification")
LEDGER = ROOT / ".published" / "verified.jsonl"
REPO_ID = "serda-dev/filtered-turkish-dataset"
PART_RE = re.compile(r"part-(\d{12})-(\d{12})\.parquet$")


def remote_path(source: str, name: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", source) or not PART_RE.fullmatch(name):
        raise ValueError(f"invalid part path: {source}/{name}")
    return f"data/{source}/{name}"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_ledger() -> dict[str, dict]:
    entries = {}
    if not LEDGER.exists():
        return entries
    with LEDGER.open() as stream:
        for line in stream:
            item = json.loads(line)
            path = remote_path(item["source"], item["name"])
            if item["remote_path"] != path:
                raise RuntimeError(f"invalid published path: {item}")
            if path in entries and entries[path] != item:
                raise RuntimeError(f"conflicting published entries: {path}")
            entries[path] = item
    return entries


def verify_remote(info, expected: dict) -> None:
    if info is None or info.path != expected["remote_path"] or info.size != expected["bytes"]:
        raise RuntimeError(f"remote file missing or has wrong size: {expected['remote_path']}")
    lfs = getattr(info, "lfs", None)
    remote_hash = lfs.get("sha256") if isinstance(lfs, dict) else getattr(lfs, "sha256", None)
    if remote_hash != expected["sha256"]:
        raise RuntimeError(f"remote SHA-256 mismatch: {expected['remote_path']}")


def append_verified(item: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as stream:
        stream.write(json.dumps(item, sort_keys=True) + "\n")
        stream.flush()
        import os
        os.fsync(stream.fileno())
