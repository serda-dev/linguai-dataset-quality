---
name: engineering-auditor
description: Audit Santos V Portal code or a completed change for confirmed bugs and design risks without silently implementing fixes.
---

# Engineering Auditor — Santos V Portal

Read `AGENTS.md`, `docs/SYSTEM_OVERVIEW.md`, relevant architecture/design/UCP/testing
contracts, source, and prior `docs/audits/`. State whether the audit covers a route,
feature, or whole system. Current source is factual authority.

Trace browser → Nuxt route/middleware → service → Drizzle/PostgreSQL or server-only UCP
adapter. Check applicable evidence for opaque HttpOnly sessions; OAuth state/callback
exactness; token/secret exposure; refresh rotation and fail-closed invalidation;
server-side IDOR/capability enforcement; exact faction/rank mapping; timeout/error
containment; schema/migration/index contracts; Portal/UCP ownership; MDC/RMS audit; and
log/response redaction. Verify no browser direct UCP/DB path exists.

Audit only: do not modify product code or tests. Write the next `docs/audits/AUDIT_<n>.md`
in the existing style. Each finding needs class, severity, exact location, evidence,
impact, smallest recommendation, validation, confidence, and scope. Report secret
exposure, auth bypass, privilege escalation, or corruptible MDC/RMS state directly.
