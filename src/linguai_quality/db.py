import hashlib
import uuid
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .contracts import POLICY_VERSION, document_id, route


class Store:
    def __init__(self, url: str):
        self.url = url

    def connect(self):
        return psycopg.connect(self.url, row_factory=dict_row, connect_timeout=3)

    def initialize(self):
        with self.connect() as conn:
            conn.execute(Path(__file__).with_name("schema.sql").read_text())

    def ping(self):
        with self.connect() as conn:
            conn.execute("SELECT 1")

    def enroll(self, *, source: str, revision: str, config: str, split: str, ordinal: int,
               text: str, sampling_run_id: str, labeling_run_id: str, max_bytes: int):
        if not sampling_run_id or not labeling_run_id:
            raise ValueError("sampling and labeling run ids required")
        if len(text.encode("utf-8")) > max_bytes:
            raise ValueError("document exceeds byte limit; no implicit truncation")
        doc_id = document_id(source, revision, config, split, ordinal, text)
        digest = hashlib.sha256(text.encode()).hexdigest()
        with self.connect() as conn:
            conn.execute("INSERT INTO labeling_runs(id) VALUES (%s) ON CONFLICT DO NOTHING", (labeling_run_id,))
            conn.execute("""INSERT INTO documents(id,source,revision,config,split,ordinal,original_text,content_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
                (doc_id, source, revision, config, split, ordinal, text, digest))
            conn.execute("INSERT INTO sample_decisions(doc_id,sampling_run_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (doc_id, sampling_run_id))
            existing = conn.execute("SELECT sampling_run_id FROM jobs WHERE run_id=%s AND doc_id=%s", (labeling_run_id, doc_id)).fetchone()
            if existing and existing["sampling_run_id"] != sampling_run_id:
                raise ValueError("labeling job already belongs to a different sampling run")
            conn.execute("INSERT INTO jobs(run_id,doc_id,sampling_run_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (labeling_run_id, doc_id, sampling_run_id))
        return doc_id

    def claim(self, max_attempts: int, lease_seconds: int = 60):
        token = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute("UPDATE jobs SET status='exhausted',lease_token=NULL WHERE status='claimed' AND lease_until<now() AND attempt_count >= %s", (max_attempts,))
            row = conn.execute("""SELECT j.id, j.run_id, j.doc_id, j.sampling_run_id, j.attempt_count, d.original_text, d.content_sha256
                FROM jobs j JOIN documents d ON d.id=j.doc_id
                WHERE (j.status='pending' AND j.available_at<=now()
                    OR j.status='claimed' AND j.lease_until<now()) AND j.attempt_count<%s
                ORDER BY j.id LIMIT 1 FOR UPDATE OF j SKIP LOCKED""", (max_attempts,)).fetchone()
            if row:
                conn.execute("""UPDATE jobs SET status='claimed',attempt_count=attempt_count+1,
                    lease_token=%s,lease_until=now()+(%s * interval '1 second') WHERE id=%s""",
                    (token, lease_seconds, row["id"]))
                row["lease_token"] = token
            return row

    def finish(self, job: dict, *, model: str, profile: str, label: dict | None = None,
               error_class: str | None = None, max_attempts: int = 3):
        with self.connect() as conn:
            locked = conn.execute("SELECT status,lease_token,attempt_count FROM jobs WHERE id=%s FOR UPDATE", (job["id"],)).fetchone()
            if locked["status"] != "claimed" or locked["lease_token"] != job["lease_token"]:
                return False  # stale claim cannot write an attempt or label
            if label is not None:
                conn.execute("""INSERT INTO labels(run_id,doc_id,sampling_run_id,teacher_label,route,policy_version,
                    teacher_model,teacher_profile,prompt_version,schema_version,document_hash)
                    VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (run_id,doc_id) DO NOTHING""",
                    (job["run_id"], job["doc_id"], job["sampling_run_id"], __import__("json").dumps(label), route(label), POLICY_VERSION,
                     model, profile, "turkish_cpt_quality_teacher_v2", "teacher_label_v1", job["content_sha256"]))
            conn.execute("INSERT INTO attempts(job_id,teacher_model,teacher_profile,outcome,error_class) VALUES (%s,%s,%s,%s,%s)",
                         (job["id"], model, profile, "accepted" if label else "failed", error_class))
            next_status = "done" if label else ("exhausted" if locked["attempt_count"] >= max_attempts else "pending")
            conn.execute("""UPDATE jobs SET status=%s,lease_token=NULL,lease_until=NULL,
                available_at=now()+interval '5 seconds' WHERE id=%s""", (next_status, job["id"]))
            return True

    def heartbeat(self, worker_id: str):
        with self.connect() as conn:
            conn.execute("""INSERT INTO worker_state(worker_id,heartbeat_at) VALUES (%s,now())
                ON CONFLICT(worker_id) DO UPDATE SET heartbeat_at=excluded.heartbeat_at""", (worker_id,))

    def worker_alive(self) -> bool:
        with self.connect() as conn:
            return bool(conn.execute("SELECT 1 FROM worker_state WHERE heartbeat_at>now()-interval '30 seconds' LIMIT 1").fetchone())
