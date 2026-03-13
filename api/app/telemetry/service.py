from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from ipaddress import ip_address
from threading import RLock
from typing import Literal
from urllib.parse import urlparse

from app.core.config import Settings, get_settings
from app.telemetry.logging import sanitize_telemetry_payload

TimelineScope = Literal["api", "auth", "audit", "readiness", "operations", "worker", "telemetry"]
TimelineSeverity = Literal["INFO", "WARNING", "ERROR"]
AlertState = Literal["OPEN", "OK", "UNAVAILABLE"]
SloState = Literal["MEETING", "BREACHING", "UNAVAILABLE"]


@dataclass(frozen=True)
class RouteMetric:
    route_template: str
    method: str
    request_count: int
    error_count: int
    average_latency_ms: float | None
    p95_latency_ms: float | None


@dataclass(frozen=True)
class TimelineEvent:
    id: int
    occurred_at: datetime
    scope: TimelineScope
    severity: TimelineSeverity
    message: str
    request_id: str | None
    trace_id: str | None
    route_template: str | None
    status_code: int | None
    details_json: dict[str, object]


@dataclass(frozen=True)
class ExporterStatus:
    mode: str
    endpoint: str | None
    state: str
    detail: str


@dataclass(frozen=True)
class TelemetrySnapshot:
    generated_at: datetime
    started_at: datetime
    request_count: int
    request_error_count: int
    error_rate_percent: float
    p95_latency_ms: float | None
    route_metrics: list[RouteMetric]
    readiness_db_checks: int
    readiness_db_failures: int
    readiness_db_last_latency_ms: float | None
    readiness_db_avg_latency_ms: float | None
    auth_success_count: int
    auth_failure_count: int
    audit_write_success_count: int
    audit_write_failure_count: int
    trace_context_enabled: bool
    queue_depth: int | None
    queue_depth_source: str
    queue_depth_detail: str
    exporter_status: ExporterStatus

    @property
    def uptime_seconds(self) -> int:
        return max(
            0,
            int((self.generated_at - self.started_at).total_seconds()),
        )


@dataclass(frozen=True)
class SloItem:
    key: str
    name: str
    target: str
    current: str
    status: SloState
    detail: str


@dataclass(frozen=True)
class AlertItem:
    key: str
    title: str
    severity: Literal["CRITICAL", "WARNING", "INFO"]
    state: AlertState
    detail: str
    threshold: str
    current: str
    updated_at: datetime


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    position = int(round((percentile / 100) * (len(ordered) - 1)))
    position = max(0, min(position, len(ordered) - 1))
    return round(ordered[position], 2)


def _safe_route_label(route_template: str) -> str:
    trimmed = route_template.strip()
    if not trimmed:
        return "/__unknown__"
    if len(trimmed) > 160:
        return f"{trimmed[:157]}..."
    return trimmed


def _safe_method_label(method: str) -> str:
    normalized = method.strip().upper()
    if not normalized:
        return "UNKNOWN"
    return normalized[:12]


def _sanitize_message(value: str, *, max_length: int = 240) -> str:
    collapsed = " ".join(value.replace("\n", " ").replace("\r", " ").split())
    return collapsed[:max_length]


