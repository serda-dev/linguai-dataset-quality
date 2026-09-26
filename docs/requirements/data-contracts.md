# Data contracts

## Teacher JSON

The exact versioned teacher response is `schemas/teacher_label_v1.schema.json`. No extra fields, no explanations or reasoning. Validate JSON first, then the schema, then assert `id == requested doc_id`; a valid but mismatched ID is rejected. The teacher system prompt is byte-preserved at `prompts/turkish_cpt_quality_teacher_v2.txt`; user payload uses `teacher_user_v1.txt` and includes only ID and sketch, never source dataset by default.

## Internal document

Source namespace, pinned revision/config/split, ordinal or stable source ID, original text, its SHA-256, immutable document ID, format flags and extraction version. The `teacher_sketch` is a derived, versioned field; never overwrite the original. Unknown source fields are mapping errors, not blank documents. Sample/run decisions are stored before teacher work.

## Accepted label envelope

`doc_id`, `teacher_label`, `format_flags`, `provenance` including `source_dataset`, `source_config`, `source_split`, `teacher_model`, `teacher_profile`, `teacher_prompt_version`, `teacher_schema_version`, `document_hash`, `sampling_run_id`, `labeling_run_id`. Route and `policy_version` are derived and persisted separately; recomputation never rewrites the teacher label. The accepted-label uniqueness key is `(labeling_run_id, doc_id)`; a new model/prompt/schema evaluation of the same document requires a **new labeling run**. Pending jobs can use a replaced endpoint, and every attempt/accepted label retains its actual profile.

## Export

The bounded Parquet envelope includes original text, teacher JSON, format flags, policy route and provenance. Until an evaluation split and near-duplicate policy are approved, `split=train` for every row. Exact whitespace-normalized duplicate families have stable group IDs; no near-duplicate guarantee is claimed. The schema above describes only the teacher reply, never a database/export row.
