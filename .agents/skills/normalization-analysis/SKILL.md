---
name: normalization-analysis
description: Analyze Santos V Portal PostgreSQL/Drizzle table ownership and consistency risks without changing schema or data.
---

# Normalization Analysis — Santos V Portal

Read `AGENTS.md`, `docs/architecture/DB_CONTRACT.md`, `server/db/schema.ts`,
relevant migrations, and data-owning services. Audit only; do not edit schema/data in
this pass.

For each table/field, identify owner, identity key, lifecycle, mutation path, indexes,
retention/audit need, and UCP relationship. Portal owns sessions, OAuth states, local
capabilities, MDC/RMS records/statuses, and access audit; UCP owns account/character/
faction truth. Flag ambiguous ownership, mutable mirrors, missing uniqueness/indexes,
non-atomic consume/update flows, unsafe retention, or rank-range inference. Give
evidence and the smallest migration-safe recommendation.
