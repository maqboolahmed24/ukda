from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user, require_platform_roles
from app.auth.models import SessionPrincipal
from app.security.findings.models import (
    RiskAcceptanceEventType,
    RiskAcceptanceStatus,
    SecurityFindingSeverity,
    SecurityFindingStatus,
)
from app.security.findings.service import (
    RiskAcceptanceConflictError,
    RiskAcceptanceNotFoundError,
    SecurityAccessDeniedError,
    SecurityFindingNotFoundError,
    SecurityFindingsService,
    SecurityValidationError,
    get_security_findings_service,
)
from app.security.findings.store import SecurityStoreUnavailableError
from app.security.status import SecurityStatusService, get_security_status_service

router = APIRouter(prefix="/admin/security")


class SecurityStatusResponse(BaseModel):
    generated_at: datetime = Field(serialization_alias="generatedAt")
    environment: str
    deny_by_default_egress: bool = Field(serialization_alias="denyByDefaultEgress")
    outbound_allowlist: list[str] = Field(serialization_alias="outboundAllowlist")
    last_successful_egress_deny_test_at: str | None = Field(
        default=None,
        serialization_alias="lastSuccessfulEgressDenyTestAt",
    )
    egress_test_detail: str = Field(serialization_alias="egressTestDetail")
    csp_mode: str = Field(serialization_alias="cspMode")
    last_backup_at: str | None = Field(default=None, serialization_alias="lastBackupAt")
    reduced_motion_preference_state: str = Field(
        serialization_alias="reducedMotionPreferenceState"
    )
    reduced_transparency_preference_state: str = Field(
        serialization_alias="reducedTransparencyPreferenceState"
    )
    export_gateway_state: str = Field(serialization_alias="exportGatewayState")


class SecurityPenTestChecklistItemResponse(BaseModel):
    key: str
    title: str
    status: str
    detail: str


class SecurityFindingResponse(BaseModel):
    id: str
    status: SecurityFindingStatus
    severity: SecurityFindingSeverity
    owner_user_id: str = Field(serialization_alias="ownerUserId")
    source: str
    opened_at: datetime = Field(serialization_alias="openedAt")
    resolved_at: datetime | None = Field(default=None, serialization_alias="resolvedAt")
    resolution_summary: str | None = Field(default=None, serialization_alias="resolutionSummary")


class SecurityFindingsListResponse(BaseModel):
    items: list[SecurityFindingResponse]
    critical_high_gate_passed: bool = Field(serialization_alias="criticalHighGatePassed")
    critical_high_unresolved_finding_ids: list[str] = Field(
        serialization_alias="criticalHighUnresolvedFindingIds"
    )
    pen_test_checklist_complete: bool = Field(serialization_alias="penTestChecklistComplete")
    pen_test_checklist: list[SecurityPenTestChecklistItemResponse] = Field(
        serialization_alias="penTestChecklist"
    )


