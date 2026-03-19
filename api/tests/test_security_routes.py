from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.main import app
from app.security.findings.models import (
    RiskAcceptanceEventRecord,
    RiskAcceptanceRecord,
    SecurityFindingRecord,
)
from app.security.findings.service import (
    RiskAcceptanceConflictError,
    RiskAcceptanceNotFoundError,
    SecurityFindingNotFoundError,
    get_security_findings_service,
)
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


class FakeSecurityFindingsService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.finding = SecurityFindingRecord(
            id="finding-model-boundary-isolation",
            status="OPEN",
            severity="CRITICAL",
            owner_user_id="security-platform-owner",
            source="MODEL_BOUNDARY_REVIEW",
            opened_at=now - timedelta(days=1),
            resolved_at=None,
            resolution_summary=None,
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(hours=1),
        )
        self.acceptance = RiskAcceptanceRecord(
            id="risk-acceptance-1",
            finding_id=self.finding.id,
            status="ACTIVE",
            justification="Temporarily accepted while deployment is remediated.",
            approved_by="user-admin",
            accepted_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=14),
            review_date=now + timedelta(days=7),
            revoked_by=None,
            revoked_at=None,
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(minutes=30),
        )
        self.events = [
            RiskAcceptanceEventRecord(
                id=1,
                risk_acceptance_id=self.acceptance.id,
                event_type="ACCEPTANCE_CREATED",
                actor_user_id="user-admin",
                expires_at=self.acceptance.expires_at,
                review_date=self.acceptance.review_date,
                reason=self.acceptance.justification,
                created_at=self.acceptance.created_at,
            )
        ]

    def list_findings(
        self, *, current_user: SessionPrincipal
    ) -> tuple[list[SecurityFindingRecord], dict[str, object]]:
        _ = current_user
        return (
            [self.finding],
            {
                "criticalHighGatePassed": False,
                "criticalHighUnresolvedFindingIds": [self.finding.id],
                "penTestChecklistComplete": False,
                "penTestChecklist": [
                    {
                        "key": "finding-model-boundary-isolation",
                        "title": "Model-boundary isolation",
                        "status": "BLOCKED",
                        "detail": "Open finding has no active mitigation.",
                    }
                ],
            },
        )

    def get_finding(
        self, *, current_user: SessionPrincipal, finding_id: str
    ) -> SecurityFindingRecord:
        _ = current_user
        if finding_id != self.finding.id:
            raise SecurityFindingNotFoundError("Security finding not found.")
        return self.finding

    def create_risk_acceptance(
        self,
        *,
        current_user: SessionPrincipal,
        finding_id: str,
        justification: str,
        expires_at: datetime | None,
        review_date: datetime | None,
    ) -> RiskAcceptanceRecord:
        _ = (current_user, justification, expires_at, review_date)
        if finding_id == "finding-conflict":
            raise RiskAcceptanceConflictError("ACTIVE risk acceptance already exists.")
        if finding_id != self.finding.id:
            raise SecurityFindingNotFoundError("Security finding not found.")
        return self.acceptance

    def list_risk_acceptances(
        self,
        *,
        current_user: SessionPrincipal,
        status: Literal["ACTIVE", "EXPIRED", "REVOKED"] | None,
        finding_id: str | None,
    ) -> list[RiskAcceptanceRecord]:
        _ = (current_user, status, finding_id)
        return [self.acceptance]

    def get_risk_acceptance(
        self, *, current_user: SessionPrincipal, risk_acceptance_id: str
    ) -> RiskAcceptanceRecord:
        _ = current_user
        if risk_acceptance_id != self.acceptance.id:
            raise RiskAcceptanceNotFoundError("Risk acceptance not found.")
        return self.acceptance

    def list_risk_acceptance_events(
        self, *, current_user: SessionPrincipal, risk_acceptance_id: str
    ) -> list[RiskAcceptanceEventRecord]:
        _ = current_user
        if risk_acceptance_id != self.acceptance.id:
            raise RiskAcceptanceNotFoundError("Risk acceptance not found.")
        return list(self.events)

    def renew_risk_acceptance(
        self,
        *,
        current_user: SessionPrincipal,
        risk_acceptance_id: str,
        justification: str,
        expires_at: datetime | None,
        review_date: datetime | None,
    ) -> RiskAcceptanceRecord:
        _ = (current_user, justification, expires_at, review_date)
        if risk_acceptance_id != self.acceptance.id:
            raise RiskAcceptanceNotFoundError("Risk acceptance not found.")
        return self.acceptance

    def schedule_risk_acceptance_review(
        self,
        *,
        current_user: SessionPrincipal,
        risk_acceptance_id: str,
        review_date: datetime,
        reason: str | None,
    ) -> RiskAcceptanceRecord:
        _ = (current_user, review_date, reason)
        if risk_acceptance_id != self.acceptance.id:
            raise RiskAcceptanceNotFoundError("Risk acceptance not found.")
        return self.acceptance

    def revoke_risk_acceptance(
        self, *, current_user: SessionPrincipal, risk_acceptance_id: str, reason: str
    ) -> RiskAcceptanceRecord:
        _ = (current_user, reason)
        if risk_acceptance_id != self.acceptance.id:
            raise RiskAcceptanceNotFoundError("Risk acceptance not found.")
        return self.acceptance


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
        app.dependency_overrides[get_security_findings_service] = (
            lambda: FakeSecurityFindingsService()
        )

        response = client.get("/admin/security/status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["denyByDefaultEgress"] is True
        assert any(
            event.get("event_type") == "ADMIN_SECURITY_STATUS_VIEWED" for event in spy.recorded
        )


def test_security_routes_read_surface_allows_admin_and_auditor() -> None:
    for roles in [("ADMIN",), ("AUDITOR",)]:
        spy = SpyAuditService()
        app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=roles)
        app.dependency_overrides[get_audit_service] = lambda: spy
        app.dependency_overrides[get_security_status_service] = lambda: FakeSecurityStatusService()
        app.dependency_overrides[get_security_findings_service] = (
            lambda: FakeSecurityFindingsService()
        )

        responses = [
            client.get("/admin/security/findings"),
            client.get("/admin/security/findings/finding-model-boundary-isolation"),
            client.get("/admin/security/risk-acceptances"),
            client.get("/admin/security/risk-acceptances/risk-acceptance-1"),
            client.get("/admin/security/risk-acceptances/risk-acceptance-1/events"),
        ]

        assert all(response.status_code == 200 for response in responses)


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/admin/security/findings/finding-model-boundary-isolation/risk-acceptance",
            {
                "justification": "Temporary acceptance pending remediation.",
                "expiresAt": "2026-05-01T00:00:00+00:00",
            },
        ),
        (
            "/admin/security/risk-acceptances/risk-acceptance-1/renew",
            {
                "justification": "Renewing acceptance while remediation progresses.",
                "expiresAt": "2026-05-15T00:00:00+00:00",
            },
        ),
        (
            "/admin/security/risk-acceptances/risk-acceptance-1/review-schedule",
            {"reviewDate": "2026-04-21T00:00:00+00:00", "reason": "Weekly review."},
        ),
        (
            "/admin/security/risk-acceptances/risk-acceptance-1/revoke",
            {"reason": "Mitigation completed."},
        ),
    ],
)
def test_security_write_routes_require_admin(path: str, payload: dict[str, object]) -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("AUDITOR",))
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_security_status_service] = lambda: FakeSecurityStatusService()
    app.dependency_overrides[get_security_findings_service] = lambda: FakeSecurityFindingsService()

    response = client.post(path, json=payload)

    assert response.status_code == 403


