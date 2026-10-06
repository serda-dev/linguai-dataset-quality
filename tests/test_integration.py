import os
import time
import uuid

import pytest

from linguai_quality.db import Store
from linguai_quality.settings import Settings
from linguai_quality.teacher import TeacherClient
from linguai_quality.worker import step
from linguai_quality.runs import SourcePlan, approve_run, create_run, ingest_records, transition, get_run
from linguai_quality.export import export_labels


def manual_run(store, run, sample_size=2):
    create_run(store, SourcePlan(run, "manual", "manual-v1", "", "train", "text", 7,
                                 sample_size, sample_size, True))
    approve_run(store, run, supplied_full_token="", configured_full_token="", unapproved_ceiling=5000)
    transition(store, run, "draft", "collecting")


def activate(store, run):
    transition(store, run, "collecting", "ready")
    transition(store, run, "ready", "active")


@pytest.fixture
def store():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL integration runs in Docker")
    result = Store(url)
    for _ in range(20):
        try:
            result.initialize()
            break
        except Exception:
            time.sleep(1)
    else:
        pytest.fail("test PostgreSQL unavailable")
    return result


def test_claim_recovery_and_accepted_label_provenance(store):
    run = str(uuid.uuid4())
    manual_run(store, run)
    settings = Settings.from_env()
    doc = store.enroll(source="manual", revision="manual-v1", config="", split="train", ordinal=1,
                       text="Türkçe öğrenme örneği", sampling_run_id="sample_test", labeling_run_id=run, max_bytes=100)
    activate(store, run)
    claim = store.claim(3, lease_seconds=-1)
    assert claim["doc_id"] == doc
    recovered = store.claim(3)
    assert recovered["id"] == claim["id"]
    assert not store.finish(claim, model="old", profile="old", error_class="Late", max_attempts=3)
    client = TeacherClient(settings.teacher_base_url, settings.teacher_api_key, settings.teacher_model)
    label = client.label(doc, recovered["original_text"])
    assert store.finish(recovered, model=settings.teacher_model, profile=settings.teacher_profile, label=label)
    with store.connect() as conn:
        saved = conn.execute("SELECT route, teacher_model, prompt_version, document_hash FROM labels WHERE run_id=%s", (run,)).fetchone()
        assert saved["route"] == "DETERMINISTIC_REPAIR"
        assert saved["teacher_model"] == settings.teacher_model
        assert saved["prompt_version"] == "turkish_cpt_quality_teacher_v2"
        assert len(saved["document_hash"]) == 64
        assert conn.execute("SELECT count(*) AS n FROM labels WHERE run_id=%s", (run,)).fetchone()["n"] == 1


def test_invalid_response_exhausts_without_label(store):
    run = str(uuid.uuid4())
    manual_run(store, run)
    settings = Settings.from_env()
    doc = store.enroll(source="manual", revision="manual-v1", config="", split="train", ordinal=2,
                       text="MOCK_WRONG_ID", sampling_run_id="sample_test", labeling_run_id=run, max_bytes=100)
    activate(store, run)
    client = TeacherClient(settings.teacher_base_url, settings.teacher_api_key, settings.teacher_model)
    for _ in range(2):
        job = store.claim(3)
        with pytest.raises(ValueError):
            client.label(doc, job["original_text"])
        assert store.finish(job, model=settings.teacher_model, profile=settings.teacher_profile,
                            error_class="ValueError", max_attempts=2)
        with store.connect() as conn:
            conn.execute("UPDATE jobs SET available_at=now()-interval '1 second' WHERE id=%s", (job["id"],))
    with store.connect() as conn:
        assert conn.execute("SELECT status FROM jobs WHERE run_id=%s", (run,)).fetchone()["status"] == "exhausted"
        assert conn.execute("SELECT count(*) AS n FROM labels WHERE run_id=%s", (run,)).fetchone()["n"] == 0


def test_readiness_tracks_database_worker_and_configuration(store):
    store.heartbeat("test-worker")
    assert store.worker_alive()