def _is_internal_endpoint(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower().strip()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    if host.endswith(".internal") or host.endswith(".local"):
        return True
    try:
        address = ip_address(host)
    except ValueError:
        return False
    return bool(address.is_private or address.is_loopback)


class TelemetryService:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings
        self._lock = RLock()
        self._started_at = datetime.now(UTC)
        self._request_count = 0
        self._request_error_count = 0
        self._request_latencies_ms: deque[float] = deque(maxlen=4096)
        self._route_request_count: dict[tuple[str, str], int] = defaultdict(int)
        self._route_error_count: dict[tuple[str, str], int] = defaultdict(int)
        self._route_latencies_ms: dict[tuple[str, str], deque[float]] = defaultdict(
            lambda: deque(maxlen=1024)
        )
        self._readiness_db_checks = 0
        self._readiness_db_failures = 0
        self._readiness_db_latencies_ms: deque[float] = deque(maxlen=512)
        self._auth_success_count = 0
        self._auth_failure_count = 0
        self._audit_write_success_count = 0
        self._audit_write_failure_count = 0
        self._queue_depth: int | None = None
        self._queue_depth_source = "worker-queue"
        self._queue_depth_detail = (
            "Queue metrics are unavailable until jobs runtime is implemented."
        )
        self._timeline: deque[TimelineEvent] = deque(maxlen=settings.telemetry_timeline_limit)
        self._timeline_next_id = 1

    def reset_for_test(self) -> None:
        with self._lock:
            self._started_at = datetime.now(UTC)
            self._request_count = 0
            self._request_error_count = 0
            self._request_latencies_ms.clear()
            self._route_request_count.clear()
            self._route_error_count.clear()
            self._route_latencies_ms.clear()
            self._readiness_db_checks = 0
            self._readiness_db_failures = 0
            self._readiness_db_latencies_ms.clear()
            self._auth_success_count = 0
            self._auth_failure_count = 0
            self._audit_write_success_count = 0
            self._audit_write_failure_count = 0
            self._queue_depth = None
            self._queue_depth_source = "worker-queue"
            self._queue_depth_detail = (
                "Queue metrics are unavailable until jobs runtime is implemented."
            )
            self._timeline.clear()
            self._timeline_next_id = 1

    def _append_timeline_unlocked(
        self,
        *,
        scope: TimelineScope,
        severity: TimelineSeverity,
        message: str,
        request_id: str | None,
        trace_id: str | None,
        route_template: str | None = None,
        status_code: int | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        event = TimelineEvent(
            id=self._timeline_next_id,
            occurred_at=datetime.now(UTC),
            scope=scope,
            severity=severity,
            message=_sanitize_message(message),
            request_id=request_id.strip()[:128] if request_id else None,
            trace_id=trace_id.strip()[:32] if trace_id else None,
            route_template=_safe_route_label(route_template) if route_template else None,
            status_code=status_code,
            details_json=sanitize_telemetry_payload(details),
        )
        self._timeline_next_id += 1
        self._timeline.append(event)

    def record_timeline(
        self,
        *,
        scope: TimelineScope,
        severity: TimelineSeverity,
        message: str,
        request_id: str | None,
        trace_id: str | None,
        route_template: str | None = None,
        status_code: int | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        with self._lock:
            self._append_timeline_unlocked(
                scope=scope,
                severity=severity,
                message=message,
                request_id=request_id,
                trace_id=trace_id,
                route_template=route_template,
                status_code=status_code,
                details=details,
            )

    def record_request(
        self,
        *,
        route_template: str,
        method: str,
        status_code: int,
        duration_ms: float,
        request_id: str | None,
        trace_id: str | None,
        project_id: str | None = None,
    ) -> None:
        safe_route = _safe_route_label(route_template)
        safe_method = _safe_method_label(method)
        key = (safe_route, safe_method)
        safe_duration_ms = max(0.0, round(duration_ms, 2))

        with self._lock:
            self._request_count += 1
            self._request_latencies_ms.append(safe_duration_ms)
            self._route_request_count[key] += 1
            self._route_latencies_ms[key].append(safe_duration_ms)
            is_error = status_code >= 500
            if is_error:
                self._request_error_count += 1
                self._route_error_count[key] += 1
                self._append_timeline_unlocked(
                    scope="api",
                    severity="ERROR",
                    message="API route returned a server error.",
                    request_id=request_id,
                    trace_id=trace_id,
                    route_template=safe_route,
                    status_code=status_code,
                    details={
                        "method": safe_method,
                        "duration_ms": safe_duration_ms,
                        "project_id": project_id,
                    },
                )

    def record_readiness_database(self, *, duration_ms: float, success: bool) -> None:
        with self._lock:
            safe_duration_ms = max(0.0, round(duration_ms, 2))
            self._readiness_db_checks += 1
            self._readiness_db_latencies_ms.append(safe_duration_ms)
            if not success:
                self._readiness_db_failures += 1
                self._append_timeline_unlocked(
                    scope="readiness",
                    severity="WARNING",
                    message="Database readiness check failed.",
                    request_id=None,
                    trace_id=None,
                    route_template="/readyz",
                    status_code=None,
                    details={"duration_ms": safe_duration_ms},
                )

    def record_auth_result(
        self,
        *,
        success: bool,
        auth_source: str,
        reason: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        with self._lock:
            if success:
                self._auth_success_count += 1
                return
            self._auth_failure_count += 1
            self._append_timeline_unlocked(
                scope="auth",
                severity="WARNING",
                message="Authentication failure recorded.",
                request_id=request_id,
                trace_id=trace_id,
                details={
                    "auth_source": auth_source,
                    "reason": reason,
                },
            )

    def record_audit_write(self, *, success: bool, event_type: str) -> None:
        with self._lock:
            if success:
                self._audit_write_success_count += 1
                return
            self._audit_write_failure_count += 1
            self._append_timeline_unlocked(
                scope="audit",
                severity="ERROR",
                message="Audit event persistence failed.",
                request_id=None,
                trace_id=None,
                details={"event_type": event_type},
            )

    def record_queue_depth(
        self,
        *,
        queue_depth: int | None,
        source: str,
        detail: str,
    ) -> None:
        with self._lock:
            self._queue_depth = queue_depth if queue_depth is None else max(0, queue_depth)
            self._queue_depth_source = _sanitize_message(source, max_length=80)
            self._queue_depth_detail = _sanitize_message(detail, max_length=240)

    def _resolve_exporter_status_unlocked(self) -> ExporterStatus:
        mode = self._settings.telemetry_export_mode
        endpoint = self._settings.telemetry_otlp_endpoint
        if mode == "none":
            return ExporterStatus(
                mode=mode,
                endpoint=None,
                state="DISABLED",
                detail="Telemetry exporter is disabled by configuration.",
            )
        if not endpoint:
            return ExporterStatus(
                mode=mode,
                endpoint=None,
                state="MISCONFIGURED",
                detail="Exporter mode is enabled but TELEMETRY_OTLP_ENDPOINT is missing.",
            )
        if not _is_internal_endpoint(endpoint):
            return ExporterStatus(
                mode=mode,
                endpoint=endpoint,
                state="BLOCKED_PUBLIC_ENDPOINT",
                detail="Configured exporter endpoint is not internal-only.",
            )
        return ExporterStatus(
            mode=mode,
            endpoint=endpoint,
            state="CONFIGURED_INTERNAL",
            detail="Exporter endpoint is configured for internal-only telemetry routing.",
        )

    def snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            route_metrics: list[RouteMetric] = []
            for route_key, request_count in self._route_request_count.items():
                latencies = list(self._route_latencies_ms[route_key])
                route_metrics.append(
                    RouteMetric(
                        route_template=route_key[0],
                        method=route_key[1],
                        request_count=request_count,
                        error_count=self._route_error_count[route_key],
                        average_latency_ms=round(sum(latencies) / len(latencies), 2)
                        if latencies
                        else None,
                        p95_latency_ms=_percentile(latencies, 95),
                    )
                )
            route_metrics.sort(key=lambda item: item.request_count, reverse=True)

            db_latencies = list(self._readiness_db_latencies_ms)
            request_count = self._request_count
            request_error_count = self._request_error_count
            exporter_status = self._resolve_exporter_status_unlocked()

            return TelemetrySnapshot(
                generated_at=datetime.now(UTC),
                started_at=self._started_at,
                request_count=request_count,
                request_error_count=request_error_count,
                error_rate_percent=round(100 * _safe_ratio(request_error_count, request_count), 3),
                p95_latency_ms=_percentile(list(self._request_latencies_ms), 95),
                route_metrics=route_metrics[:20],
                readiness_db_checks=self._readiness_db_checks,
                readiness_db_failures=self._readiness_db_failures,
                readiness_db_last_latency_ms=round(db_latencies[-1], 2) if db_latencies else None,
                readiness_db_avg_latency_ms=round(sum(db_latencies) / len(db_latencies), 2)
                if db_latencies
                else None,
                auth_success_count=self._auth_success_count,
                auth_failure_count=self._auth_failure_count,
                audit_write_success_count=self._audit_write_success_count,
                audit_write_failure_count=self._audit_write_failure_count,
                trace_context_enabled=True,
                queue_depth=self._queue_depth,
                queue_depth_source=self._queue_depth_source,
                queue_depth_detail=self._queue_depth_detail,
                exporter_status=exporter_status,
            )

    def evaluate_slos(self, snapshot: TelemetrySnapshot) -> list[SloItem]:
        items: list[SloItem] = []

        availability_target = 99.0
        if snapshot.request_count == 0:
            availability_current = "n/a"
            availability_status: SloState = "UNAVAILABLE"
            availability_detail = "No requests have been observed in the current process."
        else:
            availability_value = 100.0 - snapshot.error_rate_percent
            availability_current = f"{availability_value:.3f}%"
            availability_status = (
                "MEETING" if availability_value >= availability_target else "BREACHING"
            )
            availability_detail = "Derived from in-process request success ratio."
        items.append(
            SloItem(
                key="service_availability",
                name="Service availability",
                target=f">= {availability_target:.1f}%",
                current=availability_current,
                status=availability_status,
                detail=availability_detail,
            )
        )

        latency_target = 800.0
        if snapshot.p95_latency_ms is None:
            latency_current = "n/a"
            latency_status: SloState = "UNAVAILABLE"
            latency_detail = "No request latency samples are available yet."
        else:
            latency_current = f"{snapshot.p95_latency_ms:.2f} ms"
            latency_status = "MEETING" if snapshot.p95_latency_ms <= latency_target else "BREACHING"
            latency_detail = "Calculated as in-process p95 request latency."
        items.append(
            SloItem(
                key="request_p95_latency",
                name="Request p95 latency",
                target=f"<= {latency_target:.0f} ms",
                current=latency_current,
                status=latency_status,
                detail=latency_detail,
            )
        )

        error_rate_target = 2.0
        if snapshot.request_count == 0:
            error_rate_current = "n/a"
            error_rate_status: SloState = "UNAVAILABLE"
            error_rate_detail = "No requests have been observed in the current process."
        else:
            error_rate_current = f"{snapshot.error_rate_percent:.3f}%"
            error_rate_status = (
                "MEETING" if snapshot.error_rate_percent <= error_rate_target else "BREACHING"
            )
            error_rate_detail = "Calculated from in-process request errors."
        items.append(
            SloItem(
                key="request_error_rate",
                name="Request error rate",
                target=f"<= {error_rate_target:.1f}%",
                current=error_rate_current,
                status=error_rate_status,
                detail=error_rate_detail,
            )
        )

        db_latency_target = 250.0
        if snapshot.readiness_db_last_latency_ms is None:
            db_latency_current = "n/a"
            db_latency_status: SloState = "UNAVAILABLE"
            db_latency_detail = "Database readiness checks have not run in this process."
        else:
            db_latency_current = f"{snapshot.readiness_db_last_latency_ms:.2f} ms"
            db_latency_status = (
                "MEETING"
                if snapshot.readiness_db_last_latency_ms <= db_latency_target
                else "BREACHING"
            )
            db_latency_detail = "Latest /readyz DB check latency."
        items.append(
            SloItem(
                key="db_readiness_latency",
                name="Database readiness latency",
                target=f"<= {db_latency_target:.0f} ms",
                current=db_latency_current,
                status=db_latency_status,
                detail=db_latency_detail,
            )
        )

        audit_failure_target = 1.0
        total_audit_writes = snapshot.audit_write_success_count + snapshot.audit_write_failure_count
        if total_audit_writes == 0:
            audit_failure_current = "n/a"
            audit_failure_status: SloState = "UNAVAILABLE"
            audit_failure_detail = "No audit writes observed in this process."
        else:
            audit_failure_percent = round(
                100 * _safe_ratio(snapshot.audit_write_failure_count, total_audit_writes),
                3,
            )
            audit_failure_current = f"{audit_failure_percent:.3f}%"
            audit_failure_status = (
                "MEETING" if audit_failure_percent <= audit_failure_target else "BREACHING"
            )
            audit_failure_detail = "Audit event write failure ratio."
        items.append(
            SloItem(
                key="audit_write_failure_rate",
                name="Audit write failure rate",
                target=f"<= {audit_failure_target:.1f}%",
                current=audit_failure_current,
                status=audit_failure_status,
                detail=audit_failure_detail,
            )
        )

        queue_depth_target = 200
        if snapshot.queue_depth is None:
            queue_current = "n/a"
            queue_status: SloState = "UNAVAILABLE"
            queue_detail = snapshot.queue_depth_detail
        else:
            queue_current = str(snapshot.queue_depth)
            queue_status = "MEETING" if snapshot.queue_depth <= queue_depth_target else "BREACHING"
            queue_detail = f"Unsuperseded queued jobs from {snapshot.queue_depth_source}."
        items.append(
            SloItem(
                key="queue_depth",
                name="Queue depth",
                target=f"<= {queue_depth_target}",
                current=queue_current,
                status=queue_status,
                detail=queue_detail,
            )
        )

        return items

    def evaluate_alerts(self, snapshot: TelemetrySnapshot) -> list[AlertItem]:
        slos = self.evaluate_slos(snapshot)
        alerts: list[AlertItem] = []
        now = snapshot.generated_at

        for slo in slos:
            if slo.status == "MEETING":
                state: AlertState = "OK"
                severity: Literal["CRITICAL", "WARNING", "INFO"] = "INFO"
            elif slo.status == "UNAVAILABLE":
                state = "UNAVAILABLE"
                severity = "WARNING"
            else:
                state = "OPEN"
                severity = "CRITICAL"

            alerts.append(
                AlertItem(
                    key=f"alert_{slo.key}",
                    title=slo.name,
                    severity=severity,
                    state=state,
                    detail=slo.detail,
                    threshold=slo.target,
                    current=slo.current,
                    updated_at=now,
                )
            )

        exporter_status = snapshot.exporter_status
        if exporter_status.state in {"MISCONFIGURED", "BLOCKED_PUBLIC_ENDPOINT"}:
            alerts.append(
                AlertItem(
                    key="alert_telemetry_exporter",
                    title="Telemetry exporter configuration",
                    severity="WARNING",
                    state="OPEN",
                    detail=exporter_status.detail,
                    threshold="internal-only endpoint",
                    current=exporter_status.state,
                    updated_at=now,
                )
            )

        return alerts

    def list_alerts(
        self,
        *,
        state: AlertState | Literal["ALL"],
        cursor: int,
        page_size: int,
    ) -> tuple[list[AlertItem], int | None]:
        snapshot = self.snapshot()
        all_alerts = self.evaluate_alerts(snapshot)

        filtered = all_alerts
        if state != "ALL":
            filtered = [alert for alert in all_alerts if alert.state == state]

        safe_cursor = max(0, cursor)
        safe_page_size = max(1, min(page_size, 200))
        selected = filtered[safe_cursor : safe_cursor + safe_page_size + 1]
        has_more = len(selected) > safe_page_size
        page_items = selected[:safe_page_size]
        next_cursor = safe_cursor + safe_page_size if has_more else None
        return page_items, next_cursor

    def list_timeline(
        self,
        *,
        scope: TimelineScope | Literal["all"],
        cursor: int,
        page_size: int,
    ) -> tuple[list[TimelineEvent], int | None]:
        with self._lock:
            ordered = list(reversed(self._timeline))

        if scope != "all":
            ordered = [event for event in ordered if event.scope == scope]

        safe_cursor = max(0, cursor)
        safe_page_size = max(1, min(page_size, 200))
        selected = ordered[safe_cursor : safe_cursor + safe_page_size + 1]
        has_more = len(selected) > safe_page_size
        page_items = selected[:safe_page_size]
        next_cursor = safe_cursor + safe_page_size if has_more else None
        return page_items, next_cursor


@lru_cache
def get_telemetry_service() -> TelemetryService:
    return TelemetryService(settings=get_settings())
