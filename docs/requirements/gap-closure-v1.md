# Requirement Analyst handoff — audit gap closure v1

Status: implementable for a bounded, explicitly configured source run. Authority: `TURKISH_CPT_DATA_QUALITY_SPEC_v1`, exact teacher prompt/schema and Engineering Auditor findings F1–F8. This extension does not approve any specific HF dataset, quota distribution, teacher spend, license, train/test split or repair method.

## Actors and outcomes

- Operator: registers an explicit source ID, pinned revision, config, split and text-field mapping, a finite scan window, deterministic seed and quota; starts/resumes streaming. Unknown fields and changed stream order fail closed.
- Approver: supplies a separate secret to authorize a large run. A normal admin bearer credential alone cannot start a run whose configured quota or cumulative reservation reaches the full-run threshold.
- Worker: claims only authorized jobs, records attempt start and outcome, retains original documents, labels and profile provenance across restarts.
- Researcher: exports versioned Parquet envelopes bounded by disk budget; without an approved evaluation split, every row is marked `train`, preventing accidental train/test leakage. Exact normalized duplicate families share the same group ID.

## Acceptance conditions

1. A run cannot enqueue beyond its quota. Crossing the configured cumulative unapproved ceiling (strictly below 40k) requires the separate full-run approval credential and a durable approval record. Missing approval leaves all original rows and labels unchanged. Even 39,999 + 1 across multiple runs is rejected without approval. Production starts paused.
2. Dataset loading uses `streaming=True` and a pinned immutable revision. It never calls a full-dataset download. Source-field mapping is explicit. Malformed records are counted and skipped under a bounded failure ceiling; missing field mapping fails run configuration.
3. Given identical revision, scan window and seed, the bounded top-K keyed-hash sample and document identities are identical. Restart from a persisted cursor replays and verifies a rolling digest of the prefix before resuming; a changed or reordered stream fails without queuing teacher jobs. Selected records are committed before labeling begins.
4. An aggregate logical-text byte budget and actual free-space reserve are enforced before persisting a candidate or artifact. Reaching a limit pauses the run without deleting originals. No automatic full 40k run.
5. Export writes a temporary bounded Parquet artifact and atomically renames it; metadata includes checksum and policy/provenance. Without a reviewed evaluation split, only `train` is emitted. Re-running export is deterministic for identical accepted labels.
6. A teacher attempt is recorded before network access. Timeout, invalid JSON, wrong ID and unavailable endpoint preserve failure class and retries; a crash leaves a visible unfinished attempt and lease recovery can resume. Prompt payload equals versioned resource bytes. No raw text or secrets in operational logs.
7. Tests cover authorization race, resume-order mismatch, field mapping, duplicate candidate, disk exhaustion, lease replacement, teacher failure and Parquet envelope. `make test` remains the single Docker gate; no GitHub Actions or real teacher calls.

## Scope and decisions

SAFE_DEFAULT: source configuration requires an explicit field mapping and 40-character commit SHA; unknown license/rights require operator acknowledgement and no automatic registration. A scan window is finite, sample quota <= scan window, all selected documents use their exact text as teacher sketch within the existing byte limit. Large-run threshold uses 40,000 cumulative reserved jobs, but a configurable lower unapproved ceiling defaults to 5,000 as a cost guard. No evaluation split is emitted until leakage/strata policy is decided. A content group is exact normalized text hash; near-duplicate leakage is not claimed solved.

NEEDS_DECISION before production corpus sampling: approved dataset IDs/configs/revisions/fields/licenses, quota distribution and retention. NEEDS_DECISION before evaluation export: near-duplicate-family strategy and train/test split. NEEDS_DECISION before GPU teacher: model/profile endpoint, budget and real teacher calibration. These decisions do not prevent implementing and testing the bounded generic plumbing with fake iterators.
