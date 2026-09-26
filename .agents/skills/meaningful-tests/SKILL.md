---
name: meaningful-tests
description: Write or review Santos V Portal tests that falsify Nuxt BFF behavior, OAuth/session security, capability gates, and PostgreSQL contracts.
---

# Meaningful Tests — Santos V Portal

Read `AGENTS.md`, `docs/TESTING_AND_DEVELOPMENT.md`, relevant design/architecture,
source, and existing Vitest/Playwright-BDD tests. This is Nuxt 4/Nitro, TypeScript,
Drizzle, and PostgreSQL 16—not a PHP or browser-direct API application.

Run `npm run test:unit`, `npm run test:acceptance`, and `npm run build` in
proportion to scope. Exercise Docker/PostgreSQL and migration behavior for schema/runtime
work; mocks alone cannot prove live integration.

For each behavior, add the smallest test that fails for a plausible wrong implementation:
success, denial/invalid input, boundary values, and no state mutation after rejection.
OAuth/BFF tests cover authorization URL scopes and callback, state expiry/replay,
cancellation, code/token/userinfo errors, refresh rotation, session expiry/invalidation,
and proof tokens/secrets never reach browser output. Capability tests prove server-side
denial and exact selected faction/rank mapping, not hidden UI. Never record real
credentials, tokens, or personal data. Report unavailable UCP/DB boundaries.
