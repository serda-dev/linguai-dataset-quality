"""Run manually for one previously registered and approved HF source run."""
import argparse

from .db import Store
from .runs import get_run, ingest_records, stream_hf
from .settings import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    settings = Settings.from_env()
    store = Store(settings.database_url)
    run = get_run(store, args.run_id)
    if not run["approved"] or run["status"] not in ("draft", "collecting"):
        raise SystemExit("run must be approved and unstarted")
    ingest_records(store, args.run_id, stream_hf(run), max_document_bytes=settings.max_document_bytes,
                   max_database_bytes=settings.max_database_bytes)


if __name__ == "__main__":
    main()
