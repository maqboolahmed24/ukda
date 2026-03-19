from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.main import app
from app.operations.launch import (
    IncidentRecord,
    IncidentStatusSnapshot,
    IncidentTimelineEventRecord,
    LaunchOperationsAccessDeniedError,
    LaunchOperationsNotFoundError,
    RunbookContent,
    RunbookRecord,
    get_launch_operations_service,
)
from fastapi.testclient import TestClient

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeLaunchOperationsService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self._runbook = RunbookRecord(
            id="runbook-release-readiness",
            slug="release-readiness-evidence-and-blocker-policy",
            title="Release readiness evidence and blocker policy",
            owner_user_id="user-release-manager",
            last_reviewed_at=now - timedelta(hours=1),
            status="ACTIVE",
            storage_key="docs/runbooks/release-readiness-evidence-and-blocker-policy.md",
        )
        self._incident = IncidentRecord(
            id="incident-2026-03-18-go-live-rehearsal",
            severity="SEV3",
            status="RESOLVED",
            started_at=now - timedelta(hours=4),
            resolved_at=now - timedelta(hours=3, minutes=30),
            incident_commander_user_id="user-release-manager",
            summary=(
                "Go-live rehearsal across ingest, transcription, privacy review, and "
                "export review completed without blockers."
            ),
        )
        self._timeline = [
            IncidentTimelineEventRecord(
                id="event-1",
                incident_id=self._incident.id,
                event_type="INCIDENT_DECLARED",
                actor_user_id="user-release-manager",
                summary="Incident declared for rehearsal command.",
                created_at=now - timedelta(hours=4),
            ),
            IncidentTimelineEventRecord(
                id="event-2",
                incident_id=self._incident.id,
                event_type="INCIDENT_RESOLVED",
                actor_user_id="user-release-manager",
                summary="Incident resolved after rehearsal completion.",
                created_at=now - timedelta(hours=3, minutes=30),
            ),
        ]

    @staticmethod
    def _require_admin(current_user: SessionPrincipal) -> None:
        if "ADMIN" in set(current_user.platform_roles):
            return
        raise LaunchOperationsAccessDeniedError(
            "Current session cannot access launch-operations routes."
        )

    @staticmethod
    def _require_incident_read(current_user: SessionPrincipal) -> None:
        if {"ADMIN", "AUDITOR"}.intersection(set(current_user.platform_roles)):
            return
        raise LaunchOperationsAccessDeniedError(
            "Current session cannot access launch-operations routes."
        )

    def list_runbooks(self, *, current_user: SessionPrincipal) -> list[RunbookRecord]:
        self._require_admin(current_user)
        return [self._runbook]

    def get_runbook(self, *, current_user: SessionPrincipal, runbook_id: str) -> RunbookRecord:
        self._require_admin(current_user)
        if runbook_id != self._runbook.id:
            raise LaunchOperationsNotFoundError("Runbook not found.")
        return self._runbook

    def get_runbook_content(
        self,
        *,
        current_user: SessionPrincipal,
        runbook_id: str,
    ) -> RunbookContent:
        record = self.get_runbook(current_user=current_user, runbook_id=runbook_id)
        return RunbookContent(
            runbook=record,
            content_markdown="# Heading\n\n- alpha",
            content_html="<h1>Heading</h1>\n<ul>\n<li>alpha</li>\n</ul>",
        )

    def list_incidents(self, *, current_user: SessionPrincipal) -> list[IncidentRecord]:
        self._require_incident_read(current_user)
        return [self._incident]

    def get_incident(self, *, current_user: SessionPrincipal, incident_id: str) -> IncidentRecord:
        self._require_incident_read(current_user)
        if incident_id != self._incident.id:
            raise LaunchOperationsNotFoundError("Incident not found.")
        return self._incident

    def list_incident_timeline(
        self, *, current_user: SessionPrincipal, incident_id: str
    ) -> list[IncidentTimelineEventRecord]:
        self._require_incident_read(current_user)
        if incident_id != self._incident.id:
            raise LaunchOperationsNotFoundError("Incident not found.")
        return list(self._timeline)

    def get_incident_status(self, *, current_user: SessionPrincipal) -> IncidentStatusSnapshot:
        self._require_incident_read(current_user)
        now = datetime.now(UTC)
        return IncidentStatusSnapshot(
            generated_at=now,
            open_incident_count=0,
            unresolved_high_severity_count=0,
            by_status=[{"key": "RESOLVED", "count": 1}],
            by_severity=[{"key": "SEV3", "count": 1}],
            no_go_triggered=False,
            no_go_reasons=[],
            latest_started_at=self._incident.started_at,
            go_live_rehearsal_status="COMPLETED",
            incident_response_tabletop_status="COMPLETED",
            model_rollback_rehearsal_status="COMPLETED",
        )


