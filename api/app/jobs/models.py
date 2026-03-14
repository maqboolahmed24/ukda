from dataclasses import dataclass
from datetime import datetime
from typing import Literal

JobType = Literal[
    "NOOP",
    "EXTRACT_PAGES",
    "RENDER_THUMBNAILS",
    "PREPROCESS_DOCUMENT",
    "PREPROCESS_PAGE",
    "FINALIZE_PREPROCESS_RUN",
    "LAYOUT_ANALYZE_DOCUMENT",
    "LAYOUT_ANALYZE_PAGE",
    "FINALIZE_LAYOUT_RUN",
    "TRANSCRIBE_DOCUMENT",
    "TRANSCRIBE_PAGE",
    "FINALIZE_TRANSCRIPTION_RUN",
]
JobStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
JobEventType = Literal[
    "JOB_CREATED",
    "JOB_STARTED",
    "JOB_SUCCEEDED",
    "JOB_FAILED",
    "JOB_CANCELED",
    "JOB_RETRY_APPENDED",
]


@dataclass(frozen=True)
class JobRecord:
    id: str
    project_id: str
    attempt_number: int
    supersedes_job_id: str | None
    superseded_by_job_id: str | None
    type: JobType
    dedupe_key: str
    status: JobStatus
    attempts: int
    max_attempts: int
    payload_json: dict[str, object]
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    canceled_by: str | None
    canceled_at: datetime | None
    error_code: str | None
    error_message: str | None
    cancel_requested_by: str | None
    cancel_requested_at: datetime | None
    lease_owner_id: str | None
    lease_expires_at: datetime | None
    last_heartbeat_at: datetime | None

    @property
    def cancel_requested(self) -> bool:
        return self.cancel_requested_at is not None and self.status == "RUNNING"


@dataclass(frozen=True)
class JobEventRecord:
    id: int
    job_id: str
    project_id: str
    event_type: JobEventType
    from_status: JobStatus | None
    to_status: JobStatus
    actor_user_id: str | None
    details_json: dict[str, object]
    created_at: datetime
