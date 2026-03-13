import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.core.config import get_settings
from app.jobs.models import JobEventRecord, JobRecord
from app.jobs.service import (
    JobNotFoundError,
    JobRetryConflictError,
    JobService,
    JobTransitionError,
    get_job_service,
)
from app.main import app
from app.projects.models import ProjectSummary
from app.projects.service import ProjectAccessDeniedError, ProjectWorkspaceContext
from app.telemetry.service import get_telemetry_service
from fastapi.testclient import TestClient

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeTelemetryService:
    def record_queue_depth(self, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def record_timeline(self, **kwargs):  # type: ignore[no-untyped-def]
        return None


class FakeProjectService:
    def __init__(self) -> None:
        self._roles = {
            "project-1": {
                "user-lead": "PROJECT_LEAD",
                "user-researcher": "RESEARCHER",
                "user-reviewer": "REVIEWER",
            }
        }

    def resolve_workspace_context(
        self, *, current_user: SessionPrincipal, project_id: str
    ) -> ProjectWorkspaceContext:
        is_admin = "ADMIN" in set(current_user.platform_roles)
        role = self._roles.get(project_id, {}).get(current_user.user_id)
        if role is None and not is_admin:
            raise ProjectAccessDeniedError("Membership is required for this project route.")
        return ProjectWorkspaceContext(
            summary=ProjectSummary(
                id=project_id,
                name="Project Test",
                purpose="Testing jobs routes with deterministic fake store behavior.",
                status="ACTIVE",
                created_by="user-lead",
                created_at=datetime.now(UTC),
                intended_access_tier="CONTROLLED",
                baseline_policy_snapshot_id="baseline-phase0-v1",
                current_user_role=role,  # type: ignore[arg-type]
            ),
            is_member=role is not None,
            can_access_settings=is_admin or role == "PROJECT_LEAD",
            can_manage_members=is_admin or role == "PROJECT_LEAD",
        )


class FakeJobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, JobRecord] = {}
        self.events: list[JobEventRecord] = []
        self._event_id = 1

    @staticmethod
    def compute_dedupe_key(*, project_id: str, job_type: str, logical_key: str) -> str:
        return hashlib.sha256(f"{project_id}|{job_type}|{logical_key}".encode("utf-8")).hexdigest()

    def _append_event(
        self,
        *,
        job_id: str,
        project_id: str,
        event_type: str,
        from_status: str | None,
        to_status: str,
        actor_user_id: str | None,
    ) -> None:
        self.events.append(
            JobEventRecord(
                id=self._event_id,
                job_id=job_id,
                project_id=project_id,
                event_type=event_type,  # type: ignore[arg-type]
                from_status=from_status,  # type: ignore[arg-type]
                to_status=to_status,  # type: ignore[arg-type]
                actor_user_id=actor_user_id,
                details_json={},
                created_at=datetime.now(UTC),
            )
        )
        self._event_id += 1

    def list_project_jobs(
        self, *, project_id: str, cursor: int, page_size: int
    ) -> tuple[list[JobRecord], int | None]:
        ordered = sorted(
            [job for job in self.jobs.values() if job.project_id == project_id],
            key=lambda item: item.created_at,
            reverse=True,
        )
        selected = ordered[cursor : cursor + page_size + 1]
        has_more = len(selected) > page_size
        return selected[:page_size], cursor + page_size if has_more else None

    def get_job(self, *, project_id: str, job_id: str) -> JobRecord:
        row = self.jobs.get(job_id)
        if row is None or row.project_id != project_id:
            raise JobNotFoundError("Job not found.")
        return row

    def get_job_status(self, *, project_id: str, job_id: str) -> JobRecord:
        return self.get_job(project_id=project_id, job_id=job_id)

    def list_job_events(
        self, *, project_id: str, job_id: str, cursor: int, page_size: int
    ) -> tuple[list[JobEventRecord], int | None]:
        ordered = [
            event
            for event in self.events
            if event.project_id == project_id and event.job_id == job_id
        ]
        selected = ordered[cursor : cursor + page_size + 1]
        has_more = len(selected) > page_size
        return selected[:page_size], cursor + page_size if has_more else None

    def enqueue_job(
        self,
        *,
        project_id: str,
        job_type: str,
        dedupe_key: str,
        payload_json: dict[str, object],
        created_by: str,
        max_attempts: int,
        supersedes_job_id: str | None = None,
        event_type: str = "JOB_CREATED",
    ) -> tuple[JobRecord, bool, str]:
        for candidate in self.jobs.values():
            if (
                candidate.project_id == project_id
                and candidate.dedupe_key == dedupe_key
                and candidate.superseded_by_job_id is None
                and candidate.status in {"QUEUED", "RUNNING"}
            ):
                return candidate, False, "IN_FLIGHT"
        for candidate in self.jobs.values():
            if (
                candidate.project_id == project_id
                and candidate.dedupe_key == dedupe_key
                and candidate.superseded_by_job_id is None
                and candidate.status == "SUCCEEDED"
            ):
                return candidate, False, "SUCCEEDED"

        attempt_number = 1
        if supersedes_job_id is not None:
            supersedes = self.get_job(project_id=project_id, job_id=supersedes_job_id)
            if supersedes.superseded_by_job_id is not None:
                raise JobRetryConflictError("Retry target is already superseded.")
            attempt_number = supersedes.attempt_number + 1
        job_id = str(uuid4())
        row = JobRecord(
            id=job_id,
            project_id=project_id,
            attempt_number=attempt_number,
            supersedes_job_id=supersedes_job_id,
            superseded_by_job_id=None,
            type=job_type,  # type: ignore[arg-type]
            dedupe_key=dedupe_key,
            status="QUEUED",
            attempts=0,
            max_attempts=max_attempts,
            payload_json=payload_json,
            created_by=created_by,
            created_at=datetime.now(UTC),
            started_at=None,
            finished_at=None,
            canceled_by=None,
            canceled_at=None,
            error_code=None,
            error_message=None,
            cancel_requested_by=None,
            cancel_requested_at=None,
            lease_owner_id=None,
            lease_expires_at=None,
            last_heartbeat_at=None,
        )
        self.jobs[row.id] = row
        if supersedes_job_id is not None:
            supersedes_row = self.jobs[supersedes_job_id]
            self.jobs[supersedes_job_id] = replace(
                supersedes_row,
                superseded_by_job_id=row.id,
            )
        self._append_event(
            job_id=row.id,
            project_id=project_id,
            event_type=event_type,
            from_status=None,
            to_status="QUEUED",
            actor_user_id=created_by,
        )
        return row, True, "CREATED"

    def append_retry(
        self, *, project_id: str, job_id: str, actor_user_id: str
    ) -> tuple[JobRecord, bool, str]:
        current = self.get_job(project_id=project_id, job_id=job_id)
        if current.status not in {"FAILED", "CANCELED"}:
            raise JobTransitionError("Retry is allowed only for FAILED or CANCELED jobs.")
        return self.enqueue_job(
            project_id=project_id,
            job_type=current.type,
            dedupe_key=current.dedupe_key,
            payload_json=current.payload_json,
            created_by=actor_user_id,
            max_attempts=current.max_attempts,
            supersedes_job_id=current.id,
            event_type="JOB_RETRY_APPENDED",
        )

    def cancel_job(
        self, *, project_id: str, job_id: str, actor_user_id: str
    ) -> tuple[JobRecord, bool]:
        current = self.get_job(project_id=project_id, job_id=job_id)
        now = datetime.now(UTC)
        if current.status == "QUEUED":
            canceled = replace(
                current,
                status="CANCELED",
                canceled_by=actor_user_id,
                canceled_at=now,
                finished_at=now,
            )
            self.jobs[current.id] = canceled
            self._append_event(
                job_id=current.id,
                project_id=project_id,
                event_type="JOB_CANCELED",
                from_status="QUEUED",
                to_status="CANCELED",
                actor_user_id=actor_user_id,
            )
            return canceled, True
        if current.status == "RUNNING":
            running = replace(
                current,
                cancel_requested_by=current.cancel_requested_by or actor_user_id,
                cancel_requested_at=current.cancel_requested_at or now,
            )
            self.jobs[current.id] = running
            return running, False
        raise JobTransitionError("Cancel is allowed only for QUEUED or RUNNING jobs.")

    def claim_next_job(self, *, worker_id: str, lease_seconds: int) -> JobRecord | None:
        now = datetime.now(UTC)
        for job in list(self.jobs.values()):
            if (
                job.status == "RUNNING"
                and job.lease_expires_at is not None
                and job.lease_expires_at <= now
            ):
                if job.attempts < job.max_attempts:
                    self.jobs[job.id] = replace(
                        job,
                        status="QUEUED",
                        lease_owner_id=None,
                        lease_expires_at=None,
                        last_heartbeat_at=None,
                    )
                else:
                    self.jobs[job.id] = replace(
                        job,
                        status="FAILED",
                        finished_at=now,
                        lease_owner_id=None,
                        lease_expires_at=None,
                        last_heartbeat_at=None,
                        error_code="WORKER_LEASE_EXPIRED",
                    )

        queued = sorted(
            [
                row
                for row in self.jobs.values()
                if row.status == "QUEUED" and row.superseded_by_job_id is None
            ],
            key=lambda item: item.created_at,
        )
        if not queued:
            return None
        row = queued[0]
        running = replace(
            row,
            status="RUNNING",
            attempts=row.attempts + 1,
            started_at=row.started_at or now,
            lease_owner_id=worker_id,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            last_heartbeat_at=now,
        )
        self.jobs[row.id] = running
        self._append_event(
            job_id=row.id,
            project_id=row.project_id,
            event_type="JOB_STARTED",
            from_status="QUEUED",
            to_status="RUNNING",
            actor_user_id=None,
        )
        return running

    def heartbeat_job(self, *, job_id: str, worker_id: str, lease_seconds: int) -> bool:
        current = self.jobs.get(job_id)
        if current is None or current.status != "RUNNING":
            return False
        if current.lease_owner_id != worker_id:
            return False
        now = datetime.now(UTC)
        self.jobs[job_id] = replace(
            current,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            last_heartbeat_at=now,
        )
        return True

    def finish_running_job(
        self,
        *,
        job_id: str,
        worker_id: str,
        success: bool,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> JobRecord:
        current = self.jobs[job_id]
        if current.status != "RUNNING":
            raise JobTransitionError("Only RUNNING jobs may be finalized.")
        now = datetime.now(UTC)
        if current.cancel_requested_at is not None:
            canceled = replace(
                current,
                status="CANCELED",
                canceled_by=current.cancel_requested_by,
                canceled_at=current.cancel_requested_at,
                finished_at=now,
                lease_owner_id=None,
                lease_expires_at=None,
                last_heartbeat_at=None,
            )
            self.jobs[job_id] = canceled
            self._append_event(
                job_id=job_id,
                project_id=current.project_id,
                event_type="JOB_CANCELED",
                from_status="RUNNING",
                to_status="CANCELED",
                actor_user_id=current.cancel_requested_by,
            )
            return canceled
        if success:
            completed = replace(
                current,
                status="SUCCEEDED",
                finished_at=now,
                lease_owner_id=None,
                lease_expires_at=None,
                last_heartbeat_at=None,
            )
            self.jobs[job_id] = completed
            self._append_event(
                job_id=job_id,
                project_id=current.project_id,
                event_type="JOB_SUCCEEDED",
                from_status="RUNNING",
                to_status="SUCCEEDED",
                actor_user_id=None,
            )
            return completed
        failed = replace(
            current,
            status="FAILED",
            finished_at=now,
            error_code=error_code,
            error_message=error_message,
            lease_owner_id=None,
            lease_expires_at=None,
            last_heartbeat_at=None,
        )
        self.jobs[job_id] = failed
        self._append_event(
            job_id=job_id,
            project_id=current.project_id,
            event_type="JOB_FAILED",
            from_status="RUNNING",
            to_status="FAILED",
            actor_user_id=None,
        )
        return failed

    def count_open_jobs(self) -> int:
        return sum(
            1
            for row in self.jobs.values()
            if row.status == "QUEUED" and row.superseded_by_job_id is None
        )

    def project_job_activity(self, *, project_id: str) -> tuple[int, str | None]:
        rows = [row for row in self.jobs.values() if row.project_id == project_id]
        running = sum(
            1 for row in rows if row.status == "RUNNING" and row.superseded_by_job_id is None
        )
        if not rows:
            return running, None
        last_status = sorted(rows, key=lambda row: row.created_at, reverse=True)[0].status
        return running, last_status


def _principal(
    *,
    user_id: str,
    email: str,
    platform_roles: tuple[Literal["ADMIN", "AUDITOR"], ...] = (),
) -> SessionPrincipal:
    return SessionPrincipal(
        session_id=f"session-{user_id}",
        auth_source="bearer",
        user_id=user_id,
        oidc_sub=f"oidc-{user_id}",
        email=email,
        display_name=email,
        platform_roles=platform_roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-test",
    )


@pytest.fixture
def job_service_fixture():
    spy_audit = SpyAuditService()
    fake_store = FakeJobStore()
    service = JobService(
        settings=get_settings(),
        store=fake_store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        audit_service=spy_audit,  # type: ignore[arg-type]
        telemetry_service=FakeTelemetryService(),  # type: ignore[arg-type]
    )
    return service, spy_audit, fake_store


@pytest.fixture(autouse=True)
def clear_overrides() -> None:
    telemetry_service = get_telemetry_service()
    telemetry_service.reset_for_test()
    yield
    app.dependency_overrides.clear()
    telemetry_service.reset_for_test()


def test_researcher_can_read_jobs_but_cannot_retry_or_cancel(job_service_fixture) -> None:
    job_service, spy_audit, _ = job_service_fixture
    app.dependency_overrides[get_job_service] = lambda: job_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-researcher",
        email="researcher@local.ukde",
    )

    create_response = client.post(
        "/projects/project-1/jobs",
        json={"logical_key": "read-job", "mode": "SUCCESS", "max_attempts": 1, "delay_ms": 0},
    )
    assert create_response.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-lead",
        email="lead@local.ukde",
    )
    created = client.post(
        "/projects/project-1/jobs",
        json={"logical_key": "read-job", "mode": "SUCCESS", "max_attempts": 1, "delay_ms": 0},
    )
    assert created.status_code == 201
    job_id = created.json()["job"]["id"]

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-researcher",
        email="researcher@local.ukde",
    )
    assert client.get("/projects/project-1/jobs").status_code == 200
    assert client.get(f"/projects/project-1/jobs/{job_id}").status_code == 200
    assert client.get(f"/projects/project-1/jobs/{job_id}/status").status_code == 200
    assert client.post(f"/projects/project-1/jobs/{job_id}/retry").status_code == 403
    assert client.post(f"/projects/project-1/jobs/{job_id}/cancel").status_code == 403


