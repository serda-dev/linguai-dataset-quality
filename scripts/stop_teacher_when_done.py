"""Hourly, fail-closed shutdown of the pinned Vast Teacher after campaign completion."""

import argparse
import fcntl
import json
import subprocess
import sys
from pathlib import Path

from apply_source_plan import requests_from_plan


APP_UUID = "svv47uqopqo1dstuws1sqysq"
INSTANCE_ID = 53864048
TEACHER_IMAGE = "ghcr.io/serda-dev/linguai-teacher-model:e347027"
VASTAI = Path("/home/serda/.local/bin/vastai")
PLAN = Path(__file__).resolve().parents[1] / "deploy/source_plan_2026-10-02.json"
MARKER = Path.home() / ".local/state/linguai/teacher-53864048-destroyed"
LOCK = MARKER.with_suffix(".lock")
SQL = """
SELECT coalesce(json_agg(row_to_json(t)), '[]'::json)
FROM (
  SELECT r.run_id, r.status, r.approved, r.cursor, r.max_scan, r.sample_size,
         count(j.id) AS jobs,
         count(j.id) FILTER (WHERE j.status = 'done') AS done,
         count(j.id) FILTER (WHERE j.status = 'exhausted') AS exhausted,
         count(j.id) FILTER (WHERE j.status IN ('pending', 'claimed')) AS unfinished,
         (SELECT count(*) FROM labels l WHERE l.run_id = r.run_id) AS labels
  FROM run_controls r LEFT JOIN jobs j ON j.run_id = r.run_id
  WHERE r.run_id LIKE '20261002-%' AND r.run_id NOT LIKE '20261002-probe-%'
  GROUP BY r.run_id
  ORDER BY r.run_id
) t;
"""


def run_command(command: list[str], timeout: int = 30) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # External command output can contain credentials or signed URLs.
        raise RuntimeError(f"{Path(command[0]).name} failed (exit {result.returncode})")
    return result.stdout.strip()


def read_campaign_rows() -> list[dict]:
    names = run_command(["docker", "ps", "--format", "{{.Names}}"], timeout=15).splitlines()
    postgres = [name for name in names if name.startswith(f"postgres-{APP_UUID}-")]
    if len(postgres) != 1:
        raise RuntimeError(f"expected one campaign PostgreSQL container, found {len(postgres)}")
    output = run_command(["docker", "exec", postgres[0], "psql", "-U", "quality", "-d", "quality",
                          "-At", "-c", SQL], timeout=30)
    rows = json.loads(output)
    if not isinstance(rows, list):
        raise RuntimeError("invalid campaign status response")
    return rows


def completion_status(plan: dict, rows: list[dict]) -> tuple[bool, str]:
    expected = {run["run_id"]: run["sample_size"] for run in requests_from_plan(plan)}
    actual = {row["run_id"]: row for row in rows}
    if len(actual) != len(rows) or set(actual) != set(expected):
        return False, "campaign run set incomplete or unexpected"
    total_done = 0
    total_jobs = 0
    for run_id, quota in expected.items():
        row = actual[run_id]
        if (row["status"] != "completed" or row["approved"] is not True
                or int(row["cursor"]) != int(row["max_scan"])
                or int(row["max_scan"]) != int(plan["max_scan_per_stratum"])
                or int(row["sample_size"]) != quota):
            return False, f"{run_id} has not completed its pinned scan"
        jobs, done = int(row["jobs"]), int(row["done"])
        exhausted, unfinished, labels = (int(row[key]) for key in ("exhausted", "unfinished", "labels"))
        if jobs != quota or unfinished or done + exhausted != jobs or labels != done:
            return False, f"{run_id} still has unfinished or inconsistent jobs"
        if done * 100 < quota * 90:
            return False, f"{run_id} has too many failed labels"
        total_done += done
        total_jobs += jobs
    if total_jobs != 40_000 or total_done * 100 < total_jobs * 98:
        return False, "campaign label acceptance below 98%"
    return True, f"DONE: {total_done}/{total_jobs} labels accepted"


def check_instance() -> None:
    details = json.loads(run_command([str(VASTAI), "--raw", "show", "instance", str(INSTANCE_ID)], timeout=30))
    if details.get("id") != INSTANCE_ID or details.get("image_uuid") != TEACHER_IMAGE:
        raise RuntimeError("Vast instance identity or Teacher image differs from pinned target")
    if details.get("actual_status") != "running":
        raise RuntimeError("pinned Vast instance is not running; manual review required")


def check_and_stop(check_only: bool) -> int:
    if MARKER.exists():
        print("ALREADY_DESTROYED: local success marker exists")
        return 0
    try:
        plan = json.loads(PLAN.read_text())
        complete, message = completion_status(plan, read_campaign_rows())
        print(message, flush=True)
        if not complete or check_only:
            return 0
        check_instance()
        run_command([str(VASTAI), "destroy", "instance", str(INSTANCE_ID), "--yes"], timeout=60)
        MARKER.parent.mkdir(parents=True, exist_ok=True)
        MARKER.write_text("DONE: Vast instance 53864048 destroyed after campaign completion\n")
        print("DESTROYED: Vast instance 53864048", flush=True)
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print(f"CHECK_FAILED: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true", help="Check completion without deleting anything")
    args = parser.parse_args()
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("CHECK_SKIPPED: another completion check is running")
            return 0
        return check_and_stop(args.check_only)


if __name__ == "__main__":
    raise SystemExit(main())
