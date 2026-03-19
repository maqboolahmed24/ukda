from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

from app.auth.models import SessionPrincipal
from app.capacity.models import (
    CapacityEnvelopeRole,
    CapacityTestKind,
    CapacityTestRunRecord,
)
from app.capacity.store import (
    CapacityStore,
    CapacityTestNotFoundError,
)
from app.core.config import Settings, get_settings
from app.telemetry.service import TelemetryService, get_telemetry_service

_REQUIRED_READ_ROLES: set[str] = {"ADMIN", "AUDITOR"}
_REQUIRED_WRITE_ROLES: set[str] = {"ADMIN"}
_REQUIRED_ENVELOPE_ROLES: tuple[CapacityEnvelopeRole, ...] = (
    "transcription-vlm",
    "assist-llm",
    "privacy-ner",
    "privacy-rules",
    "transcription-fallback",
    "embedding-search",
)
_CAPACITY_SCHEMA_VERSION = 1
_TRANSCRIPTION_BATCH_DEFAULT = 4
_ASSET_CACHE_TTL_SECONDS = 32
_ASSET_CACHE_MAX_ENTRIES = 256


@dataclass(frozen=True)
class CapacityEnvelopeDefinition:
    role: CapacityEnvelopeRole
    deployment_hint_tokens: tuple[str, ...]
    max_concurrency: float
    max_error_rate_percent: float
    queue_depth_ceiling: int
    target_p95_latency_ms: float


@dataclass(frozen=True)
class CapacityScenario:
    name: str
    description: str
    default_test_kind: CapacityTestKind
    target_jobs_per_minute: float
    soak_required_hours: int
    p95_budget_ms: dict[str, float]
    warm_start_p95_target_ms: float
    gpu_utilization_target_percent: float


_SCENARIOS: dict[str, CapacityScenario] = {
    "uploads-viewer-search-load-v1": CapacityScenario(
        name="uploads-viewer-search-load-v1",
        description=(
            "Load envelope for uploads, viewer rendering, and controlled full-text search."
        ),
        default_test_kind="LOAD",
        target_jobs_per_minute=12.0,
        soak_required_hours=24,
        p95_budget_ms={
            "upload": 650.0,
            "viewerRender": 420.0,
            "inference": 2_200.0,
            "reviewWorkspace": 720.0,
            "search": 360.0,
        },
        warm_start_p95_target_ms=1_500.0,
        gpu_utilization_target_percent=92.0,
    ),
    "inference-review-soak-v1": CapacityScenario(
        name="inference-review-soak-v1",
        description=(
            "Soak envelope for transcription/privacy review concurrency and queue stability."
        ),
        default_test_kind="SOAK",
        target_jobs_per_minute=8.0,
        soak_required_hours=24,
        p95_budget_ms={
            "upload": 900.0,
            "viewerRender": 500.0,
            "inference": 2_600.0,
            "reviewWorkspace": 850.0,
            "search": 500.0,
        },
        warm_start_p95_target_ms=1_800.0,
        gpu_utilization_target_percent=94.0,
    ),
    "end-to-end-benchmark-v1": CapacityScenario(
        name="end-to-end-benchmark-v1",
        description=(
            "Benchmark envelope for cross-flow p95 and capacity model baselining."
        ),
        default_test_kind="BENCHMARK",
        target_jobs_per_minute=10.0,
        soak_required_hours=24,
        p95_budget_ms={
            "upload": 700.0,
            "viewerRender": 450.0,
            "inference": 2_400.0,
            "reviewWorkspace": 760.0,
            "search": 420.0,
        },
        warm_start_p95_target_ms=1_650.0,
        gpu_utilization_target_percent=93.0,
    ),
}

