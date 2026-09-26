---
name: logic-simplification
description: Simplify Santos V Portal TypeScript/Nitro/Drizzle logic while preserving OAuth, BFF, data-ownership, and response contracts.
---

# Logic Simplification — Santos V Portal

Read `AGENTS.md`, current service/route tests, and governing documentation. Simplify
one path at a time; retain types, controlled error mapping, 10-second UCP timeout, and
atomic OAuth state consumption.

Do not collapse the server-only UCP adapter into UI code, replace Drizzle safety with
unchecked raw SQL, merge read/write capability gates, or discard audit/session update
semantics. Preserve opaque cookies, 8-hour Portal sessions, server-only token rotation,
selected-character validation, and exact faction/rank lookups. Retain falsifiable
success, denial, and no-change-on-rejection tests.