def test_enqueue_worker_success_and_status_flow(job_service_fixture) -> None:
    job_service, spy_audit, _ = job_service_fixture
    app.dependency_overrides[get_job_service] = lambda: job_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-lead",
        email="lead@local.ukde",
    )

    create_response = client.post(
        "/projects/project-1/jobs",
        json={"logical_key": "success-flow", "mode": "SUCCESS", "max_attempts": 1, "delay_ms": 0},
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["job"]["id"]

    completed = job_service.run_worker_once(worker_id="worker-1", lease_seconds=30)
    assert completed is not None
    assert completed.id == job_id
    assert completed.status == "SUCCEEDED"

    status_response = client.get(f"/projects/project-1/jobs/{job_id}/status")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "SUCCEEDED"

    event_types = [event.get("event_type") for event in spy_audit.recorded]
    assert "JOB_RUN_CREATED" in event_types
    assert "JOB_RUN_STARTED" in event_types
    assert "JOB_RUN_FINISHED" in event_types


def test_retry_lineage_and_cancel_guards(job_service_fixture) -> None:
    job_service, spy_audit, _ = job_service_fixture
    app.dependency_overrides[get_job_service] = lambda: job_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-reviewer",
        email="reviewer@local.ukde",
    )

    create_response = client.post(
        "/projects/project-1/jobs",
        json={"logical_key": "retry-flow", "mode": "FAIL_ONCE", "max_attempts": 1, "delay_ms": 0},
    )
    assert create_response.status_code == 201
    first_job_id = create_response.json()["job"]["id"]

    first_result = job_service.run_worker_once(worker_id="worker-2", lease_seconds=30)
    assert first_result is not None
    assert first_result.status == "FAILED"

    retry_response = client.post(f"/projects/project-1/jobs/{first_job_id}/retry")
    assert retry_response.status_code == 200
    retry_payload = retry_response.json()
    second_job_id = retry_payload["job"]["id"]
    assert retry_payload["job"]["attemptNumber"] == 2
    assert retry_payload["job"]["supersedesJobId"] == first_job_id

    second_result = job_service.run_worker_once(worker_id="worker-2", lease_seconds=30)
    assert second_result is not None
    assert second_result.id == second_job_id
    assert second_result.status == "SUCCEEDED"

    first_detail = client.get(f"/projects/project-1/jobs/{first_job_id}")
    second_detail = client.get(f"/projects/project-1/jobs/{second_job_id}")
    assert first_detail.status_code == 200
    assert second_detail.status_code == 200
    assert first_detail.json()["supersededByJobId"] == second_job_id
    assert second_detail.json()["supersedesJobId"] == first_job_id

    cancel_terminal = client.post(f"/projects/project-1/jobs/{second_job_id}/cancel")
    assert cancel_terminal.status_code == 409


def test_cancel_queued_job_prevents_execution(job_service_fixture) -> None:
    job_service, spy_audit, _ = job_service_fixture
    app.dependency_overrides[get_job_service] = lambda: job_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-lead",
        email="lead@local.ukde",
    )

    create_response = client.post(
        "/projects/project-1/jobs",
        json={"logical_key": "cancel-queued", "mode": "SUCCESS", "max_attempts": 1, "delay_ms": 0},
    )
    job_id = create_response.json()["job"]["id"]

    cancel_response = client.post(f"/projects/project-1/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["terminal"] is True
    assert cancel_response.json()["job"]["status"] == "CANCELED"

    claimed = job_service.claim_next_job_for_worker(worker_id="worker-3", lease_seconds=30)
    assert claimed is None
    assert client.get(f"/projects/project-1/jobs/{job_id}/status").json()["status"] == "CANCELED"
