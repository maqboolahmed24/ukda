from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.auth.models import SessionPrincipal
from app.core.config import get_settings
from app.security.findings.models import (
    RiskAcceptanceEventRecord,
    RiskAcceptanceRecord,
    SecurityFindingRecord,
)
from app.security.findings.service import (
    SecurityAccessDeniedError,
    SecurityFindingsService,
    SecurityValidationError,
)


class FakeSecurityFindingsStore:
    def __init__(self) -> None:
        self.findings: dict[str, SecurityFindingRecord] = {}
        self.acceptances: dict[str, RiskAcceptanceRecord] = {}
        self.events: dict[str, list[RiskAcceptanceEventRecord]] = {}
        self._acceptance_sequence = 0
        self._event_sequence = 0

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def upsert_finding(
        self,
        *,
        finding_id: str,
        status,
        severity,
        owner_user_id: str,
        source: str,
        opened_at: datetime,
        resolved_at: datetime | None,
        resolution_summary: str | None,
    ) -> SecurityFindingRecord:
        existing = self.findings.get(finding_id)
        created_at = existing.created_at if existing else self._now()
        record = SecurityFindingRecord(
            id=finding_id,
            status=status,
            severity=severity,
            owner_user_id=owner_user_id,
            source=source,
            opened_at=opened_at if existing is None else min(existing.opened_at, opened_at),
            resolved_at=resolved_at,
            resolution_summary=resolution_summary,
            created_at=created_at,
            updated_at=self._now(),
        )
        self.findings[finding_id] = record
        return record

    def list_findings(self, *, statuses=None, severities=None) -> list[SecurityFindingRecord]:
        records = list(self.findings.values())
        if statuses:
            records = [record for record in records if record.status in set(statuses)]
        if severities:
            records = [record for record in records if record.severity in set(severities)]
        return sorted(records, key=lambda item: item.id)

    def get_finding(self, *, finding_id: str) -> SecurityFindingRecord:
        return self.findings[finding_id]

    def _append_event(
        self,
        *,
        risk_acceptance_id: str,
        event_type,
        actor_user_id: str | None,
        expires_at: datetime | None,
        review_date: datetime | None,
        reason: str | None,
    ) -> None:
        self._event_sequence += 1
        self.events.setdefault(risk_acceptance_id, []).append(
            RiskAcceptanceEventRecord(
                id=self._event_sequence,
                risk_acceptance_id=risk_acceptance_id,
                event_type=event_type,
                actor_user_id=actor_user_id,
                expires_at=expires_at,
                review_date=review_date,
                reason=reason,
                created_at=self._now(),
            )
        )

    def create_risk_acceptance(
        self,
        *,
        finding_id: str,
        justification: str,
        approved_by: str,
        expires_at: datetime | None,
        review_date: datetime | None,
    ) -> RiskAcceptanceRecord:
        self._acceptance_sequence += 1
        acceptance_id = f"risk-acceptance-{self._acceptance_sequence}"
        now = self._now()
        record = RiskAcceptanceRecord(
            id=acceptance_id,
            finding_id=finding_id,
            status="ACTIVE",
            justification=justification,
            approved_by=approved_by,
            accepted_at=now,
            expires_at=expires_at,
            review_date=review_date,
            revoked_by=None,
            revoked_at=None,
            created_at=now,
            updated_at=now,
        )
        self.acceptances[acceptance_id] = record
        self._append_event(
            risk_acceptance_id=acceptance_id,
            event_type="ACCEPTANCE_CREATED",
            actor_user_id=approved_by,
            expires_at=expires_at,
            review_date=review_date,
            reason=justification,
        )
        return record

    def list_risk_acceptances(self, *, status=None, finding_id=None) -> list[RiskAcceptanceRecord]:
        rows = list(self.acceptances.values())
        if status is not None:
            rows = [row for row in rows if row.status == status]
        if finding_id is not None:
            rows = [row for row in rows if row.finding_id == finding_id]
        return sorted(rows, key=lambda item: item.id)

    def get_risk_acceptance(self, *, risk_acceptance_id: str) -> RiskAcceptanceRecord:
        return self.acceptances[risk_acceptance_id]

    def list_risk_acceptance_events(
        self, *, risk_acceptance_id: str
    ) -> list[RiskAcceptanceEventRecord]:
        return list(reversed(self.events.get(risk_acceptance_id, [])))

    def renew_risk_acceptance(
        self,
        *,
        risk_acceptance_id: str,
        actor_user_id: str,
        expires_at: datetime | None,
        review_date: datetime | None,
        reason: str,
    ) -> RiskAcceptanceRecord:
        current = self.acceptances[risk_acceptance_id]
        updated = replace(
            current,
            status="ACTIVE",
            justification=reason,
            approved_by=actor_user_id,
            accepted_at=self._now(),
            expires_at=expires_at,
            review_date=review_date,
            revoked_by=None,
            revoked_at=None,
            updated_at=self._now(),
        )
        self.acceptances[risk_acceptance_id] = updated
        self._append_event(
            risk_acceptance_id=risk_acceptance_id,
            event_type="ACCEPTANCE_RENEWED",
            actor_user_id=actor_user_id,
            expires_at=expires_at,
            review_date=review_date,
            reason=reason,
        )
        return updated

    def schedule_risk_acceptance_review(
        self,
        *,
        risk_acceptance_id: str,
        actor_user_id: str,
        review_date: datetime,
        reason: str | None,
    ) -> RiskAcceptanceRecord:
        current = self.acceptances[risk_acceptance_id]
        updated = replace(
            current,
            review_date=review_date,
            updated_at=self._now(),
        )
        self.acceptances[risk_acceptance_id] = updated
        self._append_event(
            risk_acceptance_id=risk_acceptance_id,
            event_type="ACCEPTANCE_REVIEW_SCHEDULED",
            actor_user_id=actor_user_id,
            expires_at=current.expires_at,
            review_date=review_date,
            reason=reason,
        )
        return updated

    def revoke_risk_acceptance(
        self, *, risk_acceptance_id: str, actor_user_id: str, reason: str
    ) -> RiskAcceptanceRecord:
        current = self.acceptances[risk_acceptance_id]
        now = self._now()
        updated = replace(
            current,
            status="REVOKED",
            justification=reason,
            revoked_by=actor_user_id,
            revoked_at=now,
            updated_at=now,
        )
        self.acceptances[risk_acceptance_id] = updated
        self._append_event(
            risk_acceptance_id=risk_acceptance_id,
            event_type="ACCEPTANCE_REVOKED",
            actor_user_id=actor_user_id,
            expires_at=current.expires_at,
            review_date=current.review_date,
            reason=reason,
        )
        return updated

    def expire_due_risk_acceptances(
        self,
        *,
        now: datetime | None = None,
        actor_user_id: str | None = "system-risk-expiry-evaluator",
    ) -> list[RiskAcceptanceRecord]:
        effective_now = now or self._now()
        expired: list[RiskAcceptanceRecord] = []
        for acceptance_id, record in list(self.acceptances.items()):
            if record.status != "ACTIVE":
                continue
            if record.expires_at is None or record.expires_at > effective_now:
                continue
            updated = replace(
                record,
                status="EXPIRED",
                updated_at=effective_now,
            )
            self.acceptances[acceptance_id] = updated
            self._append_event(
                risk_acceptance_id=acceptance_id,
                event_type="ACCEPTANCE_EXPIRED",
                actor_user_id=actor_user_id,
                expires_at=record.expires_at,
                review_date=record.review_date,
                reason="Risk acceptance expired at scheduled expires_at timestamp.",
            )
            expired.append(updated)
        return expired