def test_security_routes_admin_flow_and_audit_events() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_security_status_service] = lambda: FakeSecurityStatusService()
    app.dependency_overrides[get_security_findings_service] = lambda: FakeSecurityFindingsService()

    findings_response = client.get("/admin/security/findings")
    finding_response = client.get("/admin/security/findings/finding-model-boundary-isolation")
    create_response = client.post(
        "/admin/security/findings/finding-model-boundary-isolation/risk-acceptance",
        json={
            "justification": "Temporary acceptance pending remediation.",
            "expiresAt": "2026-05-01T00:00:00+00:00",
        },
    )
    list_acceptances_response = client.get("/admin/security/risk-acceptances")
    acceptance_response = client.get("/admin/security/risk-acceptances/risk-acceptance-1")
    events_response = client.get("/admin/security/risk-acceptances/risk-acceptance-1/events")
    renew_response = client.post(
        "/admin/security/risk-acceptances/risk-acceptance-1/renew",
        json={
            "justification": "Renewing acceptance while remediation progresses.",
            "expiresAt": "2026-05-15T00:00:00+00:00",
        },
    )
    review_schedule_response = client.post(
        "/admin/security/risk-acceptances/risk-acceptance-1/review-schedule",
        json={"reviewDate": "2026-04-21T00:00:00+00:00", "reason": "Weekly review."},
    )
    revoke_response = client.post(
        "/admin/security/risk-acceptances/risk-acceptance-1/revoke",
        json={"reason": "Mitigation completed."},
    )

    assert findings_response.status_code == 200
    assert finding_response.status_code == 200
    assert create_response.status_code == 200
    assert list_acceptances_response.status_code == 200
    assert acceptance_response.status_code == 200
    assert events_response.status_code == 200
    assert renew_response.status_code == 200
    assert review_schedule_response.status_code == 200
    assert revoke_response.status_code == 200

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "SECURITY_FINDINGS_VIEWED" in event_types
    assert "SECURITY_FINDING_VIEWED" in event_types
    assert "RISK_ACCEPTANCE_CREATED" in event_types
    assert "SECURITY_RISK_ACCEPTANCES_VIEWED" in event_types
    assert "SECURITY_RISK_ACCEPTANCE_VIEWED" in event_types
    assert "SECURITY_RISK_ACCEPTANCE_EVENTS_VIEWED" in event_types
    assert "RISK_ACCEPTANCE_RENEWED" in event_types
    assert "RISK_ACCEPTANCE_REVIEW_SCHEDULED" in event_types
    assert "RISK_ACCEPTANCE_REVOKED" in event_types


def test_security_routes_map_404_and_409_errors() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_security_status_service] = lambda: FakeSecurityStatusService()
    app.dependency_overrides[get_security_findings_service] = lambda: FakeSecurityFindingsService()

    finding_not_found_response = client.get("/admin/security/findings/finding-unknown")
    acceptance_not_found_response = client.get("/admin/security/risk-acceptances/risk-unknown")
    conflict_response = client.post(
        "/admin/security/findings/finding-conflict/risk-acceptance",
        json={
            "justification": "Temporary acceptance pending remediation.",
            "expiresAt": "2026-05-01T00:00:00+00:00",
        },
    )

    assert finding_not_found_response.status_code == 404
    assert acceptance_not_found_response.status_code == 404
    assert conflict_response.status_code == 409


def test_security_status_denies_researcher() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=())
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_security_status_service] = lambda: FakeSecurityStatusService()
    app.dependency_overrides[get_security_findings_service] = lambda: FakeSecurityFindingsService()

    response = client.get("/admin/security/status")

    assert response.status_code == 403
    assert any(event.get("event_type") == "ACCESS_DENIED" for event in spy.recorded)
