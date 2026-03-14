from __future__ import annotations

import hashlib
import io
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.auth.models import SessionPrincipal
from app.core.config import Settings
from app.documents.models import (
    DocumentImportRecord,
    DocumentTranscriptionProjectionRecord,
    DocumentLayoutProjectionRecord,
    DocumentPageRecord,
    DocumentProcessingRunRecord,
    DocumentRecord,
    LineTranscriptionResultRecord,
    LayoutRecallCheckRecord,
    LayoutRescueCandidateRecord,
    LayoutLineArtifactRecord,
    LayoutRunRecord,
    LayoutVersionRecord,
    PageTranscriptionResultRecord,
    PageLayoutResultRecord,
    PagePreprocessResultRecord,
    TranscriptVariantLayerRecord,
    TranscriptVariantSuggestionEventRecord,
    TranscriptVariantSuggestionRecord,
    TranscriptVersionRecord,
    TokenTranscriptionResultRecord,
    TranscriptionOutputProjectionRecord,
    TranscriptionRunRecord,
)
from app.documents.service import (
    DocumentLayoutConflictError,
    DocumentTranscriptionAccessDeniedError,
    DocumentTranscriptionConflictError,
    DocumentTranscriptionVariantLayersSnapshot,
    DocumentTranscriptionVariantSuggestionDecisionSnapshot,
    DocumentService,
    DocumentStoreUnavailableError,
    DocumentValidationError,
)
from app.documents.store import (
    DocumentLayoutRunConflictError,
    DocumentTranscriptionRunConflictError,
)
from app.documents.storage import DocumentStorage, StoredDocumentObject


class InMemoryDocumentStore:
    def __init__(self) -> None:
        self.documents: dict[str, DocumentRecord] = {}
        self.imports: dict[str, DocumentImportRecord] = {}
        self.processing_runs: dict[str, DocumentProcessingRunRecord] = {}
        self.last_import_id: str | None = None
        self._processing_run_sequence = 0

    def create_upload_records(
        self,
        *,
        project_id: str,
        document_id: str,
        import_id: str,
        original_filename: str,
        created_by: str,
    ) -> None:
        now = datetime.now(UTC)
        self.last_import_id = import_id
        self.documents[document_id] = DocumentRecord(
            id=document_id,
            project_id=project_id,
            original_filename=original_filename,
            stored_filename=None,
            content_type_detected=None,
            bytes=None,
            sha256=None,
            page_count=None,
            status="UPLOADING",
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.imports[import_id] = DocumentImportRecord(
            id=import_id,
            document_id=document_id,
            status="UPLOADING",
            failure_reason=None,
            created_by=created_by,
            accepted_at=None,
            rejected_at=None,
            canceled_by=None,
            canceled_at=None,
            created_at=now,
            updated_at=now,
        )

    def get_project_byte_usage(self, *, project_id: str) -> int:
        total = 0
        for record in self.documents.values():
            if record.project_id != project_id:
                continue
            if record.status == "CANCELED":
                continue
            total += record.bytes or 0
        return total

    def get_project_document_count(self, *, project_id: str) -> int:
        return sum(
            1
            for record in self.documents.values()
            if record.project_id == project_id and record.status != "CANCELED"
        )

    def get_project_page_usage(self, *, project_id: str) -> int:
        del project_id
        return 0

    def mark_upload_queued(
        self,
        *,
        project_id: str,
        import_id: str,
        stored_filename: str,
        content_type_detected: str,
        byte_count: int,
        sha256: str,
    ) -> None:
        now = datetime.now(UTC)
        import_record = self.imports[import_id]
        document = self.documents[import_record.document_id]
        assert document.project_id == project_id
        self.imports[import_id] = replace(
            import_record,
            status="QUEUED",
            failure_reason=None,
            updated_at=now,
        )
        self.documents[document.id] = replace(
            document,
            stored_filename=stored_filename,
            content_type_detected=content_type_detected,
            bytes=byte_count,
            sha256=sha256,
            status="QUEUED",
            updated_at=now,
        )

    def mark_import_failed(
        self,
        *,
        project_id: str,
        import_id: str,
        failure_reason: str,
    ) -> None:
        now = datetime.now(UTC)
        import_record = self.imports[import_id]
        document = self.documents[import_record.document_id]
        assert document.project_id == project_id
        self.imports[import_id] = replace(
            import_record,
            status="FAILED",
            failure_reason=failure_reason,
            updated_at=now,
        )
        self.documents[document.id] = replace(
            document,
            status="FAILED",
            updated_at=now,
        )

    def create_processing_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_kind: str,
        created_by: str,
        status: str = "QUEUED",
        supersedes_processing_run_id: str | None = None,
    ) -> DocumentProcessingRunRecord:
        _ = project_id
        _ = supersedes_processing_run_id
        now = datetime.now(UTC)
        self._processing_run_sequence += 1
        run = DocumentProcessingRunRecord(
            id=f"run-{self._processing_run_sequence}",
            document_id=document_id,
            attempt_number=1,
            run_kind=run_kind,  # type: ignore[arg-type]
            supersedes_processing_run_id=None,
            superseded_by_processing_run_id=None,
            status=status,  # type: ignore[arg-type]
            created_by=created_by,
            created_at=now,
            started_at=now if status == "RUNNING" else None,
            finished_at=None,
            canceled_by=None,
            canceled_at=None,
            failure_reason=None,
        )
        self.processing_runs[run.id] = run
        return run

    def transition_processing_run(
        self,
        *,
        project_id: str,
        run_id: str,
        status: str,
        failure_reason: str | None = None,
    ) -> DocumentProcessingRunRecord:
        _ = project_id
        now = datetime.now(UTC)
        run = self.processing_runs[run_id]
        started_at = run.started_at if run.started_at is not None else now
        finished_at = now if status in {"SUCCEEDED", "FAILED", "CANCELED"} else None
        transitioned = replace(
            run,
            status=status,  # type: ignore[arg-type]
            started_at=started_at,
            finished_at=finished_at,
            failure_reason=failure_reason,
        )
        self.processing_runs[run_id] = transitioned
        return transitioned

    def get_import_snapshot(
        self,
        *,
        project_id: str,
        import_id: str,
    ) -> tuple[DocumentRecord, DocumentImportRecord] | None:
        import_record = self.imports.get(import_id)
        if import_record is None:
            return None
        document = self.documents[import_record.document_id]
        if document.project_id != project_id:
            return None
        return document, import_record


class FakeProjectService:
    @staticmethod
    def require_member_workspace(*, current_user: SessionPrincipal, project_id: str):  # type: ignore[no-untyped-def]
        del current_user
        del project_id
        return SimpleNamespace(
            summary=SimpleNamespace(current_user_role="RESEARCHER"),
        )

    @staticmethod
    def resolve_workspace_context(*, current_user: SessionPrincipal, project_id: str):  # type: ignore[no-untyped-def]
        del current_user
        del project_id
        return SimpleNamespace(
            is_member=True,
            can_access_settings=False,
            summary=SimpleNamespace(current_user_role="RESEARCHER"),
        )


class CorruptingDocumentStorage(DocumentStorage):
    def write_original(
        self,
        *,
        project_id: str,
        document_id: str,
        source_path: Path,
    ) -> StoredDocumentObject:
        stored = super().write_original(
            project_id=project_id,
            document_id=document_id,
            source_path=source_path,
        )
        stored.absolute_path.write_bytes(b"tampered")
        return stored


