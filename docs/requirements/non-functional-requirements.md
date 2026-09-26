# Non-functional requirements

- Bounded stream buffers, memory, retries, teacher timeouts and artifact bytes for an unverified planning envelope of 8 CPU, 16 GB RAM and about 100 GB free disk.
- PostgreSQL is durable truth; accepted labels and attempt provenance survive restart, while remote inference billing cannot be guaranteed exactly once across a crash.
- No real teacher/GPU or production DB in tests. `make test` uses isolated Docker, mock OpenAI-compatible teacher, PostgreSQL and cleans isolated volumes.
- No secrets, document text, prompts containing source content, or teacher response bodies in operational logs. Configure teacher credentials at runtime only.
- No GitHub Actions. Branches/commits/PRs preserve source and review history; deployment gate is separate and managed by the other agent.
