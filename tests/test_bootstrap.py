from dataclasses import replace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from linguai_quality import api, init_db
from linguai_quality.settings import Settings
from linguai_quality.worker import step


def configured():
    return Settings("postgresql://unused", "test-admin", "https://teacher.invalid/v1",
                    "", "test-model", "test-profile", "/tmp")


@pytest.mark.parametrize("field", ["teacher_base_url", "teacher_model", "teacher_profile"])
@pytest.mark.parametrize("missing", ["", "   "])
def test_missing_teacher_cannot_claim_or_activate_a_run(monkeypatch, field, missing):
    settings = replace(configured(), **{field: missing})
    store, teacher, transition = Mock(), Mock(), Mock()
    assert not step(store, teacher, settings)
    assert store.mock_calls == []  # Including no claim/attempt/retry mutation.
    assert teacher.mock_calls == []
    monkeypatch.setattr(api, "transition", transition)
    api.app.dependency_overrides[api.config] = lambda: settings
    try:
        with TestClient(api.app) as client:
            response = client.post("/runs/existing-run/start", headers={"Authorization": "Bearer test-admin"})
            assert response.status_code == 503
            assert response.json() == {"detail": "teacher is not configured"}
            assert client.get("/health").status_code == 200
        transition.assert_not_called()
    finally:
        api.app.dependency_overrides.clear()


def test_configuration_is_optional_until_gpu_is_connected(monkeypatch):
    for name in ("TEACHER_BASE_URL", "TEACHER_MODEL", "TEACHER_PROFILE", "TEACHER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin")
    monkeypatch.setenv("ARTIFACT_DIR", "/tmp")
    assert not Settings.from_env().teacher_configured
    monkeypatch.setenv("TEACHER_BASE_URL", "https://teacher.invalid/v1")
    monkeypatch.setenv("TEACHER_MODEL", "model")
    monkeypatch.setenv("TEACHER_PROFILE", "profile-v1")
    assert Settings.from_env().teacher_configured


def test_database_init_needs_only_database_configuration(monkeypatch):
    for name in ("ADMIN_TOKEN", "ARTIFACT_DIR", "TEACHER_BASE_URL", "TEACHER_MODEL", "TEACHER_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    store = Mock()
    monkeypatch.setattr(init_db, "Store", store)
    init_db.main()
    store.assert_called_once_with("postgresql://unused")
    store.return_value.initialize.assert_called_once_with()


def test_ready_does_not_treat_unconfigured_teacher_as_ready(monkeypatch, tmp_path):
    settings = replace(configured(), teacher_model="", artifact_dir=str(tmp_path))
    store = Mock()
    store.return_value.worker_alive.return_value = True
    monkeypatch.setattr(api, "Store", store)
    api.app.dependency_overrides[api.config] = lambda: settings
    try:
        with TestClient(api.app) as client:
            assert client.get("/ready").status_code == 503
            api.app.dependency_overrides[api.config] = lambda: replace(settings, teacher_model="model")
            response = client.get("/ready")
            assert response.status_code == 200
            assert response.json()["teacher_profile"] == "configured"
    finally:
        api.app.dependency_overrides.clear()
