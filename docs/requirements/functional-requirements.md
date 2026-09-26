# Functional requirements (partial, awaiting original product specification)

- FR-01: Stream each approved Hugging Face source through a dataset-specific adapter to a normalized, immutable document. Never stage a complete source corpus on VPS.
- FR-02: Record reproducible sampling parameters, source revision, source location/identifier where available, selected record identity, and selection decision. Preserve separate calibration and eventual production runs.
- FR-03: Retain source document bytes or lossless references as allowed by the source; enrichment and labels must never overwrite original content.
- FR-04: Preserve teacher request, model/profile version, prompt/schema version, attempt outcome, validation status and label provenance for each accepted label. Replace a Vast endpoint through configuration without modifying job state.
- FR-05: Persist resumable jobs and retryable claims in PostgreSQL. Avoid duplicate accepted labels after worker restart.
- FR-06: Reject malformed teacher JSON or labels violating the **supplied** schema. Store rejection metadata safely and allow bounded retry.
- FR-07: Preserve structured content as an eligible content type; never equate markup, lists, or tables with garbage solely by their format.
- FR-08: Produce reproducible classifier training exports (Parquet expected); define split and leakage policy after product contract is supplied.
- FR-09: Provide non-destructive `/health`, `/ready`, worker, teacher-configuration and artifact path smoke checks.
- FR-10: Enforce an explicit authorization gate for the full 40k teacher labeling run.

Open: exact source adaptations, sampling proportions, teacher prompt, type taxonomy, score scales, noise flags, review UI/API, classifier output shape, and accepted export fields. None are implicitly approved by this partial file.
