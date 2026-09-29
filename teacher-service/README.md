# GPU teacher service — control-plane contract

The implementation lives in [serda-dev/linguai-teacher-model](https://github.com/serda-dev/linguai-teacher-model). This folder retains the VPS/GPU acceptance scenarios; it is not a second inference implementation. The VPS owns documents, run approvals, attempts, labels and exports. A disposable GPU host handles one inference request at a time. Neither health nor readiness probes create a label.

## Existing caller

`src/linguai_quality/teacher.py` sends `POST {TEACHER_BASE_URL}/chat/completions` where the base URL ends in `/v1`. The request uses temperature zero, the byte-preserved `prompts/turkish_cpt_quality_teacher_v2.txt` system message and `prompts/teacher_user_v1.txt` user payload. The reply's `choices[0].message.content` is a JSON string valid against `schemas/teacher_label_v1.schema.json` with the requested ID. Dataset names, routing and provenance do not belong in the teacher reply.

The current VPS HTTP timeout is 20 seconds; its claim lease is 60 seconds and heartbeat freshness is 30 seconds. Longer inference requires a coordinated, separately tested control-plane change.

## Selected implementation candidate

The teacher repository selects official original Qwen3-30B-A3B Q8_0 GGUF at an immutable revision, a source-built pinned llama.cpp runtime, explicit 8192-token context, at most 1024 output tokens, 32-token safety reserve and one generation. It checks actual rendered token IDs before generation and rejects overflow without slicing input. Its requirements, profile, build and Vast runbook are authoritative for that implementation; the earlier Qwen3.5 FP8 example is not the selected model.

This selection is **not** proof of fit on a particular 48 GB card. Record the actual GPU/driver, available memory and peak after load/request, build image digest, network address, model revision, latency and output behavior. Review the small A–H rubric set before live corpus work.

## Transport and deployment

Vast maps container port 8000 to an instance-specific external port. Use the actual inference route, never the Jupyter URL. For a short explicitly scoped trial with public-source documents, an isolated teacher-only API key over direct `http://GPU_IP:EXTERNAL_PORT/v1` is an accepted operational choice. HTTP exposes the Bearer key, request and response to a party that can observe or modify the network path; rotate the trial key afterward. Before bulk labeling or sending sensitive text, choose an encrypted transport (direct TLS or a verified SSH/private tunnel). This choice does not require changing the VPS's existing Coolify TLS or public ports.

The teacher repository's connection-check script currently permits external HTTPS or HTTP over loopback only. It does **not** test a public-IP HTTP trial; update that script explicitly before relying on it for that route. The control-plane client itself accepts an HTTP base URL.

## Acceptance gate

Keep the features here as integration requirements and execute the teacher repository's mock tests plus the controlled on-GPU test. Verify one end-to-end request from the actual Coolify worker network, schema/ID correctness, model fit and p95 latency. No full dataset stream or automatic 40k labeling is authorized by this feature bundle.
