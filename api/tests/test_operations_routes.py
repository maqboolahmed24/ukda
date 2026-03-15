import re
from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.exports.models import ExportOperationsStatusRecord
from app.exports.service import get_export_service
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


class FakeExportService:
    def get_export_operations_status(  # type: ignore[no-untyped-def]
        self, *, current_user: SessionPrincipal
    ) -> ExportOperationsStatusRecord:
        _ = current_user
        return ExportOperationsStatusRecord(
            generated_at=datetime.now(UTC),
            open_request_count=5,
            aging_unstarted_count=1,
            aging_no_sla_count=0,
            aging_on_track_count=2,
            aging_due_soon_count=1,
            aging_overdue_count=1,
            stale_open_count=1,
            reminder_due_count=2,
            reminders_sent_last_24h=3,
            reminders_sent_total=9,
            escalation_due_count=1,
            escalated_open_count=2,
            escalations_total=4,
            retention_pending_count=6,
            retention_pending_window_days=14,
            terminal_approved_count=8,
            terminal_exported_count=12,
            terminal_rejected_count=3,
            terminal_returned_count=5,
            policy_sla_hours=72,
            policy_reminder_after_hours=24,
            policy_reminder_cooldown_hours=12,
            policy_escalation_after_sla_hours=24,
            policy_escalation_cooldown_hours=24,
            policy_stale_open_after_days=30,
            policy_retention_stale_open_days=60,
            policy_retention_terminal_approved_days=180,
            policy_retention_terminal_other_days=90,
        )


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


def test_operations_export_status_allows_auditor_role() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("AUDITOR",))
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_export_service] = lambda: FakeExportService()

    response = client.get("/admin/operations/export-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["openRequestCount"] == 5
    assert payload["aging"]["overdue"] == 1
    assert payload["retention"]["pendingCount"] == 6
    assert any(
        entry.get("event_type") == "OPERATIONS_EXPORT_STATUS_VIEWED"
        for entry in spy.recorded
    )


def test_operations_export_status_requires_admin_or_auditor() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: SessionPrincipal(
        session_id="session-non-admin",
        auth_source="bearer",
        user_id="user-non-admin",
        oidc_sub="oidc-user-non-admin",
        email="non-admin@test.local",
        display_name="Non Admin",
        platform_roles=(),
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-non-admin",
    )
    app.dependency_overrides[get_export_service] = lambda: FakeExportService()

    response = client.get("/admin/operations/export-status")

    assert response.status_code == 403


def test_operations_routes_emit_audit_events() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_export_service] = lambda: FakeExportService()

    overview_response = client.get("/admin/operations/overview")
    export_status_response = client.get("/admin/operations/export-status")
    slos_response = client.get("/admin/operations/slos")
    alerts_response = client.get("/admin/operations/alerts")

    assert overview_response.status_code == 200
    assert export_status_response.status_code == 200
    assert slos_response.status_code == 200
    assert alerts_response.status_code == 200
    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "OPERATIONS_OVERVIEW_VIEWED" in event_types
    assert "OPERATIONS_EXPORT_STATUS_VIEWED" in event_types
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
