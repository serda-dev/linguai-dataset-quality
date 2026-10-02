"""Resume one approved bounded HF run and activate its selected jobs on success."""
import argparse
import subprocess

from apply_source_plan import PLAN, requests_from_plan
import json

APP_UUID = "svv47uqopqo1dstuws1sqysq"


def worker_container():
    names = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}"], text=True).splitlines()
    workers = [name for name in names if name.startswith(f"worker-{APP_UUID}-")]
    if len(workers) != 1:
        raise RuntimeError(f"expected one running worker; found {len(workers)}")
    return workers[0]


def state(worker, run_id):
    code = ("from linguai_quality.db import Store; from linguai_quality.runs import get_run; "
            "from linguai_quality.settings import Settings; "
            f"print(get_run(Store(Settings.from_env().database_url), {run_id!r})['status'])")
    return subprocess.check_output(["docker", "exec", worker, "python", "-c", code], text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    approved_ids = {run["run_id"] for run in requests_from_plan(json.loads(PLAN.read_text()))}
    if args.run_id not in approved_ids:
        raise SystemExit("run id is not in pinned source plan")
    worker = worker_container()
    status = state(worker, args.run_id)
    if status in ("draft", "collecting"):
        subprocess.run(["docker", "exec", worker, "python", "-m", "linguai_quality.ingest",
                        "--run-id", args.run_id], check=True)
        status = state(worker, args.run_id)
    if status == "ready":
        code = ("from linguai_quality.db import Store; from linguai_quality.runs import transition; "
                "from linguai_quality.settings import Settings; "
                f"transition(Store(Settings.from_env().database_url), {args.run_id!r}, 'ready', 'active')")
        subprocess.run(["docker", "exec", worker, "python", "-c", code], check=True)
        status = state(worker, args.run_id)
    if status != "active":
        raise RuntimeError(f"run ended in unexpected state: {status}")
    print(args.run_id, status, flush=True)


if __name__ == "__main__":
    main()
