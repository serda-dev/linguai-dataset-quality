import logging
import os
import hashlib
import time
import httpx

from .db import Store
from .settings import Settings
from .teacher import TeacherClient

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)
TERMINAL_TEACHER_CODES = {"invalid_teacher_label", "context_length_exceeded", "output_limit"}
KNOWN_TEACHER_CODES = TERMINAL_TEACHER_CODES | {"busy", "backend_timeout", "model_not_ready"}


def failure_detail(exc: Exception) -> tuple[str, bool]:
    """Return a bounded diagnostic class and whether identical retry is futile."""
    if not isinstance(exc, httpx.HTTPStatusError):
        return type(exc).__name__, False
    status = exc.response.status_code
    try:
        code = exc.response.json()["error"]["code"]
    except (ValueError, KeyError, TypeError):
        code = None
    if code in KNOWN_TEACHER_CODES:
        return f"HTTP_{status}_{code}", code in TERMINAL_TEACHER_CODES
    return f"HTTP_{status}", False


def step(store: Store, client: TeacherClient, settings: Settings) -> bool:
    if not settings.teacher_configured:
        return False
    job = store.claim(settings.max_attempts)
    if not job:
        return False
    endpoint_fingerprint = hashlib.sha256(settings.teacher_base_url.encode()).hexdigest()[:16]
    attempt_id = store.begin_attempt(job, settings.teacher_model, settings.teacher_profile, endpoint_fingerprint)
    try:
        label = client.label(job["doc_id"], job["original_text"])
        store.finish(job, model=settings.teacher_model, profile=settings.teacher_profile,
                     label=label, max_attempts=settings.max_attempts, attempt_id=attempt_id)
    except Exception as exc:
        # Store a bounded error class/code only; messages can contain text or secrets.
        error_class, terminal = failure_detail(exc)
        LOG.warning("teacher attempt failed: %s", error_class)
        store.finish(job, model=settings.teacher_model, profile=settings.teacher_profile,
                     error_class=error_class, max_attempts=1 if terminal else settings.max_attempts,
                     attempt_id=attempt_id)
    return True


def main():
    settings = Settings.from_env()
    store = Store(settings.database_url)
    client = TeacherClient(settings.teacher_base_url, settings.teacher_api_key, settings.teacher_model)
    while True:
        try:
            store.heartbeat("worker-1")
            if os.environ.get("WORKER_TEST_IDLE") == "1":
                time.sleep(2)
                continue
            if not step(store, client, settings):
                time.sleep(2)
        except Exception as exc:
            LOG.warning("worker paused: %s", type(exc).__name__)
            time.sleep(3)


if __name__ == "__main__":
    main()
