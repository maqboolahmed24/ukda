import re
from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.main import app
from app.telemetry.service import get_telemetry_service
from fastapi.testclient import TestClient

client = TestClient(app)
TRACEPARENT_PATTERN = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


@pytest.fixture(autouse=True)
def clear_overrides_and_telemetry() -> None:
    telemetry_service = get_telemetry_service()
    telemetry_service.reset_for_test()
    yield
    app.dependency_overrides.clear()
    telemetry_service.reset_for_test()


def _principal(*, roles: tuple[Literal["ADMIN", "AUDITOR"], ...]) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-ops",
        auth_source="bearer",
        user_id="user-ops",
        oidc_sub="oidc-user-ops",
        email="ops@test.local",
        display_name="Ops User",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-ops",
    )


def test_traceparent_header_round_trips_trace_id() -> None:
    request_traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-1111111111111111-01"
    response = client.get("/healthz", headers={"traceparent": request_traceparent})

    assert response.status_code == 200
    returned = response.headers.get("traceparent")
    assert returned is not None
    match = TRACEPARENT_PATTERN.match(returned)
    assert match is not None
    assert match.group(1) == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert match.group(2) != "1111111111111111"


def test_operations_overview_requires_admin_role() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("AUDITOR",))
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    response = client.get("/admin/operations/overview")

    assert response.status_code == 403


def test_operations_timeline_allows_auditor_role() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("AUDITOR",))
    app.dependency_overrides[get_audit_service] = lambda: spy

    response = client.get("/admin/operations/timelines")

    assert response.status_code == 200
    assert any(entry.get("event_type") == "OPERATIONS_TIMELINE_VIEWED" for entry in spy.recorded)


def test_operations_routes_emit_audit_events() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_audit_service] = lambda: spy

    overview_response = client.get("/admin/operations/overview")
    slos_response = client.get("/admin/operations/slos")
    alerts_response = client.get("/admin/operations/alerts")

    assert overview_response.status_code == 200
    assert slos_response.status_code == 200
    assert alerts_response.status_code == 200
    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "OPERATIONS_OVERVIEW_VIEWED" in event_types
    assert "OPERATIONS_SLOS_VIEWED" in event_types
    assert "OPERATIONS_ALERTS_VIEWED" in event_types


def test_operations_overview_exposes_request_metrics() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_audit_service] = lambda: spy

    client.get("/healthz")
    response = client.get("/admin/operations/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["requestCount"] >= 1
    assert payload["requestErrorCount"] >= 0
    assert "topRoutes" in payload