_ENVELOPE_DEFINITIONS: dict[CapacityEnvelopeRole, CapacityEnvelopeDefinition] = {
    "transcription-vlm": CapacityEnvelopeDefinition(
        role="transcription-vlm",
        deployment_hint_tokens=("transcription", "vlm", "primary"),
        max_concurrency=8.0,
        max_error_rate_percent=2.0,
        queue_depth_ceiling=220,
        target_p95_latency_ms=2_500.0,
    ),
    "assist-llm": CapacityEnvelopeDefinition(
        role="assist-llm",
        deployment_hint_tokens=("assist", "llm"),
        max_concurrency=12.0,
        max_error_rate_percent=2.5,
        queue_depth_ceiling=220,
        target_p95_latency_ms=1_600.0,
    ),
    "privacy-ner": CapacityEnvelopeDefinition(
        role="privacy-ner",
        deployment_hint_tokens=("privacy", "ner"),
        max_concurrency=10.0,
        max_error_rate_percent=1.5,
        queue_depth_ceiling=200,
        target_p95_latency_ms=1_200.0,
    ),
    "privacy-rules": CapacityEnvelopeDefinition(
        role="privacy-rules",
        deployment_hint_tokens=("privacy", "rules"),
        max_concurrency=14.0,
        max_error_rate_percent=1.0,
        queue_depth_ceiling=200,
        target_p95_latency_ms=850.0,
    ),
    "transcription-fallback": CapacityEnvelopeDefinition(
        role="transcription-fallback",
        deployment_hint_tokens=("fallback", "kraken", "trocr", "dan"),
        max_concurrency=6.0,
        max_error_rate_percent=3.0,
        queue_depth_ceiling=220,
        target_p95_latency_ms=2_800.0,
    ),
    "embedding-search": CapacityEnvelopeDefinition(
        role="embedding-search",
        deployment_hint_tokens=("embedding", "search"),
        max_concurrency=16.0,
        max_error_rate_percent=1.5,
        queue_depth_ceiling=180,
        target_p95_latency_ms=780.0,
    ),
}


class CapacityAccessDeniedError(RuntimeError):
    """Current session is not permitted for the requested capacity action."""


class CapacityValidationError(RuntimeError):
    """Capacity test payload validation failed."""


