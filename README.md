# LinguAI Turkish CPT data quality

Early control-plane foundation for the authoritative `TURKISH_CPT_DATA_QUALITY_SPEC_v1`. The exact teacher prompt and reply schema are versioned under `prompts/` and `schemas/`. Teacher observations, policy routes and provenance are separate contracts.

The bounded run workflow is described in `docs/requirements/gap-closure-v1.md` and ADR 0003. The source owner must approve the exact HF repository, config, split, revision SHA, text field and usage rights. Nothing in this repository approves a particular upstream corpus or teacher spend.

## Validation

Run `make test` on a Docker host. It builds a candidate image, starts an isolated PostgreSQL/API/worker/mock teacher and executes unit and integration tests without a real GPU or production credentials. It removes test volumes on completion and exits nonzero on test failure. GitHub Actions are not used. Run this on the exact candidate commit before deployment.

On the VPS, `sh scripts/predeploy.sh EXACT_COMMIT_SHA` checks a clean checkout and runs that gate. After deployment, `SMOKE_BASE_URL=http://127.0.0.1:8000 sh scripts/smoke.sh` checks health, DB, heartbeat, teacher-profile presence and artifact write/read without creating a job. The deployment operator must verify the deployed image actually matches the tested commit; no GitHub Actions gate is assumed.

Without Docker, `python -m pip install -e '.[test]' && python -m pytest -q` checks units; PostgreSQL integration tests skip and this **does not satisfy** the pre-deploy gate.

## Runtime

`compose.yaml` is a reference stack for a new isolated deployment. Set `POSTGRES_PASSWORD`, `ADMIN_TOKEN`, `TEACHER_BASE_URL`, `TEACHER_MODEL` and `TEACHER_PROFILE` as runtime secrets/settings. Do not use `.env.example` defaults in production. Only the API is bound to `127.0.0.1` by default; use an authenticated TLS ingress if exposing it. Set `TEACHER_API_KEY` privately when required. `/health` checks process; `/ready` checks PostgreSQL, a recent worker heartbeat, profile presence and artifact write/read. POST `/documents` requires a bearer admin token and explicitly queues one bounded document with source coordinates, sampling and labeling run IDs. Enrollment starts teacher work; do not submit a real corpus without an approved sampling/cost plan. The teacher sees only document ID and document text; a maximum of 100,000 UTF-8 bytes prevents unapproved sketch truncation.

Approval of concrete HF sources, quota distribution, evaluation split, near-duplicate detection, student training and repair remain out of scope pending `docs/requirements/open-questions.md`. VPS/Coolify operations are handled by a separate agent. The implemented generic bounded adapter and train-only export are not approval of a production corpus or the full 40k teacher run.

## Explicit run lifecycle

Create an admin-authenticated `/runs` entry with a finite `max_scan`, `sample_size`, seed and explicit text-field mapping. Use an immutable 40-character HF commit revision and acknowledge source rights. Runs begin paused (`draft`). `/runs/{id}/approve` reserves the sample quota atomically; once cumulative reservations reach `UNAPPROVED_JOB_CEILING` (default 5,000), a separate `X-Full-Run-Approval` token is mandatory. This token is never stored in the database or committed. For an approved HF run, execute `python -m linguai_quality.ingest --run-id RUN_ID` in the application image; it streams a bounded sample, verifies prior prefix on resume and finishes in `ready`. Manually enrolled test documents use a `manual` source and `/collect`, `/documents`, `/finish`. `/runs/{id}/start` alone lets the worker claim jobs; `/pause` stops new claims. Do not set the separate approval token or call `/start` for 40k work until the user explicitly authorizes it.

For training data without an approved evaluation split, `python -m linguai_quality.export --train-only` writes an atomic, quota-bound Parquet export to the artifact volume. Every row is `train`; no evaluation set or near-duplicate guarantee is claimed. `MAX_DATABASE_BYTES`, `MAX_EXPORT_BYTES` and `MIN_ARTIFACT_FREE_BYTES` bound storage; measure actual disk free space before setting production values. Legacy jobs from before the run-control migration remain unstarted and need an explicit migration decision before processing.
