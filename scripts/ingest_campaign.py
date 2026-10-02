"""Resume the pinned source campaign inside a restartable VPS container."""
import json
import logging
import time
from pathlib import Path

from linguai_quality.db import Store
from linguai_quality.runs import get_run, ingest_records, stream_hf, transition
from linguai_quality.settings import Settings

from apply_source_plan import requests_from_plan

LOG = logging.getLogger("linguai.ingest_campaign")
PLAN = Path(__file__).resolve().parents[1] / "deploy/source_plan_2026-10-02.json"


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy_logger in ("httpx", "httpcore", "huggingface_hub", "fsspec"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
    settings = Settings.from_env()
    plan = json.loads(PLAN.read_text())
    if settings.max_document_bytes != plan["max_document_bytes"]:
        raise RuntimeError("document byte limit differs from pinned plan")
    store = Store(settings.database_url)
    for request in requests_from_plan(plan):
        run_id = request["run_id"]
        state = get_run(store, run_id)
        if any(state[key] != request[key] for key in
               ("source", "revision", "config", "split", "text_field", "seed",
                "max_scan", "sample_size", "stratum")) or not state["approved"]:
            raise RuntimeError(f"registered plan mismatch: {run_id}")
        if state["status"] in ("draft", "collecting"):
            LOG.info("ingest_start run=%s cursor=%s", run_id, state["cursor"])
            started = time.monotonic()
            ingest_records(store, run_id, stream_hf(state),
                           max_document_bytes=settings.max_document_bytes,
                           max_database_bytes=settings.max_database_bytes)
            LOG.info("ingest_ready run=%s seconds=%.1f", run_id, time.monotonic() - started)
            state = get_run(store, run_id)
        if state["status"] == "ready":
            transition(store, run_id, "ready", "active")
            LOG.info("labeling_active run=%s", run_id)
        elif state["status"] not in ("active", "completed"):
            raise RuntimeError(f"unexpected run state: {run_id}: {state['status']}")
    LOG.info("all bounded source runs activated")


if __name__ == "__main__":
    main()