class LayoutMaterializationStore:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.layout_run = LayoutRunRecord(
            id="layout-run-1",
            project_id="project-1",
            document_id="doc-1",
            input_preprocess_run_id="pre-run-1",
            run_kind="AUTO",
            parent_run_id=None,
            attempt_number=1,
            superseded_by_run_id=None,
            model_id="layout-model-v1",
            profile_id="DEFAULT",
            params_json={},
            params_hash="hash-layout-run-1",
            pipeline_version="layout-v1",
            container_digest="ukde/layout:v1",
            status="SUCCEEDED",
            created_by="user-1",
            created_at=now,
            started_at=now,
            finished_at=now,
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
            derived_image_key=None,
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
            input_object_key="controlled/derived/project-1/doc-1/pages/0.png",
            output_object_key_gray=(
                "controlled/derived/project-1/doc-1/preprocess/pre-run-1/gray/0.png"
            ),
            output_object_key_bin=None,
            metrics_json={},
            sha256_gray="sha-gray",
            sha256_bin=None,
            warnings_json=[],
            failure_reason=None,
            created_at=now,
            updated_at=now,
        )
        self.layout_projection = DocumentLayoutProjectionRecord(
            document_id=self.layout_run.document_id,
            project_id=self.layout_run.project_id,
            active_layout_run_id=self.layout_run.id,
            active_input_preprocess_run_id=self.layout_run.input_preprocess_run_id,
            updated_at=now,
            active_layout_snapshot_hash=None,
            downstream_transcription_state="CURRENT",
            downstream_transcription_invalidated_at=None,
            downstream_transcription_invalidated_reason=None,
        )
        self.page_result = PageLayoutResultRecord(
            run_id="layout-run-1",
            page_id="page-1",
            page_index=0,
            status="QUEUED",
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
        self.line_artifacts: dict[str, LayoutLineArtifactRecord] = {}
        self.line_artifacts_by_version: dict[str, dict[str, LayoutLineArtifactRecord]] = {}
        self.recall_check: LayoutRecallCheckRecord | None = None
        self.rescue_candidates: list[LayoutRescueCandidateRecord] = []
        self.layout_versions: dict[str, LayoutVersionRecord] = {}

    def get_layout_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> LayoutRunRecord | None:
        if (
            project_id != self.layout_run.project_id
            or document_id != self.layout_run.document_id
            or run_id != self.layout_run.id
        ):
            return None
        return self.layout_run

    def get_document_page(
        self,
        *,
        project_id: str,
        document_id: str,
        page_id: str,
    ) -> DocumentPageRecord | None:
        if project_id != self.layout_run.project_id or document_id != self.page.document_id:
            return None
        if page_id != self.page.id:
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
        if project_id != self.layout_run.project_id or document_id != self.layout_run.document_id:
            return None
        if run_id != self.preprocess_result.run_id or page_id != self.preprocess_result.page_id:
            return None
        return self.preprocess_result

    def complete_layout_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        page_xml_key: str,
        overlay_json_key: str,
        page_xml_sha256: str,
        overlay_json_sha256: str,
        metrics_json: dict[str, object],
        warnings_json: list[str],
        page_recall_status: str,
        active_layout_version_id: str | None = None,
    ) -> PageLayoutResultRecord:
        assert project_id == self.layout_run.project_id
        assert document_id == self.layout_run.document_id
        assert run_id == self.page_result.run_id
        assert page_id == self.page_result.page_id
        self.page_result = replace(
            self.page_result,
            status="SUCCEEDED",
            page_recall_status=page_recall_status,  # type: ignore[arg-type]
            page_xml_key=page_xml_key,
            overlay_json_key=overlay_json_key,
            page_xml_sha256=page_xml_sha256,
            overlay_json_sha256=overlay_json_sha256,
            metrics_json=dict(metrics_json),
            warnings_json=list(warnings_json),
            active_layout_version_id=active_layout_version_id
            if active_layout_version_id is not None
            else self.page_result.active_layout_version_id,
            failure_reason=None,
            updated_at=datetime.now(UTC),
        )
        return self.page_result

    def get_layout_active_version(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> LayoutVersionRecord | None:
        if (
            project_id != self.layout_run.project_id
            or document_id != self.layout_run.document_id
            or run_id != self.layout_run.id
            or page_id != self.page.id
            or self.page_result.active_layout_version_id is None
        ):
            return None
        return self.layout_versions.get(self.page_result.active_layout_version_id)

    def bootstrap_layout_page_version(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        version_id: str,
        version_etag: str,
        page_xml_key: str,
        overlay_json_key: str,
        page_xml_sha256: str,
        overlay_json_sha256: str,
        version_kind: str,
        canonical_payload_json: dict[str, object],
        reading_order_groups_json: list[dict[str, object]],
        reading_order_meta_json: dict[str, object],
        created_by: str,
    ) -> tuple[LayoutVersionRecord, PageLayoutResultRecord]:
        assert project_id == self.layout_run.project_id
        assert document_id == self.layout_run.document_id
        assert run_id == self.layout_run.id
        assert page_id == self.page.id
        current = self.get_layout_active_version(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if current is not None:
            return current, self.page_result
        record = LayoutVersionRecord(
            id=version_id,
            run_id=run_id,
            page_id=page_id,
            base_version_id=None,
            superseded_by_version_id=None,
            version_kind=version_kind,  # type: ignore[arg-type]
            version_etag=version_etag,
            page_xml_key=page_xml_key,
            overlay_json_key=overlay_json_key,
            page_xml_sha256=page_xml_sha256,
            overlay_json_sha256=overlay_json_sha256,
            run_snapshot_hash=hashlib.sha256(
                f"{run_id}|{page_id}:{version_id}".encode("utf-8")
            ).hexdigest(),
            canonical_payload_json=dict(canonical_payload_json),
            reading_order_groups_json=[dict(group) for group in reading_order_groups_json],
            reading_order_meta_json=dict(reading_order_meta_json),
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self.layout_versions[record.id] = record
        self.page_result = replace(
            self.page_result,
            active_layout_version_id=record.id,
            updated_at=datetime.now(UTC),
        )
        return record, self.page_result

    def append_layout_page_version(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        version_id: str,
        expected_version_etag: str,
        page_xml_key: str,
        overlay_json_key: str,
        page_xml_sha256: str,
        overlay_json_sha256: str,
        version_kind: str,
        canonical_payload_json: dict[str, object],
        reading_order_groups_json: list[dict[str, object]],
        reading_order_meta_json: dict[str, object],
        created_by: str,
    ) -> tuple[LayoutVersionRecord, PageLayoutResultRecord]:
        assert project_id == self.layout_run.project_id
        assert document_id == self.layout_run.document_id
        assert run_id == self.layout_run.id
        assert page_id == self.page.id
        current = self.get_layout_active_version(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if current is None:
            raise DocumentLayoutRunConflictError(
                "Layout page has no active version for optimistic update."
            )
        if current.version_etag != expected_version_etag:
            raise DocumentLayoutRunConflictError(
                "Reading-order update conflicts with a newer saved layout version."
            )
        version_etag_seed = (
            f"{run_id}|{page_id}|{version_id}|{page_xml_sha256}|{overlay_json_sha256}"
        )
        version_etag = hashlib.sha256(version_etag_seed.encode("utf-8")).hexdigest()
        created = LayoutVersionRecord(
            id=version_id,
            run_id=run_id,
            page_id=page_id,
            base_version_id=current.id,
            superseded_by_version_id=None,
            version_kind=version_kind,  # type: ignore[arg-type]
            version_etag=version_etag,
            page_xml_key=page_xml_key,
            overlay_json_key=overlay_json_key,
            page_xml_sha256=page_xml_sha256,
            overlay_json_sha256=overlay_json_sha256,
            run_snapshot_hash=hashlib.sha256(
                f"{run_id}|{page_id}:{version_id}".encode("utf-8")
            ).hexdigest(),
            canonical_payload_json=dict(canonical_payload_json),
            reading_order_groups_json=[dict(group) for group in reading_order_groups_json],
            reading_order_meta_json=dict(reading_order_meta_json),
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self.layout_versions[current.id] = replace(
            current,
            superseded_by_version_id=created.id,
        )
        self.layout_versions[created.id] = created
        self.page_result = replace(
            self.page_result,
            active_layout_version_id=created.id,
            page_xml_key=page_xml_key,
            overlay_json_key=overlay_json_key,
            page_xml_sha256=page_xml_sha256,
            overlay_json_sha256=overlay_json_sha256,
            updated_at=datetime.now(UTC),
        )
        return created, self.page_result

    def replace_layout_line_artifacts(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        layout_version_id: str,
        artifacts: list[dict[str, object]],
    ) -> list[LayoutLineArtifactRecord]:
        assert project_id == self.layout_run.project_id
        assert document_id == self.layout_run.document_id
        assert run_id == self.layout_run.id
        assert page_id == self.page.id
        records_for_version: dict[str, LayoutLineArtifactRecord] = {}
        now = datetime.now(UTC)
        for artifact in artifacts:
            line_id = str(artifact["line_id"])
            records_for_version[line_id] = LayoutLineArtifactRecord(
                run_id=run_id,
                page_id=page_id,
                layout_version_id=layout_version_id,
                line_id=line_id,
                region_id=(
                    str(artifact["region_id"])
                    if isinstance(artifact.get("region_id"), str)
                    else None
                ),
                line_crop_key=str(artifact["line_crop_key"]),
                region_crop_key=(
                    str(artifact["region_crop_key"])
                    if isinstance(artifact.get("region_crop_key"), str)
                    else None
                ),
                page_thumbnail_key=str(artifact["page_thumbnail_key"]),
                context_window_json_key=str(artifact["context_window_json_key"]),
                artifacts_sha256=str(artifact["artifacts_sha256"]),
                created_at=now,
            )
        self.line_artifacts_by_version[layout_version_id] = records_for_version
        self.line_artifacts = dict(records_for_version)
        return [
            records_for_version[key]
            for key in sorted(records_for_version)
        ]

    def upsert_layout_recall_check(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        recall_check_version: str,
        missed_text_risk_score: float | None,
        signals_json: dict[str, object],
    ) -> LayoutRecallCheckRecord:
        assert project_id == self.layout_run.project_id
        assert document_id == self.layout_run.document_id
        assert run_id == self.layout_run.id
        assert page_id == self.page.id
        self.recall_check = LayoutRecallCheckRecord(
            run_id=run_id,
            page_id=page_id,
            recall_check_version=recall_check_version,
            missed_text_risk_score=missed_text_risk_score,
            signals_json=dict(signals_json),
            created_at=datetime.now(UTC),
        )
        return self.recall_check

    def get_layout_recall_check(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> LayoutRecallCheckRecord | None:
        if (
            project_id != self.layout_run.project_id
            or document_id != self.layout_run.document_id
            or run_id != self.layout_run.id
            or page_id != self.page.id
        ):
            return None
        return self.recall_check

    def replace_layout_rescue_candidates(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        candidates: list[dict[str, object]],
    ) -> list[LayoutRescueCandidateRecord]:
        assert project_id == self.layout_run.project_id
        assert document_id == self.layout_run.document_id
        assert run_id == self.layout_run.id
        assert page_id == self.page.id
        now = datetime.now(UTC)
        self.rescue_candidates = [
            LayoutRescueCandidateRecord(
                id=str(candidate["id"]),
                run_id=run_id,
                page_id=page_id,
                candidate_kind=candidate["candidate_kind"],  # type: ignore[arg-type]
                geometry_json=dict(candidate["geometry_json"]),  # type: ignore[arg-type]
                confidence=(
                    float(candidate["confidence"])
                    if isinstance(candidate.get("confidence"), (int, float))
                    else None
                ),
                source_signal=(
                    str(candidate["source_signal"])
                    if isinstance(candidate.get("source_signal"), str)
                    else None
                ),
                status=candidate["status"],  # type: ignore[arg-type]
                created_at=now,
                updated_at=now,
            )
            for candidate in candidates
        ]
        return list(self.rescue_candidates)

    def list_layout_rescue_candidates(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[LayoutRescueCandidateRecord]:
        if (
            project_id != self.layout_run.project_id
            or document_id != self.layout_run.document_id
            or run_id != self.layout_run.id
            or page_id != self.page.id
        ):
            return []
        return list(self.rescue_candidates)

    def get_layout_line_artifact(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
        layout_version_id: str | None = None,
    ) -> LayoutLineArtifactRecord | None:
        if project_id != self.layout_run.project_id or document_id != self.layout_run.document_id:
            return None
        if run_id != self.layout_run.id or page_id != self.page.id:
            return None
        resolved_version_id = layout_version_id or self.page_result.active_layout_version_id
        if resolved_version_id is None:
            return None
        return self.line_artifacts_by_version.get(resolved_version_id, {}).get(line_id)

    def list_layout_line_artifacts(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        layout_version_id: str | None = None,
    ) -> list[LayoutLineArtifactRecord]:
        if project_id != self.layout_run.project_id or document_id != self.layout_run.document_id:
            return []
        if run_id != self.layout_run.id or page_id != self.page.id:
            return []
        resolved_version_id = layout_version_id or self.page_result.active_layout_version_id
        if resolved_version_id is None:
            return []
        records = self.line_artifacts_by_version.get(resolved_version_id, {})
        return [
            records[key]
            for key in sorted(records)
        ]

    def mark_layout_downstream_transcription_stale(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        reason: str,
        active_layout_snapshot_hash: str | None = None,
    ) -> DocumentLayoutProjectionRecord | None:
        if (
            project_id != self.layout_projection.project_id
            or document_id != self.layout_projection.document_id
            or run_id != self.layout_projection.active_layout_run_id
        ):
            return None
        self.layout_projection = replace(
            self.layout_projection,
            downstream_transcription_state="STALE",
            downstream_transcription_invalidated_at=datetime.now(UTC),
            downstream_transcription_invalidated_reason=reason,
            active_layout_snapshot_hash=active_layout_snapshot_hash
            if isinstance(active_layout_snapshot_hash, str)
            else self.layout_projection.active_layout_snapshot_hash,
            updated_at=datetime.now(UTC),
        )
        return self.layout_projection

    def get_layout_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PageLayoutResultRecord | None:
        if (
            project_id != self.layout_run.project_id
            or document_id != self.layout_run.document_id
            or run_id != self.layout_run.id
            or page_id != self.page_result.page_id
        ):
            return None
        return self.page_result

    def list_page_layout_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        status: str | None = None,
        page_recall_status: str | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[list[PageLayoutResultRecord], int | None]:
        assert project_id == self.layout_run.project_id
        assert document_id == self.layout_run.document_id
        assert run_id == self.layout_run.id
        _ = status
        _ = page_recall_status
        _ = cursor
        _ = page_size
        return [self.page_result], None


class TranscriptionCorrectionStore:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.run = TranscriptionRunRecord(
            id="transcription-run-1",
            project_id="project-1",
            document_id="doc-1",
            input_preprocess_run_id="pre-run-1",
            input_layout_run_id="layout-run-1",
            input_layout_snapshot_hash="layout-snap-1",
            engine="VLM_LINE_CONTEXT",
            model_id="model-transcription-v1",
            project_model_assignment_id=None,
            prompt_template_id="prompt-v1",
            prompt_template_sha256="prompt-sha-1",
            response_schema_version=1,
            confidence_basis="MODEL_NATIVE",
            confidence_calibration_version="v1",
            params_json={"temperature": 0.0},
            pipeline_version="transcription-v1",
            container_digest="ukde/transcription:v1",
            attempt_number=1,
            supersedes_transcription_run_id=None,
            superseded_by_transcription_run_id=None,
            status="SUCCEEDED",
            created_by="user-1",
            created_at=now - timedelta(hours=2),
            started_at=now - timedelta(hours=2),
            finished_at=now - timedelta(hours=1, minutes=59),
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
            derived_image_key=None,
            derived_image_sha256=None,
            thumbnail_key=None,
            thumbnail_sha256=None,
            failure_reason=None,
            canceled_by=None,
            canceled_at=None,
            viewer_rotation=0,
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )
        self.page_result = PageTranscriptionResultRecord(
            run_id=self.run.id,
            page_id=self.page.id,
            page_index=self.page.page_index,
            status="SUCCEEDED",
            pagexml_out_key=(
                "controlled/derived/project-1/doc-1/transcription/transcription-run-1/page/0.xml"
            ),
            pagexml_out_sha256="source-pagexml-sha-1",
            raw_model_response_key=None,
            raw_model_response_sha256=None,
            hocr_out_key=None,
            hocr_out_sha256=None,
            metrics_json={},
            warnings_json=[],
            failure_reason=None,
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )
        self.line = LineTranscriptionResultRecord(
            run_id=self.run.id,
            page_id=self.page.id,
            line_id="line-1",
            text_diplomatic="Dear diary",
            conf_line=0.91,
            confidence_basis="MODEL_NATIVE",
            confidence_calibration_version="v1",
            alignment_json_key=None,
            char_boxes_key=None,
            schema_validation_status="VALID",
            flags_json={},
            machine_output_sha256="line-sha-1",
            active_transcript_version_id="transcript-version-1",
            version_etag="line-etag-1",
            token_anchor_status="CURRENT",
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )
        self.transcript_versions: list[TranscriptVersionRecord] = [
            TranscriptVersionRecord(
                id="transcript-version-1",
                run_id=self.run.id,
                page_id=self.page.id,
                line_id=self.line.line_id,
                base_version_id=None,
                superseded_by_version_id=None,
                version_etag=self.line.version_etag,
                text_diplomatic=self.line.text_diplomatic,
                editor_user_id="user-1",
                edit_reason=None,
                created_at=now - timedelta(hours=2),
            )
        ]
        self.transcription_projection = DocumentTranscriptionProjectionRecord(
            document_id=self.run.document_id,
            project_id=self.run.project_id,
            active_transcription_run_id=self.run.id,
            active_layout_run_id=self.run.input_layout_run_id,
            active_layout_snapshot_hash=self.run.input_layout_snapshot_hash,
            active_preprocess_run_id=self.run.input_preprocess_run_id,
            downstream_redaction_state="CURRENT",
            downstream_redaction_invalidated_at=None,
            downstream_redaction_invalidated_reason=None,
            updated_at=now - timedelta(hours=1),
        )
        self.output_projection: TranscriptionOutputProjectionRecord | None = None
        self.variant_layer = TranscriptVariantLayerRecord(
            id="variant-layer-1",
            run_id=self.run.id,
            page_id=self.page.id,
            variant_kind="NORMALISED",
            base_transcript_version_id="transcript-version-1",
            base_version_set_sha256=None,
            base_projection_sha256="projection-sha-1",
            variant_text_key=(
                "controlled/derived/project-1/doc-1/transcription/transcription-run-1/variants/normalised/page/0.txt"
            ),
            variant_text_sha256="variant-text-sha-1",
            created_by="user-3",
            created_at=now - timedelta(minutes=45),
        )
        self.variant_suggestion = TranscriptVariantSuggestionRecord(
            id="variant-suggestion-1",
            variant_layer_id=self.variant_layer.id,
            line_id=self.line.line_id,
            suggestion_text="Dear Diary",
            confidence=0.8,
            status="PENDING",
            decided_by=None,
            decided_at=None,
            decision_reason=None,
            metadata_json={"source": "assist-v1"},
            created_at=now - timedelta(minutes=45),
            updated_at=now - timedelta(minutes=45),
        )
        self.variant_suggestion_events: list[TranscriptVariantSuggestionEventRecord] = []

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
            or run_id != self.run.id
            or page_id != self.page.id
        ):
            return None
        return self.page_result

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
        return [self.line]

    def append_transcript_line_version(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
        text_diplomatic: str,
        editor_user_id: str,
        expected_version_etag: str,
        edit_reason: str | None = None,
    ) -> tuple[TranscriptVersionRecord, LineTranscriptionResultRecord, bool]:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
            or page_id != self.page.id
            or line_id != self.line.line_id
        ):
            raise DocumentTranscriptionRunConflictError("Transcription line result not found.")
        if expected_version_etag != self.line.version_etag:
            raise DocumentTranscriptionRunConflictError(
                "version_etag is stale for this transcript line."
            )

        now = datetime.now(UTC)
        previous_active_id = self.line.active_transcript_version_id
        text_changed = self.line.text_diplomatic != text_diplomatic
        next_version_id = f"transcript-version-{len(self.transcript_versions) + 1}"
        next_version_etag = f"{self.line.version_etag}-next"

        if previous_active_id is not None:
            self.transcript_versions = [
                replace(item, superseded_by_version_id=next_version_id)
                if item.id == previous_active_id
                else item
                for item in self.transcript_versions
            ]

        version = TranscriptVersionRecord(
            id=next_version_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
            base_version_id=previous_active_id,
            superseded_by_version_id=None,
            version_etag=next_version_etag,
            text_diplomatic=text_diplomatic,
            editor_user_id=editor_user_id,
            edit_reason=edit_reason,
            created_at=now,
        )
        self.transcript_versions.append(version)
        self.line = replace(
            self.line,
            active_transcript_version_id=version.id,
            version_etag=version.version_etag,
            token_anchor_status=(
                "REFRESH_REQUIRED" if text_changed else self.line.token_anchor_status
            ),
            updated_at=now,
        )
        return version, self.line, text_changed

    def get_transcription_output_projection(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> TranscriptionOutputProjectionRecord | None:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
            or page_id != self.page.id
        ):
            return None
        return self.output_projection

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
            raise DocumentTranscriptionRunConflictError("Transcription projection scope mismatch.")
        self.output_projection = TranscriptionOutputProjectionRecord(
            run_id=run_id,
            document_id=document_id,
            page_id=page_id,
            corrected_pagexml_key=corrected_pagexml_key,
            corrected_pagexml_sha256=corrected_pagexml_sha256,
            corrected_text_sha256=corrected_text_sha256,
            source_pagexml_sha256=source_pagexml_sha256,
            updated_at=datetime.now(UTC),
        )
        return self.output_projection

    def mark_transcription_downstream_redaction_stale(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        reason: str,
    ) -> DocumentTranscriptionProjectionRecord | None:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.transcription_projection.active_transcription_run_id
        ):
            return None
        now = datetime.now(UTC)
        self.transcription_projection = replace(
            self.transcription_projection,
            downstream_redaction_state="STALE",
            downstream_redaction_invalidated_at=now,
            downstream_redaction_invalidated_reason=reason,
            updated_at=now,
        )
        return self.transcription_projection

    def list_transcript_variant_layers(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        variant_kind: str = "NORMALISED",
    ) -> list[TranscriptVariantLayerRecord]:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
            or page_id != self.page.id
            or variant_kind != "NORMALISED"
        ):
            return []
        return [self.variant_layer]

    def list_transcript_variant_suggestions(
        self,
        *,
        project_id: str,
        document_id: str,
        variant_layer_id: str,
    ) -> list[TranscriptVariantSuggestionRecord]:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or variant_layer_id != self.variant_layer.id
        ):
            return []
        return [self.variant_suggestion]

    def record_transcript_variant_suggestion_decision(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        variant_kind: str,
        suggestion_id: str,
        decision: str,
        actor_user_id: str,
        reason: str | None = None,
    ) -> tuple[TranscriptVariantSuggestionRecord, TranscriptVariantSuggestionEventRecord]:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
            or page_id != self.page.id
            or variant_kind != "NORMALISED"
            or suggestion_id != self.variant_suggestion.id
        ):
            raise DocumentTranscriptionRunConflictError(
                "Transcript variant suggestion not found."
            )
        if decision not in {"ACCEPT", "REJECT"}:
            raise DocumentTranscriptionRunConflictError("Invalid suggestion decision.")
        now = datetime.now(UTC)
        to_status = "ACCEPTED" if decision == "ACCEPT" else "REJECTED"
        from_status = self.variant_suggestion.status
        self.variant_suggestion = replace(
            self.variant_suggestion,
            status=to_status,  # type: ignore[arg-type]
            decided_by=actor_user_id,
            decided_at=now,
            decision_reason=reason,
            updated_at=now,
        )
        event = TranscriptVariantSuggestionEventRecord(
            id=f"variant-event-{len(self.variant_suggestion_events) + 1}",
            suggestion_id=self.variant_suggestion.id,
            variant_layer_id=self.variant_layer.id,
            actor_user_id=actor_user_id,
            decision=decision,  # type: ignore[arg-type]
            from_status=from_status,
            to_status=to_status,  # type: ignore[arg-type]
            reason=reason,
            created_at=now,
        )
        self.variant_suggestion_events.append(event)
        return self.variant_suggestion, event


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        APP_ENV="test",
        DATABASE_URL="postgresql://ukde:ukde@127.0.0.1:5432/ukde",
        STORAGE_CONTROLLED_ROOT=str(tmp_path),
    )


