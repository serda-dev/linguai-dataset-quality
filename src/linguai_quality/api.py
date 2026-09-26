import hmac
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .db import Store
from .settings import Settings
from .runs import SourcePlan, approve_run, create_run, get_run, transition

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


class RunRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    config: str = ""
    split: str = "train"
    text_field: str = Field(min_length=1)
    seed: int = Field(ge=0, le=2**63-1)
    max_scan: int = Field(gt=0, le=10_000_000)
    sample_size: int = Field(gt=0, le=40_000)
    license_ack: bool = False


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
        doc_id = Store(settings.database_url).enroll(**body.model_dump(), max_bytes=settings.max_document_bytes,
                                                      max_database_bytes=settings.max_database_bytes)
        return {"id": doc_id, "queued": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.post("/runs", dependencies=[Depends(authorized)], status_code=201)
def create(body: RunRequest, settings: Settings = Depends(config)):
    try:
        create_run(Store(settings.database_url), SourcePlan(**body.model_dump()))
        return {"run_id": body.run_id, "status": "draft"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.post("/runs/{run_id}/approve", dependencies=[Depends(authorized)])
def approve(run_id: str, x_full_run_approval: str = Header(default=""), settings: Settings = Depends(config)):
    try:
        approve_run(Store(settings.database_url), run_id,
                    supplied_full_token=x_full_run_approval, configured_full_token=settings.full_run_approval_token,
                    unapproved_ceiling=settings.unapproved_ceiling)
        return {"run_id": run_id, "approved": True}
    except PermissionError:
        raise HTTPException(status_code=403, detail="separate approval required") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.post("/runs/{run_id}/collect", dependencies=[Depends(authorized)])
def collect_manual(run_id: str, settings: Settings = Depends(config)):
    try:
        if get_run(Store(settings.database_url), run_id)["source"] != "manual":
            raise ValueError("HF ingestion runs through the bounded CLI")
        transition(Store(settings.database_url), run_id, "draft", "collecting")
        return {"status": "collecting"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.post("/runs/{run_id}/finish", dependencies=[Depends(authorized)])
def finish_manual(run_id: str, settings: Settings = Depends(config)):
    try:
        if get_run(Store(settings.database_url), run_id)["source"] != "manual":
            raise ValueError("HF ingestion runs through the bounded CLI")
        transition(Store(settings.database_url), run_id, "collecting", "ready")
        return {"status": "ready"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.post("/runs/{run_id}/start", dependencies=[Depends(authorized)])
def start(run_id: str, settings: Settings = Depends(config)):
    try:
        transition(Store(settings.database_url), run_id, "ready", "active")
        return {"status": "active"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.post("/runs/{run_id}/pause", dependencies=[Depends(authorized)])
def pause(run_id: str, settings: Settings = Depends(config)):
    try:
        transition(Store(settings.database_url), run_id, "active", "paused")
        return {"status": "paused"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
