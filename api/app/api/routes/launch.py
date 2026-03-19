from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user, require_platform_roles
from app.auth.models import SessionPrincipal
from app.operations.launch import (
    IncidentRecord,
    IncidentStatusSnapshot,
    IncidentTimelineEventRecord,
    LaunchOperationsAccessDeniedError,
    LaunchOperationsDataUnavailableError,
    LaunchOperationsNotFoundError,
    LaunchOperationsService,
    RunbookContent,
    RunbookRecord,
    get_launch_operations_service,
)

router = APIRouter(prefix="/admin")


class RunbookResponse(BaseModel):
    id: str
    slug: str
    title: str
    owner_user_id: str = Field(serialization_alias="ownerUserId")
    last_reviewed_at: datetime = Field(serialization_alias="lastReviewedAt")
    status: str
    storage_key: str = Field(serialization_alias="storageKey")


class RunbookListResponse(BaseModel):
    items: list[RunbookResponse]


class RunbookContentResponse(BaseModel):
    runbook: RunbookResponse
    content_markdown: str = Field(serialization_alias="contentMarkdown")
    content_html: str = Field(serialization_alias="contentHtml")


class IncidentResponse(BaseModel):
    id: str
    severity: str
    status: str
    started_at: datetime = Field(serialization_alias="startedAt")
    resolved_at: datetime | None = Field(default=None, serialization_alias="resolvedAt")
    incident_commander_user_id: str = Field(serialization_alias="incidentCommanderUserId")
    summary: str


class IncidentListResponse(BaseModel):
    items: list[IncidentResponse]


class IncidentStatusBucketResponse(BaseModel):
    key: str
    count: int


class IncidentStatusResponse(BaseModel):
    generated_at: datetime = Field(serialization_alias="generatedAt")
    open_incident_count: int = Field(serialization_alias="openIncidentCount")
    unresolved_high_severity_count: int = Field(
        serialization_alias="unresolvedHighSeverityCount"
    )
    by_status: list[IncidentStatusBucketResponse] = Field(serialization_alias="byStatus")
    by_severity: list[IncidentStatusBucketResponse] = Field(
        serialization_alias="bySeverity"
    )
    no_go_triggered: bool = Field(serialization_alias="noGoTriggered")
    no_go_reasons: list[str] = Field(serialization_alias="noGoReasons")
    latest_started_at: datetime | None = Field(default=None, serialization_alias="latestStartedAt")
    go_live_rehearsal_status: str = Field(serialization_alias="goLiveRehearsalStatus")
    incident_response_tabletop_status: str = Field(
        serialization_alias="incidentResponseTabletopStatus"
    )
    model_rollback_rehearsal_status: str = Field(
        serialization_alias="modelRollbackRehearsalStatus"
    )


class IncidentTimelineEventResponse(BaseModel):
    id: str
    incident_id: str = Field(serialization_alias="incidentId")
    event_type: str = Field(serialization_alias="eventType")
    actor_user_id: str = Field(serialization_alias="actorUserId")
    summary: str
    created_at: datetime = Field(serialization_alias="createdAt")


class IncidentTimelineResponse(BaseModel):
    incident_id: str = Field(serialization_alias="incidentId")
    items: list[IncidentTimelineEventResponse]


def _as_runbook_response(item: RunbookRecord) -> RunbookResponse:
    return RunbookResponse(
        id=item.id,
        slug=item.slug,
        title=item.title,
        owner_user_id=item.owner_user_id,
        last_reviewed_at=item.last_reviewed_at,
        status=item.status,
        storage_key=item.storage_key,
    )


def _as_runbook_content_response(item: RunbookContent) -> RunbookContentResponse:
    return RunbookContentResponse(
        runbook=_as_runbook_response(item.runbook),
        content_markdown=item.content_markdown,
        content_html=item.content_html,
    )


def _as_incident_response(item: IncidentRecord) -> IncidentResponse:
    return IncidentResponse(
        id=item.id,
        severity=item.severity,
        status=item.status,
        started_at=item.started_at,
        resolved_at=item.resolved_at,
        incident_commander_user_id=item.incident_commander_user_id,
        summary=item.summary,
    )


def _as_incident_timeline_event_response(
    item: IncidentTimelineEventRecord,
) -> IncidentTimelineEventResponse:
    return IncidentTimelineEventResponse(
        id=item.id,
        incident_id=item.incident_id,
        event_type=item.event_type,
        actor_user_id=item.actor_user_id,
        summary=item.summary,
        created_at=item.created_at,
    )


def _as_incident_status_response(
    item: IncidentStatusSnapshot,
) -> IncidentStatusResponse:
    return IncidentStatusResponse(
        generated_at=item.generated_at,
        open_incident_count=item.open_incident_count,
        unresolved_high_severity_count=item.unresolved_high_severity_count,
        by_status=[
            IncidentStatusBucketResponse(
                key=str(bucket.get("key", "")).strip(),
                count=int(bucket.get("count", 0)),
            )
            for bucket in item.by_status
            if isinstance(bucket, dict)
        ],
        by_severity=[
            IncidentStatusBucketResponse(
                key=str(bucket.get("key", "")).strip(),
                count=int(bucket.get("count", 0)),
            )
            for bucket in item.by_severity
            if isinstance(bucket, dict)
        ],
        no_go_triggered=item.no_go_triggered,
        no_go_reasons=item.no_go_reasons,
        latest_started_at=item.latest_started_at,
        go_live_rehearsal_status=item.go_live_rehearsal_status,
        incident_response_tabletop_status=item.incident_response_tabletop_status,
        model_rollback_rehearsal_status=item.model_rollback_rehearsal_status,
    )


