# LinguAI Turkish CPT data quality

Early control-plane foundation for the authoritative `TURKISH_CPT_DATA_QUALITY_SPEC_v1`. The exact teacher prompt and reply schema are versioned under `prompts/` and `schemas/`. Teacher observations, policy routes and provenance are separate contracts.

The bounded run workflow is described in `docs/requirements/gap-closure-v1.md` and ADR 0003. The source owner must approve the exact HF repository, config, split, revision SHA, text field and usage rights. The 2026-10-02 four-source, 40,000-job campaign is recorded separately in `docs/operations/2026-10-02-bounded-source-plan.md`; it authorizes only that bounded plan, not a full-corpus download.

## Validation

Run `make test` on a Docker host. It builds a candidate image, starts an isolated PostgreSQL/API/worker/mock teacher and executes unit and integration tests without a real GPU or production credentials. It removes test volumes on completion and exits nonzero on test failure. GitHub Actions are not used. Run this on the exact candidate commit before deployment.

On the VPS, `sh scripts/predeploy.sh EXACT_COMMIT_SHA` checks a clean checkout and runs that gate. After deployment, `SMOKE_BASE_URL=http://127.0.0.1:8000 sh scripts/smoke.sh` checks health, DB, heartbeat, teacher-profile presence and artifact write/read without creating a job. The deployment operator must verify the deployed image actually matches the tested commit; no GitHub Actions gate is assumed.

Without Docker, `python -m pip install -e '.[test]' && python -m pytest -q` checks units; PostgreSQL integration tests skip and this **does not satisfy** the pre-deploy gate.

## Runtime

`compose.yaml` can deploy before a GPU is rented. Set `POSTGRES_PASSWORD`, `DATABASE_URL` and `ADMIN_TOKEN` as runtime secrets/settings; `.env.example` lists all required values. The database DSN must use the same password, with reserved characters URL-encoded, and the internal host `postgres:5432`. Teacher settings may remain empty: the worker sends heartbeats but does not claim jobs, and `/runs/{id}/start` returns 503. Later set `TEACHER_BASE_URL` (ending in `/v1`), `TEACHER_MODEL`, `TEACHER_PROFILE` and, if required, `TEACHER_API_KEY`, then recreate the API and worker containers. See [the deployment runbook](docs/architecture/deployment.md).

Only the API is bound to `127.0.0.1` by default. `/health` checks process liveness and is used by Compose; `/ready` checks PostgreSQL, a recent worker heartbeat, teacher configuration and artifact write/read. `/ready` intentionally returns 503 before teacher configuration is supplied; a 200 response does not prove live teacher reachability or quality. POST `/documents` requires a bearer admin token and queues one bounded document with source coordinates, sampling and labeling run IDs. Only explicitly activated approved runs are claimed. The teacher sees only document ID and document text; a default maximum of 100,000 UTF-8 bytes prevents unapproved sketch truncation. `MAX_DOCUMENT_BYTES` and `MAX_ATTEMPTS` are forwarded by Compose.

Evaluation split, near-duplicate detection, student training and repair remain out of scope pending `docs/requirements/open-questions.md`. The bounded 2026-10-02 source and quota decision is in `docs/operations/2026-10-02-bounded-source-plan.md`. The generic adapter and train-only export are not approval to download entire upstream corpora.

## Explicit run lifecycle

Create an admin-authenticated `/runs` entry with a finite `max_scan`, `sample_size`, seed and explicit text-field mapping. Use an immutable 40-character HF commit revision and acknowledge source rights. Runs begin paused (`draft`). `/runs/{id}/approve` reserves the sample quota atomically; once cumulative reservations reach `UNAPPROVED_JOB_CEILING` (default 5,000), a separate `X-Full-Run-Approval` token is mandatory. This token is never stored in the database or committed. For an approved HF run, execute `python -m linguai_quality.ingest --run-id RUN_ID` in the application image; it streams a bounded sample, verifies prior prefix on resume and finishes in `ready`. Manually enrolled test documents use a `manual` source and `/collect`, `/documents`, `/finish`. `/runs/{id}/start` alone lets the worker claim jobs; `/pause` stops new claims. Do not set the separate approval token or call `/start` for 40k work until the user explicitly authorizes it.

For training data without an approved evaluation split, `python -m linguai_quality.export --train-only` writes an atomic, quota-bound Parquet export to the artifact volume. Every row is `train`; no evaluation set or near-duplicate guarantee is claimed. `MAX_DATABASE_BYTES`, `MAX_EXPORT_BYTES` and `MIN_ARTIFACT_FREE_BYTES` bound storage; measure actual disk free space before setting production values. Legacy jobs from before the run-control migration remain unstarted and need an explicit migration decision before processing.
