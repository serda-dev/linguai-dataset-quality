import hashlib
import json
import uuid
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .contracts import POLICY_VERSION, document_id, route
from .runs import family_id, format_flags, sample_rank


class Store:
    def __init__(self, url: str):
        self.url = url

    def connect(self):
        return psycopg.connect(self.url, row_factory=dict_row, connect_timeout=3)

    def initialize(self):
        with self.connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(7435721)")
            conn.execute(Path(__file__).with_name("schema.sql").read_text())
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version text PRIMARY KEY)")
            for migration in sorted(Path(__file__).with_name("migrations").glob("*.sql")):
                if not conn.execute("SELECT 1 FROM schema_migrations WHERE version=%s", (migration.name,)).fetchone():
                    conn.execute(migration.read_text())
                    conn.execute("INSERT INTO schema_migrations(version) VALUES (%s)", (migration.name,))

    def ping(self):
        with self.connect() as conn:
            conn.execute("SELECT 1")

    def enroll(self, *, source: str, revision: str, config: str, split: str, ordinal: int,
               text: str, sampling_run_id: str, labeling_run_id: str, max_bytes: int,
               max_database_bytes: int = 8_000_000_000):
        if not sampling_run_id or not labeling_run_id:
            raise ValueError("sampling and labeling run ids required")
        if len(text.encode("utf-8")) > max_bytes:
            raise ValueError("document exceeds byte limit; no implicit truncation")
        doc_id = document_id(source, revision, config, split, ordinal, text)
        digest = hashlib.sha256(text.encode()).hexdigest()
        with self.connect() as conn:
            run = conn.execute("SELECT * FROM run_controls WHERE run_id=%s FOR UPDATE", (labeling_run_id,)).fetchone()
            if not run or not run["approved"] or run["source"] != "manual" or run["status"] != "collecting":
                raise ValueError("approved collecting manual run required")
            if (source, revision, config, split) != (run["source"], run["revision"], run["config"], run["split"]):
                raise ValueError("source coordinates differ from approved run")
            existing_job = conn.execute("SELECT sampling_run_id FROM jobs WHERE run_id=%s AND doc_id=%s", (labeling_run_id, doc_id)).fetchone()
            if not existing_job and conn.execute("SELECT count(*) AS n FROM jobs WHERE run_id=%s", (labeling_run_id,)).fetchone()["n"] >= run["sample_size"]:
                raise ValueError("run quota reached")
            self._check_storage(conn, text, max_database_bytes, doc_id)
            inserted = conn.execute("""INSERT INTO documents(id,source,revision,config,split,ordinal,original_text,content_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING RETURNING id""",
                (doc_id, source, revision, config, split, ordinal, text, digest))
            if inserted.fetchone():
                conn.execute("UPDATE storage_budget SET document_bytes=document_bytes+%s WHERE id=true", (len(text.encode("utf-8")),))
            conn.execute("UPDATE documents SET format_flags=%s::jsonb,content_family=%s WHERE id=%s AND content_family IS NULL",
                         (json.dumps(format_flags(text)), family_id(text), doc_id))
            conn.execute("INSERT INTO sample_decisions(doc_id,sampling_run_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (doc_id, sampling_run_id))
            if existing_job and existing_job["sampling_run_id"] != sampling_run_id:
                raise ValueError("labeling job already belongs to a different sampling run")
            conn.execute("INSERT INTO jobs(run_id,doc_id,sampling_run_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (labeling_run_id, doc_id, sampling_run_id))
        return doc_id

    @staticmethod
    def _check_storage(conn, text: str, max_database_bytes: int, doc_id: str, *, candidate: bool = False):
        if max_database_bytes <= 0:
            raise ValueError("database byte budget invalid")
        budget = conn.execute("SELECT document_bytes,candidate_bytes FROM storage_budget WHERE id=true FOR UPDATE").fetchone()
        if not candidate and conn.execute("SELECT 1 FROM documents WHERE id=%s", (doc_id,)).fetchone():
            return
        stored = budget["document_bytes"] + budget["candidate_bytes"]
        size = conn.execute("SELECT pg_database_size(current_database()) AS n").fetchone()["n"]
        if stored + len(text.encode("utf-8")) > max_database_bytes or size > max_database_bytes:
            raise ValueError("database storage budget reached")

    def consider_candidate(self, run: dict, ordinal: int, text: str | None, record_digest: str,
                           next_digest: str, max_database_bytes: int, *, invalid: bool = False):
        from .runs import sample_rank, sampling_stratum

        with self.connect() as conn:
            live = conn.execute("SELECT cursor,prefix_digest,status FROM run_controls WHERE run_id=%s FOR UPDATE", (run["run_id"],)).fetchone()
            if not live or live["status"] != "collecting" or (live["cursor"], live["prefix_digest"]) != (ordinal, run["prefix_digest"]):
                raise ValueError("concurrent or stale source cursor")
            if text is not None and (run.get("stratum", "all") == "all"
                                     or sampling_stratum(text) == run["stratum"]):
                rank = sample_rank(run["seed"], ordinal, record_digest)
                worst = conn.execute("SELECT doc_id,rank,octet_length(original_text) AS bytes FROM sample_candidates WHERE run_id=%s ORDER BY rank DESC LIMIT 1", (run["run_id"],)).fetchone()
                count = conn.execute("SELECT count(*) AS n FROM sample_candidates WHERE run_id=%s", (run["run_id"],)).fetchone()["n"]
                if count < run["sample_size"] or rank < worst["rank"]:
                    if count >= run["sample_size"]:
                        conn.execute("DELETE FROM sample_candidates WHERE run_id=%s AND doc_id=%s", (run["run_id"], worst["doc_id"]))
                        conn.execute("UPDATE storage_budget SET candidate_bytes=candidate_bytes-%s WHERE id=true", (worst["bytes"],))
                    doc_id = document_id(run["source"], run["revision"], run["config"], run["split"], ordinal, text)
                    self._check_storage(conn, text, max_database_bytes, doc_id, candidate=True)
                    conn.execute("""INSERT INTO sample_candidates(run_id,doc_id,rank,ordinal,original_text,content_sha256,format_flags,content_family)
                        VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                        (run["run_id"],doc_id,rank,ordinal,text,hashlib.sha256(text.encode()).hexdigest(),
                         json.dumps(format_flags(text)),family_id(text)))
                    conn.execute("UPDATE storage_budget SET candidate_bytes=candidate_bytes+%s WHERE id=true", (len(text.encode("utf-8")),))
            conn.execute("""UPDATE run_controls SET cursor=cursor+1,prefix_digest=%s,
                rejected_records=rejected_records+%s WHERE run_id=%s""", (next_digest, int(invalid), run["run_id"]))

    def finalize_sample(self, run_id: str, max_database_bytes: int):
        with self.connect() as conn:
            run = conn.execute("SELECT status,approved,sample_size FROM run_controls WHERE run_id=%s FOR UPDATE", (run_id,)).fetchone()
            if not run or not run["approved"] or run["status"] != "collecting":
                raise ValueError("run not collecting")
            conn.execute("SELECT document_bytes FROM storage_budget WHERE id=true FOR UPDATE")
            count = conn.execute("SELECT count(*) AS n FROM sample_candidates WHERE run_id=%s", (run_id,)).fetchone()["n"]
            if count != run["sample_size"]:
                raise ValueError("not enough eligible source documents within scan window")
            for candidate in conn.execute("SELECT * FROM sample_candidates WHERE run_id=%s ORDER BY ordinal", (run_id,)).fetchall():
                inserted = conn.execute("""INSERT INTO documents(id,source,revision,config,split,ordinal,original_text,content_sha256,format_flags,content_family)
                    SELECT %s,source,revision,config,split,%s,%s,%s,%s::jsonb,%s
                    FROM run_controls WHERE run_id=%s ON CONFLICT(id) DO NOTHING RETURNING id""",
                    (candidate["doc_id"],candidate["ordinal"],candidate["original_text"],candidate["content_sha256"],
                     json.dumps(candidate["format_flags"]),candidate["content_family"],run_id))
                if inserted.fetchone():
                    conn.execute("UPDATE storage_budget SET document_bytes=document_bytes+%s WHERE id=true",
                                 (len(candidate["original_text"].encode("utf-8")),))
            conn.execute("""INSERT INTO sample_decisions(doc_id,sampling_run_id)
                SELECT doc_id,%s FROM sample_candidates WHERE run_id=%s ON CONFLICT DO NOTHING""", (run_id, run_id))
            conn.execute("""INSERT INTO jobs(run_id,doc_id,sampling_run_id)
                SELECT %s,doc_id,%s FROM sample_candidates WHERE run_id=%s ON CONFLICT DO NOTHING""", (run_id,run_id,run_id))
            discarded = conn.execute("DELETE FROM sample_candidates WHERE run_id=%s RETURNING octet_length(original_text) AS bytes", (run_id,)).fetchall()
            conn.execute("UPDATE storage_budget SET candidate_bytes=candidate_bytes-%s WHERE id=true",
                         (sum(row["bytes"] for row in discarded),))
            if conn.execute("SELECT pg_database_size(current_database()) AS n").fetchone()["n"] > max_database_bytes:
                raise ValueError("database storage budget reached during finalization")
            conn.execute("UPDATE run_controls SET status='ready' WHERE run_id=%s", (run_id,))

    def claim(self, max_attempts: int, lease_seconds: int = 60):
        token = str(uuid.uuid4())
        with self.connect() as conn:
            exhausted = conn.execute("""UPDATE jobs SET status='exhausted',lease_token=NULL
                WHERE status='claimed' AND lease_until<now() AND attempt_count >= %s RETURNING id""",
                (max_attempts,)).fetchall()
            for expired in exhausted:
                conn.execute("UPDATE attempts SET outcome='interrupted',finished_at=now() WHERE job_id=%s AND outcome='started'", (expired["id"],))
                conn.execute("""UPDATE run_controls r SET status='completed' WHERE r.run_id=(SELECT run_id FROM jobs WHERE id=%s)
                    AND r.status='active' AND NOT EXISTS (SELECT 1 FROM jobs j WHERE j.run_id=r.run_id AND j.status IN ('pending','claimed'))""",
                    (expired["id"],))
            row = conn.execute("""SELECT j.id, j.run_id, j.doc_id, j.sampling_run_id, j.attempt_count, d.original_text, d.content_sha256
                FROM jobs j JOIN documents d ON d.id=j.doc_id JOIN run_controls r ON r.run_id=j.run_id
                WHERE (j.status='pending' AND j.available_at<=now()
                    OR j.status='claimed' AND j.lease_until<now()) AND j.attempt_count<%s AND r.status='active' AND r.approved
                ORDER BY j.id LIMIT 1 FOR UPDATE OF j SKIP LOCKED""", (max_attempts,)).fetchone()
            if row:
                conn.execute("UPDATE attempts SET outcome='interrupted',finished_at=now() WHERE job_id=%s AND outcome='started'", (row["id"],))
                conn.execute("""UPDATE jobs SET status='claimed',attempt_count=attempt_count+1,
                    lease_token=%s,lease_until=now()+(%s * interval '1 second') WHERE id=%s""",
                    (token, lease_seconds, row["id"]))
                row["lease_token"] = token
            return row

    def begin_attempt(self, job: dict, model: str, profile: str, endpoint_fingerprint: str):
        with self.connect() as conn:
            live = conn.execute("SELECT lease_token,status FROM jobs WHERE id=%s FOR UPDATE", (job["id"],)).fetchone()
            if not live or live["status"] != "claimed" or live["lease_token"] != job["lease_token"]:
                raise ValueError("stale job claim")
            return conn.execute("""INSERT INTO attempts(job_id,teacher_model,teacher_profile,outcome,prompt_version,schema_version,endpoint_fingerprint,lease_token)
                VALUES (%s,%s,%s,'started','turkish_cpt_quality_teacher_v2','teacher_label_v1',%s,%s) RETURNING id""",
                (job["id"], model, profile, endpoint_fingerprint, job["lease_token"])).fetchone()["id"]

    def finish(self, job: dict, *, model: str, profile: str, label: dict | None = None,
               error_class: str | None = None, max_attempts: int = 3, attempt_id: int | None = None):
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
                conn.execute("""INSERT INTO route_decisions(run_id,doc_id,policy_version,route)
                    VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (job["run_id"], job["doc_id"], POLICY_VERSION, route(label)))
            if attempt_id is None:
                conn.execute("INSERT INTO attempts(job_id,teacher_model,teacher_profile,outcome,error_class,finished_at) VALUES (%s,%s,%s,%s,%s,now())",
                             (job["id"], model, profile, "accepted" if label else "failed", error_class))
            else:
                result = conn.execute("""UPDATE attempts SET outcome=%s,error_class=%s,finished_at=now()
                    WHERE id=%s AND job_id=%s AND lease_token=%s AND outcome='started'""",
                    ("accepted" if label else "failed", error_class, attempt_id, job["id"], job["lease_token"]))
                if result.rowcount != 1:
                    raise ValueError("missing current attempt")
            next_status = "done" if label else ("exhausted" if locked["attempt_count"] >= max_attempts else "pending")
            conn.execute("""UPDATE jobs SET status=%s,lease_token=NULL,lease_until=NULL,
                available_at=now()+interval '5 seconds' WHERE id=%s""", (next_status, job["id"]))
            remaining = conn.execute("SELECT 1 FROM jobs WHERE run_id=%s AND status IN ('pending','claimed') LIMIT 1", (job["run_id"],)).fetchone()
            if not remaining:
                conn.execute("UPDATE run_controls SET status='completed' WHERE run_id=%s AND status='active'", (job["run_id"],))
            return True

    def heartbeat(self, worker_id: str):
        with self.connect() as conn:
            conn.execute("""INSERT INTO worker_state(worker_id,heartbeat_at) VALUES (%s,now())
                ON CONFLICT(worker_id) DO UPDATE SET heartbeat_at=excluded.heartbeat_at""", (worker_id,))

    def worker_alive(self) -> bool:
        with self.connect() as conn:
            return bool(conn.execute("SELECT 1 FROM worker_state WHERE heartbeat_at>now()-interval '30 seconds' LIMIT 1").fetchone())
