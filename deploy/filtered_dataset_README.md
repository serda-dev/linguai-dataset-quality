---
language:
- tr
tags:
- text-classification
- data-quality
---

# Turkish corpus quality predictions

This repository archives the output of the LinguAI student classifier as the source
corpora are processed. Each Parquet file contains **classification metadata only**:
source ID, source row ordinal, stable document ID, SHA-256 of the original text,
input byte count/truncation, predicted type, six integer quality scores (0–4),
noise flags, and a derived routing decision. Original document text is not
redistributed here. Source dataset coordinates, pinned revisions, classifier
artifact hash, and completed run markers are under `metadata/`.

Parquet parts are under `data/<source-id>/`. For FineWeb2 Turkish, the two file
ranges preserve global row ordinals. A part filename records the source row range
`[start, end)`; some source rows may have no prediction if the text was empty.

These are model predictions, not verified ground truth. `KEEP`, `PREMIUM`,
`REVIEW`, `DROP`, and repair routes should be audited before destructive filtering.
In particular, a `DROP` prediction must not by itself delete original source data.

The source text remains in the original repositories, each with its own license:

- `HuggingFaceFW/fineweb-2` (`tur_Latn`): ODC-By
- `turkish-nlp-suite/BellaTurca`: CC BY-SA 4.0
- `ytu-ce-cosmos/Cosmos-Turkish-Corpus-v1.0`: CC BY 4.0
- `moganai/mogan-turkish-web`: ODC-By

The classifier uses `moganai/MoganBERT-TR` fine-tuned on Teacher labels. The
classifier artifact hash is recorded in each source's `identity.json`.
