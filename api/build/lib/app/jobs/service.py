import hashlib
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
_VALID_INGEST_DOCUMENT_JOB_TYPES = {"EXTRACT_PAGES", "RENDER_THUMBNAILS"}


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

    def enqueue_document_processing_job(
        self,
        *,
        project_id: str,
        document_id: str,
        job_type: Literal["EXTRACT_PAGES", "RENDER_THUMBNAILS"],
        created_by: str,
        processing_run_id: str | None = None,
    ) -> tuple[JobRecord, bool, str]:
        dedupe_key = self._store.compute_dedupe_key(
            project_id=project_id,
            job_type=job_type,
            logical_key=f"document:{document_id}",
        )
        payload_json = {
            "project_id": project_id,
            "document_id": document_id,
        }
        if isinstance(processing_run_id, str) and processing_run_id.strip():
            payload_json["processing_run_id"] = processing_run_id.strip()
        row, created, reason = self._store.enqueue_job(
            project_id=project_id,
            job_type=job_type,
            dedupe_key=dedupe_key,
            payload_json=payload_json,
            created_by=created_by,
            max_attempts=1,
            event_type="JOB_CREATED",
        )
        self._refresh_queue_depth()
        return row, created, reason

    def enqueue_preprocess_document_job(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        created_by: str,
    ) -> tuple[JobRecord, bool, str]:
        dedupe_key = self._store.compute_dedupe_key(
            project_id=project_id,
            job_type="PREPROCESS_DOCUMENT",
            logical_key=f"document:{document_id}|run:{run_id}",
        )
        row, created, reason = self._store.enqueue_job(
            project_id=project_id,
            job_type="PREPROCESS_DOCUMENT",
            dedupe_key=dedupe_key,
            payload_json={
                "project_id": project_id,
                "document_id": document_id,
                "run_id": run_id,
            },
            created_by=created_by,
            max_attempts=1,
            event_type="JOB_CREATED",
        )
        self._refresh_queue_depth()
        return row, created, reason

    def _enqueue_preprocess_page_job(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        page_index: int,
        created_by: str,
    ) -> tuple[JobRecord, bool, str]:
        dedupe_key = self._store.compute_dedupe_key(
            project_id=project_id,
            job_type="PREPROCESS_PAGE",
            logical_key=f"run:{run_id}|page:{page_id}",
        )
        row, created, reason = self._store.enqueue_job(
            project_id=project_id,
            job_type="PREPROCESS_PAGE",
            dedupe_key=dedupe_key,
            payload_json={
                "project_id": project_id,
                "document_id": document_id,
                "run_id": run_id,
                "page_id": page_id,
                "page_index": page_index,
            },
            created_by=created_by,
            max_attempts=2,
            event_type="JOB_CREATED",
        )
        self._refresh_queue_depth()
        return row, created, reason

    def _enqueue_preprocess_finalize_job(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        created_by: str,
    ) -> tuple[JobRecord, bool, str]:
        dedupe_key = self._store.compute_dedupe_key(
            project_id=project_id,
            job_type="FINALIZE_PREPROCESS_RUN",
            logical_key=f"run:{run_id}",
        )
        row, created, reason = self._store.enqueue_job(
            project_id=project_id,
            job_type="FINALIZE_PREPROCESS_RUN",
            dedupe_key=dedupe_key,
            payload_json={
                "project_id": project_id,
                "document_id": document_id,
                "run_id": run_id,
            },
            created_by=created_by,
            max_attempts=1,
            event_type="JOB_CREATED",
        )
        self._refresh_queue_depth()
        return row, created, reason

    def enqueue_layout_document_job(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        created_by: str,
    ) -> tuple[JobRecord, bool, str]:
        dedupe_key = self._store.compute_dedupe_key(
            project_id=project_id,
            job_type="LAYOUT_ANALYZE_DOCUMENT",
            logical_key=f"document:{document_id}|run:{run_id}",
        )
        row, created, reason = self._store.enqueue_job(
            project_id=project_id,
            job_type="LAYOUT_ANALYZE_DOCUMENT",
            dedupe_key=dedupe_key,
            payload_json={
                "project_id": project_id,
                "document_id": document_id,
                "run_id": run_id,
            },
            created_by=created_by,
            max_attempts=1,
            event_type="JOB_CREATED",
        )
        self._refresh_queue_depth()
        return row, created, reason

    def _enqueue_layout_page_job(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        page_index: int,
        created_by: str,
    ) -> tuple[JobRecord, bool, str]:
        dedupe_key = self._store.compute_dedupe_key(
            project_id=project_id,
            job_type="LAYOUT_ANALYZE_PAGE",
            logical_key=f"run:{run_id}|page:{page_id}",
        )
        row, created, reason = self._store.enqueue_job(
            project_id=project_id,
            job_type="LAYOUT_ANALYZE_PAGE",
            dedupe_key=dedupe_key,
            payload_json={
                "project_id": project_id,
                "document_id": document_id,
                "run_id": run_id,
                "page_id": page_id,
                "page_index": page_index,
            },
            created_by=created_by,
            max_attempts=2,
            event_type="JOB_CREATED",
        )
        self._refresh_queue_depth()
        return row, created, reason

    def _enqueue_layout_finalize_job(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        created_by: str,
    ) -> tuple[JobRecord, bool, str]:
        dedupe_key = self._store.compute_dedupe_key(
            project_id=project_id,
            job_type="FINALIZE_LAYOUT_RUN",
            logical_key=f"run:{run_id}",
        )
        row, created, reason = self._store.enqueue_job(
            project_id=project_id,
            job_type="FINALIZE_LAYOUT_RUN",
            dedupe_key=dedupe_key,
            payload_json={
                "project_id": project_id,
                "document_id": document_id,
                "run_id": run_id,
            },
            created_by=created_by,
            max_attempts=1,
            event_type="JOB_CREATED",
        )
        self._refresh_queue_depth()
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
        if row.type in _VALID_INGEST_DOCUMENT_JOB_TYPES:
            return self._process_document_job(worker_id=worker_id, row=row)
        if row.type == "PREPROCESS_DOCUMENT":
            return self._process_preprocess_document_job(worker_id=worker_id, row=row)
        if row.type == "PREPROCESS_PAGE":
            return self._process_preprocess_page_job(worker_id=worker_id, row=row)
        if row.type == "FINALIZE_PREPROCESS_RUN":
            return self._process_finalize_preprocess_run_job(worker_id=worker_id, row=row)
        if row.type == "LAYOUT_ANALYZE_DOCUMENT":
            return self._process_layout_document_job(worker_id=worker_id, row=row)
        if row.type == "LAYOUT_ANALYZE_PAGE":
            return self._process_layout_page_job(worker_id=worker_id, row=row)
        if row.type == "FINALIZE_LAYOUT_RUN":
            return self._process_finalize_layout_run_job(worker_id=worker_id, row=row)

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

    @staticmethod
    def _resolve_document_job_payload(row: JobRecord) -> tuple[str, str]:
        payload = row.payload_json
        project_id = payload.get("project_id")
        document_id = payload.get("document_id")
        if not isinstance(project_id, str) or not isinstance(document_id, str):
            raise JobValidationError("Document job payload requires project_id and document_id.")
        return project_id, document_id

    def _process_document_job(self, *, worker_id: str, row: JobRecord) -> JobRecord:
        from app.documents.service import get_document_service

        project_id: str
        document_id: str
        try:
            project_id, document_id = self._resolve_document_job_payload(row)
        except JobValidationError as error:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="INVALID_DOCUMENT_JOB_PAYLOAD",
                error_message=str(error),
            )

        document_service = get_document_service()
        run_kind = "EXTRACTION" if row.type == "EXTRACT_PAGES" else "THUMBNAIL_RENDER"
        emit_extraction_audit = row.type == "EXTRACT_PAGES"
        payload = row.payload_json
        processing_run_id = payload.get("processing_run_id")
        try:
            if isinstance(processing_run_id, str) and processing_run_id.strip():
                existing_run = document_service._store.get_processing_run(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=processing_run_id.strip(),
                )
                if existing_run is None:
                    raise JobValidationError(
                        "Document job payload references an unknown processing_run_id."
                    )
                if existing_run.run_kind != run_kind:
                    raise JobValidationError(
                        "Document job payload processing_run_id has a mismatched run_kind."
                    )
                if existing_run.status in {"SUCCEEDED", "FAILED", "CANCELED"}:
                    raise JobValidationError(
                        "Document job payload processing_run_id is already terminal."
                    )
                run = document_service._store.transition_processing_run(
                    project_id=project_id,
                    run_id=existing_run.id,
                    status="RUNNING",
                )
            else:
                run = document_service._store.create_processing_run(
                    project_id=project_id,
                    document_id=document_id,
                    run_kind=run_kind,
                    created_by=row.created_by,
                    status="RUNNING",
                )
        except JobValidationError as error:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="INVALID_DOCUMENT_JOB_PAYLOAD",
                error_message=str(error),
            )

        if emit_extraction_audit:
            self._audit_service.record_event_best_effort(
                event_type="DOCUMENT_PAGE_EXTRACTION_STARTED",
                actor_user_id=row.created_by,
                project_id=project_id,
                object_type="document",
                object_id=document_id,
                metadata={
                    "document_id": document_id,
                    "run_kind": run.run_kind,
                    "run_id": run.id,
                },
                request_id=f"worker:{worker_id}:{row.id}",
            )

        try:
            if row.type == "EXTRACT_PAGES":
                page_count = document_service.run_extraction_job(
                    project_id=project_id,
                    document_id=document_id,
                    created_by=row.created_by,
                )
                document_service._store.transition_processing_run(
                    project_id=project_id,
                    run_id=run.id,
                    status="SUCCEEDED",
                )
                self.enqueue_document_processing_job(
                    project_id=project_id,
                    document_id=document_id,
                    job_type="RENDER_THUMBNAILS",
                    created_by=row.created_by,
                )
                if emit_extraction_audit:
                    self._audit_service.record_event_best_effort(
                        event_type="DOCUMENT_PAGE_EXTRACTION_COMPLETED",
                        actor_user_id=row.created_by,
                        project_id=project_id,
                        object_type="document",
                        object_id=document_id,
                        metadata={
                            "document_id": document_id,
                            "run_kind": run.run_kind,
                            "run_id": run.id,
                            "page_count": page_count,
                        },
                        request_id=f"worker:{worker_id}:{row.id}",
                    )
            else:
                document_service.run_thumbnail_job(
                    project_id=project_id,
                    document_id=document_id,
                )
                document_service._store.transition_processing_run(
                    project_id=project_id,
                    run_id=run.id,
                    status="SUCCEEDED",
                )
        except Exception as error:  # noqa: BLE001
            document_service._store.transition_processing_run(
                project_id=project_id,
                run_id=run.id,
                status="FAILED",
                failure_reason=str(error),
            )
            document_service._store.set_document_status(
                project_id=project_id,
                document_id=document_id,
                status="FAILED",
            )
            if emit_extraction_audit:
                self._audit_service.record_event_best_effort(
                    event_type="DOCUMENT_PAGE_EXTRACTION_FAILED",
                    actor_user_id=row.created_by,
                    project_id=project_id,
                    object_type="document",
                    object_id=document_id,
                    metadata={
                        "document_id": document_id,
                        "run_kind": run.run_kind,
                        "run_id": run.id,
                        "reason": str(error),
                    },
                    request_id=f"worker:{worker_id}:{row.id}",
                )
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="DOCUMENT_PROCESSING_FAILED",
                error_message=str(error),
            )

        return self.finish_running_job(
            job_id=row.id,
            worker_id=worker_id,
            success=True,
        )

    @staticmethod
    def _resolve_preprocess_job_payload(
        row: JobRecord,
        *,
        require_page_id: bool = False,
    ) -> tuple[str, str, str, str | None]:
        payload = row.payload_json
        project_id = payload.get("project_id")
        document_id = payload.get("document_id")
        run_id = payload.get("run_id")
        page_id = payload.get("page_id")
        if (
            not isinstance(project_id, str)
            or not isinstance(document_id, str)
            or not isinstance(run_id, str)
        ):
            raise JobValidationError(
                "Preprocess job payload requires project_id, document_id, and run_id."
            )
        if require_page_id and not isinstance(page_id, str):
            raise JobValidationError("PREPROCESS_PAGE payload requires page_id.")
        return project_id, document_id, run_id, page_id if isinstance(page_id, str) else None

    @staticmethod
    def _resolve_layout_job_payload(
        row: JobRecord,
        *,
        require_page_id: bool = False,
    ) -> tuple[str, str, str, str | None]:
        payload = row.payload_json
        project_id = payload.get("project_id")
        document_id = payload.get("document_id")
        run_id = payload.get("run_id")
        page_id = payload.get("page_id")
        if (
            not isinstance(project_id, str)
            or not isinstance(document_id, str)
            or not isinstance(run_id, str)
        ):
            raise JobValidationError(
                "Layout job payload requires project_id, document_id, and run_id."
            )
        if require_page_id and not isinstance(page_id, str):
            raise JobValidationError("LAYOUT_ANALYZE_PAGE payload requires page_id.")
        return project_id, document_id, run_id, page_id if isinstance(page_id, str) else None

    @staticmethod
    def _resolve_bleed_pair_page_index(page_index: int) -> int | None:
        if page_index < 0:
            return None
        if page_index % 2 == 0:
            return page_index + 1
        return page_index - 1

    def _resolve_bleed_pair_payload(
        self,
        *,
        project_id: str,
        document_id: str,
        page_index: int,
    ) -> bytes | None:
        from app.documents.service import get_document_service

        document_service = get_document_service()
        candidate_index = self._resolve_bleed_pair_page_index(page_index)
        if candidate_index is None:
            return None
        document_pages = document_service._store.list_document_pages(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
        )
        pair_page = next(
            (page for page in document_pages if page.page_index == candidate_index),
            None,
        )
        if pair_page is None or pair_page.status != "READY" or not pair_page.derived_image_key:
            return None
        try:
            return document_service._storage.read_object_bytes(pair_page.derived_image_key)  # noqa: SLF001
        except Exception:  # noqa: BLE001
            return None

    def _process_preprocess_document_job(self, *, worker_id: str, row: JobRecord) -> JobRecord:
        from app.documents.service import get_document_service

        try:
            project_id, document_id, run_id, _ = self._resolve_preprocess_job_payload(row)
        except JobValidationError as error:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="INVALID_PREPROCESS_JOB_PAYLOAD",
                error_message=str(error),
            )

        document_service = get_document_service()
        run = document_service._store.get_preprocess_run(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="PREPROCESS_RUN_NOT_FOUND",
                error_message="Target preprocess run was not found.",
            )
        if run.status in {"SUCCEEDED", "FAILED", "CANCELED"}:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=True,
            )

        try:
            started_run = document_service._store.mark_preprocess_run_running(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except Exception as error:  # noqa: BLE001
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="PREPROCESS_RUN_START_FAILED",
                error_message=str(error),
            )

        self._audit_service.record_event_best_effort(
            event_type="PREPROCESS_RUN_STARTED",
            actor_user_id=started_run.created_by,
            project_id=project_id,
            object_type="preprocess_run",
            object_id=run_id,
            metadata={
                "run_id": run_id,
                "document_id": document_id,
                "pipeline_version": started_run.pipeline_version,
            },
            request_id=f"worker:{worker_id}:{row.id}",
        )

        if started_run.status == "CANCELED":
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=True,
            )

        try:
            page_cursor = 0
            while True:
                current_run = document_service._store.get_preprocess_run(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                )
                if current_run is None or current_run.status == "CANCELED":
                    break
                page_rows, next_cursor = document_service._store.list_preprocess_page_results(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    cursor=page_cursor,
                    page_size=200,
                )
                for page_row in page_rows:
                    if page_row.status in {"SUCCEEDED", "FAILED", "CANCELED"}:
                        continue
                    current_run = document_service._store.get_preprocess_run(  # noqa: SLF001
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    if current_run is None or current_run.status == "CANCELED":
                        break
                    self._enqueue_preprocess_page_job(
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                        page_id=page_row.page_id,
                        page_index=page_row.page_index,
                        created_by=row.created_by,
                    )
                if next_cursor is None:
                    break
                page_cursor = next_cursor
            self._enqueue_preprocess_finalize_job(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                created_by=row.created_by,
            )
        except Exception as error:  # noqa: BLE001
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="PREPROCESS_DOCUMENT_ORCHESTRATION_FAILED",
                error_message=str(error),
            )

        return self.finish_running_job(
            job_id=row.id,
            worker_id=worker_id,
            success=True,
        )

    def _process_preprocess_page_job(self, *, worker_id: str, row: JobRecord) -> JobRecord:
        from app.documents.preprocessing import process_preprocess_page_bytes
        from app.documents.service import get_document_service

        try:
            project_id, document_id, run_id, page_id = self._resolve_preprocess_job_payload(
                row,
                require_page_id=True,
            )
            assert page_id is not None
        except JobValidationError as error:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="INVALID_PREPROCESS_JOB_PAYLOAD",
                error_message=str(error),
            )

        document_service = get_document_service()
        run = document_service._store.get_preprocess_run(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="PREPROCESS_RUN_NOT_FOUND",
                error_message="Target preprocess run was not found.",
            )
        if run.status in {"FAILED", "CANCELED", "SUCCEEDED"}:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=True,
            )

        try:
            document_service._store.mark_preprocess_run_running(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            page_row = document_service._store.mark_preprocess_page_running(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
            )
        except Exception as error:  # noqa: BLE001
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="PREPROCESS_PAGE_TRANSITION_FAILED",
                error_message=str(error),
            )

        if page_row.status in {"SUCCEEDED", "CANCELED"}:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=True,
            )

        page = document_service._store.get_document_page(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        if page is None:
            try:
                document_service._store.fail_preprocess_page_result(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_id=page_id,
                    failure_reason="Page metadata record not found.",
                )
            except Exception:  # noqa: BLE001
                pass
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="PREPROCESS_PAGE_NOT_FOUND",
                error_message="Page metadata record not found.",
            )
        input_key = page_row.input_object_key
        if not isinstance(input_key, str) or not input_key.strip():
            try:
                document_service._store.fail_preprocess_page_result(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_id=page_id,
                    failure_reason="Input page object key is missing.",
                )
            except Exception:  # noqa: BLE001
                pass
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="PREPROCESS_INPUT_MISSING",
                error_message="Input page object key is missing.",
            )

        try:
            bleed_mode = (
                str(run.params_json.get("bleed_through_mode", "OFF")).strip().upper()
            )
            pair_payload: bytes | None = None
            if bleed_mode in {"PAIRED_PREFERRED", "SINGLE_FALLBACK"}:
                pair_payload = self._resolve_bleed_pair_payload(
                    project_id=project_id,
                    document_id=document_id,
                    page_index=page.page_index,
                )
            source_payload = document_service._storage.read_object_bytes(input_key)  # noqa: SLF001
            outcome = process_preprocess_page_bytes(
                source_payload=source_payload,
                source_dpi=page.source_dpi if page.source_dpi is not None else page.dpi,
                source_width=page.source_width if page.source_width > 0 else page.width,
                source_height=page.source_height if page.source_height > 0 else page.height,
                params_json=run.params_json,
                paired_source_payload=pair_payload,
            )
            gray_object = document_service._storage.write_preprocess_gray_image(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_index=page.page_index,
                payload=outcome.gray_png_bytes,
            )
            bin_object_key: str | None = None
            if outcome.bin_png_bytes is not None:
                bin_object = document_service._storage.write_preprocess_bin_image(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_index=page.page_index,
                    payload=outcome.bin_png_bytes,
                )
                bin_object_key = bin_object.object_key
            metrics_object = document_service._storage.write_preprocess_page_metrics(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_index=page.page_index,
                metrics_json=outcome.metrics_json,
            )
            metrics_sha256 = hashlib.sha256(metrics_object.absolute_path.read_bytes()).hexdigest()
            document_service._store.complete_preprocess_page_result(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                output_object_key_gray=gray_object.object_key,
                output_object_key_bin=bin_object_key,
                metrics_object_key=metrics_object.object_key,
                metrics_sha256=metrics_sha256,
                metrics_json=outcome.metrics_json,
                sha256_gray=outcome.sha256_gray,
                sha256_bin=outcome.sha256_bin,
                warnings_json=outcome.warnings_json,
                quality_gate_status=outcome.quality_gate_status,
            )
        except Exception as error:  # noqa: BLE001
            try:
                document_service._store.fail_preprocess_page_result(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_id=page_id,
                    failure_reason=str(error),
                )
            except Exception:  # noqa: BLE001
                pass
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="PREPROCESS_PAGE_FAILED",
                error_message=str(error),
            )

        return self.finish_running_job(
            job_id=row.id,
            worker_id=worker_id,
            success=True,
        )

    def _process_finalize_preprocess_run_job(self, *, worker_id: str, row: JobRecord) -> JobRecord:
        from app.documents.preprocessing import build_preprocess_manifest
        from app.documents.service import get_document_service

        try:
            project_id, document_id, run_id, _ = self._resolve_preprocess_job_payload(row)
        except JobValidationError as error:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="INVALID_PREPROCESS_JOB_PAYLOAD",
                error_message=str(error),
            )

        document_service = get_document_service()
        try:
            finalized_run = document_service._store.finalize_preprocess_run(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            page_rows: list[dict[str, object]] = []
            page_cursor = 0
            while True:
                batch, next_cursor = document_service._store.list_preprocess_page_results(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    cursor=page_cursor,
                    page_size=200,
                )
                for item in batch:
                    page_rows.append(
                        {
                            "pageId": item.page_id,
                            "pageIndex": item.page_index,
                            "status": item.status,
                            "qualityGateStatus": item.quality_gate_status,
                            "inputObjectKey": item.input_object_key,
                            "inputSha256": item.input_sha256,
                            "sourceResultRunId": item.source_result_run_id or item.run_id,
                            "outputObjectKeyGray": item.output_object_key_gray,
                            "outputObjectKeyBin": item.output_object_key_bin,
                            "sha256Gray": item.sha256_gray,
                            "sha256Bin": item.sha256_bin,
                            "metricsObjectKey": item.metrics_object_key,
                            "metricsSha256": item.metrics_sha256,
                            "warnings": item.warnings_json,
                            "metrics": item.metrics_json,
                            "failureReason": item.failure_reason,
                        }
                    )
                if next_cursor is None:
                    break
                page_cursor = next_cursor

            manifest_payload = build_preprocess_manifest(
                run_id=finalized_run.id,
                project_id=project_id,
                document_id=document_id,
                profile_id=finalized_run.profile_id,
                profile_version=finalized_run.profile_version,
                profile_revision=finalized_run.profile_revision,
                profile_params_hash=finalized_run.profile_params_hash,
                params_json=finalized_run.params_json,
                params_hash=finalized_run.params_hash,
                pipeline_version=finalized_run.pipeline_version,
                container_digest=finalized_run.container_digest,
                source_page_count=len(page_rows),
                manifest_generated_at=(
                    finalized_run.finished_at
                    or finalized_run.started_at
                    or finalized_run.created_at
                ),
                items=page_rows,
            )
            manifest_object = document_service._storage.write_preprocess_manifest(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                payload=manifest_payload,
            )
            manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
            document_service._store.record_preprocess_run_manifest(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                manifest_object_key=manifest_object.object_key,
                manifest_sha256=manifest_sha256,
                manifest_schema_version=2,
            )
        except Exception as error:  # noqa: BLE001
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="PREPROCESS_FINALIZE_FAILED",
                error_message=str(error),
            )

        if finalized_run.status == "SUCCEEDED":
            self._audit_service.record_event_best_effort(
                event_type="PREPROCESS_RUN_FINISHED",
                actor_user_id=finalized_run.created_by,
                project_id=project_id,
                object_type="preprocess_run",
                object_id=run_id,
                metadata={
                    "run_id": run_id,
                    "document_id": document_id,
                    "status": finalized_run.status,
                },
                request_id=f"worker:{worker_id}:{row.id}",
            )
        elif finalized_run.status == "FAILED":
            self._audit_service.record_event_best_effort(
                event_type="PREPROCESS_RUN_FAILED",
                actor_user_id=finalized_run.created_by,
                project_id=project_id,
                object_type="preprocess_run",
                object_id=run_id,
                metadata={
                    "run_id": run_id,
                    "document_id": document_id,
                    "reason": finalized_run.failure_reason or "Preprocess run failed.",
                },
                request_id=f"worker:{worker_id}:{row.id}",
            )
        elif finalized_run.status == "CANCELED":
            self._audit_service.record_event_best_effort(
                event_type="PREPROCESS_RUN_CANCELED",
                actor_user_id=finalized_run.created_by,
                project_id=project_id,
                object_type="preprocess_run",
                object_id=run_id,
                metadata={"run_id": run_id, "document_id": document_id},
                request_id=f"worker:{worker_id}:{row.id}",
            )

        return self.finish_running_job(
            job_id=row.id,
            worker_id=worker_id,
            success=True,
        )

    def _process_layout_document_job(self, *, worker_id: str, row: JobRecord) -> JobRecord:
        from app.documents.service import get_document_service

        try:
            project_id, document_id, run_id, _ = self._resolve_layout_job_payload(row)
        except JobValidationError as error:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="INVALID_LAYOUT_JOB_PAYLOAD",
                error_message=str(error),
            )

        document_service = get_document_service()
        run = document_service._store.get_layout_run(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="LAYOUT_RUN_NOT_FOUND",
                error_message="Target layout run was not found.",
            )
        if run.status in {"SUCCEEDED", "FAILED", "CANCELED"}:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=True,
            )

        try:
            started_run = document_service._store.mark_layout_run_running(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except Exception as error:  # noqa: BLE001
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="LAYOUT_RUN_START_FAILED",
                error_message=str(error),
            )

        self._audit_service.record_event_best_effort(
            event_type="LAYOUT_RUN_STARTED",
            actor_user_id=started_run.created_by,
            project_id=project_id,
            object_type="layout_run",
            object_id=run_id,
            metadata={
                "run_id": run_id,
                "document_id": document_id,
                "pipeline_version": started_run.pipeline_version,
            },
            request_id=f"worker:{worker_id}:{row.id}",
        )

        if started_run.status == "CANCELED":
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=True,
            )

        try:
            page_cursor = 0
            while True:
                current_run = document_service._store.get_layout_run(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                )
                if current_run is None or current_run.status == "CANCELED":
                    break

                page_rows, next_cursor = document_service._store.list_page_layout_results(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    cursor=page_cursor,
                    page_size=200,
                )
                for page_row in page_rows:
                    if page_row.status in {"SUCCEEDED", "FAILED", "CANCELED"}:
                        continue
                    current_run = document_service._store.get_layout_run(  # noqa: SLF001
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    if current_run is None or current_run.status == "CANCELED":
                        break
                    self._enqueue_layout_page_job(
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                        page_id=page_row.page_id,
                        page_index=page_row.page_index,
                        created_by=row.created_by,
                    )

                if next_cursor is None:
                    break
                page_cursor = next_cursor

            self._enqueue_layout_finalize_job(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                created_by=row.created_by,
            )
        except Exception as error:  # noqa: BLE001
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="LAYOUT_DOCUMENT_ORCHESTRATION_FAILED",
                error_message=str(error),
            )

        return self.finish_running_job(
            job_id=row.id,
            worker_id=worker_id,
            success=True,
        )

    def _process_layout_page_job(self, *, worker_id: str, row: JobRecord) -> JobRecord:
        from app.documents.layout_segmentation import (
            LayoutSegmentationError,
            segment_layout_page_bytes,
        )
        from app.documents.service import get_document_service

        try:
            project_id, document_id, run_id, page_id = self._resolve_layout_job_payload(
                row,
                require_page_id=True,
            )
            assert page_id is not None
        except JobValidationError as error:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="INVALID_LAYOUT_JOB_PAYLOAD",
                error_message=str(error),
            )

        document_service = get_document_service()
        run = document_service._store.get_layout_run(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="LAYOUT_RUN_NOT_FOUND",
                error_message="Target layout run was not found.",
            )
        if run.status in {"FAILED", "CANCELED", "SUCCEEDED"}:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=True,
            )

        try:
            document_service._store.mark_layout_run_running(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            page_row = document_service._store.mark_layout_page_running(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
            )
        except Exception as error:  # noqa: BLE001
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="LAYOUT_PAGE_TRANSITION_FAILED",
                error_message=str(error),
            )

        if page_row.status in {"SUCCEEDED", "CANCELED"}:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=True,
            )

        current_run = document_service._store.get_layout_run(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if current_run is None or current_run.status == "CANCELED":
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=True,
            )

        page = document_service._store.get_document_page(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        if page is None:
            try:
                document_service._store.fail_layout_page_result(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_id=page_id,
                    failure_reason="Page metadata record not found.",
                )
            except Exception:  # noqa: BLE001
                pass
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="LAYOUT_PAGE_NOT_FOUND",
                error_message="Page metadata record not found.",
            )

        preprocess_result = document_service._store.get_preprocess_page_result(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_preprocess_run_id,
            page_id=page_id,
        )
        if preprocess_result is None or preprocess_result.status != "SUCCEEDED":
            try:
                document_service._store.fail_layout_page_result(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_id=page_id,
                    failure_reason=(
                        "Input preprocess page result is missing or not SUCCEEDED."
                    ),
                )
            except Exception:  # noqa: BLE001
                pass
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="LAYOUT_PREPROCESS_INPUT_MISSING",
                error_message="Input preprocess page result is missing or not SUCCEEDED.",
            )
        input_key = preprocess_result.output_object_key_gray
        if not isinstance(input_key, str) or not input_key.strip():
            try:
                document_service._store.fail_layout_page_result(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_id=page_id,
                    failure_reason="Input preprocess grayscale object key is missing.",
                )
            except Exception:  # noqa: BLE001
                pass
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="LAYOUT_INPUT_MISSING",
                error_message="Input preprocess grayscale object key is missing.",
            )

        try:
            source_payload = document_service._storage.read_object_bytes(input_key)  # noqa: SLF001
            outcome = segment_layout_page_bytes(
                page_image_payload=source_payload,
                run_id=run_id,
                page_id=page_id,
                page_index=page.page_index,
                page_width=page.width,
                page_height=page.height,
                model_id=run.model_id,
                profile_id=run.profile_id,
                params_json=run.params_json,
            )
            document_service.materialize_layout_page_outputs(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                canonical_page_payload=outcome.canonical_page_payload,
                page_recall_status=outcome.page_recall_status,
                metrics_json=outcome.metrics_json,
                warnings_json=outcome.warnings_json,
                recall_check_version=outcome.recall_check_version,
                missed_text_risk_score=outcome.missed_text_risk_score,
                recall_signals_json=outcome.recall_signals_json,
                rescue_candidates=[
                    {
                        "id": candidate.id,
                        "candidate_kind": candidate.candidate_kind,
                        "geometry_json": dict(candidate.geometry_json),
                        "confidence": candidate.confidence,
                        "source_signal": candidate.source_signal,
                        "status": candidate.status,
                    }
                    for candidate in outcome.rescue_candidates
                ],
            )
        except LayoutSegmentationError as error:
            try:
                document_service._store.fail_layout_page_result(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_id=page_id,
                    failure_reason=str(error),
                )
            except Exception:  # noqa: BLE001
                pass
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="LAYOUT_SEGMENTATION_FAILED",
                error_message=str(error),
            )
        except Exception as error:  # noqa: BLE001
            try:
                document_service._store.fail_layout_page_result(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_id=page_id,
                    failure_reason=str(error),
                )
            except Exception:  # noqa: BLE001
                pass
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="LAYOUT_PAGE_FAILED",
                error_message=str(error),
            )

        return self.finish_running_job(
            job_id=row.id,
            worker_id=worker_id,
            success=True,
        )

    def _process_finalize_layout_run_job(self, *, worker_id: str, row: JobRecord) -> JobRecord:
        from app.documents.service import get_document_service

        try:
            project_id, document_id, run_id, _ = self._resolve_layout_job_payload(row)
        except JobValidationError as error:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="INVALID_LAYOUT_JOB_PAYLOAD",
                error_message=str(error),
            )

        document_service = get_document_service()
        try:
            finalized_run = document_service._store.finalize_layout_run(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except Exception as error:  # noqa: BLE001
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="LAYOUT_FINALIZE_FAILED",
                error_message=str(error),
            )

        if finalized_run.status == "SUCCEEDED":
            self._audit_service.record_event_best_effort(
                event_type="LAYOUT_RUN_FINISHED",
                actor_user_id=finalized_run.created_by,
                project_id=project_id,
                object_type="layout_run",
                object_id=run_id,
                metadata={
                    "run_id": run_id,
                    "document_id": document_id,
                    "status": finalized_run.status,
                },
                request_id=f"worker:{worker_id}:{row.id}",
            )
        elif finalized_run.status == "FAILED":
            self._audit_service.record_event_best_effort(
                event_type="LAYOUT_RUN_FAILED",
                actor_user_id=finalized_run.created_by,
                project_id=project_id,
                object_type="layout_run",
                object_id=run_id,
                metadata={
                    "run_id": run_id,
                    "document_id": document_id,
                    "reason": finalized_run.failure_reason or "Layout run failed.",
                },
                request_id=f"worker:{worker_id}:{row.id}",
            )
        elif finalized_run.status == "CANCELED":
            self._audit_service.record_event_best_effort(
                event_type="LAYOUT_RUN_CANCELED",
                actor_user_id=finalized_run.created_by,
                project_id=project_id,
                object_type="layout_run",
                object_id=run_id,
                metadata={"run_id": run_id, "document_id": document_id},
                request_id=f"worker:{worker_id}:{row.id}",
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
