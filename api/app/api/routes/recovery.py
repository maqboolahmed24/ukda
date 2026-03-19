from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user, require_platform_roles
from app.auth.models import SessionPrincipal
from app.recovery.models import RecoveryDrillScope, RecoveryDrillStatus
from app.recovery.service import (
    RecoveryAccessDeniedError,
    RecoveryDrillNotFoundError,
    RecoveryDrillTransitionError,
    RecoveryEvidenceUnavailableError,
    RecoveryService,
    RecoveryValidationError,
    get_recovery_service,
)
from app.recovery.store import RecoveryStoreUnavailableError

router = APIRouter(prefix="/admin/recovery")


class RecoveryScopeCatalogItemResponse(BaseModel):
    scope: RecoveryDrillScope
    description: str


class RecoveryDrillSummaryResponse(BaseModel):
    id: str
    scope: RecoveryDrillScope
    status: RecoveryDrillStatus
    started_by: str = Field(serialization_alias="startedBy")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    evidence_storage_key: str | None = Field(default=None, serialization_alias="evidenceStorageKey")
    evidence_storage_sha256: str | None = Field(
        default=None,
        serialization_alias="evidenceStorageSha256",
    )
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class RecoveryStatusResponse(BaseModel):
    generated_at: datetime = Field(serialization_alias="generatedAt")
    mode: str
    degraded: bool
    summary: str
    active_drill_count: int = Field(serialization_alias="activeDrillCount")
    queue_depth: int = Field(serialization_alias="queueDepth")
    dead_letter_count: int = Field(serialization_alias="deadLetterCount")
    replay_eligible_count: int = Field(serialization_alias="replayEligibleCount")
    storage_root: str = Field(serialization_alias="storageRoot")
    model_artifact_root: str = Field(serialization_alias="modelArtifactRoot")
    latest_drill: dict[str, object] | None = Field(default=None, serialization_alias="latestDrill")
    supported_scopes: list[RecoveryScopeCatalogItemResponse] = Field(
        serialization_alias="supportedScopes"
    )


