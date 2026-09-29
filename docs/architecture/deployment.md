# Deployment contract for the VPS agent

This repo supplies `Dockerfile`, production `compose.yaml`, isolated `compose.test.yaml`, `make test`, environment example and a smoke script. VPS agent checks out the exact candidate SHA, runs Docker tests before merging/deployment, then deploys `main` to a new isolated Coolify project with manual trigger; no GitHub Actions. Never run tests against production DB or real teacher. Post-deployment checks probe `/health`, `/ready`, worker heartbeat, teacher profile availability and artifact directory, without starting a labeling run. Resource sizing, host routing and Coolify integration are managed separately and remain unverified here.

`scripts/predeploy.sh` checks the exact clean candidate SHA and executes `make test`. The deployment operator must match deployed image identity to that SHA. `scripts/smoke.sh` performs non-destructive GET checks after deployment. The production approval token defaults to empty; an admin token alone cannot authorize large cumulative reservations.

## Coolify settings

Use a **Git repository Application**, branch `main`, **Docker Compose** build pack, repository root as Base Directory, and `compose.yaml` as Compose Location. This file is not named `docker-compose.yml`. A pasted Compose Empty resource does not track Git commits. Keep normal Compose deployment; custom build/start commands are unnecessary. Enter values in Coolify's runtime Environment Variables and reload the repository Compose definition after updating it. Set application routing, if used, on **api**, internal port **8000**. `/health` is the liveness endpoint; `/` has no page and a 404 there is expected. The project currently provides an API and CLI, not an administration web UI.

Official references: [Coolify Docker Compose](https://coolify.io/docs/applications/builds/docker-compose), [Docker dependency ordering](https://docs.docker.com/compose/how-tos/startup-order/).

## Before renting a GPU

1. Merge the deployment correction and deploy that exact commit. First run `sh scripts/predeploy.sh EXACT_COMMIT_SHA` in a clean checkout on the VPS; it uses the isolated mock teacher and does not require a GPU. Keep this test stack separate from the Coolify production stack.
2. Supply `POSTGRES_PASSWORD`, `DATABASE_URL`, `ADMIN_TOKEN`. For the bundled database the URL is `postgresql://quality:URL_ENCODED_PASSWORD@postgres:5432/quality`. Use the same password in both places; do not place raw reserved characters in the URL. Changing a password variable does not rotate an already-initialized database's password. Do not delete an existing database volume to fix a credential mismatch.
3. Leave teacher values empty. Deploy. `postgres` should become healthy, `init` should finish with **exit 0**, `api` should become healthy, and `worker` should remain running. `init` is intentionally a one-shot task with `restart: "no"`; it is not supposed to stay running. A nonzero init exit blocks API and worker startup.
4. Verify `/health` returns 200. In the worker terminal, `python -c 'from linguai_quality.settings import Settings; from linguai_quality.db import Store; s=Store(Settings.from_env().database_url); s.ping(); assert s.worker_alive(); print("DB and worker OK")'` checks the database and recent heartbeat without teacher inference. `/ready` and the full smoke script intentionally fail until teacher configuration exists.

The default host binding is `127.0.0.1:8000`; it does not serve `VPS_IP:8000` externally. A Coolify proxy uses the API's container port. If a host port is already allocated, select an unused `API_PORT`; the container and proxy target remain 8000. Preserve the `db_data` and `artifacts` named volumes through redeploys.

## After renting the GPU

The small teacher project still needs its inference server implementation, model download/loading, model revision and serving profile, endpoint exposure, schema-constrained or validated output, and calibration. PR #5 is an acceptance-feature bundle, not an installed teacher server. A Jupyter/SSH connection is not an OpenAI-compatible inference endpoint.

Once the teacher API works from the VPS, set `TEACHER_BASE_URL` with `/v1`, `TEACHER_API_KEY`, the exact served `TEACHER_MODEL` identifier, and a versioned `TEACHER_PROFILE`. Recreate/redeploy **both API and worker** to apply the values; merely editing environment variables or restarting an unchanged container does not replace its environment. Then run `scripts/smoke.sh`. Test a small agreed calibration set before activating a corpus run. `/ready` only checks that a teacher profile is configured; it never sends a teacher request.

The caller currently uses a 20-second HTTP timeout, with a 60-second claim lease and 30-second heartbeat freshness. Measure real inference latency; increasing only the timeout can cause lease/heartbeat problems. The 100,000-byte document ceiling is not a token-context guarantee. Model context and generation limits must fit the supplied prompt plus document and output. A statement of 48 GB VRAM alone does not establish model fit.

Corpus processing requires creating and approving a bounded run with the selected source/revision/config/split/text field, invoking `python -m linguai_quality.ingest --run-id RUN_ID` inside the worker container, and calling the authenticated `/runs/{id}/start`. Export is a separate CLI operation. Deployment and environment edits do not perform those steps automatically.

## Locate a failed deployment

- Before container creation: verify Compose Location and all three required secrets; inspect the first Compose interpolation/parser error.
- During image build: inspect the first Dockerfile/pip failure; do not classify it as a GPU issue.
- PostgreSQL healthy but `init` exits nonzero: inspect DB hostname/password and init logs. Teacher settings are no longer required by initialization.
- API/worker never start: inspect the `init` exit code and the dependency chain.
- API is healthy but access fails: verify API route/port and remember that `/` has no UI.
- `/ready` returns 503: verify teacher configuration, DB connectivity, worker heartbeat and artifact directory access. With empty teacher settings this is expected bootstrap behavior.

The actual Coolify deployment logs have not been inspected in this repository review. Preserve the first error and surrounding lines, redacting credentials, if the corrected stack still fails.
