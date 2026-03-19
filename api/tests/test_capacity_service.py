from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from app.auth.models import SessionPrincipal
from app.capacity.models import CapacityTestRunPage, CapacityTestRunRecord
from app.capacity.service import (
    CapacityAccessDeniedError,
    CapacityResultsUnavailableError,
    CapacityService,
)
from app.core.config import get_settings


class FakeCapacityStore:
    def __init__(self) -> None:
        self.runs: dict[str, CapacityTestRunRecord] = {}
        self._sequence = 0

    def _next_id(self) -> str:
        self._sequence += 1
        return f"capacity-test-{self._sequence}"

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def create_test_run(
        self,
        *,
        test_kind,
        scenario_name,
        started_by,
        scenario_json,
    ) -> CapacityTestRunRecord:
        run = CapacityTestRunRecord(
            id=self._next_id(),
            test_kind=test_kind,
            scenario_name=scenario_name,
            status="QUEUED",
            results_key=None,
            results_sha256=None,
            started_by=started_by,
            started_at=None,
            finished_at=None,
            created_at=self._now(),
            scenario_json=dict(scenario_json),
            results_json=None,
            failure_reason=None,
        )
        self.runs[run.id] = run
        return run

    def mark_running(self, *, run_id: str) -> CapacityTestRunRecord:
        run = self.runs[run_id]
        updated = replace(
            run,
            status="RUNNING",
            started_at=run.started_at or self._now(),
            failure_reason=None,
        )
        self.runs[run_id] = updated
        return updated

    def mark_succeeded(
        self,
        *,
        run_id: str,
        results_key: str,
        results_sha256: str,
        results_json: dict[str, object],
    ) -> CapacityTestRunRecord:
        run = self.runs[run_id]
        updated = replace(
            run,
            status="SUCCEEDED",
            results_key=results_key,
            results_sha256=results_sha256,
            results_json=dict(results_json),
            finished_at=self._now(),
            failure_reason=None,
        )
        self.runs[run_id] = updated
        return updated

    def mark_failed(self, *, run_id: str, failure_reason: str) -> CapacityTestRunRecord:
        run = self.runs[run_id]
        updated = replace(
            run,
            status="FAILED",
            finished_at=self._now(),
            failure_reason=failure_reason,
        )
        self.runs[run_id] = updated
        return updated

    def get_test_run(self, *, run_id: str) -> CapacityTestRunRecord:
        return self.runs[run_id]

    def list_test_runs(self, *, cursor: int, page_size: int) -> CapacityTestRunPage:
        ordered = sorted(
            self.runs.values(),
            key=lambda run: (run.created_at, run.id),
            reverse=True,
        )
        selected = ordered[cursor : cursor + page_size + 1]
        has_more = len(selected) > page_size
        items = selected[:page_size]
        return CapacityTestRunPage(
            items=items,
            next_cursor=(cursor + page_size) if has_more else None,
        )


class FakeTelemetryService:
    def __init__(self, *, uptime_seconds: int = 26 * 60 * 60) -> None:
        self.events: list[dict[str, object]] = []
        self._snapshot = self._build_snapshot(uptime_seconds=uptime_seconds)

    @staticmethod
    def _build_snapshot(*, uptime_seconds: int) -> SimpleNamespace:
        route_metrics = [
            SimpleNamespace(
                route_template="/projects/{projectId}/documents/import",
                p95_latency_ms=420.0,
            ),
            SimpleNamespace(
                route_template="/projects/{projectId}/documents/{documentId}/viewer",
                p95_latency_ms=310.0,
            ),
            SimpleNamespace(
                route_template="/projects/{projectId}/documents/{documentId}/transcription/workspace",
                p95_latency_ms=520.0,
            ),
            SimpleNamespace(
                route_template="/projects/{projectId}/search",
                p95_latency_ms=260.0,
            ),
        ]
        model_deployments = [
            SimpleNamespace(
                deployment_unit="transcription-vlm-primary",
                request_count=320,
                error_count=3,
                fallback_invocation_count=2,
                p95_latency_ms=1800.0,
                warm_start_p95_ms=1050.0,
                average_latency_ms=420.0,
            ),
            SimpleNamespace(
                deployment_unit="assist-llm-main",
                request_count=400,
                error_count=4,
                fallback_invocation_count=1,
                p95_latency_ms=1100.0,
                warm_start_p95_ms=720.0,
                average_latency_ms=240.0,
            ),
            SimpleNamespace(
                deployment_unit="privacy-ner-v1",
                request_count=380,
                error_count=2,
                fallback_invocation_count=0,
                p95_latency_ms=840.0,
                warm_start_p95_ms=640.0,
                average_latency_ms=210.0,
            ),
            SimpleNamespace(
                deployment_unit="privacy-rules-v1",
                request_count=450,
                error_count=0,
                fallback_invocation_count=0,
                p95_latency_ms=430.0,
                warm_start_p95_ms=300.0,
                average_latency_ms=120.0,
            ),
            SimpleNamespace(
                deployment_unit="fallback-kraken",
                request_count=90,
                error_count=2,
                fallback_invocation_count=5,
                p95_latency_ms=2100.0,
                warm_start_p95_ms=1400.0,
                average_latency_ms=520.0,
            ),
            SimpleNamespace(
                deployment_unit="embedding-search-v2",
                request_count=510,
                error_count=1,
                fallback_invocation_count=0,
                p95_latency_ms=410.0,
                warm_start_p95_ms=260.0,
                average_latency_ms=160.0,
            ),
        ]
        storage_metrics = [
            SimpleNamespace(operation="READ", p95_latency_ms=28.0),
            SimpleNamespace(operation="WRITE", p95_latency_ms=44.0),
        ]
        return SimpleNamespace(
            route_metrics=route_metrics,
            model_request_p95_latency_ms=1300.0,
            jobs_per_minute=14.0,
            uptime_seconds=uptime_seconds,
            gpu_utilization_avg_percent=74.0,
            gpu_utilization_max_percent=92.0,
            gpu_utilization_sample_count=18,
            gpu_utilization_detail="sampled",
            model_deployments=model_deployments,
            storage_metrics=storage_metrics,
            storage_request_count=1200,
            storage_error_rate_percent=0.2,
            queue_depth=72,
            queue_depth_source="jobs-store",
            queue_depth_detail="sample",
            queue_latency_p95_ms=210.0,
        )

    def snapshot(self) -> SimpleNamespace:
        return self._snapshot

    def record_timeline(self, **kwargs):  # type: ignore[no-untyped-def]
        self.events.append(kwargs)


