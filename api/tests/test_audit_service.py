from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.audit.models import AuditEventRecord, AuditRequestContext
from app.audit.service import AuditService
from app.audit.store import AuditStore, AuditStoreUnavailableError
from app.core.config import get_settings


@dataclass
class CapturedAppend:
    actor_user_id: str | None
    project_id: str | None
    event_type: str
    object_type: str | None
    object_id: str | None
    ip: str | None
    user_agent: str | None
    request_id: str
    metadata_json: dict[str, object]


class FakeAuditStore:
    def __init__(self) -> None:
        self.captured: CapturedAppend | None = None

    def append_event(self, **kwargs) -> AuditEventRecord:  # type: ignore[no-untyped-def]
        self.captured = CapturedAppend(**kwargs)
        return AuditEventRecord(
            id=str(uuid4()),
            chain_index=1,
            timestamp=datetime.now(UTC),
            actor_user_id=kwargs["actor_user_id"],
            project_id=kwargs["project_id"],
            event_type=kwargs["event_type"],
            object_type=kwargs["object_type"],
            object_id=kwargs["object_id"],
            ip=kwargs["ip"],
            user_agent=kwargs["user_agent"],
            request_id=kwargs["request_id"],
            metadata_json=kwargs["metadata_json"],
            prev_hash="GENESIS",
            row_hash="row-hash",
        )


class FailingAuditStore(FakeAuditStore):
    def append_event(self, **kwargs) -> AuditEventRecord:  # type: ignore[no-untyped-def]
        raise AuditStoreUnavailableError("unavailable")


def test_record_event_sanitizes_metadata_and_drops_sensitive_fields() -> None:
    store = FakeAuditStore()
    service = AuditService(settings=get_settings(), store=store)  # type: ignore[arg-type]

    context = AuditRequestContext(
        request_id="req-audit-123",
        method="POST",
        route_template="/projects",
        path="/projects",
        ip="127.0.0.1",
        user_agent="Test\nAgent",
    )
    service.record_event(
        event_type="PROJECT_CREATED",
        actor_user_id="user-1",
        project_id="project-1",
        object_type="project",
        object_id="project-1",
        metadata={
            "project_name": "Diaries\nCollection",
            "baseline_policy_snapshot_id": "baseline-phase0-v1",
            "intended_access_tier": "CONTROLLED",
            "session_token": "should-not-appear",
            "arbitrary": "drop-this",
        },
        request_context=context,
    )

    assert store.captured is not None
    assert store.captured.request_id == "req-audit-123"
    assert store.captured.user_agent == "Test Agent"
    assert store.captured.metadata_json == {
        "project_name": "Diaries Collection",
        "baseline_policy_snapshot_id": "baseline-phase0-v1",
        "intended_access_tier": "CONTROLLED",
    }


def test_record_event_supports_non_http_writer_context() -> None:
    store = FakeAuditStore()
    service = AuditService(settings=get_settings(), store=store)  # type: ignore[arg-type]

    service.record_event(
        event_type="PROJECT_MEMBER_ADDED",
        actor_user_id="user-2",
        project_id="project-2",
        metadata={
            "member_user_id": "user-3",
            "member_role": "RESEARCHER",
        },
        request_id="job-run-42",
        ip="10.10.0.4",
        user_agent="worker",
    )

    assert store.captured is not None
    assert store.captured.request_id == "job-run-42"
    assert store.captured.ip == "10.10.0.4"
    assert store.captured.user_agent == "worker"


def test_record_event_best_effort_swallows_store_errors() -> None:
    service = AuditService(
        settings=get_settings(),
        store=FailingAuditStore(),  # type: ignore[arg-type]
    )
    result = service.record_event_best_effort(
        event_type="AUTH_FAILED",
        actor_user_id=None,
        metadata={
            "reason": "invalid_or_expired_session",
            "auth_source": "bearer",
            "route": "/projects",
            "status_code": 401,
        },
        request_id="req-1",
    )
    assert result is None


