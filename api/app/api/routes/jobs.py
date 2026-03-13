from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.jobs.models import JobEventRecord, JobRecord
from app.jobs.service import (
    JobNotFoundError,
    JobRetryConflictError,
    JobService,
    JobStoreUnavailableError,
    JobTransitionError,
    JobValidationError,
    get_job_service,
)
from app.projects.service import ProjectAccessDeniedError
from app.projects.store import ProjectNotFoundError

router = APIRouter(
    prefix="/projects/{project_id}/jobs",
    dependencies=[Depends(require_authenticated_user)],
)


class NoopJobCreateRequest(BaseModel):
    logical_key: str = Field(serialization_alias="logicalKey", min_length=2, max_length=120)
    mode: Literal["SUCCESS", "FAIL_ONCE", "FAIL_ALWAYS"] = "SUCCESS"
    max_attempts: int = Field(default=1, ge=1, le=10, serialization_alias="maxAttempts")
    delay_ms: int = Field(default=0, ge=0, le=10000, serialization_alias="delayMs")


class JobResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    attempt_number: int = Field(serialization_alias="attemptNumber")
    supersedes_job_id: str | None = Field(default=None, serialization_alias="supersedesJobId")
    superseded_by_job_id: str | None = Field(default=None, serialization_alias="supersededByJobId")
    type: Literal["NOOP"]
    dedupe_key: str = Field(serialization_alias="dedupeKey")
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
    attempts: int
    max_attempts: int = Field(serialization_alias="maxAttempts")
    payload_json: dict[str, object] = Field(serialization_alias="payloadJson")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    error_code: str | None = Field(default=None, serialization_alias="errorCode")
    error_message: str | None = Field(default=None, serialization_alias="errorMessage")
    cancel_requested: bool = Field(serialization_alias="cancelRequested")
    cancel_requested_by: str | None = Field(
        default=None,
        serialization_alias="cancelRequestedBy",
    )
    cancel_requested_at: datetime | None = Field(
        default=None,
        serialization_alias="cancelRequestedAt",
    )


class JobListResponse(BaseModel):
    items: list[JobResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class JobStatusResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
    attempts: int
    max_attempts: int = Field(serialization_alias="maxAttempts")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    error_code: str | None = Field(default=None, serialization_alias="errorCode")
    error_message: str | None = Field(default=None, serialization_alias="errorMessage")
    superseded_by_job_id: str | None = Field(default=None, serialization_alias="supersededByJobId")
    cancel_requested: bool = Field(serialization_alias="cancelRequested")


class JobEventResponse(BaseModel):
    id: int
    job_id: str = Field(serialization_alias="jobId")
    project_id: str = Field(serialization_alias="projectId")
    event_type: Literal[
        "JOB_CREATED",
        "JOB_STARTED",
        "JOB_SUCCEEDED",
        "JOB_FAILED",
        "JOB_CANCELED",
        "JOB_RETRY_APPENDED",
    ] = Field(serialization_alias="eventType")
    from_status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"] | None = Field(
        default=None,
        serialization_alias="fromStatus",
    )
    to_status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"] = Field(
        serialization_alias="toStatus"
    )
    actor_user_id: str | None = Field(default=None, serialization_alias="actorUserId")
    details_json: dict[str, object] = Field(serialization_alias="detailsJson")
    created_at: datetime = Field(serialization_alias="createdAt")


class JobEventListResponse(BaseModel):
    items: list[JobEventResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class JobMutationResponse(BaseModel):
    job: JobResponse
    created: bool
    reason: str


class JobCancelResponse(BaseModel):
    job: JobResponse
    terminal: bool


class ProjectJobSummaryResponse(BaseModel):
    running_jobs: int = Field(serialization_alias="runningJobs")
    last_job_status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"] | None = Field(
        default=None,
        serialization_alias="lastJobStatus",
    )


def _as_job_response(job: JobRecord) -> JobResponse:
    return JobResponse(
        id=job.id,
        project_id=job.project_id,
        attempt_number=job.attempt_number,
        supersedes_job_id=job.supersedes_job_id,
        superseded_by_job_id=job.superseded_by_job_id,
        type=job.type,
        dedupe_key=job.dedupe_key,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        payload_json=job.payload_json,
        created_by=job.created_by,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        canceled_by=job.canceled_by,
        canceled_at=job.canceled_at,
        error_code=job.error_code,
        error_message=job.error_message,
        cancel_requested=job.cancel_requested,
        cancel_requested_by=job.cancel_requested_by,
        cancel_requested_at=job.cancel_requested_at,
    )


def _as_status_response(job: JobRecord) -> JobStatusResponse:
    return JobStatusResponse(
        id=job.id,
        project_id=job.project_id,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        started_at=job.started_at,
        finished_at=job.finished_at,
        canceled_at=job.canceled_at,
        canceled_by=job.canceled_by,
        error_code=job.error_code,
        error_message=job.error_message,
        superseded_by_job_id=job.superseded_by_job_id,
        cancel_requested=job.cancel_requested,
    )


def _as_event_response(event: JobEventRecord) -> JobEventResponse:
    return JobEventResponse(
        id=event.id,
        job_id=event.job_id,
        project_id=event.project_id,
        event_type=event.event_type,
        from_status=event.from_status,
        to_status=event.to_status,
        actor_user_id=event.actor_user_id,
        details_json=event.details_json,
        created_at=event.created_at,
    )


