#!/bin/sh
set -eu
: "${SMOKE_BASE_URL:=http://127.0.0.1:8000}"
python - "$SMOKE_BASE_URL" <<'PY'
import json
import sys
import urllib.request

base = sys.argv[1].rstrip('/')
for path in ('/health', '/ready'):
    with urllib.request.urlopen(base + path, timeout=5) as response:
        payload = json.load(response)
        if response.status != 200:
            raise SystemExit(f'{path}: {response.status}')
        if path == '/health' and payload.get('status') != 'ok':
            raise SystemExit('/health: unexpected response')
        if path == '/ready' and (payload.get('status'), payload.get('worker'), payload.get('teacher_profile')) != ('ready', 'alive', 'configured'):
            raise SystemExit('/ready: dependency not ready')
print('Non-destructive production smoke passed; no teacher job created.')
PY