def test_cumulative_reservations_require_separate_approval(store):
    with store.connect() as conn:
        starting = conn.execute("SELECT reserved_count AS n FROM teacher_budget WHERE id=true").fetchone()["n"]
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    for run, quota in ((first, 2), (second, 1)):
        create_run(store, SourcePlan(run, "manual", "manual-v1", "", "train", "text", 1, quota, quota, True))
    approve_run(store, first, supplied_full_token="", configured_full_token="separate", unapproved_ceiling=starting+3)
    with pytest.raises(PermissionError):
        approve_run(store, second, supplied_full_token="", configured_full_token="separate", unapproved_ceiling=starting+3)
    with store.connect() as conn:
        assert conn.execute("SELECT reserved_count AS n FROM teacher_budget WHERE id=true").fetchone()["n"] == starting+2
    assert not get_run(store, second)["approved"]
    approve_run(store, second, supplied_full_token="separate", configured_full_token="separate", unapproved_ceiling=starting+3)


def test_budget_failure_does_not_enqueue_document(store):
    run = str(uuid.uuid4())
    manual_run(store, run, 1)
    with pytest.raises(ValueError, match="storage budget"):
        store.enroll(source="manual", revision="manual-v1", config="", split="train", ordinal=817,
                     text="veri", sampling_run_id="sample_budget", labeling_run_id=run,
                     max_bytes=100, max_database_bytes=1)
    with store.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM jobs WHERE run_id=%s", (run,)).fetchone()["n"] == 0


def test_approval_quota_and_persisted_prefix_resume(store):
    run = str(uuid.uuid4())
    create_run(store, SourcePlan(run, "fixture/hf", "a"*40, "cfg", "train", "text", 17, 5, 2, True))
    with pytest.raises(PermissionError):
        approve_run(store, run, supplied_full_token="", configured_full_token="approval-secret", unapproved_ceiling=2)
    assert not get_run(store, run)["approved"]
    approve_run(store, run, supplied_full_token="approval-secret", configured_full_token="approval-secret", unapproved_ceiling=2)
    records = [{"text": f"Özgün cümle {i}"} for i in range(5)]

    def interrupted():
        yield from records[:3]
        raise OSError("source interrupted")

    with pytest.raises(OSError):
        ingest_records(store, run, interrupted(), max_document_bytes=1000, max_database_bytes=8_000_000_000)
    assert get_run(store, run)["cursor"] == 3
    with pytest.raises(ValueError, match="prefix changed"):
        ingest_records(store, run, [{"text":"changed"}, *records[1:]], max_document_bytes=1000,
                       max_database_bytes=8_000_000_000)
    assert get_run(store, run)["cursor"] == 3
    ingest_records(store, run, records, max_document_bytes=1000, max_database_bytes=8_000_000_000)
    assert get_run(store, run)["status"] == "ready"
    with store.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM jobs WHERE run_id=%s", (run,)).fetchone()["n"] == 2
    transition(store, run, "ready", "active")
    job = store.claim(3)
    assert job["run_id"] == run
    assert store.finish(job, model="mock", profile="test", error_class="Skipped", max_attempts=1)
    other = store.claim(3)
    assert other["run_id"] == run
    assert store.finish(other, model="mock", profile="test", error_class="Skipped", max_attempts=1)


def test_stratified_sampling_keeps_exclusive_buckets(store):
    texts = ["Normal bir Türkçe paragraf. " * 20, "Kısa parça", "def hesapla():\n    return 1"]
    for stratum, expected in zip(("normal", "noisy_edge", "structured"), texts):
        run = str(uuid.uuid4())
        create_run(store, SourcePlan(run, "fixture/hf", "a"*40, "cfg", "train", "text",
                                     17, 3, 1, True, stratum))
        approve_run(store, run, supplied_full_token="", configured_full_token="",
                    unapproved_ceiling=5000)
        ingest_records(store, run, [{"text": text} for text in texts],
                       max_document_bytes=1000, max_database_bytes=8_000_000_000)
        with store.connect() as conn:
            rows = conn.execute("""SELECT d.original_text FROM jobs j JOIN documents d ON d.id=j.doc_id
                WHERE j.run_id=%s""", (run,)).fetchall()
            assert [row["original_text"] for row in rows] == [expected]
        assert get_run(store, run)["stratum"] == stratum
        transition(store, run, "ready", "active")
        transition(store, run, "active", "paused")
        transition(store, run, "paused", "active")
        assert get_run(store, run)["status"] == "active"
        transition(store, run, "active", "paused")


