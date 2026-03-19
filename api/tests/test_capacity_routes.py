from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.capacity.models import CapacityTestRunRecord
from app.capacity.service import (
    CapacityAccessDeniedError,
    CapacityResultsUnavailableError,
    CapacityTestNotFoundError,
    get_capacity_service,
)
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeCapacityService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self._run = CapacityTestRunRecord(
            id="capacity-run-1",
            test_kind="BENCHMARK",
            scenario_name="end-to-end-benchmark-v1",
            status="SUCCEEDED",
            results_key="capacity-tests/end-to-end-benchmark-v1/capacity-run-1/results.json",
            results_sha256="abc123",
            started_by="user-admin",
            started_at=now - timedelta(minutes=2),
            finished_at=now - timedelta(minutes=1),
            created_at=now - timedelta(minutes=3),
            scenario_json={"name": "end-to-end-benchmark-v1"},
            results_json={
                "schemaVersion": 1,
                "criticalFlowP95Ms": {
                    "uploadMs": 420.0,
                    "viewerRenderMs": 300.0,
                    "inferenceMs": 1300.0,
                    "reviewWorkspaceMs": 520.0,
                    "searchMs": 210.0,
                },
                "gates": {
                    "criticalFlowP95Meeting": True,
                    "throughputMeeting": True,
                    "soakPassed": True,
                    "gpuSloMeeting": True,
                    "warmStartMeeting": True,
                    "capacityEnvelopesMeeting": True,
                    "evidencePersisted": True,
                },
            },
            failure_reason=None,
        )
        self._run_without_results = CapacityTestRunRecord(
            id="capacity-run-missing",
            test_kind="SOAK",
            scenario_name="inference-review-soak-v1",
            status="FAILED",
            results_key=None,
            results_sha256=None,
            started_by="user-admin",
            started_at=now - timedelta(hours=1),
            finished_at=now - timedelta(minutes=20),
            created_at=now - timedelta(hours=2),
            scenario_json={"name": "inference-review-soak-v1"},
            results_json=None,
            failure_reason="synthetic-failure",
        )

    @staticmethod
    def _require_read(current_user: SessionPrincipal) -> None:
        if {"ADMIN", "AUDITOR"}.intersection(set(current_user.platform_roles)):
            return
        raise CapacityAccessDeniedError("Current session cannot access capacity routes.")

    @staticmethod
    def _require_write(current_user: SessionPrincipal) -> None:
        if "ADMIN" in set(current_user.platform_roles):
            return
        raise CapacityAccessDeniedError("Current session cannot access capacity routes.")

    @staticmethod
    def scenario_catalog() -> list[dict[str, object]]:
        return [
            {
                "name": "end-to-end-benchmark-v1",
                "description": "Benchmark scenario",
                "defaultTestKind": "BENCHMARK",
            }
        ]

    def create_and_run_test(
        self,
        *,
        current_user: SessionPrincipal,
        test_kind: str,
        scenario_name: str,
    ) -> tuple[CapacityTestRunRecord, dict[str, object] | None]:
        self._require_write(current_user)
        _ = (test_kind, scenario_name)
        return self._run, self._run.results_json

    def list_test_runs(
        self,
        *,
        current_user: SessionPrincipal,
        cursor: int,
        page_size: int,
    ) -> tuple[list[CapacityTestRunRecord], int | None]:
        self._require_read(current_user)
        _ = (cursor, page_size)
        return [self._run, self._run_without_results], None

    def get_test_run(
        self,
        *,
        current_user: SessionPrincipal,
        run_id: str,
    ) -> CapacityTestRunRecord:
        self._require_read(current_user)
        if run_id == self._run.id:
            return self._run
        if run_id == self._run_without_results.id:
            return self._run_without_results
        raise CapacityTestNotFoundError("Capacity run not found.")

    def get_test_results(
        self,
        *,
        current_user: SessionPrincipal,
        run_id: str,
    ) -> tuple[CapacityTestRunRecord, dict[str, object]]:
        self._require_read(current_user)
        if run_id == self._run.id and self._run.results_json is not None:
            return self._run, self._run.results_json
        if run_id == self._run_without_results.id:
            raise CapacityResultsUnavailableError("Capacity test results are unavailable.")
        raise CapacityTestNotFoundError("Capacity run not found.")


def _principal(*, roles: tuple[Literal["ADMIN", "AUDITOR"], ...]) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-capacity-route",
        auth_source="bearer",
        user_id="user-capacity-route",
        oidc_sub="oidc-user-capacity-route",
        email="capacity-route@test.local",
        display_name="Capacity Route User",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-capacity-route",
    )


@pytest.fixture(autouse=True)
def clear_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_capacity_create_requires_admin() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        roles=("AUDITOR",)
    )
    app.dependency_overrides[get_capacity_service] = lambda: FakeCapacityService()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    response = client.post(
        "/admin/capacity/tests",
        json={"testKind": "BENCHMARK", "scenarioName": "end-to-end-benchmark-v1"},
    )

    assert response.status_code == 403


def test_capacity_create_returns_persisted_run_for_admin() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        roles=("ADMIN",)
    )
    app.dependency_overrides[get_capacity_service] = lambda: FakeCapacityService()
    app.dependency_overrides[get_audit_service] = lambda: spy

    response = client.post(
        "/admin/capacity/tests",
        json={"testKind": "BENCHMARK", "scenarioName": "end-to-end-benchmark-v1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["id"] == "capacity-run-1"
    assert payload["run"]["status"] == "SUCCEEDED"
    assert payload["hasResults"] is True
    assert any(item.get("event_type") == "CAPACITY_TEST_RUN_CREATED" for item in spy.recorded)


def test_capacity_list_and_detail_allow_auditor() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        roles=("AUDITOR",)
    )
    app.dependency_overrides[get_capacity_service] = lambda: FakeCapacityService()
    app.dependency_overrides[get_audit_service] = lambda: spy

    list_response = client.get("/admin/capacity/tests")
    detail_response = client.get("/admin/capacity/tests/capacity-run-1")
    results_response = client.get("/admin/capacity/tests/capacity-run-1/results")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert results_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == "capacity-run-1"
    assert detail_response.json()["run"]["scenarioName"] == "end-to-end-benchmark-v1"
    assert results_response.json()["resultsSha256"] == "abc123"
    event_types = {item.get("event_type") for item in spy.recorded}
    assert "CAPACITY_TEST_RUNS_VIEWED" in event_types
    assert "CAPACITY_TEST_RUN_VIEWED" in event_types
    assert "CAPACITY_TEST_RESULTS_VIEWED" in event_types


def test_capacity_results_returns_409_when_unavailable() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        roles=("AUDITOR",)
    )
    app.dependency_overrides[get_capacity_service] = lambda: FakeCapacityService()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    response = client.get("/admin/capacity/tests/capacity-run-missing/results")

    assert response.status_code == 409
