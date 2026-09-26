# Test handoff — audit gap closure

Unit cases encode the eight authoritative A–H labels as representation/routing contracts; they **do not** certify that a real teacher will assign those labels. `tests/test_runs.py` tests pinned streaming call, deterministic rank and fail-closed prefix replay with a fake stream. Docker integration covers cumulative approval, rollback on byte-budget failure, sampled-job persistence, lease recovery, invalid teacher JSON, provenance and train-only Parquet readback. The mock endpoint is deterministic and GPU-free.

Pending VPS execution: run `make test` against isolated PostgreSQL; record exact SHA and output. Then non-destructive `scripts/smoke.sh` on deployed stack. Human-reviewed teacher calibration on A–H and approved source adapters/strata are required before a large real teacher run. No arbitrary coverage target is used.
