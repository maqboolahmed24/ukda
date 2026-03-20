from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.documents.models import (
    DocumentPageRecord,
    LayoutRunRecord,
    PageLayoutResultRecord,
    PagePreprocessResultRecord,
)
from app.jobs.models import JobEventRecord, JobRecord
from app.jobs.service import JobService


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeTelemetryService:
    def record_queue_depth(self, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def record_job_claimed(self, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def record_job_completed(self, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def record_gpu_utilization(self, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def record_storage_operation(self, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def record_model_request(self, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def record_export_review_latency(self, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def record_timeline(self, **kwargs):  # type: ignore[no-untyped-def]
        return None


class FakeProjectService:
    def resolve_workspace_context(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("Project service should not be used in worker-only tests.")


class InMemoryJobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, JobRecord] = {}
        self.events: list[JobEventRecord] = []
        self._event_id = 1

    @staticmethod
    def compute_dedupe_key(*, project_id: str, job_type: str, logical_key: str) -> str:
        payload = f"{project_id}|{job_type}|{logical_key}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

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
        for row in self.jobs.values():
            if (
                row.project_id == project_id
                and row.dedupe_key == dedupe_key
                and row.superseded_by_job_id is None
                and row.status in {"QUEUED", "RUNNING"}
            ):
                return row, False, "IN_FLIGHT"
        for row in self.jobs.values():
            if (
                row.project_id == project_id
                and row.dedupe_key == dedupe_key
                and row.superseded_by_job_id is None
                and row.status == "SUCCEEDED"
            ):
                return row, False, "SUCCEEDED"

        attempt_number = 1
        if supersedes_job_id is not None:
            supersedes = self.jobs[supersedes_job_id]
            attempt_number = supersedes.attempt_number + 1
        now = datetime.now(UTC)
        row = JobRecord(
            id=str(uuid4()),
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
            created_at=now,
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
            supersedes = self.jobs[supersedes_job_id]
            self.jobs[supersedes_job_id] = replace(
                supersedes,
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

    def claim_next_job(self, *, worker_id: str, lease_seconds: int) -> JobRecord | None:
        queued = sorted(
            [row for row in self.jobs.values() if row.status == "QUEUED"],
            key=lambda row: row.created_at,
        )
        if not queued:
            return None
        now = datetime.now(UTC)
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
        if current is None or current.status != "RUNNING" or current.lease_owner_id != worker_id:
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
        del worker_id
        current = self.jobs[job_id]
        now = datetime.now(UTC)
        if success:
            next_row = replace(
                current,
                status="SUCCEEDED",
                finished_at=now,
                lease_owner_id=None,
                lease_expires_at=None,
                last_heartbeat_at=None,
            )
            self.jobs[job_id] = next_row
            self._append_event(
                job_id=job_id,
                project_id=current.project_id,
                event_type="JOB_SUCCEEDED",
                from_status="RUNNING",
                to_status="SUCCEEDED",
                actor_user_id=None,
            )
            return next_row

        next_row = replace(
            current,
            status="FAILED",
            finished_at=now,
            error_code=error_code,
            error_message=error_message,
            lease_owner_id=None,
            lease_expires_at=None,
            last_heartbeat_at=None,
        )
        self.jobs[job_id] = next_row
        self._append_event(
            job_id=job_id,
            project_id=current.project_id,
            event_type="JOB_FAILED",
            from_status="RUNNING",
            to_status="FAILED",
            actor_user_id=None,
        )
        return next_row

    def count_open_jobs(self) -> int:
        return sum(1 for row in self.jobs.values() if row.status == "QUEUED")

    def project_job_activity(self, *, project_id: str) -> tuple[int, str | None]:
        rows = [row for row in self.jobs.values() if row.project_id == project_id]
        if not rows:
            return 0, None
        running = sum(1 for row in rows if row.status == "RUNNING")
        latest = sorted(rows, key=lambda row: row.created_at, reverse=True)[0]
        return running, latest.status


class InMemoryLayoutStore:
    def __init__(
        self,
        *,
        preprocess_image_key: str,
        initial_run_status: str = "QUEUED",
        initial_page_status: str = "QUEUED",
    ) -> None:
        now = datetime.now(UTC)
        self.run = LayoutRunRecord(
            id="layout-run-1",
            project_id="project-1",
            document_id="doc-1",
            input_preprocess_run_id="pre-run-1",
            run_kind="AUTO",
            parent_run_id=None,
            attempt_number=1,
            superseded_by_run_id=None,
            model_id="layout-rule-v1",
            profile_id="DEFAULT",
            params_json={},
            params_hash="layout-hash",
            pipeline_version="layout-v1",
            container_digest="ukde/layout:v1",
            status=initial_run_status,  # type: ignore[arg-type]
            created_by="user-worker",
            created_at=now,
            started_at=None,
            finished_at=None,
            failure_reason=None,
        )
        self.page = DocumentPageRecord(
            id="page-1",
            document_id="doc-1",
            page_index=0,
            width=1000,
            height=1400,
            dpi=300,
            source_width=1000,
            source_height=1400,
            source_dpi=300,
            source_color_mode="GRAY",
            status="READY",
            derived_image_key="controlled/derived/project-1/doc-1/pages/0.png",
            derived_image_sha256=None,
            thumbnail_key=None,
            thumbnail_sha256=None,
            failure_reason=None,
            canceled_by=None,
            canceled_at=None,
            viewer_rotation=0,
            created_at=now,
            updated_at=now,
        )
        self.preprocess_result = PagePreprocessResultRecord(
            run_id="pre-run-1",
            page_id="page-1",
            page_index=0,
            status="SUCCEEDED",
            quality_gate_status="PASS",
            input_object_key=self.page.derived_image_key,
            output_object_key_gray=preprocess_image_key,
            output_object_key_bin=None,
            metrics_json={},
            sha256_gray="input-sha",
            sha256_bin=None,
            warnings_json=[],
            failure_reason=None,
            created_at=now,
            updated_at=now,
        )
        self.page_result = PageLayoutResultRecord(
            run_id="layout-run-1",
            page_id="page-1",
            page_index=0,
            status=initial_page_status,  # type: ignore[arg-type]
            page_recall_status="NEEDS_MANUAL_REVIEW",
            active_layout_version_id=None,
            page_xml_key=None,
            overlay_json_key=None,
            page_xml_sha256=None,
            overlay_json_sha256=None,
            metrics_json={},
            warnings_json=[],
            failure_reason=None,
            created_at=now,
            updated_at=now,
        )

    def get_layout_run(self, **kwargs):  # type: ignore[no-untyped-def]
        if (
            kwargs["project_id"] != self.run.project_id
            or kwargs["document_id"] != self.run.document_id
            or kwargs["run_id"] != self.run.id
        ):
            return None
        return self.run

    def mark_layout_run_running(self, **kwargs):  # type: ignore[no-untyped-def]
        if kwargs["run_id"] != self.run.id:
            raise RuntimeError("run not found")
        if self.run.status == "QUEUED":
            self.run = replace(
                self.run,
                status="RUNNING",
                started_at=self.run.started_at or datetime.now(UTC),
            )
            if self.page_result.status == "QUEUED":
                self.page_result = replace(self.page_result, status="RUNNING")
        return self.run

    def list_page_layout_results(self, **kwargs):  # type: ignore[no-untyped-def]
        if kwargs["run_id"] != self.run.id:
            raise RuntimeError("run not found")
        return [self.page_result], None

    def mark_layout_page_running(self, **kwargs):  # type: ignore[no-untyped-def]
        if kwargs["page_id"] != self.page_result.page_id:
            raise RuntimeError("page not found")
        if self.page_result.status in {"QUEUED", "RUNNING"}:
            self.page_result = replace(
                self.page_result,
                status="RUNNING",
                updated_at=datetime.now(UTC),
            )
        return self.page_result

    def get_document_page(self, **kwargs):  # type: ignore[no-untyped-def]
        if kwargs["page_id"] != self.page.id:
            return None
        return self.page

    def get_preprocess_page_result(self, **kwargs):  # type: ignore[no-untyped-def]
        if (
            kwargs["run_id"] != self.preprocess_result.run_id
            or kwargs["page_id"] != self.preprocess_result.page_id
        ):
            return None
        return self.preprocess_result

    def complete_layout_page_result(self, **kwargs):  # type: ignore[no-untyped-def]
        self.page_result = replace(
            self.page_result,
            status="SUCCEEDED",
            page_recall_status=kwargs["page_recall_status"],
            page_xml_key=kwargs["page_xml_key"],
            overlay_json_key=kwargs["overlay_json_key"],
            page_xml_sha256=kwargs["page_xml_sha256"],
            overlay_json_sha256=kwargs["overlay_json_sha256"],
            metrics_json=dict(kwargs["metrics_json"]),
            warnings_json=list(kwargs["warnings_json"]),
            failure_reason=None,
            updated_at=datetime.now(UTC),
        )
        return self.page_result

    def fail_layout_page_result(self, **kwargs):  # type: ignore[no-untyped-def]
        self.page_result = replace(
            self.page_result,
            status="FAILED",
            failure_reason=str(kwargs["failure_reason"]),
            updated_at=datetime.now(UTC),
        )
        return self.page_result

    def finalize_layout_run(self, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        now = datetime.now(UTC)
        if self.run.status == "CANCELED":
            self.run = replace(self.run, finished_at=now)
            return self.run
        if self.page_result.status == "FAILED":
            self.run = replace(
                self.run,
                status="FAILED",
                started_at=self.run.started_at or now,
                finished_at=now,
                failure_reason="One or more layout page tasks failed.",
            )
            return self.run
        if self.page_result.status == "CANCELED":
            self.run = replace(
                self.run,
                status="CANCELED",
                started_at=self.run.started_at or now,
                finished_at=now,
                failure_reason="Run completed with canceled pages.",
            )
            return self.run
        if self.page_result.status == "SUCCEEDED":
            self.run = replace(
                self.run,
                status="SUCCEEDED",
                started_at=self.run.started_at or now,
                finished_at=now,
                failure_reason=None,
            )
            return self.run
        self.run = replace(self.run, status="RUNNING", started_at=self.run.started_at or now)
        return self.run


class InMemoryStorage:
    def __init__(self, *, payload_by_key: dict[str, bytes]) -> None:
        self._payload_by_key = dict(payload_by_key)

    def read_object_bytes(self, object_key: str) -> bytes:
        return self._payload_by_key[object_key]


class FakeDocumentService:
    def __init__(self, *, store: InMemoryLayoutStore, storage: InMemoryStorage) -> None:
        self._store = store
        self._storage = storage

    def materialize_layout_page_outputs(self, **kwargs):  # type: ignore[no-untyped-def]
        project_id = kwargs["project_id"]
        document_id = kwargs["document_id"]
        run_id = kwargs["run_id"]
        page_id = kwargs["page_id"]
        payload = kwargs["canonical_page_payload"]
        page_index = int(payload["pageIndex"])
        page_xml_key = (
            f"controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}.xml"
        )
        overlay_key = (
            f"controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}.json"
        )
        page_xml_sha256 = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        overlay_sha256 = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return self._store.complete_layout_page_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            page_xml_key=page_xml_key,
            overlay_json_key=overlay_key,
            page_xml_sha256=page_xml_sha256,
            overlay_json_sha256=overlay_sha256,
            metrics_json=kwargs.get("metrics_json") or {},
            warnings_json=kwargs.get("warnings_json") or [],
            page_recall_status=kwargs["page_recall_status"],
        )


def _render_preprocess_page_bytes() -> bytes:
    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError as error:  # pragma: no cover - dependency guard
        raise RuntimeError("Pillow is required for layout job tests.") from error
    image = Image.new("L", (1000, 1400), color=245)
    draw = ImageDraw.Draw(image)
    for row in range(12):
        y0 = 120 + (row * 46)
        y1 = y0 + 14
        draw.rectangle((90, y0, 430, y1), fill=18)
        draw.rectangle((570, y0, 910, y1), fill=18)
    payload = BytesIO()
    image.save(payload, format="PNG", optimize=False, compress_level=9)
    return payload.getvalue()


def _drain_worker(job_service: JobService, *, max_iterations: int = 20) -> list[JobRecord]:
    completed: list[JobRecord] = []
    for _ in range(max_iterations):
        result = job_service.run_worker_once(worker_id="worker-layout", lease_seconds=30)
        if result is None:
            break
        completed.append(result)
    return completed


@pytest.fixture
def layout_worker_fixture(monkeypatch: pytest.MonkeyPatch):
    preprocess_key = "controlled/derived/project-1/doc-1/preprocess/pre-run-1/gray/0.png"
    store = InMemoryLayoutStore(preprocess_image_key=preprocess_key)
    storage = InMemoryStorage(payload_by_key={preprocess_key: _render_preprocess_page_bytes()})
    fake_document_service = FakeDocumentService(store=store, storage=storage)
    monkeypatch.setattr(
        "app.documents.service.get_document_service",
        lambda: fake_document_service,
    )

    audit = SpyAuditService()
    job_store = InMemoryJobStore()
    job_service = JobService(
        settings=get_settings(),
        store=job_store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        audit_service=audit,  # type: ignore[arg-type]
        telemetry_service=FakeTelemetryService(),  # type: ignore[arg-type]
    )
    return job_service, job_store, store, audit


def test_layout_worker_pipeline_runs_document_page_finalize(layout_worker_fixture) -> None:
    job_service, _, layout_store, audit = layout_worker_fixture

    job_service.enqueue_layout_document_job(
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        created_by="user-worker",
    )
    completed = _drain_worker(job_service)
    completed_types = {row.type for row in completed}

    assert {
        "LAYOUT_ANALYZE_DOCUMENT",
        "LAYOUT_ANALYZE_PAGE",
        "FINALIZE_LAYOUT_RUN",
    }.issubset(completed_types)
    assert layout_store.run.status == "SUCCEEDED"
    assert layout_store.page_result.status == "SUCCEEDED"
    assert layout_store.page_result.page_xml_key is not None
    assert layout_store.page_result.overlay_json_key is not None
    assert layout_store.page_result.page_recall_status in {
        "COMPLETE",
        "NEEDS_RESCUE",
        "NEEDS_MANUAL_REVIEW",
    }

    event_types = [str(event["event_type"]) for event in audit.recorded]
    assert "LAYOUT_RUN_STARTED" in event_types
    assert "LAYOUT_RUN_FINISHED" in event_types


def test_layout_page_job_enqueue_is_idempotent_after_success(layout_worker_fixture) -> None:
    job_service, _, layout_store, _ = layout_worker_fixture

    job_service.enqueue_layout_document_job(
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        created_by="user-worker",
    )
    _drain_worker(job_service)
    row, created, reason = job_service._enqueue_layout_page_job(
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        page_index=0,
        created_by="user-worker",
    )

    assert not created
    assert reason == "SUCCEEDED"
    assert row.status == "SUCCEEDED"
    assert layout_store.page_result.status == "SUCCEEDED"


def test_canceled_layout_run_stops_page_scheduling(monkeypatch: pytest.MonkeyPatch) -> None:
    preprocess_key = "controlled/derived/project-1/doc-1/preprocess/pre-run-1/gray/0.png"
    layout_store = InMemoryLayoutStore(
        preprocess_image_key=preprocess_key,
        initial_run_status="CANCELED",
        initial_page_status="CANCELED",
    )
    storage = InMemoryStorage(payload_by_key={preprocess_key: _render_preprocess_page_bytes()})
    fake_document_service = FakeDocumentService(store=layout_store, storage=storage)
    monkeypatch.setattr(
        "app.documents.service.get_document_service",
        lambda: fake_document_service,
    )

    audit = SpyAuditService()
    job_store = InMemoryJobStore()
    job_service = JobService(
        settings=get_settings(),
        store=job_store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        audit_service=audit,  # type: ignore[arg-type]
        telemetry_service=FakeTelemetryService(),  # type: ignore[arg-type]
    )
    job_service.enqueue_layout_document_job(
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        created_by="user-worker",
    )
    completed = _drain_worker(job_service)
    completed_types = {row.type for row in completed}

    assert completed_types == {"LAYOUT_ANALYZE_DOCUMENT"}
    assert layout_store.run.status == "CANCELED"
