---
name: senior-developer
description: Implement Santos V Portal changes within documented Nuxt/Nitro, TypeScript, Drizzle/PostgreSQL, OAuth BFF, and capability contracts.
---

# Senior Developer — Santos V Portal

Read `AGENTS.md`, current source/tests, and affected docs first. Keep the Nuxt 4
monolith: UI in `app/`, HTTP behavior in `server/routes/`, domain logic in focused
`server/services/`, and PostgreSQL access through `server/db/`/Drizzle. Make the
smallest complete change and reuse existing helpers.

All UCP interaction remains behind the server adapter. Never expose client secrets,
OAuth codes, access/refresh tokens, or UCP calls to browser code. Validate identity,
selected character, and capabilities server-side; scopes do not replace Portal
capabilities. Preserve state single-use, opaque cookies, 8-hour Portal sessions, 24-hour
rotating refresh tokens, exact faction/rank grants, 10-second upstream timeout, and
controlled public errors.

Schema work updates Drizzle schema and an additive migration/contract; do not write UCP
tables or create cross-DB relationships. Add falsifiable tests, run the relevant commands
from `docs/TESTING_AND_DEVELOPMENT.md`, and update affected docs plus implementation log
for material work. Use `version-control` for Git workflows.
