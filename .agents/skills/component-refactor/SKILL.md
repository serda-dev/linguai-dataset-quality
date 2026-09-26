---
name: component-refactor
description: Refactor repeated Santos V Portal Vue/Nuxt presentation code without changing routes, BFF boundaries, or server authorization.
---

# Component Refactor — Santos V Portal

Read `AGENTS.md`, the relevant feature/design document, and current component/route.
Keep Nuxt 4/Vue SSR behavior, Nuxt UI/Tailwind patterns, accessibility, URL behavior,
loading/error states, and capability visibility intact.

Refactor repeated presentation only after two real callers exist. Do not move UCP calls
into client code, duplicate auth helpers, infer security from hidden UI, or alter the
server capability check. Preserve payloads, responses, middleware, test selectors, and
protected-workspace behavior. Test the rendered workflow and capability-denied state.
