# Engineering audit — quality contract foundation

Scope: current first slice only. Reviewed requirements and architecture, source, Docker topology, schema, source immutability, retry/idempotency, recovery, provenance, security, disk growth, sampling, leakage, operational runbook and tests. This is a skeptical self-review; it is not an independent second reviewer and no live Docker/PostgreSQL execution has occurred.

| Severity | Finding, evidence, recommended action | Status |
| --- | --- | --- |
| BLOCKER for deploy | Docker/PostgreSQL integration on exact candidate commit was not executed: Docker is absent here and VPS is assigned to another agent. Run `make test` on VPS, record SHA and full outcome before deployment. | OPEN |
| HIGH for full corpus | Production HF streaming adapters, approved mappings/revisions and deterministic sampling quotas are missing; only explicit bounded enrollment exists. Obtain source contracts and implement adapters/stream interruption tests before any corpus run. | OPEN; prevents corpus run |
| HIGH for full corpus | Export, duplicate-family split, Parquet validation and student pipeline absent. Decide leakage policy and implement/verifiably test before classifier training/export. | OPEN; prevents training/export |
| MEDIUM | `schema.sql` is idempotent bootstrap, not a versioned migration framework. For a new empty DB it is safe; introduce additive numbered migrations before changing a populated schema. | OPEN |
| MEDIUM | Attempt history records failure class, model and profile but not endpoint fingerprint or prompt digest. Keep credentials redacted and add nonsecret fingerprint if endpoint-level provenance matters. | OPEN |
| MEDIUM | Source content is retained in PostgreSQL per enrolled document with a per-document byte limit; total corpus byte budget is not implemented. Add aggregate run/disk limits before bulk enrollment. | OPEN; prevents bulk run |
| LOW | Mock teacher proves transport/schema behavior but cannot verify semantic scoring quality. Calibrate against human-reviewed A–H cases after user approves teacher spend. | OPEN |

Resolved during audit: sampling run was initially stored only in `documents`, which would lose provenance for the same document selected twice. A separate `sample_decisions` table and job/label sampling ID now preserve both. Expired final-attempt claims are marked exhausted; stale lease tokens cannot store labels. SQL claim clause order was corrected. No source text or secrets are written to attempts/logs.

Conclusion: reviewable foundation PR, **not production-ready**. Docker gate remains a blocking finding; do not merge/deploy as a complete product until the owner evaluates this report and VPS validation passes. Existing production resources are outside scope.
