---
name: frontend-design
description: Design or revise Santos V Portal Nuxt/Vue interfaces while preserving its visual system, accessibility, and server-side BFF boundary.
---

# Frontend Design — Santos V Portal

Read `AGENTS.md`, `docs/UI_HANDOFF.md`, relevant feature specifications, and existing
`app/` components. Preserve Nuxt UI, Tailwind, responsive behavior, and the Santos V
visual language; use existing tokens/components before adding CSS or dependencies.

Protected UI may reflect capabilities for usability, but no client-side state decides
authorization. Keep data requests on Portal routes and never expose UCP credentials or
direct UCP/PostgreSQL access. Treat empty, loading, denied, dependency-error, and mobile
states as first-class; use semantic HTML, labels, keyboard behavior, contrast, and useful
error copy. Validate visible workflow with browser/acceptance tests when UI changes.
