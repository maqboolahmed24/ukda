from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user, require_platform_roles
from app.auth.models import SessionPrincipal
from app.telemetry.service import (
    AlertItem,
    ExporterStatus,
    RouteMetric,
    SloItem,
    TelemetryService,
    TimelineEvent,
    get_telemetry_service,
)

router = APIRouter(prefix="/admin/operations")

AlertStateQuery = Literal["OPEN", "OK", "UNAVAILABLE", "ALL"]
TimelineScopeQuery = Literal[
    "all", "api", "auth", "audit", "readiness", "operations", "worker", "telemetry"
]


class OperationsRouteMetricResponse(BaseModel):
    route_template: str = Field(serialization_alias="routeTemplate")
    method: str
    request_count: int = Field(serialization_alias="requestCount")
    error_count: int = Field(serialization_alias="errorCount")
    average_latency_ms: float | None = Field(
        default=None,
        serialization_alias="averageLatencyMs",
    )
    p95_latency_ms: float | None = Field(default=None, serialization_alias="p95LatencyMs")


class OperationsExporterStatusResponse(BaseModel):
    mode: str
    endpoint: str | None = None
    state: str
    detail: str


class OperationsOverviewResponse(BaseModel):
    generated_at: datetime = Field(serialization_alias="generatedAt")
    uptime_seconds: int = Field(serialization_alias="uptimeSeconds")
    request_count: int = Field(serialization_alias="requestCount")
    request_error_count: int = Field(serialization_alias="requestErrorCount")
    error_rate_percent: float = Field(serialization_alias="errorRatePercent")
    p95_latency_ms: float | None = Field(default=None, serialization_alias="p95LatencyMs")
    readiness_db_checks: int = Field(serialization_alias="readinessDbChecks")
    readiness_db_failures: int = Field(serialization_alias="readinessDbFailures")
    readiness_db_last_latency_ms: float | None = Field(
        default=None,
        serialization_alias="readinessDbLastLatencyMs",
    )
    readiness_db_avg_latency_ms: float | None = Field(
        default=None,
        serialization_alias="readinessDbAvgLatencyMs",
    )
    auth_success_count: int = Field(serialization_alias="authSuccessCount")
    auth_failure_count: int = Field(serialization_alias="authFailureCount")
    audit_write_success_count: int = Field(serialization_alias="auditWriteSuccessCount")
    audit_write_failure_count: int = Field(serialization_alias="auditWriteFailureCount")
    trace_context_enabled: bool = Field(serialization_alias="traceContextEnabled")
    queue_depth: int | None = Field(default=None, serialization_alias="queueDepth")
    queue_depth_source: str = Field(serialization_alias="queueDepthSource")
    queue_depth_detail: str = Field(serialization_alias="queueDepthDetail")
    exporter: OperationsExporterStatusResponse
    top_routes: list[OperationsRouteMetricResponse] = Field(serialization_alias="topRoutes")


class OperationsSloResponse(BaseModel):
    key: str
    name: str
    target: str
    current: str
    status: Literal["MEETING", "BREACHING", "UNAVAILABLE"]
    detail: str


class OperationsSloListResponse(BaseModel):
    items: list[OperationsSloResponse]


class OperationsAlertResponse(BaseModel):
    key: str
    title: str
    severity: Literal["CRITICAL", "WARNING", "INFO"]
    state: Literal["OPEN", "OK", "UNAVAILABLE"]
    detail: str
    threshold: str
    current: str
    updated_at: datetime = Field(serialization_alias="updatedAt")