def _principal(
    *,
    roles: tuple[str, ...] = (),
) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-test",
        auth_source="bearer",
        user_id="user-1",
        oidc_sub="oidc-user-1",
        email="user-1@test.local",
        display_name="User One",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-test",
    )


def _render_layout_source_page_bytes() -> bytes:
    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError as error:  # pragma: no cover - dependency guard
        raise RuntimeError("Pillow is required for layout service tests.") from error
    image = Image.new("L", (1000, 1400), color=245)
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 80, 960, 120), fill=18)
    payload = io.BytesIO()
    image.save(payload, format="PNG", optimize=False, compress_level=9)
    return payload.getvalue()


def test_upload_document_writes_source_sidecar_with_checksum_metadata(tmp_path: Path) -> None:
    payload = b"%PDF-1.7\nhello-world"
    store = InMemoryDocumentStore()
    settings = _settings(tmp_path)
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    snapshot = service.upload_document(
        current_user=_principal(),
        project_id="project-1",
        original_filename="diary.pdf",
        file_stream=io.BytesIO(payload),
    )

    assert snapshot.import_record.status == "QUEUED"
    assert snapshot.document_record.bytes == len(payload)
    assert snapshot.document_record.sha256 == hashlib.sha256(payload).hexdigest()
    assert snapshot.document_record.stored_filename is not None

    stored_path = tmp_path / snapshot.document_record.stored_filename
    assert stored_path.read_bytes() == payload

    sidecar_path = tmp_path / f"controlled/raw/project-1/{snapshot.document_record.id}/source-meta.json"
    assert sidecar_path.exists()
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["projectId"] == "project-1"
    assert sidecar["documentId"] == snapshot.document_record.id
    assert sidecar["importId"] == snapshot.import_record.id
    assert sidecar["bytes"] == len(payload)
    assert sidecar["sha256"] == hashlib.sha256(payload).hexdigest()
    assert sidecar["storedFilename"] == snapshot.document_record.stored_filename


