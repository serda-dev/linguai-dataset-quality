# Meaningful test design

The canonical `make test` starts an isolated PostgreSQL, mock OpenAI-compatible endpoint, API, worker and test runner with Docker Compose; `down -v` runs on exit. No production secrets, real HF datasets or Vast calls.

1. Unit: stable identity across exact source coordinates and content; distinct hash/revision; strict schema including null language, no extra fields and exact ID; exact prompt/template substitution and absence of source names; routing priority and noisy valuable cases; text byte limit and immutable original.
2. Integration: schema creation, explicit enrollment, concurrent lease claim uniqueness, attempt provenance, invalid JSON and mismatched ID retry, worker crash/lease expiry, stale lease rejection, duplicate accepted label, replaceable teacher profile. Database outage should fail readiness and pause work.
3. Acceptance: source independent labeling for a code document (`language=null`), high-I low-N repair routing, SEO filler with high L and low I, natural conversation without academic penalty. These are fake teacher judgments; tests assert preservation and routing, not that a mock can reason about quality.
4. Failure: teacher timeout/unavailable, worker mid-job, DB restart, HF interruption/malformed record and disk budget. The last two are gated with the production HF adapter and export, and explicitly not claimed by this foundation.

Gate A on VPS remains required to certify Docker tests; local Python tests only provide a narrower signal. Gate B is read-only except controlled artifact write/read. No labeling starts in either smoke gate.
