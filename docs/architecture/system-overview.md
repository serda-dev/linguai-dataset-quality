# Architecture — contracted foundation

The VPS control plane owns PostgreSQL, one FastAPI API process and one worker process. The disposable teacher provides OpenAI-compatible inference; it owns no durable state. PostgreSQL holds immutable documents and accepted labels, sampling/labeling run identities, jobs, leases, attempts and provenance. An isolated persistent directory is reserved for future atomic Parquet artifacts; this first slice does not export or retain source corpora.

The API currently exposes health/readiness and run/job management behind a runtime admin bearer token. The worker claims jobs with row locking and expiring leases, makes teacher requests through one client boundary, validates strictly and stores an accepted label once. Runtime teacher profile and credentials are read from environment; changing endpoint never rewrites historical provenance. The API does not expose original text or secrets.

Source adapters must implement a common normalized document contract; until dataset revisions/mappings are approved, only explicitly supplied documents can be enrolled through the protected API. Production HF ingestion, teacher calibration and export are distinct future gates, not implied by this foundation.
