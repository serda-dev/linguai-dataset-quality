# Deployment bootstrap audit and correction

Scope: repository deployment/bootstrap and teacher connection boundary at main `39c17b4`. No access to the running VPS, Coolify configuration, deployment logs or rented GPU. Requirement/architecture decisions are in `docs/requirements/deployment-bootstrap.md`.

| Finding | Class / severity | Evidence and impact | Correction / validation | Confidence |
| --- | --- | --- | --- | --- |
| Missing database password in example | Confirmed configuration defect / high | `compose.yaml` requires `POSTGRES_PASSWORD`; `.env.example` omitted it. Following the example leaves Compose interpolation blocked. | Add all three required settings; real Compose CLI rejects each missing setting and accepts supplied settings. | High |
| GPU configuration required during DB setup | Bootstrap design defect / medium | `init_db.py` read all of `Settings`; Compose required teacher fields. An unavailable GPU configuration prevented unrelated schema initialization. | Init reads only DB URL; teacher configuration is optional for bootstrap; worker/start guards reject work until configured. Unit tests cover init, each missing teacher field, no claims/mutations, and readiness. | High |
| Example production endpoint is test-only | Configuration defect / medium | `.env.example` named `mock-teacher`, which exists only in `compose.test.yaml`. Presence-only readiness cannot detect this unreachable endpoint. | Empty production teacher defaults and explicit connection instructions. Live endpoint reachability remains a deployment check. | High |
| Document/retry settings silently ignored by production Compose | Confirmed runtime configuration defect / medium | `MAX_DOCUMENT_BYTES` / `MAX_ATTEMPTS` were in settings and example but absent from production `environment`. | Forward both settings; rendered Compose verified with non-default values on API and worker. | High |
| No explicit API container healthcheck | Operational gap / low | Production Compose declared only DB health, although API exposes `/health`. | Add Python-based liveness check without a curl package dependency. Real container execution remains pending. | High |

## Verification performed

- `PYTHONPATH=src /tmp/linguai-deploy-venv/bin/python -m pytest -q`: **24 passed, 8 skipped**. PostgreSQL integration tests skip because no Docker daemon/test database is available here. One upstream Starlette TestClient deprecation warning was emitted.
- Official Docker Compose standalone CLI **v2.39.4**, `config --format json`: production bootstrap with empty teacher settings succeeds; each missing required database/admin value fails; init receives only DB URL; teacher and non-default document/retry settings reach both runtime services.
- Isolated `compose.test.yaml` renders without production credentials.
- Authoritative teacher prompt and label schema are unchanged. No DB migration is required. No real teacher requests, corpus ingestion, GitHub Actions tests or production deployment occurred.

## Remaining acceptance

Run `make test` on the VPS's Docker host, deploy the corrected commit and verify PostgreSQL, init exit 0, API liveness, worker heartbeat and volume access. Actual Coolify failure cause is **unconfirmed** without its first error/log excerpt. The current 20-second teacher timeout must be assessed together with the 60-second lease and 30-second heartbeat freshness on real inference.

GPU rental is not yet evidence that labeling can start immediately. GPU serving code/model setup, API connectivity and a small calibration run remain. PR #5 contains teacher features only. Dataset source/run creation, bounded ingestion and explicit start/export are separate operations documented in the runbook.
