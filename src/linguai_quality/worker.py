import logging
import os
import hashlib
import time

from .db import Store
from .settings import Settings
from .teacher import TeacherClient

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


def step(store: Store, client: TeacherClient, settings: Settings) -> bool:
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
        # Store the exception class only. Exception messages can contain document text or secrets.
        LOG.warning("teacher attempt failed: %s", type(exc).__name__)
        store.finish(job, model=settings.teacher_model, profile=settings.teacher_profile,
                     error_class=type(exc).__name__, max_attempts=settings.max_attempts, attempt_id=attempt_id)
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
