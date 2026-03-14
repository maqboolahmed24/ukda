from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.exports.service import ExportStubService, get_export_stub_service
from app.exports.store import ExportStubStoreUnavailableError
from app.projects.service import ProjectAccessDeniedError, ProjectService, get_project_service
from app.projects.store import ProjectNotFoundError

router = APIRouter(
    prefix="/projects/{project_id}",
    dependencies=[Depends(require_authenticated_user)],
)

_EXPORT_STUB_CODE = "EXPORT_GATEWAY_DISABLED_PHASE0"
_EXPORT_STUB_DETAIL = (
    "Export gateway workflow is intentionally disabled in Phase 0; release paths "
    "remain blocked until Phase 8."
)


class ExportStubDisabledResponse(BaseModel):
    status: Literal["DISABLED"] = "DISABLED"
    code: str = _EXPORT_STUB_CODE
    detail: str = _EXPORT_STUB_DETAIL
    route: str
    method: str
    phase: str = "PHASE_0"
    future_contract: dict[str, object] | None = Field(
        default=None,
        serialization_alias="futureContract",
    )


def _ensure_project_access(
    *,
    project_id: str,
    current_user: SessionPrincipal,
    project_service: ProjectService,
    audit_service: AuditService,
    request_context: AuditRequestContext,
) -> None:
    try:
        project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ProjectAccessDeniedError as error:
        audit_service.record_event_best_effort(
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_MEMBER", "ADMIN_OVERRIDE"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            request_context=request_context,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


def _record_stub_attempt(
    *,
    project_id: str,
    current_user: SessionPrincipal,
    request_context: AuditRequestContext,
    export_stub_service: ExportStubService,
    audit_service: AuditService,
) -> str:
    try:
        stub_event = export_stub_service.record_attempt(
            project_id=project_id,
            route=request_context.route_template,
            method=request_context.method,
            actor_user_id=current_user.user_id,
            request_id=request_context.request_id,
        )
    except ExportStubStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Export stub persistence is unavailable.",
        ) from error

    audit_service.record_event_best_effort(
        event_type="EXPORT_STUB_ROUTE_ACCESSED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_stub_event",
        object_id=stub_event.id,
        metadata={
            "route": request_context.route_template,
            "method": request_context.method,
            "status_code": status.HTTP_501_NOT_IMPLEMENTED,
            "stub_event_id": stub_event.id,
        },
        request_context=request_context,
    )
    return stub_event.id


def _disabled_response(
    *,
    route: str,
    method: str,
    future_contract: dict[str, object] | None = None,
) -> ExportStubDisabledResponse:
    return ExportStubDisabledResponse(
        route=route,
        method=method.upper(),
        future_contract=future_contract,
    )


@router.get(
    "/export-candidates",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def list_export_candidates(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(route=request_context.route_template, method=request_context.method)


@router.get(
    "/export-candidates/{candidate_id}",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def get_export_candidate(
    project_id: str,
    candidate_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = candidate_id
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(route=request_context.route_template, method=request_context.method)


@router.post(
    "/export-requests",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def create_export_request(
    project_id: str,
    payload: dict[str, object] | None = Body(default=None),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = payload
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(route=request_context.route_template, method=request_context.method)


@router.get(
    "/export-requests",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def list_export_requests(
    project_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    requester_id: str | None = Query(default=None, alias="requesterId"),
    candidate_kind: str | None = Query(default=None, alias="candidateKind"),
    cursor: str | None = Query(default=None, alias="cursor"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = (status_filter, requester_id, candidate_kind, cursor)
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(route=request_context.route_template, method=request_context.method)


@router.get(
    "/export-requests/{export_request_id}",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def get_export_request(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = export_request_id
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(route=request_context.route_template, method=request_context.method)


@router.get(
    "/export-requests/{export_request_id}/status",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def get_export_request_status(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = export_request_id
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(route=request_context.route_template, method=request_context.method)


@router.get(
    "/export-requests/{export_request_id}/release-pack",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def get_export_request_release_pack(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = export_request_id
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(route=request_context.route_template, method=request_context.method)


@router.get(
    "/export-requests/{export_request_id}/events",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def get_export_request_events(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = export_request_id
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(route=request_context.route_template, method=request_context.method)


@router.get(
    "/export-requests/{export_request_id}/reviews",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def get_export_request_reviews(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = export_request_id
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(route=request_context.route_template, method=request_context.method)


@router.post(
    "/export-requests/{export_request_id}/start-review",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def start_export_request_review(
    project_id: str,
    export_request_id: str,
    payload: dict[str, object] | None = Body(default=None),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = (export_request_id, payload)
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(route=request_context.route_template, method=request_context.method)


@router.get(
    "/export-requests/{export_request_id}/receipt",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def get_export_request_receipt(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = export_request_id
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(route=request_context.route_template, method=request_context.method)


@router.post(
    "/export-requests/{export_request_id}/resubmit",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def resubmit_export_request(
    project_id: str,
    export_request_id: str,
    payload: dict[str, object] | None = Body(default=None),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = (export_request_id, payload)
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(
        route=request_context.route_template,
        method=request_context.method,
        future_contract={
            "reserved_behavior": "Resubmission creates a new request revision in Phase 8.",
            "status": "NOT_IMPLEMENTED",
        },
    )


@router.post(
    "/export-requests/{export_request_id}/decision",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def decide_export_request(
    project_id: str,
    export_request_id: str,
    payload: dict[str, object] | None = Body(default=None),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = (export_request_id, payload)
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(
        route=request_context.route_template,
        method=request_context.method,
        future_contract={
            "reserved_behavior": "Decision supports APPROVE | REJECT | RETURN in Phase 8.",
            "status": "NOT_IMPLEMENTED",
        },
    )


@router.get(
    "/export-review",
    response_model=ExportStubDisabledResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def list_export_review_queue(
    project_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    aging_bucket: str | None = Query(default=None, alias="agingBucket"),
    reviewer_user_id: str | None = Query(default=None, alias="reviewerUserId"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
    export_stub_service: ExportStubService = Depends(get_export_stub_service),
) -> ExportStubDisabledResponse:
    _ = (status_filter, aging_bucket, reviewer_user_id)
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
        audit_service=audit_service,
        request_context=request_context,
    )
    _record_stub_attempt(
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        export_stub_service=export_stub_service,
        audit_service=audit_service,
    )
    return _disabled_response(route=request_context.route_template, method=request_context.method)

