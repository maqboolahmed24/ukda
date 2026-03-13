import time
from functools import lru_cache
from typing import Literal

from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.jobs.models import JobEventRecord, JobRecord, JobStatus
from app.jobs.store import (
    JobNotFoundError,
    JobRetryConflictError,
    JobStore,
    JobStoreUnavailableError,
    JobTransitionError,
)
from app.projects.service import (
    ProjectAccessDeniedError,
    ProjectService,
    get_project_service,
)
from app.telemetry.context import current_trace_id
from app.telemetry.service import TelemetryService, get_telemetry_service

NoopMode = Literal["SUCCESS", "FAIL_ONCE", "FAIL_ALWAYS"]
_READ_ROLES = {"PROJECT_LEAD", "RESEARCHER", "REVIEWER"}
_WRITE_ROLES = {"PROJECT_LEAD", "REVIEWER"}
_VALID_NOOP_MODES = {"SUCCESS", "FAIL_ONCE", "FAIL_ALWAYS"}


class JobValidationError(RuntimeError):
    """Job payload failed validation."""


def _normalize_logical_key(value: str) -> str:
    candidate = value.strip()
    if len(candidate) < 2:
        raise JobValidationError("logical_key must be at least 2 characters.")
    if len(candidate) > 120:
        raise JobValidationError("logical_key must be 120 characters or fewer.")
    return candidate


def _normalize_noop_mode(value: str) -> NoopMode:
    normalized = value.strip().upper()
    if normalized not in _VALID_NOOP_MODES:
        raise JobValidationError("mode must be SUCCESS, FAIL_ONCE, or FAIL_ALWAYS.")
    return normalized  # type: ignore[return-value]


def _normalize_delay_ms(value: int) -> int:
    if value < 0:
        raise JobValidationError("delay_ms must be zero or positive.")
    if value > 10_000:
        raise JobValidationError("delay_ms must be <= 10000.")
    return value


