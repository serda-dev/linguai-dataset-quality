# LinguAI Turkish CPT data quality

Early control-plane foundation for the authoritative `TURKISH_CPT_DATA_QUALITY_SPEC_v1`. The exact teacher prompt and reply schema are versioned under `prompts/` and `schemas/`. Teacher observations, policy routes and provenance are separate contracts.

## Validation

Run `make test` on a Docker host. It builds a candidate image, starts an isolated PostgreSQL/API/worker/mock teacher and executes unit and integration tests without a real GPU or production credentials. It removes test volumes on completion and exits nonzero on test failure. GitHub Actions are not used. Run this on the exact candidate commit before deployment.

Without Docker, `python -m pip install -e '.[test]' && python -m pytest -q` checks units; PostgreSQL integration tests skip and this **does not satisfy** the pre-deploy gate.

## Runtime

`compose.yaml` is a reference stack for a new isolated deployment. Set `POSTGRES_PASSWORD`, `ADMIN_TOKEN`, `TEACHER_BASE_URL`, `TEACHER_MODEL` and `TEACHER_PROFILE` as runtime secrets/settings. Do not use `.env.example` defaults in production. Only the API is bound to `127.0.0.1` by default; use an authenticated TLS ingress if exposing it. Set `TEACHER_API_KEY` privately when required. `/health` checks process; `/ready` checks PostgreSQL, a recent worker heartbeat, profile presence and artifact write/read. POST `/documents` requires a bearer admin token and explicitly queues one bounded document with source coordinates, sampling and labeling run IDs. Enrollment starts teacher work; do not submit a real corpus without an approved sampling/cost plan. The teacher sees only document ID and document text; a maximum of 100,000 UTF-8 bytes prevents unapproved sketch truncation.

Production HF adapters, sampling quotas, Parquet export/splits, student training, repair and migration versioning remain out of scope pending the decisions in `docs/requirements/open-questions.md`. VPS/Coolify operations are handled by a separate agent. Do not deploy this foundation as a completed corpus pipeline. No full 40k teacher labeling run is authorized.
