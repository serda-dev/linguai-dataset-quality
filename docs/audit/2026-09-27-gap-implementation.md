# Engineering audit — gap implementation candidate, 2026-09-27

Scope: candidate changes following the Requirement Analyst handoff `gap-closure-v1.md` and ADR 0003. This is a source review, not a claim of production readiness. Local validation: 15 passed, 8 PostgreSQL integration tests skipped; Python compilation, Compose YAML parsing and SQL grammar parsing passed. No Docker daemon/VPS access in this workstream.

## Traceability

| Previous finding | Candidate evidence | Status |
| --- | --- | --- |
| F1 full-run approval | `runs.py:approve_run` locks global reservation row and requires separate secret at/before the cumulative guard; draft/ready/active states gate `db.py:claim`. `/documents` can enroll only in an approved bounded manual run. | CODED; PostgreSQL race test awaits Docker |
| F2 HF streaming/sampling | `runs.py:stream_hf` requires pinned SHA and `streaming=True`; `ingest_records` verifies prefix digest after restart, bounded top-K stored in `sample_candidates`; no full corpus download path. | CODED generic adapter; exact source mappings/quotas still need user decision |
| F3 disk/export/leakage | `storage_budget` records candidate+document bytes under lock; `pg_database_size` and artifact free-space/byte limits fail closed; `export.py` writes atomic train-only Parquet with exact duplicate family ID. | CODED; live DB/disk tests and evaluation/near-duplicate policy still open |
| F4 Docker/live gate | `scripts/predeploy.sh` validates clean exact SHA and runs `make test`; `scripts/smoke.sh` probes health/readiness without jobs. | OPEN until other agent runs on exact candidate/deployed SHA |
| F5 provenance | Migration adds CPU format flags, family/exact sketch version, in-flight attempt metadata/endpoint fingerprint and versioned route relation; teacher JSON remains immutable. | CODED; crash/DB tests await Docker |
| F6 acceptance/failure | A–H have representability/routing unit tests; worker timeout, invalid JSON, unavailable endpoint, lease recovery, source interruption and export have unit/integration cases. | PARTIAL; semantic teacher calibration and actual DB restart still pending |
| F7 exact prompt | `contracts.py` reads prompt bytes without trimming. | RESOLVED locally |
| F8 config/migrations | Production Compose takes a pre-encoded DB URL as a secret, migration 001 is additive and versioned; attempt stores nonsecret endpoint fingerprint. | CODED; migration on populated DB requires Docker validation |

## Open findings

1. **BLOCKER** — Exact candidate Docker validation, including new migration on both empty and existing PR #2 schemas, has not run. Evidence: eight skipped tests and no Docker executable here. Action: VPS agent runs `sh scripts/predeploy.sh <commit>` in clean isolated checkout, records result and refuses deploy on failure. Status OPEN.
2. **HIGH** — Dataset IDs, revisions, configurations, text fields, licenses and per-source quotas are not approved. The generic adapter accepts explicit configuration only, and no real source run was started. Action: operator/user reviews source plans before production ingestion. Status OPEN for corpus use.
3. **HIGH** — Student evaluation split and near-duplicate grouping are unapproved. Export deliberately produces only `train`; its exact normalized family hash is not a near-duplicate detector. Action: decide split/near-duplicate policy before training/evaluation publication. Status OPEN for evaluation.
4. **MEDIUM** — PostgreSQL/WAL/backups and artifact free space on VPS have not been measured; configured byte caps bound application writes but do not replace operational disk monitoring. Action: measure and set budgets below real capacity. Status OPEN.
5. **MEDIUM** — A worker crash after a remote reply but before commit can repeat a billed inference. The started attempt remains visible and accepted labels stay unique, but exactly-once remote billing cannot be guaranteed. Action: operationally monitor interrupted attempts; accept or establish provider idempotency. Status ACCEPTED architectural limitation.

Product code was reviewed for accidental source deletion: unselected data is held only as a temporary candidate and evicted there; selected original documents remain immutable. No production resources, source corpora or GPU endpoints were accessed. A mock teacher cannot establish the semantic accuracy of scores; human-reviewed A–H calibration is required before large-scale labeling.
