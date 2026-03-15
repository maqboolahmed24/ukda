from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.main import app
from app.security.status import SecurityStatusSnapshot, get_security_status_service
from fastapi.testclient import TestClient

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeSecurityStatusService:
    def snapshot(self) -> SecurityStatusSnapshot:
        return SecurityStatusSnapshot(
            generated_at=datetime.now(UTC),
            environment="test",
            deny_by_default_egress=True,
            outbound_allowlist=["localhost", ".internal"],
            last_successful_egress_deny_test_at=datetime.now(UTC).isoformat(),
            egress_test_detail="Self-test passed.",
            csp_mode="enforce",
            last_backup_at="2026-03-12T02:00:00+00:00",
            reduced_motion_preference_state="UNAVAILABLE_SERVER_SIDE",
            reduced_transparency_preference_state="UNAVAILABLE_SERVER_SIDE",
            export_gateway_state="ENFORCED_GATEWAY_ONLY",
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def _principal(*, roles: tuple[Literal["ADMIN", "AUDITOR"], ...]) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-security",
        auth_source="bearer",
        user_id="user-security",
        oidc_sub="oidc-user-security",
        email="security@test.local",
        display_name="Security User",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-security",
    )


def test_security_status_allows_admin_and_auditor() -> None:
    for roles in [("ADMIN",), ("AUDITOR",)]:
        spy = SpyAuditService()
        app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=roles)
        app.dependency_overrides[get_audit_service] = lambda: spy
        app.dependency_overrides[get_security_status_service] = lambda: FakeSecurityStatusService()

        response = client.get("/admin/security/status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["denyByDefaultEgress"] is True
        assert any(
            event.get("event_type") == "ADMIN_SECURITY_STATUS_VIEWED" for event in spy.recorded
        )


def test_security_status_denies_researcher() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=())
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_security_status_service] = lambda: FakeSecurityStatusService()

    response = client.get("/admin/security/status")

    assert response.status_code == 403
    assert any(event.get("event_type") == "ACCESS_DENIED" for event in spy.recorded)
