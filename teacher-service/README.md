# Disposable GPU teacher service — feature handoff

This folder is a **contract bundle for a separate small GPU-serving project**, not an inference implementation inside the persistent control plane. It can be moved into its own repository when that repository is named. The VPS retains all documents, run approval, attempts, labels and artifacts; the rented GPU host only runs model inference and may be destroyed/replaced without losing a job. No startup, readiness or deployment check starts labeling.

## Existing caller contract

`src/linguai_quality/teacher.py` sends `POST {TEACHER_BASE_URL}/chat/completions` with JSON `{model, temperature: 0, messages: [{role: system, content: <verbatim v2 prompt>}, {role: user, content: <v1 payload>}]}`. It optionally sends `Authorization: Bearer <TEACHER_API_KEY>`. The service must return an OpenAI-compatible `choices[0].message.content` **string** containing only a JSON object valid against `schemas/teacher_label_v1.schema.json`, whose `id` equals the requested document ID. The caller does not send the source dataset name. The GPU service must not add provenance or routing fields to the teacher JSON. Existing caller timeout is **20 seconds**; a measured longer inference requires a separate control-plane timeout change before connecting a live model.

The verbatim system prompt is `prompts/turkish_cpt_quality_teacher_v2.txt`, the user payload is `prompts/teacher_user_v1.txt`, and the JSON schema is `schemas/teacher_label_v1.schema.json`. Bundle them in the service release at pinned hashes or retrieve from a pinned repository commit. Never silently edit the teacher prompt, and do not let a model-specific chat template change its message content without a versioned contract decision.

## Setup decisions to make when GPU access arrives

Record GPU model/count, driver, CUDA/runtime, VRAM free under actual load, storage and network reachability from the VPS. Choose the exact teacher model and pinned model revision, serving engine/version, context window, maximum concurrent requests, output-token cap and client timeout from measurements. The earlier Qwen 35B FP8 name was an example, not an approved model. Validate model fit **including weights, KV cache and server overhead** on the actual 48 GB instance before declaring readiness. Keep inference bound to a private/tunneled or authenticated encrypted address reachable from the VPS; a Jupyter URL by itself is not the teacher API URL.

## Gate

Implement and execute the features under `features/` with a mock backend and then the selected model on a tiny explicitly approved calibration set. Record request/response contract tests, latency, GPU memory peak, failure behavior and A–H rubric review. No real dataset stream or full 40k teacher run is part of setup. If the model cannot meet the client's current 20-second deadline, adjust and revalidate the control-plane timeout in a separate PR before production connection.
