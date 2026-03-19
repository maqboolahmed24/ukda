from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user, require_platform_roles
from app.auth.models import SessionPrincipal
from app.exports.service import (
    ExportAccessDeniedError,
    ExportService,
    get_export_service,
)
from app.exports.store import ExportStoreUnavailableError
from app.operations.readiness import (
    ReadinessAuditService,
    get_readiness_audit_service,
)
from app.telemetry.service import (
    AlertItem,
    ExporterStatus,
    ModelDeploymentMetric,
    ModelMetric,
    RouteMetric,
    SloItem,
    StorageMetric,
    TelemetryService,
    TimelineEvent,
    get_telemetry_service,
)

router = APIRouter(prefix="/admin/operations")

AlertStateQuery = Literal["OPEN", "OK", "UNAVAILABLE", "ALL"]
TimelineScopeQuery = Literal[
    "all",
    "api",
    "auth",
    "audit",
    "model",
    "operations",
    "readiness",
    "storage",
    "telemetry",
    "worker",
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


class OperationsStorageMetricResponse(BaseModel):
    operation: Literal["READ", "WRITE"]
    request_count: int = Field(serialization_alias="requestCount")
    error_count: int = Field(serialization_alias="errorCount")
    average_latency_ms: float | None = Field(
        default=None,
        serialization_alias="averageLatencyMs",
    )
    p95_latency_ms: float | None = Field(default=None, serialization_alias="p95LatencyMs")


class OperationsModelDeploymentMetricResponse(BaseModel):
    deployment_unit: str = Field(serialization_alias="deploymentUnit")
    request_count: int = Field(serialization_alias="requestCount")
    error_count: int = Field(serialization_alias="errorCount")
    error_rate_percent: float = Field(serialization_alias="errorRatePercent")
    fallback_invocation_count: int = Field(serialization_alias="fallbackInvocationCount")
    fallback_invocation_rate_percent: float = Field(
        serialization_alias="fallbackInvocationRatePercent"
    )
    average_latency_ms: float | None = Field(
        default=None,
        serialization_alias="averageLatencyMs",
    )
    p95_latency_ms: float | None = Field(default=None, serialization_alias="p95LatencyMs")
    cold_start_p95_ms: float | None = Field(
        default=None,
        serialization_alias="coldStartP95Ms",
    )
    warm_start_p95_ms: float | None = Field(
        default=None,
        serialization_alias="warmStartP95Ms",
    )


class OperationsModelMetricResponse(BaseModel):
    model_key: str = Field(serialization_alias="modelKey")
    deployment_unit: str = Field(serialization_alias="deploymentUnit")
    request_count: int = Field(serialization_alias="requestCount")
    error_count: int = Field(serialization_alias="errorCount")
    error_rate_percent: float = Field(serialization_alias="errorRatePercent")
    fallback_invocation_count: int = Field(serialization_alias="fallbackInvocationCount")
    fallback_invocation_rate_percent: float = Field(
        serialization_alias="fallbackInvocationRatePercent"
    )
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


class OperationsExportAgingSummaryResponse(BaseModel):
    unstarted: int
    no_sla: int = Field(serialization_alias="noSla")
    on_track: int = Field(serialization_alias="onTrack")
    due_soon: int = Field(serialization_alias="dueSoon")
    overdue: int
    stale_open: int = Field(serialization_alias="staleOpen")


class OperationsExportReminderSummaryResponse(BaseModel):
    due: int
    sent_last_24h: int = Field(serialization_alias="sentLast24h")
    total: int


class OperationsExportEscalationSummaryResponse(BaseModel):
    due: int
    open_escalated: int = Field(serialization_alias="openEscalated")
    total: int


class OperationsExportRetentionSummaryResponse(BaseModel):
    pending_count: int = Field(serialization_alias="pendingCount")
    pending_window_days: int = Field(serialization_alias="pendingWindowDays")


class OperationsExportTerminalSummaryResponse(BaseModel):
    approved: int
    exported: int
    rejected: int
    returned: int


class OperationsExportPolicySummaryResponse(BaseModel):
    sla_hours: int = Field(serialization_alias="slaHours")
    reminder_after_hours: int = Field(serialization_alias="reminderAfterHours")
    reminder_cooldown_hours: int = Field(serialization_alias="reminderCooldownHours")
    escalation_after_sla_hours: int = Field(serialization_alias="escalationAfterSlaHours")
    escalation_cooldown_hours: int = Field(serialization_alias="escalationCooldownHours")
    stale_open_after_days: int = Field(serialization_alias="staleOpenAfterDays")
    retention_stale_open_days: int = Field(serialization_alias="retentionStaleOpenDays")
    retention_terminal_approved_days: int = Field(
        serialization_alias="retentionTerminalApprovedDays"
    )
    retention_terminal_other_days: int = Field(
        serialization_alias="retentionTerminalOtherDays"
    )


class OperationsExportStatusResponse(BaseModel):
    generated_at: datetime = Field(serialization_alias="generatedAt")
    open_request_count: int = Field(serialization_alias="openRequestCount")
    aging: OperationsExportAgingSummaryResponse
    reminders: OperationsExportReminderSummaryResponse
    escalations: OperationsExportEscalationSummaryResponse
    retention: OperationsExportRetentionSummaryResponse
    terminal: OperationsExportTerminalSummaryResponse
    policy: OperationsExportPolicySummaryResponse


class OperationsOverviewResponse(BaseModel):
    generated_at: datetime = Field(serialization_alias="generatedAt")
    uptime_seconds: int = Field(serialization_alias="uptimeSeconds")
    request_count: int = Field(serialization_alias="requestCount")
    request_error_count: int = Field(serialization_alias="requestErrorCount")
    error_rate_percent: float = Field(serialization_alias="errorRatePercent")
    p95_latency_ms: float | None = Field(default=None, serialization_alias="p95LatencyMs")
    jobs_per_minute: float | None = Field(default=None, serialization_alias="jobsPerMinute")
    jobs_completed_count: int = Field(serialization_alias="jobsCompletedCount")
    queue_latency_avg_ms: float | None = Field(
        default=None,
        serialization_alias="queueLatencyAvgMs",
    )
    queue_latency_p95_ms: float | None = Field(
        default=None,
        serialization_alias="queueLatencyP95Ms",
    )
    gpu_utilization_avg_percent: float | None = Field(
        default=None,
        serialization_alias="gpuUtilizationAvgPercent",
    )
    gpu_utilization_max_percent: float | None = Field(
        default=None,
        serialization_alias="gpuUtilizationMaxPercent",
    )
    gpu_utilization_sample_count: int = Field(
        serialization_alias="gpuUtilizationSampleCount"
    )
    gpu_utilization_source: str = Field(serialization_alias="gpuUtilizationSource")
    gpu_utilization_detail: str = Field(serialization_alias="gpuUtilizationDetail")
    model_request_count: int = Field(serialization_alias="modelRequestCount")
    model_error_count: int = Field(serialization_alias="modelErrorCount")
    model_error_rate_percent: float | None = Field(
        default=None,
        serialization_alias="modelErrorRatePercent",
    )
    model_fallback_invocation_count: int = Field(
        serialization_alias="modelFallbackInvocationCount"
    )
    model_fallback_invocation_rate_percent: float | None = Field(
        default=None,
        serialization_alias="modelFallbackInvocationRatePercent",
    )
    model_request_p95_latency_ms: float | None = Field(
        default=None,
        serialization_alias="modelRequestP95LatencyMs",
    )
    export_review_latency_avg_ms: float | None = Field(
        default=None,
        serialization_alias="exportReviewLatencyAvgMs",
    )
    export_review_latency_p95_ms: float | None = Field(
        default=None,
        serialization_alias="exportReviewLatencyP95Ms",
    )
    export_review_latency_sample_count: int = Field(
        serialization_alias="exportReviewLatencySampleCount"
    )
    storage_request_count: int = Field(serialization_alias="storageRequestCount")
    storage_error_count: int = Field(serialization_alias="storageErrorCount")
    storage_error_rate_percent: float | None = Field(
        default=None,
        serialization_alias="storageErrorRatePercent",
    )
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
    storage: list[OperationsStorageMetricResponse]
    model_deployments: list[OperationsModelDeploymentMetricResponse] = Field(
        serialization_alias="modelDeployments"
    )
    models: list[OperationsModelMetricResponse]
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
    scope: Literal[
        "api",
        "auth",
        "audit",
        "model",
        "operations",
        "readiness",
        "storage",
        "worker",
        "telemetry",
    ]
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


class OperationsReadinessEvidenceResponse(BaseModel):
    label: str
    path: str
    sha256: str | None = None


class OperationsReadinessCheckResponse(BaseModel):
    id: str
    title: str
    status: Literal["PASS", "FAIL", "UNAVAILABLE"]
    blocking_policy: Literal["BLOCKING", "WARNING"] = Field(
        serialization_alias="blockingPolicy"
    )
    detail: str
    duration_seconds: float = Field(serialization_alias="durationSeconds")
    evidence: list[OperationsReadinessEvidenceResponse]
    command: str | None = None
    exit_code: int | None = Field(default=None, serialization_alias="exitCode")


class OperationsReadinessCategoryResponse(BaseModel):
    id: str
    title: str
    status: Literal["PASS", "FAIL", "UNAVAILABLE"]
    blocking_policy: Literal["BLOCKING", "WARNING"] = Field(
        serialization_alias="blockingPolicy"
    )
    summary: str
    auditor_visible: bool = Field(serialization_alias="auditorVisible")
    checks: list[OperationsReadinessCheckResponse]


class OperationsReadinessBlockerResponse(BaseModel):
    category_id: str = Field(serialization_alias="categoryId")
    check_id: str = Field(serialization_alias="checkId")
    detail: str
    evidence_path: str | None = Field(default=None, serialization_alias="evidencePath")


class OperationsReadinessResponse(BaseModel):
    matrix_version: str = Field(serialization_alias="matrixVersion")
    generated_at: datetime = Field(serialization_alias="generatedAt")
    overall_status: Literal["PASS", "FAIL", "UNAVAILABLE"] = Field(
        serialization_alias="overallStatus"
    )
    detail: str
    blocking_failure_count: int = Field(serialization_alias="blockingFailureCount")
    category_count: int = Field(serialization_alias="categoryCount")
    categories: list[OperationsReadinessCategoryResponse]
    blockers: list[OperationsReadinessBlockerResponse]


def _as_route_metric(metric: RouteMetric) -> OperationsRouteMetricResponse:
    return OperationsRouteMetricResponse(
        route_template=metric.route_template,
        method=metric.method,
        request_count=metric.request_count,
        error_count=metric.error_count,
        average_latency_ms=metric.average_latency_ms,
        p95_latency_ms=metric.p95_latency_ms,
    )


def _as_storage_metric(metric: StorageMetric) -> OperationsStorageMetricResponse:
    return OperationsStorageMetricResponse(
        operation=metric.operation,
        request_count=metric.request_count,
        error_count=metric.error_count,
        average_latency_ms=metric.average_latency_ms,
        p95_latency_ms=metric.p95_latency_ms,
    )


def _as_model_deployment_metric(
    metric: ModelDeploymentMetric,
) -> OperationsModelDeploymentMetricResponse:
    return OperationsModelDeploymentMetricResponse(
        deployment_unit=metric.deployment_unit,
        request_count=metric.request_count,
        error_count=metric.error_count,
        error_rate_percent=metric.error_rate_percent,
        fallback_invocation_count=metric.fallback_invocation_count,
        fallback_invocation_rate_percent=metric.fallback_invocation_rate_percent,
        average_latency_ms=metric.average_latency_ms,
        p95_latency_ms=metric.p95_latency_ms,
        cold_start_p95_ms=metric.cold_start_p95_ms,
        warm_start_p95_ms=metric.warm_start_p95_ms,
    )


def _as_model_metric(metric: ModelMetric) -> OperationsModelMetricResponse:
    return OperationsModelMetricResponse(
        model_key=metric.model_key,
        deployment_unit=metric.deployment_unit,
        request_count=metric.request_count,
        error_count=metric.error_count,
        error_rate_percent=metric.error_rate_percent,
        fallback_invocation_count=metric.fallback_invocation_count,
        fallback_invocation_rate_percent=metric.fallback_invocation_rate_percent,
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


def _raise_operations_export_status_error(error: Exception) -> None:
    if isinstance(error, ExportAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, ExportStoreUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Export operations status is unavailable.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(error),
    ) from error


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


def _as_readiness_response(
    payload: dict[str, object],
) -> OperationsReadinessResponse:
    categories = payload.get("categories")
    blockers = payload.get("blockers")
    generated_raw = str(payload.get("generatedAt", "")).strip()
    try:
        generated_at = datetime.fromisoformat(generated_raw)
    except ValueError:
        generated_at = datetime.now(UTC)
    return OperationsReadinessResponse(
        matrix_version=str(payload.get("matrixVersion", "")).strip(),
        generated_at=generated_at,
        overall_status=str(payload.get("overallStatus")),  # type: ignore[arg-type]
        detail=str(payload.get("detail", "")).strip(),
        blocking_failure_count=int(payload.get("blockingFailureCount", 0)),
        category_count=int(payload.get("categoryCount", 0)),
        categories=[
            OperationsReadinessCategoryResponse(
                id=str(item.get("id", "")).strip(),
                title=str(item.get("title", "")).strip(),
                status=str(item.get("status")),  # type: ignore[arg-type]
                blocking_policy=str(item.get("blockingPolicy")),  # type: ignore[arg-type]
                summary=str(item.get("summary", "")).strip(),
                auditor_visible=bool(item.get("auditorVisible", False)),
                checks=[
                    OperationsReadinessCheckResponse(
                        id=str(check.get("id", "")).strip(),
                        title=str(check.get("title", "")).strip(),
                        status=str(check.get("status")),  # type: ignore[arg-type]
                        blocking_policy=str(check.get("blockingPolicy")),  # type: ignore[arg-type]
                        detail=str(check.get("detail", "")).strip(),
                        duration_seconds=float(check.get("durationSeconds", 0) or 0),
                        evidence=[
                            OperationsReadinessEvidenceResponse(
                                label=str(ev.get("label", "")).strip(),
                                path=str(ev.get("path", "")).strip(),
                                sha256=(
                                    str(ev.get("sha256")).strip()
                                    if ev.get("sha256") is not None
                                    else None
                                ),
                            )
                            for ev in check.get("evidence", [])  # type: ignore[union-attr]
                            if isinstance(ev, dict)
                        ],
                        command=(
                            str(check.get("command", "")).strip()
                            if isinstance(check.get("command"), str)
                            and str(check.get("command", "")).strip()
                            else None
                        ),
                        exit_code=(
                            int(check.get("exitCode"))
                            if check.get("exitCode") is not None
                            else None
                        ),
                    )
                    for check in item.get("checks", [])  # type: ignore[union-attr]
                    if isinstance(check, dict)
                ],
            )
            for item in categories  # type: ignore[assignment]
            if isinstance(item, dict)
        ]
        if isinstance(categories, list)
        else [],
        blockers=[
            OperationsReadinessBlockerResponse(
                category_id=str(item.get("categoryId", "")).strip(),
                check_id=str(item.get("checkId", "")).strip(),
                detail=str(item.get("detail", "")).strip(),
                evidence_path=(
                    str(item.get("evidencePath")).strip()
                    if item.get("evidencePath") is not None
                    else None
                ),
            )
            for item in blockers  # type: ignore[assignment]
            if isinstance(item, dict)
        ]
        if isinstance(blockers, list)
        else [],
    )


_RECOVERY_TIMELINE_KEYS = {
    "drill_id",
    "drillId",
    "recovery_drill_id",
    "status",
    "started_at",
    "startedAt",
    "finished_at",
    "finishedAt",
    "summary",
    "summary_text",
    "summaryText",
    "evidence_summary_json",
    "evidenceSummaryJson",
    "evidence_summary",
    "evidenceSummary",
    "evidence_storage_key",
    "evidenceStorageKey",
    "evidence_storage_sha256",
    "evidenceStorageSha256",
    "evidence_sha256",
    "evidenceSha256",
    "evidence_key",
    "evidenceKey",
    "raw_failure_detail",
    "rawFailureDetail",
    "failure_reason",
    "failureReason",
}


def _is_recovery_timeline_event(item: TimelineEvent) -> bool:
    details = item.details_json
    if any(key in details for key in _RECOVERY_TIMELINE_KEYS):
        return True
    lowered_message = item.message.lower()
    return "recovery drill" in lowered_message or "recovery" in lowered_message


def _truncate_summary(value: str, *, max_len: int = 180) -> str:
    collapsed = " ".join(value.replace("\n", " ").replace("\r", " ").split())
    return collapsed[:max_len]


def _sanitize_recovery_timeline_for_auditor(item: TimelineEvent) -> TimelineEvent:
    details = item.details_json
    drill_id = details.get("drill_id")
    if not isinstance(drill_id, str) or not drill_id.strip():
        alt_drill_id = details.get("drillId")
        if isinstance(alt_drill_id, str) and alt_drill_id.strip():
            drill_id = alt_drill_id
    if not isinstance(drill_id, str) or not drill_id.strip():
        alt_drill_id = details.get("recovery_drill_id")
        drill_id = alt_drill_id if isinstance(alt_drill_id, str) else ""
    status_value = details.get("status")
    started_at = details.get("started_at")
    if not isinstance(started_at, str) or not started_at.strip():
        started_at = details.get("startedAt")
    finished_at = details.get("finished_at")
    if not isinstance(finished_at, str) or not finished_at.strip():
        finished_at = details.get("finishedAt")
    summary_value = details.get("summary")
    if not isinstance(summary_value, str) or not summary_value.strip():
        summary_value = details.get("summary_text")
    if not isinstance(summary_value, str) or not summary_value.strip():
        summary_value = details.get("summaryText")
    if not isinstance(summary_value, str) or not summary_value.strip():
        summary_value = item.message

    safe_details: dict[str, object] = {
        "drill_id": str(drill_id).strip(),
        "status": str(status_value).strip() if isinstance(status_value, str) else "UNKNOWN",
        "started_at": str(started_at).strip() if isinstance(started_at, str) else None,
        "finished_at": str(finished_at).strip() if isinstance(finished_at, str) else None,
        "summary": _truncate_summary(summary_value),
    }
    if safe_details["started_at"] in {None, ""}:
        safe_details["started_at"] = None
    if safe_details["finished_at"] in {None, ""}:
        safe_details["finished_at"] = None

    return TimelineEvent(
        id=item.id,
        occurred_at=item.occurred_at,
        scope=item.scope,
        severity=item.severity,
        message=_truncate_summary(str(safe_details["summary"])),
        request_id=item.request_id,
        trace_id=item.trace_id,
        route_template=item.route_template,
        status_code=item.status_code,
        details_json=safe_details,
    )


def _sanitize_timeline_for_auditor(item: TimelineEvent) -> TimelineEvent:
    if _is_recovery_timeline_event(item):
        return _sanitize_recovery_timeline_for_auditor(item)
    return item


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
        jobs_per_minute=snapshot.jobs_per_minute,
        jobs_completed_count=snapshot.jobs_completed_count,
        queue_latency_avg_ms=snapshot.queue_latency_avg_ms,
        queue_latency_p95_ms=snapshot.queue_latency_p95_ms,
        gpu_utilization_avg_percent=snapshot.gpu_utilization_avg_percent,
        gpu_utilization_max_percent=snapshot.gpu_utilization_max_percent,
        gpu_utilization_sample_count=snapshot.gpu_utilization_sample_count,
        gpu_utilization_source=snapshot.gpu_utilization_source,
        gpu_utilization_detail=snapshot.gpu_utilization_detail,
        model_request_count=snapshot.model_request_count,
        model_error_count=snapshot.model_error_count,
        model_error_rate_percent=snapshot.model_error_rate_percent,
        model_fallback_invocation_count=snapshot.model_fallback_invocation_count,
        model_fallback_invocation_rate_percent=snapshot.model_fallback_invocation_rate_percent,
        model_request_p95_latency_ms=snapshot.model_request_p95_latency_ms,
        export_review_latency_avg_ms=snapshot.export_review_latency_avg_ms,
        export_review_latency_p95_ms=snapshot.export_review_latency_p95_ms,
        export_review_latency_sample_count=snapshot.export_review_latency_sample_count,
        storage_request_count=snapshot.storage_request_count,
        storage_error_count=snapshot.storage_error_count,
        storage_error_rate_percent=snapshot.storage_error_rate_percent,
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
        storage=[_as_storage_metric(metric) for metric in snapshot.storage_metrics],
        model_deployments=[
            _as_model_deployment_metric(metric) for metric in snapshot.model_deployments
        ],
        models=[_as_model_metric(metric) for metric in snapshot.models],
        top_routes=[_as_route_metric(metric) for metric in snapshot.route_metrics],
    )


@router.get(
    "/export-status",
    response_model=OperationsExportStatusResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def operations_export_status(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    export_service: ExportService = Depends(get_export_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> OperationsExportStatusResponse:
    try:
        snapshot = export_service.get_export_operations_status(current_user=current_user)
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_operations_export_status_error(error)
    audit_service.record_event_best_effort(
        event_type="OPERATIONS_EXPORT_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "open_request_count": snapshot.open_request_count,
            "overdue_count": snapshot.aging_overdue_count,
            "escalation_due_count": snapshot.escalation_due_count,
            "retention_pending_count": snapshot.retention_pending_count,
        },
        request_context=request_context,
    )
    return OperationsExportStatusResponse(
        generated_at=snapshot.generated_at,
        open_request_count=snapshot.open_request_count,
        aging=OperationsExportAgingSummaryResponse(
            unstarted=snapshot.aging_unstarted_count,
            no_sla=snapshot.aging_no_sla_count,
            on_track=snapshot.aging_on_track_count,
            due_soon=snapshot.aging_due_soon_count,
            overdue=snapshot.aging_overdue_count,
            stale_open=snapshot.stale_open_count,
        ),
        reminders=OperationsExportReminderSummaryResponse(
            due=snapshot.reminder_due_count,
            sent_last_24h=snapshot.reminders_sent_last_24h,
            total=snapshot.reminders_sent_total,
        ),
        escalations=OperationsExportEscalationSummaryResponse(
            due=snapshot.escalation_due_count,
            open_escalated=snapshot.escalated_open_count,
            total=snapshot.escalations_total,
        ),
        retention=OperationsExportRetentionSummaryResponse(
            pending_count=snapshot.retention_pending_count,
            pending_window_days=snapshot.retention_pending_window_days,
        ),
        terminal=OperationsExportTerminalSummaryResponse(
            approved=snapshot.terminal_approved_count,
            exported=snapshot.terminal_exported_count,
            rejected=snapshot.terminal_rejected_count,
            returned=snapshot.terminal_returned_count,
        ),
        policy=OperationsExportPolicySummaryResponse(
            sla_hours=snapshot.policy_sla_hours,
            reminder_after_hours=snapshot.policy_reminder_after_hours,
            reminder_cooldown_hours=snapshot.policy_reminder_cooldown_hours,
            escalation_after_sla_hours=snapshot.policy_escalation_after_sla_hours,
            escalation_cooldown_hours=snapshot.policy_escalation_cooldown_hours,
            stale_open_after_days=snapshot.policy_stale_open_after_days,
            retention_stale_open_days=snapshot.policy_retention_stale_open_days,
            retention_terminal_approved_days=snapshot.policy_retention_terminal_approved_days,
            retention_terminal_other_days=snapshot.policy_retention_terminal_other_days,
        ),
    )


@router.get(
    "/readiness",
    response_model=OperationsReadinessResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def operations_readiness(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    readiness_audit_service: ReadinessAuditService = Depends(get_readiness_audit_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> OperationsReadinessResponse:
    is_admin = "ADMIN" in set(current_user.platform_roles)
    snapshot = readiness_audit_service.get_readiness_snapshot(
        include_admin_details=is_admin
    )
    payload = snapshot.to_dict()
    audit_service.record_event_best_effort(
        event_type="OPERATIONS_READINESS_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "overall_status": payload["overallStatus"],
            "blocking_failure_count": payload["blockingFailureCount"],
            "category_count": payload["categoryCount"],
        },
        request_context=request_context,
    )
    return _as_readiness_response(payload)


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
    is_admin = "ADMIN" in set(current_user.platform_roles)
    if not is_admin:
        events = [_sanitize_timeline_for_auditor(item) for item in events]
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
