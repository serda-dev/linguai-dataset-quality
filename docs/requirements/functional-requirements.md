# Functional requirements

FR-01: Stream approved, pinned Hugging Face dataset revisions through source-specific adapters; never download complete corpora. Reject unsupported mappings.

FR-02: Preserve original text; derive sketches and CPU format metadata separately. Stable identity includes source location, revision and text hash; persist sampling provenance and seed.

FR-03: Use the exact v2 prompt, user payload and v1 teacher reply schema. No source name in the default request. Enforce exact document ID match and reject all malformed responses.

FR-04: Teacher produces only one content type, independent L/C/I/N/S/U scores and material noise flags. Language alone may be null for absent natural language. Do not infer ideological or format-based penalties.

FR-05: Apply versioned routing outside teacher labels; never rewrite an accepted quality label when policy changes. Valuable noisy documents remain repair/review candidates.

FR-06: Persist replaceable teacher profile, attempts and provenance, bounded retries, claims, resumption and no duplicate accepted labels for one labeling run. Keep old labels on teacher replacement.

FR-07: Expose non-destructive API health/readiness and worker heartbeat. Ensure bounded artifact storage and explicit disk failure.

FR-08: Export training rows with full provenance only after split/leakage and retention decisions; target student MoganBERT-TR for type, six scores and noise.

FR-09: Never launch the full 40k teacher run without explicit approval. Production source ingestion and real teacher access require approved source/profile configuration.
