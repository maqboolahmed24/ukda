from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditEventRecord, AuditEventType, AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.audit.store import AuditEventNotFoundError, AuditStoreUnavailableError
from app.auth.dependencies import require_authenticated_user, require_platform_roles
from app.auth.models import SessionPrincipal

admin_router = APIRouter(prefix="/admin")
me_router = APIRouter(prefix="/me")


class AuditEventResponse(BaseModel):
    id: str
    chain_index: int = Field(serialization_alias="chainIndex")
    timestamp: datetime
    actor_user_id: str | None = Field(default=None, serialization_alias="actorUserId")
    project_id: str | None = Field(default=None, serialization_alias="projectId")
    event_type: AuditEventType = Field(serialization_alias="eventType")
    object_type: str | None = Field(default=None, serialization_alias="objectType")
    object_id: str | None = Field(default=None, serialization_alias="objectId")
    ip: str | None = None
    user_agent: str | None = Field(default=None, serialization_alias="userAgent")
    request_id: str = Field(serialization_alias="requestId")
    metadata_json: dict[str, object] = Field(serialization_alias="metadataJson")
    prev_hash: str = Field(serialization_alias="prevHash")
    row_hash: str = Field(serialization_alias="rowHash")


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class AuditIntegrityResponse(BaseModel):
    checked_rows: int = Field(serialization_alias="checkedRows")
    chain_head: str | None = Field(default=None, serialization_alias="chainHead")
    is_valid: bool = Field(serialization_alias="isValid")
    first_invalid_chain_index: int | None = Field(
        default=None,
        serialization_alias="firstInvalidChainIndex",
    )
    first_invalid_event_id: str | None = Field(
        default=None,
        serialization_alias="firstInvalidEventId",
    )
    detail: str


def _as_audit_event_response(event: AuditEventRecord) -> AuditEventResponse:
    return AuditEventResponse(
        id=event.id,
        chain_index=event.chain_index,
        timestamp=event.timestamp,
        actor_user_id=event.actor_user_id,
        project_id=event.project_id,
        event_type=event.event_type,
        object_type=event.object_type,
        object_id=event.object_id,
        ip=event.ip,
        user_agent=event.user_agent,
        request_id=event.request_id,
        metadata_json=event.metadata_json,
        prev_hash=event.prev_hash,
        row_hash=event.row_hash,
    )


@admin_router.get(
    "/audit-events",
    response_model=AuditEventListResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def list_audit_events(
    project_id: str | None = Query(default=None, alias="projectId"),
    actor_user_id: str | None = Query(default=None, alias="actorUserId"),
    event_type: AuditEventType | None = Query(default=None, alias="eventType"),
    from_timestamp: datetime | None = Query(default=None, alias="from"),
    to_timestamp: datetime | None = Query(default=None, alias="to"),
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditEventListResponse:
    try:
        events, next_cursor = audit_service.list_events(
            project_id=project_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            cursor=cursor,
            page_size=page_size,
        )
    except AuditStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit store is unavailable.",
        ) from error

    audit_service.record_event_best_effort(
        event_type="AUDIT_LOG_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "project_filter": project_id,
            "actor_filter": actor_user_id,
            "event_type_filter": event_type,
            "from": from_timestamp.isoformat() if from_timestamp else None,
            "to": to_timestamp.isoformat() if to_timestamp else None,
            "cursor": cursor,
            "returned_count": len(events),
        },
        request_context=request_context,
    )

    return AuditEventListResponse(
        items=[_as_audit_event_response(event) for event in events],
        next_cursor=next_cursor,
    )


@admin_router.get(
    "/audit-events/{event_id}",
    response_model=AuditEventResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def get_audit_event(
    event_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditEventResponse:
    try:
        event = audit_service.get_event(event_id=event_id)
    except AuditStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit store is unavailable.",
        ) from error
    except AuditEventNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit event not found.",
        ) from error

    audit_service.record_event_best_effort(
        event_type="AUDIT_EVENT_VIEWED",
        actor_user_id=current_user.user_id,
        object_type="audit_event",
        object_id=event.id,
        metadata={
            "viewed_event_id": event.id,
            "viewed_event_type": event.event_type,
        },
        request_context=request_context,
    )

    return _as_audit_event_response(event)


@admin_router.get(
    "/audit-integrity",
    response_model=AuditIntegrityResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def get_audit_integrity(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditIntegrityResponse:
    try:
        integrity = audit_service.verify_integrity()
    except AuditStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit store is unavailable.",
        ) from error

    audit_service.record_event_best_effort(
        event_type="AUDIT_LOG_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "returned_count": integrity.checked_rows,
        },
        request_context=request_context,
    )

    return AuditIntegrityResponse(
        checked_rows=integrity.checked_rows,
        chain_head=integrity.chain_head,
        is_valid=integrity.is_valid,
        first_invalid_chain_index=integrity.first_invalid_chain_index,
        first_invalid_event_id=integrity.first_invalid_event_id,
        detail=integrity.detail,
    )


@me_router.get(
    "/activity",
    response_model=AuditEventListResponse,
    dependencies=[Depends(require_authenticated_user)],
)
def my_activity(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditEventListResponse:
    try:
        events = audit_service.list_my_activity(
            actor_user_id=current_user.user_id,
            limit=limit,
        )
    except AuditStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit store is unavailable.",
        ) from error

    audit_service.record_event_best_effort(
        event_type="MY_ACTIVITY_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={"returned_count": len(events)},
        request_context=request_context,
    )

    return AuditEventListResponse(
        items=[_as_audit_event_response(event) for event in events],
        next_cursor=None,
    )
