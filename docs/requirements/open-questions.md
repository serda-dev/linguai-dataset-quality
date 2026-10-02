# Open questions after authoritative contracts

| Class | Decision |
| --- | --- |
| NEEDS_DECISION | Approve exact HF dataset IDs, configs, splits, revisions, row-to-text mappings, licenses and retention. The previously noted four names are leads only. Production ingestion is gated per source until confirmed. |
| NEEDS_DECISION | Approve 100/1k/5k calibration, 40k strata/quotas, sample sketch truncation, train/test split and export retention; do not silently turn prior suggestions into product requirements. |
| NEEDS_DECISION | Select live teacher model/profile, endpoint and rate/cost budget. The example `Qwen/Qwen3.5-35B-A3B-FP8` in the envelope is illustrative, not an authorization to label. |
| SAFE_DEFAULT | `DETERMINISTIC_REPAIR` only when all material noise flags are in the four specified deterministic classes, with at least one present. Other flags route to review unless an earlier explicitly safe condition applies. No repair is executed by routing. |
| SAFE_DEFAULT | New runs begin paused, require approval and bounded quota; cumulative reservations reaching a lower guard require a separate approval secret. No 40k run without user approval. No real HF streaming or teacher calls in tests. |
| SAFE_DEFAULT | When stable upstream IDs are absent, hash the exact source namespace/revision/config/split, ordinal and raw text digest. Reordering an upstream stream creates different identities; pin a source revision and fail closed on changed manifests. |
| FUTURE | Near-duplicate algorithm, actual repair methods, adjudication UI, model training and publication. |

The three product contracts no longer block a bounded generic implementation. Concrete dataset mappings, source-specific quotas and evaluation splits remain gated by source decisions. VPS/Coolify work is assigned to another agent and out of this workstream.

The user supplied and authorized a bounded four-source Teacher campaign on
2026-10-02. Its pinned source mappings and quotas are recorded in
`../operations/2026-10-02-bounded-source-plan.md`. That decision resolves source
selection only for this campaign; evaluation split, broader corpus ingestion,
student training and export retention remain separate decisions.
