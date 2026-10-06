"""Destroy the four-GPU classifier after all parts are verified on Hugging Face."""

import fcntl
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from huggingface_hub import HfApi

from student_publish_common import ROOT, REPO_ID, LEDGER, PART_RE, load_ledger, remote_path, verify_remote

INSTANCE_ID = 54151776
IMAGE = "vastai/pytorch:cuda-12.4.1-auto"
VASTAI = "/home/serda/.local/bin/vastai"
DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
MARKER = Path(f"/home/serda/.local/state/linguai/student-{INSTANCE_ID}-destroyed")
CANDIDATE = MARKER.with_name(f"student-{INSTANCE_ID}-completion-pending.json")
QUIET_SECONDS = 600
SHARDS = {"fineweb2-tur-files-00-14": (0, 14), "fineweb2-tur-files-14-30": (14, 30)}


def check_files():
    if not all((ROOT / f"GPU{gpu}_DONE").exists() for gpu in range(4)):
        return None
    sources = {source["id"]: source for source in json.loads(
        (DEPLOY / "source_plan_2026-10-02.json").read_text())["sources"]}
    expected = (set(sources) - {"fineweb2-tur"}) | set(SHARDS)
    actual = {path.name for path in ROOT.iterdir() if path.is_dir() and not path.name.startswith(".")}
    if actual != expected:
        raise RuntimeError(f"local source set differs from pinned plan: {actual ^ expected}")
    files = json.loads((DEPLOY / "fineweb2_tur_files.json").read_text())["files"]
    ledger = load_ledger()
    if {item["source"] for item in ledger.values()} - expected:
        raise RuntimeError("published ledger contains an unexpected source")
    if any(ROOT.glob("*/part-*.parquet")):
        return None
    total = 0
    model_hash = None
    expected_metadata = []
    for name in sorted(expected):
        source = sources["fineweb2-tur" if name in SHARDS else name]
        directory = ROOT / name
        identity = json.loads((directory / "identity.json").read_text())
        done = json.loads((directory / "DONE.json").read_text())
        if (identity["source_id"] != source["id"] or identity["source_repo"] != source["repo"]
                or identity["source_revision"] != source["revision"]
                or identity["source_config"] != source["config"]
                or done["student_artifact_sha256"] != identity["student_artifact_sha256"]):
            raise RuntimeError(f"source identity mismatch: {name}")
        if model_hash is None:
            model_hash = identity["student_artifact_sha256"]
        elif model_hash != identity["student_artifact_sha256"]:
            raise RuntimeError(f"model hash mismatch: {name}")
        for filename in ("identity.json", "DONE.json"):
            data = (directory / filename).read_bytes()
            expected_metadata.append((f"metadata/{name}/{filename}", len(data),
                                      hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()))
        initial = 0
        expected_end = None
        if name in SHARDS:
            start, end = SHARDS[name]
            initial = files[start]["start_ordinal"]
            expected_end = files[end - 1]["start_ordinal"] + files[end - 1]["rows"]
            if (identity["file_start"], identity["file_end"], identity["initial_ordinal"],
                    identity["end_ordinal"]) != (start, end, initial, expected_end):
                raise RuntimeError(f"file range mismatch: {name}")
        position = initial
        count = 0
        entries = sorted((item for item in ledger.values() if item["source"] == name),
                         key=lambda item: item["start"])
        for item in entries:
            match = PART_RE.fullmatch(item["name"])
            if (not match or int(match[1]) != position or int(match[2]) <= position
                    or item["end"] != int(match[2])
                    or item["remote_path"] != remote_path(name, item["name"])
                    or item["student_artifact_sha256"] != model_hash):
                raise RuntimeError(f"non-contiguous published output: {item['remote_path']}")
            position = int(match[2])
            count += item["rows"]
        if (position != done["rows_scanned"] or count != done["classified"]
                or (expected_end is not None and position != expected_end)):
            return None
        total += count
    api = HfApi()
    paths = list(ledger)
    for offset in range(0, len(paths), 100):
        group = paths[offset:offset + 100]
        remote = {item.path: item for item in api.get_paths_info(
            REPO_ID, group, repo_type="dataset", expand=True)}
        for path in group:
            verify_remote(remote.get(path), ledger[path])
    for offset in range(0, len(expected_metadata), 100):
        group = expected_metadata[offset:offset + 100]
        remote = {item.path: item for item in api.get_paths_info(
            REPO_ID, [path for path, _, _ in group], repo_type="dataset", expand=True)}
        for path, size, blob_id in group:
            info = remote.get(path)
            if info is None or info.size != size or info.blob_id != blob_id:
                raise RuntimeError(f"missing source metadata on Hugging Face: {path}")
    return total


def completion_fingerprint() -> str:
    digest = hashlib.sha256(LEDGER.read_bytes())
    for gpu in range(4):
        digest.update((ROOT / f"GPU{gpu}_DONE").read_bytes())
    return digest.hexdigest()


def quiet_period_complete(count: int, fingerprint: str, now: float) -> bool:
    state = json.loads(CANDIDATE.read_text()) if CANDIDATE.exists() else None
    if state is not None and state.get("count") == count and state.get("fingerprint") == fingerprint:
        return now - state["first_verified_at"] >= QUIET_SECONDS
    temporary = CANDIDATE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"count": count, "fingerprint": fingerprint,
                                     "first_verified_at": now}, sort_keys=True) + "\n")
    temporary.replace(CANDIDATE)
    return False


def main():
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    with MARKER.with_suffix(".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if MARKER.exists():
            print("ALREADY_DESTROYED")
            return
        count = check_files()
        if count is None:
            CANDIDATE.unlink(missing_ok=True)
            print("IN_PROGRESS")
            return
        fingerprint = completion_fingerprint()
        if not quiet_period_complete(count, fingerprint, time.time()):
            print("WAITING_FOR_SECOND_VERIFIED_CHECK_AFTER_10_MINUTES")
            return
        if check_files() != count or completion_fingerprint() != fingerprint:
            CANDIDATE.unlink(missing_ok=True)
            print("COMPLETION_CHANGED_DURING_SECOND_CHECK")
            return
        details = subprocess.check_output([VASTAI, "--raw", "show", "instance", str(INSTANCE_ID)], text=True)
        instance = json.loads(details)
        if "instances" in instance and instance["instances"] is None:
            MARKER.write_text(f"ALREADY_DESTROYED: {count} classified rows verified on Hugging Face\n")
            print(MARKER.read_text().strip())
            return
        if instance.get("id") != INSTANCE_ID or instance.get("image_uuid") != IMAGE:
            raise RuntimeError("Vast instance identity mismatch")
        if instance.get("actual_status") not in {"running", "stopped"}:
            raise RuntimeError("Vast instance state is unexpected; manual review needed")
        subprocess.run([VASTAI, "destroy", "instance", str(INSTANCE_ID), "-y"], check=True)
        MARKER.write_text(f"DESTROYED: {count} classified rows verified on Hugging Face\n")
        print(MARKER.read_text().strip())


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"STOP_CHECK_FAILED: {error}", file=sys.stderr)
        raise
