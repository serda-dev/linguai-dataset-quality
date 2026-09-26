import hmac
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .db import Store
from .settings import Settings

app = FastAPI(title="LinguAI quality control plane", docs_url=None, redoc_url=None)


def config() -> Settings:
    return Settings.from_env()


def authorized(authorization: str = Header(default=""), settings: Settings = Depends(config)):
    expected = "Bearer " + settings.admin_token
    if not settings.admin_token or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


class Enrollment(BaseModel):
    source: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    config: str = ""
    split: str = "train"
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1)
    sampling_run_id: str = Field(min_length=1)
    labeling_run_id: str = Field(min_length=1)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready(settings: Settings = Depends(config)):
    try:
        Store(settings.database_url).ping()
        worker = Store(settings.database_url).worker_alive()
        path = Path(settings.artifact_dir)
        if not path.is_dir():
            raise RuntimeError("artifact directory unavailable")
        # Prove actual write/read capability without changing a durable artifact.
        with tempfile.NamedTemporaryFile(dir=path, prefix=".ready-", delete=True) as probe:
            probe.write(b"ok")
            probe.flush()
            probe.seek(0)
            if probe.read() != b"ok":
                raise RuntimeError("artifact path read/write failed")
        if not settings.teacher_base_url or not settings.teacher_model or not settings.teacher_profile or not worker:
            raise RuntimeError("worker or teacher profile unavailable")
        return {"status": "ready", "worker": "alive", "teacher_profile": "configured"}
    except Exception:
        raise HTTPException(status_code=503, detail="not ready") from None


@app.post("/documents", dependencies=[Depends(authorized)], status_code=202)
def enroll(body: Enrollment, settings: Settings = Depends(config)):
    try:
        doc_id = Store(settings.database_url).enroll(**body.model_dump(), max_bytes=settings.max_document_bytes)
        return {"id": doc_id, "queued": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
