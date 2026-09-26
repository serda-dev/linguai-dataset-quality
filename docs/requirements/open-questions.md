# Open questions and decisions

| Class | Question / current state |
| --- | --- |
| BLOCKER | Provide the original product specification, the verbatim teacher prompt and the complete label JSON schema. Previous conversation snippets are partial assistant proposals; the required product review cannot certify them. |
| BLOCKER for live VPS validation/deployment | Provide an encrypted Coolify route (HTTPS or tunnel) and a reachable Docker execution route to the VPS. Public HTTP token use is prohibited by the supplied workflow. Current unauthenticated probes time out. |
| NEEDS_DECISION | Confirm approved HF datasets/configs/revisions and source-specific field mappings, access controls and licenses. Four previously mentioned IDs are discovery leads, not validated source contracts. |
| NEEDS_DECISION | Confirm exact calibration/40k strata, quotas, randomization, classifier target and export fields; a previous assistant proposal suggests 100→1k→5k and 28k/8k/4k but is not an approved contract. |
| SAFE_DEFAULT | No automatic teacher labeling, including small batches, until the prompt/schema and cost policy are known. Mock-only tests can proceed. |
| SAFE_DEFAULT | Disable production auto-deploy and require a recorded candidate commit, Docker pass, and explicit manual deploy. |
| FUTURE | UI and manual adjudication workflow, if the original spec calls for them. |

Implementation is gated on the first BLOCKER. Coolify creation and deployment are gated on the second BLOCKER. The supplied temporary token must not be pasted into repo, PR, commands, or logs.