def test_verify_chain_detects_tampered_hash_rows() -> None:
    timestamp = datetime.now(UTC)
    metadata = {"auth_method": "dev", "auth_source": "dev", "session_id": "s1"}
    row1 = AuditEventRecord(
        id="event-1",
        chain_index=1,
        timestamp=timestamp,
        actor_user_id="user-1",
        project_id=None,
        event_type="USER_LOGIN",
        object_type="session",
        object_id="s1",
        ip="127.0.0.1",
        user_agent="ua",
        request_id="req-1",
        metadata_json=metadata,
        prev_hash="GENESIS",
        row_hash=AuditStore._row_hash(
            chain_index=1,
            event_id="event-1",
            timestamp=timestamp,
            actor_user_id="user-1",
            project_id=None,
            event_type="USER_LOGIN",
            object_type="session",
            object_id="s1",
            ip="127.0.0.1",
            user_agent="ua",
            request_id="req-1",
            metadata_json=metadata,
            prev_hash="GENESIS",
        ),
    )
    row2 = AuditEventRecord(
        id="event-2",
        chain_index=2,
        timestamp=timestamp,
        actor_user_id="user-1",
        project_id=None,
        event_type="USER_LOGOUT",
        object_type="session",
        object_id="s1",
        ip="127.0.0.1",
        user_agent="ua",
        request_id="req-2",
        metadata_json={"auth_source": "cookie", "session_id": "s1"},
        prev_hash=row1.row_hash,
        row_hash="tampered",
    )

    integrity = AuditStore.verify_chain([row1, row2])

    assert integrity.is_valid is False
    assert integrity.first_invalid_chain_index == 2
    assert integrity.first_invalid_event_id == "event-2"


def test_verify_chain_accepts_valid_hash_rows() -> None:
    timestamp = datetime.now(UTC)
    row1_metadata = {"auth_method": "dev", "auth_source": "dev", "session_id": "s1"}
    row1_hash = AuditStore._row_hash(
        chain_index=1,
        event_id="event-1",
        timestamp=timestamp,
        actor_user_id="user-1",
        project_id=None,
        event_type="USER_LOGIN",
        object_type="session",
        object_id="s1",
        ip="127.0.0.1",
        user_agent="ua",
        request_id="req-1",
        metadata_json=row1_metadata,
        prev_hash="GENESIS",
    )
    row2_metadata = {"auth_source": "cookie", "session_id": "s1"}
    row2_hash = AuditStore._row_hash(
        chain_index=2,
        event_id="event-2",
        timestamp=timestamp,
        actor_user_id="user-1",
        project_id=None,
        event_type="USER_LOGOUT",
        object_type="session",
        object_id="s1",
        ip="127.0.0.1",
        user_agent="ua",
        request_id="req-2",
        metadata_json=row2_metadata,
        prev_hash=row1_hash,
    )
    row1 = AuditEventRecord(
        id="event-1",
        chain_index=1,
        timestamp=timestamp,
        actor_user_id="user-1",
        project_id=None,
        event_type="USER_LOGIN",
        object_type="session",
        object_id="s1",
        ip="127.0.0.1",
        user_agent="ua",
        request_id="req-1",
        metadata_json=row1_metadata,
        prev_hash="GENESIS",
        row_hash=row1_hash,
    )
    row2 = AuditEventRecord(
        id="event-2",
        chain_index=2,
        timestamp=timestamp,
        actor_user_id="user-1",
        project_id=None,
        event_type="USER_LOGOUT",
        object_type="session",
        object_id="s1",
        ip="127.0.0.1",
        user_agent="ua",
        request_id="req-2",
        metadata_json=row2_metadata,
        prev_hash=row1_hash,
        row_hash=row2_hash,
    )

    integrity = AuditStore.verify_chain([row1, row2])

    assert integrity.is_valid is True
    assert integrity.first_invalid_chain_index is None
    assert integrity.first_invalid_event_id is None