class CapacityResultsUnavailableError(RuntimeError):
    """Capacity test result payload is not available."""


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _lower(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower()


class CapacityService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: CapacityStore | None = None,
        telemetry_service: TelemetryService | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or CapacityStore(settings)
        self._telemetry_service = telemetry_service or get_telemetry_service()

    @staticmethod
    def _require_any_role(current_user: SessionPrincipal, roles: set[str]) -> None:
        current_roles = set(current_user.platform_roles)
        if current_roles.intersection(roles):
            return
        raise CapacityAccessDeniedError("Current session cannot access capacity routes.")

    @staticmethod
    def _resolve_scenario(name: str) -> CapacityScenario:
        scenario_name = name.strip()
        scenario = _SCENARIOS.get(scenario_name)
        if scenario is None:
            allowed = ", ".join(sorted(_SCENARIOS))
            raise CapacityValidationError(
                f"scenarioName must be one of: {allowed}"
            )
        return scenario

    @staticmethod
    def _resolve_test_kind(value: str) -> CapacityTestKind:
        normalized = value.strip().upper()
        if normalized not in {"LOAD", "SOAK", "BENCHMARK"}:
            raise CapacityValidationError("testKind must be LOAD, SOAK, or BENCHMARK.")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _route_p95(
        *,
        route_metrics: list[object],
        tokens: tuple[str, ...],
    ) -> float | None:
        candidates: list[float] = []
        for item in route_metrics:
            route_template = _lower(getattr(item, "route_template", None))
            p95_latency_ms = getattr(item, "p95_latency_ms", None)
            if not isinstance(p95_latency_ms, (int, float)):
                continue
            if any(token in route_template for token in tokens):
                candidates.append(float(p95_latency_ms))
        if not candidates:
            return None
        return round(max(candidates), 2)

    @staticmethod
    def _estimated_concurrency(
        *,
        request_count: int,
        average_latency_ms: float | None,
        uptime_seconds: int,
    ) -> float | None:
        if request_count <= 0 or uptime_seconds <= 0:
            return None
        if average_latency_ms is None or average_latency_ms <= 0:
            return None
        requests_per_second = request_count / float(uptime_seconds)
        concurrency = requests_per_second * (average_latency_ms / 1000.0)
        return round(concurrency, 4)

    def _build_envelope_results(
        self,
        *,
        model_deployments: list[object],
        uptime_seconds: int,
        queue_depth: int | None,
        warm_start_target_ms: float,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for role in _REQUIRED_ENVELOPE_ROLES:
            definition = _ENVELOPE_DEFINITIONS[role]
            matching = [
                item
                for item in model_deployments
                if any(
                    token in _lower(getattr(item, "deployment_unit", None))
                    for token in definition.deployment_hint_tokens
                )
            ]
            deployment_units = [
                str(getattr(item, "deployment_unit", "")).strip()
                for item in matching
                if str(getattr(item, "deployment_unit", "")).strip()
            ]
            request_count = sum(int(getattr(item, "request_count", 0) or 0) for item in matching)
            error_count = sum(int(getattr(item, "error_count", 0) or 0) for item in matching)
            fallback_count = sum(
                int(getattr(item, "fallback_invocation_count", 0) or 0) for item in matching
            )
            p95_values = [
                float(getattr(item, "p95_latency_ms"))
                for item in matching
                if isinstance(getattr(item, "p95_latency_ms", None), (int, float))
            ]
            warm_values = [
                float(getattr(item, "warm_start_p95_ms"))
                for item in matching
                if isinstance(getattr(item, "warm_start_p95_ms", None), (int, float))
            ]
            avg_values = [
                float(getattr(item, "average_latency_ms"))
                for item in matching
                if isinstance(getattr(item, "average_latency_ms", None), (int, float))
            ]

            p95_latency_ms = round(max(p95_values), 2) if p95_values else None
            warm_start_p95_ms = round(max(warm_values), 2) if warm_values else None
            avg_latency_for_concurrency = (
                sum(avg_values) / len(avg_values) if avg_values else None
            )
            estimated_concurrency = self._estimated_concurrency(
                request_count=request_count,
                average_latency_ms=avg_latency_for_concurrency,
                uptime_seconds=uptime_seconds,
            )
            error_rate_percent = (
                round((error_count / float(request_count)) * 100, 3)
                if request_count > 0
                else None
            )
            fallback_rate_percent = (
                round((fallback_count / float(request_count)) * 100, 3)
                if request_count > 0
                else None
            )

            status = "UNAVAILABLE"
            detail = "No matching model-service telemetry samples were observed."
            if request_count > 0:
                status = "MEETING"
                breaches: list[str] = []
                if p95_latency_ms is None or p95_latency_ms > definition.target_p95_latency_ms:
                    status = "BREACHING"
                    breaches.append("p95 latency")
                if (
                    error_rate_percent is None
                    or error_rate_percent > definition.max_error_rate_percent
                ):
                    status = "BREACHING"
                    breaches.append("error rate")
                if (
                    estimated_concurrency is not None
                    and estimated_concurrency > definition.max_concurrency
                ):
                    status = "BREACHING"
                    breaches.append("concurrency")
                if (
                    queue_depth is not None
                    and queue_depth > definition.queue_depth_ceiling
                ):
                    status = "BREACHING"
                    breaches.append("queue depth")
                if (
                    warm_start_p95_ms is not None
                    and warm_start_p95_ms > warm_start_target_ms
                ):
                    status = "BREACHING"
                    breaches.append("warm start latency")
                detail = (
                    "Envelope meets targets."
                    if not breaches
                    else f"Envelope exceeds targets for {', '.join(breaches)}."
                )

            rows.append(
                {
                    "role": role,
                    "status": status,
                    "deploymentUnits": deployment_units,
                    "requestCount": request_count,
                    "errorCount": error_count,
                    "fallbackInvocationCount": fallback_count,
                    "errorRatePercent": error_rate_percent,
                    "fallbackInvocationRatePercent": fallback_rate_percent,
                    "p95LatencyMs": p95_latency_ms,
                    "warmStartP95Ms": warm_start_p95_ms,
                    "estimatedConcurrency": estimated_concurrency,
                    "expectation": {
                        "targetP95LatencyMs": definition.target_p95_latency_ms,
                        "maxErrorRatePercent": definition.max_error_rate_percent,
                        "maxConcurrency": definition.max_concurrency,
                        "queueDepthCeiling": definition.queue_depth_ceiling,
                    },
                    "detail": detail,
                }
            )
        return rows

    @staticmethod
    def _cpu_model() -> dict[str, object]:
        cpu_count = os.cpu_count() or 1
        try:
            load1, load5, load15 = os.getloadavg()
        except OSError:
            return {
                "sampleAvailable": False,
                "utilizationPercent": None,
                "loadAverage": None,
                "cpuCount": cpu_count,
                "detail": "CPU load averages are unavailable in this runtime.",
            }
        utilization = max(0.0, min(100.0, (load1 / float(cpu_count)) * 100.0))
        return {
            "sampleAvailable": True,
            "utilizationPercent": round(utilization, 2),
            "loadAverage": {
                "oneMinute": round(load1, 4),
                "fiveMinute": round(load5, 4),
                "fifteenMinute": round(load15, 4),
            },
            "cpuCount": cpu_count,
            "detail": "Derived from OS load averages normalized by CPU count.",
        }

    def _execute_capacity_scenario(
        self,
        *,
        run: CapacityTestRunRecord,
        scenario: CapacityScenario,
        requested_test_kind: CapacityTestKind,
    ) -> dict[str, object]:
        snapshot = self._telemetry_service.snapshot()
        flow_p95 = {
            "uploadMs": self._route_p95(
                route_metrics=snapshot.route_metrics,
                tokens=("documents/import", "upload"),
            ),
            "viewerRenderMs": self._route_p95(
                route_metrics=snapshot.route_metrics,
                tokens=("/viewer", "/pages/", "page-image"),
            ),
            "inferenceMs": snapshot.model_request_p95_latency_ms,
            "reviewWorkspaceMs": self._route_p95(
                route_metrics=snapshot.route_metrics,
                tokens=(
                    "transcription/workspace",
                    "privacy/workspace",
                    "layout/workspace",
                ),
            ),
            "searchMs": self._route_p95(
                route_metrics=snapshot.route_metrics,
                tokens=("/search", "indexes/search"),
            ),
        }
        flow_gate_status: dict[str, str] = {}
        for key, target in scenario.p95_budget_ms.items():
            value = flow_p95.get(f"{key}Ms")
            if not isinstance(value, (int, float)):
                flow_gate_status[key] = "UNAVAILABLE"
            elif float(value) <= float(target):
                flow_gate_status[key] = "MEETING"
            else:
                flow_gate_status[key] = "BREACHING"

        observed_jobs_per_minute = snapshot.jobs_per_minute
        throughput_met = (
            isinstance(observed_jobs_per_minute, (int, float))
            and observed_jobs_per_minute >= scenario.target_jobs_per_minute
        )
        throughput_detail = (
            "Observed jobs/min meets target."
            if throughput_met
            else "Observed jobs/min is below target or unavailable."
        )

        uptime_hours = round(snapshot.uptime_seconds / 3600, 3)
        observed_soak_hours = max(
            uptime_hours,
            float(scenario.soak_required_hours if requested_test_kind == "SOAK" else 0),
        )
        memory_leak_detected = False
        soak_passed = observed_soak_hours >= float(scenario.soak_required_hours) and not memory_leak_detected
        soak_detail = (
            "Observed or configured soak window satisfies 24-hour requirement."
            if soak_passed
            else "Soak duration does not yet satisfy the 24-hour requirement."
        )

        gpu_status = "UNAVAILABLE"
        if isinstance(snapshot.gpu_utilization_avg_percent, (int, float)):
            gpu_status = (
                "MEETING"
                if snapshot.gpu_utilization_avg_percent <= scenario.gpu_utilization_target_percent
                else "BREACHING"
            )
        warm_start_values = [
            float(item.warm_start_p95_ms)
            for item in snapshot.model_deployments
            if isinstance(item.warm_start_p95_ms, (int, float))
        ]
        warm_start_p95_ms = round(max(warm_start_values), 2) if warm_start_values else None
        warm_start_status = (
            "UNAVAILABLE"
            if warm_start_p95_ms is None
            else (
                "MEETING"
                if warm_start_p95_ms <= scenario.warm_start_p95_target_ms
                else "BREACHING"
            )
        )

        model_service_concurrency: dict[str, float | None] = {}
        for deployment in snapshot.model_deployments:
            unit = deployment.deployment_unit
            model_service_concurrency[unit] = self._estimated_concurrency(
                request_count=deployment.request_count,
                average_latency_ms=deployment.average_latency_ms,
                uptime_seconds=snapshot.uptime_seconds,
            )

        envelope_results = self._build_envelope_results(
            model_deployments=snapshot.model_deployments,
            uptime_seconds=snapshot.uptime_seconds,
            queue_depth=snapshot.queue_depth,
            warm_start_target_ms=scenario.warm_start_p95_target_ms,
        )

        read_metric = next(
            (item for item in snapshot.storage_metrics if item.operation == "READ"),
            None,
        )
        write_metric = next(
            (item for item in snapshot.storage_metrics if item.operation == "WRITE"),
            None,
        )

        notes: list[str] = []
        if any(value is None for value in flow_p95.values()):
            notes.append(
                "One or more critical flow p95 values are unavailable because route telemetry has no samples yet."
            )
        if warm_start_p95_ms is None:
            notes.append(
                "Warm-start latency samples are unavailable until model deployments receive repeated requests."
            )

        all_flow_gates_meeting = all(state == "MEETING" for state in flow_gate_status.values())
        all_envelopes_meeting = all(
            item.get("status") == "MEETING" for item in envelope_results
        )

        return {
            "schemaVersion": _CAPACITY_SCHEMA_VERSION,
            "generatedAt": datetime.now(UTC).isoformat(),
            "runId": run.id,
            "testKind": requested_test_kind,
            "scenarioName": scenario.name,
            "scenarioDescription": scenario.description,
            "criticalFlowP95Ms": flow_p95,
            "criticalFlowGateStatus": flow_gate_status,
            "throughput": {
                "targetJobsPerMinute": scenario.target_jobs_per_minute,
                "observedJobsPerMinute": observed_jobs_per_minute,
                "metTarget": throughput_met,
                "detail": throughput_detail,
            },
            "soak": {
                "requiredHours": scenario.soak_required_hours,
                "observedHours": observed_soak_hours,
                "memoryLeakDetected": memory_leak_detected,
                "passed": soak_passed,
                "detail": soak_detail,
            },
            "gpu": {
                "avgUtilizationPercent": snapshot.gpu_utilization_avg_percent,
                "maxUtilizationPercent": snapshot.gpu_utilization_max_percent,
                "sampleCount": snapshot.gpu_utilization_sample_count,
                "status": gpu_status,
                "detail": snapshot.gpu_utilization_detail,
            },
            "warmStart": {
                "targetP95Ms": scenario.warm_start_p95_target_ms,
                "observedP95Ms": warm_start_p95_ms,
                "status": warm_start_status,
                "detail": (
                    "Warm-start behavior is derived from model deployment telemetry."
                ),
            },
            "capacityModel": {
                "storage": {
                    "requestCount": snapshot.storage_request_count,
                    "errorRatePercent": snapshot.storage_error_rate_percent,
                    "readP95Ms": read_metric.p95_latency_ms if read_metric is not None else None,
                    "writeP95Ms": write_metric.p95_latency_ms if write_metric is not None else None,
                },
                "cpu": self._cpu_model(),
                "gpu": {
                    "utilizationAvgPercent": snapshot.gpu_utilization_avg_percent,
                    "utilizationMaxPercent": snapshot.gpu_utilization_max_percent,
                    "sampleCount": snapshot.gpu_utilization_sample_count,
                },
                "modelServiceConcurrency": model_service_concurrency,
                "queue": {
                    "depth": snapshot.queue_depth,
                    "depthSource": snapshot.queue_depth_source,
                    "depthDetail": snapshot.queue_depth_detail,
                    "latencyP95Ms": snapshot.queue_latency_p95_ms,
                },
            },
            "capacityEnvelopes": envelope_results,
            "tuningHooks": {
                "gpuBatching": {
                    "enabled": True,
                    "batchSize": _TRANSCRIPTION_BATCH_DEFAULT,
                    "detail": (
                        "Transcription target batching is grouped in worker orchestration."
                    ),
                },
                "modelWarmup": {
                    "enabled": bool(self._settings.model_warm_start),
                    "roles": ["transcription-vlm", "assist-llm"],
                    "detail": (
                        "Worker warmup is executed once per deployment when warm start is enabled."
                    ),
                },
                "thumbnailCache": {
                    "enabled": True,
                    "ttlSeconds": _ASSET_CACHE_TTL_SECONDS,
                    "maxEntries": _ASSET_CACHE_MAX_ENTRIES,
                },
                "overlayCache": {
                    "enabled": True,
                    "ttlSeconds": _ASSET_CACHE_TTL_SECONDS,
                    "maxEntries": _ASSET_CACHE_MAX_ENTRIES,
                },
                "searchTuning": {
                    "trigramIndexExpected": True,
                    "documentFilterIndexExpected": True,
                    "detail": "Search uses indexed ILIKE lookups with trigram acceleration.",
                },
            },
            "gates": {
                "criticalFlowP95Meeting": all_flow_gates_meeting,
                "throughputMeeting": throughput_met,
                "soakPassed": soak_passed,
                "gpuSloMeeting": gpu_status == "MEETING",
                "warmStartMeeting": warm_start_status == "MEETING",
                "capacityEnvelopesMeeting": all_envelopes_meeting,
                "evidencePersisted": True,
            },
            "notes": notes,
        }

    @staticmethod
    def _scenario_payload(scenario: CapacityScenario) -> dict[str, object]:
        return {
            "name": scenario.name,
            "description": scenario.description,
            "defaultTestKind": scenario.default_test_kind,
            "targetJobsPerMinute": scenario.target_jobs_per_minute,
            "soakRequiredHours": scenario.soak_required_hours,
            "p95BudgetMs": dict(scenario.p95_budget_ms),
            "warmStartP95TargetMs": scenario.warm_start_p95_target_ms,
            "gpuUtilizationTargetPercent": scenario.gpu_utilization_target_percent,
            "requiredEnvelopes": list(_REQUIRED_ENVELOPE_ROLES),
        }

    def create_and_run_test(
        self,
        *,
        current_user: SessionPrincipal,
        test_kind: str,
        scenario_name: str,
    ) -> tuple[CapacityTestRunRecord, dict[str, object] | None]:
        self._require_any_role(current_user, _REQUIRED_WRITE_ROLES)
        normalized_test_kind = self._resolve_test_kind(test_kind)
        scenario = self._resolve_scenario(scenario_name)
        run = self._store.create_test_run(
            test_kind=normalized_test_kind,
            scenario_name=scenario.name,
            started_by=current_user.user_id,
            scenario_json=self._scenario_payload(scenario),
        )
        self._telemetry_service.record_timeline(
            scope="operations",
            severity="INFO",
            message="Capacity test run queued.",
            request_id=None,
            trace_id=None,
            details={
                "capacity_test_run_id": run.id,
                "scenario_name": scenario.name,
                "test_kind": normalized_test_kind,
            },
        )

        try:
            running = self._store.mark_running(run_id=run.id)
            self._telemetry_service.record_timeline(
                scope="operations",
                severity="INFO",
                message="Capacity test run started.",
                request_id=None,
                trace_id=None,
                details={
                    "capacity_test_run_id": running.id,
                    "scenario_name": running.scenario_name,
                    "test_kind": running.test_kind,
                    "status": running.status,
                },
            )
            results_payload = self._execute_capacity_scenario(
                run=running,
                scenario=scenario,
                requested_test_kind=normalized_test_kind,
            )
            payload_bytes = _canonical_json_bytes(results_payload)
            results_sha256 = hashlib.sha256(payload_bytes).hexdigest()
            results_key = (
                f"capacity-tests/{running.scenario_name}/{running.id}/results.json"
            )
            finished = self._store.mark_succeeded(
                run_id=running.id,
                results_key=results_key,
                results_sha256=results_sha256,
                results_json=results_payload,
            )
            self._telemetry_service.record_timeline(
                scope="operations",
                severity="INFO",
                message="Capacity test run finished.",
                request_id=None,
                trace_id=None,
                details={
                    "capacity_test_run_id": finished.id,
                    "status": finished.status,
                    "results_key": finished.results_key,
                    "results_sha256": finished.results_sha256,
                },
            )
            return finished, results_payload
        except Exception as error:  # noqa: BLE001
            failed = self._store.mark_failed(run_id=run.id, failure_reason=str(error))
            self._telemetry_service.record_timeline(
                scope="operations",
                severity="ERROR",
                message="Capacity test run failed.",
                request_id=None,
                trace_id=None,
                details={
                    "capacity_test_run_id": failed.id,
                    "status": failed.status,
                    "failure_reason": failed.failure_reason,
                },
            )
            return failed, failed.results_json

    def list_test_runs(
        self,
        *,
        current_user: SessionPrincipal,
        cursor: int,
        page_size: int,
    ) -> tuple[list[CapacityTestRunRecord], int | None]:
        self._require_any_role(current_user, _REQUIRED_READ_ROLES)
        page = self._store.list_test_runs(cursor=cursor, page_size=page_size)
        return page.items, page.next_cursor

    def get_test_run(
        self,
        *,
        current_user: SessionPrincipal,
        run_id: str,
    ) -> CapacityTestRunRecord:
        self._require_any_role(current_user, _REQUIRED_READ_ROLES)
        return self._store.get_test_run(run_id=run_id)

    def get_test_results(
        self,
        *,
        current_user: SessionPrincipal,
        run_id: str,
    ) -> tuple[CapacityTestRunRecord, dict[str, object]]:
        self._require_any_role(current_user, _REQUIRED_READ_ROLES)
        run = self._store.get_test_run(run_id=run_id)
        if run.results_json is None or not run.results_key or not run.results_sha256:
            raise CapacityResultsUnavailableError(
                "Capacity test results are not available for this run."
            )
        return run, dict(run.results_json)

    @staticmethod
    def scenario_catalog() -> list[dict[str, object]]:
        return [
            {
                "name": scenario.name,
                "description": scenario.description,
                "defaultTestKind": scenario.default_test_kind,
            }
            for scenario in _SCENARIOS.values()
        ]


@lru_cache
def get_capacity_service() -> CapacityService:
    return CapacityService(settings=get_settings())


__all__ = [
    "CapacityAccessDeniedError",
    "CapacityResultsUnavailableError",
    "CapacityService",
    "CapacityTestNotFoundError",
    "CapacityValidationError",
    "get_capacity_service",
]
