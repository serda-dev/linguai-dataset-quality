# System overview — provisional architecture

FastAPI control API and one worker share PostgreSQL for configuration, source runs, document identities, sample decisions, jobs, claims, attempts and accepted label provenance. Filesystem-backed Parquet stores exports; PostgreSQL retains artifact metadata and checksums. Each approved HF dataset gets an adapter yielding the same immutable document contract from a streaming iterator. An OpenAI-compatible TeacherClient talks to a replaceable Vast.AI endpoint; mock client implements the same boundary in tests. The worker holds a bounded lease on queued jobs and validates replies against the as-yet-unsupplied schema. No permanent GPU service on VPS.

This is a design proposal subject to exact product specification and inspection of live deployment constraints. No schema/migration or provider-specific implementation is approved yet.