class OperationsAlertListResponse(BaseModel):
    items: list[OperationsAlertResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class OperationsTimelineEventResponse(BaseModel):
    id: int
    occurred_at: datetime = Field(serialization_alias="occurredAt")
    scope: Literal["api", "auth", "audit", "readiness", "operations", "worker", "telemetry"]
    severity: Literal["INFO", "WARNING", "ERROR"]
    message: str
    request_id: str | None = Field(default=None, serialization_alias="requestId")
    trace_id: str | None = Field(default=None, serialization_alias="traceId")
    route_template: str | None = Field(default=None, serialization_alias="routeTemplate")
    status_code: int | None = Field(default=None, serialization_alias="statusCode")
    details_json: dict[str, object] = Field(serialization_alias="detailsJson")


class OperationsTimelineListResponse(BaseModel):
    items: list[OperationsTimelineEventResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


def _as_route_metric(metric: RouteMetric) -> OperationsRouteMetricResponse:
    return OperationsRouteMetricResponse(
        route_template=metric.route_template,
        method=metric.method,
        request_count=metric.request_count,
        error_count=metric.error_count,
        average_latency_ms=metric.average_latency_ms,
        p95_latency_ms=metric.p95_latency_ms,
    )


def _as_exporter_status(status: ExporterStatus) -> OperationsExporterStatusResponse:
    return OperationsExporterStatusResponse(
        mode=status.mode,
        endpoint=status.endpoint,
        state=status.state,
        detail=status.detail,
    )


def _as_slo(item: SloItem) -> OperationsSloResponse:
    return OperationsSloResponse(
        key=item.key,
        name=item.name,
        target=item.target,
        current=item.current,
        status=item.status,
        detail=item.detail,
    )


def _as_alert(item: AlertItem) -> OperationsAlertResponse:
    return OperationsAlertResponse(
        key=item.key,
        title=item.title,
        severity=item.severity,
        state=item.state,
        detail=item.detail,
        threshold=item.threshold,
        current=item.current,
        updated_at=item.updated_at,
    )


def _as_timeline(item: TimelineEvent) -> OperationsTimelineEventResponse:
    return OperationsTimelineEventResponse(
        id=item.id,
        occurred_at=item.occurred_at,
        scope=item.scope,
        severity=item.severity,
        message=item.message,
        request_id=item.request_id,
        trace_id=item.trace_id,
        route_template=item.route_template,
        status_code=item.status_code,
        details_json=item.details_json,
    )


@router.get(
    "/overview",
    response_model=OperationsOverviewResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def operations_overview(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> OperationsOverviewResponse:
    snapshot = telemetry_service.snapshot()
    audit_service.record_event_best_effort(
        event_type="OPERATIONS_OVERVIEW_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={"returned_count": len(snapshot.route_metrics)},
        request_context=request_context,
    )
    return OperationsOverviewResponse(
        generated_at=snapshot.generated_at,
        uptime_seconds=snapshot.uptime_seconds,
        request_count=snapshot.request_count,
        request_error_count=snapshot.request_error_count,
        error_rate_percent=snapshot.error_rate_percent,
        p95_latency_ms=snapshot.p95_latency_ms,
        readiness_db_checks=snapshot.readiness_db_checks,
        readiness_db_failures=snapshot.readiness_db_failures,
        readiness_db_last_latency_ms=snapshot.readiness_db_last_latency_ms,
        readiness_db_avg_latency_ms=snapshot.readiness_db_avg_latency_ms,
        auth_success_count=snapshot.auth_success_count,
        auth_failure_count=snapshot.auth_failure_count,
        audit_write_success_count=snapshot.audit_write_success_count,
        audit_write_failure_count=snapshot.audit_write_failure_count,
        trace_context_enabled=snapshot.trace_context_enabled,
        queue_depth=snapshot.queue_depth,
        queue_depth_source=snapshot.queue_depth_source,
        queue_depth_detail=snapshot.queue_depth_detail,
        exporter=_as_exporter_status(snapshot.exporter_status),
        top_routes=[_as_route_metric(metric) for metric in snapshot.route_metrics],
    )


@router.get(
    "/slos",
    response_model=OperationsSloListResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def operations_slos(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> OperationsSloListResponse:
    snapshot = telemetry_service.snapshot()
    slos = telemetry_service.evaluate_slos(snapshot)
    audit_service.record_event_best_effort(
        event_type="OPERATIONS_SLOS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={"returned_count": len(slos)},
        request_context=request_context,
    )
    return OperationsSloListResponse(items=[_as_slo(item) for item in slos])


@router.get(
    "/alerts",
    response_model=OperationsAlertListResponse,
    dependencies=[Depends(require_platform_roles("ADMIN"))],
)
def operations_alerts(
    state: AlertStateQuery = Query(default="OPEN"),
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> OperationsAlertListResponse:
    alerts, next_cursor = telemetry_service.list_alerts(
        state=state,
        cursor=cursor,
        page_size=page_size,
    )
    audit_service.record_event_best_effort(
        event_type="OPERATIONS_ALERTS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "state_filter": state,
            "cursor": cursor,
            "returned_count": len(alerts),
        },
        request_context=request_context,
    )
    return OperationsAlertListResponse(
        items=[_as_alert(item) for item in alerts],
        next_cursor=next_cursor,
    )


@router.get(
    "/timelines",
    response_model=OperationsTimelineListResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def operations_timelines(
    scope: TimelineScopeQuery = Query(default="all"),
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> OperationsTimelineListResponse:
    events, next_cursor = telemetry_service.list_timeline(
        scope=scope,
        cursor=cursor,
        page_size=page_size,
    )
    audit_service.record_event_best_effort(
        event_type="OPERATIONS_TIMELINE_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "scope_filter": scope,
            "cursor": cursor,
            "returned_count": len(events),
        },
        request_context=request_context,
    )
    return OperationsTimelineListResponse(
        items=[_as_timeline(item) for item in events],
        next_cursor=next_cursor,
    )