def _raise_launch_operations_error(error: Exception) -> None:
    if isinstance(error, LaunchOperationsAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, LaunchOperationsNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, LaunchOperationsDataUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(error),
    ) from error


@router.get(
    "/runbooks",
    response_model=RunbookListResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def list_runbooks(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    launch_service: LaunchOperationsService = Depends(get_launch_operations_service),
) -> RunbookListResponse:
    try:
        records = launch_service.list_runbooks(current_user=current_user)
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_launch_operations_error(error)
    audit_service.record_event_best_effort(
        event_type="RUNBOOK_LIST_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(records),
        },
        request_context=request_context,
    )
    return RunbookListResponse(items=[_as_runbook_response(item) for item in records])


@router.get(
    "/runbooks/{runbook_id}",
    response_model=RunbookResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def get_runbook(
    runbook_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    launch_service: LaunchOperationsService = Depends(get_launch_operations_service),
) -> RunbookResponse:
    try:
        record = launch_service.get_runbook(current_user=current_user, runbook_id=runbook_id)
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_launch_operations_error(error)
    audit_service.record_event_best_effort(
        event_type="RUNBOOK_DETAIL_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "runbook_id": record.id,
            "slug": record.slug,
            "status": record.status,
            "storage_key": record.storage_key,
            "view": "detail",
        },
        request_context=request_context,
    )
    return _as_runbook_response(record)


@router.get(
    "/runbooks/{runbook_id}/content",
    response_model=RunbookContentResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def get_runbook_content(
    runbook_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    launch_service: LaunchOperationsService = Depends(get_launch_operations_service),
) -> RunbookContentResponse:
    try:
        content = launch_service.get_runbook_content(
            current_user=current_user,
            runbook_id=runbook_id,
        )
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_launch_operations_error(error)
    audit_service.record_event_best_effort(
        event_type="RUNBOOK_DETAIL_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "runbook_id": content.runbook.id,
            "slug": content.runbook.slug,
            "status": content.runbook.status,
            "storage_key": content.runbook.storage_key,
            "view": "content",
        },
        request_context=request_context,
    )
    return _as_runbook_content_response(content)


@router.get(
    "/incidents",
    response_model=IncidentListResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def list_incidents(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    launch_service: LaunchOperationsService = Depends(get_launch_operations_service),
) -> IncidentListResponse:
    try:
        records = launch_service.list_incidents(current_user=current_user)
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_launch_operations_error(error)
    open_incidents = sum(1 for item in records if item.status != "RESOLVED")
    audit_service.record_event_best_effort(
        event_type="INCIDENT_LIST_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(records),
            "open_incident_count": open_incidents,
        },
        request_context=request_context,
    )
    return IncidentListResponse(items=[_as_incident_response(item) for item in records])


@router.get(
    "/incidents/status",
    response_model=IncidentStatusResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def get_incident_status(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    launch_service: LaunchOperationsService = Depends(get_launch_operations_service),
) -> IncidentStatusResponse:
    try:
        snapshot = launch_service.get_incident_status(current_user=current_user)
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_launch_operations_error(error)
    audit_service.record_event_best_effort(
        event_type="INCIDENT_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "open_incident_count": snapshot.open_incident_count,
            "unresolved_high_severity_count": snapshot.unresolved_high_severity_count,
            "no_go_triggered": snapshot.no_go_triggered,
        },
        request_context=request_context,
    )
    return _as_incident_status_response(snapshot)


@router.get(
    "/incidents/{incident_id}",
    response_model=IncidentResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def get_incident(
    incident_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    launch_service: LaunchOperationsService = Depends(get_launch_operations_service),
) -> IncidentResponse:
    try:
        record = launch_service.get_incident(
            current_user=current_user,
            incident_id=incident_id,
        )
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_launch_operations_error(error)
    audit_service.record_event_best_effort(
        event_type="INCIDENT_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "incident_id": record.id,
            "severity": record.severity,
            "status": record.status,
        },
        request_context=request_context,
    )
    return _as_incident_response(record)


@router.get(
    "/incidents/{incident_id}/timeline",
    response_model=IncidentTimelineResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def get_incident_timeline(
    incident_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    launch_service: LaunchOperationsService = Depends(get_launch_operations_service),
) -> IncidentTimelineResponse:
    try:
        records = launch_service.list_incident_timeline(
            current_user=current_user,
            incident_id=incident_id,
        )
    except Exception as error:  # pragma: no cover - mapped through typed handler
        _raise_launch_operations_error(error)
    audit_service.record_event_best_effort(
        event_type="INCIDENT_TIMELINE_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "incident_id": incident_id,
            "returned_count": len(records),
        },
        request_context=request_context,
    )
    return IncidentTimelineResponse(
        incident_id=incident_id,
        items=[_as_incident_timeline_event_response(item) for item in records],
    )
