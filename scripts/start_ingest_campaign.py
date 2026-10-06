"""Start the pinned campaign from the deployed Coolify worker image on this VPS."""
import json
import os
import subprocess
from pathlib import Path

APP_UUID = "svv47uqopqo1dstuws1sqysq"
NAME = "linguai-ingest-campaign"
REPO = Path(__file__).resolve().parents[1]
PRIVATE_ENV = Path.home() / ".config/linguai/ingest_campaign.env"
KEEP_ENV = ("DATABASE_URL", "ADMIN_TOKEN", "ARTIFACT_DIR", "MAX_DOCUMENT_BYTES",
            "MAX_DATABASE_BYTES", "HF_HOME", "HF_TOKEN")


def main():
    if subprocess.run(["docker", "container", "inspect", NAME], capture_output=True).returncode == 0:
        raise SystemExit(f"{NAME} exists; inspect it before creating another")
    names = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}"], text=True).splitlines()
    workers = [name for name in names if name.startswith(f"worker-{APP_UUID}-")]
    if len(workers) != 1:
        raise SystemExit(f"expected one deployed worker; found {len(workers)}")
    worker = json.loads(subprocess.check_output(["docker", "inspect", workers[0]]))[0]
    env = dict(item.split("=", 1) for item in worker["Config"]["Env"] if "=" in item)
    if any(key not in env or not env[key] for key in KEEP_ENV):
        raise SystemExit("deployed worker is missing a required ingestion setting")
    if env["MAX_DOCUMENT_BYTES"] != "20000":
        raise SystemExit("deployed document limit differs from pinned plan")
    mounts = [item for item in worker["Mounts"] if item["Destination"] == "/artifacts"]
    if len(mounts) != 1 or mounts[0]["Type"] != "volume":
        raise SystemExit("expected the shared artifacts Docker volume")
    PRIVATE_ENV.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    PRIVATE_ENV.write_text("".join(f"{key}={env[key]}\n" for key in KEEP_ENV))
    PRIVATE_ENV.chmod(0o600)
    command = [
        "docker", "run", "-d", "--name", NAME, "--restart", "on-failure:20",
        "--network", APP_UUID, "--user", "10001:999", "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,size=2g", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--env-file", str(PRIVATE_ENV),
        "--env", "PYTHONPATH=/runner/src:/runner/scripts",
        "--mount", f"type=volume,src={mounts[0]['Name']},dst=/artifacts",
        "--mount", f"type=bind,src={REPO},dst=/runner,readonly",
        worker["Config"]["Image"], "python", "/runner/scripts/ingest_campaign.py",
    ]
    container_id = subprocess.check_output(command, text=True).strip()
    print(NAME, container_id[:12])


if __name__ == "__main__":
    main()
