# Non-functional requirements

- NFR-01: Stay within an **73 GB measured free** root disk (2026-09-26); establish a reserve and enforce a lower application quota after Docker/image/PostgreSQL/backup budgets are measured and apply a fail-closed budget before ingestion.
- NFR-02: Fit the measured 8 CPU/15 GiB RAM VPS with bounded streaming buffers, bounded concurrency and bounded retries.
- NFR-03: Recover after API/worker/database restarts without losing accepted labels or duplicating billed work where a teacher call's outcome is known. Remote calls cannot provide guaranteed exactly-once billing.
- NFR-04: Run meaningful automated tests in Docker with isolated PostgreSQL and deterministic mock teacher; no GitHub-hosted CI or real GPU dependency.
- NFR-05: Keep secrets server-side; redact teacher requests and sampled source text from operational logs unless a deliberate retention policy is defined. Coolify token only via encrypted transport.
- NFR-06: Provide inspectable run metadata, job counts, failures, worker heartbeat, and migration/version records without leaking private documents.