def _principal(*, roles: tuple[Literal["ADMIN", "AUDITOR"], ...]) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-launch-routes",
        auth_source="bearer",
        user_id="user-launch-routes",
        oidc_sub="oidc-user-launch-routes",
        email="launch-routes@test.local",
        display_name="Launch Routes User",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-launch-routes",
    )


@pytest.fixture(autouse=True)
def clear_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_runbook_routes_require_admin() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("AUDITOR",))
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_launch_operations_service] = (
        lambda: FakeLaunchOperationsService()
    )

    list_response = client.get("/admin/runbooks")
    detail_response = client.get("/admin/runbooks/runbook-release-readiness")
    content_response = client.get("/admin/runbooks/runbook-release-readiness/content")

    assert list_response.status_code == 403
    assert detail_response.status_code == 403
    assert content_response.status_code == 403


@pytest.mark.parametrize("roles", [("ADMIN",), ("AUDITOR",)])
def test_incident_routes_allow_admin_and_auditor(
    roles: tuple[Literal["ADMIN", "AUDITOR"], ...]
) -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=roles)
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_launch_operations_service] = (
        lambda: FakeLaunchOperationsService()
    )

    list_response = client.get("/admin/incidents")
    status_response = client.get("/admin/incidents/status")
    detail_response = client.get("/admin/incidents/incident-2026-03-18-go-live-rehearsal")
    timeline_response = client.get(
        "/admin/incidents/incident-2026-03-18-go-live-rehearsal/timeline"
    )

    assert list_response.status_code == 200
    assert status_response.status_code == 200
    assert detail_response.status_code == 200
    assert timeline_response.status_code == 200


def test_launch_routes_emit_required_audit_events() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_launch_operations_service] = (
        lambda: FakeLaunchOperationsService()
    )

    runbook_list = client.get("/admin/runbooks")
    runbook_detail = client.get("/admin/runbooks/runbook-release-readiness")
    runbook_content = client.get("/admin/runbooks/runbook-release-readiness/content")
    incident_list = client.get("/admin/incidents")
    incident_status = client.get("/admin/incidents/status")
    incident_detail = client.get("/admin/incidents/incident-2026-03-18-go-live-rehearsal")
    incident_timeline = client.get(
        "/admin/incidents/incident-2026-03-18-go-live-rehearsal/timeline"
    )

    assert runbook_list.status_code == 200
    assert runbook_detail.status_code == 200
    assert runbook_content.status_code == 200
    assert incident_list.status_code == 200
    assert incident_status.status_code == 200
    assert incident_detail.status_code == 200
    assert incident_timeline.status_code == 200

    payload = runbook_content.json()
    assert payload["runbook"]["id"] == "runbook-release-readiness"
    assert "contentHtml" in payload

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "RUNBOOK_LIST_VIEWED" in event_types
    assert "RUNBOOK_DETAIL_VIEWED" in event_types
    assert "INCIDENT_LIST_VIEWED" in event_types
    assert "INCIDENT_STATUS_VIEWED" in event_types
    assert "INCIDENT_VIEWED" in event_types
    assert "INCIDENT_TIMELINE_VIEWED" in event_types


def test_launch_routes_map_not_found() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_launch_operations_service] = (
        lambda: FakeLaunchOperationsService()
    )

    runbook_response = client.get("/admin/runbooks/missing-runbook")
    incident_response = client.get("/admin/incidents/missing-incident")

    assert runbook_response.status_code == 404
    assert incident_response.status_code == 404