class JobService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: JobStore | None = None,
        project_service: ProjectService | None = None,
        audit_service: AuditService | None = None,
        telemetry_service: TelemetryService | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or JobStore(settings)
        self._project_service = project_service or get_project_service()
        self._audit_service = audit_service or get_audit_service()
        self._telemetry_service = telemetry_service or get_telemetry_service()

    @staticmethod
    def _is_admin(current_user: SessionPrincipal) -> bool:
        return "ADMIN" in set(current_user.platform_roles)

    def _authorize_project_scope(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        allowed_member_roles: set[str],
    ) -> None:
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if self._is_admin(current_user):
            return
        if not context.is_member:
            raise ProjectAccessDeniedError("Membership is required for this project route.")
        role = context.summary.current_user_role
        if role is None or role not in allowed_member_roles:
            raise ProjectAccessDeniedError("Current project role cannot access this job route.")

    def _refresh_queue_depth(self) -> None:
        queue_depth = self._store.count_open_jobs()
        self._telemetry_service.record_queue_depth(
            queue_depth=queue_depth,
            source="jobs-store",
            detail="Queue depth from unsuperseded QUEUED jobs.",
        )

    def list_jobs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        cursor: int,
        page_size: int,
    ) -> tuple[list[JobRecord], int | None]:
        self._authorize_project_scope(
            current_user=current_user,
            project_id=project_id,
            allowed_member_roles=_READ_ROLES,
        )
        return self._store.list_project_jobs(
            project_id=project_id,
            cursor=cursor,
            page_size=page_size,
        )

    def get_job(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        job_id: str,
    ) -> JobRecord:
        self._authorize_project_scope(
            current_user=current_user,
            project_id=project_id,
            allowed_member_roles=_READ_ROLES,
        )
        return self._store.get_job(project_id=project_id, job_id=job_id)

    def get_job_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        job_id: str,
    ) -> JobRecord:
        self._authorize_project_scope(
            current_user=current_user,
            project_id=project_id,
            allowed_member_roles=_READ_ROLES,
        )
        return self._store.get_job_status(project_id=project_id, job_id=job_id)

    def list_job_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        job_id: str,
        cursor: int,
        page_size: int,
    ) -> tuple[list[JobEventRecord], int | None]:
        self._authorize_project_scope(
            current_user=current_user,
            project_id=project_id,
            allowed_member_roles=_READ_ROLES,
        )
        return self._store.list_job_events(
            project_id=project_id,
            job_id=job_id,
            cursor=cursor,
            page_size=page_size,
        )

    def enqueue_noop(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        logical_key: str,
        mode: str,
        max_attempts: int,
        delay_ms: int,
        request_context: AuditRequestContext,
    ) -> tuple[JobRecord, bool, str]:
        self._authorize_project_scope(
            current_user=current_user,
            project_id=project_id,
            allowed_member_roles=_WRITE_ROLES,
        )
        normalized_logical_key = _normalize_logical_key(logical_key)
        normalized_mode = _normalize_noop_mode(mode)
        normalized_delay_ms = _normalize_delay_ms(delay_ms)
        if max_attempts < 1 or max_attempts > 10:
            raise JobValidationError("max_attempts must be between 1 and 10.")

        dedupe_key = self._store.compute_dedupe_key(
            project_id=project_id,
            job_type="NOOP",
            logical_key=normalized_logical_key,
        )
        payload_json = {
            "logical_key": normalized_logical_key,
            "mode": normalized_mode,
            "delay_ms": normalized_delay_ms,
        }

        row, created, reason = self._store.enqueue_job(
            project_id=project_id,
            job_type="NOOP",
            dedupe_key=dedupe_key,
            payload_json=payload_json,
            created_by=current_user.user_id,
            max_attempts=max_attempts,
            event_type="JOB_CREATED",
        )
        self._refresh_queue_depth()
        if created:
            self._audit_service.record_event_best_effort(
                event_type="JOB_RUN_CREATED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                object_type="job",
                object_id=row.id,
                metadata={
                    "job_type": row.type,
                    "status": row.status,
                    "attempt_number": row.attempt_number,
                },
                request_context=request_context,
            )
        return row, created, reason

    def retry_job(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        job_id: str,
        request_context: AuditRequestContext,
    ) -> tuple[JobRecord, bool, str]:
        self._authorize_project_scope(
            current_user=current_user,
            project_id=project_id,
            allowed_member_roles=_WRITE_ROLES,
        )
        row, created, reason = self._store.append_retry(
            project_id=project_id,
            job_id=job_id,
            actor_user_id=current_user.user_id,
        )
        self._refresh_queue_depth()
        if created:
            self._audit_service.record_event_best_effort(
                event_type="JOB_RUN_CREATED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                object_type="job",
                object_id=row.id,
                metadata={
                    "job_type": row.type,
                    "status": row.status,
                    "attempt_number": row.attempt_number,
                    "retry_of_job_id": job_id,
                },
                request_context=request_context,
            )
        return row, created, reason

    def cancel_job(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        job_id: str,
        request_context: AuditRequestContext,
    ) -> tuple[JobRecord, bool]:
        self._authorize_project_scope(
            current_user=current_user,
            project_id=project_id,
            allowed_member_roles=_WRITE_ROLES,
        )
        row, terminal = self._store.cancel_job(
            project_id=project_id,
            job_id=job_id,
            actor_user_id=current_user.user_id,
        )
        self._refresh_queue_depth()
        if terminal:
            self._audit_service.record_event_best_effort(
                event_type="JOB_RUN_CANCELED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                object_type="job",
                object_id=row.id,
                metadata={"status": row.status, "mode": "queued_direct"},
                request_context=request_context,
            )
        return row, terminal

    def claim_next_job_for_worker(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
    ) -> JobRecord | None:
        row = self._store.claim_next_job(worker_id=worker_id, lease_seconds=lease_seconds)
        self._refresh_queue_depth()
        if row is None:
            return None
        self._audit_service.record_event_best_effort(
            event_type="JOB_RUN_STARTED",
            actor_user_id=None,
            project_id=row.project_id,
            object_type="job",
            object_id=row.id,
            metadata={
                "job_type": row.type,
                "status": row.status,
                "attempt_number": row.attempt_number,
                "worker_id": worker_id,
            },
            request_id=f"worker:{worker_id}:{row.id}",
        )
        self._telemetry_service.record_timeline(
            scope="worker",
            severity="INFO",
            message="Worker claimed a queued job.",
            request_id=None,
            trace_id=current_trace_id(),
            details={"job_id": row.id, "project_id": row.project_id, "worker_id": worker_id},
        )
        return row

    def heartbeat_running_job(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_seconds: int,
    ) -> bool:
        return self._store.heartbeat_job(
            job_id=job_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )

    def finish_running_job(
        self,
        *,
        job_id: str,
        worker_id: str,
        success: bool,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> JobRecord:
        row = self._store.finish_running_job(
            job_id=job_id,
            worker_id=worker_id,
            success=success,
            error_code=error_code,
            error_message=error_message,
        )
        self._refresh_queue_depth()

        if row.status == "SUCCEEDED":
            self._audit_service.record_event_best_effort(
                event_type="JOB_RUN_FINISHED",
                actor_user_id=None,
                project_id=row.project_id,
                object_type="job",
                object_id=row.id,
                metadata={
                    "job_type": row.type,
                    "status": row.status,
                    "worker_id": worker_id,
                },
                request_id=f"worker:{worker_id}:{row.id}",
            )
            return row

        if row.status == "CANCELED":
            self._audit_service.record_event_best_effort(
                event_type="JOB_RUN_CANCELED",
                actor_user_id=row.canceled_by,
                project_id=row.project_id,
                object_type="job",
                object_id=row.id,
                metadata={
                    "job_type": row.type,
                    "status": row.status,
                    "worker_id": worker_id,
                },
                request_id=f"worker:{worker_id}:{row.id}",
            )
            return row

        if row.status in {"FAILED", "QUEUED"}:
            self._audit_service.record_event_best_effort(
                event_type="JOB_RUN_FAILED",
                actor_user_id=None,
                project_id=row.project_id,
                object_type="job",
                object_id=row.id,
                metadata={
                    "job_type": row.type,
                    "status": row.status,
                    "worker_id": worker_id,
                    "attempts": row.attempts,
                    "max_attempts": row.max_attempts,
                },
                request_id=f"worker:{worker_id}:{row.id}",
            )
            return row

        return row

    def process_claimed_job(
        self,
        *,
        worker_id: str,
        row: JobRecord,
    ) -> JobRecord:
        if row.type != "NOOP":
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="UNSUPPORTED_JOB_TYPE",
                error_message=f"Unsupported job type '{row.type}'.",
            )

        payload = row.payload_json
        raw_mode = payload.get("mode")
        mode = "SUCCESS" if not isinstance(raw_mode, str) else raw_mode
        normalized_mode = _normalize_noop_mode(mode)

        raw_delay = payload.get("delay_ms")
        delay_ms = 0 if not isinstance(raw_delay, int) else _normalize_delay_ms(raw_delay)

        if delay_ms:
            time.sleep(delay_ms / 1000)

        if normalized_mode == "FAIL_ALWAYS":
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="NOOP_CONFIGURED_FAILURE",
                error_message="NOOP job is configured to fail for deterministic validation.",
            )

        if normalized_mode == "FAIL_ONCE" and row.attempt_number == 1:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="NOOP_FAIL_ONCE",
                error_message="NOOP job is configured to fail on the first attempt row.",
            )

        return self.finish_running_job(
            job_id=row.id,
            worker_id=worker_id,
            success=True,
        )

    def run_worker_once(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
    ) -> JobRecord | None:
        claimed = self.claim_next_job_for_worker(
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        if claimed is None:
            return None
        self.heartbeat_running_job(
            job_id=claimed.id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        return self.process_claimed_job(worker_id=worker_id, row=claimed)

    def get_project_job_activity(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> tuple[int, JobStatus | None]:
        self._authorize_project_scope(
            current_user=current_user,
            project_id=project_id,
            allowed_member_roles=_READ_ROLES,
        )
        return self._store.project_job_activity(project_id=project_id)

    def queue_depth(self) -> int:
        return self._store.count_open_jobs()


@lru_cache
def get_job_service() -> JobService:
    return JobService(settings=get_settings())


__all__ = [
    "JobNotFoundError",
    "JobRetryConflictError",
    "JobService",
    "JobStoreUnavailableError",
    "JobTransitionError",
    "JobValidationError",
    "get_job_service",
]
