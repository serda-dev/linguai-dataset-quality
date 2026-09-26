# ADR 0002 — Exact teacher contract and bounded initial slice

Decision: keep the supplied system prompt and JSON Schema as exact versioned files, enforce ID equality beyond the schema, isolate deterministic routing from immutable teacher observations, and enroll only selected bounded documents until HF adapter mappings and sampling quotas are approved. Use PostgreSQL row leases rather than another queue service. Teacher output cannot carry source or provenance fields.

Rationale: prevents source bias, ambiguous data types, accidental full corpus downloads and invented production sampling policy. Consequence: real HF ingestion, classifier export, model training and automated repair are not in this slice. Operations must configure a runtime teacher profile and explicitly create a labeling run.