def _principal(*, roles: tuple[str, ...]) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-security-findings-service",
        auth_source="bearer",
        user_id="user-admin",
        oidc_sub="oidc-user-admin",
        email="admin@test.local",
        display_name="Admin User",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-security-findings-service",
    )


def _build_settings(tmp_path: Path):
    return get_settings().model_copy(
        update={
            "repo_root": tmp_path,
            "auth_session_secret": "test-change-me-session-secret",
        }
    )


def test_security_findings_service_enforces_admin_only_mutations(tmp_path: Path) -> None:
    store = FakeSecurityFindingsStore()
    service = SecurityFindingsService(settings=_build_settings(tmp_path), store=store)
    auditor = _principal(roles=("AUDITOR",))

    with pytest.raises(SecurityAccessDeniedError):
        service.create_risk_acceptance(
            current_user=auditor,
            finding_id="finding-model-boundary-isolation",
            justification="Temporary acceptance while remediation is underway.",
            expires_at=datetime.now(UTC) + timedelta(days=30),
            review_date=None,
        )


def test_security_findings_service_requires_expiry_or_review_date(tmp_path: Path) -> None:
    store = FakeSecurityFindingsStore()
    service = SecurityFindingsService(settings=_build_settings(tmp_path), store=store)
    admin = _principal(roles=("ADMIN",))

    with pytest.raises(SecurityValidationError):
        service.create_risk_acceptance(
            current_user=admin,
            finding_id="finding-model-boundary-isolation",
            justification="Temporary acceptance while remediation is underway.",
            expires_at=None,
            review_date=None,
        )


