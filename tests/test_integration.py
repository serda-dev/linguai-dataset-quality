import os
import time
import uuid

import pytest

from linguai_quality.db import Store
from linguai_quality.settings import Settings
from linguai_quality.teacher import TeacherClient
from linguai_quality.worker import step


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
    settings = Settings.from_env()
    doc = store.enroll(source="fixture", revision="v1", config="", split="train", ordinal=1,
                       text="Türkçe öğrenme örneği", sampling_run_id="sample_test", labeling_run_id=run, max_bytes=100)
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
    settings = Settings.from_env()
    doc = store.enroll(source="fixture", revision="v1", config="", split="train", ordinal=2,
                       text="MOCK_WRONG_ID", sampling_run_id="sample_test", labeling_run_id=run, max_bytes=100)
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
