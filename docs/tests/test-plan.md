# Meaningful test design — pre-implementation

Run `make test` against isolated Docker Compose PostgreSQL, API, worker, deterministic mock OpenAI-compatible teacher and test runner. Fail nonzero, tear down volumes, prohibit production credentials/real Vast calls. Tests must falsify contracts rather than count coverage.

- Units: stable document identity under identical source revision; distinct revisions/records; sketch and metadata extraction without raw mutation; deterministic sampling; policy for structured content; strict schema validation after verbatim schema is supplied.
- Integration: DB migrations on empty DB; concurrent claim uniqueness; retry ceiling; expired-lease recovery; duplicate accepted-label rejection; worker killed during request/commit boundary; DB restart; mock timeout, unavailable endpoint, invalid JSON, malformed source record, HF stream interruption; endpoint profile replacement; atomic Parquet export/checksum.
- Acceptance: execute scenarios in `features/` with fake streams and mock teacher; no GPU or real HF corpus required. Extend for exact prompt, schema and dataset mappings once supplied.
- Failure/resource: disk budget reached must stop safely; bounded memory and artifact size; no secret or raw-source logging; test split duplicate-family isolation.
- VPS Gate A: exact candidate SHA/image, isolated Compose stack, integration/acceptance and migration tests. Gate B: deployed read-only /health, /ready, DB connectivity, worker heartbeat, artifact write/read and teacher configuration. Neither gate starts teacher labeling.

Status: design only. Docker absent locally; VPS unavailable; no test execution claimed.
