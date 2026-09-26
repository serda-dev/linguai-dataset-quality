# Data flow

Approved source/revision → bounded streaming adapter → immutable document text/hash/identity → sampling decision → explicit labeling run → queued job → worker lease → OpenAI-compatible client with exact system and user prompts → JSON parse/schema and ID validation → transactionally insert attempt/accepted label → separately apply versioned route policy. Failed attempts have bounded retries and no accepted label. Teacher receives no source metadata by default.

This foundation accepts an explicit selected document and records its sampling run; no HF adapter is enabled until source mappings are verified. A teacher sketch initially equals the exact original text for small, bounded documents. Sketch extraction for larger texts awaits an approved truncation contract and is rejected rather than silently truncating.