def test_security_findings_service_appends_expected_lifecycle_events(tmp_path: Path) -> None:
    store = FakeSecurityFindingsStore()
    service = SecurityFindingsService(settings=_build_settings(tmp_path), store=store)
    admin = _principal(roles=("ADMIN",))
    now = datetime.now(UTC)

    created = service.create_risk_acceptance(
        current_user=admin,
        finding_id="finding-secret-rotation-coverage",
        justification="Temporary acceptance while remediation is underway.",
        expires_at=now + timedelta(days=20),
        review_date=now + timedelta(days=7),
    )
    renewed = service.renew_risk_acceptance(
        current_user=admin,
        risk_acceptance_id=created.id,
        justification="Renewed while mitigation rollout completes.",
        expires_at=now + timedelta(days=40),
        review_date=now + timedelta(days=14),
    )
    scheduled = service.schedule_risk_acceptance_review(
        current_user=admin,
        risk_acceptance_id=created.id,
        review_date=now + timedelta(days=21),
        reason="Bi-weekly control review.",
    )
    revoked = service.revoke_risk_acceptance(
        current_user=admin,
        risk_acceptance_id=created.id,
        reason="Mitigation verified and closure approved.",
    )

    assert created.status == "ACTIVE"
    assert renewed.status == "ACTIVE"
    assert scheduled.review_date is not None
    assert revoked.status == "REVOKED"

    events = store.list_risk_acceptance_events(risk_acceptance_id=created.id)
    event_types = [event.event_type for event in reversed(events)]
    assert event_types == [
        "ACCEPTANCE_CREATED",
        "ACCEPTANCE_RENEWED",
        "ACCEPTANCE_REVIEW_SCHEDULED",
        "ACCEPTANCE_REVOKED",
    ]


def test_security_findings_service_evaluates_due_expiries(tmp_path: Path) -> None:
    store = FakeSecurityFindingsStore()
    service = SecurityFindingsService(settings=_build_settings(tmp_path), store=store)
    admin = _principal(roles=("ADMIN",))
    now = datetime.now(UTC)

    created = service.create_risk_acceptance(
        current_user=admin,
        finding_id="finding-secret-rotation-coverage",
        justification="Short-lived acceptance for immediate remediation work.",
        expires_at=now + timedelta(days=3),
        review_date=now + timedelta(days=2),
    )

    store.acceptances[created.id] = replace(
        store.acceptances[created.id],
        expires_at=now - timedelta(minutes=1),
        updated_at=now - timedelta(minutes=1),
    )

    expired = service.evaluate_due_acceptances_system()

    assert len(expired) == 1
    assert expired[0].status == "EXPIRED"
    events = store.list_risk_acceptance_events(risk_acceptance_id=created.id)
    assert events[0].event_type == "ACCEPTANCE_EXPIRED"
