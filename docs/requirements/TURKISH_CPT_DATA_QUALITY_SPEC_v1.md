# TURKISH_CPT_DATA_QUALITY_SPEC_v1

Status: **AUTHORITATIVE**. Purpose: quality labeling of documents for general-purpose Turkish continual pretraining (CPT). This document transcribes the operational contract supplied by the user; the prompt and schema are separate, versioned resources in `prompts/` and `schemas/`.

## Evaluation principle

Determine whether the original content provides reliable, meaningful CPT learning signal. Separate directly usable, valuable but noisy, weak but potentially useful, and unusable content. High information and low cleanliness is valid and does not automatically mean DROP. Do not use viewpoint, politics, religion, profanity, controversy, informality, or genre as a quality proxy. Formal or academic tone is not intrinsically high quality. Code, mathematics, lists, tables, JSON/XML, legal text, technical content, conversation and creative writing can all be valuable.

## Teacher observations

Exactly one `type`: `general` (ordinary prose), `reference` (encyclopedia/dictionary/knowledge base/documentation), `academic_technical` (STEM, engineering, scientific/technical publication), `news` (journalism, interviews, analysis), `conversation` (forum/chat/Q&A/dialogue), `creative` (fiction/poetry/script), `legal_official` (legislation/decisions/institutional text), `code` (code is primary signal), `structured_data` (tables/lists/JSON/XML are primary signal), `noise_unknown` (type cannot be reliably established or content is largely broken).

All six scores use integers 0–4. `language` alone may be `null`, only if essentially no natural language exists. Do not set language to zero merely because a good code or structured document lacks Turkish prose.

| Score | 0 | 1 | 2 | 3 | 4 |
| --- | --- | --- | --- | --- | --- |
| L language | severely broken/unintelligible | widespread errors | usable with errors | natural good Turkish | excellent natural Turkish |
| C coherence/integrity | fragment soup | major problems | partly coherent/incomplete | coherent usable | strongly coherent/intact |
| I information/learning signal | none | very little | moderate | strong | exceptionally rich |
| N cleanliness | severely contaminated | highly noisy | noticeable repairable noise | mostly clean | clean |
| S structure for its content type | destroyed | major structural damage | mixed/partly preserved | good | excellent |
| U holistic CPT utility | unusable | mostly harmful/very weak | usable but weak/review/repair | good | premium |

`U` is **not** a mathematical average. `I` includes factual, explanatory, procedural, experiential, dialogic, stylistic, legal, mathematical and code patterns. `N` measures crawl, boilerplate, duplicate, SEO, markup, OCR and encoding artifacts independently of `I`. `S` respects the document's format.

Before responding, the teacher silently examines: L1 Turkish dominance when natural language exists; L2 natural Turkish versus broken translation; L3 grammar/punctuation/readability; L4 lexical/terminology integrity; C1 local coherence; C2 global continuity; C3 context/completeness; C4 unrelated joins; I1 meaningful factual/explanatory/experiential/procedural/linguistic signal; I2 signal density; I3 specificity/details/examples; I4 learnable content-type patterns; N1 boilerplate/UI; N2 repetition; N3 SEO/advertising; N4 OCR/encoding/extraction corruption; S1 section boundaries; S2 lists/tables/JSON/XML/markup integrity; S3 code/math/formula integrity; S4 format supports meaning. The 20 checks are internal and not extra teacher output fields.

`noise` contains zero or more materially present flags: `boilerplate_ui` (navigation/cookie/menu/footer), `repetition` (meaningless repeated content), `seo_advertising` (keyword stuffing/affiliate/filler), `markup_extraction` (HTML parsing remnants), `encoding_ocr` (mojibake/OCR), `truncation_fragment` (serious missing context), `unrelated_merge` (unrelated concatenation), `linguistic_corruption` (transformation/extraction damages language).

CPU-derived `format_flags` may contain `code`, `math`, `table`, `list`, `markup`, `multilingual`; these are metadata, not teacher semantic labels, and multiple may apply. A format flag alone never determines type or quality.

## Versioned routing policy

Apply in this priority order to produce exactly one route (first match):

1. PREMIUM: U=4, I≥3, N≥3, C≥3.
2. KEEP: U≥3, N≥3.
3. DETERMINISTIC_REPAIR: I≥3, N≤2, and noise is predominantly `boilerplate_ui`, `repetition`, `seo_advertising`, or `markup_extraction`.
4. MODEL_REPAIR: I≥3, C≥2 and noise includes `encoding_ocr` or `linguistic_corruption`.
5. DROP: U≤1 or (I≤1 and N≤1).
6. REVIEW: all others.

The qualitative term “predominantly” requires a separately documented conservative policy interpretation. `truncation_fragment` and `unrelated_merge` do not permit automatic semantic rewrite. The teacher returns observations only; route is derived and versioned without mutating the label.

## Provenance, storage and student

The exact teacher JSON is `schemas/teacher_label_v1.schema.json`. The complete, unchanged system prompt is `prompts/turkish_cpt_quality_teacher_v2.txt`; the user payload template is `prompts/teacher_user_v1.txt`. Do not include source dataset name in the default teacher request. Application envelope adds `doc_id`, `teacher_label`, CPU `format_flags`, and `provenance` (`source_dataset`, `source_config`, `source_split`, `teacher_model`, `teacher_prompt_version`, `sampling_run_id`, `labeling_run_id`, plus immutable model/profile/content identity). Never send provenance in the teacher output schema.

Labels are append-only with teacher model/profile, prompt version, document hash and labeling run. Teacher changes create new labels. Keep `original_text` immutable; future `repaired_text`, method, model and version are separate. Student target: `moganai/MoganBERT-TR`, learning content type, six dimensions and multilabel noise; format flags need not be learned.

## Acceptance exemplars

- A: excellent natural Turkish article → high L/C/I/N/S/U.
- B: informative article with cookie/menu/HTML debris → high I, low N, not automatic DROP.
- C: meaningful Python/C++ → `code`, L may be null, I/S/U may be high.
- D: meaningful math/table/reference → no prose-format penalty.
- E: fluent SEO filler → potentially high L with low I/N.
- F: natural forum dialogue → no academic-tone penalty.
- G: random fragments → low C/S/U.
- H: information-rich OCR damage → high I, low N/L, possible repair candidate.
