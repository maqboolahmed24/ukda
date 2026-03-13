import re
from dataclasses import asdict
from datetime import datetime
from functools import lru_cache
from typing import Any
from uuid import uuid4

from app.audit.context import current_request_id
from app.audit.models import (
    AuditEventRecord,
    AuditEventType,
    AuditIntegrityStatus,
    AuditRequestContext,
)
from app.audit.store import AuditEventNotFoundError, AuditStore, AuditStoreUnavailableError
from app.core.config import Settings, get_settings
from app.telemetry.service import get_telemetry_service

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "password",
    "secret",
    "raw",
    "content",
    "bytes",
)

_METADATA_ALLOWLIST: dict[AuditEventType, set[str]] = {
    "USER_LOGIN": {"auth_method", "auth_source", "session_id"},
    "USER_LOGOUT": {"auth_source", "session_id"},
    "AUTH_FAILED": {"reason", "auth_source", "route", "status_code"},
    "PROJECT_CREATED": {
        "project_name",
        "intended_access_tier",
        "baseline_policy_snapshot_id",
    },
    "PROJECT_MEMBER_ADDED": {"member_user_id", "member_role"},
    "PROJECT_MEMBER_REMOVED": {"member_user_id", "member_role"},
    "PROJECT_MEMBER_ROLE_CHANGED": {
        "member_user_id",
        "previous_role",
        "new_role",
    },
    "BASELINE_POLICY_SNAPSHOT_SEEDED": {
        "snapshot_id",
        "seeded_by",
    },
    "PROJECT_BASELINE_POLICY_ATTACHED": {
        "project_id",
        "baseline_policy_snapshot_id",
    },
    "AUDIT_LOG_VIEWED": {
        "project_filter",
        "actor_filter",
        "event_type_filter",
        "from",
        "to",
        "cursor",
        "returned_count",
    },
    "AUDIT_EVENT_VIEWED": {"viewed_event_id", "viewed_event_type"},
    "MY_ACTIVITY_VIEWED": {"returned_count"},
    "OUTBOUND_CALL_BLOCKED": {"method", "url", "host", "purpose", "reason"},
    "EXPORT_STUB_ROUTE_ACCESSED": {
        "route",
        "method",
        "status_code",
        "stub_event_id",
    },
    "ADMIN_SECURITY_STATUS_VIEWED": {"csp_mode", "egress_deny_test"},
    "ACCESS_DENIED": {"route", "required_roles", "status_code"},
    "JOB_LIST_VIEWED": {"cursor", "returned_count"},
    "JOB_RUN_CREATED": {"job_type", "status", "attempt_number", "retry_of_job_id"},
    "JOB_RUN_STARTED": {"job_type", "status", "attempt_number", "worker_id"},
    "JOB_RUN_FINISHED": {"job_type", "status", "worker_id"},
    "JOB_RUN_FAILED": {"job_type", "status", "worker_id", "attempts", "max_attempts"},
    "JOB_RUN_CANCELED": {"job_type", "status", "worker_id", "mode"},
    "JOB_RUN_VIEWED": {"status", "cursor", "returned_count"},
    "JOB_RUN_STATUS_VIEWED": {"status"},
    "OPERATIONS_OVERVIEW_VIEWED": {"returned_count"},
    "OPERATIONS_SLOS_VIEWED": {"returned_count"},
    "OPERATIONS_ALERTS_VIEWED": {"state_filter", "cursor", "returned_count"},
    "OPERATIONS_TIMELINE_VIEWED": {"scope_filter", "cursor", "returned_count"},
}


def _sanitize_text(value: str, *, max_length: int = 512) -> str:
    collapsed = _CONTROL_CHARS_RE.sub(" ", value)
    collapsed = collapsed.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    collapsed = " ".join(collapsed.split())
    return collapsed[:max_length]


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _sanitize_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_value(entry) for entry in value[:20]]
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for raw_key, raw_value in list(value.items())[:20]:
            key = _sanitize_text(str(raw_key), max_length=64)
            if _is_sensitive_key(key):
                continue
            sanitized[key] = _sanitize_value(raw_value)
        return sanitized
    return _sanitize_text(str(value))


