---
name: version-control
description: Handle Santos V Portal branches, commits, pushes, and PRs with explicit operator approval and traceable verification.
---

# Version Control — Santos V Portal

Inspect `git status`, current branch, diff, and relevant tests before proposing a Git
action. Preserve unrelated user changes; never reset, checkout away, force-push, or
rewrite history without explicit instruction.

Commit, branch creation, push, PR creation, merge, and remote changes require explicit
operator approval. Before requesting it, report changed files, user-visible and
security/data effects, migration requirements, and tests run/remaining. For Portal work,
normally run relevant `npm run test:unit`, `npm run test:acceptance`, and
`npm run build`; include Docker/PostgreSQL validation for migration/runtime changes.

Use focused, reviewable commits. Do not claim a live UCP OAuth flow was verified unless it
actually ran against the registered application without exposing credentials.
