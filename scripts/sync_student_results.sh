#!/usr/bin/env bash
set -euo pipefail

instance_id=${1:-54145120}
destination=/home/serda/.local/share/linguai-classification
key=/home/serda/.ssh/linguai_vast_teacher
url=$(/home/serda/.local/bin/vastai ssh-url "$instance_id")
read -r host port < <(python3 -c 'import sys,urllib.parse; u=urllib.parse.urlparse(sys.argv[1]); print(u.hostname,u.port)' "$url")

mkdir -p "$destination"
exclude_file=$(mktemp)
trap 'rm -f "$exclude_file"' EXIT
python3 - "$destination/.published/verified.jsonl" "$exclude_file" <<'PY'
import json
import re
import sys
from pathlib import Path

ledger = Path(sys.argv[1])
with open(sys.argv[2], "w") as output:
    if ledger.exists():
        for line in ledger.open():
            item = json.loads(line)
            source, name = item["source"], item["name"]
            if not re.fullmatch(r"[a-z0-9-]+", source) or not re.fullmatch(r"part-\d{12}-\d{12}\.parquet", name):
                raise RuntimeError("invalid published file in rsync exclusion ledger")
            output.write(f"/{source}/{name}\n")
PY
available_kb=$(df -Pk "$destination" | awk 'NR==2 {print $4}')
if (( available_kb < 8388608 )); then
  echo "Less than 8 GiB free at $destination; refusing to sync" >&2
  exit 1
fi

rsync -a --partial-dir=.rsync-partial --exclude-from="$exclude_file" \
  --include='*/' --include='part-*.parquet' --include='identity.json' \
  --include='DONE.json' --include='ALL_DONE' --include='GPU?_DONE' \
  --include='job.log' --include='job-gpu*.log' --exclude='*' \
  -e "ssh -i $key -o IdentitiesOnly=yes -o ConnectTimeout=10 -p $port" \
  "root@$host:/workspace/linguai-classification/" "$destination/"

python3 - "$destination" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
summary = {}
for source in sorted(path for path in root.iterdir() if path.is_dir()):
    parts = list(source.glob("part-*.parquet"))
    if parts:
        summary[source.name] = {"parts": len(parts), "bytes": sum(part.stat().st_size for part in parts),
                                "done": (source / "DONE.json").exists()}
print(json.dumps(summary, sort_keys=True))
PY
