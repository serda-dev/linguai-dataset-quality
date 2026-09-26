CREATE TABLE IF NOT EXISTS documents (
    id text PRIMARY KEY,
    source text NOT NULL, revision text NOT NULL, config text NOT NULL, split text NOT NULL,
    ordinal bigint NOT NULL, original_text text NOT NULL, content_sha256 text NOT NULL,
    UNIQUE (source, revision, config, split, ordinal, content_sha256)
);
CREATE TABLE IF NOT EXISTS labeling_runs (
    id text PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sample_decisions (
    doc_id text NOT NULL REFERENCES documents(id), sampling_run_id text NOT NULL,
    PRIMARY KEY(doc_id, sampling_run_id)
);
CREATE TABLE IF NOT EXISTS jobs (
    id bigserial PRIMARY KEY, run_id text NOT NULL REFERENCES labeling_runs(id),
    doc_id text NOT NULL REFERENCES documents(id), sampling_run_id text NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    attempt_count integer NOT NULL DEFAULT 0, lease_token text, lease_until timestamptz,
    available_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, doc_id)
);
CREATE TABLE IF NOT EXISTS attempts (
    id bigserial PRIMARY KEY, job_id bigint NOT NULL REFERENCES jobs(id),
    teacher_model text NOT NULL, teacher_profile text NOT NULL,
    outcome text NOT NULL, error_class text,
    occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS labels (
    run_id text NOT NULL REFERENCES labeling_runs(id), doc_id text NOT NULL REFERENCES documents(id),
    sampling_run_id text NOT NULL, teacher_label jsonb NOT NULL,
    route text NOT NULL, policy_version text NOT NULL,
    teacher_model text NOT NULL, teacher_profile text NOT NULL,
    prompt_version text NOT NULL, schema_version text NOT NULL, document_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (run_id, doc_id)
);
CREATE TABLE IF NOT EXISTS worker_state (
    worker_id text PRIMARY KEY, heartbeat_at timestamptz NOT NULL
);
