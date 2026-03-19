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
from app.capacity.models import CapacityTestKind, CapacityTestStatus
from app.capacity.service import (
    CapacityAccessDeniedError,
    CapacityResultsUnavailableError,
    CapacityService,
    CapacityTestNotFoundError,
    CapacityValidationError,
    get_capacity_service,
)
from app.capacity.store import CapacityStoreUnavailableError

router = APIRouter(prefix="/admin/capacity")


class CapacityScenarioResponse(BaseModel):
    name: str
    description: str
    default_test_kind: CapacityTestKind = Field(serialization_alias="defaultTestKind")


class CapacityTestRunResponse(BaseModel):
    id: str
    test_kind: CapacityTestKind = Field(serialization_alias="testKind")
    scenario_name: str = Field(serialization_alias="scenarioName")
    status: CapacityTestStatus
    results_key: str | None = Field(default=None, serialization_alias="resultsKey")
    results_sha256: str | None = Field(default=None, serialization_alias="resultsSha256")
    started_by: str = Field(serialization_alias="startedBy")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")


class CapacityTestRunListResponse(BaseModel):
    items: list[CapacityTestRunResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")
    scenario_catalog: list[CapacityScenarioResponse] = Field(
        serialization_alias="scenarioCatalog"
    )


class CapacityTestRunDetailResponse(BaseModel):
    run: CapacityTestRunResponse
    has_results: bool = Field(serialization_alias="hasResults")


class CapacityTestRunResultsResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    results_key: str = Field(serialization_alias="resultsKey")
    results_sha256: str = Field(serialization_alias="resultsSha256")
    results: dict[str, object]


class CapacityTestCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    test_kind: Literal["LOAD", "SOAK", "BENCHMARK"] = Field(
        alias="testKind",
        serialization_alias="testKind",
    )
    scenario_name: str = Field(alias="scenarioName", serialization_alias="scenarioName")


class CapacityTestCreateResponse(BaseModel):
    run: CapacityTestRunResponse
    has_results: bool = Field(serialization_alias="hasResults")


def _as_run_response(run) -> CapacityTestRunResponse:  # type: ignore[no-untyped-def]
    return CapacityTestRunResponse(
        id=run.id,
        test_kind=run.test_kind,
        scenario_name=run.scenario_name,
        status=run.status,
        results_key=run.results_key,
        results_sha256=run.results_sha256,
        started_by=run.started_by,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        failure_reason=run.failure_reason,
    )


def _raise_capacity_error(error: Exception) -> None:
    if isinstance(error, CapacityAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, CapacityValidationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    if isinstance(error, CapacityTestNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, CapacityResultsUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    if isinstance(error, CapacityStoreUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Capacity test persistence is unavailable.",
        ) from error
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@router.post(
    "/tests",
    response_model=CapacityTestCreateResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def create_capacity_test(
    payload: CapacityTestCreateRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    capacity_service: CapacityService = Depends(get_capacity_service),
) -> CapacityTestCreateResponse:
    try:
        run, results = capacity_service.create_and_run_test(
            current_user=current_user,
            test_kind=payload.test_kind,
            scenario_name=payload.scenario_name,
        )
    except Exception as error:  # pragma: no cover - mapped through typed error handler
        _raise_capacity_error(error)
    has_results = results is not None and run.results_key is not None
    audit_service.record_event_best_effort(
        event_type="CAPACITY_TEST_RUN_CREATED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "test_kind": run.test_kind,
            "scenario_name": run.scenario_name,
            "status": run.status,
            "has_results": has_results,
        },
        request_context=request_context,
    )
    return CapacityTestCreateResponse(
        run=_as_run_response(run),
        has_results=has_results,
    )


@router.get(
    "/tests",
    response_model=CapacityTestRunListResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def list_capacity_tests(
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    capacity_service: CapacityService = Depends(get_capacity_service),
) -> CapacityTestRunListResponse:
    try:
        items, next_cursor = capacity_service.list_test_runs(
            current_user=current_user,
            cursor=cursor,
            page_size=page_size,
        )
    except Exception as error:  # pragma: no cover - mapped through typed error handler
        _raise_capacity_error(error)
    audit_service.record_event_best_effort(
        event_type="CAPACITY_TEST_RUNS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "cursor": cursor,
            "page_size": page_size,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return CapacityTestRunListResponse(
        items=[_as_run_response(item) for item in items],
        next_cursor=next_cursor,
        scenario_catalog=[
            CapacityScenarioResponse(
                name=str(item["name"]),
                description=str(item["description"]),
                default_test_kind=str(item["defaultTestKind"]),  # type: ignore[arg-type]
            )
            for item in capacity_service.scenario_catalog()
        ],
    )


@router.get(
    "/tests/{test_run_id}",
    response_model=CapacityTestRunDetailResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def get_capacity_test(
    test_run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    capacity_service: CapacityService = Depends(get_capacity_service),
) -> CapacityTestRunDetailResponse:
    try:
        run = capacity_service.get_test_run(current_user=current_user, run_id=test_run_id)
    except Exception as error:  # pragma: no cover - mapped through typed error handler
        _raise_capacity_error(error)
    has_results = run.results_json is not None
    audit_service.record_event_best_effort(
        event_type="CAPACITY_TEST_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "status": run.status,
            "has_results": has_results,
        },
        request_context=request_context,
    )
    return CapacityTestRunDetailResponse(
        run=_as_run_response(run),
        has_results=has_results,
    )


@router.get(
    "/tests/{test_run_id}/results",
    response_model=CapacityTestRunResultsResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def get_capacity_test_results(
    test_run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    capacity_service: CapacityService = Depends(get_capacity_service),
) -> CapacityTestRunResultsResponse:
    try:
        run, results = capacity_service.get_test_results(
            current_user=current_user,
            run_id=test_run_id,
        )
    except Exception as error:  # pragma: no cover - mapped through typed error handler
        _raise_capacity_error(error)
    assert run.results_key is not None
    assert run.results_sha256 is not None
    audit_service.record_event_best_effort(
        event_type="CAPACITY_TEST_RESULTS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "results_key": run.results_key,
        },
        request_context=request_context,
    )
    return CapacityTestRunResultsResponse(
        run_id=run.id,
        results_key=run.results_key,
        results_sha256=run.results_sha256,
        results=results,
    )
