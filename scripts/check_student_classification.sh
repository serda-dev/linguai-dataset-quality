#!/usr/bin/env bash
set -euo pipefail

cd /home/serda/linguai-dataset-quality
/usr/bin/flock -n /tmp/linguai-classification-sync.lock bash -c '
  set -euo pipefail
  if [[ -f /home/serda/.local/state/linguai/student-54151776-destroyed ]]; then exit 0; fi
  /home/serda/.local/share/linguai-training/venv/bin/python scripts/publish_student_results.py
  scripts/sync_student_results.sh 54151776
  /home/serda/.local/share/linguai-training/venv/bin/python scripts/publish_student_results.py
  /home/serda/.local/share/linguai-training/venv/bin/python scripts/stop_student_when_done.py
  if [[ -f /home/serda/.local/state/linguai/student-54151776-destroyed ]]; then exit 0; fi
  if [[ -f /home/serda/.local/state/linguai/student-54151776-completion-pending.json ]]; then exit 0; fi
  credit=$(/home/serda/.local/bin/vastai show user --raw | python3 -c "import json,sys; print(json.load(sys.stdin)[\"credit\"])")
  if python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) < 5 else 1)" "$credit"; then
    echo "Credit below $5 ($credit); stopping GPU to protect budget" >&2
    /home/serda/.local/bin/vastai stop instance 54151776
  fi
'
