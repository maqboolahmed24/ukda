from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditEventType, AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.pseudonyms.models import (
    PseudonymRegistryEntryEventRecord,
    PseudonymRegistryEntryRecord,
)
from app.pseudonyms.service import (
    PseudonymRegistryAccessDeniedError,
    PseudonymRegistryConflictError,
    PseudonymRegistryNotFoundError,
    PseudonymRegistryService,
    PseudonymRegistryValidationError,
    get_pseudonym_registry_service,
)
from app.pseudonyms.store import PseudonymRegistryStoreUnavailableError

router = APIRouter(
    prefix="/projects/{project_id}/pseudonym-registry",
    dependencies=[Depends(require_authenticated_user)],
)

PseudonymRegistryEntryStatusLiteral = Literal["ACTIVE", "RETIRED"]
PseudonymRegistryEntryEventTypeLiteral = Literal[
    "ENTRY_CREATED",
    "ENTRY_REUSED",
    "ENTRY_RETIRED",
]


class PseudonymRegistryEntryResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    source_run_id: str = Field(serialization_alias="sourceRunId")
    source_fingerprint_hmac_sha256: str = Field(
        serialization_alias="sourceFingerprintHmacSha256"
    )
    alias_value: str = Field(serialization_alias="aliasValue")
    policy_id: str = Field(serialization_alias="policyId")
    salt_version_ref: str = Field(serialization_alias="saltVersionRef")
    alias_strategy_version: str = Field(serialization_alias="aliasStrategyVersion")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    last_used_run_id: str | None = Field(default=None, serialization_alias="lastUsedRunId")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    status: PseudonymRegistryEntryStatusLiteral
    retired_at: datetime | None = Field(default=None, serialization_alias="retiredAt")
    retired_by: str | None = Field(default=None, serialization_alias="retiredBy")
    supersedes_entry_id: str | None = Field(
        default=None,
        serialization_alias="supersedesEntryId",
    )
    superseded_by_entry_id: str | None = Field(
        default=None,
        serialization_alias="supersededByEntryId",
    )


class PseudonymRegistryEntryListResponse(BaseModel):
    items: list[PseudonymRegistryEntryResponse]


class PseudonymRegistryEntryEventResponse(BaseModel):
    id: str
    entry_id: str = Field(serialization_alias="entryId")
    event_type: PseudonymRegistryEntryEventTypeLiteral = Field(
        serialization_alias="eventType"
    )
    run_id: str = Field(serialization_alias="runId")
    actor_user_id: str | None = Field(default=None, serialization_alias="actorUserId")
    created_at: datetime = Field(serialization_alias="createdAt")


class PseudonymRegistryEntryEventListResponse(BaseModel):
    items: list[PseudonymRegistryEntryEventResponse]


def _as_entry_response(
    record: PseudonymRegistryEntryRecord,
) -> PseudonymRegistryEntryResponse:
    return PseudonymRegistryEntryResponse(
        id=record.id,
        project_id=record.project_id,
        source_run_id=record.source_run_id,
        source_fingerprint_hmac_sha256=record.source_fingerprint_hmac_sha256,
        alias_value=record.alias_value,
        policy_id=record.policy_id,
        salt_version_ref=record.salt_version_ref,
        alias_strategy_version=record.alias_strategy_version,
        created_by=record.created_by,
        created_at=record.created_at,
        last_used_run_id=record.last_used_run_id,
        updated_at=record.updated_at,
        status=record.status,
        retired_at=record.retired_at,
        retired_by=record.retired_by,
        supersedes_entry_id=record.supersedes_entry_id,
        superseded_by_entry_id=record.superseded_by_entry_id,
    )


def _as_event_response(
    record: PseudonymRegistryEntryEventRecord,
) -> PseudonymRegistryEntryEventResponse:
    return PseudonymRegistryEntryEventResponse(
        id=record.id,
        entry_id=record.entry_id,
        event_type=record.event_type,
        run_id=record.run_id,
        actor_user_id=record.actor_user_id,
        created_at=record.created_at,
    )


def _record_audit_event(
    *,
    audit_service: AuditService,
    request_context: AuditRequestContext,
    event_type: AuditEventType,
    actor_user_id: str,
    project_id: str,
    object_type: str | None = None,
    object_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    audit_service.record_event_best_effort(
        event_type=event_type,
        actor_user_id=actor_user_id,
        project_id=project_id,
        object_type=object_type,
        object_id=object_id,
        metadata=metadata,
        request_context=request_context,
    )


def _handle_registry_exception(*, error: Exception) -> HTTPException:
    if isinstance(error, PseudonymRegistryAccessDeniedError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, PseudonymRegistryNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, PseudonymRegistryConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, PseudonymRegistryValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )
    if isinstance(error, PseudonymRegistryStoreUnavailableError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pseudonym registry store is unavailable.",
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected pseudonym registry failure.",
    )


@router.get("", response_model=PseudonymRegistryEntryListResponse)
def list_project_pseudonym_registry_entries(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    registry_service: PseudonymRegistryService = Depends(get_pseudonym_registry_service),
) -> PseudonymRegistryEntryListResponse:
    try:
        rows = registry_service.list_entries(
            current_user=current_user,
            project_id=project_id,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PseudonymRegistryAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": ["PROJECT_LEAD", "ADMIN", "AUDITOR"],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_registry_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="PSEUDONYM_REGISTRY_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(rows),
        },
    )
    return PseudonymRegistryEntryListResponse(
        items=[_as_entry_response(row) for row in rows]
    )


@router.get("/{entry_id}", response_model=PseudonymRegistryEntryResponse)
def get_project_pseudonym_registry_entry(
    project_id: str,
    entry_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    registry_service: PseudonymRegistryService = Depends(get_pseudonym_registry_service),
) -> PseudonymRegistryEntryResponse:
    try:
        entry = registry_service.get_entry(
            current_user=current_user,
            project_id=project_id,
            entry_id=entry_id,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PseudonymRegistryAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": ["PROJECT_LEAD", "ADMIN", "AUDITOR"],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_registry_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="PSEUDONYM_REGISTRY_ENTRY_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="pseudonym_registry_entry",
        object_id=entry.id,
        metadata={
            "route": request_context.route_template,
            "entry_id": entry.id,
        },
    )
    return _as_entry_response(entry)


@router.get("/{entry_id}/events", response_model=PseudonymRegistryEntryEventListResponse)
def list_project_pseudonym_registry_entry_events(
    project_id: str,
    entry_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    registry_service: PseudonymRegistryService = Depends(get_pseudonym_registry_service),
) -> PseudonymRegistryEntryEventListResponse:
    try:
        events = registry_service.list_entry_events(
            current_user=current_user,
            project_id=project_id,
            entry_id=entry_id,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PseudonymRegistryAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": ["PROJECT_LEAD", "ADMIN", "AUDITOR"],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_registry_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="PSEUDONYM_REGISTRY_EVENTS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="pseudonym_registry_entry",
        object_id=entry_id,
        metadata={
            "route": request_context.route_template,
            "entry_id": entry_id,
            "returned_count": len(events),
        },
    )
    return PseudonymRegistryEntryEventListResponse(
        items=[_as_event_response(event) for event in events]
    )
