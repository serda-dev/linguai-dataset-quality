# Data flow — provisional

Pinned HF revision/config → streaming source adapter → normalized identity and metadata → seeded, stratified selection → persisted run decision/document → PostgreSQL queued job → leased worker → TeacherClient → strict product-schema validation → append-only attempt and accepted label → versioned Parquet export with provenance and leakage-safe split.

Commit the selection before contacting the teacher. Keep raw content immutable; store derived sketch/metadata separately. Retry only bounded transient failures, record permanent invalid data distinctly, and pin every transformation version. Use a duplicate-family identifier in split assignment after the original contract determines normalization and near-duplicate policy.
