from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.exports.models import ExportStubEventRecord
from app.exports.service import get_export_stub_service
from app.main import app
from app.projects.models import ProjectSummary
from app.projects.service import (
    ProjectAccessDeniedError,
    ProjectService,
    ProjectWorkspaceContext,
    get_project_service,
)
from fastapi.testclient import TestClient

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeExportStubService:
    def __init__(self) -> None:
        self.attempts: list[dict[str, object]] = []

    def record_attempt(self, **kwargs) -> ExportStubEventRecord:  # type: ignore[no-untyped-def]
        self.attempts.append(kwargs)
        return ExportStubEventRecord(
            id="stub-event-1",
            project_id=kwargs.get("project_id"),
            route=kwargs.get("route"),
            method=kwargs.get("method"),
            actor_user_id=kwargs.get("actor_user_id"),
            request_id=kwargs.get("request_id"),
            created_at=datetime.now(UTC),
        )


class FakeProjectService(ProjectService):
    def __init__(self, *, allow_access: bool) -> None:
        self._allow_access = allow_access

    def resolve_workspace_context(
        self, *, current_user: SessionPrincipal, project_id: str
    ) -> ProjectWorkspaceContext:
        if not self._allow_access:
            raise ProjectAccessDeniedError("Membership is required for this project route.")
        summary = ProjectSummary(
            id=project_id,
            name="Export Test",
            purpose="Phase 0 export stub route validation.",
            status="ACTIVE",
            created_by=current_user.user_id,
            created_at=datetime.now(UTC),
            intended_access_tier="CONTROLLED",
            baseline_policy_snapshot_id="baseline-phase0-v1",
            current_user_role="RESEARCHER",
        )
        return ProjectWorkspaceContext(
            summary=summary,
            is_member=True,
            can_access_settings=False,
            can_manage_members=False,
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def _principal(*, roles: tuple[Literal["ADMIN", "AUDITOR"], ...] = ()) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-export",
        auth_source="bearer",
        user_id="user-export",
        oidc_sub="oidc-user-export",
        email="export@test.local",
        display_name="Export User",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-export",
    )


def test_export_stub_route_returns_disabled_and_audits_attempt() -> None:
    spy = SpyAuditService()
    stub_service = FakeExportStubService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_project_service] = lambda: FakeProjectService(
        allow_access=True
    )
    app.dependency_overrides[get_export_stub_service] = lambda: stub_service

    response = client.get("/projects/project-1/export-candidates")

    assert response.status_code == 501
    payload = response.json()
    assert payload["code"] == "EXPORT_GATEWAY_DISABLED_PHASE0"
    assert len(stub_service.attempts) == 1
    assert stub_service.attempts[0]["project_id"] == "project-1"
    assert any(
        event.get("event_type") == "EXPORT_STUB_ROUTE_ACCESSED" for event in spy.recorded
    )


def test_export_resubmit_stub_reserves_future_contract() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_project_service] = lambda: FakeProjectService(
        allow_access=True
    )
    app.dependency_overrides[get_export_stub_service] = lambda: FakeExportStubService()

    response = client.post(
        "/projects/project-1/export-requests/request-1/resubmit",
        json={"note": "retry"},
    )

    assert response.status_code == 501
    payload = response.json()
    assert payload["futureContract"]["status"] == "NOT_IMPLEMENTED"


def test_export_stub_route_denies_non_member_access() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_project_service] = lambda: FakeProjectService(
        allow_access=False
    )
    app.dependency_overrides[get_export_stub_service] = lambda: FakeExportStubService()

    response = client.get("/projects/project-1/export-requests")

    assert response.status_code == 403
    assert any(event.get("event_type") == "ACCESS_DENIED" for event in spy.recorded)

