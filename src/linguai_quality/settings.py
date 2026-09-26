import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    admin_token: str
    teacher_base_url: str
    teacher_api_key: str
    teacher_model: str
    teacher_profile: str
    artifact_dir: str
    max_document_bytes: int = 100_000
    max_attempts: int = 3
    max_database_bytes: int = 8_000_000_000
    max_export_bytes: int = 1_000_000_000
    min_artifact_free_bytes: int = 2_000_000_000
    unapproved_ceiling: int = 5_000
    full_run_approval_token: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ["DATABASE_URL"], admin_token=os.environ["ADMIN_TOKEN"],
            teacher_base_url=os.environ["TEACHER_BASE_URL"], teacher_api_key=os.environ.get("TEACHER_API_KEY", ""),
            teacher_model=os.environ["TEACHER_MODEL"], teacher_profile=os.environ["TEACHER_PROFILE"],
            artifact_dir=os.environ["ARTIFACT_DIR"],
            max_document_bytes=int(os.environ.get("MAX_DOCUMENT_BYTES", "100000")),
            max_attempts=int(os.environ.get("MAX_ATTEMPTS", "3")),
            max_database_bytes=int(os.environ.get("MAX_DATABASE_BYTES", "8000000000")),
            max_export_bytes=int(os.environ.get("MAX_EXPORT_BYTES", "1000000000")),
            min_artifact_free_bytes=int(os.environ.get("MIN_ARTIFACT_FREE_BYTES", "2000000000")),
            unapproved_ceiling=int(os.environ.get("UNAPPROVED_JOB_CEILING", "5000")),
            full_run_approval_token=os.environ.get("FULL_RUN_APPROVAL_TOKEN", ""),
        )
