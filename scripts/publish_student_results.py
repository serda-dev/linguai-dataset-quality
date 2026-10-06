"""Upload complete Parquet parts and remove only remotely verified VPS copies."""

import argparse
import json
import os
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import pyarrow.parquet as pq
from huggingface_hub import CommitOperationAdd, HfApi

from student_publish_common import (ROOT, REPO_ID, PART_RE, append_verified,
                                    file_sha256, load_ledger, remote_path, verify_remote)

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
SHARDS = {"fineweb2-tur-files-00-14": "fineweb2-tur",
          "fineweb2-tur-files-14-30": "fineweb2-tur"}


def paths_info(api: HfApi, paths: list[str]) -> dict:
    if not paths:
        return {}
    return {item.path: item for item in api.get_paths_info(REPO_ID, paths, repo_type="dataset", expand=True)}


def verify_after_commit(api: HfApi, items: list[dict]):
    for attempt in range(6):
        infos = paths_info(api, [item["remote_path"] for item in items])
        try:
            for item in items:
                verify_remote(infos.get(item["remote_path"]), item)
            return
        except RuntimeError:
            if attempt == 5:
                raise
            time.sleep(2 ** attempt)


def publish_metadata(api: HfApi, source: str, directory: Path):
    for name in ("identity.json", "DONE.json"):
        path = directory / name
        if not path.is_file():
            continue
        remote = f"metadata/{source}/{name}"
        info = paths_info(api, [remote]).get(remote)
        data = path.read_bytes()
        import hashlib
        git_blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if info is not None and info.size == len(data) and info.blob_id == git_blob:
            continue
        api.upload_file(path_or_fileobj=path, path_in_repo=remote, repo_id=REPO_ID,
                        repo_type="dataset", commit_message=f"Update {source} metadata")
        info = paths_info(api, [remote]).get(remote)
        if info is None or info.size != len(data) or info.blob_id != git_blob:
            raise RuntimeError(f"metadata upload could not be verified: {remote}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-files", type=int, default=0, help="Limit one run for an initial canary")
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    if args.max_files < 0 or not 1 <= args.batch_size <= 16:
        raise ValueError("invalid upload limit or batch size")
    api = HfApi()
    user = api.whoami()
    if user.get("name") != "serda-dev":
        raise RuntimeError("unexpected Hugging Face account")
    repo = api.repo_info(REPO_ID, repo_type="dataset")
    if repo.id != REPO_ID or not repo.private:
        raise RuntimeError("target dataset identity or privacy changed")
    source_plan = {item["id"]: item for item in json.loads(
        (DEPLOY / "source_plan_2026-10-02.json").read_text())["sources"]}
    ledger = load_ledger()
    candidates = []
    for directory in sorted(path for path in ROOT.iterdir() if path.is_dir() and not path.name.startswith(".")):
        source = source_plan.get(SHARDS.get(directory.name, directory.name))
        if source is None:
            raise RuntimeError(f"unexpected source directory: {directory}")
        identity = json.loads((directory / "identity.json").read_text())
        if (identity["source_id"] != source["id"] or identity["source_repo"] != source["repo"]
                or identity["source_revision"] != source["revision"]
                or identity["source_config"] != source["config"]):
            raise RuntimeError(f"source identity mismatch: {directory.name}")
        publish_metadata(api, directory.name, directory)
        for part in sorted(directory.glob("part-*.parquet")):
            match = PART_RE.fullmatch(part.name)
            if match is None:
                raise RuntimeError(f"invalid part name: {part}")
            path = remote_path(directory.name, part.name)
            item = {"source": directory.name, "name": part.name, "remote_path": path,
                    "start": int(match[1]), "end": int(match[2]),
                    "bytes": part.stat().st_size, "sha256": file_sha256(part),
                    "rows": pq.read_metadata(part).num_rows,
                    "student_artifact_sha256": identity["student_artifact_sha256"]}
            if path in ledger:
                if ledger[path] != item:
                    raise RuntimeError(f"local part differs from published ledger: {path}")
                part.unlink()
                continue
            candidates.append((part, item))
    if args.max_files:
        candidates = candidates[:args.max_files]
    published = 0
    for offset in range(0, len(candidates), args.batch_size):
        batch = candidates[offset:offset + args.batch_size]
        infos = paths_info(api, [item["remote_path"] for _, item in batch])
        additions = []
        for part, item in batch:
            info = infos.get(item["remote_path"])
            if info is None:
                additions.append(CommitOperationAdd(path_in_repo=item["remote_path"], path_or_fileobj=part))
            else:
                verify_remote(info, item)
        if additions:
            api.create_commit(repo_id=REPO_ID, repo_type="dataset", operations=additions,
                              commit_message=f"Add {len(additions)} classified Parquet parts",
                              num_threads=4)
        verify_after_commit(api, [item for _, item in batch])
        for part, item in batch:
            append_verified(item)
            part.unlink()
            ledger[item["remote_path"]] = item
            published += 1
        print(json.dumps({"published_parts": published, "remaining_snapshot": len(candidates)-published}), flush=True)
    print(json.dumps({"published_parts": published, "verified_total": len(ledger)}), flush=True)


if __name__ == "__main__":
    main()
