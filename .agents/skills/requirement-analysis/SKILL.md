---
name: requirement-analysis
description: Turn a material Santos V Portal change into testable scope using its BFF, data-ownership, and security contracts.
---

# Requirement Analysis — Santos V Portal

Read `AGENTS.md`, `docs/SYSTEM_OVERVIEW.md`, `plan.md`, relevant architecture/design
and feature documents, then current source. Use for material features, UCP/OAuth,
ownership, authorization, or schema changes—not one-line fixes.

State user outcome, actors, routes, server boundary, owner of every changed datum,
capabilities, non-goals, and observable criteria for success, rejection, boundary input,
and no-change-on-rejection. Update the relevant existing design/spec in its established
style. Record only genuinely blocking ambiguity; do not invent UCP endpoints, payloads,
scopes, faction matrices, or table shapes.

Keep explicit: browser cannot receive UCP credentials or call UCP/DB; scopes constrain
UCP API reach rather than Portal authorization; UCP identity/game data stays
authoritative; rank grants are exact mappings; Portal-local MDC/RMS/capability data has
Portal ownership. Name the code, migration, tests, and docs implementation must update.
