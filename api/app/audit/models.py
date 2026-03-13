from dataclasses import dataclass
from datetime import datetime
from typing import Literal

AuditEventType = Literal[
    "USER_LOGIN",
    "USER_LOGOUT",
    "AUTH_FAILED",
    "PROJECT_CREATED",
    "PROJECT_MEMBER_ADDED",
    "PROJECT_MEMBER_REMOVED",
    "PROJECT_MEMBER_ROLE_CHANGED",
    "BASELINE_POLICY_SNAPSHOT_SEEDED",
    "PROJECT_BASELINE_POLICY_ATTACHED",
    "AUDIT_LOG_VIEWED",
    "AUDIT_EVENT_VIEWED",
    "MY_ACTIVITY_VIEWED",
    "OUTBOUND_CALL_BLOCKED",
    "EXPORT_STUB_ROUTE_ACCESSED",
    "ADMIN_SECURITY_STATUS_VIEWED",
    "ACCESS_DENIED",
    "JOB_LIST_VIEWED",
    "JOB_RUN_CREATED",
    "JOB_RUN_STARTED",
    "JOB_RUN_FINISHED",
    "JOB_RUN_FAILED",
    "JOB_RUN_CANCELED",
    "JOB_RUN_VIEWED",
    "JOB_RUN_STATUS_VIEWED",
    "OPERATIONS_OVERVIEW_VIEWED",
    "OPERATIONS_SLOS_VIEWED",
    "OPERATIONS_ALERTS_VIEWED",
    "OPERATIONS_TIMELINE_VIEWED",
]


@dataclass(frozen=True)
class AuditRequestContext:
    request_id: str
    method: str
    route_template: str
    path: str
    ip: str | None
    user_agent: str | None


@dataclass(frozen=True)
class AuditEventRecord:
    id: str
    chain_index: int
    timestamp: datetime
    actor_user_id: str | None
    project_id: str | None
    event_type: AuditEventType
    object_type: str | None
    object_id: str | None
    ip: str | None
    user_agent: str | None
    request_id: str
    metadata_json: dict[str, object]
    prev_hash: str
    row_hash: str


@dataclass(frozen=True)
class AuditIntegrityStatus:
    checked_rows: int
    chain_head: str | None
    is_valid: bool
    first_invalid_chain_index: int | None
    first_invalid_event_id: str | None
    detail: str
