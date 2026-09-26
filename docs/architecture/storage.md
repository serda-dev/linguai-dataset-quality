# Storage

PostgreSQL tables: `documents` with immutable source coordinates, content hash and text; `labeling_runs`; `jobs` with unique run/document, claim token, lease, bounded attempts; `attempts` with outcome and safe error class, no raw payload; `labels` with unique run/document and full model/profile/prompt/schema/hash provenance; `worker_state` heartbeat. Database initialized by an idempotent schema script for this new, empty project only; future schema changes require explicit migrations. No destructive change is authorized.

The artifact directory is isolated and writable for a non-destructive smoke check. No Parquet export is implemented until split, leakage and retention contracts are approved. A configurable document byte limit blocks unbounded DB storage; no full corpus cache is used.
