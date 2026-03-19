from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.main import app
from app.recovery.models import RecoveryDrillRecord
from app.recovery.service import (
    RecoveryAccessDeniedError,
    RecoveryDrillNotFoundError,
    RecoveryEvidenceUnavailableError,
    get_recovery_service,
)
from fastapi.testclient import TestClient

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeRecoveryService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self._drill = RecoveryDrillRecord(
            id="recovery-drill-1",
            scope="FULL_RECOVERY",
            status="SUCCEEDED",
            started_by="user-admin",
            started_at=now - timedelta(minutes=6),
            finished_at=now - timedelta(minutes=1),
            canceled_by=None,
            canceled_at=None,
            evidence_summary_json={
                "schemaVersion": 1,
                "summary": "Recovery drill completed and required resilience gates passed.",
                "gates": {"allPassed": True},
            },
            failure_reason=None,
            evidence_storage_key="controlled/derived/recovery/drills/full_recovery/recovery-drill-1/evidence.json",
            evidence_storage_sha256="abc123",
            created_at=now - timedelta(minutes=7),
            updated_at=now - timedelta(minutes=1),
        )
        self._canceled = replace(
            self._drill,
            status="CANCELED",
            canceled_by="user-admin",
            canceled_at=now,
            updated_at=now,
        )

    @staticmethod
    def _require_admin(current_user: SessionPrincipal) -> None:
        if "ADMIN" in set(current_user.platform_roles):
            return
        raise RecoveryAccessDeniedError("Current session cannot access recovery routes.")

    @staticmethod
    def scope_catalog() -> list[dict[str, str]]:
        return [
            {"scope": "QUEUE_REPLAY", "description": "Queue replay and dead-letter recovery posture."},
            {"scope": "STORAGE_INTERRUPT", "description": "Storage interruption fail-closed degradation drill."},
            {"scope": "RESTORE_CLEAN_ENV", "description": "Database/object-store/model restore sequencing drill."},
            {"scope": "FULL_RECOVERY", "description": "Full resilience drill covering replay, restore, and degradation checks."},
        ]

    def get_recovery_status(self, *, current_user: SessionPrincipal) -> dict[str, object]:
        self._require_admin(current_user)
        return {
            "generatedAt": datetime.now(UTC).isoformat(),
            "mode": "STANDBY",
            "degraded": False,
            "summary": "Recovery mode is standby; no active drills are running.",
            "activeDrillCount": 0,
            "queueDepth": 2,
            "deadLetterCount": 0,
            "replayEligibleCount": 0,
            "storageRoot": "/tmp/storage",
            "modelArtifactRoot": "/tmp/models",
            "latestDrill": {
                "id": self._drill.id,
                "scope": self._drill.scope,
                "status": self._drill.status,
                "startedAt": self._drill.started_at.isoformat() if self._drill.started_at else None,
                "finishedAt": self._drill.finished_at.isoformat() if self._drill.finished_at else None,
            },
            "supportedScopes": self.scope_catalog(),
        }

    def list_drills(
        self,
        *,
        current_user: SessionPrincipal,
        cursor: int,
        page_size: int,
    ) -> tuple[list[RecoveryDrillRecord], int | None]:
        self._require_admin(current_user)
        _ = (cursor, page_size)
        return [self._drill], None

    def create_and_run_drill(
        self,
        *,
        current_user: SessionPrincipal,
        scope: str,
    ) -> tuple[RecoveryDrillRecord, dict[str, object] | None]:
        self._require_admin(current_user)
        _ = scope
        return self._drill, dict(self._drill.evidence_summary_json)

    def get_drill(self, *, current_user: SessionPrincipal, drill_id: str) -> RecoveryDrillRecord:
        self._require_admin(current_user)
        if drill_id != self._drill.id:
            raise RecoveryDrillNotFoundError("Recovery drill not found.")
        return self._drill

    def get_drill_status(
        self,
        *,
        current_user: SessionPrincipal,
        drill_id: str,
    ) -> RecoveryDrillRecord:
        return self.get_drill(current_user=current_user, drill_id=drill_id)

    def get_drill_evidence(
        self,
        *,
        current_user: SessionPrincipal,
        drill_id: str,
    ) -> tuple[RecoveryDrillRecord, dict[str, object]]:
        self._require_admin(current_user)
        if drill_id == "recovery-drill-no-evidence":
            raise RecoveryEvidenceUnavailableError("Recovery drill evidence is not available.")
        if drill_id != self._drill.id:
            raise RecoveryDrillNotFoundError("Recovery drill not found.")
        return self._drill, {
            **self._drill.evidence_summary_json,
            "events": [
                {
                    "id": 1,
                    "eventType": "DRILL_FINISHED",
                    "fromStatus": "RUNNING",
                    "toStatus": "SUCCEEDED",
                    "actorUserId": "user-admin",
                    "createdAt": datetime.now(UTC).isoformat(),
                    "details": {"summary": "finished"},
                }
            ],
        }

    def cancel_drill(self, *, current_user: SessionPrincipal, drill_id: str) -> RecoveryDrillRecord:
        self._require_admin(current_user)
        if drill_id != self._drill.id:
            raise RecoveryDrillNotFoundError("Recovery drill not found.")
        return self._canceled


