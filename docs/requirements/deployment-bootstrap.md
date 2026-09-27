# Deployment bootstrap correction

## Requirement analysis

The operator must be able to deploy PostgreSQL, schema initialization, API and an idle worker before renting the teacher GPU. Required database/admin credentials must be documented consistently. The exact teacher prompt, labeling schema, routing policy and persistent run data remain governed by the existing contracts.

Acceptance: missing database/admin credentials prevent deployment; missing teacher endpoint/model/profile permit bootstrap but prevent run activation and worker claims. No retry budget is consumed while unconfigured. `/health` proves API liveness; `/ready` continues to return 503 until database, worker, artifacts and teacher configuration are available. A configured teacher is not proof of a reachable or calibrated model. A later environment update and container recreation enable the existing worker path.

## Architecture decision

Keep the current four-service Compose stack and named volumes. `init` needs only `DATABASE_URL`; runtime services share explicit environment values. Unconfigured teacher fields default to empty, not a fake production endpoint. The API rejects `/start` and the worker checks configuration before claiming. Add an API liveness healthcheck using Python already in the image. Keep the one-shot `init` with `restart: "no"` and the successful-completion dependency. No schema migration or new infrastructure is needed.

The current 20-second teacher HTTP timeout, 60-second job lease and 30-second heartbeat freshness require joint review if live GPU latency needs a larger timeout. This correction does not independently increase one of those values.

## Scope and evidence

Confirmed at main `39c17b4`: `.env.example` omits required `POSTGRES_PASSWORD`; it points to a mock service absent from production; `MAX_DOCUMENT_BYTES` and `MAX_ATTEMPTS` are documented but not forwarded by production Compose; teacher fields are mandatory even for database initialization. Actual Coolify error logs are unavailable, so these findings do not identify the exact failed production phase.

Implementation touches Compose, environment example, settings, initialization, run-start guard, worker guard, deployment instructions and focused tests. Docker tests with the mock teacher are required on a Docker host before production acceptance. GPU serving code is a separate deliverable; PR #5 only describes its acceptance features.
