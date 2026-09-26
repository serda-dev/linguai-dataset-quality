ALTER TABLE documents ADD COLUMN IF NOT EXISTS format_flags jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_family text;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS sketch_version text NOT NULL DEFAULT 'exact_v1';

ALTER TABLE attempts ADD COLUMN IF NOT EXISTS prompt_version text;
ALTER TABLE attempts ADD COLUMN IF NOT EXISTS schema_version text;
ALTER TABLE attempts ADD COLUMN IF NOT EXISTS endpoint_fingerprint text;
ALTER TABLE attempts ADD COLUMN IF NOT EXISTS lease_token text;
ALTER TABLE attempts ADD COLUMN IF NOT EXISTS finished_at timestamptz;

CREATE TABLE IF NOT EXISTS run_controls (
    run_id text PRIMARY KEY REFERENCES labeling_runs(id),
    source text NOT NULL, revision text NOT NULL, config text NOT NULL, split text NOT NULL,
    text_field text NOT NULL, seed bigint NOT NULL, max_scan integer NOT NULL CHECK(max_scan>0),
    sample_size integer NOT NULL CHECK(sample_size>0 AND sample_size<=max_scan),
    status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','collecting','ready','active','paused','completed','failed')),
    approved boolean NOT NULL DEFAULT false, full_approved boolean NOT NULL DEFAULT false,
    approved_at timestamptz, cursor bigint NOT NULL DEFAULT 0,
    prefix_digest text NOT NULL DEFAULT repeat('0',64), rejected_records integer NOT NULL DEFAULT 0,
    license_ack boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS teacher_budget (
    id boolean PRIMARY KEY DEFAULT true CHECK(id), reserved_count bigint NOT NULL DEFAULT 0
);
INSERT INTO teacher_budget(id,reserved_count) VALUES(true,0) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS sample_candidates (
    run_id text NOT NULL REFERENCES run_controls(run_id), doc_id text NOT NULL,
    rank text NOT NULL, ordinal bigint NOT NULL, original_text text NOT NULL,
    content_sha256 text NOT NULL, format_flags jsonb NOT NULL,
    content_family text NOT NULL,
    PRIMARY KEY(run_id,doc_id), UNIQUE(run_id,ordinal)
);
CREATE TABLE IF NOT EXISTS storage_budget (
    id boolean PRIMARY KEY DEFAULT true CHECK(id),
    document_bytes bigint NOT NULL DEFAULT 0,
    candidate_bytes bigint NOT NULL DEFAULT 0
);
INSERT INTO storage_budget(id,document_bytes,candidate_bytes)
SELECT true,COALESCE(sum(octet_length(original_text)),0),0 FROM documents
ON CONFLICT DO NOTHING;
CREATE INDEX IF NOT EXISTS candidates_rank_idx ON sample_candidates(run_id,rank DESC);
CREATE TABLE IF NOT EXISTS route_decisions (
    run_id text NOT NULL, doc_id text NOT NULL, policy_version text NOT NULL, route text NOT NULL,
    PRIMARY KEY(run_id,doc_id,policy_version),
    FOREIGN KEY(run_id,doc_id) REFERENCES labels(run_id,doc_id)
);
INSERT INTO route_decisions(run_id,doc_id,policy_version,route)
SELECT run_id,doc_id,policy_version,route FROM labels ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS artifact_exports (
    id text PRIMARY KEY, relative_path text NOT NULL UNIQUE, sha256 text NOT NULL,
    bytes bigint NOT NULL, row_count bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
