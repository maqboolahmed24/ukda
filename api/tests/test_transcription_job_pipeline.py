from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.documents.models import (
    ApprovedModelRecord,
    DocumentPageRecord,
    LayoutLineArtifactRecord,
    LayoutRescueCandidateRecord,
    LineTranscriptionResultRecord,
    PageLayoutResultRecord,
    PagePreprocessResultRecord,
    PageTranscriptionResultRecord,
    TokenTranscriptionResultRecord,
    TranscriptionOutputProjectionRecord,
    TranscriptionRunRecord,
)
from app.jobs.models import JobEventRecord, JobRecord
from app.jobs.service import JobService
from app.security.outbound import OutboundRequestBlockedError


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


@dataclass(frozen=True)
class StoredObjectRef:
    object_key: str


class InMemoryStorage:
    def __init__(self, *, payload_by_key: dict[str, bytes]) -> None:
        self.payload_by_key = dict(payload_by_key)

    def read_object_bytes(self, object_key: str) -> bytes:
        payload = self.payload_by_key.get(object_key)
        if payload is None:
            raise RuntimeError(f"Missing payload for key: {object_key}")
        return payload

    def _write_immutable(self, *, object_key: str, payload: bytes) -> StoredObjectRef:
        current = self.payload_by_key.get(object_key)
        if current is not None and current != payload:
            raise RuntimeError("Immutable object payload mismatch.")
        self.payload_by_key[object_key] = payload
        return StoredObjectRef(object_key=object_key)

    def write_transcription_page_xml(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        payload: bytes,
    ) -> StoredObjectRef:
        return self._write_immutable(
            object_key=(
                f"controlled/derived/{project_id}/{document_id}/transcription/"
                f"{run_id}/page/{page_index}.xml"
            ),
            payload=payload,
        )

    def write_transcription_raw_response(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        payload: bytes,
    ) -> StoredObjectRef:
        return self._write_immutable(
            object_key=(
                f"controlled/derived/{project_id}/{document_id}/transcription/"
                f"{run_id}/page/{page_index}.response.json"
            ),
            payload=payload,
        )

    def write_transcription_hocr(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        payload: bytes,
    ) -> StoredObjectRef:
        return self._write_immutable(
            object_key=(
                f"controlled/derived/{project_id}/{document_id}/transcription/"
                f"{run_id}/page/{page_index}.hocr"
            ),
            payload=payload,
        )

    def write_transcription_line_alignment(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
        payload: bytes,
    ) -> StoredObjectRef:
        return self._write_immutable(
            object_key=(
                f"controlled/derived/{project_id}/{document_id}/transcription/"
                f"{run_id}/page/{page_index}/lines/{line_id}.alignment.json"
            ),
            payload=payload,
        )

    def write_transcription_line_char_boxes(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
        payload: bytes,
    ) -> StoredObjectRef:
        return self._write_immutable(
            object_key=(
                f"controlled/derived/{project_id}/{document_id}/transcription/"
                f"{run_id}/page/{page_index}/lines/{line_id}.char-boxes.json"
            ),
            payload=payload,
        )


def _layout_pagexml_payload() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">'
        b'<Page imageWidth="1000" imageHeight="1400">'
        b'<TextRegion id="reg-1">'
        b'<Coords points="0,0 1000,0 1000,1400 0,1400"/>'
        b'<TextLine id="line-1"><Coords points="10,10 200,10 200,40 10,40"/></TextLine>'
        b'<TextLine id="line-2"><Coords points="10,60 200,60 200,90 10,90"/></TextLine>'
        b"</TextRegion>"
        b"</Page>"
        b"</PcGts>\n"
    )


