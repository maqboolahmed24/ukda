from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.audit.models import AuditEventRecord
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal, SessionRecord, UserRecord
from app.auth.service import SessionIssue, get_auth_service
from app.main import app
from app.projects.models import ProjectMember, ProjectSummary
from app.projects.service import get_project_service
from fastapi.testclient import TestClient

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []
        self.activity_lookup: tuple[str, int] | None = None

    def record_event(self, **kwargs) -> AuditEventRecord:  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return AuditEventRecord(
            id="event-recorded",
            chain_index=1,
            timestamp=datetime.now(UTC),
            actor_user_id=kwargs.get("actor_user_id"),
            project_id=kwargs.get("project_id"),
            event_type=kwargs.get("event_type"),
            object_type=kwargs.get("object_type"),
            object_id=kwargs.get("object_id"),
            ip=kwargs.get("ip"),
            user_agent=kwargs.get("user_agent"),
            request_id=kwargs.get("request_id") or "req-spy",
            metadata_json=kwargs.get("metadata") or {},
            prev_hash="GENESIS",
            row_hash="hash",
        )

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None

    def list_events(self, **kwargs):  # type: ignore[no-untyped-def]
        return [], None

    def get_event(self, *, event_id: str) -> AuditEventRecord:
        return AuditEventRecord(
            id=event_id,
            chain_index=1,
            timestamp=datetime.now(UTC),
            actor_user_id="user-test",
            project_id="project-test",
            event_type="PROJECT_CREATED",
            object_type="project",
            object_id="project-test",
            ip="127.0.0.1",
            user_agent="test",
            request_id="req-test",
            metadata_json={},
            prev_hash="GENESIS",
            row_hash="hash-1",
        )

    def verify_integrity(self):  # type: ignore[no-untyped-def]
        from app.audit.models import AuditIntegrityStatus

        return AuditIntegrityStatus(
            checked_rows=0,
            chain_head=None,
            is_valid=True,
            first_invalid_chain_index=None,
            first_invalid_event_id=None,
            detail="ok",
        )

    def list_my_activity(self, *, actor_user_id: str, limit: int):  # type: ignore[no-untyped-def]
        self.activity_lookup = (actor_user_id, limit)
        return []