def _principal(*, roles: tuple[Literal["ADMIN", "AUDITOR"], ...]) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-recovery-route",
        auth_source="bearer",
        user_id="user-recovery-route",
        oidc_sub="oidc-user-recovery-route",
        email="recovery-route@test.local",
        display_name="Recovery Route User",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-recovery-route",
    )


@pytest.fixture(autouse=True)
def clear_overrides() -> None:
    yield
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/admin/recovery/status", None),
        ("GET", "/admin/recovery/drills", None),
        ("POST", "/admin/recovery/drills", {"scope": "FULL_RECOVERY"}),
        ("GET", "/admin/recovery/drills/recovery-drill-1", None),
        ("GET", "/admin/recovery/drills/recovery-drill-1/status", None),
        ("GET", "/admin/recovery/drills/recovery-drill-1/evidence", None),
        ("POST", "/admin/recovery/drills/recovery-drill-1/cancel", None),
    ],
)
def test_recovery_routes_require_admin(
    method: str, path: str, payload: dict[str, object] | None
) -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("AUDITOR",))
    app.dependency_overrides[get_recovery_service] = lambda: FakeRecoveryService()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    if method == "POST":
        response = client.post(path, json=payload)
    else:
        response = client.get(path)

    assert response.status_code == 403


def test_recovery_routes_admin_flow_and_audit_events() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_recovery_service] = lambda: FakeRecoveryService()
    app.dependency_overrides[get_audit_service] = lambda: spy

    status_response = client.get("/admin/recovery/status")
    list_response = client.get("/admin/recovery/drills")
    create_response = client.post("/admin/recovery/drills", json={"scope": "FULL_RECOVERY"})
    detail_response = client.get("/admin/recovery/drills/recovery-drill-1")
    status_poll_response = client.get("/admin/recovery/drills/recovery-drill-1/status")
    evidence_response = client.get("/admin/recovery/drills/recovery-drill-1/evidence")
    cancel_response = client.post("/admin/recovery/drills/recovery-drill-1/cancel")

    assert status_response.status_code == 200
    assert list_response.status_code == 200
    assert create_response.status_code == 200
    assert detail_response.status_code == 200
    assert status_poll_response.status_code == 200
    assert evidence_response.status_code == 200
    assert cancel_response.status_code == 200
    assert create_response.json()["drill"]["id"] == "recovery-drill-1"
    assert evidence_response.json()["drillId"] == "recovery-drill-1"
    assert cancel_response.json()["drill"]["status"] == "CANCELED"

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "RECOVERY_STATUS_VIEWED" in event_types
    assert "RECOVERY_DRILLS_VIEWED" in event_types
    assert "RECOVERY_DRILL_VIEWED" in event_types
    assert "RECOVERY_DRILL_STATUS_VIEWED" in event_types
    assert "RECOVERY_DRILL_EVIDENCE_VIEWED" in event_types
    assert "RECOVERY_DRILL_CREATED" in event_types
    assert "RECOVERY_DRILL_STARTED" in event_types
    assert "RECOVERY_DRILL_FINISHED" in event_types
    assert "RECOVERY_DRILL_CANCELED" in event_types


def test_recovery_evidence_route_returns_409_when_unavailable() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_recovery_service] = lambda: FakeRecoveryService()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    response = client.get("/admin/recovery/drills/recovery-drill-no-evidence/evidence")

    assert response.status_code == 409


def test_recovery_drill_route_returns_404_for_unknown_id() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_recovery_service] = lambda: FakeRecoveryService()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    response = client.get("/admin/recovery/drills/recovery-drill-unknown")

    assert response.status_code == 404