def _sanitize_metadata(
    *,
    event_type: AuditEventType,
    metadata: dict[str, object] | None,
) -> dict[str, object]:
    if metadata is None:
        return {}
    allowed = _METADATA_ALLOWLIST[event_type]
    sanitized: dict[str, object] = {}
    for raw_key, raw_value in metadata.items():
        key = _sanitize_text(raw_key, max_length=64)
        if key not in allowed:
            continue
        if _is_sensitive_key(key):
            continue
        sanitized[key] = _sanitize_value(raw_value)
    return sanitized


class AuditService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: AuditStore | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or AuditStore(settings)

    def record_event(
        self,
        *,
        event_type: AuditEventType,
        actor_user_id: str | None,
        project_id: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        metadata: dict[str, object] | None = None,
        request_context: AuditRequestContext | None = None,
        request_id: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEventRecord:
        context = request_context
        resolved_request_id = (
            request_id
            or (context.request_id if context else None)
            or current_request_id()
            or str(uuid4())
        )
        resolved_ip = ip if ip is not None else (context.ip if context else None)
        resolved_user_agent = (
            user_agent if user_agent is not None else (context.user_agent if context else None)
        )

        sanitized_metadata = _sanitize_metadata(event_type=event_type, metadata=metadata)
        sanitized_object_type = _sanitize_text(object_type, max_length=100) if object_type else None
        sanitized_object_id = _sanitize_text(object_id, max_length=128) if object_id else None
        sanitized_project_id = _sanitize_text(project_id, max_length=128) if project_id else None
        sanitized_ip = _sanitize_text(resolved_ip, max_length=64) if resolved_ip else None
        sanitized_user_agent = (
            _sanitize_text(resolved_user_agent, max_length=320) if resolved_user_agent else None
        )

        telemetry_service = get_telemetry_service()

        try:
            record = self._store.append_event(
                actor_user_id=actor_user_id,
                project_id=sanitized_project_id,
                event_type=event_type,
                object_type=sanitized_object_type,
                object_id=sanitized_object_id,
                ip=sanitized_ip,
                user_agent=sanitized_user_agent,
                request_id=resolved_request_id,
                metadata_json=sanitized_metadata,
            )
        except AuditStoreUnavailableError:
            telemetry_service.record_audit_write(success=False, event_type=event_type)
            raise

        telemetry_service.record_audit_write(success=True, event_type=event_type)
        return record

    def record_event_best_effort(
        self,
        *,
        event_type: AuditEventType,
        actor_user_id: str | None,
        project_id: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        metadata: dict[str, object] | None = None,
        request_context: AuditRequestContext | None = None,
        request_id: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEventRecord | None:
        try:
            return self.record_event(
                event_type=event_type,
                actor_user_id=actor_user_id,
                project_id=project_id,
                object_type=object_type,
                object_id=object_id,
                metadata=metadata,
                request_context=request_context,
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
            )
        except AuditStoreUnavailableError:
            return None

    def list_events(
        self,
        *,
        project_id: str | None,
        actor_user_id: str | None,
        event_type: AuditEventType | None,
        from_timestamp: datetime | None,
        to_timestamp: datetime | None,
        cursor: int,
        page_size: int,
    ) -> tuple[list[AuditEventRecord], int | None]:
        return self._store.list_events(
            project_id=project_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            cursor=cursor,
            page_size=page_size,
        )

    def get_event(self, *, event_id: str) -> AuditEventRecord:
        return self._store.get_event(event_id=event_id)

    def list_my_activity(
        self,
        *,
        actor_user_id: str,
        limit: int,
    ) -> list[AuditEventRecord]:
        return self._store.list_user_activity(actor_user_id=actor_user_id, limit=limit)

    def verify_integrity(self) -> AuditIntegrityStatus:
        return self._store.verify_integrity()

    @staticmethod
    def as_record_payload(record: AuditEventRecord) -> dict[str, Any]:
        return asdict(record)

    @staticmethod
    def is_event_not_found(error: Exception) -> bool:
        return isinstance(error, AuditEventNotFoundError)


@lru_cache
def get_audit_service() -> AuditService:
    settings = get_settings()
    return AuditService(settings=settings)
