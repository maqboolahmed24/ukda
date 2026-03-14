import base64
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from functools import lru_cache
from urllib.parse import urlparse
from typing import Any, Literal

import httpx

from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.jobs.models import JobEventRecord, JobRecord, JobStatus
from app.security.outbound import OutboundRequestBlockedError, validate_outbound_url
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
_PAGE_XML_NAMESPACE = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
_PAGE_XML_NS = {"pc": _PAGE_XML_NAMESPACE}
_TRANSCRIPTION_PROMPT_SCHEMA_VERSION = 1
_TRANSCRIPTION_FIXED_SYSTEM_PROMPT = (
    "You are UKDE handwriting transcription engine. "
    "Return only strict JSON object matching the requested schema. "
    "Do not include markdown, prose, or explanations."
)
_TRANSCRIPTION_MAX_OUTPUT_TOKENS = 512
_TRANSCRIPTION_DEFAULT_REVIEW_CONFIDENCE_THRESHOLD = 0.85
_TRANSCRIPTION_DEFAULT_FALLBACK_CONFIDENCE_THRESHOLD = 0.72
_TRANSCRIPTION_FALLBACK_CONFIDENCE_SIGNAL_WEIGHT = 0.35


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

    def enqueue_transcription_document_job(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        created_by: str,
    ) -> tuple[JobRecord, bool, str]:
        dedupe_key = self._store.compute_dedupe_key(
            project_id=project_id,
            job_type="TRANSCRIBE_DOCUMENT",
            logical_key=f"document:{document_id}|run:{run_id}",
        )
        row, created, reason = self._store.enqueue_job(
            project_id=project_id,
            job_type="TRANSCRIBE_DOCUMENT",
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

    def _enqueue_transcription_page_job(
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
            job_type="TRANSCRIBE_PAGE",
            logical_key=f"run:{run_id}|page:{page_id}",
        )
        row, created, reason = self._store.enqueue_job(
            project_id=project_id,
            job_type="TRANSCRIBE_PAGE",
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

    def _enqueue_transcription_finalize_job(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        created_by: str,
    ) -> tuple[JobRecord, bool, str]:
        dedupe_key = self._store.compute_dedupe_key(
            project_id=project_id,
            job_type="FINALIZE_TRANSCRIPTION_RUN",
            logical_key=f"run:{run_id}",
        )
        row, created, reason = self._store.enqueue_job(
            project_id=project_id,
            job_type="FINALIZE_TRANSCRIPTION_RUN",
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
        if row.type == "TRANSCRIBE_DOCUMENT":
            return self._process_transcription_document_job(worker_id=worker_id, row=row)
        if row.type == "TRANSCRIBE_PAGE":
            return self._process_transcription_page_job(worker_id=worker_id, row=row)
        if row.type == "FINALIZE_TRANSCRIPTION_RUN":
            return self._process_finalize_transcription_run_job(worker_id=worker_id, row=row)

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
    def _resolve_transcription_job_payload(
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
                "Transcription job payload requires project_id, document_id, and run_id."
            )
        if require_page_id and not isinstance(page_id, str):
            raise JobValidationError("TRANSCRIBE_PAGE payload requires page_id.")
        return project_id, document_id, run_id, page_id if isinstance(page_id, str) else None

    def _load_model_service_map(self) -> dict[str, object]:
        try:
            raw_payload = json.loads(
                self._settings.model_service_map_path.read_text(encoding="utf-8")
            )
        except OSError as error:
            raise JobValidationError(
                f"MODEL_SERVICE_MAP_PATH could not be read: {self._settings.model_service_map_path}"
            ) from error
        except json.JSONDecodeError as error:
            raise JobValidationError("MODEL_SERVICE_MAP_PATH contains invalid JSON.") from error
        if not isinstance(raw_payload, dict):
            raise JobValidationError("MODEL_SERVICE_MAP_PATH must contain a JSON object.")
        services = raw_payload.get("services")
        if not isinstance(services, dict):
            raise JobValidationError("MODEL_SERVICE_MAP_PATH services map is missing.")
        return raw_payload

    @staticmethod
    def _resolve_origin(url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise JobValidationError("Model service base_url is invalid.")
        return f"{parsed.scheme}://{parsed.netloc}"

    def _resolve_transcription_service_endpoint(
        self,
        *,
        document_service: Any,
        run: Any,
    ) -> tuple[str, str]:
        model = document_service._store.get_approved_model(  # noqa: SLF001
            model_id=run.model_id
        )
        if model is None:
            raise JobValidationError("Run model_id does not resolve to approved_models.")
        if model.status != "APPROVED":
            raise JobValidationError("Transcription run model must be APPROVED.")
        if model.serving_interface != "OPENAI_CHAT":
            raise JobValidationError(
                "Primary transcription path requires an OPENAI_CHAT serving interface."
            )
        service_map = self._load_model_service_map()
        services = service_map.get("services")
        if not isinstance(services, dict):
            raise JobValidationError("Model service map is invalid.")
        service_entry = services.get(model.deployment_unit)
        if not isinstance(service_entry, dict):
            raise JobValidationError(
                f"Model deployment unit '{model.deployment_unit}' was not found in service map."
            )
        base_url = service_entry.get("base_url")
        if not isinstance(base_url, str) or not base_url.strip():
            raise JobValidationError("Model service base_url is missing.")
        endpoints = service_entry.get("endpoints")
        if not isinstance(endpoints, dict):
            raise JobValidationError("Model service endpoints map is missing.")
        chat_path = endpoints.get("chat")
        if not isinstance(chat_path, str) or not chat_path.strip():
            raise JobValidationError("Model service chat endpoint is missing.")
        chat_path = chat_path.strip()
        if chat_path.startswith("http://") or chat_path.startswith("https://"):
            endpoint = chat_path
        else:
            endpoint = f"{self._resolve_origin(base_url.strip())}{chat_path}"
        metadata = model.metadata_json if isinstance(model.metadata_json, dict) else {}
        metadata_model_name = metadata.get("model")
        if isinstance(metadata_model_name, str) and metadata_model_name.strip():
            model_name = metadata_model_name.strip()
        else:
            model_name = f"{model.model_family}-{model.model_version}"
        return endpoint, model_name

    @staticmethod
    def _encode_image_as_data_url(payload: bytes) -> str:
        encoded = base64.b64encode(payload).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    @staticmethod
    def _strip_markdown_code_fence(value: str) -> str:
        fenced = value.strip()
        if fenced.startswith("```"):
            fenced = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", fenced)
            fenced = re.sub(r"\s*```$", "", fenced)
        return fenced.strip()

    def _parse_structured_response_payload(self, content: object) -> dict[str, object]:
        if isinstance(content, dict):
            return content
        if isinstance(content, list):
            flattened = []
            for part in content:
                if isinstance(part, dict):
                    text_part = part.get("text")
                    if isinstance(text_part, str):
                        flattened.append(text_part)
            content = "\n".join(flattened)
        if not isinstance(content, str):
            raise JobValidationError("Model response content is not a JSON object.")
        stripped = self._strip_markdown_code_fence(content)
        if not stripped:
            raise JobValidationError("Model response content is empty.")
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as error:
            raise JobValidationError("Model response content is not valid JSON.") from error
        if not isinstance(payload, dict):
            raise JobValidationError("Model response JSON must be an object.")
        if isinstance(payload.get("item"), dict):
            return payload["item"]  # type: ignore[return-value]
        items = payload.get("items")
        if isinstance(items, list) and len(items) == 1 and isinstance(items[0], dict):
            return items[0]
        return payload

    def _extract_structured_transcription_item(
        self,
        *,
        response_payload: dict[str, object],
    ) -> dict[str, object]:
        choices = response_payload.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    return self._parse_structured_response_payload(
                        message.get("content")
                    )
                if isinstance(first.get("text"), str):
                    return self._parse_structured_response_payload(first.get("text"))
        return self._parse_structured_response_payload(response_payload)

    def _call_primary_transcription_service(
        self,
        *,
        endpoint_url: str,
        model_name: str,
        request_payload: dict[str, object],
        actor_user_id: str | None,
        request_id: str,
    ) -> dict[str, object]:
        validate_outbound_url(
            method="POST",
            url=endpoint_url,
            purpose="transcription-primary-vlm",
            settings=self._settings,
            actor_user_id=actor_user_id,
            audit_service=self._audit_service,
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.openai_api_key}",
        }
        body = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": _TRANSCRIPTION_FIXED_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": json.dumps(request_payload, sort_keys=True)},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": request_payload["imageDataUrl"],
                            },
                        },
                    ],
                },
            ],
            "temperature": 0,
            "max_tokens": _TRANSCRIPTION_MAX_OUTPUT_TOKENS,
        }
        try:
            response = httpx.post(
                endpoint_url,
                headers=headers,
                json=body,
                timeout=httpx.Timeout(120.0, connect=5.0),
            )
        except httpx.HTTPError as error:
            raise JobValidationError(
                f"Primary transcription service request failed: {error.__class__.__name__}"
            ) from error
        if response.status_code != 200:
            raise JobValidationError(
                f"Primary transcription service returned {response.status_code}."
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise JobValidationError(
                "Primary transcription service returned non-JSON payload."
            ) from error
        if not isinstance(payload, dict):
            raise JobValidationError("Primary transcription service payload is invalid.")
        return payload

    @staticmethod
    def _fallback_engine_default_confidence(engine: str) -> float:
        if engine == "KRAKEN_LINE":
            return 0.74
        if engine == "TROCR_LINE":
            return 0.7
        if engine == "DAN_PAGE":
            return 0.68
        return 0.72

    @staticmethod
    def _build_governed_fallback_text(
        *,
        engine: str,
        request_payload: dict[str, object],
    ) -> str:
        target = request_payload.get("target")
        source_ref_id = None
        line_id = None
        if isinstance(target, dict):
            if isinstance(target.get("sourceRefId"), str):
                source_ref_id = target.get("sourceRefId")
            if isinstance(target.get("lineId"), str):
                line_id = target.get("lineId")
        context_window = request_payload.get("contextWindow")
        if isinstance(context_window, dict):
            for key in ("lineText", "lineHint", "transcriptHint"):
                value = context_window.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        anchor = line_id or source_ref_id or "unknown-anchor"
        prefix = {
            "KRAKEN_LINE": "kraken",
            "TROCR_LINE": "trocr",
            "DAN_PAGE": "dan",
        }.get(engine, "fallback")
        return f"[{prefix}:{anchor}]"

    def _call_governed_fallback_adapter(
        self,
        *,
        engine: str,
        request_payload: dict[str, object],
    ) -> dict[str, object]:
        target = request_payload.get("target")
        source_kind = "LINE"
        source_ref_id = "unknown-source-ref"
        line_id = None
        if isinstance(target, dict):
            if isinstance(target.get("sourceKind"), str) and target.get("sourceKind"):
                source_kind = str(target["sourceKind"]).strip().upper()
            if isinstance(target.get("sourceRefId"), str) and target.get("sourceRefId"):
                source_ref_id = str(target["sourceRefId"]).strip()
            if isinstance(target.get("lineId"), str) and target.get("lineId"):
                line_id = str(target["lineId"]).strip()
        return {
            "sourceKind": source_kind,
            "sourceRefId": source_ref_id,
            "lineId": line_id,
            "textDiplomatic": self._build_governed_fallback_text(
                engine=engine,
                request_payload=request_payload,
            ),
            "confidence": self._fallback_engine_default_confidence(engine),
            "adapterEngine": engine,
            "adapterKind": "GOVERNED_FALLBACK",
        }

    def _invoke_transcription_engine_adapter(
        self,
        *,
        run: Any,
        request_payload: dict[str, object],
        endpoint_url: str | None,
        model_name: str | None,
        actor_user_id: str | None,
        request_id: str,
    ) -> dict[str, object]:
        engine = str(getattr(run, "engine", "VLM_LINE_CONTEXT") or "VLM_LINE_CONTEXT")
        if engine == "VLM_LINE_CONTEXT":
            if not endpoint_url or not model_name:
                raise JobValidationError(
                    "Primary transcription engine requires resolved endpoint and model."
                )
            return self._call_primary_transcription_service(
                endpoint_url=endpoint_url,
                model_name=model_name,
                request_payload=request_payload,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
        if engine in {"KRAKEN_LINE", "TROCR_LINE", "DAN_PAGE", "REVIEW_COMPOSED"}:
            return self._call_governed_fallback_adapter(
                engine=engine,
                request_payload=request_payload,
            )
        raise JobValidationError(
            f"Transcription engine '{engine}' is not supported by the worker adapter interface."
        )

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

    @staticmethod
    def _coerce_confidence(value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            confidence = float(value)
            if 0 <= confidence <= 1:
                return confidence
        return None

    @staticmethod
    def _coerce_span_index(value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return None

    @staticmethod
    def _resolve_transcription_thresholds(
        *,
        run: Any,
    ) -> tuple[float, float]:
        params = getattr(run, "params_json", {})
        review_threshold = _TRANSCRIPTION_DEFAULT_REVIEW_CONFIDENCE_THRESHOLD
        fallback_threshold = _TRANSCRIPTION_DEFAULT_FALLBACK_CONFIDENCE_THRESHOLD
        if isinstance(params, dict):
            review_raw = params.get("review_confidence_threshold")
            fallback_raw = params.get("fallback_confidence_threshold")
            if isinstance(review_raw, (int, float)) and not isinstance(review_raw, bool):
                review_threshold = float(review_raw)
            if isinstance(fallback_raw, (int, float)) and not isinstance(
                fallback_raw, bool
            ):
                fallback_threshold = float(fallback_raw)
        review_threshold = max(0.0, min(1.0, review_threshold))
        fallback_threshold = max(0.0, min(1.0, fallback_threshold))
        if fallback_threshold > review_threshold:
            fallback_threshold = review_threshold
        return review_threshold, fallback_threshold

    @staticmethod
    def _normalize_agreement_text(value: str) -> str:
        lowered = value.strip().lower()
        lowered = re.sub(r"\s+", " ", lowered)
        lowered = re.sub(r"[^a-z0-9 ]+", "", lowered)
        return lowered.strip()

    @classmethod
    def _compute_text_agreement_score(cls, left: str, right: str) -> float:
        normalized_left = cls._normalize_agreement_text(left)
        normalized_right = cls._normalize_agreement_text(right)
        if not normalized_left and not normalized_right:
            return 0.0
        if normalized_left == normalized_right:
            return 1.0
        return max(
            0.0,
            min(
                1.0,
                SequenceMatcher(None, normalized_left, normalized_right).ratio(),
            ),
        )

    @staticmethod
    def _calibrate_confidence_value(
        *,
        raw_score: float,
        basis: str,
        calibration_version: str,
    ) -> float:
        score = max(0.0, min(1.0, raw_score))
        normalized_version = calibration_version.strip().lower()
        if normalized_version in {"v1", "1", "cal-v1"}:
            if basis == "MODEL_NATIVE":
                return max(0.0, min(1.0, 0.05 + (score * 0.95)))
            if basis == "READ_AGREEMENT":
                return max(0.0, min(1.0, 0.1 + (score * 0.9)))
            if basis == "FALLBACK_DISAGREEMENT":
                return max(0.0, min(1.0, score))
        return score

    @staticmethod
    def _resolve_confidence_band(
        *,
        confidence: float | None,
        review_threshold: float,
        fallback_threshold: float,
    ) -> str:
        if not isinstance(confidence, float):
            return "UNKNOWN"
        if confidence >= review_threshold:
            return "HIGH"
        if confidence >= fallback_threshold:
            return "MEDIUM"
        return "LOW"

    @classmethod
    def _build_compact_alignment_payload(
        cls,
        *,
        response_item: dict[str, object],
        line_id_hint: str | None,
    ) -> tuple[dict[str, object] | None, list[str]]:
        warnings: list[str] = []
        raw_spans: object | None = None
        if isinstance(response_item.get("alignmentSpans"), list):
            raw_spans = response_item.get("alignmentSpans")
        elif isinstance(response_item.get("alignment"), dict):
            alignment_payload = response_item.get("alignment")
            assert isinstance(alignment_payload, dict)
            if isinstance(alignment_payload.get("spans"), list):
                raw_spans = alignment_payload.get("spans")
        elif isinstance(response_item.get("spans"), list):
            raw_spans = response_item.get("spans")

        if raw_spans is None:
            return None, warnings

        assert isinstance(raw_spans, list)
        spans: list[dict[str, object]] = []
        malformed_count = 0
        anchor_mismatch_count = 0
        for raw_span in raw_spans:
            if not isinstance(raw_span, dict):
                malformed_count += 1
                continue
            start = cls._coerce_span_index(raw_span.get("start"))
            end = cls._coerce_span_index(raw_span.get("end"))
            if start is None or end is None or start < 0 or end <= start:
                malformed_count += 1
                continue
            anchor_line_id = (
                str(raw_span["lineId"]).strip()
                if isinstance(raw_span.get("lineId"), str)
                and str(raw_span["lineId"]).strip()
                else None
            )
            if (
                line_id_hint is not None
                and anchor_line_id is not None
                and anchor_line_id != line_id_hint
            ):
                anchor_mismatch_count += 1
            spans.append(
                {
                    "start": start,
                    "end": end,
                    "kind": (
                        str(raw_span["kind"]).strip()
                        if isinstance(raw_span.get("kind"), str)
                        and str(raw_span["kind"]).strip()
                        else "TOKEN"
                    ),
                    "lineId": anchor_line_id,
                }
            )

        if malformed_count > 0:
            warnings.append("MALFORMED_ALIGNMENT_SPANS")
        if anchor_mismatch_count > 0:
            warnings.append("ALIGNMENT_ANCHOR_MISMATCH")
        payload: dict[str, object] = {
            "schemaVersion": 1,
            "spanCount": len(spans),
            "spans": spans,
        }
        if line_id_hint is not None:
            payload["lineIdHint"] = line_id_hint
        if warnings:
            payload["warnings"] = list(warnings)
        return payload, warnings

    @staticmethod
    def _build_compact_char_boxes_payload(
        *,
        response_item: dict[str, object],
        text_diplomatic: str,
    ) -> tuple[dict[str, object] | None, list[dict[str, object]], bool]:
        raw_boxes = response_item.get("charBoxes")
        if raw_boxes is None:
            raw_boxes = response_item.get("char_boxes")
        if not isinstance(raw_boxes, list):
            return None, [], False

        compact_boxes: list[dict[str, object]] = []
        preview: list[dict[str, object]] = []
        malformed = False
        for index, raw_box in enumerate(raw_boxes):
            if not isinstance(raw_box, dict):
                malformed = True
                continue
            char_value = raw_box.get("char")
            if not isinstance(char_value, str):
                malformed = True
                continue
            confidence = JobService._coerce_confidence(raw_box.get("confidence"))
            box_row: dict[str, object] = {
                "index": index,
                "char": char_value[:1],
                "confidence": confidence,
            }
            compact_boxes.append(box_row)
            if len(preview) < 32:
                preview.append(box_row)

        if not compact_boxes:
            return None, [], malformed

        payload: dict[str, object] = {
            "schemaVersion": 1,
            "charCount": len(compact_boxes),
            "textLength": len(text_diplomatic),
            "boxes": compact_boxes,
        }
        if malformed:
            payload["warnings"] = ["MALFORMED_CHAR_BOXES"]
        return payload, preview, malformed

    def _compute_line_confidence(
        self,
        *,
        run: Any,
        request_payload: dict[str, object],
        response_item: dict[str, object],
        text_diplomatic: str,
        actor_user_id: str | None,
        request_id: str,
        endpoint_url: str | None,
        model_name: str | None,
    ) -> tuple[float | None, str, dict[str, object]]:
        calibration_version = str(
            getattr(run, "confidence_calibration_version", "v1") or "v1"
        )
        run_basis = str(getattr(run, "confidence_basis", "MODEL_NATIVE") or "MODEL_NATIVE")
        signals: dict[str, object] = {}

        model_native = self._coerce_confidence(response_item.get("confidence"))
        if model_native is not None:
            calibrated = self._calibrate_confidence_value(
                raw_score=model_native,
                basis="MODEL_NATIVE",
                calibration_version=calibration_version,
            )
            confidence = calibrated
            basis = "MODEL_NATIVE"
            signals["modelNativeRaw"] = model_native
        else:
            crop_only_text = ""
            try:
                crop_only_request = dict(request_payload)
                crop_only_request["contextWindow"] = {}
                crop_only_response = self._invoke_transcription_engine_adapter(
                    run=run,
                    request_payload=crop_only_request,
                    endpoint_url=endpoint_url,
                    model_name=model_name,
                    actor_user_id=actor_user_id,
                    request_id=f"{request_id}:agreement",
                )
                crop_only_item = self._extract_structured_transcription_item(
                    response_payload=crop_only_response
                )
                crop_only_text_raw = crop_only_item.get("textDiplomatic")
                if not isinstance(crop_only_text_raw, str):
                    crop_only_text_raw = crop_only_item.get("text")
                crop_only_text = (
                    crop_only_text_raw.strip()
                    if isinstance(crop_only_text_raw, str)
                    else ""
                )
            except Exception as error:  # noqa: BLE001
                signals["agreementReadError"] = error.__class__.__name__
                crop_only_text = ""
            agreement_score = self._compute_text_agreement_score(
                text_diplomatic,
                crop_only_text,
            )
            confidence = self._calibrate_confidence_value(
                raw_score=agreement_score,
                basis="READ_AGREEMENT",
                calibration_version=calibration_version,
            )
            basis = "READ_AGREEMENT"
            signals["agreementScore"] = round(agreement_score, 6)

        params = getattr(run, "params_json", {})
        use_fallback_signal = run_basis == "FALLBACK_DISAGREEMENT"
        if isinstance(params, dict):
            fallback_signal_setting = params.get("fallback_disagreement_signal")
            if isinstance(fallback_signal_setting, bool):
                use_fallback_signal = fallback_signal_setting
        if use_fallback_signal and text_diplomatic.strip():
            fallback_response = self._call_governed_fallback_adapter(
                engine="KRAKEN_LINE",
                request_payload=request_payload,
            )
            fallback_text = (
                str(fallback_response.get("textDiplomatic")).strip()
                if isinstance(fallback_response.get("textDiplomatic"), str)
                else ""
            )
            disagreement_score = 1.0 - self._compute_text_agreement_score(
                text_diplomatic,
                fallback_text,
            )
            base_confidence = confidence if isinstance(confidence, float) else 0.5
            disagreement_adjusted = max(
                0.0,
                min(
                    1.0,
                    base_confidence
                    - (disagreement_score * _TRANSCRIPTION_FALLBACK_CONFIDENCE_SIGNAL_WEIGHT),
                ),
            )
            disagreement_calibrated = self._calibrate_confidence_value(
                raw_score=disagreement_adjusted,
                basis="FALLBACK_DISAGREEMENT",
                calibration_version=calibration_version,
            )
            if run_basis == "FALLBACK_DISAGREEMENT":
                confidence = disagreement_calibrated
                basis = "FALLBACK_DISAGREEMENT"
            else:
                confidence = min(base_confidence, disagreement_calibrated)
            signals["fallbackDisagreementScore"] = round(disagreement_score, 6)
            signals["fallbackSignalApplied"] = True
        else:
            signals["fallbackSignalApplied"] = False

        if not isinstance(confidence, float):
            return None, basis, signals
        return max(0.0, min(1.0, confidence)), basis, signals

    @staticmethod
    def _safe_xml_identifier(value: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9._:-]+", "-", value.strip())
        normalized = normalized.strip("-")
        if not normalized:
            return "resc"
        if normalized[0].isdigit():
            return f"id-{normalized}"
        return normalized[:120]

    @staticmethod
    def _format_points(points: list[tuple[float, float]]) -> str:
        return " ".join(f"{point[0]:.4f},{point[1]:.4f}" for point in points)

    @staticmethod
    def _points_from_geometry(geometry_json: dict[str, object]) -> list[tuple[float, float]] | None:
        polygon = geometry_json.get("polygon")
        if isinstance(polygon, list):
            points: list[tuple[float, float]] = []
            for raw_point in polygon:
                if not isinstance(raw_point, dict):
                    continue
                raw_x = raw_point.get("x")
                raw_y = raw_point.get("y")
                if not isinstance(raw_x, (int, float)) or not isinstance(raw_y, (int, float)):
                    continue
                points.append((float(raw_x), float(raw_y)))
            if len(points) >= 3:
                return points
        bbox = geometry_json.get("bbox")
        if not isinstance(bbox, dict):
            return None
        raw_x = bbox.get("x")
        raw_y = bbox.get("y")
        raw_w = bbox.get("width")
        raw_h = bbox.get("height")
        if not all(isinstance(value, (int, float)) for value in (raw_x, raw_y, raw_w, raw_h)):
            return None
        x = float(raw_x)
        y = float(raw_y)
        width = float(raw_w)
        height = float(raw_h)
        if width <= 0 or height <= 0:
            return None
        return [
            (x, y),
            (x + width, y),
            (x + width, y + height),
            (x, y + height),
        ]

    @staticmethod
    def _bbox_from_points(points: list[tuple[float, float]]) -> dict[str, float] | None:
        if len(points) < 3:
            return None
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)
        width = max_x - min_x
        height = max_y - min_y
        if width <= 0 or height <= 0:
            return None
        return {
            "x": round(min_x, 4),
            "y": round(min_y, 4),
            "width": round(width, 4),
            "height": round(height, 4),
        }

    @staticmethod
    def _parse_pagexml_points(value: str | None) -> list[tuple[float, float]]:
        if not isinstance(value, str) or not value.strip():
            return []
        points: list[tuple[float, float]] = []
        for raw_point in value.split():
            if "," not in raw_point:
                continue
            raw_x, raw_y = raw_point.split(",", 1)
            try:
                x = float(raw_x)
                y = float(raw_y)
            except ValueError:
                continue
            points.append((x, y))
        return points

    def _extract_line_geometry_from_pagexml(
        self,
        *,
        layout_pagexml_bytes: bytes,
    ) -> tuple[dict[str, dict[str, object]], float, float]:
        try:
            root = ET.fromstring(layout_pagexml_bytes)
        except ET.ParseError as error:
            raise JobValidationError("Layout PAGE-XML payload is invalid.") from error
        page_element = root.find("pc:Page", _PAGE_XML_NS)
        if page_element is None:
            raise JobValidationError("Layout PAGE-XML payload is missing Page element.")
        try:
            page_width = float(page_element.attrib["imageWidth"])
            page_height = float(page_element.attrib["imageHeight"])
        except (KeyError, ValueError) as error:
            raise JobValidationError(
                "Layout PAGE-XML payload is missing page dimensions."
            ) from error
        if page_width <= 0 or page_height <= 0:
            raise JobValidationError("Layout PAGE-XML page dimensions are invalid.")

        line_geometry_by_id: dict[str, dict[str, object]] = {}
        for line_element in page_element.findall(".//pc:TextLine", _PAGE_XML_NS):
            line_id = line_element.get("id")
            if not isinstance(line_id, str) or not line_id.strip():
                continue
            coords_element = line_element.find("pc:Coords", _PAGE_XML_NS)
            points = self._parse_pagexml_points(
                coords_element.get("points") if coords_element is not None else None
            )
            if len(points) < 3:
                continue
            bbox = self._bbox_from_points(points)
            if bbox is None:
                continue
            line_geometry_by_id[line_id.strip()] = {
                "bbox": bbox,
                "polygon": [
                    {"x": round(point[0], 4), "y": round(point[1], 4)}
                    for point in points
                ],
            }
        return line_geometry_by_id, page_width, page_height

    def _normalize_token_geometry(
        self,
        *,
        geometry_json: dict[str, object],
        page_width: float,
        page_height: float,
    ) -> tuple[dict[str, object] | None, dict[str, object] | None]:
        if page_width <= 0 or page_height <= 0:
            return None, None
        points = self._points_from_geometry(geometry_json)
        if points is None:
            return None, None

        bounded_points: list[tuple[float, float]] = []
        for point_x, point_y in points:
            bounded_x = min(max(float(point_x), 0.0), page_width)
            bounded_y = min(max(float(point_y), 0.0), page_height)
            bounded_points.append((bounded_x, bounded_y))
        bbox = self._bbox_from_points(bounded_points)
        if bbox is None:
            return None, None
        polygon_json = {
            "points": [
                {"x": round(point_x, 4), "y": round(point_y, 4)}
                for point_x, point_y in bounded_points
            ]
        }
        return bbox, polygon_json

    @staticmethod
    def _tokenize_transcription_text(
        text: str,
    ) -> list[tuple[str, int, int]]:
        tokens: list[tuple[str, int, int]] = []
        for match in re.finditer(r"\S+", text):
            token_text = match.group(0)
            if token_text:
                tokens.append((token_text, match.start(), match.end()))
        return tokens

    @staticmethod
    def _build_token_anchor_id(
        *,
        run_id: str,
        page_id: str,
        source_kind: str,
        source_ref_id: str,
        line_id: str | None,
        token_index: int,
        token_start: int,
        token_end: int,
        token_text: str,
    ) -> str:
        seed = "|".join(
            [
                run_id,
                page_id,
                source_kind,
                source_ref_id,
                line_id or "",
                str(token_index),
                f"{token_start}:{token_end}",
                token_text,
            ]
        )
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return f"tok-{digest[:24]}"

    @staticmethod
    def _set_text_equiv(line_element: ET.Element, text: str) -> None:
        for text_equiv in list(line_element.findall("pc:TextEquiv", _PAGE_XML_NS)):
            line_element.remove(text_equiv)
        text_equiv = ET.SubElement(line_element, f"{{{_PAGE_XML_NAMESPACE}}}TextEquiv")
        unicode_element = ET.SubElement(text_equiv, f"{{{_PAGE_XML_NAMESPACE}}}Unicode")
        unicode_element.text = text

    def _build_transcription_pagexml(
        self,
        *,
        layout_pagexml_bytes: bytes,
        line_text_by_line_id: dict[str, str],
        rescue_entries: list[dict[str, object]],
    ) -> bytes:
        try:
            root = ET.fromstring(layout_pagexml_bytes)
        except ET.ParseError as error:
            raise JobValidationError("Layout PAGE-XML payload is invalid.") from error
        page_element = root.find("pc:Page", _PAGE_XML_NS)
        if page_element is None:
            raise JobValidationError("Layout PAGE-XML payload is missing Page element.")

        text_line_elements: dict[str, ET.Element] = {}
        for line_element in page_element.findall(".//pc:TextLine", _PAGE_XML_NS):
            line_id = line_element.get("id")
            if isinstance(line_id, str) and line_id.strip():
                text_line_elements[line_id.strip()] = line_element

        for line_id, text in line_text_by_line_id.items():
            target = text_line_elements.get(line_id)
            if target is None:
                raise JobValidationError(
                    f"Line anchor '{line_id}' is missing from layout PAGE-XML."
                )
            self._set_text_equiv(target, text)

        for rescue in rescue_entries:
            rescue_line_id = str(rescue["line_id"])
            rescue_text = str(rescue["text_diplomatic"])
            geometry_json = rescue.get("geometry_json")
            if not isinstance(geometry_json, dict):
                raise JobValidationError(
                    f"Rescue geometry is invalid for line '{rescue_line_id}'."
                )
            points = self._points_from_geometry(geometry_json)
            if points is None:
                raise JobValidationError(
                    f"Rescue geometry is missing polygon/bbox for line '{rescue_line_id}'."
                )
            source_ref_id = str(rescue["source_ref_id"])
            source_kind = str(rescue["source_kind"])
            region_id = f"resc-reg-{self._safe_xml_identifier(source_ref_id)}"
            region_element = ET.SubElement(
                page_element,
                f"{{{_PAGE_XML_NAMESPACE}}}TextRegion",
                {
                    "id": region_id,
                    "type": "RESCUE",
                    "sourceKind": source_kind,
                    "sourceRefId": source_ref_id,
                },
            )
            ET.SubElement(
                region_element,
                f"{{{_PAGE_XML_NAMESPACE}}}Coords",
                {"points": self._format_points(points)},
            )
            line_element = ET.SubElement(
                region_element,
                f"{{{_PAGE_XML_NAMESPACE}}}TextLine",
                {
                    "id": rescue_line_id,
                    "sourceKind": source_kind,
                    "sourceRefId": source_ref_id,
                },
            )
            ET.SubElement(
                line_element,
                f"{{{_PAGE_XML_NAMESPACE}}}Coords",
                {"points": self._format_points(points)},
            )
            self._set_text_equiv(line_element, rescue_text)

        payload = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
        try:
            parsed = ET.fromstring(payload)
        except ET.ParseError as error:
            raise JobValidationError("Transcription PAGE-XML output is invalid.") from error

        for line_id in line_text_by_line_id:
            target = None
            for candidate in parsed.findall(".//pc:TextLine", _PAGE_XML_NS):
                if candidate.get("id") == line_id:
                    target = candidate
                    break
            if target is None:
                raise JobValidationError(
                    f"Transcription PAGE-XML is missing TextLine '{line_id}'."
                )
            unicode_node = target.find("pc:TextEquiv/pc:Unicode", _PAGE_XML_NS)
            if unicode_node is None or not (unicode_node.text or "").strip():
                raise JobValidationError(
                    f"Transcription PAGE-XML is missing TextEquiv content for '{line_id}'."
                )
        return payload

    @staticmethod
    def _engine_emits_hocr(engine: str) -> bool:
        return engine in {"KRAKEN_LINE", "TROCR_LINE", "DAN_PAGE"}

    def _build_fallback_hocr_payload(
        self,
        *,
        engine: str,
        page_index: int,
        line_text_by_line_id: dict[str, str],
        rescue_entries: list[dict[str, object]],
    ) -> bytes:
        lines: list[str] = []
        for line_id, text in sorted(line_text_by_line_id.items()):
            lines.append(
                f'<span class="ocr_line" data-line-id="{line_id}">{text}</span>'
            )
        for entry in rescue_entries:
            line_id = str(entry.get("line_id") or "resc")
            text = str(entry.get("text_diplomatic") or "")
            lines.append(
                f'<span class="ocr_line" data-line-id="{line_id}">{text}</span>'
            )
        body = "\n".join(lines)
        payload = (
            "<html><body>"
            f'<div class="ocr_page" data-engine="{engine}" data-page-index="{page_index}">'
            f"{body}"
            "</div></body></html>\n"
        )
        return payload.encode("utf-8")

    def _process_transcription_document_job(self, *, worker_id: str, row: JobRecord) -> JobRecord:
        from app.documents.service import get_document_service

        try:
            project_id, document_id, run_id, _ = self._resolve_transcription_job_payload(row)
        except JobValidationError as error:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="INVALID_TRANSCRIPTION_JOB_PAYLOAD",
                error_message=str(error),
            )

        document_service = get_document_service()
        run = document_service._store.get_transcription_run(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="TRANSCRIPTION_RUN_NOT_FOUND",
                error_message="Target transcription run was not found.",
            )
        if run.status in {"SUCCEEDED", "FAILED", "CANCELED"}:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=True,
            )

        try:
            started_run = document_service._store.mark_transcription_run_running(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except Exception as error:  # noqa: BLE001
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="TRANSCRIPTION_RUN_START_FAILED",
                error_message=str(error),
            )

        self._audit_service.record_event_best_effort(
            event_type="TRANSCRIPTION_RUN_STARTED",
            actor_user_id=started_run.created_by,
            project_id=project_id,
            object_type="transcription_run",
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
                current_run = document_service._store.get_transcription_run(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                )
                if current_run is None or current_run.status == "CANCELED":
                    break
                page_rows, next_cursor = document_service._store.list_page_transcription_results(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    cursor=page_cursor,
                    page_size=200,
                )
                for page_row in page_rows:
                    if page_row.status in {"SUCCEEDED", "FAILED", "CANCELED"}:
                        continue
                    current_run = document_service._store.get_transcription_run(  # noqa: SLF001
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    if current_run is None or current_run.status == "CANCELED":
                        break
                    self._enqueue_transcription_page_job(
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

            self._enqueue_transcription_finalize_job(
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
                error_code="TRANSCRIPTION_DOCUMENT_ORCHESTRATION_FAILED",
                error_message=str(error),
            )

        return self.finish_running_job(
            job_id=row.id,
            worker_id=worker_id,
            success=True,
        )

    def _process_transcription_page_job(self, *, worker_id: str, row: JobRecord) -> JobRecord:
        from app.documents.service import get_document_service

        try:
            project_id, document_id, run_id, page_id = self._resolve_transcription_job_payload(
                row,
                require_page_id=True,
            )
            assert page_id is not None
        except JobValidationError as error:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="INVALID_TRANSCRIPTION_JOB_PAYLOAD",
                error_message=str(error),
            )

        document_service = get_document_service()
        run = document_service._store.get_transcription_run(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="TRANSCRIPTION_RUN_NOT_FOUND",
                error_message="Target transcription run was not found.",
            )
        if run.status in {"FAILED", "CANCELED", "SUCCEEDED"}:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=True,
            )

        try:
            document_service._store.mark_transcription_run_running(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            page_result = document_service._store.mark_transcription_page_running(  # noqa: SLF001
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
                error_code="TRANSCRIPTION_PAGE_TRANSITION_FAILED",
                error_message=str(error),
            )

        if page_result.status in {"SUCCEEDED", "CANCELED"}:
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
                document_service._store.fail_transcription_page_result(  # noqa: SLF001
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
                error_code="TRANSCRIPTION_PAGE_NOT_FOUND",
                error_message="Page metadata record not found.",
            )

        preprocess_result = document_service._store.get_preprocess_page_result(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_preprocess_run_id,
            page_id=page_id,
        )
        if (
            preprocess_result is None
            or preprocess_result.status != "SUCCEEDED"
            or not preprocess_result.output_object_key_gray
        ):
            try:
                document_service._store.fail_transcription_page_result(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_id=page_id,
                    failure_reason="Input preprocess page result is missing or not SUCCEEDED.",
                )
            except Exception:  # noqa: BLE001
                pass
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="TRANSCRIPTION_PREPROCESS_INPUT_MISSING",
                error_message="Input preprocess page result is missing or not SUCCEEDED.",
            )

        layout_page_result = document_service._store.get_layout_page_result(  # noqa: SLF001
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_layout_run_id,
            page_id=page_id,
        )
        if (
            layout_page_result is None
            or layout_page_result.status != "SUCCEEDED"
            or not layout_page_result.page_xml_key
        ):
            try:
                document_service._store.fail_transcription_page_result(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_id=page_id,
                    failure_reason="Input layout page result is missing or not SUCCEEDED.",
                )
            except Exception:  # noqa: BLE001
                pass
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="TRANSCRIPTION_LAYOUT_INPUT_MISSING",
                error_message="Input layout page result is missing or not SUCCEEDED.",
            )

        try:
            preprocess_page_image = document_service._storage.read_object_bytes(  # noqa: SLF001
                preprocess_result.output_object_key_gray
            )
            layout_pagexml_bytes = document_service._storage.read_object_bytes(  # noqa: SLF001
                layout_page_result.page_xml_key
            )
            line_geometry_by_id, page_width, page_height = (
                self._extract_line_geometry_from_pagexml(
                    layout_pagexml_bytes=layout_pagexml_bytes
                )
            )
            line_artifacts = document_service._store.list_layout_line_artifacts(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run.input_layout_run_id,
                page_id=page_id,
            )
            rescue_candidates = document_service._store.list_layout_rescue_candidates(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run.input_layout_run_id,
                page_id=page_id,
            )
            endpoint_url: str | None = None
            model_name: str | None = None
            if run.engine == "VLM_LINE_CONTEXT":
                endpoint_url, model_name = self._resolve_transcription_service_endpoint(
                    document_service=document_service,
                    run=run,
                )
            elif run.engine not in {
                "KRAKEN_LINE",
                "TROCR_LINE",
                "DAN_PAGE",
                "REVIEW_COMPOSED",
            }:
                raise JobValidationError(
                    f"Transcription engine '{run.engine}' is not supported."
                )
        except Exception as error:  # noqa: BLE001
            try:
                document_service._store.fail_transcription_page_result(  # noqa: SLF001
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
                error_code="TRANSCRIPTION_INPUT_RESOLUTION_FAILED",
                error_message=str(error),
            )

        artifacts_by_line_id = {artifact.line_id: artifact for artifact in line_artifacts}
        accepted_rescue_candidates = [
            candidate
            for candidate in rescue_candidates
            if candidate.status in {"ACCEPTED", "RESOLVED"}
        ]
        accepted_rescue_ids = {candidate.id for candidate in accepted_rescue_candidates}

        targets: list[dict[str, object]] = []
        for artifact in sorted(line_artifacts, key=lambda item: item.line_id):
            context_payload: dict[str, object] = {}
            try:
                context_bytes = document_service._storage.read_object_bytes(  # noqa: SLF001
                    artifact.context_window_json_key
                )
                parsed_context = json.loads(context_bytes.decode("utf-8"))
                if isinstance(parsed_context, dict):
                    context_payload = parsed_context
            except Exception:  # noqa: BLE001
                context_payload = {}
            targets.append(
                {
                    "source_kind": "LINE",
                    "source_ref_id": artifact.line_id,
                    "line_id": artifact.line_id,
                    "line_result_id": artifact.line_id,
                    "image_key": artifact.line_crop_key,
                    "context_payload": context_payload,
                    "geometry_json": line_geometry_by_id.get(artifact.line_id) or {},
                }
            )

        for candidate in sorted(accepted_rescue_candidates, key=lambda item: item.id):
            source_kind = (
                "RESCUE_CANDIDATE"
                if candidate.candidate_kind == "LINE_EXPANSION"
                else "PAGE_WINDOW"
            )
            geometry_json = (
                dict(candidate.geometry_json)
                if isinstance(candidate.geometry_json, dict)
                else {}
            )
            referenced_line_id = geometry_json.get("lineId")
            line_id = (
                str(referenced_line_id).strip()
                if isinstance(referenced_line_id, str) and str(referenced_line_id).strip()
                else None
            )
            artifact = artifacts_by_line_id.get(line_id) if line_id is not None else None
            context_payload: dict[str, object] = {}
            image_key = (
                artifact.line_crop_key
                if artifact is not None
                else preprocess_result.output_object_key_gray
            )
            if artifact is not None:
                try:
                    context_bytes = document_service._storage.read_object_bytes(  # noqa: SLF001
                        artifact.context_window_json_key
                    )
                    parsed_context = json.loads(context_bytes.decode("utf-8"))
                    if isinstance(parsed_context, dict):
                        context_payload = parsed_context
                except Exception:  # noqa: BLE001
                    context_payload = {}
            targets.append(
                {
                    "source_kind": source_kind,
                    "source_ref_id": candidate.id,
                    "line_id": line_id,
                    "line_result_id": f"resc:{candidate.id}",
                    "image_key": image_key,
                    "context_payload": context_payload,
                    "geometry_json": geometry_json,
                }
            )

        if not targets:
            try:
                raw_payload = {
                    "schemaVersion": _TRANSCRIPTION_PROMPT_SCHEMA_VERSION,
                    "runId": run_id,
                    "pageId": page_id,
                    "pageIndex": page.page_index,
                    "targets": [],
                    "targetResponses": [],
                    "error": "No transcription targets available for this page.",
                }
                raw_bytes = (
                    json.dumps(raw_payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
                    + b"\n"
                )
                raw_sha = hashlib.sha256(raw_bytes).hexdigest()
                raw_object = document_service._storage.write_transcription_raw_response(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_index=page.page_index,
                    payload=raw_bytes,
                )
                document_service._store.fail_transcription_page_result(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_id=page_id,
                    failure_reason="No transcription targets available for this page.",
                    raw_model_response_key=raw_object.object_key,
                    raw_model_response_sha256=raw_sha,
                    metrics_json={
                        "schemaVersion": _TRANSCRIPTION_PROMPT_SCHEMA_VERSION,
                        "targetCount": 0,
                        "validCount": 0,
                        "invalidCount": 0,
                    },
                    warnings_json=["NO_TRANSCRIPTION_TARGETS"],
                )
            except Exception:  # noqa: BLE001
                pass
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="TRANSCRIPTION_TARGETS_MISSING",
                error_message="No transcription targets available for this page.",
            )

        line_rows: list[dict[str, object]] = []
        token_rows: list[dict[str, object]] = []
        response_rows: list[dict[str, object]] = []
        valid_line_texts: dict[str, str] = {}
        valid_rescue_entries: list[dict[str, object]] = []
        valid_target_records: list[dict[str, object]] = []
        invalid_counts_by_code: dict[str, int] = {}
        valid_count = 0
        invalid_count = 0
        fallback_invocation_count = 0
        alignment_warning_count = 0
        char_box_warning_count = 0
        review_threshold, fallback_threshold = self._resolve_transcription_thresholds(
            run=run
        )

        for target in targets:
            source_kind = str(target["source_kind"])
            source_ref_id = str(target["source_ref_id"])
            line_result_id = str(target["line_result_id"])
            line_id_hint = (
                str(target["line_id"])
                if isinstance(target.get("line_id"), str)
                else None
            )
            image_key = str(target["image_key"])
            target_errors: list[str] = []
            target_warnings: list[str] = []
            service_response: dict[str, object] | None = None
            raw_item: dict[str, object] = {}
            request_payload: dict[str, object] | None = None
            text_diplomatic = ""
            confidence: float | None = None
            confidence_basis = str(run.confidence_basis)
            confidence_signals: dict[str, object] = {}
            confidence_band = "UNKNOWN"
            alignment_payload: dict[str, object] | None = None
            char_boxes_payload: dict[str, object] | None = None
            char_box_cue_preview: list[dict[str, object]] = []
            response_line_id: str | None = None
            try:
                image_payload = document_service._storage.read_object_bytes(image_key)  # noqa: SLF001
                image_data_url = self._encode_image_as_data_url(image_payload)
                request_payload = {
                    "schemaVersion": _TRANSCRIPTION_PROMPT_SCHEMA_VERSION,
                    "responseSchemaVersion": run.response_schema_version,
                    "promptTemplateId": run.prompt_template_id,
                    "target": {
                        "sourceKind": source_kind,
                        "sourceRefId": source_ref_id,
                        "lineId": line_id_hint,
                    },
                    "contextWindow": target.get("context_payload") or {},
                    "geometry": target.get("geometry_json") or {},
                    "params": run.params_json,
                    "imageDataUrl": image_data_url,
                }
                service_response = self._invoke_transcription_engine_adapter(
                    run=run,
                    request_payload=request_payload,
                    endpoint_url=endpoint_url,
                    model_name=model_name,
                    actor_user_id=row.created_by,
                    request_id=f"worker:{worker_id}:{row.id}",
                )
                raw_item = self._extract_structured_transcription_item(
                    response_payload=service_response
                )
                raw_source_kind = raw_item.get("sourceKind")
                if isinstance(raw_source_kind, str) and raw_source_kind.strip():
                    source_kind = raw_source_kind.strip().upper()
                raw_source_ref_id = raw_item.get("sourceRefId")
                if isinstance(raw_source_ref_id, str) and raw_source_ref_id.strip():
                    source_ref_id = raw_source_ref_id.strip()
                raw_line_id = raw_item.get("lineId")
                if isinstance(raw_line_id, str) and raw_line_id.strip():
                    response_line_id = raw_line_id.strip()
                raw_text = raw_item.get("textDiplomatic")
                if not isinstance(raw_text, str):
                    raw_text = raw_item.get("text")
                text_diplomatic = raw_text.strip() if isinstance(raw_text, str) else ""
                if request_payload is not None:
                    confidence, confidence_basis, confidence_signals = (
                        self._compute_line_confidence(
                            run=run,
                            request_payload=request_payload,
                            response_item=raw_item,
                            text_diplomatic=text_diplomatic,
                            actor_user_id=row.created_by,
                            request_id=f"worker:{worker_id}:{row.id}",
                            endpoint_url=endpoint_url,
                            model_name=model_name,
                        )
                    )
                alignment_payload, alignment_warnings = self._build_compact_alignment_payload(
                    response_item=raw_item,
                    line_id_hint=line_id_hint,
                )
                for warning in alignment_warnings:
                    if warning not in target_warnings:
                        target_warnings.append(warning)
                alignment_warning_count += len(alignment_warnings)
                (
                    char_boxes_payload,
                    char_box_cue_preview,
                    char_boxes_malformed,
                ) = self._build_compact_char_boxes_payload(
                    response_item=raw_item,
                    text_diplomatic=text_diplomatic,
                )
                if char_boxes_malformed:
                    target_warnings.append("MALFORMED_CHAR_BOXES")
                    char_box_warning_count += 1
                confidence_band = self._resolve_confidence_band(
                    confidence=confidence,
                    review_threshold=review_threshold,
                    fallback_threshold=fallback_threshold,
                )
                if confidence_signals.get("fallbackSignalApplied") is True:
                    fallback_invocation_count += 1
            except OutboundRequestBlockedError as error:
                target_errors.append(f"OUTBOUND_BLOCKED:{error.code}")
            except Exception as error:  # noqa: BLE001
                target_errors.append(
                    f"SERVICE_CALL_FAILED:{error.__class__.__name__}"
                )

            target_geometry = (
                dict(target["geometry_json"])
                if isinstance(target.get("geometry_json"), dict)
                else {}
            )
            normalized_bbox_json: dict[str, object] | None = None
            normalized_polygon_json: dict[str, object] | None = None
            if target_geometry:
                normalized_bbox_json, normalized_polygon_json = self._normalize_token_geometry(
                    geometry_json=target_geometry,
                    page_width=page_width,
                    page_height=page_height,
                )
                if normalized_bbox_json is None or normalized_polygon_json is None:
                    target_errors.append("INVALID_GEOMETRY")
            elif source_kind != "LINE":
                target_errors.append("INVALID_RESCUE_GEOMETRY")

            if source_kind not in {"LINE", "RESCUE_CANDIDATE", "PAGE_WINDOW"}:
                target_errors.append("INVALID_SOURCE_KIND")
            if text_diplomatic == "":
                target_errors.append("EMPTY_TEXT")
            if source_kind == "LINE":
                if source_ref_id not in artifacts_by_line_id:
                    target_errors.append("UNKNOWN_LINE_ANCHOR")
                if response_line_id is not None and response_line_id != source_ref_id:
                    target_errors.append("LINE_ID_ANCHOR_MISMATCH")
            else:
                if source_ref_id not in accepted_rescue_ids:
                    target_errors.append("UNKNOWN_RESCUE_ANCHOR")
                if response_line_id is not None and response_line_id not in artifacts_by_line_id:
                    target_errors.append("UNKNOWN_LINE_REFERENCE")

            if target_errors:
                invalid_count += 1
                for code in target_errors:
                    invalid_counts_by_code[code] = invalid_counts_by_code.get(code, 0) + 1
            else:
                valid_count += 1
                if source_kind == "LINE":
                    valid_line_texts[source_ref_id] = text_diplomatic
                else:
                    valid_rescue_entries.append(
                        {
                            "line_id": line_result_id,
                            "text_diplomatic": text_diplomatic,
                            "source_kind": source_kind,
                            "source_ref_id": source_ref_id,
                            "geometry_json": target_geometry,
                        }
                    )
                token_line_id: str | None
                if source_kind == "LINE":
                    token_line_id = source_ref_id
                elif line_id_hint is not None and line_id_hint in artifacts_by_line_id:
                    token_line_id = line_id_hint
                else:
                    token_line_id = None
                valid_target_records.append(
                    {
                        "line_result_id": line_result_id,
                        "source_kind": source_kind,
                        "source_ref_id": source_ref_id,
                        "line_id": token_line_id,
                        "text_diplomatic": text_diplomatic,
                        "token_confidence": confidence,
                        "bbox_json": normalized_bbox_json,
                        "polygon_json": normalized_polygon_json,
                    }
                )

            line_machine_payload = {
                "target": {
                    "sourceKind": str(target["source_kind"]),
                    "sourceRefId": str(target["source_ref_id"]),
                    "lineId": line_id_hint,
                },
                "response": raw_item,
                "serviceResponse": service_response,
                "validationErrors": target_errors,
                "validationWarnings": target_warnings,
                "confidence": {
                    "basis": confidence_basis,
                    "value": confidence,
                    "band": confidence_band,
                    "signals": confidence_signals,
                },
            }
            machine_output_sha = hashlib.sha256(
                json.dumps(
                    line_machine_payload,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            version_etag = hashlib.sha256(
                f"{run_id}|{page_id}|{line_result_id}|{machine_output_sha}".encode("utf-8")
            ).hexdigest()
            line_rows.append(
                {
                    "line_id": line_result_id,
                    "text_diplomatic": text_diplomatic if not target_errors else "",
                    "conf_line": confidence if not target_errors else None,
                    "confidence_band": confidence_band if not target_errors else "UNKNOWN",
                    "confidence_basis": confidence_basis,
                    "confidence_calibration_version": run.confidence_calibration_version,
                    "alignment_json_key": None,
                    "char_boxes_key": None,
                    "schema_validation_status": (
                        "VALID" if not target_errors else "INVALID"
                    ),
                    "flags_json": {
                        "sourceKind": source_kind,
                        "sourceRefId": source_ref_id,
                        "lineIdHint": line_id_hint,
                        "responseLineId": response_line_id,
                        "validationErrors": target_errors,
                        "validationWarnings": target_warnings,
                        "confidenceSignals": confidence_signals,
                        "charBoxesStatus": (
                            "AVAILABLE"
                            if char_boxes_payload is not None
                            else (
                                "MALFORMED"
                                if "MALFORMED_CHAR_BOXES" in target_warnings
                                else "UNAVAILABLE"
                            )
                        ),
                        "charBoxCuePreview": char_box_cue_preview,
                    },
                    "alignment_payload": alignment_payload,
                    "char_boxes_payload": char_boxes_payload,
                    "machine_output_sha256": machine_output_sha,
                    "active_transcript_version_id": None,
                    "version_etag": version_etag,
                    "token_anchor_status": "REFRESH_REQUIRED",
                }
            )
            response_rows.append(
                {
                    "target": {
                        "sourceKind": str(target["source_kind"]),
                        "sourceRefId": str(target["source_ref_id"]),
                        "lineId": line_id_hint,
                    },
                    "response": raw_item,
                    "serviceResponse": service_response,
                    "validationErrors": target_errors,
                    "validationWarnings": target_warnings,
                }
            )

        tokenized_line_result_ids: set[str] = set()
        page_token_index = 0
        for target_record in valid_target_records:
            source_kind = str(target_record["source_kind"])
            source_ref_id = str(target_record["source_ref_id"])
            token_line_id = (
                str(target_record["line_id"])
                if isinstance(target_record.get("line_id"), str)
                and str(target_record["line_id"]).strip()
                else None
            )
            text_diplomatic = str(target_record["text_diplomatic"])
            token_confidence = (
                float(target_record["token_confidence"])
                if isinstance(target_record.get("token_confidence"), (int, float))
                else None
            )
            token_spans = self._tokenize_transcription_text(text_diplomatic)
            if not token_spans:
                continue
            for token_text, token_start, token_end in token_spans:
                token_id = self._build_token_anchor_id(
                    run_id=run_id,
                    page_id=page_id,
                    source_kind=source_kind,
                    source_ref_id=source_ref_id,
                    line_id=token_line_id,
                    token_index=page_token_index,
                    token_start=token_start,
                    token_end=token_end,
                    token_text=token_text,
                )
                token_rows.append(
                    {
                        "line_id": token_line_id,
                        "token_id": token_id,
                        "token_index": page_token_index,
                        "token_text": token_text,
                        "token_confidence": token_confidence,
                        "bbox_json": target_record.get("bbox_json"),
                        "polygon_json": target_record.get("polygon_json"),
                        "source_kind": source_kind,
                        "source_ref_id": source_ref_id,
                        "projection_basis": "ENGINE_OUTPUT",
                    }
                )
                page_token_index += 1
            tokenized_line_result_ids.add(str(target_record["line_result_id"]))

        for row_payload in line_rows:
            if row_payload["schema_validation_status"] != "VALID":
                continue
            line_result_id = str(row_payload["line_id"])
            row_payload["token_anchor_status"] = (
                "CURRENT" if line_result_id in tokenized_line_result_ids else "REFRESH_REQUIRED"
            )

        missing_anchor_line_ids = [
            str(row_payload["line_id"])
            for row_payload in line_rows
            if row_payload["schema_validation_status"] == "VALID"
            and row_payload["token_anchor_status"] != "CURRENT"
        ]
        if missing_anchor_line_ids:
            invalid_counts_by_code["TOKEN_ANCHOR_MATERIALIZATION_FAILED"] = len(
                missing_anchor_line_ids
            )
        anchor_materialization_failure_count = len(missing_anchor_line_ids)
        total_invalid_count = invalid_count + anchor_materialization_failure_count
        token_id_count = len({str(row["token_id"]) for row in token_rows})
        if str(run.engine) in {"KRAKEN_LINE", "TROCR_LINE", "DAN_PAGE", "REVIEW_COMPOSED"}:
            fallback_invocation_count = max(fallback_invocation_count, len(targets))
        confidence_band_counts = {
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "UNKNOWN": 0,
        }
        low_confidence_line_count = 0
        for line_payload in line_rows:
            confidence_band = (
                str(line_payload.get("confidence_band") or "UNKNOWN")
                if isinstance(line_payload.get("confidence_band"), str)
                else "UNKNOWN"
            )
            if confidence_band not in confidence_band_counts:
                confidence_band = "UNKNOWN"
            confidence_band_counts[confidence_band] += 1
            line_confidence = line_payload.get("conf_line")
            if isinstance(line_confidence, (int, float)) and float(line_confidence) < review_threshold:
                low_confidence_line_count += 1

        raw_page_payload = {
            "schemaVersion": _TRANSCRIPTION_PROMPT_SCHEMA_VERSION,
            "runId": run_id,
            "pageId": page_id,
            "pageIndex": page.page_index,
            "responseSchemaVersion": run.response_schema_version,
            "promptTemplateId": run.prompt_template_id,
            "targetResponses": response_rows,
            "summary": {
                "targetCount": len(targets),
                "validCount": valid_count,
                "invalidCount": total_invalid_count,
                "invalidTargetCount": invalid_count,
                "invalidByCode": invalid_counts_by_code,
                "tokenCount": len(token_rows),
                "lowConfidenceLineCount": low_confidence_line_count,
                "confidenceBands": confidence_band_counts,
                "fallbackInvocationCount": fallback_invocation_count,
            },
        }
        raw_page_bytes = (
            json.dumps(
                raw_page_payload,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
        raw_page_sha256 = hashlib.sha256(raw_page_bytes).hexdigest()

        warnings: list[str] = []
        if total_invalid_count > 0:
            warnings.append("SCHEMA_VALIDATION_FAILED")
        if anchor_materialization_failure_count > 0:
            warnings.append("TOKEN_ANCHOR_MATERIALIZATION_FAILED")
        if alignment_warning_count > 0:
            warnings.append("ALIGNMENT_WARNINGS_PRESENT")
        if char_box_warning_count > 0:
            warnings.append("CHAR_BOX_WARNINGS_PRESENT")
        metrics = {
            "schemaVersion": _TRANSCRIPTION_PROMPT_SCHEMA_VERSION,
            "targetCount": len(targets),
            "validCount": valid_count,
            "invalidCount": total_invalid_count,
            "invalidTargetCount": invalid_count,
            "invalidByCode": invalid_counts_by_code,
            "tokenCount": len(token_rows),
            "tokenIdCount": token_id_count,
            "anchorRefreshRequiredCount": anchor_materialization_failure_count,
            "lineArtifactCount": len(line_artifacts),
            "acceptedRescueCandidateCount": len(accepted_rescue_candidates),
            "reviewConfidenceThreshold": review_threshold,
            "fallbackConfidenceThreshold": fallback_threshold,
            "lowConfidenceLineCount": low_confidence_line_count,
            "confidenceBands": confidence_band_counts,
            "fallbackInvocationCount": fallback_invocation_count,
            "alignmentWarningCount": alignment_warning_count,
            "charBoxWarningCount": char_box_warning_count,
        }

        try:
            raw_response_object = document_service._storage.write_transcription_raw_response(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_index=page.page_index,
                payload=raw_page_bytes,
            )
            for row_payload in line_rows:
                safe_line_id = self._safe_xml_identifier(str(row_payload["line_id"]))
                alignment_payload = row_payload.pop("alignment_payload", None)
                if isinstance(alignment_payload, dict):
                    alignment_bytes = (
                        json.dumps(
                            alignment_payload,
                            ensure_ascii=True,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                        + b"\n"
                    )
                    alignment_object = (
                        document_service._storage.write_transcription_line_alignment(  # noqa: SLF001
                            project_id=project_id,
                            document_id=document_id,
                            run_id=run_id,
                            page_index=page.page_index,
                            line_id=safe_line_id,
                            payload=alignment_bytes,
                        )
                    )
                    row_payload["alignment_json_key"] = alignment_object.object_key
                else:
                    row_payload["alignment_json_key"] = None

                char_boxes_payload = row_payload.pop("char_boxes_payload", None)
                if isinstance(char_boxes_payload, dict):
                    char_boxes_bytes = (
                        json.dumps(
                            char_boxes_payload,
                            ensure_ascii=True,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                        + b"\n"
                    )
                    char_boxes_object = (
                        document_service._storage.write_transcription_line_char_boxes(  # noqa: SLF001
                            project_id=project_id,
                            document_id=document_id,
                            run_id=run_id,
                            page_index=page.page_index,
                            line_id=safe_line_id,
                            payload=char_boxes_bytes,
                        )
                    )
                    row_payload["char_boxes_key"] = char_boxes_object.object_key
                else:
                    row_payload["char_boxes_key"] = None

            document_service._store.replace_line_transcription_results(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                rows=line_rows,
            )
            document_service._store.replace_token_transcription_results(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                rows=token_rows,
            )
            line_anchor_targets = [target for target in targets if target["source_kind"] == "LINE"]
            if line_anchor_targets and not valid_line_texts:
                raise JobValidationError("No valid line-level transcription outputs were produced.")
            if token_id_count != len(token_rows):
                raise JobValidationError("Token anchor ID collision detected for this page.")
            if anchor_materialization_failure_count > 0:
                raise JobValidationError(
                    "Token-anchor materialization failed for one or more validated outputs."
                )
            if invalid_count > 0:
                raise JobValidationError(
                    "Structured output validation failed for one or more transcription targets."
                )

            pagexml_payload = self._build_transcription_pagexml(
                layout_pagexml_bytes=layout_pagexml_bytes,
                line_text_by_line_id=valid_line_texts,
                rescue_entries=valid_rescue_entries,
            )
            pagexml_sha256 = hashlib.sha256(pagexml_payload).hexdigest()
            pagexml_object = document_service._storage.write_transcription_page_xml(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_index=page.page_index,
                payload=pagexml_payload,
            )
            hocr_out_key: str | None = None
            hocr_out_sha256: str | None = None
            if self._engine_emits_hocr(str(run.engine)):
                hocr_payload = self._build_fallback_hocr_payload(
                    engine=str(run.engine),
                    page_index=page.page_index,
                    line_text_by_line_id=valid_line_texts,
                    rescue_entries=valid_rescue_entries,
                )
                hocr_out_sha256 = hashlib.sha256(hocr_payload).hexdigest()
                hocr_object = document_service._storage.write_transcription_hocr(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_index=page.page_index,
                    payload=hocr_payload,
                )
                hocr_out_key = hocr_object.object_key

            corrected_text_sha = hashlib.sha256(
                "\n".join(
                    sorted(
                        value
                        for value in [line.text_diplomatic for line in document_service._store.list_line_transcription_results(  # noqa: SLF001,E501
                            project_id=project_id,
                            document_id=document_id,
                            run_id=run_id,
                            page_id=page_id,
                        )]
                        if value
                    )
                ).encode("utf-8")
            ).hexdigest()

            document_service._store.complete_transcription_page_result(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                pagexml_out_key=pagexml_object.object_key,
                pagexml_out_sha256=pagexml_sha256,
                raw_model_response_key=raw_response_object.object_key,
                raw_model_response_sha256=raw_page_sha256,
                metrics_json=metrics,
                warnings_json=warnings,
                hocr_out_key=hocr_out_key,
                hocr_out_sha256=hocr_out_sha256,
            )
            source_pagexml_sha256 = (
                layout_page_result.page_xml_sha256
                if isinstance(layout_page_result.page_xml_sha256, str)
                and layout_page_result.page_xml_sha256
                else hashlib.sha256(layout_pagexml_bytes).hexdigest()
            )
            document_service._store.upsert_transcription_output_projection(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                corrected_pagexml_key=pagexml_object.object_key,
                corrected_pagexml_sha256=pagexml_sha256,
                corrected_text_sha256=corrected_text_sha,
                source_pagexml_sha256=source_pagexml_sha256,
            )
        except Exception as error:  # noqa: BLE001
            try:
                document_service._store.fail_transcription_page_result(  # noqa: SLF001
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_id=page_id,
                    failure_reason=str(error),
                    raw_model_response_key=(
                        raw_response_object.object_key
                        if "raw_response_object" in locals()
                        else None
                    ),
                    raw_model_response_sha256=raw_page_sha256,
                    metrics_json=metrics,
                    warnings_json=warnings,
                )
            except Exception:  # noqa: BLE001
                pass
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="TRANSCRIPTION_PAGE_FAILED",
                error_message=str(error),
            )

        return self.finish_running_job(
            job_id=row.id,
            worker_id=worker_id,
            success=True,
        )

    def _process_finalize_transcription_run_job(
        self,
        *,
        worker_id: str,
        row: JobRecord,
    ) -> JobRecord:
        from app.documents.service import get_document_service

        try:
            project_id, document_id, run_id, _ = self._resolve_transcription_job_payload(row)
        except JobValidationError as error:
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="INVALID_TRANSCRIPTION_JOB_PAYLOAD",
                error_message=str(error),
            )

        document_service = get_document_service()
        try:
            finalized_run = document_service._store.finalize_transcription_run(  # noqa: SLF001
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except Exception as error:  # noqa: BLE001
            return self.finish_running_job(
                job_id=row.id,
                worker_id=worker_id,
                success=False,
                error_code="TRANSCRIPTION_FINALIZE_FAILED",
                error_message=str(error),
            )

        if finalized_run.status == "SUCCEEDED":
            self._audit_service.record_event_best_effort(
                event_type="TRANSCRIPTION_RUN_FINISHED",
                actor_user_id=finalized_run.created_by,
                project_id=project_id,
                object_type="transcription_run",
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
                event_type="TRANSCRIPTION_RUN_FAILED",
                actor_user_id=finalized_run.created_by,
                project_id=project_id,
                object_type="transcription_run",
                object_id=run_id,
                metadata={
                    "run_id": run_id,
                    "document_id": document_id,
                    "reason": finalized_run.failure_reason
                    or "Transcription run failed.",
                },
                request_id=f"worker:{worker_id}:{row.id}",
            )
        elif finalized_run.status == "CANCELED":
            self._audit_service.record_event_best_effort(
                event_type="TRANSCRIPTION_RUN_CANCELED",
                actor_user_id=finalized_run.created_by,
                project_id=project_id,
                object_type="transcription_run",
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
