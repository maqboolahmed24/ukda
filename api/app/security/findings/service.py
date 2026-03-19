from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.core.model_stack import validate_model_stack
from app.security.findings.models import (
    RiskAcceptanceEventRecord,
    RiskAcceptanceRecord,
    RiskAcceptanceStatus,
    SecurityFindingRecord,
    SecurityFindingStatus,
)
from app.security.findings.store import (
    RiskAcceptanceConflictError,
    RiskAcceptanceNotFoundError,
    SecurityFindingNotFoundError,
    SecurityFindingsStore,
)

_READ_ROLES: set[str] = {"ADMIN", "AUDITOR"}
_WRITE_ROLES: set[str] = {"ADMIN"}
_SYSTEM_FINDING_OWNER = "security-platform-owner"


@dataclass(frozen=True)
class SecurityPenTestChecklistItem:
    key: str
    title: str
    status: str
    detail: str


class SecurityAccessDeniedError(RuntimeError):
    """Current session cannot access security findings routes."""


class SecurityValidationError(RuntimeError):
    """Security findings payload is invalid."""


class SecurityFindingsService:
    def __init__(self, *, settings: Settings, store: SecurityFindingsStore | None = None) -> None:
        self._settings = settings
        self._store = store or SecurityFindingsStore(settings)

    @staticmethod
    def _require_any_role(current_user: SessionPrincipal, required: set[str]) -> None:
        if set(current_user.platform_roles).intersection(required):
            return
        raise SecurityAccessDeniedError("Current session cannot access security findings routes.")

    @staticmethod
    def _normalize_text(value: str, *, field: str, minimum: int = 1, maximum: int = 2000) -> str:
        candidate = value.strip()
        if len(candidate) < minimum or len(candidate) > maximum:
            raise SecurityValidationError(
                f"{field} must be between {minimum} and {maximum} characters."
            )
        return candidate

    @staticmethod
    def _require_review_or_expiry(
        *,
        expires_at: datetime | None,
        review_date: datetime | None,
    ) -> None:
        if expires_at is None and review_date is None:
            raise SecurityValidationError(
                "Risk acceptance requires an expiresAt or reviewDate."
            )

    @staticmethod
    def _ensure_not_past(value: datetime | None, *, field: str) -> None:
        if value is None:
            return
        now = datetime.now(UTC)
        if value <= now:
            raise SecurityValidationError(f"{field} must be in the future.")

    def _repo_file_exists(self, relative_path: str) -> bool:
        path = (self._settings.repo_root / relative_path).resolve()
        return path.exists() and path.is_file()

    def _read_repo_file(self, relative_path: str) -> str:
        path = (self._settings.repo_root / relative_path).resolve()
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _sync_system_findings(self) -> None:
        now = datetime.now(UTC)
        model_stack_result = validate_model_stack(self._settings)
        model_status: SecurityFindingStatus = (
            "RESOLVED" if model_stack_result.status == "ok" else "OPEN"
        )
        model_resolution = (
            model_stack_result.detail
            if model_status == "RESOLVED"
            else f"Model-boundary validation failed: {model_stack_result.detail}"
        )
        self._store.upsert_finding(
            finding_id="finding-model-boundary-isolation",
            status=model_status,
            severity="CRITICAL",
            owner_user_id=_SYSTEM_FINDING_OWNER,
            source="MODEL_BOUNDARY_REVIEW",
            opened_at=now,
            resolved_at=now if model_status == "RESOLVED" else None,
            resolution_summary=model_resolution,
        )

        insecure_secrets = []
        default_like = (
            self._settings.auth_session_secret,
            self._settings.pseudonym_registry_master_secret,
            self._settings.internal_export_gateway_token,
            self._settings.provenance_signing_secret,
        )
        for value in default_like:
            if "change-me" in value.lower():
                insecure_secrets.append(value)
        secret_status: SecurityFindingStatus = "RESOLVED" if not insecure_secrets else "OPEN"
        secret_summary = (
            "Secret-rotation coverage check passed; environment secrets are non-default."
            if secret_status == "RESOLVED"
            else (
                "Secret-rotation coverage check failed; one or more runtime secrets still use "
                "development placeholder material."
            )
        )
        self._store.upsert_finding(
            finding_id="finding-secret-rotation-coverage",
            status=secret_status,
            severity="HIGH",
            owner_user_id=_SYSTEM_FINDING_OWNER,
            source="SECRET_ROTATION_REVIEW",
            opened_at=now,
            resolved_at=now if secret_status == "RESOLVED" else None,
            resolution_summary=secret_summary,
        )

        network_templates = [
            "infra/helm/ukde/templates/networkpolicy-default-deny-egress.yaml",
            "infra/helm/ukde/templates/networkpolicy-allow-internal-egress.yaml",
        ]
        missing_network_templates = [
            template for template in network_templates if not self._repo_file_exists(template)
        ]
        network_status: SecurityFindingStatus = (
            "RESOLVED" if not missing_network_templates else "OPEN"
        )
        network_summary = (
            "Network-policy review artifacts are present for deny-by-default and "
            "internal allowlist controls."
            if network_status == "RESOLVED"
            else (
                "Network-policy review failed; missing templates: "
                + ", ".join(missing_network_templates)
            )
        )
        self._store.upsert_finding(
            finding_id="finding-network-policy-review",
            status=network_status,
            severity="HIGH",
            owner_user_id=_SYSTEM_FINDING_OWNER,
            source="NETWORK_POLICY_REVIEW",
            opened_at=now,
            resolved_at=now if network_status == "RESOLVED" else None,
            resolution_summary=network_summary,
        )

        service_account_templates = [
            "infra/helm/ukde/templates/serviceaccount-api.yaml",
            "infra/helm/ukde/templates/serviceaccount-workers.yaml",
        ]
        missing_service_account_templates = [
            template
            for template in service_account_templates
            if not self._repo_file_exists(template)
        ]
        api_deployment = self._read_repo_file("infra/helm/ukde/templates/deployment-api.yaml")
        worker_deployment = self._read_repo_file(
            "infra/helm/ukde/templates/deployment-workers.yaml"
        )
        service_account_reference_present = (
            "serviceAccountName:" in api_deployment
            and "serviceAccountName:" in worker_deployment
            and "automountServiceAccountToken: false" in api_deployment
            and "automountServiceAccountToken: false" in worker_deployment
        )
        service_account_status: SecurityFindingStatus = (
            "RESOLVED"
            if not missing_service_account_templates and service_account_reference_present
            else "OPEN"
        )
        if service_account_status == "RESOLVED":
            service_account_summary = (
                "Least-privilege service-account templates and deployment bindings are present."
            )
        else:
            missing = ", ".join(missing_service_account_templates) or "deployment bindings"
            service_account_summary = (
                "Least-privilege service-account boundary check failed; missing: "
                f"{missing}."
            )
        self._store.upsert_finding(
            finding_id="finding-service-account-boundary",
            status=service_account_status,
            severity="HIGH",
            owner_user_id=_SYSTEM_FINDING_OWNER,
            source="SERVICE_ACCOUNT_BOUNDARY_REVIEW",
            opened_at=now,
            resolved_at=now if service_account_status == "RESOLVED" else None,
            resolution_summary=service_account_summary,
        )

    def _active_risk_acceptance_index(self) -> dict[str, RiskAcceptanceRecord]:
        rows = self._store.list_risk_acceptances(status="ACTIVE")
        index: dict[str, RiskAcceptanceRecord] = {}
        for record in rows:
            index[record.finding_id] = record
        return index

    def _critical_and_high_gate(
        self, findings: list[SecurityFindingRecord]
    ) -> tuple[bool, list[str]]:
        active_by_finding = self._active_risk_acceptance_index()
        unresolved: list[str] = []
        for finding in findings:
            if finding.severity not in {"CRITICAL", "HIGH"}:
                continue
            if finding.status == "RESOLVED":
                continue
            if finding.id in active_by_finding:
                continue
            unresolved.append(finding.id)
        return (len(unresolved) == 0, unresolved)

    def _build_pen_test_checklist(
        self, findings: list[SecurityFindingRecord]
    ) -> tuple[list[SecurityPenTestChecklistItem], bool]:
        by_id = {finding.id: finding for finding in findings}
        active_by_finding = self._active_risk_acceptance_index()

        def _item_for_finding(finding_id: str, title: str) -> SecurityPenTestChecklistItem:
            finding = by_id.get(finding_id)
            if finding is None:
                return SecurityPenTestChecklistItem(
                    key=finding_id,
                    title=title,
                    status="BLOCKED",
                    detail="Finding is missing from the findings store.",
                )
            if finding.status == "RESOLVED":
                return SecurityPenTestChecklistItem(
                    key=finding_id,
                    title=title,
                    status="PASS",
                    detail=finding.resolution_summary or "Resolved.",
                )
            acceptance = active_by_finding.get(finding.id)
            if acceptance is not None:
                expires_at_display = (
                    acceptance.expires_at.isoformat() if acceptance.expires_at else "n/a"
                )
                return SecurityPenTestChecklistItem(
                    key=finding_id,
                    title=title,
                    status="RISK_ACCEPTED",
                    detail=(
                        "Open finding has ACTIVE risk acceptance "
                        f"{acceptance.id} (expires {expires_at_display})."
                    ),
                )
            return SecurityPenTestChecklistItem(
                key=finding_id,
                title=title,
                status="BLOCKED",
                detail="Open finding has no ACTIVE risk acceptance.",
            )

        checklist = [
            _item_for_finding(
                "finding-model-boundary-isolation",
                "Model-boundary isolation and no-public-runtime-fetch checks",
            ),
            _item_for_finding(
                "finding-secret-rotation-coverage",
                "Secret rotation coverage and non-default runtime secrets",
            ),
            _item_for_finding(
                "finding-network-policy-review",
                "Network-policy review for deny-by-default egress controls",
            ),
            _item_for_finding(
                "finding-service-account-boundary",
                "Least-privilege service-account boundary encoding",
            ),
        ]
        complete = all(item.status in {"PASS", "RISK_ACCEPTED"} for item in checklist)
        return checklist, complete

    def list_findings(
        self, *, current_user: SessionPrincipal
    ) -> tuple[list[SecurityFindingRecord], dict[str, object]]:
        self._require_any_role(current_user, _READ_ROLES)
        self._sync_system_findings()
        findings = self._store.list_findings()
        gate_passed, unresolved_ids = self._critical_and_high_gate(findings)
        checklist, checklist_complete = self._build_pen_test_checklist(findings)
        summary = {
            "criticalHighGatePassed": gate_passed,
            "criticalHighUnresolvedFindingIds": unresolved_ids,
            "penTestChecklistComplete": checklist_complete and gate_passed,
            "penTestChecklist": [
                {
                    "key": item.key,
                    "title": item.title,
                    "status": item.status,
                    "detail": item.detail,
                }
                for item in checklist
            ],
        }
        return findings, summary

    def get_finding(
        self, *, current_user: SessionPrincipal, finding_id: str
    ) -> SecurityFindingRecord:
        self._require_any_role(current_user, _READ_ROLES)
        self._sync_system_findings()
        return self._store.get_finding(finding_id=finding_id)

    def create_risk_acceptance(
        self,
        *,
        current_user: SessionPrincipal,
        finding_id: str,
        justification: str,
        expires_at: datetime | None,
        review_date: datetime | None,
    ) -> RiskAcceptanceRecord:
        self._require_any_role(current_user, _WRITE_ROLES)
        self._sync_system_findings()
        normalized_justification = self._normalize_text(
            justification, field="justification", minimum=8
        )
        self._require_review_or_expiry(expires_at=expires_at, review_date=review_date)
        self._ensure_not_past(expires_at, field="expiresAt")
        self._ensure_not_past(review_date, field="reviewDate")
        finding = self._store.get_finding(finding_id=finding_id)
        if finding.status == "RESOLVED":
            raise SecurityValidationError(
                "Risk acceptance cannot be created for a RESOLVED finding."
            )
        return self._store.create_risk_acceptance(
            finding_id=finding_id,
            justification=normalized_justification,
            approved_by=current_user.user_id,
            expires_at=expires_at,
            review_date=review_date,
        )

    def list_risk_acceptances(
        self,
        *,
        current_user: SessionPrincipal,
        status: RiskAcceptanceStatus | None,
        finding_id: str | None,
    ) -> list[RiskAcceptanceRecord]:
        self._require_any_role(current_user, _READ_ROLES)
        self.evaluate_due_acceptances_system()
        if finding_id is not None:
            finding_candidate = finding_id.strip()
            if not finding_candidate:
                raise SecurityValidationError("findingId filter cannot be empty.")
            finding_id = finding_candidate
        return self._store.list_risk_acceptances(status=status, finding_id=finding_id)

    def get_risk_acceptance(
        self, *, current_user: SessionPrincipal, risk_acceptance_id: str
    ) -> RiskAcceptanceRecord:
        self._require_any_role(current_user, _READ_ROLES)
        self.evaluate_due_acceptances_system()
        return self._store.get_risk_acceptance(risk_acceptance_id=risk_acceptance_id)

    def list_risk_acceptance_events(
        self, *, current_user: SessionPrincipal, risk_acceptance_id: str
    ) -> list[RiskAcceptanceEventRecord]:
        self._require_any_role(current_user, _READ_ROLES)
        self.evaluate_due_acceptances_system()
        self._store.get_risk_acceptance(risk_acceptance_id=risk_acceptance_id)
        return self._store.list_risk_acceptance_events(risk_acceptance_id=risk_acceptance_id)

    def renew_risk_acceptance(
        self,
        *,
        current_user: SessionPrincipal,
        risk_acceptance_id: str,
        justification: str,
        expires_at: datetime | None,
        review_date: datetime | None,
    ) -> RiskAcceptanceRecord:
        self._require_any_role(current_user, _WRITE_ROLES)
        normalized_justification = self._normalize_text(
            justification, field="justification", minimum=8
        )
        self._require_review_or_expiry(expires_at=expires_at, review_date=review_date)
        self._ensure_not_past(expires_at, field="expiresAt")
        self._ensure_not_past(review_date, field="reviewDate")
        return self._store.renew_risk_acceptance(
            risk_acceptance_id=risk_acceptance_id,
            actor_user_id=current_user.user_id,
            expires_at=expires_at,
            review_date=review_date,
            reason=normalized_justification,
        )

    def schedule_risk_acceptance_review(
        self,
        *,
        current_user: SessionPrincipal,
        risk_acceptance_id: str,
        review_date: datetime,
        reason: str | None,
    ) -> RiskAcceptanceRecord:
        self._require_any_role(current_user, _WRITE_ROLES)
        self._ensure_not_past(review_date, field="reviewDate")
        normalized_reason = None
        if reason is not None and reason.strip():
            normalized_reason = self._normalize_text(reason, field="reason", minimum=3, maximum=800)
        return self._store.schedule_risk_acceptance_review(
            risk_acceptance_id=risk_acceptance_id,
            actor_user_id=current_user.user_id,
            review_date=review_date,
            reason=normalized_reason,
        )

    def revoke_risk_acceptance(
        self,
        *,
        current_user: SessionPrincipal,
        risk_acceptance_id: str,
        reason: str,
    ) -> RiskAcceptanceRecord:
        self._require_any_role(current_user, _WRITE_ROLES)
        normalized_reason = self._normalize_text(reason, field="reason", minimum=3, maximum=800)
        return self._store.revoke_risk_acceptance(
            risk_acceptance_id=risk_acceptance_id,
            actor_user_id=current_user.user_id,
            reason=normalized_reason,
        )

    def evaluate_due_acceptances_system(self) -> list[RiskAcceptanceRecord]:
        return self._store.expire_due_risk_acceptances()


@lru_cache
def get_security_findings_service() -> SecurityFindingsService:
    settings = get_settings()
    return SecurityFindingsService(settings=settings)


__all__ = [
    "RiskAcceptanceConflictError",
    "RiskAcceptanceNotFoundError",
    "SecurityAccessDeniedError",
    "SecurityFindingNotFoundError",
    "SecurityFindingsService",
    "SecurityValidationError",
    "get_security_findings_service",
]