def test_upload_document_fails_closed_when_stored_payload_integrity_mismatch(
    tmp_path: Path,
) -> None:
    payload = b"%PDF-1.7\nintegrity"
    store = InMemoryDocumentStore()
    settings = _settings(tmp_path)
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=CorruptingDocumentStorage(settings=settings),
    )

    with pytest.raises(DocumentStoreUnavailableError):
        service.upload_document(
            current_user=_principal(),
            project_id="project-1",
            original_filename="integrity.pdf",
            file_stream=io.BytesIO(payload),
        )

    assert store.last_import_id is not None
    failed_snapshot = store.get_import_snapshot(
        project_id="project-1",
        import_id=store.last_import_id,
    )
    assert failed_snapshot is not None
    document, import_record = failed_snapshot
    assert import_record.status == "FAILED"
    assert import_record.failure_reason == "Stored upload integrity verification failed."
    assert document.status == "FAILED"


def test_materialize_layout_page_outputs_persists_hashes_and_manifest(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    store = LayoutMaterializationStore()
    preprocess_source_path = tmp_path / str(store.preprocess_result.output_object_key_gray)
    preprocess_source_path.parent.mkdir(parents=True, exist_ok=True)
    preprocess_source_path.write_bytes(_render_layout_source_page_bytes())
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    page_result = service.materialize_layout_page_outputs(
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        canonical_page_payload={
            "schemaVersion": 1,
            "runId": "layout-run-1",
            "pageId": "page-1",
            "pageIndex": 0,
            "page": {"width": 1000, "height": 1400},
            "regions": [
                {
                    "id": "region-1",
                    "type": "TEXT",
                    "polygon": [[20, 40], [980, 40], [980, 320], [20, 320]],
                    "lineIds": ["line-1"],
                }
            ],
            "lines": [
                {
                    "id": "line-1",
                    "parentRegionId": "region-1",
                    "polygon": [[40, 80], [960, 80], [960, 120], [40, 120]],
                    "baseline": [[48, 112], [950, 112]],
                }
            ],
            "readingOrder": [{"fromId": "region-1", "toId": "line-1"}],
        },
        page_recall_status="NEEDS_RESCUE",
        metrics_json={"region_count": 1, "line_count": 1},
        warnings_json=["LOW_LINES"],
        recall_check_version="layout-recall-v1",
        missed_text_risk_score=0.42,
        recall_signals_json={
            "algorithm_version": "layout-recall-v1",
            "candidate_count": 1,
            "accepted_candidate_count": 1,
        },
        rescue_candidates=[
            {
                "id": "resc-0001-001-fixture",
                "candidate_kind": "LINE_EXPANSION",
                "geometry_json": {
                    "schemaVersion": 1,
                    "pageId": "page-1",
                    "pageIndex": 0,
                    "bbox": {"x": 32, "y": 72, "width": 940, "height": 70},
                },
                "confidence": 0.72,
                "source_signal": "UNASSOCIATED_COMPONENT_NEAR_LINE",
                "status": "ACCEPTED",
            }
        ],
    )

    assert (
        page_result.page_xml_key
        == "controlled/derived/project-1/doc-1/layout/layout-run-1/page/0.xml"
    )
    assert (
        page_result.overlay_json_key
        == "controlled/derived/project-1/doc-1/layout/layout-run-1/page/0.json"
    )
    assert page_result.page_xml_sha256 is not None
    assert page_result.overlay_json_sha256 is not None
    assert len(page_result.page_xml_sha256) == 64
    assert len(page_result.overlay_json_sha256) == 64

    pagexml_path = tmp_path / page_result.page_xml_key
    overlay_path = tmp_path / page_result.overlay_json_key
    assert pagexml_path.exists()
    assert overlay_path.exists()
    assert hashlib.sha256(pagexml_path.read_bytes()).hexdigest() == page_result.page_xml_sha256
    assert (
        hashlib.sha256(overlay_path.read_bytes()).hexdigest()
        == page_result.overlay_json_sha256
    )
    artifact = store.line_artifacts["line-1"]
    assert "/versions/layoutv-" in artifact.line_crop_key
    assert artifact.line_crop_key.endswith("/page/0/lines/line-1.png")
    assert artifact.region_crop_key is not None
    assert "/versions/layoutv-" in artifact.region_crop_key
    assert artifact.region_crop_key.endswith("/page/0/regions/region-1.png")
    assert "/versions/layoutv-" in artifact.page_thumbnail_key
    assert artifact.page_thumbnail_key.endswith("/page/0/thumbnail.png")
    assert "/versions/layoutv-" in artifact.context_window_json_key
    assert artifact.context_window_json_key.endswith("/page/0/context/line-1.json")
    assert len(artifact.artifacts_sha256) == 64

    assert (tmp_path / artifact.line_crop_key).exists()
    assert (tmp_path / str(artifact.region_crop_key)).exists()
    assert (tmp_path / artifact.page_thumbnail_key).exists()
    context_payload = json.loads(
        (tmp_path / artifact.context_window_json_key).read_text(encoding="utf-8")
    )
    assert context_payload["lineId"] == "line-1"
    assert context_payload["regionId"] == "region-1"
    assert context_payload["lineIndexWithinRegion"] == 0
    assert store.recall_check is not None
    assert store.recall_check.recall_check_version == "layout-recall-v1"
    assert store.recall_check.missed_text_risk_score == 0.42
    assert store.recall_check.signals_json["candidate_count"] == 1
    assert len(store.rescue_candidates) == 1
    assert store.rescue_candidates[0].status == "ACCEPTED"
    assert store.rescue_candidates[0].candidate_kind == "LINE_EXPANSION"

    manifest_path = (
        tmp_path
        / "controlled/derived/project-1/doc-1/layout/layout-run-1/manifest.json"
    )
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["runId"] == "layout-run-1"
    assert manifest["pages"][0]["pageId"] == "page-1"
    assert manifest["pages"][0]["pageXmlSha256"] == page_result.page_xml_sha256
    assert manifest["pages"][0]["overlayJsonSha256"] == page_result.overlay_json_sha256


def test_materialize_layout_page_outputs_rejects_invalid_geometry(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    store = LayoutMaterializationStore()
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    with pytest.raises(DocumentValidationError):
        service.materialize_layout_page_outputs(
            project_id="project-1",
            document_id="doc-1",
            run_id="layout-run-1",
            page_id="page-1",
            canonical_page_payload={
                "schemaVersion": 1,
                "runId": "layout-run-1",
                "pageId": "page-1",
                "pageIndex": 0,
                "page": {"width": 1000, "height": 1400},
                "regions": [
                    {
                        "id": "region-1",
                        "type": "TEXT",
                        "polygon": [[20, 40], [1800, 40], [980, 320], [20, 320]],
                        "lineIds": ["line-1"],
                    }
                ],
                "lines": [
                    {
                        "id": "line-1",
                        "parentRegionId": "region-1",
                        "polygon": [[40, 80], [960, 80], [960, 120], [40, 120]],
                        "baseline": [[48, 112], [950, 112]],
                    }
                ],
            },
        )


def test_read_layout_outputs_returns_overlay_and_pagexml_after_materialization(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    store = LayoutMaterializationStore()
    preprocess_source_path = tmp_path / str(store.preprocess_result.output_object_key_gray)
    preprocess_source_path.parent.mkdir(parents=True, exist_ok=True)
    preprocess_source_path.write_bytes(_render_layout_source_page_bytes())
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    service.materialize_layout_page_outputs(
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        canonical_page_payload={
            "schemaVersion": 1,
            "runId": "layout-run-1",
            "pageId": "page-1",
            "pageIndex": 0,
            "page": {"width": 1000, "height": 1400},
            "regions": [
                {
                    "id": "region-1",
                    "type": "TEXT",
                    "polygon": [[20, 40], [980, 40], [980, 320], [20, 320]],
                    "lineIds": ["line-1"],
                }
            ],
            "lines": [
                {
                    "id": "line-1",
                    "parentRegionId": "region-1",
                    "polygon": [[40, 80], [960, 80], [960, 120], [40, 120]],
                    "baseline": [[48, 112], [950, 112]],
                }
            ],
            "readingOrder": [{"fromId": "region-1", "toId": "line-1"}],
        },
    )

    overlay = service.read_layout_page_overlay(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
    )
    assert overlay.payload["schemaVersion"] == 1
    assert overlay.payload["pageId"] == "page-1"
    assert overlay.etag_seed is not None

    pagexml = service.read_layout_page_xml(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
    )
    assert b"<PcGts" in pagexml.payload
    assert pagexml.media_type == "application/xml"
    assert pagexml.etag_seed is not None


def test_update_layout_page_reading_order_appends_version_and_refreshes_context(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    store = LayoutMaterializationStore()
    preprocess_source_path = tmp_path / str(store.preprocess_result.output_object_key_gray)
    preprocess_source_path.parent.mkdir(parents=True, exist_ok=True)
    preprocess_source_path.write_bytes(_render_layout_source_page_bytes())
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    service.materialize_layout_page_outputs(
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        canonical_page_payload={
            "schemaVersion": 1,
            "runId": "layout-run-1",
            "pageId": "page-1",
            "pageIndex": 0,
            "page": {"width": 1000, "height": 1400},
            "regions": [
                {
                    "id": "region-1",
                    "type": "TEXT",
                    "polygon": [[20, 40], [490, 40], [490, 320], [20, 320]],
                    "lineIds": ["line-1"],
                },
                {
                    "id": "region-2",
                    "type": "TEXT",
                    "polygon": [[510, 40], [980, 40], [980, 320], [510, 320]],
                    "lineIds": ["line-2"],
                },
            ],
            "lines": [
                {
                    "id": "line-1",
                    "parentRegionId": "region-1",
                    "polygon": [[40, 80], [470, 80], [470, 120], [40, 120]],
                    "baseline": [[48, 112], [460, 112]],
                },
                {
                    "id": "line-2",
                    "parentRegionId": "region-2",
                    "polygon": [[530, 80], [960, 80], [960, 120], [530, 120]],
                    "baseline": [[538, 112], [950, 112]],
                },
            ],
            "readingOrder": [
                {"fromId": "region-1", "toId": "line-1"},
                {"fromId": "line-1", "toId": "line-2"},
                {"fromId": "region-2", "toId": "line-2"},
            ],
            "readingOrderGroups": [
                {
                    "id": "g-0001",
                    "ordered": True,
                    "regionIds": ["region-1", "region-2"],
                }
            ],
            "readingOrderMeta": {
                "schemaVersion": 1,
                "mode": "ORDERED",
                "source": "AUTO_INFERRED",
                "ambiguityScore": 0.18,
                "columnCertainty": 0.9,
                "overlapConflictScore": 0.02,
                "orphanLineCount": 0,
                "nonTextComplexityScore": 0.0,
                "orderWithheld": False,
            },
        },
    )
    overlay_before = service.read_layout_page_overlay(
        current_user=_principal(roles=("ADMIN",)),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
    )
    assert overlay_before.payload["readingOrderMeta"]["versionEtag"]
    initial_version_etag = str(overlay_before.payload["readingOrderMeta"]["versionEtag"])
    initial_context_keys = {
        line_id: artifact.context_window_json_key
        for line_id, artifact in store.line_artifacts.items()
    }

    snapshot = service.update_layout_page_reading_order(
        current_user=_principal(roles=("ADMIN",)),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        version_etag=initial_version_etag,
        mode="UNORDERED",
        groups=[{"id": "g-0001", "ordered": False, "regionIds": ["region-1", "region-2"]}],
    )

    assert snapshot.mode == "UNORDERED"
    assert snapshot.layout_version_id == store.page_result.active_layout_version_id
    assert snapshot.version_etag != initial_version_etag
    assert len(snapshot.groups) == 1
    updated_context_keys = {
        line_id: artifact.context_window_json_key
        for line_id, artifact in store.line_artifacts.items()
    }
    assert updated_context_keys != initial_context_keys
    assert all(
        f"/versions/{snapshot.layout_version_id}/" in path
        for path in updated_context_keys.values()
    )

    overlay_after = service.read_layout_page_overlay(
        current_user=_principal(roles=("ADMIN",)),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
    )
    assert overlay_after.payload["readingOrderMeta"]["layoutVersionId"] == snapshot.layout_version_id
    assert overlay_after.payload["readingOrderMeta"]["versionEtag"] == snapshot.version_etag

    with pytest.raises(DocumentLayoutConflictError):
        service.update_layout_page_reading_order(
            current_user=_principal(roles=("ADMIN",)),
            project_id="project-1",
            document_id="doc-1",
            run_id="layout-run-1",
            page_id="page-1",
            version_etag=initial_version_etag,
            mode="ORDERED",
            groups=[{"id": "g-0001", "ordered": True, "regionIds": ["region-1", "region-2"]}],
        )


def test_layout_line_artifacts_surface_paths_and_assets(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = LayoutMaterializationStore()
    preprocess_source_path = tmp_path / str(store.preprocess_result.output_object_key_gray)
    preprocess_source_path.parent.mkdir(parents=True, exist_ok=True)
    preprocess_source_path.write_bytes(_render_layout_source_page_bytes())
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    service.materialize_layout_page_outputs(
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        canonical_page_payload={
            "schemaVersion": 1,
            "runId": "layout-run-1",
            "pageId": "page-1",
            "pageIndex": 0,
            "page": {"width": 1000, "height": 1400},
            "regions": [
                {
                    "id": "region-1",
                    "type": "TEXT",
                    "polygon": [[20, 40], [980, 40], [980, 320], [20, 320]],
                    "lineIds": ["line-1"],
                }
            ],
            "lines": [
                {
                    "id": "line-1",
                    "parentRegionId": "region-1",
                    "polygon": [[40, 80], [960, 80], [960, 120], [40, 120]],
                    "baseline": [[48, 112], [950, 112]],
                }
            ],
            "readingOrder": [{"fromId": "region-1", "toId": "line-1"}],
        },
    )

    snapshot = service.get_layout_line_artifacts(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        line_id="line-1",
    )
    assert snapshot.line_crop_path.endswith("/lines/line-1/crop")
    assert snapshot.region_crop_path is not None
    assert snapshot.page_thumbnail_path.endswith("/pages/page-1/thumbnail")
    assert snapshot.context_window_path.endswith("/lines/line-1/context")
    assert snapshot.context_window["lineId"] == "line-1"

    line_crop = service.read_layout_line_crop_image(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        line_id="line-1",
        variant="line",
    )
    assert line_crop.media_type == "image/png"
    assert line_crop.payload

    region_crop = service.read_layout_line_crop_image(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        line_id="line-1",
        variant="region",
    )
    assert region_crop.media_type == "image/png"
    assert region_crop.payload

    thumbnail = service.read_layout_page_thumbnail(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
    )
    assert thumbnail.media_type == "image/png"
    assert thumbnail.payload

    context = service.read_layout_line_context_window(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        line_id="line-1",
    )
    assert context.payload["lineId"] == "line-1"


def test_update_layout_page_elements_appends_version_and_invalidates_downstream(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    store = LayoutMaterializationStore()
    preprocess_source_path = tmp_path / str(store.preprocess_result.output_object_key_gray)
    preprocess_source_path.parent.mkdir(parents=True, exist_ok=True)
    preprocess_source_path.write_bytes(_render_layout_source_page_bytes())
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    service.materialize_layout_page_outputs(
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        canonical_page_payload={
            "schemaVersion": 1,
            "runId": "layout-run-1",
            "pageId": "page-1",
            "pageIndex": 0,
            "page": {"width": 1000, "height": 1400},
            "regions": [
                {
                    "id": "region-1",
                    "type": "TEXT",
                    "polygon": [[20, 40], [490, 40], [490, 320], [20, 320]],
                    "lineIds": ["line-1"],
                },
                {
                    "id": "region-2",
                    "type": "TEXT",
                    "polygon": [[510, 40], [980, 40], [980, 320], [510, 320]],
                    "lineIds": ["line-2"],
                },
            ],
            "lines": [
                {
                    "id": "line-1",
                    "parentRegionId": "region-1",
                    "polygon": [[40, 80], [470, 80], [470, 120], [40, 120]],
                    "baseline": [[48, 112], [460, 112]],
                },
                {
                    "id": "line-2",
                    "parentRegionId": "region-2",
                    "polygon": [[530, 80], [960, 80], [960, 120], [530, 120]],
                    "baseline": [[538, 112], [950, 112]],
                },
            ],
            "readingOrder": [
                {"fromId": "region-1", "toId": "line-1"},
                {"fromId": "line-1", "toId": "line-2"},
                {"fromId": "region-2", "toId": "line-2"},
            ],
            "readingOrderGroups": [
                {
                    "id": "g-0001",
                    "ordered": True,
                    "regionIds": ["region-1", "region-2"],
                }
            ],
        },
    )
    before_overlay = service.read_layout_page_overlay(
        current_user=_principal(roles=("ADMIN",)),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
    )
    baseline_etag = str(before_overlay.payload["readingOrderMeta"]["versionEtag"])

    snapshot = service.update_layout_page_elements(
        current_user=_principal(roles=("ADMIN",)),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        version_etag=baseline_etag,
        operations=[
            {
                "kind": "MOVE_LINE",
                "lineId": "line-1",
                "polygon": [
                    {"x": 44, "y": 90},
                    {"x": 476, "y": 90},
                    {"x": 476, "y": 130},
                    {"x": 44, "y": 130},
                ],
            },
            {
                "kind": "ASSIGN_LINE_REGION",
                "lineId": "line-2",
                "parentRegionId": "region-1",
                "afterLineId": "line-1",
            },
            {
                "kind": "REORDER_REGION_LINES",
                "regionId": "region-1",
                "lineIds": ["line-2", "line-1"],
            },
            {
                "kind": "SET_REGION_READING_ORDER_INCLUDED",
                "regionId": "region-2",
                "includeInReadingOrder": False,
            },
        ],
    )

    assert snapshot.operations_applied == 4
    assert snapshot.layout_version_id == store.page_result.active_layout_version_id
    assert snapshot.version_etag != baseline_etag
    assert snapshot.downstream_transcription_invalidated is True
    assert snapshot.downstream_transcription_state == "STALE"
    assert snapshot.downstream_transcription_invalidated_reason is not None
    assert "page-1" in snapshot.downstream_transcription_invalidated_reason
    assert store.layout_projection.downstream_transcription_state == "STALE"

    updated_overlay = snapshot.overlay_payload
    line_two = next(
        element
        for element in updated_overlay["elements"]
        if element["id"] == "line-2"
    )
    assert line_two["parentId"] == "region-1"
    groups = updated_overlay["readingOrderGroups"]
    assert all("region-2" not in group["regionIds"] for group in groups)
    assert updated_overlay["readingOrderMeta"]["layoutVersionId"] == snapshot.layout_version_id
    assert updated_overlay["readingOrderMeta"]["versionEtag"] == snapshot.version_etag
    assert all(
        f"/versions/{snapshot.layout_version_id}/" in artifact.line_crop_key
        for artifact in store.line_artifacts.values()
    )

    with pytest.raises(DocumentLayoutConflictError):
        service.update_layout_page_elements(
            current_user=_principal(roles=("ADMIN",)),
            project_id="project-1",
            document_id="doc-1",
            run_id="layout-run-1",
            page_id="page-1",
            version_etag=baseline_etag,
            operations=[
                {
                    "kind": "MOVE_REGION",
                    "regionId": "region-1",
                    "polygon": [
                        {"x": 20, "y": 40},
                        {"x": 490, "y": 40},
                        {"x": 490, "y": 320},
                        {"x": 20, "y": 320},
                    ],
                }
            ],
        )


def test_update_layout_page_elements_rejects_invalid_geometry_and_unknown_elements(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    store = LayoutMaterializationStore()
    preprocess_source_path = tmp_path / str(store.preprocess_result.output_object_key_gray)
    preprocess_source_path.parent.mkdir(parents=True, exist_ok=True)
    preprocess_source_path.write_bytes(_render_layout_source_page_bytes())
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    service.materialize_layout_page_outputs(
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        canonical_page_payload={
            "schemaVersion": 1,
            "runId": "layout-run-1",
            "pageId": "page-1",
            "pageIndex": 0,
            "page": {"width": 1000, "height": 1400},
            "regions": [
                {
                    "id": "region-1",
                    "type": "TEXT",
                    "polygon": [[20, 40], [980, 40], [980, 320], [20, 320]],
                    "lineIds": ["line-1"],
                }
            ],
            "lines": [
                {
                    "id": "line-1",
                    "parentRegionId": "region-1",
                    "polygon": [[40, 80], [960, 80], [960, 120], [40, 120]],
                    "baseline": [[48, 112], [950, 112]],
                }
            ],
            "readingOrder": [{"fromId": "region-1", "toId": "line-1"}],
        },
    )
    overlay = service.read_layout_page_overlay(
        current_user=_principal(roles=("ADMIN",)),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
    )
    etag = str(overlay.payload["readingOrderMeta"]["versionEtag"])

    with pytest.raises(DocumentValidationError):
        service.update_layout_page_elements(
            current_user=_principal(roles=("ADMIN",)),
            project_id="project-1",
            document_id="doc-1",
            run_id="layout-run-1",
            page_id="page-1",
            version_etag=etag,
            operations=[
                {
                    "kind": "MOVE_REGION",
                    "regionId": "region-1",
                    "polygon": [
                        {"x": 20, "y": 40},
                        {"x": 1600, "y": 40},
                        {"x": 980, "y": 320},
                        {"x": 20, "y": 320},
                    ],
                }
            ],
        )

    with pytest.raises(DocumentValidationError):
        service.update_layout_page_elements(
            current_user=_principal(roles=("ADMIN",)),
            project_id="project-1",
            document_id="doc-1",
            run_id="layout-run-1",
            page_id="page-1",
            version_etag=etag,
            operations=[
                {
                    "kind": "DELETE_LINE",
                    "lineId": "line-missing",
                }
            ],
        )


def test_layout_recall_status_and_rescue_candidates_surface(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    store = LayoutMaterializationStore()
    preprocess_source_path = tmp_path / str(store.preprocess_result.output_object_key_gray)
    preprocess_source_path.parent.mkdir(parents=True, exist_ok=True)
    preprocess_source_path.write_bytes(_render_layout_source_page_bytes())
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    service.materialize_layout_page_outputs(
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
        canonical_page_payload={
            "schemaVersion": 1,
            "runId": "layout-run-1",
            "pageId": "page-1",
            "pageIndex": 0,
            "page": {"width": 1000, "height": 1400},
            "regions": [
                {
                    "id": "region-1",
                    "type": "TEXT",
                    "polygon": [[20, 40], [980, 40], [980, 320], [20, 320]],
                    "lineIds": ["line-1"],
                }
            ],
            "lines": [
                {
                    "id": "line-1",
                    "parentRegionId": "region-1",
                    "polygon": [[40, 80], [960, 80], [960, 120], [40, 120]],
                    "baseline": [[48, 112], [950, 112]],
                }
            ],
            "readingOrder": [{"fromId": "region-1", "toId": "line-1"}],
        },
        page_recall_status="NEEDS_RESCUE",
        recall_check_version="layout-recall-v1",
        missed_text_risk_score=0.39,
        recall_signals_json={
            "algorithm_version": "layout-recall-v1",
            "candidate_count": 2,
            "accepted_candidate_count": 1,
        },
        rescue_candidates=[
            {
                "id": "resc-0001-001-a",
                "candidate_kind": "LINE_EXPANSION",
                "geometry_json": {"schemaVersion": 1, "bbox": {"x": 10, "y": 20, "width": 100, "height": 30}},
                "confidence": 0.66,
                "source_signal": "UNASSOCIATED_COMPONENT_NEAR_LINE",
                "status": "ACCEPTED",
            },
            {
                "id": "resc-0001-002-b",
                "candidate_kind": "PAGE_WINDOW",
                "geometry_json": {"schemaVersion": 1, "bbox": {"x": 120, "y": 220, "width": 140, "height": 70}},
                "confidence": 0.31,
                "source_signal": "UNASSOCIATED_COMPONENT_PAGE_WINDOW",
                "status": "REJECTED",
            },
        ],
    )

    recall_status = service.get_layout_page_recall_status(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
    )
    assert recall_status.page_recall_status == "NEEDS_RESCUE"
    assert recall_status.recall_check_version == "layout-recall-v1"
    assert recall_status.unresolved_count == 0
    assert recall_status.rescue_candidate_counts["ACCEPTED"] == 1
    assert recall_status.rescue_candidate_counts["REJECTED"] == 1
    assert "ACCEPTED_RESCUE_MISSING" not in recall_status.blocker_reason_codes

    rescue_candidates = service.list_layout_page_rescue_candidates(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-1",
        run_id="layout-run-1",
        page_id="page-1",
    )
    assert len(rescue_candidates) == 2
    assert {candidate.candidate_kind for candidate in rescue_candidates} == {
        "LINE_EXPANSION",
        "PAGE_WINDOW",
    }


def test_correct_transcription_line_appends_version_and_invalidates_downstream_basis(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    store = TranscriptionCorrectionStore()
    storage = DocumentStorage(settings=settings)
    source_pagexml = b"""<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">
  <Page imageFilename="page-1.png" imageWidth="1000" imageHeight="1400">
    <TextRegion id="region-1">
      <TextLine id="line-1">
        <TextEquiv><Unicode>Dear diary</Unicode></TextEquiv>
      </TextLine>
    </TextRegion>
  </Page>
</PcGts>
"""
    stored_pagexml = storage.write_transcription_page_xml(
        project_id=store.run.project_id,
        document_id=store.run.document_id,
        run_id=store.run.id,
        page_index=store.page.page_index,
        payload=source_pagexml,
    )
    assert stored_pagexml.object_key == store.page_result.pagexml_out_key

    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=storage,
    )

    snapshot = service.correct_transcription_line(
        current_user=_principal(roles=("ADMIN",)),
        project_id=store.run.project_id,
        document_id=store.run.document_id,
        run_id=store.run.id,
        page_id=store.page.id,
        line_id=store.line.line_id,
        text_diplomatic="Dear diary!",
        version_etag="line-etag-1",
        edit_reason="Add exclamation mark",
    )

    assert snapshot.text_changed is True
    assert snapshot.active_version.base_version_id == "transcript-version-1"
    assert snapshot.active_version.text_diplomatic == "Dear diary!"
    assert snapshot.line.active_transcript_version_id == snapshot.active_version.id
    assert snapshot.line.token_anchor_status == "REFRESH_REQUIRED"
    assert snapshot.projection.source_pagexml_sha256 == "source-pagexml-sha-1"
    assert (
        f"/versions/{snapshot.active_version.id}/page/0.xml"
        in snapshot.projection.corrected_pagexml_key
    )
    assert snapshot.downstream_projection is not None
    assert snapshot.downstream_projection.downstream_redaction_state == "STALE"
    assert snapshot.downstream_projection.downstream_redaction_invalidated_at is not None
    assert snapshot.downstream_projection.downstream_redaction_invalidated_reason is not None
    assert snapshot.active_version.id in snapshot.downstream_projection.downstream_redaction_invalidated_reason

    previous_version = next(
        item for item in store.transcript_versions if item.id == "transcript-version-1"
    )
    assert previous_version.superseded_by_version_id == snapshot.active_version.id

    corrected_pagexml_path = tmp_path / snapshot.projection.corrected_pagexml_key
    assert corrected_pagexml_path.exists()
    corrected_payload = corrected_pagexml_path.read_text(encoding="utf-8")
    assert "Dear diary!" in corrected_payload


def test_correct_transcription_line_rejects_stale_version_etag(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = TranscriptionCorrectionStore()
    storage = DocumentStorage(settings=settings)
    storage.write_transcription_page_xml(
        project_id=store.run.project_id,
        document_id=store.run.document_id,
        run_id=store.run.id,
        page_index=store.page.page_index,
        payload=b"""<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">
  <Page imageFilename="page-1.png" imageWidth="1000" imageHeight="1400">
    <TextRegion id="region-1">
      <TextLine id="line-1">
        <TextEquiv><Unicode>Dear diary</Unicode></TextEquiv>
      </TextLine>
    </TextRegion>
  </Page>
</PcGts>
""",
    )
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=storage,
    )

    with pytest.raises(DocumentTranscriptionConflictError):
        service.correct_transcription_line(
            current_user=_principal(roles=("ADMIN",)),
            project_id=store.run.project_id,
            document_id=store.run.document_id,
            run_id=store.run.id,
            page_id=store.page.id,
            line_id=store.line.line_id,
            text_diplomatic="Dear diary?",
            version_etag="line-etag-stale",
        )


def test_variant_layer_decisions_append_events_without_mutating_diplomatic_text(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    store = TranscriptionCorrectionStore()
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=FakeProjectService(),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    layers_snapshot: DocumentTranscriptionVariantLayersSnapshot = (
        service.list_transcription_variant_layers(
            current_user=_principal(roles=("ADMIN",)),
            project_id=store.run.project_id,
            document_id=store.run.document_id,
            run_id=store.run.id,
            page_id=store.page.id,
            variant_kind="NORMALISED",
        )
    )
    assert layers_snapshot.variant_kind == "NORMALISED"
    assert len(layers_snapshot.layers) == 1
    assert layers_snapshot.layers[0].layer.base_transcript_version_id == "transcript-version-1"
    assert layers_snapshot.layers[0].suggestions[0].status == "PENDING"

    first_decision: DocumentTranscriptionVariantSuggestionDecisionSnapshot = (
        service.record_transcription_variant_suggestion_decision(
            current_user=_principal(roles=("ADMIN",)),
            project_id=store.run.project_id,
            document_id=store.run.document_id,
            run_id=store.run.id,
            page_id=store.page.id,
            variant_kind="NORMALISED",
            suggestion_id="variant-suggestion-1",
            decision="ACCEPT",
            reason="Prefer standard sentence casing.",
        )
    )
    assert first_decision.suggestion.status == "ACCEPTED"
    assert first_decision.event.from_status == "PENDING"
    assert first_decision.event.to_status == "ACCEPTED"

    second_decision: DocumentTranscriptionVariantSuggestionDecisionSnapshot = (
        service.record_transcription_variant_suggestion_decision(
            current_user=_principal(roles=("ADMIN",)),
            project_id=store.run.project_id,
            document_id=store.run.document_id,
            run_id=store.run.id,
            page_id=store.page.id,
            variant_kind="NORMALISED",
            suggestion_id="variant-suggestion-1",
            decision="REJECT",
            reason="Revert for diplomatic comparison.",
        )
    )
    assert second_decision.suggestion.status == "REJECTED"
    assert second_decision.event.from_status == "ACCEPTED"
    assert second_decision.event.to_status == "REJECTED"
    assert len(store.variant_suggestion_events) == 2
    assert store.line.text_diplomatic == "Dear diary"


class TranscriptionTriageStore:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.document = DocumentRecord(
            id="doc-triage",
            project_id="project-1",
            original_filename="triage.pdf",
            stored_filename="controlled/raw/project-1/doc-triage/original.bin",
            content_type_detected="application/pdf",
            bytes=1024,
            sha256="sha-doc-triage",
            page_count=2,
            status="READY",
            created_by="user-1",
            created_at=now - timedelta(hours=3),
            updated_at=now - timedelta(hours=2),
        )
        self.run = TranscriptionRunRecord(
            id="transcription-run-triage",
            project_id="project-1",
            document_id=self.document.id,
            input_preprocess_run_id="pre-run-1",
            input_layout_run_id="layout-run-1",
            input_layout_snapshot_hash="layout-snapshot-triage",
            engine="VLM_LINE_CONTEXT",
            model_id="model-transcription-v1",
            project_model_assignment_id=None,
            prompt_template_id="prompt-v1",
            prompt_template_sha256="prompt-sha-1",
            response_schema_version=1,
            confidence_basis="MODEL_NATIVE",
            confidence_calibration_version="v1",
            params_json={
                "review_confidence_threshold": 0.85,
                "fallback_confidence_threshold": 0.72,
            },
            pipeline_version="transcription-v1",
            container_digest="ukde/transcription:v1",
            attempt_number=1,
            supersedes_transcription_run_id=None,
            superseded_by_transcription_run_id=None,
            status="SUCCEEDED",
            created_by="user-1",
            created_at=now - timedelta(hours=2),
            started_at=now - timedelta(hours=2),
            finished_at=now - timedelta(hours=1, minutes=55),
            canceled_by=None,
            canceled_at=None,
            failure_reason=None,
        )
        self.projection = DocumentTranscriptionProjectionRecord(
            document_id=self.document.id,
            project_id=self.document.project_id,
            active_transcription_run_id=self.run.id,
            active_layout_run_id=self.run.input_layout_run_id,
            active_layout_snapshot_hash=self.run.input_layout_snapshot_hash,
            active_preprocess_run_id=self.run.input_preprocess_run_id,
            downstream_redaction_state="NOT_STARTED",
            downstream_redaction_invalidated_at=None,
            downstream_redaction_invalidated_reason=None,
            updated_at=now - timedelta(hours=1, minutes=50),
        )
        self.page_results: list[PageTranscriptionResultRecord] = [
            PageTranscriptionResultRecord(
                run_id=self.run.id,
                page_id="page-a",
                page_index=0,
                status="FAILED",
                pagexml_out_key=None,
                pagexml_out_sha256=None,
                raw_model_response_key="controlled/derived/project-1/doc-triage/transcription/run/page/0.response.json",
                raw_model_response_sha256="sha-page-a-response",
                hocr_out_key=None,
                hocr_out_sha256=None,
                metrics_json={
                    "invalidTargetCount": 2,
                    "fallbackInvocationCount": 2,
                },
                warnings_json=["SCHEMA_VALIDATION_FAILED"],
                failure_reason="Structured output failed.",
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=2),
            ),
            PageTranscriptionResultRecord(
                run_id=self.run.id,
                page_id="page-b",
                page_index=1,
                status="SUCCEEDED",
                pagexml_out_key="controlled/derived/project-1/doc-triage/transcription/run/page/1.xml",
                pagexml_out_sha256="sha-page-b-xml",
                raw_model_response_key="controlled/derived/project-1/doc-triage/transcription/run/page/1.response.json",
                raw_model_response_sha256="sha-page-b-response",
                hocr_out_key=None,
                hocr_out_sha256=None,
                metrics_json={"fallbackInvocationCount": 1},
                warnings_json=[],
                failure_reason=None,
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=2),
            ),
        ]
        self.lines_by_page: dict[str, list[LineTranscriptionResultRecord]] = {
            "page-a": [
                LineTranscriptionResultRecord(
                    run_id=self.run.id,
                    page_id="page-a",
                    line_id="line-a1",
                    text_diplomatic="",
                    conf_line=0.41,
                    confidence_band="LOW",
                    confidence_basis="MODEL_NATIVE",
                    confidence_calibration_version="v1",
                    alignment_json_key=None,
                    char_boxes_key=None,
                    schema_validation_status="INVALID",
                    flags_json={},
                    machine_output_sha256="sha-line-a1",
                    active_transcript_version_id=None,
                    version_etag="etag-line-a1",
                    token_anchor_status="REFRESH_REQUIRED",
                    created_at=now,
                    updated_at=now,
                ),
                LineTranscriptionResultRecord(
                    run_id=self.run.id,
                    page_id="page-a",
                    line_id="line-a2",
                    text_diplomatic="Low confidence text",
                    conf_line=0.63,
                    confidence_band="LOW",
                    confidence_basis="READ_AGREEMENT",
                    confidence_calibration_version="v1",
                    alignment_json_key=None,
                    char_boxes_key=None,
                    schema_validation_status="VALID",
                    flags_json={},
                    machine_output_sha256="sha-line-a2",
                    active_transcript_version_id=None,
                    version_etag="etag-line-a2",
                    token_anchor_status="CURRENT",
                    created_at=now,
                    updated_at=now,
                ),
            ],
            "page-b": [
                LineTranscriptionResultRecord(
                    run_id=self.run.id,
                    page_id="page-b",
                    line_id="line-b1",
                    text_diplomatic="Stable text",
                    conf_line=0.96,
                    confidence_band="HIGH",
                    confidence_basis="MODEL_NATIVE",
                    confidence_calibration_version="v1",
                    alignment_json_key=None,
                    char_boxes_key=None,
                    schema_validation_status="VALID",
                    flags_json={},
                    machine_output_sha256="sha-line-b1",
                    active_transcript_version_id=None,
                    version_etag="etag-line-b1",
                    token_anchor_status="CURRENT",
                    created_at=now,
                    updated_at=now,
                ),
                LineTranscriptionResultRecord(
                    run_id=self.run.id,
                    page_id="page-b",
                    line_id="line-b2",
                    text_diplomatic="",
                    conf_line=0.82,
                    confidence_band="MEDIUM",
                    confidence_basis="READ_AGREEMENT",
                    confidence_calibration_version="v1",
                    alignment_json_key=None,
                    char_boxes_key=None,
                    schema_validation_status="VALID",
                    flags_json={},
                    machine_output_sha256="sha-line-b2",
                    active_transcript_version_id=None,
                    version_etag="etag-line-b2",
                    token_anchor_status="CURRENT",
                    created_at=now,
                    updated_at=now,
                ),
            ],
        }
        self.tokens_by_page: dict[str, list[TokenTranscriptionResultRecord]] = {
            "page-a": [
                TokenTranscriptionResultRecord(
                    run_id=self.run.id,
                    page_id="page-a",
                    line_id="line-a2",
                    token_id="tok-a1",
                    token_index=0,
                    token_text="Low",
                    token_confidence=0.61,
                    bbox_json=None,
                    polygon_json=None,
                    source_kind="LINE",
                    source_ref_id="line-a2",
                    projection_basis="ENGINE_OUTPUT",
                    created_at=now,
                    updated_at=now,
                )
            ],
            "page-b": [
                TokenTranscriptionResultRecord(
                    run_id=self.run.id,
                    page_id="page-b",
                    line_id="line-b1",
                    token_id="tok-b1",
                    token_index=0,
                    token_text="Stable",
                    token_confidence=0.94,
                    bbox_json=None,
                    polygon_json=None,
                    source_kind="LINE",
                    source_ref_id="line-b1",
                    projection_basis="ENGINE_OUTPUT",
                    created_at=now,
                    updated_at=now,
                )
            ],
        }

    def get_document(self, *, project_id: str, document_id: str) -> DocumentRecord | None:
        if project_id != self.document.project_id or document_id != self.document.id:
            return None
        return self.document

    def get_transcription_projection(
        self, *, project_id: str, document_id: str
    ) -> DocumentTranscriptionProjectionRecord | None:
        if project_id != self.projection.project_id or document_id != self.projection.document_id:
            return None
        return self.projection

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
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
        ):
            return [], None
        rows = list(self.page_results)
        if isinstance(status, str):
            rows = [row for row in rows if row.status == status]
        start = max(0, cursor)
        end = start + max(1, min(page_size, 500))
        next_cursor = end if end < len(rows) else None
        return rows[start:end], next_cursor

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
        ):
            return []
        return list(self.lines_by_page.get(page_id, []))

    def list_token_transcription_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[TokenTranscriptionResultRecord]:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
        ):
            return []
        return list(self.tokens_by_page.get(page_id, []))

    def update_page_transcription_assignment(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        reviewer_user_id: str | None,
        updated_by: str,
    ) -> PageTranscriptionResultRecord:
        if (
            project_id != self.run.project_id
            or document_id != self.run.document_id
            or run_id != self.run.id
        ):
            raise RuntimeError("Transcription run not found.")
        page_index = next(
            (index for index, row in enumerate(self.page_results) if row.page_id == page_id),
            -1,
        )
        if page_index < 0:
            raise RuntimeError("Transcription page result not found.")
        updated = replace(
            self.page_results[page_index],
            reviewer_assignment_user_id=reviewer_user_id,
            reviewer_assignment_updated_by=updated_by,
            reviewer_assignment_updated_at=datetime.now(UTC),
        )
        self.page_results[page_index] = updated
        return updated


class TriageProjectService:
    def __init__(
        self,
        *,
        role: str = "REVIEWER",
        is_member: bool = True,
    ) -> None:
        self.role = role
        self.is_member = is_member

    def resolve_workspace_context(self, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        return SimpleNamespace(
            is_member=self.is_member,
            can_access_settings=False,
            summary=SimpleNamespace(current_user_role=self.role),
        )


def test_transcription_triage_ranking_is_deterministic_and_explainable(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = TranscriptionTriageStore()
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=TriageProjectService(role="REVIEWER"),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    _, run, rows, _ = service.list_transcription_triage(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-triage",
        run_id="transcription-run-triage",
        page_size=20,
    )

    assert run is not None
    assert len(rows) == 2
    assert rows[0].page_id == "page-a"
    assert rows[0].ranking_score >= rows[1].ranking_score
    assert rows[0].ranking_rationale != ""
    assert "FAILED" in rows[0].issues


def test_transcription_metrics_align_with_triage_counts(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = TranscriptionTriageStore()
    service = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=TriageProjectService(role="REVIEWER"),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    _, _, triage_rows, _ = service.list_transcription_triage(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-triage",
        run_id="transcription-run-triage",
        page_size=20,
    )
    _, run, metrics = service.get_transcription_metrics(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-triage",
        run_id="transcription-run-triage",
    )

    assert run is not None
    assert metrics.low_confidence_line_count == sum(
        item.low_confidence_lines for item in triage_rows
    )
    assert metrics.low_confidence_page_count == sum(
        1 for item in triage_rows if item.low_confidence_lines > 0
    )
    assert metrics.line_count == sum(metrics.confidence_bands.values())
    assert metrics.fallback_invocation_count == 3


def test_transcription_assignment_requires_mutation_role(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = TranscriptionTriageStore()
    service_read_only = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=TriageProjectService(role="RESEARCHER"),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )

    with pytest.raises(DocumentTranscriptionAccessDeniedError):
        service_read_only.update_transcription_triage_page_assignment(
            current_user=_principal(),
            project_id="project-1",
            document_id="doc-triage",
            page_id="page-a",
            reviewer_user_id="user-reviewer",
            run_id="transcription-run-triage",
        )

    service_mutation = DocumentService(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        project_service=TriageProjectService(role="REVIEWER"),  # type: ignore[arg-type]
        storage=DocumentStorage(settings=settings),
    )
    _, _, row = service_mutation.update_transcription_triage_page_assignment(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-triage",
        page_id="page-a",
        reviewer_user_id="user-reviewer",
        run_id="transcription-run-triage",
    )
    assert row.reviewer_assignment_user_id == "user-reviewer"
    assert row.reviewer_assignment_updated_by == "user-1"