class RiskAcceptanceResponse(BaseModel):
    id: str
    finding_id: str = Field(serialization_alias="findingId")
    status: RiskAcceptanceStatus
    justification: str
    approved_by: str = Field(serialization_alias="approvedBy")
    accepted_at: datetime = Field(serialization_alias="acceptedAt")
    expires_at: datetime | None = Field(default=None, serialization_alias="expiresAt")
    review_date: datetime | None = Field(default=None, serialization_alias="reviewDate")
    revoked_by: str | None = Field(default=None, serialization_alias="revokedBy")
    revoked_at: datetime | None = Field(default=None, serialization_alias="revokedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class RiskAcceptanceListResponse(BaseModel):
    items: list[RiskAcceptanceResponse]


class RiskAcceptanceEventResponse(BaseModel):
    id: int
    risk_acceptance_id: str = Field(serialization_alias="riskAcceptanceId")
    event_type: RiskAcceptanceEventType = Field(serialization_alias="eventType")
    actor_user_id: str | None = Field(default=None, serialization_alias="actorUserId")
    expires_at: datetime | None = Field(default=None, serialization_alias="expiresAt")
    review_date: datetime | None = Field(default=None, serialization_alias="reviewDate")
    reason: str | None = Field(default=None)
    created_at: datetime = Field(serialization_alias="createdAt")


class RiskAcceptanceEventsResponse(BaseModel):
    items: list[RiskAcceptanceEventResponse]


class CreateRiskAcceptanceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    justification: str
    expires_at: datetime | None = Field(
        default=None, alias="expiresAt", serialization_alias="expiresAt"
    )
    review_date: datetime | None = Field(
        default=None, alias="reviewDate", serialization_alias="reviewDate"
    )


class RenewRiskAcceptanceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    justification: str
    expires_at: datetime | None = Field(
        default=None, alias="expiresAt", serialization_alias="expiresAt"
    )
    review_date: datetime | None = Field(
        default=None, alias="reviewDate", serialization_alias="reviewDate"
    )


class ReviewScheduleRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    review_date: datetime = Field(alias="reviewDate", serialization_alias="reviewDate")
    reason: str | None = None


class RevokeRiskAcceptanceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    reason: str


def _as_finding_response(finding) -> SecurityFindingResponse:  # type: ignore[no-untyped-def]
    return SecurityFindingResponse(
        id=finding.id,
        status=finding.status,
        severity=finding.severity,
        owner_user_id=finding.owner_user_id,
        source=finding.source,
        opened_at=finding.opened_at,
        resolved_at=finding.resolved_at,
        resolution_summary=finding.resolution_summary,
    )


def _as_risk_acceptance_response(item) -> RiskAcceptanceResponse:  # type: ignore[no-untyped-def]
    return RiskAcceptanceResponse(
        id=item.id,
        finding_id=item.finding_id,
        status=item.status,
        justification=item.justification,
        approved_by=item.approved_by,
        accepted_at=item.accepted_at,
        expires_at=item.expires_at,
        review_date=item.review_date,
        revoked_by=item.revoked_by,
        revoked_at=item.revoked_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _as_risk_acceptance_event_response(item) -> RiskAcceptanceEventResponse:  # type: ignore[no-untyped-def]
    return RiskAcceptanceEventResponse(
        id=item.id,
        risk_acceptance_id=item.risk_acceptance_id,
        event_type=item.event_type,
        actor_user_id=item.actor_user_id,
        expires_at=item.expires_at,
        review_date=item.review_date,
        reason=item.reason,
        created_at=item.created_at,
    )


def _raise_security_error(error: Exception) -> None:
    if isinstance(error, SecurityAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, SecurityValidationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    if isinstance(error, SecurityFindingNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, RiskAcceptanceNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, RiskAcceptanceConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if isinstance(error, SecurityStoreUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Security findings persistence is unavailable.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(error),
    ) from error


@router.get(
    "/status",
    response_model=SecurityStatusResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def security_status(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    security_status_service: SecurityStatusService = Depends(get_security_status_service),
) -> SecurityStatusResponse:
    snapshot = security_status_service.snapshot()
    audit_service.record_event_best_effort(
        event_type="ADMIN_SECURITY_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "csp_mode": snapshot.csp_mode,
            "egress_deny_test": "PASS"
            if snapshot.last_successful_egress_deny_test_at
            else "UNSET",
        },
        request_context=request_context,
    )
    return SecurityStatusResponse(
        generated_at=snapshot.generated_at,
        environment=snapshot.environment,
        deny_by_default_egress=snapshot.deny_by_default_egress,
        outbound_allowlist=snapshot.outbound_allowlist,
        last_successful_egress_deny_test_at=snapshot.last_successful_egress_deny_test_at,
        egress_test_detail=snapshot.egress_test_detail,
        csp_mode=snapshot.csp_mode,
        last_backup_at=snapshot.last_backup_at,
        reduced_motion_preference_state=snapshot.reduced_motion_preference_state,
        reduced_transparency_preference_state=snapshot.reduced_transparency_preference_state,
        export_gateway_state=snapshot.export_gateway_state,
    )


@router.get(
    "/findings",
    response_model=SecurityFindingsListResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def list_security_findings(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    security_findings_service: SecurityFindingsService = Depends(get_security_findings_service),
) -> SecurityFindingsListResponse:
    try:
        findings, summary = security_findings_service.list_findings(current_user=current_user)
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_security_error(error)
    audit_service.record_event_best_effort(
        event_type="SECURITY_FINDINGS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(findings),
            "critical_high_gate_passed": bool(summary["criticalHighGatePassed"]),
            "pen_test_checklist_complete": bool(summary["penTestChecklistComplete"]),
        },
        request_context=request_context,
    )
    return SecurityFindingsListResponse(
        items=[_as_finding_response(item) for item in findings],
        critical_high_gate_passed=bool(summary["criticalHighGatePassed"]),
        critical_high_unresolved_finding_ids=[
            str(item) for item in summary["criticalHighUnresolvedFindingIds"]  # type: ignore[index]
        ],
        pen_test_checklist_complete=bool(summary["penTestChecklistComplete"]),
        pen_test_checklist=[
            SecurityPenTestChecklistItemResponse(
                key=str(item["key"]),
                title=str(item["title"]),
                status=str(item["status"]),
                detail=str(item["detail"]),
            )
            for item in summary["penTestChecklist"]  # type: ignore[index]
            if isinstance(item, dict)
        ],
    )


@router.get(
    "/findings/{finding_id}",
    response_model=SecurityFindingResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def get_security_finding(
    finding_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    security_findings_service: SecurityFindingsService = Depends(get_security_findings_service),
) -> SecurityFindingResponse:
    try:
        finding = security_findings_service.get_finding(
            current_user=current_user, finding_id=finding_id
        )
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_security_error(error)
    audit_service.record_event_best_effort(
        event_type="SECURITY_FINDING_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "finding_id": finding.id,
            "status": finding.status,
            "severity": finding.severity,
        },
        request_context=request_context,
    )
    return _as_finding_response(finding)


@router.post(
    "/findings/{finding_id}/risk-acceptance",
    response_model=RiskAcceptanceResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def create_risk_acceptance(
    finding_id: str,
    payload: CreateRiskAcceptanceRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    security_findings_service: SecurityFindingsService = Depends(get_security_findings_service),
) -> RiskAcceptanceResponse:
    try:
        record = security_findings_service.create_risk_acceptance(
            current_user=current_user,
            finding_id=finding_id,
            justification=payload.justification,
            expires_at=payload.expires_at,
            review_date=payload.review_date,
        )
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_security_error(error)
    audit_service.record_event_best_effort(
        event_type="RISK_ACCEPTANCE_CREATED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "finding_id": finding_id,
            "risk_acceptance_id": record.id,
            "status": record.status,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            "review_date": record.review_date.isoformat() if record.review_date else None,
        },
        request_context=request_context,
    )
    return _as_risk_acceptance_response(record)


@router.get(
    "/risk-acceptances",
    response_model=RiskAcceptanceListResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def list_risk_acceptances(
    status_filter: Literal["ACTIVE", "EXPIRED", "REVOKED"] | None = Query(
        default=None, alias="status"
    ),
    finding_id: str | None = Query(default=None, alias="findingId"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    security_findings_service: SecurityFindingsService = Depends(get_security_findings_service),
) -> RiskAcceptanceListResponse:
    try:
        records = security_findings_service.list_risk_acceptances(
            current_user=current_user,
            status=status_filter,  # type: ignore[arg-type]
            finding_id=finding_id,
        )
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_security_error(error)
    audit_service.record_event_best_effort(
        event_type="SECURITY_RISK_ACCEPTANCES_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "status_filter": status_filter or "",
            "finding_id_filter": finding_id or "",
            "returned_count": len(records),
        },
        request_context=request_context,
    )
    return RiskAcceptanceListResponse(
        items=[_as_risk_acceptance_response(item) for item in records]
    )


@router.get(
    "/risk-acceptances/{risk_acceptance_id}",
    response_model=RiskAcceptanceResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def get_risk_acceptance(
    risk_acceptance_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    security_findings_service: SecurityFindingsService = Depends(get_security_findings_service),
) -> RiskAcceptanceResponse:
    try:
        record = security_findings_service.get_risk_acceptance(
            current_user=current_user, risk_acceptance_id=risk_acceptance_id
        )
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_security_error(error)
    audit_service.record_event_best_effort(
        event_type="SECURITY_RISK_ACCEPTANCE_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "risk_acceptance_id": record.id,
            "status": record.status,
            "finding_id": record.finding_id,
        },
        request_context=request_context,
    )
    return _as_risk_acceptance_response(record)


@router.get(
    "/risk-acceptances/{risk_acceptance_id}/events",
    response_model=RiskAcceptanceEventsResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def list_risk_acceptance_events(
    risk_acceptance_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    security_findings_service: SecurityFindingsService = Depends(get_security_findings_service),
) -> RiskAcceptanceEventsResponse:
    try:
        items = security_findings_service.list_risk_acceptance_events(
            current_user=current_user,
            risk_acceptance_id=risk_acceptance_id,
        )
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_security_error(error)
    audit_service.record_event_best_effort(
        event_type="SECURITY_RISK_ACCEPTANCE_EVENTS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "risk_acceptance_id": risk_acceptance_id,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return RiskAcceptanceEventsResponse(
        items=[_as_risk_acceptance_event_response(item) for item in items]
    )


@router.post(
    "/risk-acceptances/{risk_acceptance_id}/renew",
    response_model=RiskAcceptanceResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def renew_risk_acceptance(
    risk_acceptance_id: str,
    payload: RenewRiskAcceptanceRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    security_findings_service: SecurityFindingsService = Depends(get_security_findings_service),
) -> RiskAcceptanceResponse:
    try:
        record = security_findings_service.renew_risk_acceptance(
            current_user=current_user,
            risk_acceptance_id=risk_acceptance_id,
            justification=payload.justification,
            expires_at=payload.expires_at,
            review_date=payload.review_date,
        )
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_security_error(error)
    audit_service.record_event_best_effort(
        event_type="RISK_ACCEPTANCE_RENEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "risk_acceptance_id": record.id,
            "status": record.status,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            "review_date": record.review_date.isoformat() if record.review_date else None,
        },
        request_context=request_context,
    )
    return _as_risk_acceptance_response(record)


@router.post(
    "/risk-acceptances/{risk_acceptance_id}/review-schedule",
    response_model=RiskAcceptanceResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def schedule_risk_acceptance_review(
    risk_acceptance_id: str,
    payload: ReviewScheduleRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    security_findings_service: SecurityFindingsService = Depends(get_security_findings_service),
) -> RiskAcceptanceResponse:
    try:
        record = security_findings_service.schedule_risk_acceptance_review(
            current_user=current_user,
            risk_acceptance_id=risk_acceptance_id,
            review_date=payload.review_date,
            reason=payload.reason,
        )
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_security_error(error)
    audit_service.record_event_best_effort(
        event_type="RISK_ACCEPTANCE_REVIEW_SCHEDULED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "risk_acceptance_id": record.id,
            "status": record.status,
            "review_date": record.review_date.isoformat() if record.review_date else None,
        },
        request_context=request_context,
    )
    return _as_risk_acceptance_response(record)


@router.post(
    "/risk-acceptances/{risk_acceptance_id}/revoke",
    response_model=RiskAcceptanceResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def revoke_risk_acceptance(
    risk_acceptance_id: str,
    payload: RevokeRiskAcceptanceRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    security_findings_service: SecurityFindingsService = Depends(get_security_findings_service),
) -> RiskAcceptanceResponse:
    try:
        record = security_findings_service.revoke_risk_acceptance(
            current_user=current_user,
            risk_acceptance_id=risk_acceptance_id,
            reason=payload.reason,
        )
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_security_error(error)
    audit_service.record_event_best_effort(
        event_type="RISK_ACCEPTANCE_REVOKED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "risk_acceptance_id": record.id,
            "status": record.status,
        },
        request_context=request_context,
    )
    return _as_risk_acceptance_response(record)
