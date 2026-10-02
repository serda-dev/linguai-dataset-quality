# Four-source Teacher sampling plan — 2026-10-02

The operator-approved target is 10,000 documents each from FineWeb-2 Turkish,
BellaTurca, Cosmos Turkish Corpus and Mogan Turkish Web: 7,000 normal, 2,000
noisy/edge and 1,000 structured per source. BellaTurca's four accessible
subsets split each quota equally, for 2,500 documents per subset. Exact pinned
commits, configs, splits, text fields, license labels and quotas are in
`deploy/source_plan_2026-10-02.json`. These are 40,000 *maximum reserved jobs*,
not a claim that 40,000 valid labels will be accepted.

Every stratum is selected by seeded SHA-256 rank from eligible records in the
first 100,000 rows of its pinned split. The three content buckets are exclusive:
structured has format flags, at least two colons or a numbered list; noisy/edge
has short text (<300 characters), long text (>4,000 characters), replacement
characters or >20% non-letter punctuation; the rest is normal. Format flags
take precedence over edge cues. These CPU cues only construct the sample; the
Teacher alone assigns quality labels. Documents above 20,000 UTF-8 bytes are
ineligible and are never truncated. A short read-only preflight of 3,000 rows
per subset found enough category diversity to justify a bounded 100,000-row
window; the run still fails closed if a category quota is not met.

This is a sample of each bounded prefix, not a uniform sample of entire remote
corpora. The service stores pinned revisions, scan cursors, prefix digests,
source coordinates and selected originals so resume detects changed ordering.
The 40,000-job aggregate triggers the separate full-run approval token.
Before activating every run, inspect initial real Teacher outputs for semantic
quality, timeout and rejection rates; a schema-valid response alone is not a
human-reviewed rubric calibration. No evaluation split or public export is
implied by this plan.
