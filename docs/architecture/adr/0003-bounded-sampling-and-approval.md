# ADR 0003 — bounded streaming selection and durable approval

Status: accepted for implementation of generic plumbing; no dataset is approved by this ADR.

## Source adapter and selection

One dataset-specific configuration supplies HF repo, immutable commit revision, config, split and a text field. The adapter calls `load_dataset(..., streaming=True, revision=...)`, yields one normalized record at a time, and rejects missing/non-string fields. The iterator is not materialized. A single ingestion process serializes one sampling run under a PostgreSQL advisory lock. A run stores seed, finite `max_scan`, quota, cursor and rolling prefix digest; on restart it replays exactly the prefix to validate source order before processing new rows. An interruption before a checkpoint may replay a record, so selection and cursor advance in one transaction.

Selected sample is the K smallest keyed SHA-256 ranks among the first N eligible stream rows. The database stores at most K selected originals per run; when a better rank arrives, evict the worst candidate without deleting an original referenced by another run/job/label. After exactly N rows or source exhaustion, commit the selected IDs to jobs in a single controlled transition. Prefix digest is a chain over ordinal and original record hash, including rejected records, so a reordered pinned source fails closed. This is uniform within the bounded window, not a claim about the whole remote corpus.

## Approval and spend

`run_controls` stores draft/collecting/ready/active/paused/completed state and `approved_limit`. `teacher_budget` serializes global job reservations. Ordinary administrator may approve a bounded run only while its quota and cumulative reservations stay below a configurable ceiling (<40k). Reaching the full-run threshold requires a separate runtime approval secret; its hash is never logged and a durable approval record records run ID, quota and time, without the secret. Workers claim only jobs of active runs. No source-name or untrusted document text is given to the teacher by default.

## Storage and output

Enforce configured aggregate original-text byte budget with a DB row lock, and compare actual artifact free space to reserve before writing. Persist format flags as CPU metadata, exact-original sketch version and content group hash. Accepted label table remains append-only; add versioned route records to support reapplication. Export scans accepted labels in stable order with bounded batches into `ParquetWriter`, writes to a temporary file, checks size/free space after batches, fsyncs/renames, then registers SHA-256 and metadata. The first release exports `split=train` only. Exact normalized duplicate groups share `family_id`; no claim about near duplicates or an evaluation set.

## Failures and migration

An additive numbered SQL migration extends existing PR #2 tables; bootstrap runs first for a fresh DB, then migrations under a PostgreSQL advisory lock and in a transaction. A teacher attempt row is inserted before network access; on stale lease, leave an interrupted attempt for reconciliation, never accept a stale result. Invalid JSON/timeout/unavailability are bounded failures. Changed source ordering or revision pauses ingestion with an explicit error. A disk budget failure pauses work without deleting accepted data. Logs report run/job identifiers and exception class only.

No broker, GPU service, auto-published evaluation set or arbitrary code execution is introduced. The generic adapter is deliberately disabled unless explicit source config is provided.
