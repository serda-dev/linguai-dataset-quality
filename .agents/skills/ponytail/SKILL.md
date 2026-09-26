---
name: ponytail
description: Choose the smallest safe Santos V Portal change when existing Nuxt, BFF, and Drizzle helpers matter.
---

# Ponytail — Santos V Portal

Read `AGENTS.md`, relevant docs, and current code before choosing a solution. Prefer
the smallest complete vertical slice: Vue component → existing Portal route → small
service → owner system. Reuse existing UCP, session, capability, Drizzle, and audit
helpers before adding an abstraction or package.

Do not add microservices, a second frontend/backend, generic repositories/DI, queues,
event buses, cache, GraphQL, or a permission framework for a single caller. The UCP
adapter is deliberately separate because it protects a confidential OAuth boundary.
Preserve server-side authorization, Portal/UCP ownership, token secrecy, and testable
behavior; document a real reason before adding a layer or dependency.
