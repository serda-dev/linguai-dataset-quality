# Engineering Audit Register

Findings from [engineering-auditor](../../.agents/skills/engineering-auditor/SKILL.md).
This is a diagnosis and triage record, not an approval or implementation log.

## Scope

- **Date:** `<YYYY-MM-DD>`
- **Boundary:** `<full system | story | endpoint | worker | integration>`
- **Mode:** `<runtime-assisted | source-only>`
- **Why source-only, if applicable:** `<reason or —>`
- **Baseline:** `<commit, story, invariant, or release under audit>`

## Index

| ID | Class | Severity | Title | Location | Confidence | Status | Route |
|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — |

**Status:** `Open` → `Accepted` → `Scoped` / `Fixed`, or `Open` → `Declined` with the
reason recorded. Never delete a row; a declined finding is evidence against repeating
the same audit claim.

## Findings

<!--
### BF-<n> | SD-<n>: <short title>
**Class:** <Confirmed Bug | System-Design Risk>
**Severity:** <S0 | S1 | S2 | S3>
**Status:** <Open | Accepted | Scoped | Fixed | Declined>
**Location:** <file:line, route, query, job, or observed path>
**Evidence:** <reproduction, trace, mechanical call-count/bound, or contract>
**Failure condition:** <input, data size, traffic, interleaving, or dependency state>
**Problem:** <the precise defect or design gap>
**Impact:** <what becomes wrong, slower, more expensive, unsafe, or impossible>
**Recommendation:** <the smallest direction that closes the gap; do not implement it>
**Validation:** <test, metric, bound, or invariant that would prove it fixed>
**Cost:** <trivial | a pass | multi-pass | needs architecture>
**Confidence:** <high | medium | low>
**Trade-off:** <the honest reason a sensible engineer may defer or reject it>
**Route:** <owning story/model | new story | architecture review | immediate human attention>
-->