def test_oversize_record_is_ineligible_without_malformed_budget(store):
    run = str(uuid.uuid4())
    create_run(store, SourcePlan(run, "fixture/hf", "a"*40, "cfg", "train", "text",
                                 17, 3, 2, True))
    approve_run(store, run, supplied_full_token="", configured_full_token="",
                unapproved_ceiling=5000)
    ingest_records(store, run, [{"text": "x" * 101}, {"text": "kısa bir"}, {"text": "ikinci kısa"}],
                   max_document_bytes=100, max_database_bytes=8_000_000_000)
    assert get_run(store, run)["rejected_records"] == 0
    with store.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM jobs WHERE run_id=%s", (run,)).fetchone()["n"] == 2


def test_nul_record_is_ineligible_and_resume_keeps_prefix(store):
    run = str(uuid.uuid4())
    create_run(store, SourcePlan(run, "fixture/hf", "a"*40, "cfg", "train", "text",
                                 17, 3, 2, True))
    approve_run(store, run, supplied_full_token="", configured_full_token="",
                unapproved_ceiling=5000)
    records = [{"text": "ilk metin"}, {"text": "bozuk\x00metin"}, {"text": "son metin"}]

    def interrupted():
        yield from records[:2]
        raise OSError("source interrupted")

    with pytest.raises(OSError):
        ingest_records(store, run, interrupted(), max_document_bytes=100,
                       max_database_bytes=8_000_000_000)
    assert get_run(store, run)["cursor"] == 2
    ingest_records(store, run, records, max_document_bytes=100,
                   max_database_bytes=8_000_000_000)
    with store.connect() as conn:
        rows = conn.execute("""SELECT d.original_text FROM jobs j JOIN documents d ON d.id=j.doc_id
            WHERE j.run_id=%s ORDER BY d.ordinal""", (run,)).fetchall()
        assert [row["original_text"] for row in rows] == ["ilk metin", "son metin"]


def test_failed_teacher_records_attempt_and_export_train_only(store, tmp_path):
    run = str(uuid.uuid4())
    manual_run(store, run, 2)
    settings = Settings.from_env()
    store.enroll(source="manual", revision="manual-v1", config="", split="train", ordinal=991,
                 text="MOCK_INVALID_JSON", sampling_run_id="s", labeling_run_id=run, max_bytes=100)
    activate(store, run)
    client = TeacherClient(settings.teacher_base_url, settings.teacher_api_key, settings.teacher_model)
    assert step(store, client, settings)
    with store.connect() as conn:
        attempt = conn.execute("""SELECT outcome,error_class,prompt_version,endpoint_fingerprint
            FROM attempts a JOIN jobs j ON a.job_id=j.id WHERE j.run_id=%s""", (run,)).fetchone()
        assert attempt["outcome"] == "failed" and attempt["error_class"] == "JSONDecodeError"
        assert attempt["prompt_version"] == "turkish_cpt_quality_teacher_v2"
        assert len(attempt["endpoint_fingerprint"]) == 16
    filename, rows = export_labels(store, str(tmp_path), max_bytes=5_000_000, min_free_bytes=0)
    import pyarrow.parquet as pq
    table = pq.read_table(tmp_path / filename)
    assert rows == table.num_rows
    assert set(table.column("split").to_pylist()) <= {"train"}


def test_unavailable_teacher_is_retryable_and_restart_keeps_job(store):
    run = str(uuid.uuid4())
    manual_run(store, run, 1)
    settings = Settings.from_env()
    store.enroll(source="manual", revision="manual-v1", config="", split="train", ordinal=992,
                 text="MOCK_UNAVAILABLE", sampling_run_id="s", labeling_run_id=run, max_bytes=100)
    activate(store, run)
    assert step(store, TeacherClient(settings.teacher_base_url, settings.teacher_api_key, settings.teacher_model), settings)
    restarted = Store(settings.database_url)
    with restarted.connect() as conn:
        job = conn.execute("SELECT status,attempt_count FROM jobs WHERE run_id=%s", (run,)).fetchone()
        assert job["status"] == "pending" and job["attempt_count"] == 1
        assert conn.execute("SELECT error_class FROM attempts a JOIN jobs j ON j.id=a.job_id WHERE j.run_id=%s", (run,)).fetchone()["error_class"] == "HTTP_503"
        conn.execute("UPDATE jobs SET available_at=now()-interval '1 second' WHERE run_id=%s", (run,))
    retried = restarted.claim(settings.max_attempts)
    assert retried["run_id"] == run and retried["attempt_count"] == 1
    assert restarted.finish(retried, model=settings.teacher_model, profile="replacement-profile",
                            error_class="HTTPStatusError", max_attempts=2)