class RecoveryDrillListResponse(BaseModel):
    items: list[RecoveryDrillSummaryResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")
    scope_catalog: list[RecoveryScopeCatalogItemResponse] = Field(
        serialization_alias="scopeCatalog"
    )


class RecoveryDrillDetailResponse(BaseModel):
    drill: RecoveryDrillSummaryResponse
    has_evidence: bool = Field(serialization_alias="hasEvidence")


class RecoveryDrillStatusResponse(BaseModel):
    drill_id: str = Field(serialization_alias="drillId")
    status: RecoveryDrillStatus
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")


class RecoveryDrillEvidenceResponse(BaseModel):
    drill_id: str = Field(serialization_alias="drillId")
    evidence_storage_key: str | None = Field(default=None, serialization_alias="evidenceStorageKey")
    evidence_storage_sha256: str | None = Field(
        default=None,
        serialization_alias="evidenceStorageSha256",
    )
    evidence: dict[str, object]


class RecoveryDrillCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    scope: RecoveryDrillScope


class RecoveryDrillCreateResponse(BaseModel):
    drill: RecoveryDrillSummaryResponse
    has_evidence: bool = Field(serialization_alias="hasEvidence")


class RecoveryDrillCancelResponse(BaseModel):
    drill: RecoveryDrillSummaryResponse


def _as_drill_response(drill) -> RecoveryDrillSummaryResponse:  # type: ignore[no-untyped-def]
    return RecoveryDrillSummaryResponse(
        id=drill.id,
        scope=drill.scope,
        status=drill.status,
        started_by=drill.started_by,
        started_at=drill.started_at,
        finished_at=drill.finished_at,
        canceled_by=drill.canceled_by,
        canceled_at=drill.canceled_at,
        failure_reason=drill.failure_reason,
        evidence_storage_key=drill.evidence_storage_key,
        evidence_storage_sha256=drill.evidence_storage_sha256,
        created_at=drill.created_at,
        updated_at=drill.updated_at,
    )


def _raise_recovery_error(error: Exception) -> None:
    if isinstance(error, RecoveryAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, RecoveryValidationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    if isinstance(error, RecoveryDrillNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, RecoveryEvidenceUnavailableError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if isinstance(error, RecoveryDrillTransitionError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if isinstance(error, RecoveryStoreUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recovery persistence is unavailable.",
        ) from error
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@router.get(
    "/status",
    response_model=RecoveryStatusResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def get_recovery_status(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    recovery_service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryStatusResponse:
    try:
        payload = recovery_service.get_recovery_status(current_user=current_user)
    except Exception as error:  # pragma: no cover - mapped through typed error handler
        _raise_recovery_error(error)
    audit_service.record_event_best_effort(
        event_type="RECOVERY_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "mode": payload["mode"],
            "degraded": payload["degraded"],
            "active_drill_count": payload["activeDrillCount"],
        },
        request_context=request_context,
    )
    return RecoveryStatusResponse(
        generated_at=datetime.fromisoformat(str(payload["generatedAt"])),
        mode=str(payload["mode"]),
        degraded=bool(payload["degraded"]),
        summary=str(payload["summary"]),
        active_drill_count=int(payload["activeDrillCount"]),
        queue_depth=int(payload["queueDepth"]),
        dead_letter_count=int(payload["deadLetterCount"]),
        replay_eligible_count=int(payload["replayEligibleCount"]),
        storage_root=str(payload["storageRoot"]),
        model_artifact_root=str(payload["modelArtifactRoot"]),
        latest_drill=payload.get("latestDrill") if isinstance(payload.get("latestDrill"), dict) else None,
        supported_scopes=[
            RecoveryScopeCatalogItemResponse(
                scope=item["scope"],  # type: ignore[arg-type]
                description=str(item["description"]),
            )
            for item in payload["supportedScopes"]  # type: ignore[index]
            if isinstance(item, dict) and "scope" in item and "description" in item
        ],
    )


@router.get(
    "/drills",
    response_model=RecoveryDrillListResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def list_recovery_drills(
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    recovery_service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryDrillListResponse:
    try:
        items, next_cursor = recovery_service.list_drills(
            current_user=current_user,
            cursor=cursor,
            page_size=page_size,
        )
    except Exception as error:  # pragma: no cover - mapped through typed error handler
        _raise_recovery_error(error)
    audit_service.record_event_best_effort(
        event_type="RECOVERY_DRILLS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "cursor": cursor,
            "page_size": page_size,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return RecoveryDrillListResponse(
        items=[_as_drill_response(item) for item in items],
        next_cursor=next_cursor,
        scope_catalog=[
            RecoveryScopeCatalogItemResponse(
                scope=item["scope"],  # type: ignore[arg-type]
                description=str(item["description"]),
            )
            for item in recovery_service.scope_catalog()
        ],
    )


@router.post(
    "/drills",
    response_model=RecoveryDrillCreateResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def create_recovery_drill(
    payload: RecoveryDrillCreateRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    recovery_service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryDrillCreateResponse:
    try:
        run, evidence = recovery_service.create_and_run_drill(
            current_user=current_user,
            scope=payload.scope,
        )
    except Exception as error:  # pragma: no cover - mapped through typed error handler
        _raise_recovery_error(error)

    has_evidence = bool(evidence)
    audit_service.record_event_best_effort(
        event_type="RECOVERY_DRILL_CREATED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "drill_id": run.id,
            "scope": run.scope,
            "status": run.status,
            "has_evidence": has_evidence,
        },
        request_context=request_context,
    )
    if run.started_at is not None:
        audit_service.record_event_best_effort(
            event_type="RECOVERY_DRILL_STARTED",
            actor_user_id=current_user.user_id,
            metadata={
                "route": request_context.route_template,
                "drill_id": run.id,
                "scope": run.scope,
                "status": run.status,
            },
            request_context=request_context,
        )
    if run.status == "SUCCEEDED":
        audit_service.record_event_best_effort(
            event_type="RECOVERY_DRILL_FINISHED",
            actor_user_id=current_user.user_id,
            metadata={
                "route": request_context.route_template,
                "drill_id": run.id,
                "status": run.status,
                "evidence_storage_key": run.evidence_storage_key,
            },
            request_context=request_context,
        )
    if run.status == "FAILED":
        audit_service.record_event_best_effort(
            event_type="RECOVERY_DRILL_FAILED",
            actor_user_id=current_user.user_id,
            metadata={
                "route": request_context.route_template,
                "drill_id": run.id,
                "status": run.status,
                "failure_reason": run.failure_reason,
            },
            request_context=request_context,
        )

    return RecoveryDrillCreateResponse(
        drill=_as_drill_response(run),
        has_evidence=has_evidence,
    )


@router.get(
    "/drills/{drill_id}",
    response_model=RecoveryDrillDetailResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def get_recovery_drill(
    drill_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    recovery_service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryDrillDetailResponse:
    try:
        drill = recovery_service.get_drill(current_user=current_user, drill_id=drill_id)
    except Exception as error:  # pragma: no cover - mapped through typed error handler
        _raise_recovery_error(error)
    has_evidence = bool(drill.evidence_summary_json)
    audit_service.record_event_best_effort(
        event_type="RECOVERY_DRILL_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "drill_id": drill.id,
            "scope": drill.scope,
            "status": drill.status,
            "has_evidence": has_evidence,
        },
        request_context=request_context,
    )
    return RecoveryDrillDetailResponse(drill=_as_drill_response(drill), has_evidence=has_evidence)


@router.get(
    "/drills/{drill_id}/status",
    response_model=RecoveryDrillStatusResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def get_recovery_drill_status(
    drill_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    recovery_service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryDrillStatusResponse:
    try:
        drill = recovery_service.get_drill_status(current_user=current_user, drill_id=drill_id)
    except Exception as error:  # pragma: no cover - mapped through typed error handler
        _raise_recovery_error(error)
    audit_service.record_event_best_effort(
        event_type="RECOVERY_DRILL_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "drill_id": drill.id,
            "scope": drill.scope,
            "status": drill.status,
        },
        request_context=request_context,
    )
    return RecoveryDrillStatusResponse(
        drill_id=drill.id,
        status=drill.status,
        started_at=drill.started_at,
        finished_at=drill.finished_at,
        canceled_at=drill.canceled_at,
    )


@router.get(
    "/drills/{drill_id}/evidence",
    response_model=RecoveryDrillEvidenceResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def get_recovery_drill_evidence(
    drill_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    recovery_service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryDrillEvidenceResponse:
    try:
        drill, evidence = recovery_service.get_drill_evidence(
            current_user=current_user,
            drill_id=drill_id,
        )
    except Exception as error:  # pragma: no cover - mapped through typed error handler
        _raise_recovery_error(error)
    audit_service.record_event_best_effort(
        event_type="RECOVERY_DRILL_EVIDENCE_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "drill_id": drill.id,
            "status": drill.status,
            "evidence_storage_key": drill.evidence_storage_key,
        },
        request_context=request_context,
    )
    return RecoveryDrillEvidenceResponse(
        drill_id=drill.id,
        evidence_storage_key=drill.evidence_storage_key,
        evidence_storage_sha256=drill.evidence_storage_sha256,
        evidence=evidence,
    )


@router.post(
    "/drills/{drill_id}/cancel",
    response_model=RecoveryDrillCancelResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def cancel_recovery_drill(
    drill_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    recovery_service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryDrillCancelResponse:
    try:
        drill = recovery_service.cancel_drill(current_user=current_user, drill_id=drill_id)
    except Exception as error:  # pragma: no cover - mapped through typed error handler
        _raise_recovery_error(error)
    audit_service.record_event_best_effort(
        event_type="RECOVERY_DRILL_CANCELED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "drill_id": drill.id,
            "scope": drill.scope,
            "status": drill.status,
        },
        request_context=request_context,
    )
    return RecoveryDrillCancelResponse(drill=_as_drill_response(drill))