class InMemoryTranscriptionStore:
    def __init__(
        self,
        *,
        run_status: str = "QUEUED",
        page_status: str = "QUEUED",
    ) -> None:
        now = datetime.now(UTC)
        self.run = TranscriptionRunRecord(
            id="transcription-run-1",
            project_id="project-1",
            document_id="doc-1",
            input_preprocess_run_id="pre-run-1",
            input_layout_run_id="layout-run-1",
            input_layout_snapshot_hash="layout-snap-1",
            engine="VLM_LINE_CONTEXT",
            model_id="model-primary-1",
            project_model_assignment_id="assignment-1",
            prompt_template_id="ukde.transcription.v1.line-context",
            prompt_template_sha256="prompt-sha",
            response_schema_version=1,
            confidence_basis="MODEL_NATIVE",
            confidence_calibration_version="v1",
            params_json={"review_confidence_threshold": 0.85},
            pipeline_version="transcription-v1",
            container_digest="ukde/transcription:v1",
            attempt_number=1,
            supersedes_transcription_run_id=None,
            superseded_by_transcription_run_id=None,
            status=run_status,  # type: ignore[arg-type]
            created_by="user-worker",
            created_at=now,
            started_at=None,
            finished_at=None,
            canceled_by=None,
            canceled_at=None,
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
        self.page_result = PageTranscriptionResultRecord(
            run_id=self.run.id,
            page_id=self.page.id,
            page_index=0,
            status=page_status,  # type: ignore[arg-type]
            pagexml_out_key=None,
            pagexml_out_sha256=None,
            raw_model_response_key=None,
            raw_model_response_sha256=None,
            hocr_out_key=None,
            hocr_out_sha256=None,
            metrics_json={},
            warnings_json=[],
            failure_reason=None,
            created_at=now,
            updated_at=now,
        )
        self.preprocess_result = PagePreprocessResultRecord(
            run_id=self.run.input_preprocess_run_id,
            page_id=self.page.id,
            page_index=0,
            status="SUCCEEDED",
            quality_gate_status="PASS",
            input_object_key="controlled/raw/project-1/doc-1/original.bin",
            output_object_key_gray=(
                "controlled/derived/project-1/doc-1/preprocess/pre-run-1/gray/0.png"
            ),
            output_object_key_bin=None,
            metrics_json={},
            sha256_gray="gray-sha",
            sha256_bin=None,
            warnings_json=[],
            failure_reason=None,
            created_at=now,
            updated_at=now,
            input_sha256="input-sha",
            source_result_run_id="pre-run-1",
            metrics_object_key=None,
            metrics_sha256=None,
        )
        self.layout_result = PageLayoutResultRecord(
            run_id=self.run.input_layout_run_id,
            page_id=self.page.id,
            page_index=0,
            status="SUCCEEDED",
            page_recall_status="COMPLETE",
            active_layout_version_id="layout-version-1",
            page_xml_key=(
                "controlled/derived/project-1/doc-1/layout/layout-run-1/page/0.xml"
            ),
            overlay_json_key=(
                "controlled/derived/project-1/doc-1/layout/layout-run-1/page/0.json"
            ),
            page_xml_sha256=hashlib.sha256(_layout_pagexml_payload()).hexdigest(),
            overlay_json_sha256="overlay-sha",
            metrics_json={},
            warnings_json=[],
            failure_reason=None,
            created_at=now,
            updated_at=now,
        )
        self.line_artifacts = [
            LayoutLineArtifactRecord(
                run_id=self.layout_result.run_id,
                page_id=self.layout_result.page_id,
                layout_version_id="layout-version-1",
                line_id="line-1",
                region_id="reg-1",
                line_crop_key=(
                    "controlled/derived/project-1/doc-1/layout/layout-run-1/"
                    "page/0/lines/line-1.png"
                ),
                region_crop_key=None,
                page_thumbnail_key=(
                    "controlled/derived/project-1/doc-1/layout/layout-run-1/"
                    "page/0/thumbnail.png"
                ),
                context_window_json_key=(
                    "controlled/derived/project-1/doc-1/layout/layout-run-1/"
                    "page/0/context/line-1.json"
                ),
                artifacts_sha256="artifact-sha-1",
                created_at=now,
            ),
            LayoutLineArtifactRecord(
                run_id=self.layout_result.run_id,
                page_id=self.layout_result.page_id,
                layout_version_id="layout-version-1",
                line_id="line-2",
                region_id="reg-1",
                line_crop_key=(
                    "controlled/derived/project-1/doc-1/layout/layout-run-1/"
                    "page/0/lines/line-2.png"
                ),
                region_crop_key=None,
                page_thumbnail_key=(
                    "controlled/derived/project-1/doc-1/layout/layout-run-1/"
                    "page/0/thumbnail.png"
                ),
                context_window_json_key=(
                    "controlled/derived/project-1/doc-1/layout/layout-run-1/"
                    "page/0/context/line-2.json"
                ),
                artifacts_sha256="artifact-sha-2",
                created_at=now,
            ),
        ]
        self.rescue_candidates = [
            LayoutRescueCandidateRecord(
                id="resc-1",
                run_id=self.layout_result.run_id,
                page_id=self.layout_result.page_id,
                candidate_kind="PAGE_WINDOW",
                geometry_json={"bbox": {"x": 260, "y": 120, "width": 220, "height": 48}},
                confidence=0.71,
                source_signal="recall-window",
                status="ACCEPTED",
                created_at=now,
                updated_at=now,
            )
        ]
        self.approved_model = ApprovedModelRecord(
            id="model-primary-1",
            model_type="VLM",
            model_role="TRANSCRIPTION_PRIMARY",
            model_family="qwen2.5-vl",
            model_version="3b-instruct",
            serving_interface="OPENAI_CHAT",
            engine_family="qwen",
            deployment_unit="internal-vlm",
            artifact_subpath="models/qwen2.5-vl-3b-instruct",
            checksum_sha256="model-sha",
            runtime_profile="gpu",
            response_contract_version="v1",
            metadata_json={"model": "internal-vlm-test"},
            status="APPROVED",
            approved_by="admin-user",
            approved_at=now,
            created_at=now,
            updated_at=now,
        )
        self.line_results: list[LineTranscriptionResultRecord] = []
        self.token_results: list[TokenTranscriptionResultRecord] = []
        self.output_projection_by_page_id: dict[str, TranscriptionOutputProjectionRecord] = {}

    def get_transcription_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> TranscriptionRunRecord | None:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
        ):
            return None
        return self.run

    def mark_transcription_run_running(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> TranscriptionRunRecord:
        current = self.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if current is None:
            raise RuntimeError("Run not found.")
        if current.status == "QUEUED":
            self.run = replace(
                current,
                status="RUNNING",
                started_at=current.started_at or datetime.now(UTC),
                failure_reason=None,
            )
        return self.run

    def list_page_transcription_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        status: str | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[list[PageTranscriptionResultRecord], int | None]:
        del page_size
        if cursor > 0:
            return [], None
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
        ):
            return [], None
        if status is not None and self.page_result.status != status:
            return [], None
        return [self.page_result], None

    def mark_transcription_page_running(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PageTranscriptionResultRecord:
        current = self.get_page_transcription_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if current is None:
            raise RuntimeError("Page result not found.")
        if current.status in {"QUEUED", "RUNNING"}:
            self.page_result = replace(
                current,
                status="RUNNING",
                updated_at=datetime.now(UTC),
            )
        return self.page_result

    def get_page_transcription_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PageTranscriptionResultRecord | None:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.page_result.run_id
            or page_id != self.page_result.page_id
        ):
            return None
        return self.page_result

    def get_document_page(
        self,
        *,
        project_id: str,
        document_id: str,
        page_id: str,
    ) -> DocumentPageRecord | None:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or page_id != self.page.id
        ):
            return None
        return self.page

    def get_preprocess_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PagePreprocessResultRecord | None:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.preprocess_result.run_id
            or page_id != self.preprocess_result.page_id
        ):
            return None
        return self.preprocess_result

    def get_layout_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PageLayoutResultRecord | None:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.layout_result.run_id
            or page_id != self.layout_result.page_id
        ):
            return None
        return self.layout_result

    def list_layout_line_artifacts(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[LayoutLineArtifactRecord]:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.layout_result.run_id
            or page_id != self.layout_result.page_id
        ):
            return []
        return list(self.line_artifacts)

    def list_layout_rescue_candidates(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[LayoutRescueCandidateRecord]:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.layout_result.run_id
            or page_id != self.layout_result.page_id
        ):
            return []
        return list(self.rescue_candidates)

    def get_approved_model(self, *, model_id: str) -> ApprovedModelRecord | None:
        if model_id != self.approved_model.id:
            return None
        return self.approved_model

    def replace_line_transcription_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        rows: list[dict[str, object]],
    ) -> list[LineTranscriptionResultRecord]:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
            or page_id != self.page.id
        ):
            raise RuntimeError("Line write target not found.")
        now = datetime.now(UTC)
        self.line_results = [
            LineTranscriptionResultRecord(
                run_id=run_id,
                page_id=page_id,
                line_id=str(row["line_id"]),
                text_diplomatic=str(row.get("text_diplomatic") or ""),
                conf_line=(
                    float(row["conf_line"])
                    if isinstance(row.get("conf_line"), (int, float))
                    else None
                ),
                confidence_band=str(row.get("confidence_band") or "UNKNOWN"),  # type: ignore[arg-type]
                confidence_basis=str(row.get("confidence_basis") or "MODEL_NATIVE"),  # type: ignore[arg-type]
                confidence_calibration_version=str(
                    row.get("confidence_calibration_version") or "v1"
                ),
                alignment_json_key=(
                    str(row["alignment_json_key"])
                    if isinstance(row.get("alignment_json_key"), str)
                    else None
                ),
                char_boxes_key=(
                    str(row["char_boxes_key"])
                    if isinstance(row.get("char_boxes_key"), str)
                    else None
                ),
                schema_validation_status=str(
                    row.get("schema_validation_status") or "INVALID"
                ),  # type: ignore[arg-type]
                flags_json=(
                    dict(row["flags_json"])
                    if isinstance(row.get("flags_json"), dict)
                    else {}
                ),
                machine_output_sha256=(
                    str(row["machine_output_sha256"])
                    if isinstance(row.get("machine_output_sha256"), str)
                    else None
                ),
                active_transcript_version_id=(
                    str(row["active_transcript_version_id"])
                    if isinstance(row.get("active_transcript_version_id"), str)
                    else None
                ),
                version_etag=str(row["version_etag"]),
                token_anchor_status=str(
                    row.get("token_anchor_status") or "REFRESH_REQUIRED"
                ),  # type: ignore[arg-type]
                created_at=now,
                updated_at=now,
            )
            for row in rows
        ]
        return list(self.line_results)

    def list_line_transcription_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[LineTranscriptionResultRecord]:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
            or page_id != self.page.id
        ):
            return []
        return list(self.line_results)

    def replace_token_transcription_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        rows: list[dict[str, object]],
    ) -> list[TokenTranscriptionResultRecord]:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
            or page_id != self.page.id
        ):
            raise RuntimeError("Token write target not found.")
        now = datetime.now(UTC)
        self.token_results = [
            TokenTranscriptionResultRecord(
                run_id=run_id,
                page_id=page_id,
                line_id=(
                    str(row["line_id"]) if isinstance(row.get("line_id"), str) else None
                ),
                token_id=str(row["token_id"]),
                token_index=int(row["token_index"]),
                token_text=str(row["token_text"]),
                token_confidence=(
                    float(row["token_confidence"])
                    if isinstance(row.get("token_confidence"), (int, float))
                    else None
                ),
                bbox_json=(
                    dict(row["bbox_json"])
                    if isinstance(row.get("bbox_json"), dict)
                    else None
                ),
                polygon_json=(
                    dict(row["polygon_json"])
                    if isinstance(row.get("polygon_json"), dict)
                    else None
                ),
                source_kind=str(row.get("source_kind") or "LINE"),  # type: ignore[arg-type]
                source_ref_id=str(row["source_ref_id"]),
                projection_basis=str(
                    row.get("projection_basis") or "ENGINE_OUTPUT"
                ),  # type: ignore[arg-type]
                created_at=now,
                updated_at=now,
            )
            for row in rows
        ]
        return list(self.token_results)

    def complete_transcription_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        pagexml_out_key: str,
        pagexml_out_sha256: str,
        raw_model_response_key: str,
        raw_model_response_sha256: str,
        metrics_json: dict[str, object],
        warnings_json: list[str],
        hocr_out_key: str | None = None,
        hocr_out_sha256: str | None = None,
    ) -> PageTranscriptionResultRecord:
        current = self.get_page_transcription_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if current is None:
            raise RuntimeError("Page result not found.")
        self.page_result = replace(
            current,
            status="SUCCEEDED",
            pagexml_out_key=pagexml_out_key,
            pagexml_out_sha256=pagexml_out_sha256,
            raw_model_response_key=raw_model_response_key,
            raw_model_response_sha256=raw_model_response_sha256,
            metrics_json=dict(metrics_json),
            warnings_json=list(warnings_json),
            hocr_out_key=hocr_out_key,
            hocr_out_sha256=hocr_out_sha256,
            failure_reason=None,
            updated_at=datetime.now(UTC),
        )
        return self.page_result

    def fail_transcription_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        failure_reason: str,
        raw_model_response_key: str | None = None,
        raw_model_response_sha256: str | None = None,
        metrics_json: dict[str, object] | None = None,
        warnings_json: list[str] | None = None,
    ) -> PageTranscriptionResultRecord:
        current = self.get_page_transcription_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if current is None:
            raise RuntimeError("Page result not found.")
        self.page_result = replace(
            current,
            status="FAILED",
            raw_model_response_key=raw_model_response_key or current.raw_model_response_key,
            raw_model_response_sha256=(
                raw_model_response_sha256 or current.raw_model_response_sha256
            ),
            metrics_json=dict(metrics_json or {}),
            warnings_json=list(warnings_json or []),
            failure_reason=failure_reason,
            updated_at=datetime.now(UTC),
        )
        return self.page_result

    def upsert_transcription_output_projection(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        corrected_pagexml_key: str,
        corrected_pagexml_sha256: str,
        corrected_text_sha256: str,
        source_pagexml_sha256: str,
    ) -> TranscriptionOutputProjectionRecord:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
            or page_id != self.page.id
        ):
            raise RuntimeError("Projection target not found.")
        projection = TranscriptionOutputProjectionRecord(
            run_id=run_id,
            document_id=document_id,
            page_id=page_id,
            corrected_pagexml_key=corrected_pagexml_key,
            corrected_pagexml_sha256=corrected_pagexml_sha256,
            corrected_text_sha256=corrected_text_sha256,
            source_pagexml_sha256=source_pagexml_sha256,
            updated_at=datetime.now(UTC),
        )
        self.output_projection_by_page_id[page_id] = projection
        return projection

    def finalize_transcription_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> TranscriptionRunRecord:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
        ):
            raise RuntimeError("Run not found.")
        if self.page_result.status == "SUCCEEDED":
            self.run = replace(
                self.run,
                status="SUCCEEDED",
                finished_at=datetime.now(UTC),
                failure_reason=None,
            )
        elif self.page_result.status == "FAILED":
            self.run = replace(
                self.run,
                status="FAILED",
                finished_at=datetime.now(UTC),
                failure_reason="One or more transcription page tasks failed.",
            )
        elif self.page_result.status == "CANCELED":
            self.run = replace(
                self.run,
                status="CANCELED",
                finished_at=datetime.now(UTC),
                failure_reason="Run completed with canceled pages.",
            )
        else:
            self.run = replace(self.run, status="RUNNING")
        return self.run