def _record_job_read_audit(
    *,
    audit_service: AuditService,
    current_user: SessionPrincipal,
    request_context: AuditRequestContext,
    event_type: Literal["JOB_LIST_VIEWED", "JOB_RUN_VIEWED", "JOB_RUN_STATUS_VIEWED"],
    project_id: str,
    object_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    audit_service.record_event_best_effort(
        event_type=event_type,
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="job" if object_id else None,
        object_id=object_id,
        metadata=metadata,
        request_context=request_context,
    )


def _raise_http_from_error(
    *,
    error: Exception,
    current_user: SessionPrincipal,
    project_id: str,
    audit_service: AuditService,
    request_context: AuditRequestContext,
) -> None:
    if isinstance(error, ProjectNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, ProjectAccessDeniedError):
        audit_service.record_event_best_effort(
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_JOB_SCOPE"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            request_context=request_context,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, JobNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, (JobTransitionError, JobRetryConflictError)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if isinstance(error, JobValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    if isinstance(error, JobStoreUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Jobs service is unavailable.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected jobs route failure.",
    ) from error


@router.get("", response_model=JobListResponse)
def list_project_jobs(
    project_id: str,
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    job_service: JobService = Depends(get_job_service),
) -> JobListResponse:
    try:
        items, next_cursor = job_service.list_jobs(
            current_user=current_user,
            project_id=project_id,
            cursor=cursor,
            page_size=page_size,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    _record_job_read_audit(
        audit_service=audit_service,
        current_user=current_user,
        request_context=request_context,
        event_type="JOB_LIST_VIEWED",
        project_id=project_id,
        metadata={"cursor": cursor, "returned_count": len(items)},
    )
    return JobListResponse(
        items=[_as_job_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.post("", response_model=JobMutationResponse, status_code=status.HTTP_201_CREATED)
def enqueue_project_noop_job(
    project_id: str,
    payload: NoopJobCreateRequest,
    response: Response,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    job_service: JobService = Depends(get_job_service),
) -> JobMutationResponse:
    try:
        row, created, reason = job_service.enqueue_noop(
            current_user=current_user,
            project_id=project_id,
            logical_key=payload.logical_key,
            mode=payload.mode,
            max_attempts=payload.max_attempts,
            delay_ms=payload.delay_ms,
            request_context=request_context,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    if not created:
        response.status_code = status.HTTP_200_OK
    return JobMutationResponse(job=_as_job_response(row), created=created, reason=reason)


@router.get("/summary", response_model=ProjectJobSummaryResponse)
def get_project_jobs_summary(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    job_service: JobService = Depends(get_job_service),
) -> ProjectJobSummaryResponse:
    try:
        running_jobs, last_job_status = job_service.get_project_job_activity(
            current_user=current_user,
            project_id=project_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    _record_job_read_audit(
        audit_service=audit_service,
        current_user=current_user,
        request_context=request_context,
        event_type="JOB_LIST_VIEWED",
        project_id=project_id,
        metadata={"cursor": 0, "returned_count": 0},
    )
    return ProjectJobSummaryResponse(
        running_jobs=running_jobs,
        last_job_status=last_job_status,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_project_job(
    project_id: str,
    job_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    try:
        row = job_service.get_job(
            current_user=current_user,
            project_id=project_id,
            job_id=job_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    _record_job_read_audit(
        audit_service=audit_service,
        current_user=current_user,
        request_context=request_context,
        event_type="JOB_RUN_VIEWED",
        project_id=project_id,
        object_id=job_id,
        metadata={"status": row.status},
    )
    return _as_job_response(row)


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_project_job_status(
    project_id: str,
    job_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    job_service: JobService = Depends(get_job_service),
) -> JobStatusResponse:
    try:
        row = job_service.get_job_status(
            current_user=current_user,
            project_id=project_id,
            job_id=job_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    _record_job_read_audit(
        audit_service=audit_service,
        current_user=current_user,
        request_context=request_context,
        event_type="JOB_RUN_STATUS_VIEWED",
        project_id=project_id,
        object_id=job_id,
        metadata={"status": row.status},
    )
    return _as_status_response(row)


@router.get("/{job_id}/events", response_model=JobEventListResponse)
def list_project_job_events(
    project_id: str,
    job_id: str,
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=100, ge=1, le=200, alias="pageSize"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    job_service: JobService = Depends(get_job_service),
) -> JobEventListResponse:
    try:
        items, next_cursor = job_service.list_job_events(
            current_user=current_user,
            project_id=project_id,
            job_id=job_id,
            cursor=cursor,
            page_size=page_size,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    _record_job_read_audit(
        audit_service=audit_service,
        current_user=current_user,
        request_context=request_context,
        event_type="JOB_RUN_VIEWED",
        project_id=project_id,
        object_id=job_id,
        metadata={"cursor": cursor, "returned_count": len(items)},
    )
    return JobEventListResponse(
        items=[_as_event_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.post("/{job_id}/retry", response_model=JobMutationResponse)
def retry_project_job(
    project_id: str,
    job_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    job_service: JobService = Depends(get_job_service),
) -> JobMutationResponse:
    try:
        row, created, reason = job_service.retry_job(
            current_user=current_user,
            project_id=project_id,
            job_id=job_id,
            request_context=request_context,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )
    return JobMutationResponse(job=_as_job_response(row), created=created, reason=reason)


@router.post("/{job_id}/cancel", response_model=JobCancelResponse)
def cancel_project_job(
    project_id: str,
    job_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    job_service: JobService = Depends(get_job_service),
) -> JobCancelResponse:
    try:
        row, terminal = job_service.cancel_job(
            current_user=current_user,
            project_id=project_id,
            job_id=job_id,
            request_context=request_context,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )
    return JobCancelResponse(job=_as_job_response(row), terminal=terminal)
