"""Bounded train-only Parquet export with atomic artifact publication."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .db import Store
from .settings import Settings
from .runs import family_id, format_flags


def export_labels(store: Store, artifact_dir: str, *, max_bytes: int,
                  min_free_bytes: int, batch_size: int = 256) -> tuple[str, int]:
    if max_bytes <= 0 or min_free_bytes < 0 or batch_size <= 0:
        raise ValueError("invalid export budget")
    root = Path(artifact_dir)
    if not root.is_dir() or shutil.disk_usage(root).free <= min_free_bytes:
        raise ValueError("artifact disk reserve reached")
    schema = pa.schema([
        ("doc_id", pa.string()), ("original_text", pa.string()), ("content_family", pa.string()),
        ("teacher_label_json", pa.string()), ("format_flags", pa.list_(pa.string())),
        ("source_dataset", pa.string()), ("source_revision", pa.string()),
        ("source_config", pa.string()), ("source_split", pa.string()),
        ("teacher_model", pa.string()), ("teacher_profile", pa.string()),
        ("teacher_prompt_version", pa.string()), ("teacher_schema_version", pa.string()),
        ("document_hash", pa.string()), ("sampling_run_id", pa.string()),
        ("labeling_run_id", pa.string()), ("policy_version", pa.string()),
        ("route", pa.string()), ("split", pa.string()),
    ])
    fd, temporary = tempfile.mkstemp(prefix=".export-", suffix=".parquet.tmp", dir=root)
    os.close(fd)
    rows = 0
    try:
        with store.connect() as conn:
            with conn.cursor(name="quality_export") as cursor:
                cursor.execute("""SELECT l.run_id,l.doc_id,l.sampling_run_id,l.teacher_label,l.teacher_model,
                    l.teacher_profile,l.prompt_version,l.schema_version,l.document_hash,
                    d.original_text,d.content_family,d.format_flags,d.source,d.revision,d.config,d.split,
                    r.policy_version,r.route FROM labels l JOIN documents d ON d.id=l.doc_id
                    JOIN route_decisions r ON r.run_id=l.run_id AND r.doc_id=l.doc_id
                    WHERE r.policy_version='turkish_cpt_routing_v1' ORDER BY l.run_id,l.doc_id""")
                with pq.ParquetWriter(temporary, schema=schema, compression="zstd") as writer:
                    while batch := cursor.fetchmany(batch_size):
                        if shutil.disk_usage(root).free <= min_free_bytes:
                            raise ValueError("artifact disk reserve reached")
                        output = [{
                            "doc_id": item["doc_id"], "original_text": item["original_text"],
                            "content_family": item["content_family"] or family_id(item["original_text"]),
                            "teacher_label_json": json.dumps(item["teacher_label"], ensure_ascii=False, sort_keys=True),
                            "format_flags": item["format_flags"] or format_flags(item["original_text"]),
                            "source_dataset": item["source"], "source_revision": item["revision"],
                            "source_config": item["config"], "source_split": item["split"],
                            "teacher_model": item["teacher_model"], "teacher_profile": item["teacher_profile"],
                            "teacher_prompt_version": item["prompt_version"], "teacher_schema_version": item["schema_version"],
                            "document_hash": item["document_hash"], "sampling_run_id": item["sampling_run_id"],
                            "labeling_run_id": item["run_id"], "policy_version": item["policy_version"],
                            "route": item["route"], "split": "train",
                        } for item in batch]
                        writer.write_table(pa.Table.from_pylist(output, schema=schema))
                        rows += len(output)
                        if Path(temporary).stat().st_size > max_bytes:
                            raise ValueError("export byte budget reached")
        size = Path(temporary).stat().st_size
        if size > max_bytes or shutil.disk_usage(root).free < min_free_bytes:
            raise ValueError("export byte budget or disk reserve reached")
        with open(temporary, "rb") as reader:
            os.fsync(reader.fileno())
            digest = hashlib.file_digest(reader, "sha256").hexdigest()
        filename = f"quality-train-{digest}.parquet"
        destination = root / filename
        os.replace(temporary, destination)
        with store.connect() as conn:
            conn.execute("""INSERT INTO artifact_exports(id,relative_path,sha256,bytes,row_count)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""", (digest, filename, digest, size, rows))
        return filename, rows
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-only", action="store_true", required=True)
    parser.parse_args()
    settings = Settings.from_env()
    print(export_labels(Store(settings.database_url), settings.artifact_dir,
                        max_bytes=settings.max_export_bytes,
                        min_free_bytes=settings.min_artifact_free_bytes))


if __name__ == "__main__":
    main()