def _principal(*, roles: tuple[str, ...]) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-capacity",
        auth_source="bearer",
        user_id="user-capacity",
        oidc_sub="oidc-user-capacity",
        email="capacity@test.local",
        display_name="Capacity User",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-capacity",
    )


def test_capacity_service_persists_results_and_capacity_envelopes() -> None:
    settings = get_settings()
    store = FakeCapacityStore()
    telemetry = FakeTelemetryService()
    service = CapacityService(settings=settings, store=store, telemetry_service=telemetry)

    run, results = service.create_and_run_test(
        current_user=_principal(roles=("ADMIN",)),
        test_kind="BENCHMARK",
        scenario_name="end-to-end-benchmark-v1",
    )

    assert run.status == "SUCCEEDED"
    assert run.results_key is not None
    assert run.results_sha256 is not None
    assert results is not None
    assert results["criticalFlowP95Ms"]["uploadMs"] is not None
    assert results["tuningHooks"]["gpuBatching"]["enabled"] is True
    assert results["tuningHooks"]["modelWarmup"]["enabled"] is settings.model_warm_start
    envelopes = results["capacityEnvelopes"]
    roles = {str(item["role"]) for item in envelopes if isinstance(item, dict)}
    assert roles == {
        "transcription-vlm",
        "assist-llm",
        "privacy-ner",
        "privacy-rules",
        "transcription-fallback",
        "embedding-search",
    }
    assert results["gates"]["evidencePersisted"] is True
    timeline_messages = {str(item.get("message")) for item in telemetry.events}
    assert "Capacity test run queued." in timeline_messages
    assert "Capacity test run started." in timeline_messages
    assert "Capacity test run finished." in timeline_messages


def test_capacity_service_enforces_role_boundaries() -> None:
    settings = get_settings()
    store = FakeCapacityStore()
    telemetry = FakeTelemetryService()
    service = CapacityService(settings=settings, store=store, telemetry_service=telemetry)
    admin = _principal(roles=("ADMIN",))
    auditor = _principal(roles=("AUDITOR",))

    run, _ = service.create_and_run_test(
        current_user=admin,
        test_kind="LOAD",
        scenario_name="uploads-viewer-search-load-v1",
    )
    listed, _ = service.list_test_runs(current_user=auditor, cursor=0, page_size=10)
    assert len(listed) == 1
    assert service.get_test_run(current_user=auditor, run_id=run.id).id == run.id
    assert service.get_test_results(current_user=auditor, run_id=run.id)[0].id == run.id

    with pytest.raises(CapacityAccessDeniedError):
        service.create_and_run_test(
            current_user=auditor,
            test_kind="LOAD",
            scenario_name="uploads-viewer-search-load-v1",
        )


def test_capacity_service_reports_results_unavailable_for_non_success_runs() -> None:
    settings = get_settings()
    store = FakeCapacityStore()
    telemetry = FakeTelemetryService()
    service = CapacityService(settings=settings, store=store, telemetry_service=telemetry)
    admin = _principal(roles=("ADMIN",))

    run = store.create_test_run(
        test_kind="LOAD",
        scenario_name="uploads-viewer-search-load-v1",
        started_by=admin.user_id,
        scenario_json={"name": "uploads-viewer-search-load-v1"},
    )
    store.mark_failed(run_id=run.id, failure_reason="synthetic-failure")

    with pytest.raises(CapacityResultsUnavailableError):
        service.get_test_results(current_user=admin, run_id=run.id)


def test_capacity_service_soak_evidence_tracks_required_duration() -> None:
    settings = get_settings()
    store = FakeCapacityStore()
    telemetry = FakeTelemetryService(uptime_seconds=28 * 60 * 60)
    service = CapacityService(settings=settings, store=store, telemetry_service=telemetry)

    _, results = service.create_and_run_test(
        current_user=_principal(roles=("ADMIN",)),
        test_kind="SOAK",
        scenario_name="inference-review-soak-v1",
    )

    assert results is not None
    assert results["soak"]["requiredHours"] == 24
    assert results["soak"]["observedHours"] >= 24
    assert results["soak"]["passed"] is True
