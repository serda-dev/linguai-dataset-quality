# ADR 0001: PostgreSQL-backed worker queue (proposed)

Status: Proposed pending original product contract and VPS inspection.

One dedicated worker claims jobs with `FOR UPDATE SKIP LOCKED` and expiring leases. PostgreSQL also holds source and label state. This avoids another broker on an 8 CPU/16 GB user-estimated VPS, provides transactional accepted-label uniqueness, and supports restart recovery. A remote teacher request cannot be in the DB transaction; a crash can repeat billed calls. Record attempt identity and preserve the at-least-once limitation. Revisit only after measured throughput or external job requirements prove this insufficient.