class FakeProjectService:
    def create_project(self, **kwargs) -> ProjectSummary:  # type: ignore[no-untyped-def]
        current_user = kwargs["current_user"]
        return ProjectSummary(
            id="project-1",
            name=kwargs["name"],
            purpose=kwargs["purpose"],
            status="ACTIVE",
            created_by=current_user.user_id,
            created_at=datetime.now(UTC),
            intended_access_tier=kwargs["intended_access_tier"],
            baseline_policy_snapshot_id="baseline-phase0-v1",
            current_user_role="PROJECT_LEAD",
        )

    def add_project_member(self, **kwargs) -> ProjectMember:  # type: ignore[no-untyped-def]
        return ProjectMember(
            project_id=kwargs["project_id"],
            user_id="member-1",
            email=kwargs["member_email"],
            display_name="Member One",
            role=kwargs["role"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def list_my_projects(self, **kwargs):  # type: ignore[no-untyped-def]
        return []

    def require_member_workspace(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("unused")

    def resolve_workspace_context(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("unused")

    def list_project_members(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("unused")

    def get_project_member_for_settings(self, **kwargs):  # type: ignore[no-untyped-def]
        return ProjectMember(
            project_id=kwargs["project_id"],
            user_id=kwargs["member_user_id"],
            email="member-1@local.ukde",
            display_name="Member One",
            role="REVIEWER",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def change_project_member_role(self, **kwargs):  # type: ignore[no-untyped-def]
        return ProjectMember(
            project_id=kwargs["project_id"],
            user_id=kwargs["member_user_id"],
            email="member-1@local.ukde",
            display_name="Member One",
            role=kwargs["role"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def remove_project_member(self, **kwargs):  # type: ignore[no-untyped-def]
        return "REVIEWER"


class FakeAuthService:
    @property
    def settings(self):  # type: ignore[no-untyped-def]
        class Settings:
            oidc_enabled = False
            auth_dev_mode_enabled = True

        return Settings()

    def issue_session_for_dev_seed(self, seed_key: str) -> SessionIssue:
        now = datetime.now(UTC)
        user = UserRecord(
            id="user-login",
            oidc_sub="oidc-user-login",
            email="login@test.local",
            display_name="Login User",
            last_login_at=now,
            platform_roles=(),
        )
        session = SessionRecord(
            id="session-login",
            user_id="user-login",
            auth_method="dev",
            issued_at=now,
            expires_at=now + timedelta(hours=1),
            csrf_token="csrf-login",
        )
        return SessionIssue(user=user, session=session, session_token="token-test")

    def revoke_session(self, *, session_id: str) -> None:
        return None


@pytest.fixture(autouse=True)
def clear_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def _principal(*, roles: tuple[Literal["ADMIN", "AUDITOR"], ...]) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-test",
        auth_source="bearer",
        user_id="user-test",
        oidc_sub="oidc-user-test",
        email="user@test.local",
        display_name="User Test",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-test",
    )


def test_request_id_header_is_present_on_healthz() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) >= 8


def test_request_id_header_reuses_valid_client_request_id() -> None:
    response = client.get("/healthz", headers={"X-Request-ID": "client-req-0001"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "client-req-0001"


def test_admin_audit_list_requires_platform_role() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=())
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    response = client.get("/admin/audit-events")

    assert response.status_code == 403


def test_admin_audit_list_emits_view_event() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_audit_service] = lambda: spy

    response = client.get("/admin/audit-events")

    assert response.status_code == 200
    assert any(event.get("event_type") == "AUDIT_LOG_VIEWED" for event in spy.recorded)


def test_admin_audit_list_allows_auditor_role() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("AUDITOR",))
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    response = client.get("/admin/audit-events")

    assert response.status_code == 200


def test_admin_audit_routes_disallow_mutation_methods() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    patch_response = client.patch("/admin/audit-events/event-1")
    delete_response = client.delete("/admin/audit-events/event-1")

    assert patch_response.status_code == 405
    assert delete_response.status_code == 405


def test_admin_audit_detail_emits_view_event() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_audit_service] = lambda: spy

    response = client.get("/admin/audit-events/event-1")

    assert response.status_code == 200
    assert any(event.get("event_type") == "AUDIT_EVENT_VIEWED" for event in spy.recorded)


def test_my_activity_emits_view_event() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=())
    app.dependency_overrides[get_audit_service] = lambda: spy

    response = client.get("/me/activity")

    assert response.status_code == 200
    assert any(event.get("event_type") == "MY_ACTIVITY_VIEWED" for event in spy.recorded)
    assert spy.activity_lookup == ("user-test", 50)


def test_project_create_emits_project_created_event() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=())
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_project_service] = lambda: FakeProjectService()

    response = client.post(
        "/projects",
        json={
            "name": "Audit Route Test",
            "purpose": "Validate audit event emission from project create route.",
            "intended_access_tier": "CONTROLLED",
        },
    )

    assert response.status_code == 201
    assert any(event.get("event_type") == "PROJECT_CREATED" for event in spy.recorded)
    assert any(
        event.get("event_type") == "PROJECT_BASELINE_POLICY_ATTACHED" for event in spy.recorded
    )


def test_project_member_add_emits_member_added_event() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=())
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_project_service] = lambda: FakeProjectService()

    response = client.post(
        "/projects/project-1/members",
        json={"member_email": "reviewer@local.ukde", "role": "REVIEWER"},
    )

    assert response.status_code == 201
    assert any(event.get("event_type") == "PROJECT_MEMBER_ADDED" for event in spy.recorded)


def test_project_member_role_change_emits_member_role_changed_event() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=())
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_project_service] = lambda: FakeProjectService()

    response = client.patch(
        "/projects/project-1/members/member-1",
        json={"role": "RESEARCHER"},
    )

    assert response.status_code == 200
    assert any(event.get("event_type") == "PROJECT_MEMBER_ROLE_CHANGED" for event in spy.recorded)


def test_project_member_remove_emits_member_removed_event() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=())
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_project_service] = lambda: FakeProjectService()

    response = client.delete("/projects/project-1/members/member-1")

    assert response.status_code == 204
    assert any(event.get("event_type") == "PROJECT_MEMBER_REMOVED" for event in spy.recorded)


def test_dev_login_emits_user_login_event() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()

    response = client.post("/auth/dev/login", json={"seed_key": "project-lead"})

    assert response.status_code == 200
    assert any(event.get("event_type") == "USER_LOGIN" for event in spy.recorded)


def test_logout_emits_user_logout_event() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=())
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()

    response = client.post("/auth/logout", headers={"X-CSRF-Token": "csrf-test"})

    assert response.status_code == 204
    assert any(event.get("event_type") == "USER_LOGOUT" for event in spy.recorded)
