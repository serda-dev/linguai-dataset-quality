# Deployment design — blocked pending VPS inspection

Build a single pinned application image for API, worker and tests, with an isolated PostgreSQL container and persistent database/artifact volumes. Test Compose must have its own database and mock teacher, no production secrets. Pre-deploy: checkout exact candidate SHA in an isolated VPS working directory, build exact image, run `make test` with Compose and clean up. Then review/merge PR and manually deploy main in a new isolated Coolify project `linguai-dataset-quality` (`production`). Keep push auto-deployment off unless a real gate can enforce tests first. Post-deploy check /health, /ready, DB, heartbeat, artifact write/read, teacher profile; do not enqueue labeling.

Coolify API token must travel only through HTTPS or an encrypted tunnel. No Coolify resources have been created, enumerated or altered; no capacity claims have been verified.
