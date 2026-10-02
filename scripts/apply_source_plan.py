"""Register the pinned bounded HF runs; activation and ingestion are separate."""
import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1] / "deploy/source_plan_2026-10-02.json"
STRATA = ("normal", "noisy_edge", "structured")


def requests_from_plan(plan):
    requests = []
    for source in plan["sources"]:
        for stratum in STRATA:
            requests.append({
                "run_id": f"20261002-{source['id']}-{stratum}",
                "source": source["repo"], "revision": source["revision"],
                "config": source["config"], "split": source["split"],
                "text_field": source["text_field"], "seed": plan["seed"],
                "max_scan": plan["max_scan_per_stratum"],
                "sample_size": source["quotas"][stratum],
                "license_ack": True, "stratum": stratum,
            })
    assert len(requests) == 21
    assert sum(item["sample_size"] for item in requests) == 40_000
    assert len({item["run_id"] for item in requests}) == len(requests)
    return requests


def post(base, path, token, body=None, full_token=""):
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    if full_token:
        headers["X-Full-Run-Approval"] = full_token
    request = urllib.request.Request(base.rstrip("/") + path, method="POST",
                                     headers=headers, data=json.dumps(body or {}).encode())
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Create and approve the pinned runs")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text())
    runs = requests_from_plan(plan)
    if not args.apply:
        for run in runs:
            print(run["run_id"], run["sample_size"], run["source"], run["config"])
        print("runs", len(runs), "reserved_jobs", sum(run["sample_size"] for run in runs))
        return
    admin = os.environ["LINGUAI_ADMIN_TOKEN"]
    approval = os.environ["LINGUAI_FULL_APPROVAL_TOKEN"]
    for run in runs:
        try:
            created = post(args.base_url, "/runs", admin, run)
            approved = post(args.base_url, f"/runs/{run['run_id']}/approve", admin,
                            full_token=approval)
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"{run['run_id']}: HTTP {exc.code}; stop and inspect the run") from None
        print(run["run_id"], "created", created, "approved", approved, flush=True)


if __name__ == "__main__":
    main()