class FakeDocumentService:
    def __init__(self, *, store: InMemoryTranscriptionStore, storage: InMemoryStorage) -> None:
        self._store = store
        self._storage = storage


def _seed_storage_payloads(store: InMemoryTranscriptionStore) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {
        store.preprocess_result.output_object_key_gray: b"gray-page-png-bytes",
        store.layout_result.page_xml_key: _layout_pagexml_payload(),
    }
    for artifact in store.line_artifacts:
        payloads[artifact.line_crop_key] = f"crop:{artifact.line_id}".encode("utf-8")
        payloads[artifact.context_window_json_key] = (
            json.dumps(
                {
                    "lineId": artifact.line_id,
                    "window": {"before": "", "after": ""},
                },
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
    return payloads


def _default_primary_response(*, request_payload: dict[str, object]) -> dict[str, object]:
    target = request_payload["target"]
    assert isinstance(target, dict)
    source_kind = str(target.get("sourceKind") or "LINE")
    source_ref_id = str(target.get("sourceRefId") or "")
    line_id_hint = target.get("lineId")
    line_id = (
        str(line_id_hint).strip()
        if isinstance(line_id_hint, str) and str(line_id_hint).strip()
        else None
    )
    if source_kind != "LINE" and line_id is None:
        line_id = "line-1"
    if source_kind == "LINE":
        line_id = source_ref_id
    item = {
        "sourceKind": source_kind,
        "sourceRefId": source_ref_id,
        "lineId": line_id,
        "textDiplomatic": f"text-{source_kind.lower()}-{source_ref_id}",
        "confidence": 0.93,
    }
    return {"choices": [{"message": {"content": json.dumps(item, sort_keys=True)}}]}


def _drain_worker(job_service: JobService, *, max_iterations: int = 20) -> list[JobRecord]:
    completed: list[JobRecord] = []
    for _ in range(max_iterations):
        row = job_service.run_worker_once(worker_id="worker-transcription", lease_seconds=30)
        if row is None:
            break
        completed.append(row)
    return completed


def _create_page_job_and_claim(
    *,
    job_service: JobService,
    job_store: InMemoryJobStore,
    dedupe_suffix: str,
) -> JobRecord:
    row, _, _ = job_store.enqueue_job(
        project_id="project-1",
        job_type="TRANSCRIBE_PAGE",
        dedupe_key=job_store.compute_dedupe_key(
            project_id="project-1",
            job_type="TRANSCRIBE_PAGE",
            logical_key=f"transcription-run-1|page-1|{dedupe_suffix}",
        ),
        payload_json={
            "project_id": "project-1",
            "document_id": "doc-1",
            "run_id": "transcription-run-1",
            "page_id": "page-1",
        },
        created_by="user-worker",
        max_attempts=3,
    )
    assert row.type == "TRANSCRIBE_PAGE"
    claimed = job_store.claim_next_job(worker_id="worker-transcription", lease_seconds=30)
    assert claimed is not None
    assert claimed.id == row.id
    return claimed


@pytest.fixture
def transcription_worker_fixture(monkeypatch: pytest.MonkeyPatch):
    store = InMemoryTranscriptionStore()
    storage = InMemoryStorage(payload_by_key=_seed_storage_payloads(store))
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
    monkeypatch.setattr(
        job_service,
        "_resolve_transcription_service_endpoint",
        lambda **_: ("http://127.0.0.1:8010/v1/chat/completions", "internal-vlm-test"),
    )
    monkeypatch.setattr(
        job_service,
        "_call_primary_transcription_service",
        lambda **kwargs: _default_primary_response(
            request_payload=kwargs["request_payload"]  # type: ignore[arg-type]
        ),
    )
    return job_service, job_store, store, storage, audit


def test_transcription_worker_pipeline_runs_document_page_finalize(
    transcription_worker_fixture,
) -> None:
    job_service, _, store, storage, audit = transcription_worker_fixture

    job_service.enqueue_transcription_document_job(
        project_id="project-1",
        document_id="doc-1",
        run_id="transcription-run-1",
        created_by="user-worker",
    )
    completed = _drain_worker(job_service)
    completed_types = {row.type for row in completed}

    assert {
        "TRANSCRIBE_DOCUMENT",
        "TRANSCRIBE_PAGE",
        "FINALIZE_TRANSCRIPTION_RUN",
    }.issubset(completed_types)
    assert store.run.status == "SUCCEEDED"
    assert store.page_result.status == "SUCCEEDED"
    assert store.page_result.pagexml_out_key is not None
    assert store.page_result.raw_model_response_key is not None
    assert store.page_result.raw_model_response_key.startswith(
        "controlled/derived/project-1/doc-1/transcription/transcription-run-1/page/0"
    )
    assert store.page_result.raw_model_response_sha256 is not None
    assert len(store.token_results) == 3
    assert len(store.line_results) == 3
    assert all(
        row.token_anchor_status == "CURRENT"
        for row in store.line_results
        if row.schema_validation_status == "VALID"
    )
    assert {row.token_index for row in store.token_results} == {0, 1, 2}
    assert len({row.token_id for row in store.token_results}) == len(store.token_results)
    rescue_tokens = [row for row in store.token_results if row.source_kind != "LINE"]
    assert len(rescue_tokens) == 1
    assert rescue_tokens[0].source_kind == "PAGE_WINDOW"
    assert rescue_tokens[0].source_ref_id == "resc-1"
    assert rescue_tokens[0].line_id is None
    assert isinstance(rescue_tokens[0].bbox_json, dict)
    assert isinstance(rescue_tokens[0].polygon_json, dict)
    for token in store.token_results:
        assert "/" not in token.source_ref_id
        assert "\\" not in token.source_ref_id
        assert token.bbox_json is not None
        assert token.polygon_json is not None
        bbox = token.bbox_json
        assert isinstance(bbox.get("x"), (int, float))
        assert isinstance(bbox.get("y"), (int, float))
        assert isinstance(bbox.get("width"), (int, float))
        assert isinstance(bbox.get("height"), (int, float))
        assert float(bbox["x"]) >= 0
        assert float(bbox["y"]) >= 0
        assert float(bbox["x"]) + float(bbox["width"]) <= store.page.width
        assert float(bbox["y"]) + float(bbox["height"]) <= store.page.height
        polygon = token.polygon_json
        points = polygon.get("points") if isinstance(polygon, dict) else None
        assert isinstance(points, list) and len(points) >= 3
        for point in points:
            assert isinstance(point, dict)
            assert isinstance(point.get("x"), (int, float))
            assert isinstance(point.get("y"), (int, float))
            assert float(point["x"]) >= 0
            assert float(point["x"]) <= store.page.width
            assert float(point["y"]) >= 0
            assert float(point["y"]) <= store.page.height
    assert "page-1" in store.output_projection_by_page_id

    persisted_pagexml = storage.read_object_bytes(store.page_result.pagexml_out_key)
    assert b'line-1"' in persisted_pagexml
    assert b"TextEquiv" in persisted_pagexml

    event_types = [str(event["event_type"]) for event in audit.recorded]
    assert "TRANSCRIPTION_RUN_STARTED" in event_types
    assert "TRANSCRIPTION_RUN_FINISHED" in event_types


def test_transcription_page_retry_is_idempotent_and_hashes_stable(
    transcription_worker_fixture,
) -> None:
    job_service, job_store, store, _, _ = transcription_worker_fixture
    store.run = replace(store.run, status="RUNNING", started_at=datetime.now(UTC))
    store.page_result = replace(store.page_result, status="RUNNING")

    claimed_first = _create_page_job_and_claim(
        job_service=job_service,
        job_store=job_store,
        dedupe_suffix="attempt-a",
    )
    first = job_service._process_transcription_page_job(
        worker_id="worker-transcription",
        row=claimed_first,
    )
    assert first.status == "SUCCEEDED"
    first_hashes = {row.line_id: row.machine_output_sha256 for row in store.line_results}
    first_token_snapshot = [
        (
            token.token_id,
            token.token_index,
            token.line_id,
            token.source_kind,
            token.source_ref_id,
            json.dumps(token.bbox_json, sort_keys=True),
            json.dumps(token.polygon_json, sort_keys=True),
        )
        for token in store.token_results
    ]
    assert len(first_hashes) == len(store.line_results)

    store.page_result = replace(store.page_result, status="RUNNING")
    claimed_second = _create_page_job_and_claim(
        job_service=job_service,
        job_store=job_store,
        dedupe_suffix="attempt-b",
    )
    second = job_service._process_transcription_page_job(
        worker_id="worker-transcription",
        row=claimed_second,
    )
    assert second.status == "SUCCEEDED"
    second_hashes = {row.line_id: row.machine_output_sha256 for row in store.line_results}
    second_token_snapshot = [
        (
            token.token_id,
            token.token_index,
            token.line_id,
            token.source_kind,
            token.source_ref_id,
            json.dumps(token.bbox_json, sort_keys=True),
            json.dumps(token.polygon_json, sort_keys=True),
        )
        for token in store.token_results
    ]

    assert first_hashes == second_hashes
    assert first_token_snapshot == second_token_snapshot
    assert len({row.token_id for row in store.token_results}) == len(store.token_results)
    assert len(store.line_results) == len(set(row.line_id for row in store.line_results))
    assert all(
        row.token_anchor_status == "CURRENT"
        for row in store.line_results
        if row.schema_validation_status == "VALID"
    )
    assert store.page_result.status == "SUCCEEDED"


def test_transcription_validation_failure_is_persisted_with_machine_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryTranscriptionStore(run_status="RUNNING", page_status="RUNNING")
    storage = InMemoryStorage(payload_by_key=_seed_storage_payloads(store))
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
    monkeypatch.setattr(
        job_service,
        "_resolve_transcription_service_endpoint",
        lambda **_: ("http://127.0.0.1:8010/v1/chat/completions", "internal-vlm-test"),
    )

    def _invalid_response(*, request_payload: dict[str, object]) -> dict[str, object]:
        target = request_payload["target"]
        assert isinstance(target, dict)
        if target.get("sourceKind") == "LINE" and target.get("sourceRefId") == "line-2":
            payload = {
                "sourceKind": "LINE",
                "sourceRefId": "line-404",
                "lineId": "line-404",
                "textDiplomatic": "invalid-anchor",
                "confidence": 0.8,
            }
            return {"choices": [{"message": {"content": json.dumps(payload, sort_keys=True)}}]}
        return _default_primary_response(request_payload=request_payload)

    monkeypatch.setattr(
        job_service,
        "_call_primary_transcription_service",
        lambda **kwargs: _invalid_response(
            request_payload=kwargs["request_payload"]  # type: ignore[arg-type]
        ),
    )

    claimed = _create_page_job_and_claim(
        job_service=job_service,
        job_store=job_store,
        dedupe_suffix="validation-failure",
    )
    finished = job_service._process_transcription_page_job(
        worker_id="worker-transcription",
        row=claimed,
    )

    assert finished.status == "FAILED"
    assert finished.error_code == "TRANSCRIPTION_PAGE_FAILED"
    assert store.page_result.status == "FAILED"
    assert store.page_result.raw_model_response_key is not None
    assert store.page_result.raw_model_response_key.endswith(".response.json")
    assert store.page_result.metrics_json.get("invalidCount") == 1
    assert "SCHEMA_VALIDATION_FAILED" in store.page_result.warnings_json
    assert any(row.schema_validation_status == "INVALID" for row in store.line_results)
    for row in store.line_results:
        if row.schema_validation_status == "INVALID":
            assert row.text_diplomatic == ""
            validation_errors = row.flags_json.get("validationErrors")
            assert isinstance(validation_errors, list)
            assert validation_errors


def test_primary_service_call_respects_outbound_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def _unexpected_http_post(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal called
        called = True
        raise AssertionError("httpx.post should not be called when outbound URL is blocked.")

    monkeypatch.setattr("app.jobs.service.httpx.post", _unexpected_http_post)
    job_service = JobService(
        settings=get_settings(),
        store=InMemoryJobStore(),  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        audit_service=SpyAuditService(),  # type: ignore[arg-type]
        telemetry_service=FakeTelemetryService(),  # type: ignore[arg-type]
    )
    with pytest.raises(OutboundRequestBlockedError):
        job_service._call_primary_transcription_service(
            endpoint_url="https://api.openai.com/v1/chat/completions",
            model_name="gpt-test",
            request_payload={"imageDataUrl": "data:image/png;base64,AAAA"},
            actor_user_id="user-1",
            request_id="worker:test:job-1",
        )
    assert called is False


def test_fallback_engine_path_persists_hocr_output(
    transcription_worker_fixture,
) -> None:
    job_service, _, store, storage, _ = transcription_worker_fixture
    store.run = replace(
        store.run,
        engine="KRAKEN_LINE",
        confidence_basis="FALLBACK_DISAGREEMENT",
        status="QUEUED",
        started_at=None,
        finished_at=None,
        failure_reason=None,
    )
    store.page_result = replace(
        store.page_result,
        status="QUEUED",
        pagexml_out_key=None,
        pagexml_out_sha256=None,
        raw_model_response_key=None,
        raw_model_response_sha256=None,
        hocr_out_key=None,
        hocr_out_sha256=None,
        warnings_json=[],
        metrics_json={},
        failure_reason=None,
    )
    store.line_results = []
    store.token_results = []
    store.output_projection_by_page_id = {}

    job_service.enqueue_transcription_document_job(
        project_id="project-1",
        document_id="doc-1",
        run_id="transcription-run-1",
        created_by="user-worker",
    )
    _drain_worker(job_service)

    assert store.run.status == "SUCCEEDED"
    assert store.page_result.status == "SUCCEEDED"
    assert store.page_result.hocr_out_key is not None
    assert store.page_result.hocr_out_key.endswith("/page/0.hocr")
    assert store.page_result.hocr_out_sha256 is not None
    assert store.page_result.pagexml_out_key is not None
    assert store.page_result.raw_model_response_key is not None
    assert store.page_result.metrics_json.get("validCount") == 3
    assert store.page_result.metrics_json.get("tokenCount") == 3
    assert all(line.schema_validation_status == "VALID" for line in store.line_results)
    assert all(line.token_anchor_status == "CURRENT" for line in store.line_results)
    assert len(store.token_results) == 3
    assert store.page_result.hocr_out_key in storage.payload_by_key
    hocr_payload = storage.payload_by_key[store.page_result.hocr_out_key]
    assert b'data-engine="KRAKEN_LINE"' in hocr_payload


def test_agreement_based_confidence_is_deterministic_for_same_crop_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryTranscriptionStore(run_status="RUNNING", page_status="RUNNING")
    store.run = replace(
        store.run,
        confidence_basis="READ_AGREEMENT",
        confidence_calibration_version="v1",
    )
    storage = InMemoryStorage(payload_by_key=_seed_storage_payloads(store))
    fake_document_service = FakeDocumentService(store=store, storage=storage)
    monkeypatch.setattr(
        "app.documents.service.get_document_service",
        lambda: fake_document_service,
    )
    job_store = InMemoryJobStore()
    job_service = JobService(
        settings=get_settings(),
        store=job_store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        audit_service=SpyAuditService(),  # type: ignore[arg-type]
        telemetry_service=FakeTelemetryService(),  # type: ignore[arg-type]
    )
    monkeypatch.setattr(
        job_service,
        "_resolve_transcription_service_endpoint",
        lambda **_: ("http://127.0.0.1:8010/v1/chat/completions", "internal-vlm-test"),
    )

    def _agreement_response(*, request_payload: dict[str, object]) -> dict[str, object]:
        target = request_payload["target"]
        assert isinstance(target, dict)
        source_kind = str(target.get("sourceKind") or "LINE")
        source_ref_id = str(target.get("sourceRefId") or "")
        context_window = request_payload.get("contextWindow")
        has_context = isinstance(context_window, dict) and bool(context_window)
        text_value = (
            f"text-{source_kind.lower()}-{source_ref_id}"
            if has_context
            else f"text-{source_kind.lower()}-{source_ref_id}-crop"
        )
        payload = {
            "sourceKind": source_kind,
            "sourceRefId": source_ref_id,
            "lineId": target.get("lineId"),
            "textDiplomatic": text_value,
            "alignmentSpans": [
                {"start": 0, "end": max(1, min(4, len(text_value))), "kind": "TOKEN"}
            ],
        }
        return {"choices": [{"message": {"content": json.dumps(payload, sort_keys=True)}}]}

    monkeypatch.setattr(
        job_service,
        "_call_primary_transcription_service",
        lambda **kwargs: _agreement_response(
            request_payload=kwargs["request_payload"]  # type: ignore[arg-type]
        ),
    )

    claimed_first = _create_page_job_and_claim(
        job_service=job_service,
        job_store=job_store,
        dedupe_suffix="agreement-a",
    )
    first = job_service._process_transcription_page_job(
        worker_id="worker-transcription",
        row=claimed_first,
    )
    assert first.status == "SUCCEEDED"
    first_snapshot = {
        row.line_id: (row.conf_line, row.confidence_basis, row.confidence_band)
        for row in store.line_results
    }
    assert first_snapshot
    assert all(
        row.confidence_basis == "READ_AGREEMENT"
        for row in store.line_results
        if row.schema_validation_status == "VALID"
    )

    store.page_result = replace(store.page_result, status="RUNNING")
    claimed_second = _create_page_job_and_claim(
        job_service=job_service,
        job_store=job_store,
        dedupe_suffix="agreement-b",
    )
    second = job_service._process_transcription_page_job(
        worker_id="worker-transcription",
        row=claimed_second,
    )
    assert second.status == "SUCCEEDED"
    second_snapshot = {
        row.line_id: (row.conf_line, row.confidence_basis, row.confidence_band)
        for row in store.line_results
    }
    assert first_snapshot == second_snapshot


def test_malformed_alignment_warnings_are_visible_without_mutating_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryTranscriptionStore(run_status="RUNNING", page_status="RUNNING")
    storage = InMemoryStorage(payload_by_key=_seed_storage_payloads(store))
    fake_document_service = FakeDocumentService(store=store, storage=storage)
    monkeypatch.setattr(
        "app.documents.service.get_document_service",
        lambda: fake_document_service,
    )
    job_store = InMemoryJobStore()
    job_service = JobService(
        settings=get_settings(),
        store=job_store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        audit_service=SpyAuditService(),  # type: ignore[arg-type]
        telemetry_service=FakeTelemetryService(),  # type: ignore[arg-type]
    )
    monkeypatch.setattr(
        job_service,
        "_resolve_transcription_service_endpoint",
        lambda **_: ("http://127.0.0.1:8010/v1/chat/completions", "internal-vlm-test"),
    )

    def _response_with_malformed_alignment(
        *,
        request_payload: dict[str, object],
    ) -> dict[str, object]:
        target = request_payload["target"]
        assert isinstance(target, dict)
        source_kind = str(target.get("sourceKind") or "LINE")
        source_ref_id = str(target.get("sourceRefId") or "")
        item = {
            "sourceKind": source_kind,
            "sourceRefId": source_ref_id,
            "lineId": target.get("lineId"),
            "textDiplomatic": f"text-{source_kind.lower()}-{source_ref_id}",
            "confidence": 0.91,
            "alignmentSpans": [{"start": "bad", "end": 2}],
            "charBoxes": [{"char": "a", "confidence": 0.88}, "invalid-box"],
        }
        return {"choices": [{"message": {"content": json.dumps(item, sort_keys=True)}}]}

    monkeypatch.setattr(
        job_service,
        "_call_primary_transcription_service",
        lambda **kwargs: _response_with_malformed_alignment(
            request_payload=kwargs["request_payload"]  # type: ignore[arg-type]
        ),
    )

    claimed = _create_page_job_and_claim(
        job_service=job_service,
        job_store=job_store,
        dedupe_suffix="alignment-warning",
    )
    finished = job_service._process_transcription_page_job(
        worker_id="worker-transcription",
        row=claimed,
    )
    assert finished.status == "SUCCEEDED"
    assert store.page_result.status == "SUCCEEDED"
    assert "ALIGNMENT_WARNINGS_PRESENT" in store.page_result.warnings_json
    assert "CHAR_BOX_WARNINGS_PRESENT" in store.page_result.warnings_json
    valid_rows = [row for row in store.line_results if row.schema_validation_status == "VALID"]
    assert valid_rows
    for line in valid_rows:
        warnings = line.flags_json.get("validationWarnings")
        assert isinstance(warnings, list)
        assert "MALFORMED_ALIGNMENT_SPANS" in warnings
        assert "MALFORMED_CHAR_BOXES" in warnings
        assert line.text_diplomatic.startswith("text-")


def test_fallback_disagreement_signal_does_not_mutate_primary_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryTranscriptionStore(run_status="RUNNING", page_status="RUNNING")
    store.run = replace(
        store.run,
        confidence_basis="FALLBACK_DISAGREEMENT",
        params_json={
            "review_confidence_threshold": 0.85,
            "fallback_confidence_threshold": 0.72,
            "fallback_disagreement_signal": True,
        },
    )
    storage = InMemoryStorage(payload_by_key=_seed_storage_payloads(store))
    fake_document_service = FakeDocumentService(store=store, storage=storage)
    monkeypatch.setattr(
        "app.documents.service.get_document_service",
        lambda: fake_document_service,
    )
    job_store = InMemoryJobStore()
    job_service = JobService(
        settings=get_settings(),
        store=job_store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        audit_service=SpyAuditService(),  # type: ignore[arg-type]
        telemetry_service=FakeTelemetryService(),  # type: ignore[arg-type]
    )
    monkeypatch.setattr(
        job_service,
        "_resolve_transcription_service_endpoint",
        lambda **_: ("http://127.0.0.1:8010/v1/chat/completions", "internal-vlm-test"),
    )
    monkeypatch.setattr(
        job_service,
        "_call_primary_transcription_service",
        lambda **kwargs: _default_primary_response(
            request_payload=kwargs["request_payload"]  # type: ignore[arg-type]
        ),
    )
    monkeypatch.setattr(
        job_service,
        "_call_governed_fallback_adapter",
        lambda **kwargs: {
            "sourceKind": kwargs["request_payload"]["target"]["sourceKind"],  # type: ignore[index]
            "sourceRefId": kwargs["request_payload"]["target"]["sourceRefId"],  # type: ignore[index]
            "lineId": kwargs["request_payload"]["target"].get("lineId"),  # type: ignore[index]
            "textDiplomatic": "fallback-different-text",
            "confidence": 0.65,
            "adapterEngine": kwargs["engine"],
            "adapterKind": "GOVERNED_FALLBACK",
        },
    )

    claimed = _create_page_job_and_claim(
        job_service=job_service,
        job_store=job_store,
        dedupe_suffix="fallback-disagreement",
    )
    finished = job_service._process_transcription_page_job(
        worker_id="worker-transcription",
        row=claimed,
    )
    assert finished.status == "SUCCEEDED"
    assert store.page_result.status == "SUCCEEDED"
    assert int(store.page_result.metrics_json.get("fallbackInvocationCount") or 0) > 0
    assert all(
        line.text_diplomatic.startswith("text-")
        for line in store.line_results
        if line.schema_validation_status == "VALID"
    )
    assert all(
        line.confidence_basis == "FALLBACK_DISAGREEMENT"
        for line in store.line_results
        if line.schema_validation_status == "VALID"
    )
