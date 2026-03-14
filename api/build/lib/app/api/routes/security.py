from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user, require_platform_roles
from app.auth.models import SessionPrincipal
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

