# Data contracts — unresolved product fields

## Normalized document (design boundary, not final schema)
Stable source namespace, source revision/config/split, source-native key if supplied, immutable raw content/reference, content digest, source metadata and extraction version. Define fallback identity for sources without stable keys before implementation. Processing annotations must be separate from raw content.

## Sampling decision
Run ID, seed, stratum, source iterator position/checkpoint semantics, candidate ID, inclusion decision, adapter version. Resume fidelity depends on upstream streaming revision and record-order stability; assess each source.

## Teacher request and result
Job ID and document ID, teacher profile/endpoint reference, prompt version, schema version, deterministic request identity, attempt IDs/timestamps, response validation outcome and provenance. **The exact supplied prompt and exact JSON schema are missing; no keys, scales, defaults or category set are ratified here.**

## Export
Parquet with document/label provenance and split assignment that prevents duplicate-family train/test leakage. Exact column types and handling of source text await the original spec and licensing/retention decisions.
