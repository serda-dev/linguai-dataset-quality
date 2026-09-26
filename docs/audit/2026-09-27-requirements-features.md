# Engineering Auditor — requirements and features, 2026-09-27

Scope: `main` commit `eb6c7ad6c3ab696e3dbe42b11a6c4477e39fcf35` (merged PR #2), authoritative spec/prompt/schema, requirement/architecture documents, four feature files, implementation and tests. Review only: no product code changed. Local `python -m pytest -q`: **5 passed, 3 skipped** (PostgreSQL unavailable); `compileall` passed. No Docker/VPS/production result is claimed.

## Feature traceability

| Scenario | Evidence and status |
| --- | --- |
| `quality-contract`: valuable noisy text; null language for code; wrong teacher ID | `contracts.py` and unit tests cover the three cases, but no Gherkin runner executes the feature. **PARTIAL** |
| `streaming`: bounded pinned dataset sample, interruption and resume | No HF adapter, sampling seed/stratum or stream checkpoint exists. **NOT IMPLEMENTED** |
| `teacher`: crashed claim and unique accepted label | `db.py` uses leases and unique `(run_id,doc_id)`; integration test targets expiry/stale token, but was skipped. **PARTIAL/UNVERIFIED** |
| `teacher`: malformed JSON and bounded retry | JSON parsing and worker catch exist; integration test uses wrong ID rather than invalid JSON and calls the client directly, not `worker.step`. **PARTIAL/UNTESTED** |
| `teacher`: endpoint replacement | Worker reads profile at startup, so restart can change endpoint; no replacement test or endpoint fingerprint. **PARTIAL/UNTESTED** |
| `deployment`: test failure prevents deployment | `make test` exists, but no enforced link from tested candidate SHA to deployment or execution evidence here. **EXTERNAL GATE UNVERIFIED** |
| `deployment`: post-deploy smoke without workload | `/health` and `/ready` check DB, heartbeat, profile presence, artifact write/read; no automated smoke script or live result. **PARTIAL** |
| `deployment`: 40k approval | Authenticated `/documents` queues arbitrary repeated requests; no run cap or approval record. **NOT ENFORCED** |

A–H acceptance exemplars appear as prose in the spec; Gherkin covers B and C only. A, D, E, F, G and H have no runnable scenarios. A mock teacher cannot validate semantic quality; human-reviewed calibration remains necessary.

## Findings

### F1 — BLOCKER: full-run approval is not enforced

Description: a bearer admin can POST `/documents` repeatedly, creating jobs and arbitrary run IDs without an approval state, quota or explicit start. Evidence: `api.py:62-68`, `db.py:27-44`, `schema.sql:7-21`, `features/deployment.feature` final scenario. Impact: unapproved large teacher spend is possible. Recommended action: separate run creation from enrollment; default paused, store approved quota, atomically enforce counts and explicit start, test concurrent requests. Status: **OPEN**, high confidence; blocks real teacher production use.

### F2 — BLOCKER: HF streaming and reproducible sampling are absent

Description: no dataset-specific adapter, pinned source checkpoint, seeded sample or interrupted-stream recovery; `sample_decisions` contains only doc ID and supplied run ID. Evidence: `src/linguai_quality/`, `schema.sql:10-13`, `features/streaming.feature`, FR-01/FR-02. Impact: cannot execute or reproduce corpus selection. Recommended action: approve dataset revisions/configs/mappings and strata; implement bounded streaming, seed/selection provenance and interruption tests. Status: **OPEN**, high confidence; blocks corpus run.

### F3 — BLOCKER: aggregate disk, export and leakage controls are absent

Description: per-document byte limit exists, aggregate/run quota does not; no Parquet exporter or duplicate-family split. Evidence: `db.py:29-43`, `schema.sql`, FR-07/FR-08. Impact: repeated enrollment can fill DB/WAL; no leakage-safe training export. Recommended action: measure disk, reserve headroom and enforce aggregate quotas; approve split/retention, implement atomic Parquet export and tests. Status: **OPEN**, high confidence; blocks bulk ingest/training.

### F4 — BLOCKER: Docker and deployment gates lack evidence

Description: three integration tests skipped locally; no exact candidate SHA Docker result or production smoke result here. PR #2 was merged while its audit recorded this gate open. Evidence: local test result, `README.md`, `features/deployment.feature`. Impact: SQL recovery, Compose and deployment behavior remain unverified. Recommended action: VPS agent runs `make test` on exact deployed SHA and records outcome, then non-destructive smoke; block on failure. Status: **OPEN**, high confidence; blocks a claim of live validation.

### F5 — HIGH: documented data contracts diverge from storage

Description: no derived sketch, CPU format flags or extraction version; original text is sent whole. Attempts record only completed calls and lack prompt/schema or in-flight records. Labels store route in the same row rather than a separate policy result. Data contract says unique acceptance key includes model/profile, while SQL uniquely keys `(run_id,doc_id)`. Evidence: `db.py:50-76`, `worker.py:15-24`, `schema.sql:1-37`, `docs/requirements/data-contracts.md`. Impact: crash trace/provenance and relabeling/export do not meet written contract. Recommended action: define sketch/extractor; store format flags, attempt start/completion, and versioned route separately; enforce immutable profile per run or revise label key. Status: **OPEN**, high confidence; resolve before real corpus labeling.

### F6 — HIGH: acceptance and failure tests are incomplete

Description: Gherkin files have no runner; no A–H semantic calibration; no worker invalid JSON/timeout/unavailable, endpoint replacement, DB restart, disk limit or HF interruption test. Evidence: `features/`, `tests/`, `docs/tests/test-plan.md`. Impact: five passing local tests do not establish product conformance. Recommended action: tie scenarios to falsifiable tests for each implemented boundary; retain semantic cases for reviewed teacher calibration. Status: **OPEN**, high confidence.

### F7 — MEDIUM: exact prompt bytes are changed at runtime

Description: `contracts.py:11-12` calls `.rstrip("\n")` on both prompt files, stripping their final newlines. Impact: request payload differs from unchanged versioned resource. Recommended action: read without trimming and assert request equality to file content, or explicitly version the transformation. Status: **OPEN**, high confidence.

### F8 — MEDIUM: configuration and migration risks

Description: `compose.yaml:18` interpolates arbitrary `POSTGRES_PASSWORD` into a URL without escaping reserved characters. `schema.sql` uses `IF NOT EXISTS` bootstrap, not migrations. `teacher.py` records no endpoint fingerprint. Impact: password rotation may break startup; populated DB schema can silently drift. Recommended action: safe connection configuration/encoding, numbered additive migrations before evolving tables, non-secret endpoint identity if required. Status: **OPEN**, high confidence on URL and migration.

## Decision

**Live testing is not the only remaining work.** F1–F3 are independent implementation blockers; F4 is the separate Docker/production validation blocker. This repository currently contains a foundation, not a complete corpus-quality pipeline. Keep the full 40k teacher run stopped. This is an audit, not an implementation approval or a claim about the external VPS agent's current status.
