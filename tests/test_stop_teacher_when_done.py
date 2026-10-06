"""Guard against premature destruction when the campaign is incomplete."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stop_teacher_when_done import completion_status  # noqa: E402
from apply_source_plan import requests_from_plan  # noqa: E402


PLAN = json.loads((Path(__file__).resolve().parents[1] / "deploy/source_plan_2026-10-02.json").read_text())


def completed_rows():
    return [{"run_id": run["run_id"], "status": "completed", "approved": True,
             "cursor": 100_000, "max_scan": 100_000, "sample_size": run["sample_size"],
             "jobs": run["sample_size"], "done": run["sample_size"], "exhausted": 0,
             "unfinished": 0, "labels": run["sample_size"]}
            for run in requests_from_plan(PLAN)]


def test_only_exact_completed_campaign_returns_done():
    rows = completed_rows()
    assert completion_status(PLAN, rows)[0]
    rows[0]["status"] = "active"
    assert not completion_status(PLAN, rows)[0]
    rows = completed_rows()[:-1]
    assert not completion_status(PLAN, rows)[0]


def test_inconsistent_jobs_and_mass_failure_block_destroy():
    rows = completed_rows()
    rows[0]["unfinished"] = 1
    assert not completion_status(PLAN, rows)[0]
    rows = completed_rows()
    rows[0]["done"] = 0
    rows[0]["exhausted"] = rows[0]["jobs"]
    rows[0]["labels"] = 0
    assert not completion_status(PLAN, rows)[0]
