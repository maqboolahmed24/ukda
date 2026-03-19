from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

RecoveryDrillScope = Literal[
    "QUEUE_REPLAY",
    "STORAGE_INTERRUPT",
    "RESTORE_CLEAN_ENV",
    "FULL_RECOVERY",
]
RecoveryDrillStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
RecoveryDrillEventType = Literal[
    "DRILL_CREATED",
    "DRILL_STARTED",
    "DRILL_FINISHED",
    "DRILL_FAILED",
    "DRILL_CANCELED",
]


@dataclass(frozen=True)
class RecoveryDrillRecord:
    id: str
    scope: RecoveryDrillScope
    status: RecoveryDrillStatus
    started_by: str
    started_at: datetime | None
    finished_at: datetime | None
    canceled_by: str | None
    canceled_at: datetime | None
    evidence_summary_json: dict[str, object]
    failure_reason: str | None
    evidence_storage_key: str | None
    evidence_storage_sha256: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RecoveryDrillEventRecord:
    id: int
    drill_id: str
    event_type: RecoveryDrillEventType
    from_status: RecoveryDrillStatus | None
    to_status: RecoveryDrillStatus
    actor_user_id: str | None
    details_json: dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class RecoveryDrillPage:
    items: list[RecoveryDrillRecord]
    next_cursor: int | None
