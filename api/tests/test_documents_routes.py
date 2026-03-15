from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import BinaryIO, Literal

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.documents.models import (
    TranscriptionCompareDecisionEventRecord,
    TranscriptionCompareDecisionRecord,
    DocumentTranscriptionProjectionRecord,
    LineTranscriptionResultRecord,
    PageTranscriptionResultRecord,
    TranscriptVariantLayerRecord,
    TranscriptVariantSuggestionEventRecord,
    TranscriptVariantSuggestionRecord,
    TranscriptVersionRecord,
    TokenTranscriptionResultRecord,
    TranscriptionOutputProjectionRecord,
    TranscriptionRunRecord,
    DocumentLayoutProjectionRecord,
    LayoutActivationBlockerRecord,
    LayoutActivationDownstreamImpactRecord,
    LayoutActivationGateRecord,
    DocumentPreprocessProjectionRecord,
    DocumentImportRecord,
    DocumentImportSnapshot,
    DocumentListFilters,
    DocumentPageRecord,
    LayoutRescueCandidateRecord,
    LayoutRunRecord,
    PageLayoutResultRecord,
    PagePreprocessResultRecord,
    PreprocessDownstreamBasisReferencesRecord,
    PreprocessRunRecord,
    DocumentProcessingRunRecord,
    DocumentUploadSessionRecord,
    DocumentRecord,
)
from app.documents.service import (
    DocumentTranscriptionAccessDeniedError,
    DocumentTranscriptionCompareFinalizeSnapshot,
    DocumentTranscriptionCompareLineDiffSnapshot,
    DocumentTranscriptionComparePageSnapshot,
    DocumentTranscriptionCompareSnapshot,
    DocumentTranscriptionCompareTokenDiffSnapshot,
    DocumentTranscriptionConflictError,
    DocumentTranscriptionLineCorrectionSnapshot,
    DocumentTranscriptionLineVersionHistorySnapshot,
    DocumentTranscriptionLowConfidencePageSnapshot,
    DocumentTranscriptionMetricsSnapshot,
    DocumentTranscriptionOverviewSnapshot,
    DocumentTranscriptionPageRescueSourcesSnapshot,
    DocumentTranscriptionRescuePageStatusSnapshot,
    DocumentTranscriptionRescueSourceSnapshot,
    DocumentTranscriptionRunNotFoundError,
    DocumentTranscriptionRunRescueStatusSnapshot,
    DocumentTranscriptionTriagePageSnapshot,
    DocumentTranscriptionVariantLayerSnapshot,
    DocumentTranscriptionVariantLayersSnapshot,
    DocumentTranscriptionVariantSuggestionDecisionSnapshot,
    DocumentTranscriptVersionLineageSnapshot,
    DocumentLayoutAccessDeniedError,
    DocumentLayoutConflictError,
    DocumentLayoutContextWindowAsset,
    DocumentLayoutElementsSnapshot,
    DocumentLayoutLineArtifactsSnapshot,
    DocumentLayoutOverlayAsset,
    DocumentLayoutReadingOrderGroupSnapshot,
    DocumentLayoutReadingOrderSnapshot,
    DocumentLayoutPageRecallStatusSnapshot,
    DocumentLayoutPageXmlAsset,
    DocumentLayoutOverviewSnapshot,
    DocumentLayoutRunNotFoundError,
    DocumentLayoutSummarySnapshot,
    DocumentPreprocessAccessDeniedError,
    DocumentPreprocessConflictError,
    DocumentPreprocessOverviewSnapshot,
    DocumentPreprocessRunNotFoundError,
    DocumentPreprocessCompareSnapshot,
    DocumentPreprocessComparePageSnapshot,
    DocumentPageImageAsset,
    DocumentPageVariantAvailability,
    DocumentPageVariantsSnapshot,
    DocumentImportConflictError,
    DocumentImportNotFoundError,
    DocumentNotFoundError,
    DocumentPageAssetNotReadyError,
    DocumentPageNotFoundError,
    DocumentProcessingRunNotFoundError,
    DocumentQuotaExceededError,
    DocumentRetryAccessDeniedError,
    DocumentRetryConflictError,
    DocumentUploadSessionSnapshot,
    DocumentValidationError,
    get_document_service,
)
from app.documents.store import (
    DocumentUploadSessionConflictError,
    DocumentUploadSessionNotFoundError,
)
from app.documents.validation import DocumentUploadValidationError, validate_extension_matches_magic
from app.jobs.service import get_job_service
from app.main import app
from app.projects.service import ProjectAccessDeniedError
from fastapi.testclient import TestClient

client = TestClient(app)
ADVANCED_RISK_CONFIRMATION_COPY = (
    "Advanced full-document preprocessing can remove faint handwriting details. "
    "Confirm only when stronger cleanup is necessary and compare review will follow."
)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeJobService:
    def __init__(self) -> None:
        self.enqueued: list[dict[str, str]] = []

    def enqueue_document_processing_job(
        self,
        *,
        project_id: str,
        document_id: str,
        job_type: Literal["EXTRACT_PAGES", "RENDER_THUMBNAILS"],
        created_by: str,
        processing_run_id: str | None = None,
    ) -> tuple[object, bool, str]:
        self.enqueued.append(
            {
                "project_id": project_id,
                "document_id": document_id,
                "job_type": job_type,
                "created_by": created_by,
                "processing_run_id": processing_run_id or "",
            }
        )
        return object(), True, "created"

    def run_worker_once(self, *, worker_id: str, lease_seconds: int):  # type: ignore[no-untyped-def]
        del worker_id
        del lease_seconds
        return None


class FakeDocumentService:
    def __init__(
        self,
        *,
        auto_scan: bool = False,
        max_upload_bytes: int = 8 * 1024 * 1024,
        project_quota_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        now = datetime.now(UTC)
        self.auto_scan = auto_scan
        self.max_upload_bytes = max_upload_bytes
        self.project_quota_bytes = project_quota_bytes
        self._settings = type(
            "FakeDocumentSettings",
            (),
            {
                "documents_resumable_chunk_bytes": 4 * 1024 * 1024,
                "documents_max_upload_bytes": max_upload_bytes,
            },
        )()
        self._documents: dict[str, list[DocumentRecord]] = {
            "project-1": [
                DocumentRecord(
                    id="doc-1",
                    project_id="project-1",
                    original_filename="diary-1871.pdf",
                    stored_filename=None,
                    content_type_detected="application/pdf",
                    bytes=None,
                    sha256=None,
                    page_count=None,
                    status="SCANNING",
                    created_by="user-1",
                    created_at=now - timedelta(minutes=5),
                    updated_at=now - timedelta(minutes=2),
                ),
                DocumentRecord(
                    id="doc-2",
                    project_id="project-1",
                    original_filename="register-1880.pdf",
                    stored_filename="controlled/raw/project-1/doc-2/original.bin",
                    content_type_detected="application/pdf",
                    bytes=125_000,
                    sha256="4a6f95f913f2f7f6f613ebd4f8f1df31a5a4f83017db8e8fbf949f4ba4af0bc9",
                    page_count=2,
                    status="READY",
                    created_by="user-1",
                    created_at=now - timedelta(days=1),
                    updated_at=now - timedelta(hours=6),
                ),
                DocumentRecord(
                    id="doc-3",
                    project_id="project-1",
                    original_filename="failed-collection.pdf",
                    stored_filename="controlled/raw/project-1/doc-3/original.bin",
                    content_type_detected="application/pdf",
                    bytes=110_000,
                    sha256="bf6f95f913f2f7f6f613ebd4f8f1df31a5a4f83017db8e8fbf949f4ba4af0bc8",
                    page_count=1,
                    status="FAILED",
                    created_by="user-1",
                    created_at=now - timedelta(days=2),
                    updated_at=now - timedelta(hours=1),
                ),
            ]
        }
        self._timeline: dict[str, list[DocumentProcessingRunRecord]] = {
            "doc-1": [
                DocumentProcessingRunRecord(
                    id="run-1",
                    document_id="doc-1",
                    attempt_number=1,
                    run_kind="SCAN",
                    supersedes_processing_run_id=None,
                    superseded_by_processing_run_id=None,
                    status="RUNNING",
                    created_by="user-1",
                    created_at=now - timedelta(minutes=5),
                    started_at=now - timedelta(minutes=4),
                    finished_at=None,
                    canceled_by=None,
                    canceled_at=None,
                    failure_reason=None,
                )
            ],
            "doc-2": [
                DocumentProcessingRunRecord(
                    id="run-5",
                    document_id="doc-2",
                    attempt_number=1,
                    run_kind="THUMBNAIL_RENDER",
                    supersedes_processing_run_id=None,
                    superseded_by_processing_run_id=None,
                    status="SUCCEEDED",
                    created_by="user-1",
                    created_at=now - timedelta(hours=5, minutes=45),
                    started_at=now - timedelta(hours=5, minutes=44),
                    finished_at=now - timedelta(hours=5, minutes=43),
                    canceled_by=None,
                    canceled_at=None,
                    failure_reason=None,
                ),
                DocumentProcessingRunRecord(
                    id="run-4",
                    document_id="doc-2",
                    attempt_number=1,
                    run_kind="EXTRACTION",
                    supersedes_processing_run_id=None,
                    superseded_by_processing_run_id=None,
                    status="SUCCEEDED",
                    created_by="user-1",
                    created_at=now - timedelta(hours=5, minutes=50),
                    started_at=now - timedelta(hours=5, minutes=49),
                    finished_at=now - timedelta(hours=5, minutes=46),
                    canceled_by=None,
                    canceled_at=None,
                    failure_reason=None,
                ),
            ],
            "doc-3": [
                DocumentProcessingRunRecord(
                    id="run-6",
                    document_id="doc-3",
                    attempt_number=1,
                    run_kind="EXTRACTION",
                    supersedes_processing_run_id=None,
                    superseded_by_processing_run_id=None,
                    status="FAILED",
                    created_by="user-1",
                    created_at=now - timedelta(hours=2),
                    started_at=now - timedelta(hours=2),
                    finished_at=now - timedelta(hours=1, minutes=58),
                    canceled_by=None,
                    canceled_at=None,
                    failure_reason="Fixture extraction failed.",
                )
            ],
        }
        self._pages: dict[str, list[DocumentPageRecord]] = {
            "doc-2": [
                DocumentPageRecord(
                    id="page-1",
                    document_id="doc-2",
                    page_index=0,
                    width=1000,
                    height=1400,
                    dpi=300,
                    source_width=1000,
                    source_height=1400,
                    source_dpi=300,
                    source_color_mode="GRAY",
                    status="READY",
                    derived_image_key="controlled/derived/project-1/doc-2/pages/0.png",
                    derived_image_sha256="sha-page-0",
                    thumbnail_key="controlled/derived/project-1/doc-2/thumbs/0.jpg",
                    thumbnail_sha256="sha-thumb-0",
                    failure_reason=None,
                    canceled_by=None,
                    canceled_at=None,
                    viewer_rotation=0,
                    created_at=now - timedelta(hours=5, minutes=48),
                    updated_at=now - timedelta(hours=5, minutes=43),
                ),
                DocumentPageRecord(
                    id="page-2",
                    document_id="doc-2",
                    page_index=1,
                    width=1000,
                    height=1400,
                    dpi=300,
                    source_width=1000,
                    source_height=1400,
                    source_dpi=300,
                    source_color_mode="GRAY",
                    status="READY",
                    derived_image_key="controlled/derived/project-1/doc-2/pages/1.png",
                    derived_image_sha256="sha-page-1",
                    thumbnail_key="controlled/derived/project-1/doc-2/thumbs/1.jpg",
                    thumbnail_sha256="sha-thumb-1",
                    failure_reason=None,
                    canceled_by=None,
                    canceled_at=None,
                    viewer_rotation=0,
                    created_at=now - timedelta(hours=5, minutes=48),
                    updated_at=now - timedelta(hours=5, minutes=43),
                ),
            ]
        }
        baseline_preprocess_run = PreprocessRunRecord(
            id="pre-run-1",
            project_id="project-1",
            document_id="doc-2",
            parent_run_id=None,
            attempt_number=1,
            superseded_by_run_id="pre-run-2",
            profile_id="BALANCED",
            params_json={},
            params_hash="hash-pre-run-1",
            pipeline_version="preprocess-v1",
            container_digest="ukde/preprocess:v1",
            status="SUCCEEDED",
            created_by="user-1",
            created_at=now - timedelta(hours=4),
            started_at=now - timedelta(hours=4),
            finished_at=now - timedelta(hours=3, minutes=59),
            failure_reason=None,
        )
        active_preprocess_run = PreprocessRunRecord(
            id="pre-run-2",
            project_id="project-1",
            document_id="doc-2",
            parent_run_id="pre-run-1",
            attempt_number=2,
            superseded_by_run_id=None,
            profile_id="BALANCED",
            params_json={"deskew": True},
            params_hash="hash-pre-run-2",
            pipeline_version="preprocess-v1",
            container_digest="ukde/preprocess:v1",
            status="SUCCEEDED",
            created_by="user-1",
            created_at=now - timedelta(hours=3),
            started_at=now - timedelta(hours=3),
            finished_at=now - timedelta(hours=2, minutes=59),
            failure_reason=None,
        )
        self._preprocess_runs: dict[str, list[PreprocessRunRecord]] = {
            "doc-2": [active_preprocess_run, baseline_preprocess_run]
        }
        self._preprocess_pages: dict[str, list[PagePreprocessResultRecord]] = {
            "pre-run-1": [
                PagePreprocessResultRecord(
                    run_id="pre-run-1",
                    page_id="page-1",
                    page_index=0,
                    status="SUCCEEDED",
                    quality_gate_status="PASS",
                    input_object_key="controlled/derived/project-1/doc-2/pages/0.png",
                    output_object_key_gray="controlled/derived/project-1/doc-2/preprocess/pre-run-1/gray/0.png",
                    output_object_key_bin=None,
                    metrics_json={"dpi_estimate": 300},
                    sha256_gray="gray-1-0",
                    sha256_bin=None,
                    warnings_json=[],
                    failure_reason=None,
                    created_at=now - timedelta(hours=4),
                    updated_at=now - timedelta(hours=4),
                ),
                PagePreprocessResultRecord(
                    run_id="pre-run-1",
                    page_id="page-2",
                    page_index=1,
                    status="SUCCEEDED",
                    quality_gate_status="REVIEW_REQUIRED",
                    input_object_key="controlled/derived/project-1/doc-2/pages/1.png",
                    output_object_key_gray="controlled/derived/project-1/doc-2/preprocess/pre-run-1/gray/1.png",
                    output_object_key_bin=None,
                    metrics_json={"dpi_estimate": 180},
                    sha256_gray="gray-1-1",
                    sha256_bin=None,
                    warnings_json=["LOW_DPI"],
                    failure_reason=None,
                    created_at=now - timedelta(hours=4),
                    updated_at=now - timedelta(hours=4),
                ),
            ],
            "pre-run-2": [
                PagePreprocessResultRecord(
                    run_id="pre-run-2",
                    page_id="page-1",
                    page_index=0,
                    status="SUCCEEDED",
                    quality_gate_status="PASS",
                    input_object_key="controlled/derived/project-1/doc-2/pages/0.png",
                    output_object_key_gray="controlled/derived/project-1/doc-2/preprocess/pre-run-2/gray/0.png",
                    output_object_key_bin=None,
                    metrics_json={"dpi_estimate": 300},
                    sha256_gray="gray-2-0",
                    sha256_bin=None,
                    warnings_json=[],
                    failure_reason=None,
                    created_at=now - timedelta(hours=3),
                    updated_at=now - timedelta(hours=3),
                ),
                PagePreprocessResultRecord(
                    run_id="pre-run-2",
                    page_id="page-2",
                    page_index=1,
                    status="SUCCEEDED",
                    quality_gate_status="PASS",
                    input_object_key="controlled/derived/project-1/doc-2/pages/1.png",
                    output_object_key_gray="controlled/derived/project-1/doc-2/preprocess/pre-run-2/gray/1.png",
                    output_object_key_bin=None,
                    metrics_json={"dpi_estimate": 240},
                    sha256_gray="gray-2-1",
                    sha256_bin=None,
                    warnings_json=[],
                    failure_reason=None,
                    created_at=now - timedelta(hours=3),
                    updated_at=now - timedelta(hours=3),
                ),
            ],
        }
        self._preprocess_projection: dict[str, DocumentPreprocessProjectionRecord] = {
            "doc-2": DocumentPreprocessProjectionRecord(
                document_id="doc-2",
                project_id="project-1",
                active_preprocess_run_id="pre-run-2",
                active_profile_id="BALANCED",
                updated_at=now - timedelta(hours=3),
            )
        }
        baseline_layout_run = LayoutRunRecord(
            id="layout-run-1",
            project_id="project-1",
            document_id="doc-2",
            input_preprocess_run_id="pre-run-1",
            run_kind="AUTO",
            parent_run_id=None,
            attempt_number=1,
            superseded_by_run_id="layout-run-2",
            model_id="layout-model-v1",
            profile_id="DEFAULT",
            params_json={},
            params_hash="hash-layout-run-1",
            pipeline_version="layout-v1",
            container_digest="ukde/layout:v1",
            status="SUCCEEDED",
            created_by="user-1",
            created_at=now - timedelta(hours=2, minutes=30),
            started_at=now - timedelta(hours=2, minutes=29),
            finished_at=now - timedelta(hours=2, minutes=28),
            failure_reason=None,
        )
        active_layout_run = LayoutRunRecord(
            id="layout-run-2",
            project_id="project-1",
            document_id="doc-2",
            input_preprocess_run_id="pre-run-2",
            run_kind="AUTO",
            parent_run_id="layout-run-1",
            attempt_number=2,
            superseded_by_run_id=None,
            model_id="layout-model-v1",
            profile_id="DEFAULT",
            params_json={"line_merge": "balanced"},
            params_hash="hash-layout-run-2",
            pipeline_version="layout-v1",
            container_digest="ukde/layout:v1",
            status="SUCCEEDED",
            created_by="user-1",
            created_at=now - timedelta(hours=2),
            started_at=now - timedelta(hours=1, minutes=59),
            finished_at=now - timedelta(hours=1, minutes=58),
            failure_reason=None,
        )
        self._layout_runs: dict[str, list[LayoutRunRecord]] = {
            "doc-2": [active_layout_run, baseline_layout_run]
        }
        self._layout_pages: dict[str, list[PageLayoutResultRecord]] = {
            "layout-run-1": [
                PageLayoutResultRecord(
                    run_id="layout-run-1",
                    page_id="page-1",
                    page_index=0,
                    status="SUCCEEDED",
                    page_recall_status="COMPLETE",
                    active_layout_version_id=None,
                    page_xml_key=None,
                    overlay_json_key=None,
                    page_xml_sha256=None,
                    overlay_json_sha256=None,
                    metrics_json={
                        "region_count": 9,
                        "line_count": 41,
                        "coverage_percent": 90.1,
                        "structure_confidence": 0.92,
                    },
                    warnings_json=[],
                    failure_reason=None,
                    created_at=now - timedelta(hours=2, minutes=30),
                    updated_at=now - timedelta(hours=2, minutes=30),
                ),
                PageLayoutResultRecord(
                    run_id="layout-run-1",
                    page_id="page-2",
                    page_index=1,
                    status="SUCCEEDED",
                    page_recall_status="NEEDS_MANUAL_REVIEW",
                    active_layout_version_id=None,
                    page_xml_key=None,
                    overlay_json_key=None,
                    page_xml_sha256=None,
                    overlay_json_sha256=None,
                    metrics_json={
                        "region_count": 6,
                        "line_count": 0,
                        "coverage_percent": 62.0,
                        "structure_confidence": 0.51,
                    },
                    warnings_json=["MISSING_LINES"],
                    failure_reason=None,
                    created_at=now - timedelta(hours=2, minutes=30),
                    updated_at=now - timedelta(hours=2, minutes=30),
                ),
            ],
            "layout-run-2": [
                PageLayoutResultRecord(
                    run_id="layout-run-2",
                    page_id="page-1",
                    page_index=0,
                    status="SUCCEEDED",
                    page_recall_status="COMPLETE",
                    active_layout_version_id=None,
                    page_xml_key=None,
                    overlay_json_key=None,
                    page_xml_sha256=None,
                    overlay_json_sha256=None,
                    metrics_json={
                        "region_count": 10,
                        "line_count": 44,
                        "coverage_percent": 93.6,
                        "structure_confidence": 0.95,
                    },
                    warnings_json=[],
                    failure_reason=None,
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
                PageLayoutResultRecord(
                    run_id="layout-run-2",
                    page_id="page-2",
                    page_index=1,
                    status="SUCCEEDED",
                    page_recall_status="NEEDS_RESCUE",
                    active_layout_version_id=None,
                    page_xml_key=None,
                    overlay_json_key=None,
                    page_xml_sha256=None,
                    overlay_json_sha256=None,
                    metrics_json={
                        "region_count": 8,
                        "line_count": 21,
                        "coverage_percent": 74.2,
                        "structure_confidence": 0.73,
                        "overlap_count": 2,
                    },
                    warnings_json=["OVERLAP_DETECTED"],
                    failure_reason=None,
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
            ],
        }
        self._layout_projection: dict[str, DocumentLayoutProjectionRecord] = {
            "doc-2": DocumentLayoutProjectionRecord(
                document_id="doc-2",
                project_id="project-1",
                active_layout_run_id="layout-run-2",
                active_input_preprocess_run_id="pre-run-2",
                updated_at=now - timedelta(hours=2),
            )
        }
        self._layout_overlay_payloads: dict[tuple[str, str], dict[str, object]] = {
            (
                "layout-run-2",
                "page-1",
            ): {
                "schemaVersion": 1,
                "runId": "layout-run-2",
                "pageId": "page-1",
                "pageIndex": 0,
                "page": {"width": 1000, "height": 1400},
                "elements": [
                    {
                        "id": "region-1",
                        "type": "REGION",
                        "parentId": None,
                        "childIds": ["line-1"],
                        "regionType": "TEXT",
                        "polygon": [
                            {"x": 20.0, "y": 40.0},
                            {"x": 980.0, "y": 40.0},
                            {"x": 980.0, "y": 320.0},
                            {"x": 20.0, "y": 320.0},
                        ],
                    },
                    {
                        "id": "line-1",
                        "type": "LINE",
                        "parentId": "region-1",
                        "polygon": [
                            {"x": 40.0, "y": 80.0},
                            {"x": 960.0, "y": 80.0},
                            {"x": 960.0, "y": 120.0},
                            {"x": 40.0, "y": 120.0},
                        ],
                        "baseline": [
                            {"x": 48.0, "y": 112.0},
                            {"x": 950.0, "y": 112.0},
                        ],
                    },
                ],
                "readingOrder": [{"fromId": "region-1", "toId": "line-1"}],
                "readingOrderGroups": [
                    {"id": "g-0001", "ordered": True, "regionIds": ["region-1"]}
                ],
                "readingOrderMeta": {
                    "schemaVersion": 1,
                    "mode": "ORDERED",
                    "source": "AUTO_INFERRED",
                    "ambiguityScore": 0.12,
                    "columnCertainty": 0.92,
                    "overlapConflictScore": 0.03,
                    "orphanLineCount": 0,
                    "nonTextComplexityScore": 0.01,
                    "orderWithheld": False,
                    "versionEtag": "layout-etag-1",
                    "layoutVersionId": "layout-version-1",
                },
            }
        }
        self._layout_reading_order_revisions: dict[tuple[str, str], int] = {
            ("layout-run-2", "page-1"): 1
        }
        self._layout_pagexml_payloads: dict[tuple[str, str], bytes] = {
            (
                "layout-run-2",
                "page-1",
            ): (
                b'<?xml version="1.0" encoding="utf-8"?>\n'
                b'<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">\n'
                b'  <Page runId="layout-run-2" pageId="page-1" pageIndex="0" imageWidth="1000" imageHeight="1400">\n'
                b'    <TextRegion id="region-1" type="TEXT">\n'
                b'      <Coords points="20,40 980,40 980,320 20,320" />\n'
                b'      <TextLine id="line-1">\n'
                b'        <Coords points="40,80 960,80 960,120 40,120" />\n'
                b'        <Baseline points="48,112 950,112" />\n'
                b"      </TextLine>\n"
                b"    </TextRegion>\n"
                b"  </Page>\n"
                b"</PcGts>\n"
            )
        }
        self._layout_line_artifacts: dict[
            tuple[str, str, str], DocumentLayoutLineArtifactsSnapshot
        ] = {
            (
                "layout-run-2",
                "page-1",
                "line-1",
            ): DocumentLayoutLineArtifactsSnapshot(
                run_id="layout-run-2",
                page_id="page-1",
                page_index=0,
                line_id="line-1",
                region_id="region-1",
                artifacts_sha256=(
                    "7f9ce8d5f5ab7f95f6f89e9895b31dbf95f8f12db67fdd5ea6f9557f7a6f5a22"
                ),
                line_crop_path=(
                    "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/"
                    "page-1/lines/line-1/crop"
                ),
                region_crop_path=(
                    "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/"
                    "page-1/lines/line-1/crop?variant=region"
                ),
                page_thumbnail_path=(
                    "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/"
                    "page-1/thumbnail"
                ),
                context_window_path=(
                    "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/"
                    "page-1/lines/line-1/context"
                ),
                context_window={
                    "schemaVersion": 1,
                    "runId": "layout-run-2",
                    "pageId": "page-1",
                    "pageIndex": 0,
                    "lineId": "line-1",
                    "regionId": "region-1",
                    "regionLineIds": ["line-1"],
                    "lineIndexWithinRegion": 0,
                    "previousLineId": None,
                    "nextLineId": None,
                },
            )
        }
        self._layout_crop_payloads: dict[tuple[str, str, str, str], bytes] = {
            ("layout-run-2", "page-1", "line-1", "line"): b"line-crop-png",
            ("layout-run-2", "page-1", "line-1", "region"): b"region-crop-png",
        }
        self._layout_page_thumbnail_payloads: dict[tuple[str, str], bytes] = {
            ("layout-run-2", "page-1"): b"layout-thumb-png"
        }
        self._layout_recall_status_snapshots: dict[
            tuple[str, str], DocumentLayoutPageRecallStatusSnapshot
        ] = {
            (
                "layout-run-1",
                "page-1",
            ): DocumentLayoutPageRecallStatusSnapshot(
                run_id="layout-run-1",
                page_id="page-1",
                page_index=0,
                page_recall_status="COMPLETE",
                recall_check_version="layout-recall-v1",
                missed_text_risk_score=0.11,
                signals_json={
                    "algorithm_version": "layout-recall-v1",
                    "candidate_count": 0,
                },
                rescue_candidate_counts={
                    "PENDING": 0,
                    "ACCEPTED": 0,
                    "REJECTED": 0,
                    "RESOLVED": 0,
                },
                blocker_reason_codes=[],
                unresolved_count=0,
            ),
            (
                "layout-run-1",
                "page-2",
            ): DocumentLayoutPageRecallStatusSnapshot(
                run_id="layout-run-1",
                page_id="page-2",
                page_index=1,
                page_recall_status="NEEDS_MANUAL_REVIEW",
                recall_check_version="layout-recall-v1",
                missed_text_risk_score=0.67,
                signals_json={
                    "algorithm_version": "layout-recall-v1",
                    "candidate_count": 0,
                },
                rescue_candidate_counts={
                    "PENDING": 0,
                    "ACCEPTED": 0,
                    "REJECTED": 0,
                    "RESOLVED": 0,
                },
                blocker_reason_codes=["MANUAL_REVIEW_REQUIRED"],
                unresolved_count=1,
            ),
            (
                "layout-run-2",
                "page-1",
            ): DocumentLayoutPageRecallStatusSnapshot(
                run_id="layout-run-2",
                page_id="page-1",
                page_index=0,
                page_recall_status="COMPLETE",
                recall_check_version="layout-recall-v1",
                missed_text_risk_score=0.08,
                signals_json={
                    "algorithm_version": "layout-recall-v1",
                    "candidate_count": 0,
                },
                rescue_candidate_counts={
                    "PENDING": 0,
                    "ACCEPTED": 0,
                    "REJECTED": 0,
                    "RESOLVED": 0,
                },
                blocker_reason_codes=[],
                unresolved_count=0,
            ),
            (
                "layout-run-2",
                "page-2",
            ): DocumentLayoutPageRecallStatusSnapshot(
                run_id="layout-run-2",
                page_id="page-2",
                page_index=1,
                page_recall_status="NEEDS_RESCUE",
                recall_check_version="layout-recall-v1",
                missed_text_risk_score=0.44,
                signals_json={
                    "algorithm_version": "layout-recall-v1",
                    "candidate_count": 2,
                    "accepted_candidate_count": 1,
                },
                rescue_candidate_counts={
                    "PENDING": 0,
                    "ACCEPTED": 1,
                    "REJECTED": 1,
                    "RESOLVED": 0,
                },
                blocker_reason_codes=[],
                unresolved_count=0,
            ),
        }
        self._layout_rescue_candidates: dict[
            tuple[str, str], list[LayoutRescueCandidateRecord]
        ] = {
            (
                "layout-run-2",
                "page-2",
            ): [
                LayoutRescueCandidateRecord(
                    id="resc-0002-001-a",
                    run_id="layout-run-2",
                    page_id="page-2",
                    candidate_kind="LINE_EXPANSION",
                    geometry_json={
                        "schemaVersion": 1,
                        "bbox": {"x": 24, "y": 512, "width": 340, "height": 76},
                    },
                    confidence=0.71,
                    source_signal="UNASSOCIATED_COMPONENT_NEAR_LINE",
                    status="ACCEPTED",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
                LayoutRescueCandidateRecord(
                    id="resc-0002-002-b",
                    run_id="layout-run-2",
                    page_id="page-2",
                    candidate_kind="PAGE_WINDOW",
                    geometry_json={
                        "schemaVersion": 1,
                        "bbox": {"x": 780, "y": 620, "width": 180, "height": 92},
                    },
                    confidence=0.28,
                    source_signal="UNASSOCIATED_COMPONENT_PAGE_WINDOW",
                    status="REJECTED",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
            ]
        }
        self._layout_projection_input_preprocess_run_id: dict[str, str | None] = {
            "doc-2": "pre-run-2"
        }
        active_transcription_run = TranscriptionRunRecord(
            id="transcription-run-1",
            project_id="project-1",
            document_id="doc-2",
            input_preprocess_run_id="pre-run-2",
            input_layout_run_id="layout-run-2",
            input_layout_snapshot_hash="layout-snap-2",
            engine="VLM_LINE_CONTEXT",
            model_id="model-transcription-primary-qwen2.5-vl-3b-instruct",
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
            superseded_by_transcription_run_id="transcription-run-2",
            status="SUCCEEDED",
            created_by="user-1",
            created_at=now - timedelta(hours=2),
            started_at=now - timedelta(hours=2),
            finished_at=now - timedelta(hours=1, minutes=55),
            canceled_by=None,
            canceled_at=None,
            failure_reason=None,
        )
        queued_transcription_run = TranscriptionRunRecord(
            id="transcription-run-2",
            project_id="project-1",
            document_id="doc-2",
            input_preprocess_run_id="pre-run-2",
            input_layout_run_id="layout-run-2",
            input_layout_snapshot_hash="layout-snap-2",
            engine="VLM_LINE_CONTEXT",
            model_id="model-transcription-primary-qwen2.5-vl-3b-instruct",
            project_model_assignment_id=None,
            prompt_template_id="prompt-v1",
            prompt_template_sha256="prompt-sha-1",
            response_schema_version=1,
            confidence_basis="MODEL_NATIVE",
            confidence_calibration_version="v1",
            params_json={"temperature": 0.0},
            pipeline_version="transcription-v1",
            container_digest="ukde/transcription:v1",
            attempt_number=2,
            supersedes_transcription_run_id="transcription-run-1",
            superseded_by_transcription_run_id=None,
            status="QUEUED",
            created_by="user-1",
            created_at=now - timedelta(minutes=30),
            started_at=None,
            finished_at=None,
            canceled_by=None,
            canceled_at=None,
            failure_reason=None,
        )
        self._transcription_runs: dict[str, list[TranscriptionRunRecord]] = {
            "doc-2": [queued_transcription_run, active_transcription_run]
        }
        self._transcription_pages: dict[str, list[PageTranscriptionResultRecord]] = {
            "transcription-run-1": [
                PageTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-1",
                    page_index=0,
                    status="SUCCEEDED",
                    pagexml_out_key=(
                        "controlled/derived/project-1/doc-2/transcription/transcription-run-1/"
                        "page-1/page.xml"
                    ),
                    pagexml_out_sha256="trans-pagexml-1",
                    raw_model_response_key=(
                        "controlled/derived/project-1/doc-2/transcription/transcription-run-1/"
                        "page-1/model-response.json"
                    ),
                    raw_model_response_sha256="trans-raw-1",
                    hocr_out_key=None,
                    hocr_out_sha256=None,
                    metrics_json={"line_count": 2, "token_count": 7},
                    warnings_json=[],
                    failure_reason=None,
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
                PageTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-2",
                    page_index=1,
                    status="SUCCEEDED",
                    pagexml_out_key=(
                        "controlled/derived/project-1/doc-2/transcription/transcription-run-1/"
                        "page-2/page.xml"
                    ),
                    pagexml_out_sha256="trans-pagexml-2",
                    raw_model_response_key=(
                        "controlled/derived/project-1/doc-2/transcription/transcription-run-1/"
                        "page-2/model-response.json"
                    ),
                    raw_model_response_sha256="trans-raw-2",
                    hocr_out_key=None,
                    hocr_out_sha256=None,
                    metrics_json={"line_count": 1, "token_count": 3},
                    warnings_json=["LOW_CONFIDENCE_LINE"],
                    failure_reason=None,
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
            ],
            "transcription-run-2": [
                PageTranscriptionResultRecord(
                    run_id="transcription-run-2",
                    page_id="page-1",
                    page_index=0,
                    status="QUEUED",
                    pagexml_out_key=None,
                    pagexml_out_sha256=None,
                    raw_model_response_key=None,
                    raw_model_response_sha256=None,
                    hocr_out_key=None,
                    hocr_out_sha256=None,
                    metrics_json={},
                    warnings_json=[],
                    failure_reason=None,
                    created_at=now - timedelta(minutes=30),
                    updated_at=now - timedelta(minutes=30),
                ),
                PageTranscriptionResultRecord(
                    run_id="transcription-run-2",
                    page_id="page-2",
                    page_index=1,
                    status="QUEUED",
                    pagexml_out_key=None,
                    pagexml_out_sha256=None,
                    raw_model_response_key=None,
                    raw_model_response_sha256=None,
                    hocr_out_key=None,
                    hocr_out_sha256=None,
                    metrics_json={},
                    warnings_json=[],
                    failure_reason=None,
                    created_at=now - timedelta(minutes=30),
                    updated_at=now - timedelta(minutes=30),
                ),
            ],
        }
        self._transcription_lines: dict[
            tuple[str, str], list[LineTranscriptionResultRecord]
        ] = {
            ("transcription-run-1", "page-1"): [
                LineTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-1",
                    line_id="line-1",
                    text_diplomatic="Dear diary",
                    conf_line=0.94,
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
                ),
                LineTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-1",
                    line_id="line-2",
                    text_diplomatic="Weather clear",
                    conf_line=0.62,
                    confidence_basis="MODEL_NATIVE",
                    confidence_calibration_version="v1",
                    alignment_json_key=None,
                    char_boxes_key=None,
                    schema_validation_status="VALID",
                    flags_json={"low_confidence": True},
                    machine_output_sha256="line-sha-2",
                    active_transcript_version_id=None,
                    version_etag="line-etag-2",
                    token_anchor_status="CURRENT",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
            ],
            ("transcription-run-1", "page-2"): [
                LineTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-2",
                    line_id="line-3",
                    text_diplomatic="Met station clerk",
                    conf_line=0.58,
                    confidence_basis="MODEL_NATIVE",
                    confidence_calibration_version="v1",
                    alignment_json_key=None,
                    char_boxes_key=None,
                    schema_validation_status="VALID",
                    flags_json={"low_confidence": True},
                    machine_output_sha256="line-sha-3",
                    active_transcript_version_id=None,
                    version_etag="line-etag-3",
                    token_anchor_status="CURRENT",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                )
            ],
        }
        self._transcription_tokens: dict[
            tuple[str, str], list[TokenTranscriptionResultRecord]
        ] = {
            ("transcription-run-1", "page-1"): [
                TokenTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-1",
                    line_id="line-1",
                    token_id="token-1",
                    token_index=0,
                    token_text="Dear",
                    token_confidence=0.96,
                    bbox_json={"x": 10, "y": 20, "w": 40, "h": 12},
                    polygon_json=None,
                    source_kind="LINE",
                    source_ref_id="line-1",
                    projection_basis="ENGINE_OUTPUT",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
                TokenTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-1",
                    line_id="line-1",
                    token_id="token-2",
                    token_index=1,
                    token_text="diary",
                    token_confidence=0.95,
                    bbox_json={"x": 52, "y": 20, "w": 48, "h": 12},
                    polygon_json=None,
                    source_kind="LINE",
                    source_ref_id="line-1",
                    projection_basis="ENGINE_OUTPUT",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
                TokenTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-1",
                    line_id="line-2",
                    token_id="token-3",
                    token_index=2,
                    token_text="Weather",
                    token_confidence=0.71,
                    bbox_json={"x": 12, "y": 40, "w": 58, "h": 12},
                    polygon_json=None,
                    source_kind="LINE",
                    source_ref_id="line-2",
                    projection_basis="ENGINE_OUTPUT",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
                TokenTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-1",
                    line_id="line-2",
                    token_id="token-4",
                    token_index=3,
                    token_text="clear",
                    token_confidence=0.66,
                    bbox_json={"x": 72, "y": 40, "w": 42, "h": 12},
                    polygon_json=None,
                    source_kind="LINE",
                    source_ref_id="line-2",
                    projection_basis="ENGINE_OUTPUT",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
            ],
            ("transcription-run-1", "page-2"): [
                TokenTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-2",
                    line_id="line-3",
                    token_id="token-5",
                    token_index=0,
                    token_text="Met",
                    token_confidence=0.68,
                    bbox_json={"x": 14, "y": 24, "w": 26, "h": 12},
                    polygon_json=None,
                    source_kind="LINE",
                    source_ref_id="line-3",
                    projection_basis="ENGINE_OUTPUT",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
                TokenTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-2",
                    line_id="line-3",
                    token_id="token-6",
                    token_index=1,
                    token_text="station",
                    token_confidence=0.61,
                    bbox_json={"x": 42, "y": 24, "w": 56, "h": 12},
                    polygon_json=None,
                    source_kind="LINE",
                    source_ref_id="line-3",
                    projection_basis="ENGINE_OUTPUT",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
                TokenTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-2",
                    line_id="line-3",
                    token_id="token-7",
                    token_index=2,
                    token_text="clerk",
                    token_confidence=0.59,
                    bbox_json={"x": 104, "y": 24, "w": 44, "h": 12},
                    polygon_json=None,
                    source_kind="LINE",
                    source_ref_id="line-3",
                    projection_basis="ENGINE_OUTPUT",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
                TokenTranscriptionResultRecord(
                    run_id="transcription-run-1",
                    page_id="page-2",
                    line_id="line-3",
                    token_id="token-8",
                    token_index=3,
                    token_text="marginalia",
                    token_confidence=0.63,
                    bbox_json={"x": 150, "y": 24, "w": 70, "h": 12},
                    polygon_json=None,
                    source_kind="RESCUE_CANDIDATE",
                    source_ref_id="resc-0002-001-a",
                    projection_basis="ENGINE_OUTPUT",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
            ],
        }
        self._transcription_rescue_resolutions: dict[
            tuple[str, str], dict[str, object]
        ] = {}
        self._transcription_projection: dict[str, DocumentTranscriptionProjectionRecord] = {
            "doc-2": DocumentTranscriptionProjectionRecord(
                document_id="doc-2",
                project_id="project-1",
                active_transcription_run_id="transcription-run-1",
                active_layout_run_id="layout-run-2",
                active_layout_snapshot_hash="layout-snap-2",
                active_preprocess_run_id="pre-run-2",
                downstream_redaction_state="NOT_STARTED",
                downstream_redaction_invalidated_at=None,
                downstream_redaction_invalidated_reason=None,
                updated_at=now - timedelta(hours=1, minutes=55),
            )
        }
        self._transcription_projection_preprocess_run_id: dict[str, str | None] = {
            "doc-2": "pre-run-2"
        }
        self._transcription_compare_decisions: list[TranscriptionCompareDecisionRecord] = []
        self._transcription_compare_decision_events: list[
            TranscriptionCompareDecisionEventRecord
        ] = []
        self._transcript_versions: dict[
            tuple[str, str, str], list[TranscriptVersionRecord]
        ] = {
            ("transcription-run-1", "page-1", "line-1"): [
                TranscriptVersionRecord(
                    id="transcript-version-1",
                    run_id="transcription-run-1",
                    page_id="page-1",
                    line_id="line-1",
                    base_version_id=None,
                    superseded_by_version_id=None,
                    version_etag="line-etag-1",
                    text_diplomatic="Dear diary",
                    editor_user_id="user-1",
                    edit_reason=None,
                    created_at=now - timedelta(hours=2),
                )
            ]
        }
        self._transcription_output_projections: dict[
            tuple[str, str], TranscriptionOutputProjectionRecord
        ] = {
            ("transcription-run-1", "page-1"): TranscriptionOutputProjectionRecord(
                run_id="transcription-run-1",
                document_id="doc-2",
                page_id="page-1",
                corrected_pagexml_key=(
                    "controlled/derived/project-1/doc-2/transcription/transcription-run-1/"
                    "versions/transcript-version-1/page/0.xml"
                ),
                corrected_pagexml_sha256="corrected-pagexml-sha-1",
                corrected_text_sha256="corrected-text-sha-1",
                source_pagexml_sha256="trans-pagexml-1",
                updated_at=now - timedelta(hours=2),
            )
        }
        self._transcript_variant_layers: dict[
            tuple[str, str, str], list[TranscriptVariantLayerRecord]
        ] = {
            ("transcription-run-1", "page-1", "NORMALISED"): [
                TranscriptVariantLayerRecord(
                    id="variant-layer-1",
                    run_id="transcription-run-1",
                    page_id="page-1",
                    variant_kind="NORMALISED",
                    base_transcript_version_id="transcript-version-1",
                    base_version_set_sha256=None,
                    base_projection_sha256="projection-sha-1",
                    variant_text_key=(
                        "controlled/derived/project-1/doc-2/transcription/transcription-run-1/"
                        "variants/normalised/page/0.txt"
                    ),
                    variant_text_sha256="variant-text-sha-1",
                    created_by="user-3",
                    created_at=now - timedelta(hours=1),
                )
            ]
        }
        self._transcript_variant_suggestions: dict[
            str, list[TranscriptVariantSuggestionRecord]
        ] = {
            "variant-layer-1": [
                TranscriptVariantSuggestionRecord(
                    id="variant-suggestion-1",
                    variant_layer_id="variant-layer-1",
                    line_id="line-1",
                    suggestion_text="Dear Diary",
                    confidence=0.81,
                    status="PENDING",
                    decided_by=None,
                    decided_at=None,
                    decision_reason=None,
                    metadata_json={"source": "assist-v1"},
                    created_at=now - timedelta(minutes=50),
                    updated_at=now - timedelta(minutes=50),
                )
            ]
        }
        self._transcript_variant_suggestion_events: list[
            TranscriptVariantSuggestionEventRecord
        ] = []
        self._imports: dict[str, DocumentImportSnapshot] = {}
        self._import_payloads: dict[str, bytes] = {}
        self._upload_sessions: dict[str, DocumentUploadSessionRecord] = {}
        self._upload_session_chunks: dict[str, dict[int, bytes]] = {}
        self.scan_transitions: dict[str, list[str]] = {}
        self._upload_session_sequence = 0
        self._processing_run_sequence = 10
        self._preprocess_run_sequence = 2
        self._layout_run_sequence = 2
        self._transcription_run_sequence = 2
        self._project_roles: dict[str, Literal["PROJECT_LEAD", "RESEARCHER", "REVIEWER"]] = {
            "user-1": "PROJECT_LEAD",
            "user-2": "RESEARCHER",
            "user-3": "REVIEWER",
        }

    def _require_project_access(self, project_id: str) -> None:
        if project_id != "project-1":
            raise ProjectAccessDeniedError("Membership is required for this project route.")

    def _find_document(self, project_id: str, document_id: str) -> DocumentRecord | None:
        for row in self._documents.get(project_id, []):
            if row.id == document_id:
                return row
        return None

    def _resolve_project_role(
        self,
        *,
        current_user: SessionPrincipal,
    ) -> Literal["PROJECT_LEAD", "RESEARCHER", "REVIEWER"] | None:
        return self._project_roles.get(current_user.user_id)

    def _require_preprocess_view_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        self._require_project_access(project_id)
        if "ADMIN" in set(current_user.platform_roles):
            return
        role = self._resolve_project_role(current_user=current_user)
        if role not in {"PROJECT_LEAD", "RESEARCHER", "REVIEWER"}:
            raise DocumentPreprocessAccessDeniedError(
                "Current role cannot view preprocessing runs in this project."
            )

    def _require_preprocess_mutation_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        self._require_project_access(project_id)
        if "ADMIN" in set(current_user.platform_roles):
            return
        role = self._resolve_project_role(current_user=current_user)
        if role not in {"PROJECT_LEAD", "REVIEWER"}:
            raise DocumentPreprocessAccessDeniedError(
                "Current role cannot create, rerun, cancel, or activate preprocessing runs."
            )

    def _require_layout_view_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        self._require_project_access(project_id)
        if "ADMIN" in set(current_user.platform_roles):
            return
        role = self._resolve_project_role(current_user=current_user)
        if role not in {"PROJECT_LEAD", "RESEARCHER", "REVIEWER"}:
            raise DocumentLayoutAccessDeniedError(
                "Current role cannot view layout analysis routes in this project."
            )

    def _require_layout_mutation_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        self._require_project_access(project_id)
        if "ADMIN" in set(current_user.platform_roles):
            return
        role = self._resolve_project_role(current_user=current_user)
        if role not in {"PROJECT_LEAD", "REVIEWER"}:
            raise DocumentLayoutAccessDeniedError(
                "Current role cannot create, cancel, or activate layout runs."
            )

    def _require_transcription_view_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        self._require_project_access(project_id)
        if "ADMIN" in set(current_user.platform_roles):
            return
        role = self._resolve_project_role(current_user=current_user)
        if role not in {"PROJECT_LEAD", "RESEARCHER", "REVIEWER"}:
            raise DocumentTranscriptionAccessDeniedError(
                "Current role cannot view transcription routes in this project."
            )

    def _require_transcription_mutation_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        self._require_project_access(project_id)
        if "ADMIN" in set(current_user.platform_roles):
            return
        role = self._resolve_project_role(current_user=current_user)
        if role not in {"PROJECT_LEAD", "REVIEWER"}:
            raise DocumentTranscriptionAccessDeniedError(
                "Current role cannot create, cancel, or activate transcription runs."
            )

    def _get_preprocess_run_or_raise(
        self,
        *,
        document_id: str,
        run_id: str,
    ) -> PreprocessRunRecord:
        for row in self._preprocess_runs.get(document_id, []):
            if row.id == run_id:
                return row
        raise DocumentPreprocessRunNotFoundError("Preprocessing run not found.")

    def _get_layout_run_or_raise(
        self,
        *,
        document_id: str,
        run_id: str,
    ) -> LayoutRunRecord:
        for row in self._layout_runs.get(document_id, []):
            if row.id == run_id:
                return row
        raise DocumentLayoutRunNotFoundError("Layout run not found.")

    def _get_transcription_run_or_raise(
        self,
        *,
        document_id: str,
        run_id: str,
    ) -> TranscriptionRunRecord:
        for row in self._transcription_runs.get(document_id, []):
            if row.id == run_id:
                return row
        raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")

    def _build_layout_activation_gate(
        self,
        *,
        document_id: str,
        run: LayoutRunRecord,
    ) -> LayoutActivationGateRecord:
        blockers: list[LayoutActivationBlockerRecord] = []
        page_rows = list(self._layout_pages.get(run.id, []))
        if run.status != "SUCCEEDED":
            blockers.append(
                LayoutActivationBlockerRecord(
                    code="LAYOUT_RUN_NOT_SUCCEEDED",
                    message=(
                        "Only SUCCEEDED layout runs can be activated; "
                        f"current status is {run.status}."
                    ),
                    count=1,
                )
            )
        if not page_rows:
            blockers.append(
                LayoutActivationBlockerRecord(
                    code="LAYOUT_RECALL_PAGE_RESULTS_MISSING",
                    message="Run has no page layout results.",
                    count=1,
                )
            )
        unresolved_rows = [row for row in page_rows if row.status != "SUCCEEDED"]
        if unresolved_rows:
            blockers.append(
                LayoutActivationBlockerRecord(
                    code="LAYOUT_RECALL_STATUS_UNRESOLVED",
                    message=(
                        f"{len(unresolved_rows)} page(s) are not in SUCCEEDED status."
                    ),
                    count=len(unresolved_rows),
                    page_ids=tuple(row.page_id for row in unresolved_rows),
                    page_numbers=tuple(row.page_index + 1 for row in unresolved_rows),
                )
            )
        missing_recall_rows = [
            row
            for row in page_rows
            if (run.id, row.page_id) not in self._layout_recall_status_snapshots
        ]
        if missing_recall_rows:
            blockers.append(
                LayoutActivationBlockerRecord(
                    code="LAYOUT_RECALL_CHECK_MISSING",
                    message=(
                        f"{len(missing_recall_rows)} page(s) are missing persisted recall-check records."
                    ),
                    count=len(missing_recall_rows),
                    page_ids=tuple(row.page_id for row in missing_recall_rows),
                    page_numbers=tuple(row.page_index + 1 for row in missing_recall_rows),
                )
            )
        pending_rows = []
        for row in page_rows:
            snapshot = self._layout_recall_status_snapshots.get((run.id, row.page_id))
            if snapshot is None:
                continue
            if snapshot.rescue_candidate_counts.get("PENDING", 0) > 0:
                pending_rows.append((row, snapshot.rescue_candidate_counts["PENDING"]))
        if pending_rows:
            blockers.append(
                LayoutActivationBlockerRecord(
                    code="LAYOUT_RESCUE_PENDING",
                    message=(
                        f"{len(pending_rows)} page(s) still have PENDING rescue candidates."
                    ),
                    count=sum(count for _, count in pending_rows),
                    page_ids=tuple(row.page_id for row, _ in pending_rows),
                    page_numbers=tuple(row.page_index + 1 for row, _ in pending_rows),
                )
            )
        rescue_acceptance_rows = []
        for row in page_rows:
            if row.page_recall_status != "NEEDS_RESCUE":
                continue
            snapshot = self._layout_recall_status_snapshots.get((run.id, row.page_id))
            accepted = (
                snapshot.rescue_candidate_counts.get("ACCEPTED", 0)
                if snapshot is not None
                else 0
            )
            if accepted <= 0:
                rescue_acceptance_rows.append(row)
        if rescue_acceptance_rows:
            blockers.append(
                LayoutActivationBlockerRecord(
                    code="LAYOUT_RESCUE_ACCEPTANCE_MISSING",
                    message=(
                        f"{len(rescue_acceptance_rows)} NEEDS_RESCUE page(s) have no ACCEPTED rescue candidate."
                    ),
                    count=len(rescue_acceptance_rows),
                    page_ids=tuple(row.page_id for row in rescue_acceptance_rows),
                    page_numbers=tuple(
                        row.page_index + 1 for row in rescue_acceptance_rows
                    ),
                )
            )
        projection = self._layout_projection.get(document_id)
        if projection is not None and projection.downstream_transcription_state != "NOT_STARTED":
            downstream_impact = LayoutActivationDownstreamImpactRecord(
                transcription_state_after_activation="STALE",
                invalidates_existing_transcription_basis=True,
                reason=(
                    "LAYOUT_ACTIVATION_SUPERSEDED: Active layout run changed; "
                    "transcription basis requires refresh."
                ),
                has_active_transcription_projection=True,
                active_transcription_run_id="transcription-run-1",
            )
        else:
            downstream_impact = LayoutActivationDownstreamImpactRecord(
                transcription_state_after_activation="NOT_STARTED",
                invalidates_existing_transcription_basis=False,
                reason=None,
                has_active_transcription_projection=False,
                active_transcription_run_id=None,
            )
        return LayoutActivationGateRecord(
            eligible=not blockers,
            blocker_count=len(blockers),
            blockers=tuple(blockers),
            evaluated_at=datetime.now(UTC),
            downstream_impact=downstream_impact,
        )

    def _with_layout_activation_gate(
        self,
        *,
        document_id: str,
        run: LayoutRunRecord,
    ) -> LayoutRunRecord:
        return replace(
            run,
            activation_gate=self._build_layout_activation_gate(
                document_id=document_id,
                run=run,
            ),
        )

    def _resolve_preprocess_run_for_variant(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str | None = None,
    ) -> tuple[str | None, PreprocessRunRecord]:
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        requested = run_id.strip() if isinstance(run_id, str) and run_id.strip() else None
        if requested is not None:
            return requested, self._get_preprocess_run_or_raise(
                document_id=document_id,
                run_id=requested,
            )
        projection = self._preprocess_projection.get(document_id)
        if projection is None or not projection.active_preprocess_run_id:
            raise DocumentPreprocessConflictError(
                "No active preprocess run exists for this document."
            )
        return None, self._get_preprocess_run_or_raise(
            document_id=document_id,
            run_id=projection.active_preprocess_run_id,
        )

    def _write_import_snapshot(
        self,
        *,
        project_id: str,
        import_id: str,
        document: DocumentRecord,
        import_record: DocumentImportRecord,
    ) -> DocumentImportSnapshot:
        snapshot = DocumentImportSnapshot(
            import_record=import_record,
            document_record=document,
        )
        self._imports[import_id] = snapshot
        self._documents[project_id] = [
            document if row.id == document.id else row for row in self._documents[project_id]
        ]
        return snapshot

    def list_documents(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        filters: DocumentListFilters,
    ) -> tuple[list[DocumentRecord], int | None]:
        self._require_project_access(project_id)
        rows = list(self._documents.get(project_id, []))
        if filters.q:
            needle = filters.q.lower()
            rows = [row for row in rows if needle in row.original_filename.lower()]
        if filters.status:
            rows = [row for row in rows if row.status == filters.status]
        if filters.uploader:
            needle = filters.uploader.lower()
            rows = [row for row in rows if needle in row.created_by.lower()]
        if filters.from_timestamp:
            rows = [row for row in rows if row.created_at >= filters.from_timestamp]
        if filters.to_timestamp:
            rows = [row for row in rows if row.created_at <= filters.to_timestamp]

        if filters.sort == "name":
            rows.sort(key=lambda row: (row.original_filename.lower(), row.id))
        elif filters.sort == "created":
            rows.sort(key=lambda row: (row.created_at, row.id))
        else:
            rows.sort(key=lambda row: (row.updated_at, row.id))
        if filters.direction == "desc":
            rows.reverse()

        start = filters.cursor
        end = start + filters.page_size
        next_cursor = end if end < len(rows) else None
        return rows[start:end], next_cursor

    def get_document(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentRecord:
        self._require_project_access(project_id)
        row = self._find_document(project_id, document_id)
        if row is None:
            raise DocumentNotFoundError("Document not found.")
        return row

    def list_document_timeline(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        limit: int = 100,
    ) -> list[DocumentProcessingRunRecord]:
        self._require_project_access(project_id)
        document = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        rows = self._timeline.get(document.id, [])
        return rows[:limit]

    def list_document_pages(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> list[DocumentPageRecord]:
        self._require_project_access(project_id)
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        return list(self._pages.get(document_id, []))

    def get_document_page(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        page_id: str,
    ) -> DocumentPageRecord:
        self._require_project_access(project_id)
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        for page in self._pages.get(document_id, []):
            if page.id == page_id:
                return page
        raise DocumentPageNotFoundError("Page not found.")

    def update_document_page_rotation(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        page_id: str,
        viewer_rotation: int,
    ) -> DocumentPageRecord:
        self._require_project_access(project_id)
        pages = self._pages.get(document_id, [])
        for index, page in enumerate(pages):
            if page.id == page_id:
                updated = replace(
                    page,
                    viewer_rotation=viewer_rotation,
                    updated_at=datetime.now(UTC),
                )
                pages[index] = updated
                return updated
        raise DocumentPageNotFoundError("Page not found.")

    def read_document_page_image(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        page_id: str,
        variant: str,
        run_id: str | None = None,
    ) -> DocumentPageImageAsset:
        page = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        if variant == "full":
            if not page.derived_image_key:
                raise DocumentPageAssetNotReadyError("Page image is not ready.")
            return DocumentPageImageAsset(
                payload=b"fixture-page-image",
                media_type="image/png",
                etag_seed=page.derived_image_sha256,
                cache_control="private, no-cache, max-age=0, must-revalidate",
            )
        if variant == "thumb":
            if not page.thumbnail_key:
                raise DocumentPageAssetNotReadyError("Page thumbnail is not ready.")
            return DocumentPageImageAsset(
                payload=b"fixture-page-thumb",
                media_type="image/jpeg",
                etag_seed=page.thumbnail_sha256,
                cache_control="private, no-cache, max-age=0, must-revalidate",
            )
        if variant in {"preprocessed_gray", "preprocessed_bin"}:
            _, run = self._resolve_preprocess_run_for_variant(
                current_user=current_user,
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            page_result = next(
                (row for row in self._preprocess_pages.get(run.id, []) if row.page_id == page_id),
                None,
            )
            if page_result is None:
                raise DocumentPageAssetNotReadyError("Preprocessed page variant is not ready.")
            if variant == "preprocessed_gray":
                if not page_result.output_object_key_gray:
                    raise DocumentPageAssetNotReadyError("Preprocessed grayscale image is not ready.")
                return DocumentPageImageAsset(
                    payload=b"fixture-preprocess-gray",
                    media_type="image/png",
                    etag_seed=page_result.sha256_gray,
                    cache_control="private, no-cache, max-age=0, must-revalidate",
                )
            if not page_result.output_object_key_bin:
                raise DocumentPageAssetNotReadyError("Preprocessed binary image is not ready.")
            return DocumentPageImageAsset(
                payload=b"fixture-preprocess-bin",
                media_type="image/png",
                etag_seed=page_result.sha256_bin,
                cache_control="private, no-cache, max-age=0, must-revalidate",
            )
        raise DocumentValidationError(
            "variant must be 'full', 'thumb', 'preprocessed_gray', or 'preprocessed_bin'."
        )

    def get_document_page_variants(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        page_id: str,
        run_id: str | None = None,
    ) -> DocumentPageVariantsSnapshot:
        document = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        page = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        requested_run_id, run = self._resolve_preprocess_run_for_variant(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page_result = next(
            (row for row in self._preprocess_pages.get(run.id, []) if row.page_id == page_id),
            None,
        )
        metrics_json = page_result.metrics_json if page_result is not None else {}
        warnings_json = list(page_result.warnings_json) if page_result is not None else []
        status = page_result.status if page_result is not None else None
        gate = page_result.quality_gate_status if page_result is not None else None
        variants = [
            DocumentPageVariantAvailability(
                variant="ORIGINAL",
                image_variant="full",
                available=bool(page.derived_image_key),
                media_type="image/png",
                run_id=None,
                result_status=None,
                quality_gate_status=None,
                warnings_json=[],
                metrics_json={},
            ),
            DocumentPageVariantAvailability(
                variant="PREPROCESSED_GRAY",
                image_variant="preprocessed_gray",
                available=bool(page_result and page_result.output_object_key_gray),
                media_type="image/png",
                run_id=run.id,
                result_status=status,
                quality_gate_status=gate,
                warnings_json=warnings_json,
                metrics_json=metrics_json,
            ),
            DocumentPageVariantAvailability(
                variant="PREPROCESSED_BIN",
                image_variant="preprocessed_bin",
                available=bool(page_result and page_result.output_object_key_bin),
                media_type="image/png",
                run_id=run.id,
                result_status=status,
                quality_gate_status=gate,
                warnings_json=warnings_json,
                metrics_json=metrics_json,
            ),
        ]
        return DocumentPageVariantsSnapshot(
            document=document,
            page=page,
            requested_run_id=requested_run_id,
            resolved_run=run,
            variants=variants,
        )

    def upload_document(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        original_filename: str,
        file_stream: BinaryIO,
    ) -> DocumentImportSnapshot:
        self._require_project_access(project_id)
        payload = file_stream.read()
        if not isinstance(payload, bytes):
            raise DocumentValidationError("Upload payload is invalid.")
        if len(payload) > self.max_upload_bytes:
            raise DocumentValidationError("File exceeds the configured maximum upload size.")
        if len(payload) < 1:
            raise DocumentValidationError("Uploaded file is empty.")

        try:
            detection = validate_extension_matches_magic(
                filename=original_filename,
                prefix_bytes=payload[:64],
            )
        except DocumentUploadValidationError as error:
            raise DocumentValidationError(str(error)) from error

        current_usage = sum(
            row.bytes or 0 for row in self._documents.get(project_id, []) if row.status != "CANCELED"
        )
        if current_usage + len(payload) > self.project_quota_bytes:
            raise DocumentQuotaExceededError("Project storage quota exceeded for this upload.")

        now = datetime.now(UTC)
        document_id = f"doc-upload-{len(self._imports) + 1}"
        import_id = f"import-upload-{len(self._imports) + 1}"
        document = DocumentRecord(
            id=document_id,
            project_id=project_id,
            original_filename=original_filename,
            stored_filename=f"controlled/raw/{project_id}/{document_id}/original.bin",
            content_type_detected=detection.detected_content_type,
            bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            page_count=None,
            status="QUEUED",
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        import_record = DocumentImportRecord(
            id=import_id,
            document_id=document_id,
            status="QUEUED",
            failure_reason=None,
            created_by=current_user.user_id,
            accepted_at=None,
            rejected_at=None,
            canceled_by=None,
            canceled_at=None,
            created_at=now,
            updated_at=now,
        )
        self._documents.setdefault(project_id, []).insert(0, document)
        snapshot = self._write_import_snapshot(
            project_id=project_id,
            import_id=import_id,
            document=document,
            import_record=import_record,
        )
        self._import_payloads[import_id] = payload
        self.scan_transitions[import_id] = ["QUEUED"]
        return snapshot

    def get_document_import(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        import_id: str,
    ) -> DocumentImportSnapshot:
        self._require_project_access(project_id)
        snapshot = self._imports.get(import_id)
        if snapshot is None or snapshot.document_record.project_id != project_id:
            raise DocumentImportNotFoundError("Document import not found.")
        return snapshot

    def cancel_document_import(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        import_id: str,
    ) -> DocumentImportSnapshot:
        snapshot = self.get_document_import(
            current_user=current_user,
            project_id=project_id,
            import_id=import_id,
        )
        if snapshot.import_record.status not in {"UPLOADING", "QUEUED"}:
            raise DocumentImportConflictError(
                "Cancel is only allowed while status is UPLOADING or QUEUED."
            )
        now = datetime.now(UTC)
        import_record = replace(
            snapshot.import_record,
            status="CANCELED",
            canceled_by=current_user.user_id,
            canceled_at=now,
            updated_at=now,
        )
        document = replace(
            snapshot.document_record,
            status="CANCELED",
            updated_at=now,
        )
        self.scan_transitions.setdefault(import_id, []).append("CANCELED")
        return self._write_import_snapshot(
            project_id=project_id,
            import_id=import_id,
            document=document,
            import_record=import_record,
        )

    def begin_scan(
        self,
        *,
        project_id: str,
        import_id: str,
    ) -> DocumentImportSnapshot | None:
        snapshot = self._imports.get(import_id)
        if not self.auto_scan or snapshot is None:
            return None
        if snapshot.document_record.project_id != project_id:
            return None
        if snapshot.import_record.status != "QUEUED":
            return None
        now = datetime.now(UTC)
        import_record = replace(
            snapshot.import_record,
            status="SCANNING",
            updated_at=now,
        )
        document = replace(snapshot.document_record, status="SCANNING", updated_at=now)
        self.scan_transitions.setdefault(import_id, []).append("SCANNING")
        return self._write_import_snapshot(
            project_id=project_id,
            import_id=import_id,
            document=document,
            import_record=import_record,
        )

    def complete_scan(
        self,
        *,
        project_id: str,
        import_id: str,
    ) -> DocumentImportSnapshot:
        snapshot = self._imports.get(import_id)
        if snapshot is None or snapshot.document_record.project_id != project_id:
            raise DocumentImportNotFoundError("Document import not found.")
        if snapshot.import_record.status != "SCANNING":
            raise DocumentImportConflictError("Scan completion requires SCANNING status.")

        now = datetime.now(UTC)
        payload = self._import_payloads.get(import_id, b"")
        if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in payload:
            import_record = replace(
                snapshot.import_record,
                status="REJECTED",
                rejected_at=now,
                failure_reason="Deterministic scanner rejected the upload sample.",
                updated_at=now,
            )
            document = replace(snapshot.document_record, status="FAILED", updated_at=now)
            self.scan_transitions.setdefault(import_id, []).append("REJECTED")
        else:
            import_record = replace(
                snapshot.import_record,
                status="ACCEPTED",
                accepted_at=now,
                updated_at=now,
            )
            document = replace(snapshot.document_record, status="EXTRACTING", updated_at=now)
            self.scan_transitions.setdefault(import_id, []).append("ACCEPTED")

        return self._write_import_snapshot(
            project_id=project_id,
            import_id=import_id,
            document=document,
            import_record=import_record,
        )

    def get_document_processing_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentProcessingRunRecord:
        self._require_project_access(project_id)
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        for run in self._timeline.get(document_id, []):
            if run.id == run_id:
                return run
        raise DocumentProcessingRunNotFoundError("Processing run not found.")

    def retry_document_extraction(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentProcessingRunRecord:
        self._require_project_access(project_id)
        if "ADMIN" not in set(current_user.platform_roles) and current_user.user_id != "user-1":
            raise DocumentRetryAccessDeniedError(
                "Current role cannot retry extraction in this project."
            )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        timeline = self._timeline.get(document_id, [])
        target = next(
            (
                run
                for run in timeline
                if run.run_kind == "EXTRACTION" and run.superseded_by_processing_run_id is None
            ),
            None,
        )
        if target is None:
            raise DocumentRetryConflictError("No extraction attempt is available for retry.")
        if target.status not in {"FAILED", "CANCELED"}:
            raise DocumentRetryConflictError(
                "Retry is allowed only when the latest extraction attempt is FAILED or CANCELED."
            )
        now = datetime.now(UTC)
        self._processing_run_sequence += 1
        retry_run = DocumentProcessingRunRecord(
            id=f"run-{self._processing_run_sequence}",
            document_id=document_id,
            attempt_number=target.attempt_number + 1,
            run_kind="EXTRACTION",
            supersedes_processing_run_id=target.id,
            superseded_by_processing_run_id=None,
            status="QUEUED",
            created_by=current_user.user_id,
            created_at=now,
            started_at=None,
            finished_at=None,
            canceled_by=None,
            canceled_at=None,
            failure_reason=None,
        )
        target_index = timeline.index(target)
        timeline[target_index] = replace(target, superseded_by_processing_run_id=retry_run.id)
        timeline.insert(0, retry_run)
        documents = self._documents.get(project_id, [])
        for index, row in enumerate(documents):
            if row.id == document_id:
                documents[index] = replace(row, status="EXTRACTING", updated_at=now)
        return retry_run

    def list_preprocess_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        cursor: int = 0,
        page_size: int = 50,
    ) -> tuple[list[PreprocessRunRecord], int | None]:
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        rows = list(self._preprocess_runs.get(document_id, []))
        start = max(0, cursor)
        safe_page_size = max(1, min(page_size, 200))
        end = start + safe_page_size
        next_cursor = end if end < len(rows) else None
        return rows[start:end], next_cursor

    def get_preprocess_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> PreprocessRunRecord:
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        return self._get_preprocess_run_or_raise(document_id=document_id, run_id=run_id)

    def get_preprocess_run_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> PreprocessRunRecord:
        return self.get_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )

    def get_preprocess_projection(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentPreprocessProjectionRecord | None:
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        return self._preprocess_projection.get(document_id)

    def get_active_preprocess_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> tuple[DocumentPreprocessProjectionRecord | None, PreprocessRunRecord | None]:
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        projection = self._preprocess_projection.get(document_id)
        if projection is None or not projection.active_preprocess_run_id:
            return projection, None
        return projection, self._get_preprocess_run_or_raise(
            document_id=document_id,
            run_id=projection.active_preprocess_run_id,
        )

    def get_preprocess_downstream_basis_references(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> PreprocessDownstreamBasisReferencesRecord:
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        return PreprocessDownstreamBasisReferencesRecord(
            has_layout_projection=document_id
            in self._layout_projection_input_preprocess_run_id,
            layout_active_input_preprocess_run_id=self._layout_projection_input_preprocess_run_id.get(
                document_id
            ),
            has_transcription_projection=document_id
            in self._transcription_projection_preprocess_run_id,
            transcription_active_preprocess_run_id=self._transcription_projection_preprocess_run_id.get(
                document_id
            ),
        )

    def list_preprocess_run_pages(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        status: str | None = None,
        warning: str | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[list[PagePreprocessResultRecord], int | None]:
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        rows = list(self._preprocess_pages.get(run_id, []))
        if isinstance(status, str):
            rows = [row for row in rows if row.status == status]
        if isinstance(warning, str) and warning.strip():
            rows = [row for row in rows if warning.strip() in row.warnings_json]
        start = max(0, cursor)
        safe_page_size = max(1, min(page_size, 500))
        end = start + safe_page_size
        next_cursor = end if end < len(rows) else None
        return rows[start:end], next_cursor

    def get_preprocess_run_page(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PagePreprocessResultRecord:
        items, _ = self.list_preprocess_run_pages(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            cursor=0,
            page_size=500,
        )
        for row in items:
            if row.page_id == page_id:
                return row
        raise DocumentPageNotFoundError("Preprocessing page result not found.")

    def list_preprocessing_quality(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str | None = None,
        status: str | None = None,
        warning: str | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[
        DocumentPreprocessProjectionRecord | None,
        PreprocessRunRecord | None,
        list[PagePreprocessResultRecord],
        int | None,
    ]:
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        projection = self._preprocess_projection.get(document_id)
        selected_run_id = run_id or (
            projection.active_preprocess_run_id if projection else None
        )
        if not selected_run_id:
            return projection, None, [], None
        run = self.get_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=selected_run_id,
        )
        items, next_cursor = self.list_preprocess_run_pages(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            status=status,
            warning=warning,
            cursor=cursor,
            page_size=page_size,
        )
        return projection, run, items, next_cursor

    def create_preprocess_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        profile_id: str | None = None,
        params_json: dict[str, object] | None = None,
        pipeline_version: str | None = None,
        container_digest: str | None = None,
        parent_run_id: str | None = None,
        supersedes_run_id: str | None = None,
        target_page_ids: list[str] | None = None,
        advanced_risk_confirmed: bool | None = None,
        advanced_risk_acknowledgement: str | None = None,
    ) -> PreprocessRunRecord:
        self._require_preprocess_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        runs = self._preprocess_runs.setdefault(document_id, [])
        if parent_run_id is not None:
            _ = self._get_preprocess_run_or_raise(
                document_id=document_id,
                run_id=parent_run_id,
            )
        if supersedes_run_id is not None:
            superseded = self._get_preprocess_run_or_raise(
                document_id=document_id,
                run_id=supersedes_run_id,
            )
            if superseded.superseded_by_run_id is not None:
                raise DocumentPreprocessConflictError(
                    "Superseded preprocess run is already superseded."
                )
        now = datetime.now(UTC)
        self._preprocess_run_sequence += 1
        run_id = f"pre-run-{self._preprocess_run_sequence}"
        normalized_target_page_ids = (
            list(dict.fromkeys(page_id.strip() for page_id in target_page_ids if page_id.strip()))
            if target_page_ids
            else None
        )
        resolved_profile_id = profile_id or "BALANCED"
        is_advanced_profile = resolved_profile_id in {"AGGRESSIVE", "BLEED_THROUGH"}
        confirmation_required = is_advanced_profile and normalized_target_page_ids is None
        if confirmation_required and advanced_risk_confirmed is not True:
            raise DocumentPreprocessConflictError(
                "Advanced full-document preprocessing requires explicit risk confirmation."
            )
        params_payload = dict(params_json or {})
        if normalized_target_page_ids:
            params_payload["target_page_ids"] = normalized_target_page_ids
        else:
            params_payload.pop("target_page_ids", None)
        params_payload["profile_risk_posture"] = (
            "ADVANCED_GATED" if is_advanced_profile else "SAFE_DEFAULT"
        )
        params_payload["advanced_risk_confirmation_required"] = confirmation_required
        params_payload["advanced_risk_confirmation"] = {
            "confirmed": confirmation_required,
            "confirmed_by_role": "REVIEWER" if confirmation_required else None,
            "confirmed_by_user_id": current_user.user_id if confirmation_required else None,
            "acknowledgement": (
                advanced_risk_acknowledgement or ADVANCED_RISK_CONFIRMATION_COPY
            )
            if confirmation_required
            else None,
        }
        run = PreprocessRunRecord(
            id=run_id,
            project_id=project_id,
            document_id=document_id,
            parent_run_id=parent_run_id,
            attempt_number=len(runs) + 1,
            superseded_by_run_id=None,
            profile_id=resolved_profile_id,
            params_json=params_payload,
            params_hash=f"hash-{run_id}",
            pipeline_version=pipeline_version or "preprocess-v1",
            container_digest=container_digest or "ukde/preprocess:v1",
            status="QUEUED",
            created_by=current_user.user_id,
            created_at=now,
            started_at=None,
            finished_at=None,
            failure_reason=None,
            run_scope="PAGE_SUBSET" if normalized_target_page_ids else "FULL_DOCUMENT",
            target_page_ids_json=normalized_target_page_ids,
        )
        if supersedes_run_id is not None:
            for index, row in enumerate(runs):
                if row.id == supersedes_run_id:
                    runs[index] = replace(row, superseded_by_run_id=run.id)
                    break
        runs.insert(0, run)

        page_results: list[PagePreprocessResultRecord] = []
        for page in self._pages.get(document_id, []):
            if normalized_target_page_ids and page.id not in normalized_target_page_ids:
                continue
            source_dpi = page.source_dpi if page.source_dpi is not None else page.dpi
            if source_dpi is None:
                gate = "REVIEW_REQUIRED"
                warnings = ["LOW_DPI"]
            elif source_dpi < 150:
                gate = "BLOCKED"
                warnings = ["LOW_DPI"]
            elif source_dpi < 200:
                gate = "REVIEW_REQUIRED"
                warnings = ["LOW_DPI"]
            else:
                gate = "PASS"
                warnings = []
            page_results.append(
                PagePreprocessResultRecord(
                    run_id=run.id,
                    page_id=page.id,
                    page_index=page.page_index,
                    status="QUEUED",
                    quality_gate_status=gate,  # type: ignore[arg-type]
                    input_object_key=page.derived_image_key,
                    output_object_key_gray=None,
                    output_object_key_bin=None,
                    metrics_json={},
                    sha256_gray=None,
                    sha256_bin=None,
                    warnings_json=warnings,
                    failure_reason=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        self._preprocess_pages[run.id] = page_results
        return run

    def rerun_preprocess_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        profile_id: str | None = None,
        params_json: dict[str, object] | None = None,
        pipeline_version: str | None = None,
        container_digest: str | None = None,
        target_page_ids: list[str] | None = None,
        advanced_risk_confirmed: bool | None = None,
        advanced_risk_acknowledgement: str | None = None,
    ) -> PreprocessRunRecord:
        source = self.get_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if source.status in {"QUEUED", "RUNNING"}:
            raise DocumentPreprocessConflictError("Rerun requires a terminal source run.")
        resolved_params = dict(params_json or source.params_json)
        if target_page_ids:
            resolved_params["target_page_ids"] = list(dict.fromkeys(target_page_ids))
        else:
            resolved_params.pop("target_page_ids", None)
        return self.create_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            profile_id=profile_id or source.profile_id,
            params_json=resolved_params,
            pipeline_version=pipeline_version or source.pipeline_version,
            container_digest=container_digest or source.container_digest,
            parent_run_id=source.parent_run_id or source.id,
            supersedes_run_id=source.id,
            target_page_ids=target_page_ids,
            advanced_risk_confirmed=advanced_risk_confirmed,
            advanced_risk_acknowledgement=advanced_risk_acknowledgement,
        )

    def cancel_preprocess_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> PreprocessRunRecord:
        self._require_preprocess_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        run = self.get_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run.status not in {"QUEUED", "RUNNING"}:
            raise DocumentPreprocessConflictError(
                "Preprocess run can be canceled only while QUEUED or RUNNING."
            )
        now = datetime.now(UTC)
        canceled = replace(
            run,
            status="CANCELED",
            finished_at=now,
            failure_reason=f"Canceled by {current_user.user_id}.",
        )
        runs = self._preprocess_runs.get(document_id, [])
        for index, row in enumerate(runs):
            if row.id == run.id:
                runs[index] = canceled
                break
        page_rows = self._preprocess_pages.get(run.id, [])
        self._preprocess_pages[run.id] = [
            replace(
                row,
                status="CANCELED" if row.status in {"QUEUED", "RUNNING"} else row.status,
                failure_reason=(
                    row.failure_reason
                    if row.failure_reason
                    else "Run canceled before completion."
                ),
                updated_at=now,
            )
            for row in page_rows
        ]
        return canceled

    def activate_preprocess_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentPreprocessProjectionRecord:
        self._require_preprocess_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        run = self.get_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run.status != "SUCCEEDED":
            raise DocumentPreprocessConflictError("Only SUCCEEDED preprocess runs can be activated.")
        page_rows = self._preprocess_pages.get(run.id, [])
        if any(row.quality_gate_status == "BLOCKED" for row in page_rows):
            raise DocumentPreprocessConflictError(
                "Activation is blocked while any page is BLOCKED."
            )
        projection = DocumentPreprocessProjectionRecord(
            document_id=document_id,
            project_id=project_id,
            active_preprocess_run_id=run.id,
            active_profile_id=run.profile_id,
            updated_at=datetime.now(UTC),
        )
        self._preprocess_projection[document_id] = projection
        return projection

    def get_preprocessing_overview(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentPreprocessOverviewSnapshot:
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        document = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        projection, active_run = self.get_active_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        runs = list(self._preprocess_runs.get(document_id, []))
        status_counts = {
            "QUEUED": 0,
            "RUNNING": 0,
            "SUCCEEDED": 0,
            "FAILED": 0,
            "CANCELED": 0,
        }
        quality_counts = {"PASS": 0, "REVIEW_REQUIRED": 0, "BLOCKED": 0}
        warning_count = 0
        if active_run is not None:
            for row in self._preprocess_pages.get(active_run.id, []):
                status_counts[row.status] += 1
                quality_counts[row.quality_gate_status] += 1
                warning_count += len(row.warnings_json)
        return DocumentPreprocessOverviewSnapshot(
            document=document,
            projection=projection,
            active_run=active_run,
            latest_run=runs[0] if runs else None,
            total_runs=len(runs),
            page_count=len(self._pages.get(document_id, [])),
            active_status_counts=status_counts,  # type: ignore[arg-type]
            active_quality_gate_counts=quality_counts,  # type: ignore[arg-type]
            active_warning_count=warning_count,
        )

    def compare_preprocess_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        base_run_id: str,
        candidate_run_id: str,
    ) -> DocumentPreprocessCompareSnapshot:
        if base_run_id == candidate_run_id:
            raise DocumentValidationError(
                "baseRunId and candidateRunId must reference different runs."
            )
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        document = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        base_run = self.get_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=base_run_id,
        )
        candidate_run = self.get_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=candidate_run_id,
        )
        base_pages = self._preprocess_pages.get(base_run.id, [])
        candidate_pages = self._preprocess_pages.get(candidate_run.id, [])
        by_page: dict[str, dict[str, object]] = {}
        for row in base_pages:
            by_page[row.page_id] = {
                "page_index": row.page_index,
                "base": row,
                "candidate": None,
            }
        for row in candidate_pages:
            if row.page_id not in by_page:
                by_page[row.page_id] = {
                    "page_index": row.page_index,
                    "base": None,
                    "candidate": row,
                }
            else:
                by_page[row.page_id]["candidate"] = row
        pairs = [
            DocumentPreprocessComparePageSnapshot(
                page_id=page_id,
                page_index=int(entry["page_index"]),
                base_result=entry["base"],  # type: ignore[arg-type]
                candidate_result=entry["candidate"],  # type: ignore[arg-type]
            )
            for page_id, entry in sorted(
                by_page.items(),
                key=lambda item: (int(item[1]["page_index"]), item[0]),
            )
        ]
        return DocumentPreprocessCompareSnapshot(
            document=document,
            base_run=base_run,
            candidate_run=candidate_run,
            page_pairs=pairs,
            base_warning_count=sum(len(row.warnings_json) for row in base_pages),
            candidate_warning_count=sum(len(row.warnings_json) for row in candidate_pages),
            base_blocked_count=sum(
                1 for row in base_pages if row.quality_gate_status == "BLOCKED"
            ),
            candidate_blocked_count=sum(
                1 for row in candidate_pages if row.quality_gate_status == "BLOCKED"
            ),
        )

    def list_layout_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        cursor: int = 0,
        page_size: int = 50,
    ) -> tuple[list[LayoutRunRecord], int | None]:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        rows = list(self._layout_runs.get(document_id, []))
        start = max(0, cursor)
        safe_page_size = max(1, min(page_size, 200))
        end = start + safe_page_size
        next_cursor = end if end < len(rows) else None
        return rows[start:end], next_cursor

    def get_layout_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> LayoutRunRecord:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        run = self._get_layout_run_or_raise(document_id=document_id, run_id=run_id)
        return self._with_layout_activation_gate(document_id=document_id, run=run)

    def get_layout_run_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> LayoutRunRecord:
        return self.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )

    def get_layout_projection(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentLayoutProjectionRecord | None:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        return self._layout_projection.get(document_id)

    def get_active_layout_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> tuple[DocumentLayoutProjectionRecord | None, LayoutRunRecord | None]:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        projection = self._layout_projection.get(document_id)
        if projection is None or not projection.active_layout_run_id:
            return projection, None
        run = self._get_layout_run_or_raise(
            document_id=document_id,
            run_id=projection.active_layout_run_id,
        )
        return projection, self._with_layout_activation_gate(
            document_id=document_id,
            run=run,
        )

    def list_layout_run_pages(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        status: str | None = None,
        page_recall_status: str | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[list[PageLayoutResultRecord], int | None]:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        rows = list(self._layout_pages.get(run_id, []))
        if isinstance(status, str):
            rows = [row for row in rows if row.status == status]
        if isinstance(page_recall_status, str):
            rows = [row for row in rows if row.page_recall_status == page_recall_status]
        start = max(0, cursor)
        safe_page_size = max(1, min(page_size, 500))
        end = start + safe_page_size
        next_cursor = end if end < len(rows) else None
        return rows[start:end], next_cursor

    def get_layout_page_recall_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> DocumentLayoutPageRecallStatusSnapshot:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _ = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        snapshot = self._layout_recall_status_snapshots.get((run_id, page_id))
        if snapshot is None:
            raise DocumentPageAssetNotReadyError("Layout recall status is not ready.")
        return snapshot

    def list_layout_page_rescue_candidates(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[LayoutRescueCandidateRecord]:
        _ = self.get_layout_page_recall_status(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        return list(self._layout_rescue_candidates.get((run_id, page_id), []))

    def read_layout_page_overlay(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> DocumentLayoutOverlayAsset:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _ = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        payload = self._layout_overlay_payloads.get((run_id, page_id))
        if payload is None:
            raise DocumentPageAssetNotReadyError("Layout overlay is not ready.")
        return DocumentLayoutOverlayAsset(
            payload=payload,
            etag_seed=f"overlay-{run_id}-{page_id}",
        )

    def read_layout_page_xml(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> DocumentLayoutPageXmlAsset:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _ = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        payload = self._layout_pagexml_payloads.get((run_id, page_id))
        if payload is None:
            raise DocumentPageAssetNotReadyError("Layout PAGE-XML is not ready.")
        return DocumentLayoutPageXmlAsset(
            payload=payload,
            media_type="application/xml",
            etag_seed=f"pagexml-{run_id}-{page_id}",
        )

    def update_layout_page_reading_order(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        version_etag: str,
        groups: list[dict[str, object]],
        mode: str | None = None,
    ) -> DocumentLayoutReadingOrderSnapshot:
        self._require_layout_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        payload = self._layout_overlay_payloads.get((run_id, page_id))
        if payload is None:
            raise DocumentPageAssetNotReadyError("Layout overlay is not ready.")
        metadata = payload.get("readingOrderMeta")
        if not isinstance(metadata, dict):
            metadata = {}
            payload["readingOrderMeta"] = metadata
        expected_etag = str(metadata.get("versionEtag") or "").strip()
        if not expected_etag:
            expected_etag = "layout-etag-1"
            metadata["versionEtag"] = expected_etag
        if version_etag.strip() != expected_etag:
            raise DocumentLayoutConflictError(
                "Reading-order update conflicts with a newer saved layout version."
            )

        normalized_groups: list[dict[str, object]] = []
        for index, group in enumerate(groups):
            group_id = str(group.get("id") or f"g-{index + 1:04d}").strip() or f"g-{index + 1:04d}"
            raw_region_ids = group.get("regionIds")
            if not isinstance(raw_region_ids, list):
                continue
            region_ids = [
                str(region_id).strip()
                for region_id in raw_region_ids
                if isinstance(region_id, str) and region_id.strip()
            ]
            if not region_ids:
                continue
            normalized_groups.append(
                {
                    "id": group_id,
                    "ordered": bool(group.get("ordered", True)),
                    "regionIds": region_ids,
                }
            )
        resolved_mode = mode.strip().upper() if isinstance(mode, str) else ""
        if resolved_mode not in {"ORDERED", "UNORDERED", "WITHHELD"}:
            resolved_mode = (
                "ORDERED"
                if normalized_groups and all(bool(group["ordered"]) for group in normalized_groups)
                else "UNORDERED"
                if normalized_groups
                else "WITHHELD"
            )
        if resolved_mode == "WITHHELD":
            normalized_groups = []

        line_by_region: dict[str, str] = {}
        raw_elements = payload.get("elements")
        if isinstance(raw_elements, list):
            for raw_element in raw_elements:
                if not isinstance(raw_element, dict):
                    continue
                if raw_element.get("type") != "LINE":
                    continue
                line_id = str(raw_element.get("id") or "").strip()
                parent_id = str(raw_element.get("parentId") or "").strip()
                if line_id and parent_id and parent_id not in line_by_region:
                    line_by_region[parent_id] = line_id
        edges: list[dict[str, str]] = []
        for group in normalized_groups:
            region_ids = [
                str(region_id)
                for region_id in group.get("regionIds", [])
                if isinstance(region_id, str)
            ]
            previous_region_id: str | None = None
            for region_id in region_ids:
                line_id = line_by_region.get(region_id)
                if line_id is not None:
                    edges.append({"fromId": region_id, "toId": line_id})
                if bool(group.get("ordered", True)) and previous_region_id is not None:
                    edges.append({"fromId": previous_region_id, "toId": region_id})
                previous_region_id = region_id

        revision_key = (run_id, page_id)
        next_revision = self._layout_reading_order_revisions.get(revision_key, 1) + 1
        self._layout_reading_order_revisions[revision_key] = next_revision
        next_layout_version_id = f"layout-version-{next_revision}"
        next_version_etag = f"layout-etag-{next_revision}"
        payload["readingOrder"] = edges
        payload["readingOrderGroups"] = normalized_groups
        payload["readingOrderMeta"] = {
            "schemaVersion": 1,
            "mode": resolved_mode,
            "source": "MANUAL_OVERRIDE",
            "ambiguityScore": metadata.get("ambiguityScore", 0.12),
            "columnCertainty": metadata.get("columnCertainty", 0.92),
            "overlapConflictScore": metadata.get("overlapConflictScore", 0.03),
            "orphanLineCount": metadata.get("orphanLineCount", 0),
            "nonTextComplexityScore": metadata.get("nonTextComplexityScore", 0.01),
            "orderWithheld": resolved_mode == "WITHHELD",
            "versionEtag": next_version_etag,
            "layoutVersionId": next_layout_version_id,
        }
        return DocumentLayoutReadingOrderSnapshot(
            run_id=run_id,
            page_id=page_id,
            page_index=page.page_index,
            layout_version_id=next_layout_version_id,
            version_etag=next_version_etag,
            mode=resolved_mode,
            groups=tuple(
                DocumentLayoutReadingOrderGroupSnapshot(
                    group_id=str(group["id"]),
                    ordered=bool(group["ordered"]),
                    region_ids=tuple(
                        str(region_id)
                        for region_id in group["regionIds"]
                        if isinstance(region_id, str)
                    ),
                )
                for group in normalized_groups
            ),
            edges=tuple(edges),
            signals_json=dict(payload["readingOrderMeta"]),
        )

    @staticmethod
    def _coerce_overlay_points(
        value: object,
        *,
        field_name: str,
        minimum_points: int,
    ) -> list[dict[str, float]]:
        if not isinstance(value, list):
            raise DocumentValidationError(f"{field_name} must be an array of points.")
        points: list[dict[str, float]] = []
        for index, raw_point in enumerate(value):
            if not isinstance(raw_point, dict):
                raise DocumentValidationError(
                    f"{field_name}[{index}] must be an object with x/y."
                )
            x = raw_point.get("x")
            y = raw_point.get("y")
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                raise DocumentValidationError(
                    f"{field_name}[{index}] must include numeric x/y."
                )
            points.append({"x": float(x), "y": float(y)})
        if len(points) < minimum_points:
            raise DocumentValidationError(
                f"{field_name} must include at least {minimum_points} points."
            )
        return points

    def update_layout_page_elements(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        version_etag: str,
        operations: list[dict[str, object]],
    ) -> DocumentLayoutElementsSnapshot:
        self._require_layout_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        payload = self._layout_overlay_payloads.get((run_id, page_id))
        if payload is None:
            raise DocumentPageAssetNotReadyError("Layout overlay is not ready.")
        if not operations:
            raise DocumentValidationError("At least one layout edit operation is required.")
        metadata = payload.get("readingOrderMeta")
        if not isinstance(metadata, dict):
            metadata = {}
            payload["readingOrderMeta"] = metadata
        expected_etag = str(metadata.get("versionEtag") or "").strip()
        if not expected_etag:
            expected_etag = "layout-etag-1"
            metadata["versionEtag"] = expected_etag
        if version_etag.strip() != expected_etag:
            raise DocumentLayoutConflictError(
                "Layout update conflicts with a newer saved layout version."
            )

        raw_elements = payload.get("elements")
        if not isinstance(raw_elements, list):
            raise DocumentValidationError("Overlay elements are unavailable for edit.")
        elements: list[dict[str, object]] = [dict(item) for item in raw_elements if isinstance(item, dict)]

        def find_element(
            element_id: str,
            *,
            expected_type: str | None = None,
        ) -> dict[str, object]:
            for element in elements:
                if str(element.get("id")) == element_id:
                    if expected_type and str(element.get("type")) != expected_type:
                        break
                    return element
            raise DocumentValidationError(
                f"Element '{element_id}' is not present on page '{page_id}'."
            )

        def sync_region_children() -> None:
            region_map = {
                str(element.get("id")): element
                for element in elements
                if str(element.get("type")) == "REGION"
            }
            for region in region_map.values():
                current = [
                    str(line_id)
                    for line_id in region.get("childIds", [])
                    if isinstance(line_id, str)
                ]
                owned = [
                    str(line.get("id"))
                    for line in elements
                    if str(line.get("type")) == "LINE"
                    and str(line.get("parentId")) == str(region.get("id"))
                ]
                ordered = [line_id for line_id in current if line_id in owned]
                for line_id in owned:
                    if line_id not in ordered:
                        ordered.append(line_id)
                region["childIds"] = ordered

        for operation_index, operation in enumerate(operations):
            kind = str(operation.get("kind") or "").strip().upper()
            if not kind:
                raise DocumentValidationError(f"operations[{operation_index}].kind is required.")

            if kind == "ADD_REGION":
                region_id = str(operation.get("regionId") or "").strip()
                if not region_id:
                    raise DocumentValidationError(
                        f"operations[{operation_index}].regionId is required."
                    )
                polygon = self._coerce_overlay_points(
                    operation.get("polygon"),
                    field_name=f"operations[{operation_index}].polygon",
                    minimum_points=3,
                )
                elements.append(
                    {
                        "id": region_id,
                        "type": "REGION",
                        "parentId": None,
                        "childIds": [],
                        "regionType": str(operation.get("regionType") or "TEXT"),
                        "includeInReadingOrder": bool(
                            operation.get("includeInReadingOrder", True)
                        ),
                        "polygon": polygon,
                    }
                )
                continue

            if kind == "ADD_LINE":
                line_id = str(operation.get("lineId") or "").strip()
                parent_region_id = str(operation.get("parentRegionId") or "").strip()
                if not line_id:
                    raise DocumentValidationError(
                        f"operations[{operation_index}].lineId is required."
                    )
                if not parent_region_id:
                    raise DocumentValidationError(
                        f"operations[{operation_index}].parentRegionId is required."
                    )
                _ = find_element(parent_region_id, expected_type="REGION")
                polygon = self._coerce_overlay_points(
                    operation.get("polygon"),
                    field_name=f"operations[{operation_index}].polygon",
                    minimum_points=3,
                )
                candidate: dict[str, object] = {
                    "id": line_id,
                    "type": "LINE",
                    "parentId": parent_region_id,
                    "polygon": polygon,
                }
                if operation.get("baseline") is not None:
                    candidate["baseline"] = self._coerce_overlay_points(
                        operation.get("baseline"),
                        field_name=f"operations[{operation_index}].baseline",
                        minimum_points=2,
                    )
                elements.append(candidate)
                sync_region_children()
                continue

            if kind == "MOVE_REGION":
                region_id = str(operation.get("regionId") or "").strip()
                region = find_element(region_id, expected_type="REGION")
                region["polygon"] = self._coerce_overlay_points(
                    operation.get("polygon"),
                    field_name=f"operations[{operation_index}].polygon",
                    minimum_points=3,
                )
                continue

            if kind == "MOVE_LINE":
                line_id = str(operation.get("lineId") or "").strip()
                line = find_element(line_id, expected_type="LINE")
                line["polygon"] = self._coerce_overlay_points(
                    operation.get("polygon"),
                    field_name=f"operations[{operation_index}].polygon",
                    minimum_points=3,
                )
                continue

            if kind == "MOVE_BASELINE":
                line_id = str(operation.get("lineId") or "").strip()
                line = find_element(line_id, expected_type="LINE")
                if operation.get("baseline") is None:
                    line.pop("baseline", None)
                else:
                    line["baseline"] = self._coerce_overlay_points(
                        operation.get("baseline"),
                        field_name=f"operations[{operation_index}].baseline",
                        minimum_points=2,
                    )
                continue

            if kind == "DELETE_LINE":
                line_id = str(operation.get("lineId") or "").strip()
                _ = find_element(line_id, expected_type="LINE")
                elements = [
                    element
                    for element in elements
                    if str(element.get("id")) != line_id
                ]
                sync_region_children()
                continue

            if kind == "DELETE_REGION":
                region_id = str(operation.get("regionId") or "").strip()
                _ = find_element(region_id, expected_type="REGION")
                elements = [
                    element
                    for element in elements
                    if str(element.get("id")) != region_id
                    and str(element.get("parentId")) != region_id
                ]
                sync_region_children()
                continue

            if kind == "RETAG_REGION":
                region_id = str(operation.get("regionId") or "").strip()
                region = find_element(region_id, expected_type="REGION")
                region_type = str(operation.get("regionType") or "").strip()
                if not region_type:
                    raise DocumentValidationError(
                        f"operations[{operation_index}].regionType is required."
                    )
                region["regionType"] = region_type
                continue

            if kind == "ASSIGN_LINE_REGION":
                line_id = str(operation.get("lineId") or "").strip()
                parent_region_id = str(operation.get("parentRegionId") or "").strip()
                if not parent_region_id:
                    raise DocumentValidationError(
                        f"operations[{operation_index}].parentRegionId is required."
                    )
                line = find_element(line_id, expected_type="LINE")
                _ = find_element(parent_region_id, expected_type="REGION")
                line["parentId"] = parent_region_id
                sync_region_children()
                continue

            if kind == "REORDER_REGION_LINES":
                region_id = str(operation.get("regionId") or "").strip()
                region = find_element(region_id, expected_type="REGION")
                raw_line_ids = operation.get("lineIds")
                if not isinstance(raw_line_ids, list):
                    raise DocumentValidationError(
                        f"operations[{operation_index}].lineIds must be an array."
                    )
                next_line_ids = [
                    str(line_id).strip()
                    for line_id in raw_line_ids
                    if isinstance(line_id, str) and line_id.strip()
                ]
                owned_line_ids = {
                    str(line.get("id"))
                    for line in elements
                    if str(line.get("type")) == "LINE"
                    and str(line.get("parentId")) == region_id
                }
                if set(next_line_ids) != owned_line_ids:
                    raise DocumentValidationError(
                        f"operations[{operation_index}].lineIds must match region line ids."
                    )
                region["childIds"] = next_line_ids
                continue

            if kind == "SET_REGION_READING_ORDER_INCLUDED":
                region_id = str(operation.get("regionId") or "").strip()
                region = find_element(region_id, expected_type="REGION")
                include = operation.get("includeInReadingOrder")
                if not isinstance(include, bool):
                    raise DocumentValidationError(
                        "includeInReadingOrder must be boolean."
                    )
                region["includeInReadingOrder"] = include
                continue

            raise DocumentValidationError(f"Unsupported operation kind '{kind}'.")

        sync_region_children()
        valid_ids = {
            str(element.get("id"))
            for element in elements
            if isinstance(element.get("id"), str)
        }
        excluded_region_ids = {
            str(region.get("id"))
            for region in elements
            if str(region.get("type")) == "REGION"
            and not bool(region.get("includeInReadingOrder", True))
        }
        filtered_groups: list[dict[str, object]] = []
        raw_groups = payload.get("readingOrderGroups")
        if isinstance(raw_groups, list):
            for group in raw_groups:
                if not isinstance(group, dict):
                    continue
                region_ids = [
                    str(region_id)
                    for region_id in group.get("regionIds", [])
                    if isinstance(region_id, str)
                    and region_id in valid_ids
                    and region_id not in excluded_region_ids
                ]
                if not region_ids:
                    continue
                filtered_groups.append(
                    {
                        "id": str(group.get("id") or ""),
                        "ordered": bool(group.get("ordered", True)),
                        "regionIds": region_ids,
                    }
                )

        payload["elements"] = elements
        payload["readingOrderGroups"] = filtered_groups
        if filtered_groups and all(bool(group.get("ordered", True)) for group in filtered_groups):
            mode = "ORDERED"
            order_withheld = False
        elif filtered_groups:
            mode = "UNORDERED"
            order_withheld = False
        else:
            mode = "WITHHELD"
            order_withheld = True
        payload["readingOrder"] = [
            edge
            for edge in payload.get("readingOrder", [])
            if isinstance(edge, dict)
            and str(edge.get("fromId")) in valid_ids
            and str(edge.get("toId")) in valid_ids
            and str(edge.get("fromId")) not in excluded_region_ids
            and str(edge.get("toId")) not in excluded_region_ids
        ]

        revision_key = (run_id, page_id)
        next_revision = self._layout_reading_order_revisions.get(revision_key, 1) + 1
        self._layout_reading_order_revisions[revision_key] = next_revision
        next_layout_version_id = f"layout-version-{next_revision}"
        next_version_etag = f"layout-etag-{next_revision}"
        payload["readingOrderMeta"] = {
            "schemaVersion": 1,
            "mode": mode,
            "source": "MANUAL_OVERRIDE",
            "ambiguityScore": metadata.get("ambiguityScore", 0.12),
            "columnCertainty": metadata.get("columnCertainty", 0.92),
            "overlapConflictScore": metadata.get("overlapConflictScore", 0.03),
            "orphanLineCount": metadata.get("orphanLineCount", 0),
            "nonTextComplexityScore": metadata.get("nonTextComplexityScore", 0.01),
            "orderWithheld": order_withheld,
            "versionEtag": next_version_etag,
            "layoutVersionId": next_layout_version_id,
        }

        downstream_invalidated = False
        downstream_state: str | None = None
        downstream_reason: str | None = None
        projection = self._layout_projection.get(document_id)
        if projection and projection.active_layout_run_id == run_id:
            downstream_invalidated = True
            downstream_state = "STALE"
            downstream_reason = (
                f"Layout edit changed active transcription basis for page {page_id}."
            )
            now = datetime.now(UTC)
            self._layout_projection[document_id] = replace(
                projection,
                downstream_transcription_state="STALE",
                downstream_transcription_invalidated_at=now,
                downstream_transcription_invalidated_reason=downstream_reason,
                updated_at=now,
            )

        return DocumentLayoutElementsSnapshot(
            run_id=run_id,
            page_id=page_id,
            page_index=page.page_index,
            layout_version_id=next_layout_version_id,
            version_etag=next_version_etag,
            operations_applied=len(operations),
            overlay_payload=dict(payload),
            downstream_transcription_invalidated=downstream_invalidated,
            downstream_transcription_state=downstream_state,
            downstream_transcription_invalidated_reason=downstream_reason,
        )

    def get_layout_line_artifacts(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
    ) -> DocumentLayoutLineArtifactsSnapshot:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _ = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        snapshot = self._layout_line_artifacts.get((run_id, page_id, line_id))
        if snapshot is None:
            raise DocumentPageAssetNotReadyError("Layout line artifacts are not ready.")
        return snapshot

    def read_layout_line_crop_image(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
        variant: str = "line",
    ) -> DocumentPageImageAsset:
        _ = self.get_layout_line_artifacts(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
        )
        payload = self._layout_crop_payloads.get((run_id, page_id, line_id, variant))
        if payload is None:
            raise DocumentPageAssetNotReadyError("Layout crop is not ready.")
        return DocumentPageImageAsset(
            payload=payload,
            media_type="image/png",
            etag_seed=f"crop-{run_id}-{page_id}-{line_id}-{variant}",
            cache_control="private, no-cache, max-age=0, must-revalidate",
        )

    def read_layout_page_thumbnail(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> DocumentPageImageAsset:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _ = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        payload = self._layout_page_thumbnail_payloads.get((run_id, page_id))
        if payload is None:
            raise DocumentPageAssetNotReadyError("Layout page thumbnail is not ready.")
        return DocumentPageImageAsset(
            payload=payload,
            media_type="image/png",
            etag_seed=f"layout-thumb-{run_id}-{page_id}",
            cache_control="private, no-cache, max-age=0, must-revalidate",
        )

    def read_layout_line_context_window(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
    ) -> DocumentLayoutContextWindowAsset:
        snapshot = self.get_layout_line_artifacts(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
        )
        return DocumentLayoutContextWindowAsset(
            payload=snapshot.context_window,
            etag_seed=f"context-{run_id}-{page_id}-{line_id}",
        )

    def create_layout_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        input_preprocess_run_id: str | None = None,
        model_id: str | None = None,
        profile_id: str | None = None,
        params_json: dict[str, object] | None = None,
        pipeline_version: str | None = None,
        container_digest: str | None = None,
        parent_run_id: str | None = None,
        supersedes_run_id: str | None = None,
    ) -> LayoutRunRecord:
        self._require_layout_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        runs = self._layout_runs.setdefault(document_id, [])
        resolved_input_run = (
            input_preprocess_run_id
            or (
                self._preprocess_projection[document_id].active_preprocess_run_id
                if document_id in self._preprocess_projection
                else None
            )
        )
        if not resolved_input_run:
            raise DocumentLayoutConflictError(
                "Layout run creation requires inputPreprocessRunId or an active preprocess projection."
            )
        preprocess_run = self._get_preprocess_run_or_raise(
            document_id=document_id,
            run_id=resolved_input_run,
        )
        if preprocess_run.status != "SUCCEEDED":
            raise DocumentLayoutConflictError(
                "Layout runs require a SUCCEEDED preprocess input run."
            )
        if parent_run_id is not None:
            _ = self._get_layout_run_or_raise(
                document_id=document_id,
                run_id=parent_run_id,
            )
        if supersedes_run_id is not None:
            superseded = self._get_layout_run_or_raise(
                document_id=document_id,
                run_id=supersedes_run_id,
            )
            if superseded.superseded_by_run_id is not None:
                raise DocumentLayoutConflictError(
                    "Superseded layout run is already superseded."
                )

        now = datetime.now(UTC)
        self._layout_run_sequence += 1
        run_id = f"layout-run-{self._layout_run_sequence}"
        run = LayoutRunRecord(
            id=run_id,
            project_id=project_id,
            document_id=document_id,
            input_preprocess_run_id=resolved_input_run,
            run_kind="AUTO",
            parent_run_id=parent_run_id,
            attempt_number=len(runs) + 1,
            superseded_by_run_id=None,
            model_id=model_id,
            profile_id=profile_id,
            params_json=dict(params_json or {}),
            params_hash=f"hash-{run_id}",
            pipeline_version=pipeline_version or "layout-v1",
            container_digest=container_digest or "ukde/layout:v1",
            status="QUEUED",
            created_by=current_user.user_id,
            created_at=now,
            started_at=None,
            finished_at=None,
            failure_reason=None,
        )
        if supersedes_run_id is not None:
            for index, row in enumerate(runs):
                if row.id == supersedes_run_id:
                    runs[index] = replace(row, superseded_by_run_id=run.id)
                    break
        runs.insert(0, run)
        self._layout_pages[run.id] = [
            PageLayoutResultRecord(
                run_id=run.id,
                page_id=page.id,
                page_index=page.page_index,
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
            for page in self._pages.get(document_id, [])
        ]
        return run

    def cancel_layout_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> LayoutRunRecord:
        self._require_layout_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        run = self.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run.status not in {"QUEUED", "RUNNING"}:
            raise DocumentLayoutConflictError(
                "Layout run can be canceled only while QUEUED or RUNNING."
            )
        now = datetime.now(UTC)
        canceled = replace(
            run,
            status="CANCELED",
            finished_at=now,
            failure_reason=f"Canceled by {current_user.user_id}.",
        )
        runs = self._layout_runs.get(document_id, [])
        for index, row in enumerate(runs):
            if row.id == run.id:
                runs[index] = canceled
                break
        self._layout_pages[run.id] = [
            replace(
                page,
                status="CANCELED" if page.status in {"QUEUED", "RUNNING"} else page.status,
                failure_reason=(
                    page.failure_reason
                    if page.failure_reason
                    else "Run canceled before completion."
                ),
                updated_at=now,
            )
            for page in self._layout_pages.get(run.id, [])
        ]
        return canceled

    def activate_layout_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentLayoutProjectionRecord:
        self._require_layout_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        run = self.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        gate = self._build_layout_activation_gate(document_id=document_id, run=run)
        if not gate.eligible:
            first_blocker = gate.blockers[0]
            raise DocumentLayoutConflictError(
                f"Activation is blocked [{first_blocker.code}]: {first_blocker.message}",
                activation_gate=gate,
            )
        downstream_state = gate.downstream_impact.transcription_state_after_activation
        downstream_reason = gate.downstream_impact.reason
        now = datetime.now(UTC)
        projection = DocumentLayoutProjectionRecord(
            document_id=document_id,
            project_id=project_id,
            active_layout_run_id=run.id,
            active_input_preprocess_run_id=run.input_preprocess_run_id,
            downstream_transcription_state=downstream_state,
            downstream_transcription_invalidated_at=(
                now if downstream_state == "STALE" else None
            ),
            downstream_transcription_invalidated_reason=downstream_reason,
            updated_at=now,
        )
        self._layout_projection[document_id] = projection
        self._layout_projection_input_preprocess_run_id[document_id] = (
            run.input_preprocess_run_id
        )
        return projection

    def get_layout_overview(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentLayoutOverviewSnapshot:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        document = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        projection, active_run = self.get_active_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        runs = list(self._layout_runs.get(document_id, []))
        status_counts = {
            "QUEUED": 0,
            "RUNNING": 0,
            "SUCCEEDED": 0,
            "FAILED": 0,
            "CANCELED": 0,
        }
        recall_counts = {
            "COMPLETE": 0,
            "NEEDS_RESCUE": 0,
            "NEEDS_MANUAL_REVIEW": 0,
        }
        pages_with_issues = 0
        region_total = 0
        line_total = 0
        coverage_values: list[float] = []
        structure_values: list[float] = []
        if active_run is not None:
            for row in self._layout_pages.get(active_run.id, []):
                status_counts[row.status] += 1
                recall_counts[row.page_recall_status] += 1
                if (
                    row.page_recall_status != "COMPLETE"
                    or row.status != "SUCCEEDED"
                    or bool(row.failure_reason)
                    or len(row.warnings_json) > 0
                ):
                    pages_with_issues += 1
                region = row.metrics_json.get("region_count")
                if isinstance(region, (int, float)):
                    region_total += int(region)
                line = row.metrics_json.get("line_count")
                if isinstance(line, (int, float)):
                    line_total += int(line)
                coverage = row.metrics_json.get("coverage_percent")
                if isinstance(coverage, (int, float)):
                    coverage_values.append(float(coverage))
                confidence = row.metrics_json.get("structure_confidence")
                if isinstance(confidence, (int, float)):
                    structure_values.append(float(confidence))
        latest_run = (
            self._with_layout_activation_gate(document_id=document_id, run=runs[0])
            if runs
            else None
        )
        return DocumentLayoutOverviewSnapshot(
            document=document,
            projection=projection,
            active_run=active_run,
            latest_run=latest_run,
            total_runs=len(runs),
            page_count=len(self._pages.get(document_id, [])),
            active_status_counts=status_counts,  # type: ignore[arg-type]
            active_recall_counts=recall_counts,  # type: ignore[arg-type]
            summary=DocumentLayoutSummarySnapshot(
                regions_detected=region_total if active_run is not None else None,
                lines_detected=line_total if active_run is not None else None,
                pages_with_issues=pages_with_issues,
                coverage_percent=(
                    sum(coverage_values) / len(coverage_values)
                    if coverage_values
                    else None
                ),
                structure_confidence=(
                    sum(structure_values) / len(structure_values)
                    if structure_values
                    else None
                ),
            ),
        )

    def list_transcription_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        cursor: int = 0,
        page_size: int = 50,
    ) -> tuple[list[TranscriptionRunRecord], int | None]:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        rows = list(self._transcription_runs.get(document_id, []))
        start = max(0, cursor)
        safe_page_size = max(1, min(page_size, 200))
        end = start + safe_page_size
        next_cursor = end if end < len(rows) else None
        return rows[start:end], next_cursor

    def get_transcription_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> TranscriptionRunRecord:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        return self._get_transcription_run_or_raise(
            document_id=document_id,
            run_id=run_id,
        )

    def get_transcription_run_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> TranscriptionRunRecord:
        return self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )

    def get_transcription_projection(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentTranscriptionProjectionRecord | None:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        return self._transcription_projection.get(document_id)

    def get_active_transcription_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> tuple[DocumentTranscriptionProjectionRecord | None, TranscriptionRunRecord | None]:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        projection = self._transcription_projection.get(document_id)
        if projection is None or not projection.active_transcription_run_id:
            return projection, None
        run = self._get_transcription_run_or_raise(
            document_id=document_id,
            run_id=projection.active_transcription_run_id,
        )
        return projection, run

    def create_transcription_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        input_preprocess_run_id: str | None = None,
        input_layout_run_id: str | None = None,
        engine: str | None = None,
        model_id: str | None = None,
        project_model_assignment_id: str | None = None,
        prompt_template_id: str | None = None,
        prompt_template_sha256: str | None = None,
        response_schema_version: int = 1,
        confidence_basis: str | None = None,
        confidence_calibration_version: str | None = None,
        params_json: dict[str, object] | None = None,
        pipeline_version: str | None = None,
        container_digest: str | None = None,
        supersedes_transcription_run_id: str | None = None,
    ) -> TranscriptionRunRecord:
        self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        runs = self._transcription_runs.setdefault(document_id, [])
        resolved_input_preprocess_run_id = (
            input_preprocess_run_id
            or (
                self._preprocess_projection[document_id].active_preprocess_run_id
                if document_id in self._preprocess_projection
                else None
            )
        )
        if not resolved_input_preprocess_run_id:
            raise DocumentTranscriptionConflictError(
                "Transcription run creation requires inputPreprocessRunId or an active preprocess projection."
            )
        preprocess_run = self._get_preprocess_run_or_raise(
            document_id=document_id,
            run_id=resolved_input_preprocess_run_id,
        )
        if preprocess_run.status != "SUCCEEDED":
            raise DocumentTranscriptionConflictError(
                "Transcription runs require a SUCCEEDED preprocess input run."
            )
        resolved_input_layout_run_id = (
            input_layout_run_id
            or (
                self._layout_projection[document_id].active_layout_run_id
                if document_id in self._layout_projection
                else None
            )
        )
        if not resolved_input_layout_run_id:
            raise DocumentTranscriptionConflictError(
                "Transcription run creation requires inputLayoutRunId or an active layout projection."
            )
        layout_run = self._get_layout_run_or_raise(
            document_id=document_id,
            run_id=resolved_input_layout_run_id,
        )
        if layout_run.status != "SUCCEEDED":
            raise DocumentTranscriptionConflictError(
                "Transcription runs require a SUCCEEDED layout input run."
            )
        if supersedes_transcription_run_id is not None:
            superseded = self._get_transcription_run_or_raise(
                document_id=document_id,
                run_id=supersedes_transcription_run_id,
            )
            if superseded.superseded_by_transcription_run_id is not None:
                raise DocumentTranscriptionConflictError(
                    "Superseded transcription run is already superseded."
                )

        now = datetime.now(UTC)
        self._transcription_run_sequence += 1
        run_id = f"transcription-run-{self._transcription_run_sequence}"
        run = TranscriptionRunRecord(
            id=run_id,
            project_id=project_id,
            document_id=document_id,
            input_preprocess_run_id=resolved_input_preprocess_run_id,
            input_layout_run_id=resolved_input_layout_run_id,
            input_layout_snapshot_hash="layout-snap-2",
            engine=(engine or "VLM_LINE_CONTEXT"),  # type: ignore[arg-type]
            model_id=(model_id or "model-transcription-primary-qwen2.5-vl-3b-instruct"),
            project_model_assignment_id=project_model_assignment_id,
            prompt_template_id=prompt_template_id,
            prompt_template_sha256=prompt_template_sha256,
            response_schema_version=max(1, int(response_schema_version)),
            confidence_basis=(confidence_basis or "MODEL_NATIVE"),  # type: ignore[arg-type]
            confidence_calibration_version=confidence_calibration_version or "v1",
            params_json=dict(params_json or {}),
            pipeline_version=pipeline_version or "transcription-v1",
            container_digest=container_digest or "ukde/transcription:v1",
            attempt_number=len(runs) + 1,
            supersedes_transcription_run_id=supersedes_transcription_run_id,
            superseded_by_transcription_run_id=None,
            status="QUEUED",
            created_by=current_user.user_id,
            created_at=now,
            started_at=None,
            finished_at=None,
            canceled_by=None,
            canceled_at=None,
            failure_reason=None,
        )
        if supersedes_transcription_run_id is not None:
            for index, row in enumerate(runs):
                if row.id == supersedes_transcription_run_id:
                    runs[index] = replace(
                        row,
                        superseded_by_transcription_run_id=run.id,
                    )
                    break
        runs.insert(0, run)
        self._transcription_pages[run.id] = [
            PageTranscriptionResultRecord(
                run_id=run.id,
                page_id=page.id,
                page_index=page.page_index,
                status="QUEUED",
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
            for page in self._pages.get(document_id, [])
        ]
        return run

    def create_fallback_transcription_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        base_run_id: str | None = None,
        engine: str | None = None,
        model_id: str | None = None,
        project_model_assignment_id: str | None = None,
        prompt_template_id: str | None = None,
        prompt_template_sha256: str | None = None,
        response_schema_version: int = 1,
        confidence_calibration_version: str | None = None,
        params_json: dict[str, object] | None = None,
        pipeline_version: str | None = None,
        container_digest: str | None = None,
        fallback_reason_codes: list[str] | None = None,
        fallback_confidence_threshold: float | None = None,
    ) -> tuple[TranscriptionRunRecord, list[str]]:
        self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        resolved_engine = (engine or "KRAKEN_LINE").strip().upper()
        if resolved_engine not in {"KRAKEN_LINE", "TROCR_LINE", "DAN_PAGE"}:
            raise DocumentTranscriptionConflictError(
                "Fallback run creation requires a fallback engine."
            )
        if resolved_engine in {"TROCR_LINE", "DAN_PAGE"} and not project_model_assignment_id:
            raise DocumentTranscriptionConflictError(
                "TROCR_LINE and DAN_PAGE remain disabled until an ACTIVE TRANSCRIPTION_FALLBACK assignment is configured."
            )
        runs = self._transcription_runs.get(document_id, [])
        if not runs:
            raise DocumentTranscriptionRunNotFoundError(
                "Fallback run creation requires a base transcription run."
            )
        resolved_base = (
            self._get_transcription_run_or_raise(
                document_id=document_id, run_id=base_run_id
            )
            if base_run_id
            else runs[0]
        )
        threshold = (
            fallback_confidence_threshold
            if isinstance(fallback_confidence_threshold, (int, float))
            else 0.72
        )
        inferred_reasons: list[str] = []
        for page in self._transcription_pages.get(resolved_base.id, []):
            lines = self._transcription_lines.get((resolved_base.id, page.page_id), [])
            if any(line.schema_validation_status == "INVALID" for line in lines):
                inferred_reasons.append("SCHEMA_VALIDATION_FAILED")
            if any(line.token_anchor_status != "CURRENT" for line in lines):
                inferred_reasons.append("ANCHOR_RESOLUTION_FAILED")
            if any(
                isinstance(line.conf_line, float) and line.conf_line < threshold
                for line in lines
            ):
                inferred_reasons.append("CONFIDENCE_BELOW_THRESHOLD")
        deduped_reasons = []
        for code in fallback_reason_codes or inferred_reasons:
            normalized = code.strip().upper()
            if normalized and normalized not in deduped_reasons:
                deduped_reasons.append(normalized)
        if not deduped_reasons:
            raise DocumentTranscriptionConflictError(
                "Fallback run creation is gated: no fallback trigger conditions were detected."
            )
        merged_params = dict(params_json or {})
        merged_params["fallback_invocation"] = {
            "base_run_id": resolved_base.id,
            "reason_codes": deduped_reasons,
            "confidence_threshold": threshold,
        }
        run = self.create_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            input_preprocess_run_id=resolved_base.input_preprocess_run_id,
            input_layout_run_id=resolved_base.input_layout_run_id,
            engine=resolved_engine,
            model_id=model_id,
            project_model_assignment_id=project_model_assignment_id,
            prompt_template_id=prompt_template_id,
            prompt_template_sha256=prompt_template_sha256,
            response_schema_version=response_schema_version,
            confidence_basis="FALLBACK_DISAGREEMENT",
            confidence_calibration_version=confidence_calibration_version,
            params_json=merged_params,
            pipeline_version=pipeline_version,
            container_digest=container_digest,
            supersedes_transcription_run_id=None,
        )
        return run, deduped_reasons

    def compare_transcription_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        base_run_id: str,
        candidate_run_id: str,
        page_number: int | None = None,
        line_id: str | None = None,
        token_id: str | None = None,
    ) -> DocumentTranscriptionCompareSnapshot:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        document = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        base_run = self._get_transcription_run_or_raise(
            document_id=document_id,
            run_id=base_run_id,
        )
        candidate_run = self._get_transcription_run_or_raise(
            document_id=document_id,
            run_id=candidate_run_id,
        )
        if (
            base_run.input_preprocess_run_id != candidate_run.input_preprocess_run_id
            or base_run.input_layout_run_id != candidate_run.input_layout_run_id
            or base_run.input_layout_snapshot_hash
            != candidate_run.input_layout_snapshot_hash
        ):
            raise DocumentTranscriptionConflictError(
                "Compare requires base and candidate runs to share preprocess/layout basis and layout snapshot hash."
            )
        base_pages = {row.page_id: row for row in self._transcription_pages.get(base_run.id, [])}
        candidate_pages = {
            row.page_id: row for row in self._transcription_pages.get(candidate_run.id, [])
        }
        page_ids = sorted(set(base_pages) | set(candidate_pages))
        selected_page_ids: set[str] | None = None
        if isinstance(page_number, int):
            if page_number < 1:
                raise DocumentValidationError("page must be 1 or greater.")
            selected_page_ids = {
                page_id
                for page_id in page_ids
                if (
                    (
                        base_pages.get(page_id).page_index
                        if base_pages.get(page_id) is not None
                        else candidate_pages.get(page_id).page_index
                    )
                    + 1
                    == page_number
                )
            }
            if not selected_page_ids:
                raise DocumentPageNotFoundError(
                    "Compared page target was not found for selected runs."
                )

        normalized_line_id = line_id.strip() if isinstance(line_id, str) and line_id.strip() else None
        normalized_token_id = token_id.strip() if isinstance(token_id, str) and token_id.strip() else None

        decisions = [
            item
            for item in self._transcription_compare_decisions
            if item.base_run_id == base_run_id and item.candidate_run_id == candidate_run_id
        ]
        if selected_page_ids is not None:
            decisions = [item for item in decisions if item.page_id in selected_page_ids]
        if normalized_line_id is not None:
            decisions = [item for item in decisions if item.line_id == normalized_line_id]
        if normalized_token_id is not None:
            decisions = [item for item in decisions if item.token_id == normalized_token_id]
        decision_index = {
            (item.page_id, item.line_id, item.token_id): item for item in decisions
        }
        decision_events = [
            item
            for item in self._transcription_compare_decision_events
            if item.base_run_id == base_run_id and item.candidate_run_id == candidate_run_id
        ]
        if selected_page_ids is not None:
            decision_events = [
                item for item in decision_events if item.page_id in selected_page_ids
            ]
        if normalized_line_id is not None:
            decision_events = [
                item for item in decision_events if item.line_id == normalized_line_id
            ]
        if normalized_token_id is not None:
            decision_events = [
                item for item in decision_events if item.token_id == normalized_token_id
            ]
        pages: list[DocumentTranscriptionComparePageSnapshot] = []
        changed_lines = 0
        changed_tokens = 0
        changed_confidence = 0
        matched_line_filter = normalized_line_id is None
        matched_token_filter = normalized_token_id is None
        for page_id in page_ids:
            if selected_page_ids is not None and page_id not in selected_page_ids:
                continue
            base_page = base_pages.get(page_id)
            candidate_page = candidate_pages.get(page_id)
            page_index = (
                base_page.page_index
                if base_page is not None
                else candidate_page.page_index if candidate_page is not None else 0
            )
            base_lines = {
                row.line_id: row
                for row in self._transcription_lines.get((base_run.id, page_id), [])
            }
            candidate_lines = {
                row.line_id: row
                for row in self._transcription_lines.get((candidate_run.id, page_id), [])
            }
            line_ids = sorted(set(base_lines) | set(candidate_lines))
            if normalized_line_id is not None:
                line_ids = [item for item in line_ids if item == normalized_line_id]
            if not line_ids and normalized_line_id is not None:
                continue
            line_diffs: list[DocumentTranscriptionCompareLineDiffSnapshot] = []
            for line_id in line_ids:
                matched_line_filter = True
                base_line = base_lines.get(line_id)
                candidate_line = candidate_lines.get(line_id)
                confidence_delta = (
                    round(candidate_line.conf_line - base_line.conf_line, 6)
                    if (
                        base_line is not None
                        and candidate_line is not None
                        and isinstance(base_line.conf_line, float)
                        and isinstance(candidate_line.conf_line, float)
                    )
                    else None
                )
                changed = (
                    base_line is None
                    or candidate_line is None
                    or base_line.text_diplomatic != candidate_line.text_diplomatic
                    or confidence_delta is not None
                )
                if changed:
                    changed_lines += 1
                if confidence_delta is not None:
                    changed_confidence += 1
                decision = decision_index.get((page_id, line_id, None))
                line_diffs.append(
                    DocumentTranscriptionCompareLineDiffSnapshot(
                        line_id=line_id,
                        base_line=base_line,
                        candidate_line=candidate_line,
                        changed=changed,
                        confidence_delta=confidence_delta,
                        current_decision=decision,
                    )
                )
            base_tokens = {
                row.token_id: row
                for row in self._transcription_tokens.get((base_run.id, page_id), [])
            }
            candidate_tokens = {
                row.token_id: row
                for row in self._transcription_tokens.get((candidate_run.id, page_id), [])
            }
            token_ids = sorted(set(base_tokens) | set(candidate_tokens))
            if normalized_token_id is not None:
                token_ids = [item for item in token_ids if item == normalized_token_id]
            if not token_ids and normalized_token_id is not None:
                continue
            token_diffs: list[DocumentTranscriptionCompareTokenDiffSnapshot] = []
            for token_id in token_ids:
                matched_token_filter = True
                base_token = base_tokens.get(token_id)
                candidate_token = candidate_tokens.get(token_id)
                confidence_delta = (
                    round(candidate_token.token_confidence - base_token.token_confidence, 6)
                    if (
                        base_token is not None
                        and candidate_token is not None
                        and isinstance(base_token.token_confidence, float)
                        and isinstance(candidate_token.token_confidence, float)
                    )
                    else None
                )
                changed = (
                    base_token is None
                    or candidate_token is None
                    or base_token.token_text != candidate_token.token_text
                    or confidence_delta is not None
                )
                if changed:
                    changed_tokens += 1
                line_id = (
                    base_token.line_id
                    if base_token is not None
                    else candidate_token.line_id if candidate_token is not None else None
                )
                if normalized_line_id is not None and line_id != normalized_line_id:
                    continue
                decision = decision_index.get((page_id, line_id, token_id))
                token_diffs.append(
                    DocumentTranscriptionCompareTokenDiffSnapshot(
                        token_id=token_id,
                        token_index=(
                            base_token.token_index
                            if base_token is not None
                            else candidate_token.token_index
                            if candidate_token is not None
                            else None
                        ),
                        line_id=line_id,
                        base_token=base_token,
                        candidate_token=candidate_token,
                        changed=changed,
                        confidence_delta=confidence_delta,
                        current_decision=decision,
                    )
                )
            if (
                (normalized_line_id is not None or normalized_token_id is not None)
                and not line_diffs
                and not token_diffs
            ):
                continue
            pages.append(
                DocumentTranscriptionComparePageSnapshot(
                    page_id=page_id,
                    page_index=page_index,
                    base_page=base_page,
                    candidate_page=candidate_page,
                    line_diffs=line_diffs,
                    token_diffs=token_diffs,
                    changed_line_count=sum(1 for row in line_diffs if row.changed),
                    changed_token_count=sum(1 for row in token_diffs if row.changed),
                    changed_confidence_count=sum(
                        1 for row in line_diffs if row.confidence_delta is not None
                    ),
                    output_availability={
                        "basePageXml": bool(base_page and base_page.pagexml_out_key),
                        "baseRawResponse": bool(
                            base_page and base_page.raw_model_response_sha256
                        ),
                        "baseHocr": bool(base_page and base_page.hocr_out_key),
                        "candidatePageXml": bool(
                            candidate_page and candidate_page.pagexml_out_key
                        ),
                        "candidateRawResponse": bool(
                            candidate_page and candidate_page.raw_model_response_sha256
                        ),
                        "candidateHocr": bool(
                            candidate_page and candidate_page.hocr_out_key
                        ),
                    },
                )
            )
        if not matched_line_filter:
            raise DocumentPageNotFoundError("Compared line target was not found.")
        if not matched_token_filter:
            raise DocumentPageNotFoundError("Compared token target was not found.")
        decision_snapshot_hash = hashlib.sha256(
            (
                "|".join(sorted(item.id for item in decisions))
                + "||"
                + "|".join(sorted(item.id for item in decision_events))
            ).encode("utf-8")
        ).hexdigest()
        return DocumentTranscriptionCompareSnapshot(
            document=document,
            base_run=base_run,
            candidate_run=candidate_run,
            pages=pages,
            changed_line_count=changed_lines,
            changed_token_count=changed_tokens,
            changed_confidence_count=changed_confidence,
            base_engine_metadata={
                "engine": base_run.engine,
                "modelId": base_run.model_id,
                "runId": base_run.id,
            },
            candidate_engine_metadata={
                "engine": candidate_run.engine,
                "modelId": candidate_run.model_id,
                "runId": candidate_run.id,
            },
            compare_decision_snapshot_hash=decision_snapshot_hash,
            compare_decision_count=len(decisions),
            compare_decision_event_count=len(decision_events),
        )

    def record_transcription_compare_decisions(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        base_run_id: str,
        candidate_run_id: str,
        items: list[dict[str, object]],
    ) -> list[TranscriptionCompareDecisionRecord]:
        self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.compare_transcription_runs(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            base_run_id=base_run_id,
            candidate_run_id=candidate_run_id,
        )
        persisted: list[TranscriptionCompareDecisionRecord] = []
        for item in items:
            page_id = str(item.get("pageId") or "").strip()
            if not page_id:
                raise DocumentValidationError("Compare decision item requires pageId.")
            line_id = (
                str(item.get("lineId")).strip()
                if isinstance(item.get("lineId"), str) and str(item.get("lineId")).strip()
                else None
            )
            token_id = (
                str(item.get("tokenId")).strip()
                if isinstance(item.get("tokenId"), str) and str(item.get("tokenId")).strip()
                else None
            )
            decision = str(item.get("decision") or "").strip().upper()
            if decision not in {"KEEP_BASE", "PROMOTE_CANDIDATE"}:
                raise DocumentValidationError(
                    "decision must be KEEP_BASE or PROMOTE_CANDIDATE."
                )
            decision_reason = (
                str(item.get("decisionReason")).strip()
                if isinstance(item.get("decisionReason"), str)
                and str(item.get("decisionReason")).strip()
                else None
            )
            decision_etag = (
                str(item.get("decisionEtag")).strip()
                if isinstance(item.get("decisionEtag"), str)
                and str(item.get("decisionEtag")).strip()
                else None
            )
            existing = None
            for row in self._transcription_compare_decisions:
                if (
                    row.document_id == document_id
                    and row.base_run_id == base_run_id
                    and row.candidate_run_id == candidate_run_id
                    and row.page_id == page_id
                    and row.line_id == line_id
                    and row.token_id == token_id
                ):
                    existing = row
                    break
            now = datetime.now(UTC)
            if existing is None:
                if decision_etag is not None:
                    raise DocumentTranscriptionConflictError(
                        "decisionEtag cannot be provided for a new compare decision."
                    )
                event_time = now
                created = TranscriptionCompareDecisionRecord(
                    id=f"cmp-decision-{len(self._transcription_compare_decisions) + 1}",
                    document_id=document_id,
                    base_run_id=base_run_id,
                    candidate_run_id=candidate_run_id,
                    page_id=page_id,
                    line_id=line_id,
                    token_id=token_id,
                    decision=decision,  # type: ignore[arg-type]
                    decision_etag=hashlib.sha256(
                        f"{document_id}|{base_run_id}|{candidate_run_id}|{page_id}|{line_id}|{token_id}|{now.isoformat()}".encode(
                            "utf-8"
                        )
                    ).hexdigest(),
                    decided_by=current_user.user_id,
                    decided_at=now,
                    decision_reason=decision_reason,
                    created_at=now,
                    updated_at=now,
                )
                self._transcription_compare_decisions.append(created)
                self._transcription_compare_decision_events.append(
                    TranscriptionCompareDecisionEventRecord(
                        id=f"cmp-event-{len(self._transcription_compare_decision_events) + 1}",
                        decision_id=created.id,
                        document_id=document_id,
                        base_run_id=base_run_id,
                        candidate_run_id=candidate_run_id,
                        page_id=page_id,
                        line_id=line_id,
                        token_id=token_id,
                        from_decision=None,
                        to_decision=decision,  # type: ignore[arg-type]
                        actor_user_id=current_user.user_id,
                        reason=decision_reason,
                        created_at=event_time,
                    )
                )
                persisted.append(created)
                continue
            if decision_etag is None or decision_etag != existing.decision_etag:
                raise DocumentTranscriptionConflictError(
                    "decisionEtag is stale for this compare decision target."
                )
            event_time = now
            updated = replace(
                existing,
                decision=decision,  # type: ignore[arg-type]
                decision_etag=hashlib.sha256(
                    f"{existing.id}|{decision}|{now.isoformat()}".encode("utf-8")
                ).hexdigest(),
                decided_by=current_user.user_id,
                decided_at=now,
                decision_reason=decision_reason,
                updated_at=now,
            )
            self._transcription_compare_decisions = [
                updated if row.id == existing.id else row
                for row in self._transcription_compare_decisions
            ]
            self._transcription_compare_decision_events.append(
                TranscriptionCompareDecisionEventRecord(
                    id=f"cmp-event-{len(self._transcription_compare_decision_events) + 1}",
                    decision_id=existing.id,
                    document_id=document_id,
                    base_run_id=base_run_id,
                    candidate_run_id=candidate_run_id,
                    page_id=page_id,
                    line_id=line_id,
                    token_id=token_id,
                    from_decision=existing.decision,
                    to_decision=decision,  # type: ignore[arg-type]
                    actor_user_id=current_user.user_id,
                    reason=decision_reason,
                    created_at=event_time,
                )
            )
            persisted.append(updated)
        return persisted

    def finalize_transcription_compare(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        base_run_id: str,
        candidate_run_id: str,
        page_ids: list[str] | None = None,
        expected_compare_decision_snapshot_hash: str | None = None,
    ) -> DocumentTranscriptionCompareFinalizeSnapshot:
        self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        compare_snapshot = self.compare_transcription_runs(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            base_run_id=base_run_id,
            candidate_run_id=candidate_run_id,
            page_number=None,
            line_id=None,
            token_id=None,
        )
        decisions = [
            item
            for item in self._transcription_compare_decisions
            if item.base_run_id == base_run_id and item.candidate_run_id == candidate_run_id
        ]
        normalized_page_ids = sorted(
            {
                item.strip()
                for item in (page_ids or [])
                if isinstance(item, str) and item.strip()
            }
        )
        if normalized_page_ids:
            decisions = [item for item in decisions if item.page_id in normalized_page_ids]
        if not decisions:
            raise DocumentTranscriptionConflictError(
                "Compare finalization requires at least one explicit compare decision."
            )
        if (
            isinstance(expected_compare_decision_snapshot_hash, str)
            and expected_compare_decision_snapshot_hash.strip()
            and expected_compare_decision_snapshot_hash.strip()
            != compare_snapshot.compare_decision_snapshot_hash
        ):
            raise DocumentTranscriptionConflictError(
                "Compare decision snapshot is stale; refresh compare before finalizing."
            )

        now = datetime.now(UTC)
        self._transcription_run_sequence += 1
        new_run_id = f"transcription-run-{self._transcription_run_sequence}"
        base_run = self._get_transcription_run_or_raise(
            document_id=document_id, run_id=base_run_id
        )
        candidate_run = self._get_transcription_run_or_raise(
            document_id=document_id, run_id=candidate_run_id
        )
        composed_run = TranscriptionRunRecord(
            id=new_run_id,
            project_id=project_id,
            document_id=document_id,
            input_preprocess_run_id=base_run.input_preprocess_run_id,
            input_layout_run_id=base_run.input_layout_run_id,
            input_layout_snapshot_hash=base_run.input_layout_snapshot_hash,
            engine="REVIEW_COMPOSED",
            model_id=base_run.model_id,
            project_model_assignment_id=None,
            prompt_template_id=None,
            prompt_template_sha256=None,
            response_schema_version=base_run.response_schema_version,
            confidence_basis="READ_AGREEMENT",
            confidence_calibration_version=base_run.confidence_calibration_version,
            params_json={
                **dict(base_run.params_json),
                "baseRunId": base_run_id,
                "candidateRunId": candidate_run_id,
                "compareDecisionSnapshotHash": compare_snapshot.compare_decision_snapshot_hash,
                "pageScope": normalized_page_ids,
                "finalizedBy": current_user.user_id,
                "finalizedAt": now.isoformat(),
            },
            pipeline_version=base_run.pipeline_version,
            container_digest=base_run.container_digest,
            attempt_number=max(
                (item.attempt_number for item in self._transcription_runs.get(document_id, [])),
                default=0,
            )
            + 1,
            supersedes_transcription_run_id=None,
            superseded_by_transcription_run_id=None,
            status="SUCCEEDED",
            created_by=current_user.user_id,
            created_at=now,
            started_at=now,
            finished_at=now,
            canceled_by=None,
            canceled_at=None,
            failure_reason=None,
        )
        self._transcription_runs.setdefault(document_id, []).insert(0, composed_run)

        pages = []
        base_pages = {item.page_id: item for item in self._transcription_pages.get(base_run_id, [])}
        candidate_pages = {
            item.page_id: item for item in self._transcription_pages.get(candidate_run_id, [])
        }
        for page_id in sorted(set(base_pages) | set(candidate_pages)):
            if normalized_page_ids and page_id not in normalized_page_ids:
                continue
            source_page = candidate_pages.get(page_id) or base_pages.get(page_id)
            if source_page is None:
                continue
            pages.append(
                replace(
                    source_page,
                    run_id=new_run_id,
                    status="SUCCEEDED",
                    pagexml_out_key=(
                        f"controlled/derived/{project_id}/{document_id}/transcription/"
                        f"{new_run_id}/{page_id}/page.xml"
                    ),
                    pagexml_out_sha256=f"sha-{new_run_id}-{page_id}",
                    raw_model_response_key=(
                        f"controlled/derived/{project_id}/{document_id}/transcription/"
                        f"{new_run_id}/{page_id}/model-response.json"
                    ),
                    raw_model_response_sha256=f"sha-raw-{new_run_id}-{page_id}",
                    created_at=now,
                    updated_at=now,
                )
            )
        self._transcription_pages[new_run_id] = pages

        decision_index = {
            (item.page_id, item.line_id, item.token_id): item for item in decisions
        }
        for page in pages:
            base_lines = list(self._transcription_lines.get((base_run_id, page.page_id), []))
            candidate_lines = {
                item.line_id: item
                for item in self._transcription_lines.get((candidate_run_id, page.page_id), [])
            }
            composed_lines: list[LineTranscriptionResultRecord] = []
            for line in base_lines:
                decision = decision_index.get((page.page_id, line.line_id, None))
                source_line = (
                    candidate_lines.get(line.line_id)
                    if decision is not None
                    and decision.decision == "PROMOTE_CANDIDATE"
                    and candidate_lines.get(line.line_id) is not None
                    else line
                )
                composed_lines.append(
                    replace(
                        source_line,
                        run_id=new_run_id,
                        page_id=page.page_id,
                        active_transcript_version_id=None,
                        version_etag=f"{source_line.version_etag}-composed",
                        created_at=now,
                        updated_at=now,
                    )
                )
            self._transcription_lines[(new_run_id, page.page_id)] = composed_lines

            base_tokens = list(self._transcription_tokens.get((base_run_id, page.page_id), []))
            candidate_tokens = {
                item.token_id: item
                for item in self._transcription_tokens.get((candidate_run_id, page.page_id), [])
            }
            composed_tokens: list[TokenTranscriptionResultRecord] = []
            for token in base_tokens:
                decision = decision_index.get((page.page_id, token.line_id, token.token_id))
                source_token = (
                    candidate_tokens.get(token.token_id)
                    if decision is not None
                    and decision.decision == "PROMOTE_CANDIDATE"
                    and candidate_tokens.get(token.token_id) is not None
                    else token
                )
                composed_tokens.append(
                    replace(
                        source_token,
                        run_id=new_run_id,
                        page_id=page.page_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
            self._transcription_tokens[(new_run_id, page.page_id)] = composed_tokens

        document = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        return DocumentTranscriptionCompareFinalizeSnapshot(
            document=document,
            base_run=base_run,
            candidate_run=candidate_run,
            composed_run=composed_run,
            compare_decision_snapshot_hash=compare_snapshot.compare_decision_snapshot_hash,
            page_scope=tuple(normalized_page_ids),
        )

    def cancel_transcription_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> TranscriptionRunRecord:
        self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        run = self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run.status not in {"QUEUED", "RUNNING"}:
            raise DocumentTranscriptionConflictError(
                "Transcription run can be canceled only while QUEUED or RUNNING."
            )
        now = datetime.now(UTC)
        canceled = replace(
            run,
            status="CANCELED",
            canceled_by=current_user.user_id,
            canceled_at=now,
            finished_at=now,
            failure_reason=f"Canceled by {current_user.user_id}.",
        )
        runs = self._transcription_runs.get(document_id, [])
        for index, row in enumerate(runs):
            if row.id == run.id:
                runs[index] = canceled
                break
        self._transcription_pages[run.id] = [
            replace(
                page,
                status="CANCELED" if page.status in {"QUEUED", "RUNNING"} else page.status,
                failure_reason=(
                    page.failure_reason
                    if page.failure_reason
                    else "Run canceled before completion."
                ),
                updated_at=now,
            )
            for page in self._transcription_pages.get(run.id, [])
        ]
        return canceled

    def activate_transcription_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentTranscriptionProjectionRecord:
        self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        run = self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run.status != "SUCCEEDED":
            raise DocumentTranscriptionConflictError(
                "Only SUCCEEDED transcription runs can be activated."
            )
        layout_projection = self._layout_projection.get(document_id)
        if layout_projection is None or not layout_projection.active_layout_run_id:
            raise DocumentTranscriptionConflictError(
                "Activation requires an active layout projection."
            )
        if layout_projection.active_layout_run_id != run.input_layout_run_id:
            raise DocumentTranscriptionConflictError(
                "Transcription run layout basis is stale against active layout projection."
            )
        if (
            layout_projection.active_layout_snapshot_hash
            and layout_projection.active_layout_snapshot_hash
            != run.input_layout_snapshot_hash
        ):
            raise DocumentTranscriptionConflictError(
                "Transcription run snapshot hash no longer matches active layout basis."
            )
        rescue_status = self.get_transcription_run_rescue_status(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if not rescue_status.ready_for_activation:
            blocked_pages = [
                row.page_index + 1
                for row in rescue_status.pages
                if row.blocker_reason_codes
            ]
            conflict = DocumentTranscriptionConflictError(
                "RESCUE_UNRESOLVED: Activation requires resolved rescue/manual-review readiness before promotion."
            )
            setattr(conflict, "rescue_status", rescue_status)
            setattr(conflict, "blocker_codes", tuple(rescue_status.run_blocker_reason_codes))
            if blocked_pages:
                raise conflict
            raise conflict
        layout_rows = list(self._layout_pages.get(run.input_layout_run_id, []))
        required_pages = [
            row for row in layout_rows if row.page_recall_status != "NEEDS_MANUAL_REVIEW"
        ]
        for page_row in required_pages:
            page_tokens = self._transcription_tokens.get((run.id, page_row.page_id), [])
            if len(page_tokens) == 0:
                conflict = DocumentTranscriptionConflictError(
                    "Activation requires token anchors for all eligible pages; "
                    f"missing anchors on page {page_row.page_index + 1}."
                )
                setattr(conflict, "blocker_codes", ("TOKEN_ANCHOR_MISSING",))
                raise conflict
            page_lines = self._transcription_lines.get((run.id, page_row.page_id), [])
            if any(line.token_anchor_status != "CURRENT" for line in page_lines):
                conflict = DocumentTranscriptionConflictError(
                    "Activation requires CURRENT token-anchor status for all eligible lines."
                )
                setattr(conflict, "blocker_codes", ("TOKEN_ANCHOR_STALE",))
                raise conflict
        projection = DocumentTranscriptionProjectionRecord(
            document_id=document_id,
            project_id=project_id,
            active_transcription_run_id=run.id,
            active_layout_run_id=run.input_layout_run_id,
            active_layout_snapshot_hash=run.input_layout_snapshot_hash,
            active_preprocess_run_id=run.input_preprocess_run_id,
            downstream_redaction_state="NOT_STARTED",
            downstream_redaction_invalidated_at=None,
            downstream_redaction_invalidated_reason=None,
            updated_at=datetime.now(UTC),
        )
        self._transcription_projection[document_id] = projection
        self._transcription_projection_preprocess_run_id[document_id] = (
            run.input_preprocess_run_id
        )
        return projection

    @staticmethod
    def _is_manual_override_resolution(resolution: dict[str, object] | None) -> bool:
        if not isinstance(resolution, dict):
            return False
        return resolution.get("resolution_status") == "MANUAL_REVIEW_RESOLVED"

    def _build_transcription_page_rescue_status(
        self,
        *,
        run: TranscriptionRunRecord,
        page_row: PageLayoutResultRecord,
    ) -> DocumentTranscriptionRescuePageStatusSnapshot:
        candidates = list(
            self._layout_rescue_candidates.get((run.input_layout_run_id, page_row.page_id), [])
        )
        tokens = list(self._transcription_tokens.get((run.id, page_row.page_id), []))
        page_transcription = next(
            (
                row
                for row in self._transcription_pages.get(run.id, [])
                if row.page_id == page_row.page_id
            ),
            None,
        )
        resolution = self._transcription_rescue_resolutions.get((run.id, page_row.page_id))
        manual_override = self._is_manual_override_resolution(resolution)

        eligible = [item for item in candidates if item.status in {"ACCEPTED", "RESOLVED"}]
        rescue_source_count = len(eligible)
        rescue_transcribed_source_count = 0
        for candidate in eligible:
            source_kind = (
                "RESCUE_CANDIDATE"
                if candidate.candidate_kind == "LINE_EXPANSION"
                else "PAGE_WINDOW"
            )
            if any(
                token.source_kind == source_kind and token.source_ref_id == candidate.id
                for token in tokens
            ):
                rescue_transcribed_source_count += 1
        rescue_unresolved_source_count = max(
            0, rescue_source_count - rescue_transcribed_source_count
        )
        blocker_reason_codes: list[str] = []
        if page_transcription is None or page_transcription.status != "SUCCEEDED":
            blocker_reason_codes.append("PAGE_TRANSCRIPTION_NOT_SUCCEEDED")
        if page_row.page_recall_status == "NEEDS_RESCUE":
            if rescue_source_count <= 0 and not manual_override:
                blocker_reason_codes.append("RESCUE_SOURCE_MISSING")
            elif rescue_unresolved_source_count > 0 and not manual_override:
                blocker_reason_codes.append("RESCUE_SOURCE_UNTRANSCRIBED")
        if (
            page_row.page_recall_status == "NEEDS_MANUAL_REVIEW"
            and not manual_override
        ):
            blocker_reason_codes.append("MANUAL_REVIEW_RESOLUTION_REQUIRED")
        deduped_codes = tuple(dict.fromkeys(blocker_reason_codes))
        if not deduped_codes:
            readiness_state = "READY"
        elif "MANUAL_REVIEW_RESOLUTION_REQUIRED" in deduped_codes:
            readiness_state = "BLOCKED_MANUAL_REVIEW"
        elif any(
            code in {"RESCUE_SOURCE_MISSING", "RESCUE_SOURCE_UNTRANSCRIBED"}
            for code in deduped_codes
        ):
            readiness_state = "BLOCKED_RESCUE"
        else:
            readiness_state = "BLOCKED_PAGE_STATUS"

        return DocumentTranscriptionRescuePageStatusSnapshot(
            run_id=run.id,
            page_id=page_row.page_id,
            page_index=page_row.page_index,
            page_recall_status=page_row.page_recall_status,
            rescue_source_count=rescue_source_count,
            rescue_transcribed_source_count=rescue_transcribed_source_count,
            rescue_unresolved_source_count=rescue_unresolved_source_count,
            readiness_state=readiness_state,
            blocker_reason_codes=deduped_codes,  # type: ignore[arg-type]
            resolution_status=(
                resolution.get("resolution_status")
                if isinstance(resolution, dict)
                else None
            ),  # type: ignore[arg-type]
            resolution_reason=(
                resolution.get("resolution_reason")
                if isinstance(resolution, dict)
                else None
            ),  # type: ignore[arg-type]
            resolution_updated_by=(
                resolution.get("updated_by")
                if isinstance(resolution, dict)
                else None
            ),  # type: ignore[arg-type]
            resolution_updated_at=(
                resolution.get("updated_at")
                if isinstance(resolution, dict)
                else None
            ),  # type: ignore[arg-type]
        )

    def get_transcription_run_rescue_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentTranscriptionRunRescueStatusSnapshot:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        document = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        run = self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        layout_rows = list(self._layout_pages.get(run.input_layout_run_id, []))
        page_snapshots = tuple(
            self._build_transcription_page_rescue_status(run=run, page_row=row)
            for row in layout_rows
        )
        run_blocker_reason_codes: list[str] = []
        if run.status != "SUCCEEDED":
            run_blocker_reason_codes.append("RUN_NOT_SUCCEEDED")
        for row in page_snapshots:
            run_blocker_reason_codes.extend(row.blocker_reason_codes)
        deduped = tuple(dict.fromkeys(run_blocker_reason_codes))
        return DocumentTranscriptionRunRescueStatusSnapshot(
            document=document,
            run=run,
            ready_for_activation=len(deduped) == 0,
            blocker_count=len(deduped) + sum(1 for row in page_snapshots if row.blocker_reason_codes),
            run_blocker_reason_codes=deduped,  # type: ignore[arg-type]
            pages=page_snapshots,
        )

    def list_transcription_run_page_rescue_sources(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> DocumentTranscriptionPageRescueSourcesSnapshot:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        document = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        run = self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        layout_row = next(
            (
                row
                for row in self._layout_pages.get(run.input_layout_run_id, [])
                if row.page_id == page_id
            ),
            None,
        )
        if layout_row is None:
            raise DocumentPageNotFoundError("Layout page result backing this run was not found.")
        page_status = self._build_transcription_page_rescue_status(
            run=run,
            page_row=layout_row,
        )
        tokens = list(self._transcription_tokens.get((run.id, page_id), []))
        rescue_sources: list[DocumentTranscriptionRescueSourceSnapshot] = []
        for candidate in self._layout_rescue_candidates.get((run.input_layout_run_id, page_id), []):
            source_kind = (
                "RESCUE_CANDIDATE"
                if candidate.candidate_kind == "LINE_EXPANSION"
                else "PAGE_WINDOW"
            )
            token_count = sum(
                1
                for token in tokens
                if token.source_kind == source_kind and token.source_ref_id == candidate.id
            )
            rescue_sources.append(
                DocumentTranscriptionRescueSourceSnapshot(
                    source_ref_id=candidate.id,
                    source_kind=source_kind,  # type: ignore[arg-type]
                    candidate_kind=candidate.candidate_kind,
                    candidate_status=candidate.status,
                    token_count=token_count,
                    has_transcription_output=token_count > 0,
                    confidence=candidate.confidence,
                    source_signal=candidate.source_signal,
                    geometry_json=dict(candidate.geometry_json),
                )
            )
        return DocumentTranscriptionPageRescueSourcesSnapshot(
            document=document,
            run=run,
            page=page,
            page_recall_status=page_status.page_recall_status,
            readiness_state=page_status.readiness_state,
            blocker_reason_codes=page_status.blocker_reason_codes,
            rescue_sources=tuple(rescue_sources),
            resolution_status=page_status.resolution_status,
            resolution_reason=page_status.resolution_reason,
            resolution_updated_by=page_status.resolution_updated_by,
            resolution_updated_at=page_status.resolution_updated_at,
        )

    def update_transcription_page_rescue_resolution(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        resolution_status: str,
        resolution_reason: str | None = None,
    ) -> DocumentTranscriptionPageRescueSourcesSnapshot:
        self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        if resolution_status not in {"RESCUE_VERIFIED", "MANUAL_REVIEW_RESOLVED"}:
            raise DocumentValidationError("resolutionStatus is invalid.")
        run = self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        layout_row = next(
            (
                row
                for row in self._layout_pages.get(run.input_layout_run_id, [])
                if row.page_id == page_id
            ),
            None,
        )
        if layout_row is None:
            raise DocumentPageNotFoundError("Layout page result not found.")
        if layout_row.page_recall_status == "COMPLETE":
            raise DocumentTranscriptionConflictError(
                "Rescue resolution is only valid for NEEDS_RESCUE or NEEDS_MANUAL_REVIEW pages."
            )
        self._transcription_rescue_resolutions[(run.id, page_id)] = {
            "resolution_status": resolution_status,
            "resolution_reason": resolution_reason.strip() if isinstance(resolution_reason, str) and resolution_reason.strip() else None,
            "updated_by": current_user.user_id,
            "updated_at": datetime.now(UTC),
        }
        return self.list_transcription_run_page_rescue_sources(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page_id,
        )

    def list_transcription_run_pages(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        status: str | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[list[PageTranscriptionResultRecord], int | None]:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        rows = list(self._transcription_pages.get(run_id, []))
        if isinstance(status, str):
            rows = [row for row in rows if row.status == status]
        start = max(0, cursor)
        safe_page_size = max(1, min(page_size, 500))
        end = start + safe_page_size
        next_cursor = end if end < len(rows) else None
        return rows[start:end], next_cursor

    def list_transcription_run_page_lines(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[LineTranscriptionResultRecord]:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page_rows = self._transcription_pages.get(run_id, [])
        if not any(page.page_id == page_id for page in page_rows):
            raise DocumentPageNotFoundError("Transcription page result not found.")
        return list(self._transcription_lines.get((run_id, page_id), []))

    def list_transcription_line_versions(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
    ) -> DocumentTranscriptionLineVersionHistorySnapshot:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        run = self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        line_rows = self.list_transcription_run_page_lines(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        line = next((item for item in line_rows if item.line_id == line_id), None)
        if line is None:
            raise DocumentPageNotFoundError("Transcription line result not found.")
        versions = list(self._transcript_versions.get((run_id, page_id, line_id), []))
        snapshots = tuple(
            DocumentTranscriptVersionLineageSnapshot(
                version=version,
                is_active=version.id == line.active_transcript_version_id,
                source_type=(
                    "COMPARE_COMPOSED"
                    if run.engine == "REVIEW_COMPOSED"
                    else "ENGINE_OUTPUT"
                    if version.base_version_id is None
                    else "REVIEWER_CORRECTION"
                ),
            )
            for version in versions
        )
        return DocumentTranscriptionLineVersionHistorySnapshot(
            run=run,
            page=page,
            line=line,
            versions=snapshots,
        )

    def get_transcription_line_version(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
        version_id: str,
    ) -> DocumentTranscriptVersionLineageSnapshot:
        history = self.list_transcription_line_versions(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
        )
        for item in history.versions:
            if item.version.id == version_id:
                return item
        raise DocumentPageNotFoundError("Transcript version was not found.")

    def list_transcription_run_page_tokens(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[TokenTranscriptionResultRecord]:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page_rows = self._transcription_pages.get(run_id, [])
        if not any(page.page_id == page_id for page in page_rows):
            raise DocumentPageNotFoundError("Transcription page result not found.")
        return list(self._transcription_tokens.get((run_id, page_id), []))

    def correct_transcription_line(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
        text_diplomatic: str,
        version_etag: str,
        edit_reason: str | None = None,
    ) -> DocumentTranscriptionLineCorrectionSnapshot:
        self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        run = self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        line_rows = self._transcription_lines.get((run_id, page_id), [])
        line_index: int | None = None
        for index, row in enumerate(line_rows):
            if row.line_id == line_id:
                line_index = index
                break
        if line_index is None:
            raise DocumentPageNotFoundError("Transcription line result not found.")
        current_line = line_rows[line_index]
        if current_line.version_etag != version_etag:
            raise DocumentTranscriptionConflictError(
                "version_etag is stale for this transcript line."
            )

        now = datetime.now(UTC)
        version_count = sum(len(items) for items in self._transcript_versions.values())
        next_version_id = f"transcript-version-{version_count + 1}"
        next_version_etag = (
            f"{current_line.version_etag}-v{version_count + 1}"
        )
        versions_key = (run_id, page_id, line_id)
        versions = list(self._transcript_versions.get(versions_key, []))
        if current_line.active_transcript_version_id is not None:
            versions = [
                replace(item, superseded_by_version_id=next_version_id)
                if item.id == current_line.active_transcript_version_id
                else item
                for item in versions
            ]

        active_version = TranscriptVersionRecord(
            id=next_version_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
            base_version_id=current_line.active_transcript_version_id,
            superseded_by_version_id=None,
            version_etag=next_version_etag,
            text_diplomatic=text_diplomatic,
            editor_user_id=current_user.user_id,
            edit_reason=edit_reason,
            created_at=now,
        )
        versions.append(active_version)
        self._transcript_versions[versions_key] = versions

        text_changed = current_line.text_diplomatic != text_diplomatic
        updated_line = replace(
            current_line,
            active_transcript_version_id=active_version.id,
            version_etag=active_version.version_etag,
            token_anchor_status=(
                "REFRESH_REQUIRED"
                if text_changed
                else current_line.token_anchor_status
            ),
            updated_at=now,
        )
        line_rows[line_index] = updated_line

        page_row = next(
            row for row in self._transcription_pages.get(run_id, []) if row.page_id == page_id
        )
        existing_projection = self._transcription_output_projections.get((run_id, page_id))
        projection = TranscriptionOutputProjectionRecord(
            run_id=run_id,
            document_id=document_id,
            page_id=page_id,
            corrected_pagexml_key=(
                "controlled/derived/"
                f"{project_id}/{document_id}/transcription/{run_id}/versions/"
                f"{active_version.id}/page/{page.page_index}.xml"
            ),
            corrected_pagexml_sha256=f"corrected-pagexml-{active_version.id}",
            corrected_text_sha256=hashlib.sha256(
                text_diplomatic.encode("utf-8")
            ).hexdigest(),
            source_pagexml_sha256=(
                existing_projection.source_pagexml_sha256
                if existing_projection is not None
                else str(page_row.pagexml_out_sha256 or "source-pagexml-sha-missing")
            ),
            updated_at=now,
        )
        self._transcription_output_projections[(run_id, page_id)] = projection

        downstream_projection: DocumentTranscriptionProjectionRecord | None = None
        projection_row = self._transcription_projection.get(document_id)
        if (
            text_changed
            and projection_row is not None
            and projection_row.active_transcription_run_id == run_id
        ):
            downstream_projection = replace(
                projection_row,
                downstream_redaction_state="STALE",
                downstream_redaction_invalidated_at=now,
                downstream_redaction_invalidated_reason=(
                    "TRANSCRIPT_CORRECTION_ACTIVE_BASIS_CHANGED: "
                    f"run={run_id};page={page_id};line={line_id};version={active_version.id}"
                ),
                updated_at=now,
            )
            self._transcription_projection[document_id] = downstream_projection

        return DocumentTranscriptionLineCorrectionSnapshot(
            run=run,
            page=page,
            line=updated_line,
            active_version=active_version,
            projection=projection,
            text_changed=text_changed,
            downstream_projection=downstream_projection,
        )

    def list_transcription_variant_layers(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        variant_kind: str = "NORMALISED",
    ) -> DocumentTranscriptionVariantLayersSnapshot:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_variant_kind = variant_kind.strip().upper()
        if normalized_variant_kind != "NORMALISED":
            raise DocumentValidationError("variantKind must be NORMALISED.")
        run = self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        layers = list(
            self._transcript_variant_layers.get(
                (run_id, page_id, normalized_variant_kind),
                [],
            )
        )
        snapshots = tuple(
            DocumentTranscriptionVariantLayerSnapshot(
                layer=layer,
                suggestions=tuple(
                    self._transcript_variant_suggestions.get(layer.id, [])
                ),
            )
            for layer in layers
        )
        return DocumentTranscriptionVariantLayersSnapshot(
            run=run,
            page=page,
            variant_kind="NORMALISED",
            layers=snapshots,
        )

    def record_transcription_variant_suggestion_decision(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        variant_kind: str,
        suggestion_id: str,
        decision: str,
        reason: str | None = None,
    ) -> DocumentTranscriptionVariantSuggestionDecisionSnapshot:
        self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_variant_kind = variant_kind.strip().upper()
        if normalized_variant_kind != "NORMALISED":
            raise DocumentValidationError("variantKind must be NORMALISED.")
        normalized_decision = decision.strip().upper()
        if normalized_decision not in {"ACCEPT", "REJECT"}:
            raise DocumentValidationError("decision must be ACCEPT or REJECT.")

        run = self.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page = self.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )

        layer = next(
            (
                item
                for item in self._transcript_variant_layers.get(
                    (run_id, page_id, normalized_variant_kind),
                    [],
                )
            ),
            None,
        )
        if layer is None:
            raise DocumentPageNotFoundError("Transcript variant layer not found.")

        suggestions = list(self._transcript_variant_suggestions.get(layer.id, []))
        suggestion_index: int | None = None
        for index, item in enumerate(suggestions):
            if item.id == suggestion_id:
                suggestion_index = index
                break
        if suggestion_index is None:
            raise DocumentPageNotFoundError("Transcript variant suggestion not found.")

        now = datetime.now(UTC)
        current_suggestion = suggestions[suggestion_index]
        next_status = "ACCEPTED" if normalized_decision == "ACCEPT" else "REJECTED"
        updated_suggestion = replace(
            current_suggestion,
            status=next_status,
            decided_by=current_user.user_id,
            decided_at=now,
            decision_reason=reason,
            updated_at=now,
        )
        suggestions[suggestion_index] = updated_suggestion
        self._transcript_variant_suggestions[layer.id] = suggestions

        event = TranscriptVariantSuggestionEventRecord(
            id=f"variant-event-{len(self._transcript_variant_suggestion_events) + 1}",
            suggestion_id=updated_suggestion.id,
            variant_layer_id=layer.id,
            actor_user_id=current_user.user_id,
            decision=normalized_decision,  # type: ignore[arg-type]
            from_status=current_suggestion.status,
            to_status=next_status,  # type: ignore[arg-type]
            reason=reason,
            created_at=now,
        )
        self._transcript_variant_suggestion_events.append(event)

        return DocumentTranscriptionVariantSuggestionDecisionSnapshot(
            run=run,
            page=page,
            variant_kind="NORMALISED",
            suggestion=updated_suggestion,
            event=event,
        )

    def get_transcription_overview(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentTranscriptionOverviewSnapshot:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        document = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        projection, active_run = self.get_active_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        runs = list(self._transcription_runs.get(document_id, []))
        status_counts = {
            "QUEUED": 0,
            "RUNNING": 0,
            "SUCCEEDED": 0,
            "FAILED": 0,
            "CANCELED": 0,
        }
        line_count = 0
        token_count = 0
        anchor_refresh_required = 0
        low_confidence_lines = 0
        if active_run is not None:
            for row in self._transcription_pages.get(active_run.id, []):
                status_counts[row.status] += 1
                lines = self._transcription_lines.get((active_run.id, row.page_id), [])
                tokens = self._transcription_tokens.get((active_run.id, row.page_id), [])
                line_count += len(lines)
                token_count += len(tokens)
                anchor_refresh_required += sum(
                    1 for line in lines if line.token_anchor_status != "CURRENT"
                )
                low_confidence_lines += sum(
                    1
                    for line in lines
                    if isinstance(line.conf_line, float) and line.conf_line < 0.75
                )
        return DocumentTranscriptionOverviewSnapshot(
            document=document,
            projection=projection,
            active_run=active_run,
            latest_run=runs[0] if runs else None,
            total_runs=len(runs),
            page_count=len(self._pages.get(document_id, [])),
            active_status_counts=status_counts,  # type: ignore[arg-type]
            active_line_count=line_count,
            active_token_count=token_count,
            active_anchor_refresh_required=anchor_refresh_required,
            active_low_confidence_lines=low_confidence_lines,
        )

    def list_transcription_triage(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str | None = None,
        status: str | None = None,
        confidence_below: float | None = None,
        page_number: int | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[
        DocumentTranscriptionProjectionRecord | None,
        TranscriptionRunRecord | None,
        list[DocumentTranscriptionTriagePageSnapshot],
        int | None,
    ]:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        projection = self._transcription_projection.get(document_id)
        target_run: TranscriptionRunRecord | None = None
        if run_id is not None:
            target_run = self._get_transcription_run_or_raise(
                document_id=document_id,
                run_id=run_id,
            )
        elif projection is not None and projection.active_transcription_run_id:
            target_run = self._get_transcription_run_or_raise(
                document_id=document_id,
                run_id=projection.active_transcription_run_id,
            )
        if target_run is None:
            return projection, None, [], None

        rows = list(self._transcription_pages.get(target_run.id, []))
        if isinstance(status, str):
            rows = [row for row in rows if row.status == status]
        triage_rows: list[DocumentTranscriptionTriagePageSnapshot] = []
        threshold = confidence_below if confidence_below is not None else 0.75
        fallback_threshold = (
            float(target_run.params_json.get("fallback_confidence_threshold"))
            if isinstance(target_run.params_json.get("fallback_confidence_threshold"), (int, float))
            else 0.72
        )
        fallback_threshold = max(0.0, min(float(threshold), fallback_threshold))
        for row in rows:
            if page_number is not None and row.page_index + 1 != page_number:
                continue
            line_rows = list(self._transcription_lines.get((target_run.id, row.page_id), []))
            token_rows = list(self._transcription_tokens.get((target_run.id, row.page_id), []))
            confidence_values = [
                line.conf_line
                for line in line_rows
                if isinstance(line.conf_line, float)
            ]
            min_confidence = min(confidence_values) if confidence_values else None
            avg_confidence = (
                sum(confidence_values) / len(confidence_values)
                if confidence_values
                else None
            )
            low_confidence_lines = sum(
                1
                for line in line_rows
                if isinstance(line.conf_line, float) and line.conf_line < threshold
            )
            if (
                confidence_below is not None
                and low_confidence_lines == 0
                and (min_confidence is None or min_confidence >= confidence_below)
            ):
                continue
            confidence_bands = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
            anchor_refresh_required = sum(
                1 for line in line_rows if line.token_anchor_status != "CURRENT"
            )
            validation_failures = sum(
                1 for line in line_rows if line.schema_validation_status == "INVALID"
            )
            segmentation_mismatch = sum(
                1
                for line in line_rows
                if line.schema_validation_status != "INVALID"
                and not line.text_diplomatic.strip()
            )
            for line in line_rows:
                band = line.confidence_band
                if band == "UNKNOWN":
                    if isinstance(line.conf_line, float):
                        if line.conf_line >= threshold:
                            band = "HIGH"
                        elif line.conf_line >= fallback_threshold:
                            band = "MEDIUM"
                        else:
                            band = "LOW"
                confidence_bands[band] += 1
            ranking_score = 0.0
            rationale_parts: list[str] = []
            issues: list[str] = []
            if row.status == "FAILED":
                ranking_score += 500.0
                rationale_parts.append("page status FAILED")
                issues.append("FAILED")
            if low_confidence_lines > 0:
                ranking_score += low_confidence_lines * 25.0
                rationale_parts.append(
                    f"{low_confidence_lines} low-confidence line(s) below {threshold:.3f}"
                )
                issues.append("LOW_CONFIDENCE")
            if min_confidence is not None:
                ranking_score += (1.0 - min_confidence) * 100.0
                rationale_parts.append(f"minimum confidence {min_confidence:.3f}")
            if validation_failures > 0:
                ranking_score += validation_failures * 40.0
                rationale_parts.append(f"{validation_failures} structured validation failure(s)")
                issues.append("SCHEMA_VALIDATION_FAILED")
            if segmentation_mismatch > 0:
                ranking_score += segmentation_mismatch * 15.0
                rationale_parts.append(f"{segmentation_mismatch} segmentation mismatch warning(s)")
                issues.append("SEGMENTATION_MISMATCH")
            if anchor_refresh_required > 0:
                ranking_score += anchor_refresh_required * 20.0
                rationale_parts.append(f"{anchor_refresh_required} anchor refresh required")
                issues.append("ANCHOR_REFRESH_REQUIRED")
            for warning in row.warnings_json:
                if warning not in issues:
                    issues.append(warning)
            triage_rows.append(
                DocumentTranscriptionTriagePageSnapshot(
                    run_id=row.run_id,
                    page_id=row.page_id,
                    page_index=row.page_index,
                    status=row.status,
                    line_count=len(line_rows),
                    token_count=len(token_rows),
                    anchor_refresh_required=anchor_refresh_required,
                    low_confidence_lines=low_confidence_lines,
                    min_confidence=min_confidence,
                    avg_confidence=avg_confidence,
                    warnings_json=list(row.warnings_json),
                    confidence_bands=confidence_bands,  # type: ignore[arg-type]
                    issues=issues,
                    ranking_score=round(ranking_score, 6),
                    ranking_rationale=(
                        "; ".join(rationale_parts)
                        if rationale_parts
                        else "No elevated risk factors."
                    ),
                    reviewer_assignment_user_id=row.reviewer_assignment_user_id,
                    reviewer_assignment_updated_by=row.reviewer_assignment_updated_by,
                    reviewer_assignment_updated_at=row.reviewer_assignment_updated_at,
                )
            )
        triage_rows.sort(
            key=lambda item: (-item.ranking_score, item.page_index, item.page_id)
        )
        start = max(0, cursor)
        safe_page_size = max(1, min(page_size, 500))
        end = start + safe_page_size
        next_cursor = end if end < len(triage_rows) else None
        return projection, target_run, triage_rows[start:end], next_cursor

    def get_transcription_metrics(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str | None = None,
        confidence_below: float | None = None,
    ) -> tuple[
        DocumentTranscriptionProjectionRecord | None,
        TranscriptionRunRecord | None,
        DocumentTranscriptionMetricsSnapshot,
    ]:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        projection = self._transcription_projection.get(document_id)
        target_run: TranscriptionRunRecord | None = None
        if run_id is not None:
            target_run = self._get_transcription_run_or_raise(
                document_id=document_id,
                run_id=run_id,
            )
        elif projection is not None and projection.active_transcription_run_id:
            target_run = self._get_transcription_run_or_raise(
                document_id=document_id,
                run_id=projection.active_transcription_run_id,
            )

        if target_run is None:
            return projection, None, DocumentTranscriptionMetricsSnapshot(
                run_id=None,
                review_confidence_threshold=(
                    float(confidence_below)
                    if isinstance(confidence_below, (int, float))
                    else 0.85
                ),
                fallback_confidence_threshold=0.72,
                page_count=0,
                line_count=0,
                token_count=0,
                low_confidence_line_count=0,
                percent_lines_below_threshold=0.0,
                low_confidence_page_count=0,
                low_confidence_page_distribution=[],
                segmentation_mismatch_warning_count=0,
                structured_validation_failure_count=0,
                fallback_invocation_count=0,
                confidence_bands={"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0},
            )

        review_threshold = (
            float(confidence_below)
            if isinstance(confidence_below, (int, float))
            else (
                float(target_run.params_json.get("review_confidence_threshold"))
                if isinstance(target_run.params_json.get("review_confidence_threshold"), (int, float))
                else 0.85
            )
        )
        fallback_threshold = (
            float(target_run.params_json.get("fallback_confidence_threshold"))
            if isinstance(target_run.params_json.get("fallback_confidence_threshold"), (int, float))
            else 0.72
        )
        fallback_threshold = max(0.0, min(review_threshold, fallback_threshold))
        page_rows = list(self._transcription_pages.get(target_run.id, []))
        line_count = 0
        token_count = 0
        low_confidence_line_count = 0
        segmentation_mismatch_warning_count = 0
        structured_validation_failure_count = 0
        fallback_invocation_count = 0
        confidence_bands = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
        low_confidence_pages: list[DocumentTranscriptionLowConfidencePageSnapshot] = []

        for page_row in page_rows:
            line_rows = list(self._transcription_lines.get((target_run.id, page_row.page_id), []))
            token_rows = list(self._transcription_tokens.get((target_run.id, page_row.page_id), []))
            line_count += len(line_rows)
            token_count += len(token_rows)
            page_low_confidence = 0
            line_validation_failures = 0
            metric_fallback = page_row.metrics_json.get("fallbackInvocationCount")
            if isinstance(metric_fallback, (int, float)):
                fallback_invocation_count += int(metric_fallback)
            for line in line_rows:
                band = line.confidence_band
                if band == "UNKNOWN":
                    if isinstance(line.conf_line, float):
                        if line.conf_line >= review_threshold:
                            band = "HIGH"
                        elif line.conf_line >= fallback_threshold:
                            band = "MEDIUM"
                        else:
                            band = "LOW"
                confidence_bands[band] += 1
                if line.schema_validation_status == "INVALID":
                    line_validation_failures += 1
                if line.schema_validation_status != "INVALID" and not line.text_diplomatic.strip():
                    segmentation_mismatch_warning_count += 1
                if isinstance(line.conf_line, float) and line.conf_line < review_threshold:
                    low_confidence_line_count += 1
                    page_low_confidence += 1
            metric_invalid = page_row.metrics_json.get("invalidTargetCount")
            if not isinstance(metric_invalid, (int, float)):
                metric_invalid = page_row.metrics_json.get("invalidCount")
            warning_invalid = 1 if "SCHEMA_VALIDATION_FAILED" in page_row.warnings_json else 0
            structured_validation_failure_count += max(
                line_validation_failures,
                int(metric_invalid) if isinstance(metric_invalid, (int, float)) else 0,
                warning_invalid,
            )
            if page_low_confidence > 0:
                low_confidence_pages.append(
                    DocumentTranscriptionLowConfidencePageSnapshot(
                        page_id=page_row.page_id,
                        page_index=page_row.page_index,
                        low_confidence_lines=page_low_confidence,
                    )
                )

        if fallback_invocation_count == 0 and target_run.confidence_basis == "FALLBACK_DISAGREEMENT":
            fallback_invocation_count = 1
        low_confidence_pages.sort(
            key=lambda item: (-item.low_confidence_lines, item.page_index, item.page_id)
        )
        percent_lines_below_threshold = (
            round((low_confidence_line_count / line_count) * 100, 6)
            if line_count > 0
            else 0.0
        )
        return projection, target_run, DocumentTranscriptionMetricsSnapshot(
            run_id=target_run.id,
            review_confidence_threshold=review_threshold,
            fallback_confidence_threshold=fallback_threshold,
            page_count=len(page_rows),
            line_count=line_count,
            token_count=token_count,
            low_confidence_line_count=low_confidence_line_count,
            percent_lines_below_threshold=percent_lines_below_threshold,
            low_confidence_page_count=len(low_confidence_pages),
            low_confidence_page_distribution=low_confidence_pages,
            segmentation_mismatch_warning_count=segmentation_mismatch_warning_count,
            structured_validation_failure_count=structured_validation_failure_count,
            fallback_invocation_count=fallback_invocation_count,
            confidence_bands=confidence_bands,  # type: ignore[arg-type]
        )

    def update_transcription_triage_page_assignment(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        page_id: str,
        reviewer_user_id: str | None,
        run_id: str | None = None,
    ) -> tuple[
        DocumentTranscriptionProjectionRecord | None,
        TranscriptionRunRecord,
        DocumentTranscriptionTriagePageSnapshot,
    ]:
        self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        projection = self._transcription_projection.get(document_id)
        if run_id is not None:
            target_run = self._get_transcription_run_or_raise(
                document_id=document_id,
                run_id=run_id,
            )
        elif projection is not None and projection.active_transcription_run_id:
            target_run = self._get_transcription_run_or_raise(
                document_id=document_id,
                run_id=projection.active_transcription_run_id,
            )
        else:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")

        page_rows = list(self._transcription_pages.get(target_run.id, []))
        row_index = next((index for index, row in enumerate(page_rows) if row.page_id == page_id), -1)
        if row_index < 0:
            raise DocumentPageNotFoundError("Transcription page result not found.")
        updated_page_row = replace(
            page_rows[row_index],
            reviewer_assignment_user_id=reviewer_user_id,
            reviewer_assignment_updated_by=current_user.user_id,
            reviewer_assignment_updated_at=datetime.now(UTC),
        )
        page_rows[row_index] = updated_page_row
        self._transcription_pages[target_run.id] = page_rows

        _, _, rows, _ = self.list_transcription_triage(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=target_run.id,
            page_number=updated_page_row.page_index + 1,
            cursor=0,
            page_size=5,
        )
        triage_row = next((item for item in rows if item.page_id == page_id), None)
        if triage_row is None:
            raise DocumentPageNotFoundError("Transcription page result not found.")
        return projection, target_run, triage_row

    def _snapshot_for_session(
        self,
        *,
        project_id: str,
        session_id: str,
    ) -> DocumentUploadSessionSnapshot:
        session = self._upload_sessions.get(session_id)
        if session is None or session.project_id != project_id:
            raise DocumentUploadSessionNotFoundError("Upload session not found.")
        import_snapshot = self._imports.get(session.import_id)
        if import_snapshot is None:
            raise DocumentUploadSessionNotFoundError("Upload session import was not found.")
        return DocumentUploadSessionSnapshot(
            session_record=session,
            import_record=import_snapshot.import_record,
            document_record=import_snapshot.document_record,
        )

    def start_upload_session(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        original_filename: str,
        expected_sha256: str | None = None,
        expected_total_bytes: int | None = None,
    ) -> DocumentUploadSessionSnapshot:
        self._require_project_access(project_id)
        del expected_sha256
        now = datetime.now(UTC)
        self._upload_session_sequence += 1
        session_id = f"session-{self._upload_session_sequence}"
        document_id = f"doc-session-{self._upload_session_sequence}"
        import_id = f"import-session-{self._upload_session_sequence}"
        document = DocumentRecord(
            id=document_id,
            project_id=project_id,
            original_filename=original_filename,
            stored_filename=None,
            content_type_detected=None,
            bytes=None,
            sha256=None,
            page_count=None,
            status="UPLOADING",
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        import_record = DocumentImportRecord(
            id=import_id,
            document_id=document_id,
            status="UPLOADING",
            failure_reason=None,
            created_by=current_user.user_id,
            accepted_at=None,
            rejected_at=None,
            canceled_by=None,
            canceled_at=None,
            created_at=now,
            updated_at=now,
        )
        self._documents.setdefault(project_id, []).insert(0, document)
        self._imports[import_id] = DocumentImportSnapshot(
            import_record=import_record,
            document_record=document,
        )
        self._upload_sessions[session_id] = DocumentUploadSessionRecord(
            id=session_id,
            project_id=project_id,
            document_id=document_id,
            import_id=import_id,
            original_filename=original_filename,
            status="ACTIVE",
            expected_sha256=None,
            expected_total_bytes=expected_total_bytes,
            bytes_received=0,
            last_chunk_index=-1,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
            completed_at=None,
            canceled_at=None,
            failure_reason=None,
        )
        self._upload_session_chunks[session_id] = {}
        return self._snapshot_for_session(project_id=project_id, session_id=session_id)

    def get_upload_session(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        session_id: str,
    ) -> DocumentUploadSessionSnapshot:
        self._require_project_access(project_id)
        return self._snapshot_for_session(project_id=project_id, session_id=session_id)

    def append_upload_session_chunk(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        session_id: str,
        chunk_index: int,
        file_stream: BinaryIO,
    ) -> DocumentUploadSessionSnapshot:
        self._require_project_access(project_id)
        snapshot = self._snapshot_for_session(project_id=project_id, session_id=session_id)
        session = snapshot.session_record
        if session.status != "ACTIVE":
            raise DocumentUploadSessionConflictError(
                f"Upload session is {session.status} and cannot accept chunks."
            )
        payload = file_stream.read()
        if not isinstance(payload, bytes) or not payload:
            raise DocumentValidationError("Upload chunk payload is empty.")
        expected_next = session.last_chunk_index + 1
        if chunk_index > expected_next:
            raise DocumentUploadSessionConflictError(
                f"Chunk index gap detected. Resume from chunk {expected_next}."
            )
        chunks = self._upload_session_chunks.setdefault(session_id, {})
        bytes_received = session.bytes_received
        if chunk_index in chunks:
            if chunks[chunk_index] != payload:
                raise DocumentUploadSessionConflictError(
                    "Upload session chunk collision detected for this index."
                )
        else:
            chunks[chunk_index] = payload
            bytes_received += len(payload)
        now = datetime.now(UTC)
        self._upload_sessions[session_id] = replace(
            session,
            bytes_received=bytes_received,
            last_chunk_index=max(session.last_chunk_index, chunk_index),
            updated_at=now,
        )
        return self._snapshot_for_session(project_id=project_id, session_id=session_id)

    def complete_upload_session(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        session_id: str,
    ) -> DocumentUploadSessionSnapshot:
        self._require_project_access(project_id)
        snapshot = self._snapshot_for_session(project_id=project_id, session_id=session_id)
        session = snapshot.session_record
        if session.status != "ACTIVE":
            raise DocumentUploadSessionConflictError(
                f"Upload session is {session.status} and cannot be completed."
            )
        chunks = self._upload_session_chunks.get(session_id, {})
        if not chunks:
            raise DocumentUploadSessionConflictError("Upload session has no persisted chunks.")
        now = datetime.now(UTC)
        assembled = b"".join(
            chunks[index] for index in sorted(chunks.keys())
        )
        self._upload_sessions[session_id] = replace(
            session,
            status="COMPLETED",
            bytes_received=len(assembled),
            completed_at=now,
            updated_at=now,
        )
        import_snapshot = self._imports[session.import_id]
        queued_import = replace(import_snapshot.import_record, status="QUEUED", updated_at=now)
        queued_document = replace(
            import_snapshot.document_record,
            status="QUEUED",
            bytes=len(assembled),
            updated_at=now,
        )
        self._imports[session.import_id] = DocumentImportSnapshot(
            import_record=queued_import,
            document_record=queued_document,
        )
        self._documents[project_id] = [
            queued_document if row.id == queued_document.id else row
            for row in self._documents.get(project_id, [])
        ]
        return self._snapshot_for_session(project_id=project_id, session_id=session_id)

    def cancel_upload_session(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        session_id: str,
    ) -> DocumentUploadSessionSnapshot:
        self._require_project_access(project_id)
        snapshot = self._snapshot_for_session(project_id=project_id, session_id=session_id)
        session = snapshot.session_record
        if session.status in {"FAILED", "CANCELED", "COMPLETED"}:
            raise DocumentUploadSessionConflictError(f"Upload session is already {session.status}.")
        now = datetime.now(UTC)
        self._upload_sessions[session_id] = replace(
            session,
            status="CANCELED",
            canceled_at=now,
            updated_at=now,
        )
        canceled_import = replace(
            snapshot.import_record,
            status="CANCELED",
            canceled_by=current_user.user_id,
            canceled_at=now,
            updated_at=now,
        )
        canceled_document = replace(snapshot.document_record, status="CANCELED", updated_at=now)
        self._imports[session.import_id] = DocumentImportSnapshot(
            import_record=canceled_import,
            document_record=canceled_document,
        )
        self._documents[project_id] = [
            canceled_document if row.id == canceled_document.id else row
            for row in self._documents.get(project_id, [])
        ]
        return self._snapshot_for_session(project_id=project_id, session_id=session_id)


def _principal(
    *,
    user_id: str = "user-1",
    roles: tuple[Literal["ADMIN", "AUDITOR"], ...] = (),
) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-docs",
        auth_source="bearer",
        user_id=user_id,
        oidc_sub=f"oidc-{user_id}",
        email=f"{user_id}@test.local",
        display_name=user_id.title(),
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-docs",
    )


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    app.dependency_overrides[get_job_service] = lambda: FakeJobService()
    yield
    app.dependency_overrides.clear()


def test_list_documents_returns_project_scoped_items_and_audit_event() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    response = client.get("/projects/project-1/documents")

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == ["doc-1", "doc-3", "doc-2"]
    assert payload["nextCursor"] is None
    assert any(
        entry.get("event_type") == "DOCUMENT_LIBRARY_VIEWED" for entry in spy.recorded
    )


def test_list_documents_supports_search_filters_sort_and_cursor() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    filtered = client.get(
        "/projects/project-1/documents",
        params={
            "search": "register",
            "status": "READY",
            "uploader": "user-1",
            "sort": "name",
            "direction": "asc",
        },
    )

    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == ["doc-2"]
    assert filtered.json()["nextCursor"] is None

    first_page = client.get(
        "/projects/project-1/documents",
        params={"sort": "created", "direction": "desc", "pageSize": 1},
    )
    assert first_page.status_code == 200
    assert [item["id"] for item in first_page.json()["items"]] == ["doc-1"]
    assert first_page.json()["nextCursor"] == 1

    second_page = client.get(
        "/projects/project-1/documents",
        params={"sort": "created", "direction": "desc", "pageSize": 1, "cursor": 1},
    )
    assert second_page.status_code == 200
    assert [item["id"] for item in second_page.json()["items"]] == ["doc-2"]
    assert second_page.json()["nextCursor"] == 2

    third_page = client.get(
        "/projects/project-1/documents",
        params={"sort": "created", "direction": "desc", "pageSize": 1, "cursor": 2},
    )
    assert third_page.status_code == 200
    assert [item["id"] for item in third_page.json()["items"]] == ["doc-3"]
    assert third_page.json()["nextCursor"] is None


def test_list_documents_supports_legacy_q_alias_and_date_filters() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    search_alias = client.get(
        "/projects/project-1/documents",
        params={"q": "diary"},
    )
    assert search_alias.status_code == 200
    assert [item["id"] for item in search_alias.json()["items"]] == ["doc-1"]

    from_iso = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    date_filtered = client.get(
        "/projects/project-1/documents",
        params={"from": from_iso},
    )
    assert date_filtered.status_code == 200
    assert [item["id"] for item in date_filtered.json()["items"]] == ["doc-1"]

    invalid_range = client.get(
        "/projects/project-1/documents",
        params={"from": "2026-03-12", "to": "2026-03-11"},
    )
    assert invalid_range.status_code == 422


def test_get_document_detail_and_timeline_emit_expected_audit_events() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    detail_response = client.get("/projects/project-1/documents/doc-2")
    timeline_response = client.get("/projects/project-1/documents/doc-2/timeline")

    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "READY"
    assert timeline_response.status_code == 200
    assert timeline_response.json()["items"][0]["runKind"] == "THUMBNAIL_RENDER"
    assert timeline_response.json()["items"][0]["status"] == "SUCCEEDED"
    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "DOCUMENT_DETAIL_VIEWED" in event_types
    assert "DOCUMENT_TIMELINE_VIEWED" in event_types


def test_processing_runs_alias_and_status_endpoint_return_expected_payload() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    runs_response = client.get("/projects/project-1/documents/doc-1/processing-runs")
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload["items"][0]["id"] == "run-1"
    assert runs_payload["items"][0]["attemptNumber"] == 1
    assert runs_payload["items"][0]["status"] == "RUNNING"

    run_detail = client.get("/projects/project-1/documents/doc-1/processing-runs/run-1")
    assert run_detail.status_code == 200
    detail_payload = run_detail.json()
    assert detail_payload["documentId"] == "doc-1"
    assert detail_payload["attemptNumber"] == 1
    assert detail_payload["supersedesProcessingRunId"] is None
    assert detail_payload["supersededByProcessingRunId"] is None
    assert detail_payload["active"] is True

    run_status = client.get(
        "/projects/project-1/documents/doc-1/processing-runs/run-1/status"
    )
    assert run_status.status_code == 200
    status_payload = run_status.json()
    assert status_payload["runId"] == "run-1"
    assert status_payload["documentId"] == "doc-1"
    assert status_payload["attemptNumber"] == 1
    assert status_payload["runKind"] == "SCAN"
    assert status_payload["supersedesProcessingRunId"] is None
    assert status_payload["supersededByProcessingRunId"] is None
    assert status_payload["status"] == "RUNNING"
    assert status_payload["active"] is True

    missing = client.get(
        "/projects/project-1/documents/doc-1/processing-runs/run-missing/status"
    )
    assert missing.status_code == 404

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "DOCUMENT_TIMELINE_VIEWED" in event_types
    assert "DOCUMENT_PROCESSING_RUN_VIEWED" in event_types
    assert "DOCUMENT_PROCESSING_RUN_STATUS_VIEWED" in event_types


def test_preprocess_overview_quality_and_run_routes_emit_expected_audit_events() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    overview = client.get("/projects/project-1/documents/doc-2/preprocessing/overview")
    quality = client.get("/projects/project-1/documents/doc-2/preprocessing/quality")
    runs = client.get("/projects/project-1/documents/doc-2/preprocess-runs")
    active = client.get("/projects/project-1/documents/doc-2/preprocess-runs/active")
    detail = client.get("/projects/project-1/documents/doc-2/preprocess-runs/pre-run-2")
    status_response = client.get(
        "/projects/project-1/documents/doc-2/preprocess-runs/pre-run-2/status"
    )
    pages = client.get(
        "/projects/project-1/documents/doc-2/preprocess-runs/pre-run-2/pages"
    )
    page = client.get(
        "/projects/project-1/documents/doc-2/preprocess-runs/pre-run-2/pages/page-1"
    )
    compare = client.get(
        "/projects/project-1/documents/doc-2/preprocess-runs/compare",
        params={"baseRunId": "pre-run-1", "candidateRunId": "pre-run-2"},
    )

    assert overview.status_code == 200
    assert quality.status_code == 200
    assert runs.status_code == 200
    assert active.status_code == 200
    assert detail.status_code == 200
    assert status_response.status_code == 200
    assert pages.status_code == 200
    assert page.status_code == 200
    assert compare.status_code == 200
    assert overview.json()["activeRun"]["id"] == "pre-run-2"
    active_payload = active.json()
    assert active_payload["run"]["id"] == "pre-run-2"
    assert active_payload["projection"]["selectionMode"] == "EXPLICIT_ACTIVATION"
    assert (
        active_payload["projection"]["downstreamDefaultConsumer"]
        == "LAYOUT_ANALYSIS_PHASE_3"
    )
    assert (
        active_payload["projection"]["downstreamImpact"]["layoutBasisState"]
        == "CURRENT"
    )
    assert (
        active_payload["projection"]["downstreamImpact"]["transcriptionBasisState"]
        == "CURRENT"
    )
    detail_payload = detail.json()
    assert detail_payload["profileVersion"] == "v1"
    assert "manifestSchemaVersion" in detail_payload
    assert detail_payload["isActiveProjection"] is True
    assert detail_payload["isCurrentAttempt"] is True
    assert detail_payload["isHistoricalAttempt"] is False
    assert detail_payload["downstreamImpact"]["layoutBasisState"] == "CURRENT"
    page_payload = page.json()
    assert "sourceResultRunId" in page_payload
    assert "metricsObjectKey" in page_payload
    runs_payload = runs.json()
    assert runs_payload["items"][0]["isActiveProjection"] is True
    assert runs_payload["items"][1]["isSuperseded"] is True
    assert compare.json()["baseRun"]["id"] == "pre-run-1"
    assert compare.json()["candidateRun"]["id"] == "pre-run-2"
    first_compare_item = compare.json()["items"][0]
    assert "warningDelta" in first_compare_item
    assert "metricDeltas" in first_compare_item
    assert "outputAvailability" in first_compare_item

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "PREPROCESS_OVERVIEW_VIEWED" in event_types
    assert "PREPROCESS_QUALITY_VIEWED" in event_types
    assert "PREPROCESS_RUNS_VIEWED" in event_types
    assert "PREPROCESS_ACTIVE_RUN_VIEWED" in event_types
    assert "PREPROCESS_RUN_VIEWED" in event_types
    assert "PREPROCESS_RUN_STATUS_VIEWED" in event_types
    assert "PREPROCESS_COMPARE_VIEWED" in event_types


def test_preprocess_mutations_enforce_rbac_and_lineage_events() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    denied = client.post("/projects/project-1/documents/doc-2/preprocess-runs")
    assert denied.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    created = client.post(
        "/projects/project-1/documents/doc-2/preprocess-runs",
        json={"profileId": "CONSERVATIVE", "pipelineVersion": "preprocess-v2"},
    )
    assert created.status_code == 201
    created_payload = created.json()
    assert created_payload["status"] == "QUEUED"

    aggressive_without_confirmation = client.post(
        "/projects/project-1/documents/doc-2/preprocess-runs/pre-run-2/rerun",
        json={"profileId": "AGGRESSIVE"},
    )
    assert aggressive_without_confirmation.status_code == 409

    aggressive_with_confirmation = client.post(
        "/projects/project-1/documents/doc-2/preprocess-runs/pre-run-2/rerun",
        json={
            "profileId": "AGGRESSIVE",
            "advancedRiskConfirmed": True,
            "advancedRiskAcknowledgement": "Stronger cleanup required for this source.",
        },
    )
    assert aggressive_with_confirmation.status_code == 201
    aggressive_payload = aggressive_with_confirmation.json()
    aggressive_run_id = aggressive_payload["id"]
    assert aggressive_payload["runScope"] == "FULL_DOCUMENT"
    assert aggressive_payload["paramsJson"]["profile_risk_posture"] == "ADVANCED_GATED"
    assert aggressive_payload["paramsJson"]["advanced_risk_confirmation_required"] is True

    for index, row in enumerate(fake._preprocess_runs["doc-2"]):
        if row.id == aggressive_run_id:
            fake._preprocess_runs["doc-2"][index] = replace(
                row,
                status="SUCCEEDED",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
            break

    subset_rerun = client.post(
        f"/projects/project-1/documents/doc-2/preprocess-runs/{aggressive_run_id}/rerun",
        json={"profileId": "AGGRESSIVE", "targetPageIds": ["page-2"]},
    )
    assert subset_rerun.status_code == 201
    subset_payload = subset_rerun.json()
    assert subset_payload["runScope"] == "PAGE_SUBSET"
    assert subset_payload["targetPageIdsJson"] == ["page-2"]
    subset_pages = client.get(
        f"/projects/project-1/documents/doc-2/preprocess-runs/{subset_payload['id']}/pages"
    )
    assert subset_pages.status_code == 200
    assert [item["pageId"] for item in subset_pages.json()["items"]] == ["page-2"]

    canceled = client.post(
        f"/projects/project-1/documents/doc-2/preprocess-runs/{created_payload['id']}/cancel"
    )
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "CANCELED"

    activated = client.post(
        "/projects/project-1/documents/doc-2/preprocess-runs/pre-run-2/activate"
    )
    assert activated.status_code == 200
    assert activated.json()["projection"]["activePreprocessRunId"] == "pre-run-2"

    activated_again = client.post(
        "/projects/project-1/documents/doc-2/preprocess-runs/pre-run-2/activate"
    )
    assert activated_again.status_code == 200
    assert activated_again.json()["projection"]["activePreprocessRunId"] == "pre-run-2"

    activate_historical = client.post(
        "/projects/project-1/documents/doc-2/preprocess-runs/pre-run-1/activate"
    )
    assert activate_historical.status_code == 200
    activate_historical_payload = activate_historical.json()
    assert activate_historical_payload["projection"]["activePreprocessRunId"] == "pre-run-1"
    assert (
        activate_historical_payload["projection"]["downstreamImpact"]["layoutBasisState"]
        == "STALE"
    )

    old_active = client.get(
        "/projects/project-1/documents/doc-2/preprocess-runs/pre-run-2"
    )
    assert old_active.status_code == 200
    assert old_active.json()["supersededByRunId"] == aggressive_run_id
    assert old_active.json()["isActiveProjection"] is False

    historical = client.get(
        "/projects/project-1/documents/doc-2/preprocess-runs/pre-run-1"
    )
    assert historical.status_code == 200
    assert historical.json()["supersededByRunId"] == "pre-run-2"
    assert historical.json()["isActiveProjection"] is True

    creation_events = [
        entry for entry in spy.recorded if entry.get("event_type") == "PREPROCESS_RUN_CREATED"
    ]
    assert creation_events
    assert "params_hash" in creation_events[0].get("metadata", {})
    assert "pipeline_version" in creation_events[0].get("metadata", {})
    assert "profile_risk_posture" in creation_events[0].get("metadata", {})
    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "PREPROCESS_RUN_CANCELED" in event_types
    assert "PREPROCESS_RUN_ACTIVATED" in event_types


def test_layout_overview_triage_and_run_routes_emit_expected_audit_events() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    overview = client.get("/projects/project-1/documents/doc-2/layout/overview")
    runs = client.get("/projects/project-1/documents/doc-2/layout-runs")
    active = client.get("/projects/project-1/documents/doc-2/layout-runs/active")
    detail = client.get("/projects/project-1/documents/doc-2/layout-runs/layout-run-2")
    status_response = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/status"
    )
    pages = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages",
        params={"pageRecallStatus": "NEEDS_RESCUE"},
    )

    assert overview.status_code == 200
    assert runs.status_code == 200
    assert active.status_code == 200
    assert detail.status_code == 200
    assert status_response.status_code == 200
    assert pages.status_code == 200

    overview_payload = overview.json()
    assert overview_payload["activeRun"]["id"] == "layout-run-2"
    assert overview_payload["latestRun"]["id"] == "layout-run-2"
    assert overview_payload["projection"]["activeLayoutRunId"] == "layout-run-2"
    assert overview_payload["projection"]["activeInputPreprocessRunId"] == "pre-run-2"
    assert overview_payload["totalRuns"] == 2
    assert overview_payload["pageCount"] == 2
    assert overview_payload["activeStatusCounts"]["SUCCEEDED"] == 2
    assert overview_payload["activeRecallCounts"]["COMPLETE"] == 1
    assert overview_payload["activeRecallCounts"]["NEEDS_RESCUE"] == 1
    assert overview_payload["summary"]["regionsDetected"] == 18
    assert overview_payload["summary"]["linesDetected"] == 65
    assert overview_payload["summary"]["pagesWithIssues"] == 1
    assert overview_payload["summary"]["coveragePercent"] == 83.9
    assert overview_payload["summary"]["structureConfidence"] == 0.84

    runs_payload = runs.json()
    assert [item["id"] for item in runs_payload["items"]] == ["layout-run-2", "layout-run-1"]
    assert runs_payload["items"][0]["isActiveProjection"] is True
    assert runs_payload["items"][1]["isSuperseded"] is True

    active_payload = active.json()
    assert active_payload["run"]["id"] == "layout-run-2"
    assert active_payload["projection"]["activeLayoutRunId"] == "layout-run-2"

    detail_payload = detail.json()
    assert detail_payload["id"] == "layout-run-2"
    assert detail_payload["isActiveProjection"] is True
    assert detail_payload["isCurrentAttempt"] is True
    assert detail_payload["isHistoricalAttempt"] is False

    status_payload = status_response.json()
    assert status_payload["runId"] == "layout-run-2"
    assert status_payload["status"] == "SUCCEEDED"
    assert status_payload["active"] is False

    pages_payload = pages.json()
    assert pages_payload["runId"] == "layout-run-2"
    assert [item["pageId"] for item in pages_payload["items"]] == ["page-2"]
    assert pages_payload["items"][0]["pageRecallStatus"] == "NEEDS_RESCUE"

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "LAYOUT_OVERVIEW_VIEWED" in event_types
    assert "LAYOUT_TRIAGE_VIEWED" in event_types
    assert "LAYOUT_RUNS_VIEWED" in event_types
    assert "LAYOUT_ACTIVE_RUN_VIEWED" in event_types


def test_layout_overlay_and_pagexml_routes_emit_audit_and_handle_not_ready() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    overlay = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-1/overlay"
    )
    assert overlay.status_code == 200
    assert overlay.headers["content-type"].startswith("application/json")
    assert overlay.headers["cache-control"] == "private, no-cache, max-age=0, must-revalidate"
    assert overlay.headers["x-content-type-options"] == "nosniff"
    assert (
        overlay.headers["cross-origin-resource-policy"] == "same-origin"
    )
    assert "authorization" in overlay.headers["vary"].lower()
    overlay_payload = overlay.json()
    assert overlay_payload["schemaVersion"] == 1
    assert overlay_payload["runId"] == "layout-run-2"
    assert overlay_payload["pageId"] == "page-1"
    assert len(overlay_payload["elements"]) == 2
    assert overlay_payload["readingOrderGroups"][0]["id"] == "g-0001"
    assert overlay_payload["readingOrderMeta"]["mode"] == "ORDERED"
    assert overlay_payload["readingOrderMeta"]["versionEtag"] == "layout-etag-1"

    overlay_not_modified = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-1/overlay",
        headers={"If-None-Match": overlay.headers["etag"]},
    )
    assert overlay_not_modified.status_code == 304
    assert overlay_not_modified.content == b""

    pagexml = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-1/pagexml"
    )
    assert pagexml.status_code == 200
    assert pagexml.headers["content-type"].startswith("application/xml")
    assert pagexml.headers["cache-control"] == "private, no-cache, max-age=0, must-revalidate"
    assert pagexml.headers["x-content-type-options"] == "nosniff"
    assert "content-disposition" not in pagexml.headers
    assert b"<PcGts" in pagexml.content

    pagexml_not_modified = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-1/pagexml",
        headers={"If-None-Match": pagexml.headers["etag"]},
    )
    assert pagexml_not_modified.status_code == 304
    assert pagexml_not_modified.content == b""

    overlay_not_ready = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-2/overlay"
    )
    assert overlay_not_ready.status_code == 409

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "LAYOUT_OVERLAY_ACCESSED" in event_types
    assert "LAYOUT_PAGEXML_ACCESSED" in event_types


def test_layout_reading_order_patch_persists_new_version_and_audit_event() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    response = client.patch(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-1/reading-order",
        json={
            "versionEtag": "layout-etag-1",
            "mode": "UNORDERED",
            "groups": [{"id": "g-0001", "ordered": False, "regionIds": ["region-1"]}],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["layoutVersionId"] == "layout-version-2"
    assert payload["versionEtag"] == "layout-etag-2"
    assert payload["mode"] == "UNORDERED"
    assert payload["groups"][0]["ordered"] is False

    refreshed_overlay = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-1/overlay"
    )
    assert refreshed_overlay.status_code == 200
    refreshed_payload = refreshed_overlay.json()
    assert refreshed_payload["readingOrderMeta"]["versionEtag"] == "layout-etag-2"
    assert refreshed_payload["readingOrderMeta"]["layoutVersionId"] == "layout-version-2"

    reading_order_events = [
        entry
        for entry in spy.recorded
        if entry.get("event_type") == "LAYOUT_READING_ORDER_UPDATED"
    ]
    assert len(reading_order_events) == 1
    metadata = reading_order_events[0].get("metadata", {})
    assert metadata.get("mode") == "UNORDERED"
    assert metadata.get("layout_version_id") == "layout-version-2"
    assert metadata.get("version_etag") == "layout-etag-2"


def test_layout_reading_order_patch_rejects_stale_version_etag() -> None:
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    response = client.patch(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-1/reading-order",
        json={
            "versionEtag": "layout-etag-stale",
            "mode": "ORDERED",
            "groups": [{"id": "g-0001", "ordered": True, "regionIds": ["region-1"]}],
        },
    )
    assert response.status_code == 409


def test_layout_elements_patch_persists_version_and_emits_audit_events() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    response = client.patch(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-1/elements",
        json={
            "versionEtag": "layout-etag-1",
            "operations": [
                {
                    "kind": "RETAG_REGION",
                    "regionId": "region-1",
                    "regionType": "HEADER",
                },
                {
                    "kind": "SET_REGION_READING_ORDER_INCLUDED",
                    "regionId": "region-1",
                    "includeInReadingOrder": False,
                },
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["layoutVersionId"] == "layout-version-2"
    assert payload["versionEtag"] == "layout-etag-2"
    assert payload["operationsApplied"] == 2
    assert payload["downstreamTranscriptionInvalidated"] is True
    assert payload["downstreamTranscriptionState"] == "STALE"
    assert payload["downstreamTranscriptionInvalidatedReason"] is not None
    region = next(
        element
        for element in payload["overlay"]["elements"]
        if element["id"] == "region-1"
    )
    assert region["regionType"] == "HEADER"
    assert region["includeInReadingOrder"] is False
    assert payload["overlay"]["readingOrderGroups"] == []
    assert payload["overlay"]["readingOrderMeta"]["versionEtag"] == "layout-etag-2"
    assert payload["overlay"]["readingOrderMeta"]["layoutVersionId"] == "layout-version-2"

    refreshed_overlay = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-1/overlay"
    )
    assert refreshed_overlay.status_code == 200
    refreshed_payload = refreshed_overlay.json()
    assert refreshed_payload["readingOrderMeta"]["versionEtag"] == "layout-etag-2"
    assert refreshed_payload["readingOrderMeta"]["layoutVersionId"] == "layout-version-2"

    edit_events = [
        entry for entry in spy.recorded if entry.get("event_type") == "LAYOUT_EDIT_APPLIED"
    ]
    assert len(edit_events) == 1
    edit_metadata = edit_events[0].get("metadata", {})
    assert edit_metadata.get("layout_version_id") == "layout-version-2"
    assert edit_metadata.get("version_etag") == "layout-etag-2"
    assert set(edit_metadata.get("operation_kinds", [])) == {
        "RETAG_REGION",
        "SET_REGION_READING_ORDER_INCLUDED",
    }

    invalidation_events = [
        entry
        for entry in spy.recorded
        if entry.get("event_type") == "LAYOUT_DOWNSTREAM_INVALIDATED"
    ]
    assert len(invalidation_events) == 1
    invalidation_metadata = invalidation_events[0].get("metadata", {})
    assert invalidation_metadata.get("layout_version_id") == "layout-version-2"
    assert invalidation_metadata.get("downstream_state") == "STALE"


def test_layout_elements_patch_rejects_stale_etag_and_cross_page_line_reference() -> None:
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    stale_response = client.patch(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-1/elements",
        json={
            "versionEtag": "layout-etag-stale",
            "operations": [
                {
                    "kind": "RETAG_REGION",
                    "regionId": "region-1",
                    "regionType": "TEXT",
                }
            ],
        },
    )
    assert stale_response.status_code == 409

    cross_page_response = client.patch(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-1/elements",
        json={
            "versionEtag": "layout-etag-1",
            "operations": [
                {
                    "kind": "MOVE_LINE",
                    "lineId": "line-9",
                    "polygon": [
                        {"x": 10, "y": 10},
                        {"x": 20, "y": 10},
                        {"x": 20, "y": 20},
                        {"x": 10, "y": 20},
                    ],
                }
            ],
        },
    )
    assert cross_page_response.status_code == 422


def test_layout_line_artifact_routes_expose_paths_without_storage_keys() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    artifacts = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-1/lines/line-1/artifacts"
    )
    assert artifacts.status_code == 200
    payload = artifacts.json()
    assert payload["runId"] == "layout-run-2"
    assert payload["pageId"] == "page-1"
    assert payload["lineId"] == "line-1"
    assert payload["lineCropPath"].endswith("/lines/line-1/crop")
    assert payload["pageThumbnailPath"].endswith("/pages/page-1/thumbnail")
    assert payload["contextWindowPath"].endswith("/lines/line-1/context")
    assert "lineCropKey" not in payload
    assert "regionCropKey" not in payload
    assert "pageThumbnailKey" not in payload
    assert "contextWindowJsonKey" not in payload

    line_crop = client.get(payload["lineCropPath"])
    assert line_crop.status_code == 200
    assert line_crop.headers["content-type"].startswith("image/png")

    region_crop = client.get(f"{payload['lineCropPath']}?variant=region")
    assert region_crop.status_code == 200
    assert region_crop.headers["content-type"].startswith("image/png")

    context = client.get(payload["contextWindowPath"])
    assert context.status_code == 200
    assert context.headers["content-type"].startswith("application/json")
    assert context.json()["lineId"] == "line-1"

    thumbnail = client.get(payload["pageThumbnailPath"])
    assert thumbnail.status_code == 200
    assert thumbnail.headers["content-type"].startswith("image/png")

    not_ready = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-2/lines/line-9/artifacts"
    )
    assert not_ready.status_code == 409

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "LAYOUT_LINE_ARTIFACTS_VIEWED" in event_types
    assert "LAYOUT_LINE_CROP_ACCESSED" in event_types
    assert "LAYOUT_CONTEXT_WINDOW_ACCESSED" in event_types
    assert "LAYOUT_THUMBNAIL_ACCESSED" in event_types


def test_layout_recall_status_and_rescue_candidate_routes_emit_audit() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    recall_status = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-2/recall-status"
    )
    assert recall_status.status_code == 200
    recall_payload = recall_status.json()
    assert recall_payload["runId"] == "layout-run-2"
    assert recall_payload["pageId"] == "page-2"
    assert recall_payload["pageRecallStatus"] == "NEEDS_RESCUE"
    assert recall_payload["recallCheckVersion"] == "layout-recall-v1"
    assert recall_payload["rescueCandidateCounts"]["ACCEPTED"] == 1
    assert recall_payload["unresolvedCount"] == 0

    candidates = client.get(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-2/pages/page-2/rescue-candidates"
    )
    assert candidates.status_code == 200
    candidates_payload = candidates.json()
    assert candidates_payload["runId"] == "layout-run-2"
    assert candidates_payload["pageId"] == "page-2"
    assert len(candidates_payload["items"]) == 2
    assert candidates_payload["items"][0]["candidateKind"] in {
        "LINE_EXPANSION",
        "PAGE_WINDOW",
    }

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "LAYOUT_RECALL_STATUS_VIEWED" in event_types
    assert "LAYOUT_RESCUE_CANDIDATES_VIEWED" in event_types


def test_layout_mutations_enforce_rbac_and_projection_updates() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    denied_create = client.post("/projects/project-1/documents/doc-2/layout-runs")
    assert denied_create.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    created = client.post(
        "/projects/project-1/documents/doc-2/layout-runs",
        json={
            "inputPreprocessRunId": "pre-run-2",
            "modelId": "layout-model-v2",
            "profileId": "DEFAULT",
        },
    )
    assert created.status_code == 201
    created_payload = created.json()
    assert created_payload["status"] == "QUEUED"
    assert created_payload["runKind"] == "AUTO"
    assert created_payload["inputPreprocessRunId"] == "pre-run-2"

    canceled = client.post(
        f"/projects/project-1/documents/doc-2/layout-runs/{created_payload['id']}/cancel"
    )
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "CANCELED"

    activate_canceled = client.post(
        f"/projects/project-1/documents/doc-2/layout-runs/{created_payload['id']}/activate"
    )
    assert activate_canceled.status_code == 409
    blocked_payload = activate_canceled.json()
    assert blocked_payload["activationGate"]["eligible"] is False
    blocker_codes = {
        blocker["code"] for blocker in blocked_payload["activationGate"]["blockers"]
    }
    assert "LAYOUT_RUN_NOT_SUCCEEDED" in blocker_codes

    activated = client.post(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-1/activate"
    )
    assert activated.status_code == 200
    activated_payload = activated.json()
    assert activated_payload["projection"]["activeLayoutRunId"] == "layout-run-1"
    assert activated_payload["projection"]["activeInputPreprocessRunId"] == "pre-run-1"
    assert activated_payload["run"]["id"] == "layout-run-1"
    assert activated_payload["run"]["isActiveProjection"] is True
    assert activated_payload["activationGate"]["eligible"] is True
    assert activated_payload["projection"]["downstreamTranscriptionState"] == "NOT_STARTED"

    active = client.get("/projects/project-1/documents/doc-2/layout-runs/active")
    assert active.status_code == 200
    assert active.json()["run"]["id"] == "layout-run-1"

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-missing-role"
    )
    denied_overview = client.get("/projects/project-1/documents/doc-2/layout/overview")
    assert denied_overview.status_code == 403

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "LAYOUT_RUN_CREATED" in event_types
    assert "LAYOUT_RUN_CANCELED" in event_types
    assert "LAYOUT_RUN_ACTIVATED" in event_types


def test_layout_activation_marks_downstream_stale_when_basis_is_superseded() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    fake._layout_projection["doc-2"] = replace(  # noqa: SLF001
        fake._layout_projection["doc-2"],  # noqa: SLF001
        downstream_transcription_state="CURRENT",
        downstream_transcription_invalidated_at=None,
        downstream_transcription_invalidated_reason=None,
    )
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-3"
    )

    activated = client.post(
        "/projects/project-1/documents/doc-2/layout-runs/layout-run-1/activate"
    )
    assert activated.status_code == 200
    payload = activated.json()
    assert payload["projection"]["downstreamTranscriptionState"] == "STALE"
    assert (
        "LAYOUT_ACTIVATION_SUPERSEDED"
        in payload["projection"]["downstreamTranscriptionInvalidatedReason"]
    )
    assert payload["activationGate"]["downstreamImpact"][
        "transcriptionStateAfterActivation"
    ] == "STALE"


def test_transcription_overview_triage_and_run_routes_emit_expected_audit_events() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    overview = client.get("/projects/project-1/documents/doc-2/transcription/overview")
    triage = client.get(
        "/projects/project-1/documents/doc-2/transcription/triage",
        params={"runId": "transcription-run-1", "confidenceBelow": 0.75},
    )
    runs = client.get("/projects/project-1/documents/doc-2/transcription-runs")
    active = client.get("/projects/project-1/documents/doc-2/transcription-runs/active")
    detail = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1"
    )
    status = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/status"
    )
    pages = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages"
    )
    lines = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-1/lines"
    )
    tokens = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-1/tokens"
    )

    assert overview.status_code == 200
    overview_payload = overview.json()
    assert overview_payload["activeRun"]["id"] == "transcription-run-1"
    assert overview_payload["latestRun"]["id"] == "transcription-run-2"
    assert overview_payload["projection"]["activeTranscriptionRunId"] == "transcription-run-1"

    assert triage.status_code == 200
    triage_payload = triage.json()
    assert triage_payload["run"]["id"] == "transcription-run-1"
    assert len(triage_payload["items"]) >= 1

    assert runs.status_code == 200
    runs_payload = runs.json()
    assert [item["id"] for item in runs_payload["items"]] == [
        "transcription-run-2",
        "transcription-run-1",
    ]
    assert runs_payload["nextCursor"] is None

    assert active.status_code == 200
    active_payload = active.json()
    assert active_payload["run"]["id"] == "transcription-run-1"
    assert active_payload["projection"]["activeTranscriptionRunId"] == "transcription-run-1"

    assert detail.status_code == 200
    assert detail.json()["id"] == "transcription-run-1"

    assert status.status_code == 200
    assert status.json()["runId"] == "transcription-run-1"

    assert pages.status_code == 200
    assert pages.json()["runId"] == "transcription-run-1"
    assert pages.json()["items"][0]["status"] == "SUCCEEDED"
    assert pages.json()["items"][0]["rawModelResponseKey"] is None
    assert pages.json()["items"][0]["rawModelResponseSha256"] is not None

    assert lines.status_code == 200
    assert lines.json()["runId"] == "transcription-run-1"
    line_items = lines.json()["items"]
    assert len(line_items) >= 1
    assert isinstance(line_items[0]["lineId"], str)
    assert isinstance(line_items[0]["tokenAnchorStatus"], str)

    assert tokens.status_code == 200
    assert tokens.json()["runId"] == "transcription-run-1"
    token_items = tokens.json()["items"]
    assert len(token_items) >= 1
    token_item = token_items[0]
    assert isinstance(token_item["tokenId"], str)
    assert isinstance(token_item["sourceKind"], str)
    assert isinstance(token_item["sourceRefId"], str)
    assert "/" not in token_item["sourceRefId"]
    assert "\\" not in token_item["sourceRefId"]

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "TRANSCRIPTION_OVERVIEW_VIEWED" in event_types
    assert "TRANSCRIPTION_TRIAGE_VIEWED" in event_types
    assert "TRANSCRIPTION_RUN_VIEWED" in event_types
    assert "TRANSCRIPTION_RUN_STATUS_VIEWED" in event_types
    assert "TRANSCRIPTION_ACTIVE_RUN_VIEWED" in event_types


def test_transcription_metrics_route_returns_aggregate_payload() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    response = client.get(
        "/projects/project-1/documents/doc-2/transcription/metrics",
        params={"runId": "transcription-run-1", "confidenceBelow": 0.8},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["id"] == "transcription-run-1"
    assert payload["pageCount"] >= 1
    assert payload["lineCount"] >= 1
    assert isinstance(payload["confidenceBands"]["HIGH"], int)
    assert isinstance(payload["fallbackInvocationCount"], int)
    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "TRANSCRIPTION_TRIAGE_VIEWED" in event_types


def test_transcription_triage_assignment_patch_enforces_rbac_and_emits_audit() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    denied = client.patch(
        "/projects/project-1/documents/doc-2/transcription/triage/pages/page-1/assignment",
        json={"runId": "transcription-run-1", "reviewerUserId": "user-3"},
    )
    assert denied.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    allowed = client.patch(
        "/projects/project-1/documents/doc-2/transcription/triage/pages/page-1/assignment",
        json={"runId": "transcription-run-1", "reviewerUserId": "user-3"},
    )
    assert allowed.status_code == 200
    allowed_payload = allowed.json()
    assert allowed_payload["run"]["id"] == "transcription-run-1"
    assert allowed_payload["item"]["pageId"] == "page-1"
    assert allowed_payload["item"]["reviewerAssignmentUserId"] == "user-3"
    assert isinstance(allowed_payload["item"]["rankingScore"], float)

    event_types = [entry.get("event_type") for entry in spy.recorded]
    assert "TRANSCRIPTION_TRIAGE_ASSIGNMENT_UPDATED" in event_types


def test_transcription_rescue_status_routes_and_resolution_patch_emit_audit() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    run_status_response = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/rescue-status"
    )
    assert run_status_response.status_code == 200
    run_status_payload = run_status_response.json()
    assert run_status_payload["runId"] == "transcription-run-1"
    assert run_status_payload["readyForActivation"] is True
    assert len(run_status_payload["pages"]) == 2

    page_status_response = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-2/rescue-sources"
    )
    assert page_status_response.status_code == 200
    page_status_payload = page_status_response.json()
    assert page_status_payload["pageId"] == "page-2"
    assert page_status_payload["readinessState"] == "READY"
    assert len(page_status_payload["rescueSources"]) == 2
    accepted = next(
        row
        for row in page_status_payload["rescueSources"]
        if row["candidateStatus"] == "ACCEPTED"
    )
    assert accepted["hasTranscriptionOutput"] is True
    assert accepted["sourceKind"] == "RESCUE_CANDIDATE"

    fake._transcription_tokens[("transcription-run-1", "page-2")] = [  # noqa: SLF001
        row
        for row in fake._transcription_tokens[("transcription-run-1", "page-2")]  # noqa: SLF001
        if row.source_kind == "LINE"
    ]
    blocked_run_status_response = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/rescue-status"
    )
    assert blocked_run_status_response.status_code == 200
    blocked_payload = blocked_run_status_response.json()
    assert blocked_payload["readyForActivation"] is False
    blocked_page = next(
        row for row in blocked_payload["pages"] if row["pageId"] == "page-2"
    )
    assert "RESCUE_SOURCE_UNTRANSCRIBED" in blocked_page["blockerReasonCodes"]

    patched_resolution = client.patch(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-2/rescue-resolution",
        json={
            "resolutionStatus": "MANUAL_REVIEW_RESOLVED",
            "resolutionReason": "Escalated and verified manually."
        },
    )
    assert patched_resolution.status_code == 200
    patched_payload = patched_resolution.json()
    assert patched_payload["readinessState"] == "READY"
    assert patched_payload["resolutionStatus"] == "MANUAL_REVIEW_RESOLVED"
    assert patched_payload["resolutionUpdatedBy"] == "user-3"

    event_types = [entry.get("event_type") for entry in spy.recorded]
    assert "TRANSCRIPTION_RESCUE_STATUS_VIEWED" in event_types
    assert "TRANSCRIPTION_RESCUE_RESOLUTION_UPDATED" in event_types


def test_transcription_rescue_resolution_patch_enforces_rbac() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    response = client.patch(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-2/rescue-resolution",
        json={"resolutionStatus": "MANUAL_REVIEW_RESOLVED"},
    )
    assert response.status_code == 403


def test_transcription_activation_blocked_when_rescue_unresolved() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    fake._transcription_tokens[("transcription-run-1", "page-2")] = [  # noqa: SLF001
        row
        for row in fake._transcription_tokens[("transcription-run-1", "page-2")]  # noqa: SLF001
        if row.source_kind == "LINE"
    ]

    response = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/activate"
    )
    assert response.status_code == 409
    payload = response.json()
    assert "RESCUE_UNRESOLVED" in payload["detail"]
    assert "RESCUE_SOURCE_UNTRANSCRIBED" in payload["blockerCodes"]
    assert payload["rescueStatus"]["readyForActivation"] is False

    event_types = [entry.get("event_type") for entry in spy.recorded]
    assert "TRANSCRIPTION_RUN_ACTIVATION_BLOCKED" in event_types


def test_transcription_mutations_enforce_rbac_and_projection_rules() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    denied_create = client.post("/projects/project-1/documents/doc-2/transcription-runs")
    assert denied_create.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    created = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs",
        json={
            "inputPreprocessRunId": "pre-run-2",
            "inputLayoutRunId": "layout-run-2",
            "engine": "VLM_LINE_CONTEXT",
        },
    )
    assert created.status_code == 201
    created_payload = created.json()
    assert created_payload["status"] == "QUEUED"
    assert created_payload["inputPreprocessRunId"] == "pre-run-2"
    assert created_payload["inputLayoutRunId"] == "layout-run-2"

    canceled = client.post(
        f"/projects/project-1/documents/doc-2/transcription-runs/{created_payload['id']}/cancel"
    )
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "CANCELED"

    activate_non_succeeded = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-2/activate"
    )
    assert activate_non_succeeded.status_code == 409

    activate_succeeded = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/activate"
    )
    assert activate_succeeded.status_code == 200
    activated_payload = activate_succeeded.json()
    assert activated_payload["projection"]["activeTranscriptionRunId"] == "transcription-run-1"
    assert activated_payload["run"]["id"] == "transcription-run-1"
    assert activated_payload["run"]["isActiveProjection"] is True

    stale_line = fake._transcription_lines[("transcription-run-1", "page-2")][0]  # noqa: SLF001
    fake._transcription_lines[("transcription-run-1", "page-2")][0] = replace(  # noqa: SLF001
        stale_line,
        token_anchor_status="REFRESH_REQUIRED",
    )
    blocked_by_anchor = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/activate"
    )
    assert blocked_by_anchor.status_code == 409
    assert "token-anchor" in blocked_by_anchor.json()["detail"].lower()
    assert "TOKEN_ANCHOR_STALE" in blocked_by_anchor.json()["blockerCodes"]

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "TRANSCRIPTION_RUN_CREATED" in event_types
    assert "TRANSCRIPTION_RUN_CANCELED" in event_types
    assert "TRANSCRIPTION_RUN_ACTIVATED" in event_types
    assert "TRANSCRIPTION_RUN_ACTIVATION_BLOCKED" in event_types


def test_transcription_line_correction_and_variant_routes_emit_expected_audit_events() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")

    correction = client.patch(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-1/lines/line-1",
        json={
            "textDiplomatic": "Dear diary!",
            "versionEtag": "line-etag-1",
            "editReason": "Punctuation normalization",
        },
    )
    assert correction.status_code == 200
    correction_payload = correction.json()
    assert correction_payload["runId"] == "transcription-run-1"
    assert correction_payload["pageId"] == "page-1"
    assert correction_payload["lineId"] == "line-1"
    assert correction_payload["textChanged"] is True
    assert correction_payload["line"]["tokenAnchorStatus"] == "REFRESH_REQUIRED"
    assert correction_payload["activeVersion"]["textDiplomatic"] == "Dear diary!"
    assert correction_payload["downstreamRedactionInvalidated"] is True
    assert correction_payload["downstreamRedactionState"] == "STALE"
    assert (
        "TRANSCRIPT_CORRECTION_ACTIVE_BASIS_CHANGED"
        in correction_payload["downstreamRedactionInvalidatedReason"]
    )

    layers = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-1/variant-layers",
        params={"variantKind": "NORMALISED"},
    )
    assert layers.status_code == 200
    layers_payload = layers.json()
    assert layers_payload["runId"] == "transcription-run-1"
    assert layers_payload["variantKind"] == "NORMALISED"
    assert len(layers_payload["items"]) == 1
    assert layers_payload["items"][0]["suggestions"][0]["id"] == "variant-suggestion-1"

    decision = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-1/variant-layers/NORMALISED/suggestions/variant-suggestion-1/decision",
        json={"decision": "ACCEPT", "reason": "Apply normalised casing."},
    )
    assert decision.status_code == 200
    decision_payload = decision.json()
    assert decision_payload["runId"] == "transcription-run-1"
    assert decision_payload["variantKind"] == "NORMALISED"
    assert decision_payload["suggestion"]["status"] == "ACCEPTED"
    assert decision_payload["event"]["decision"] == "ACCEPT"
    assert decision_payload["event"]["fromStatus"] == "PENDING"
    assert decision_payload["event"]["toStatus"] == "ACCEPTED"

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "TRANSCRIPT_LINE_CORRECTED" in event_types
    assert "TRANSCRIPT_DOWNSTREAM_INVALIDATED" in event_types
    assert "TRANSCRIPT_VARIANT_LAYER_VIEWED" in event_types
    assert "TRANSCRIPT_ASSIST_DECISION_RECORDED" in event_types


def test_transcription_line_correction_conflict_emits_audit_event() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")

    response = client.patch(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-1/lines/line-1",
        json={
            "textDiplomatic": "Dear diary?",
            "versionEtag": "line-etag-stale",
        },
    )
    assert response.status_code == 409
    assert "stale" in response.json()["detail"].lower()
    assert any(
        entry.get("event_type") == "TRANSCRIPT_EDIT_CONFLICT_DETECTED"
        for entry in spy.recorded
    )


def test_transcription_workspace_lines_request_emits_workspace_audit_event() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")

    response = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-1/lines",
        params={
            "workspaceView": "true",
            "lineId": "line-1",
            "tokenId": "token-1",
            "sourceKind": "LINE",
            "sourceRefId": "line-1",
        },
    )
    assert response.status_code == 200

    workspace_event = next(
        (
            entry
            for entry in spy.recorded
            if entry.get("event_type") == "TRANSCRIPTION_WORKSPACE_VIEWED"
        ),
        None,
    )
    assert workspace_event is not None
    assert workspace_event["metadata"]["run_id"] == "transcription-run-1"
    assert workspace_event["metadata"]["document_id"] == "doc-2"
    assert workspace_event["metadata"]["page_id"] == "page-1"
    assert workspace_event["metadata"]["line_id"] == "line-1"
    assert workspace_event["metadata"]["token_id"] == "token-1"
    assert workspace_event["metadata"]["source_kind"] == "LINE"
    assert workspace_event["metadata"]["source_ref_id"] == "line-1"


def test_transcription_variant_and_correction_mutations_enforce_rbac() -> None:
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")

    view_layers = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-1/variant-layers"
    )
    assert view_layers.status_code == 200

    denied_correction = client.patch(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-1/lines/line-1",
        json={"textDiplomatic": "Denied", "versionEtag": "line-etag-1"},
    )
    assert denied_correction.status_code == 403

    denied_decision = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-1/variant-layers/NORMALISED/suggestions/variant-suggestion-1/decision",
        json={"decision": "REJECT"},
    )
    assert denied_decision.status_code == 403


def test_transcription_fallback_compare_and_decision_routes_emit_expected_audit_events() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")

    fallback_response = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/fallback",
        json={
            "baseRunId": "transcription-run-1",
            "engine": "KRAKEN_LINE",
        },
    )
    assert fallback_response.status_code == 201
    fallback_payload = fallback_response.json()
    assert fallback_payload["engine"] == "KRAKEN_LINE"
    assert fallback_payload["confidenceBasis"] == "FALLBACK_DISAGREEMENT"
    fallback_run_id = fallback_payload["id"]

    status_response = client.get(
        f"/projects/project-1/documents/doc-2/transcription-runs/{fallback_run_id}/status"
    )
    assert status_response.status_code == 200
    assert status_response.json()["runId"] == fallback_run_id

    compare_response = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/compare",
        params={
            "baseRunId": "transcription-run-1",
            "candidateRunId": fallback_run_id,
        },
    )
    assert compare_response.status_code == 200
    compare_payload = compare_response.json()
    assert compare_payload["baseRun"]["id"] == "transcription-run-1"
    assert compare_payload["candidateRun"]["id"] == fallback_run_id
    assert compare_payload["candidateEngineMetadata"]["engine"] == "KRAKEN_LINE"
    assert compare_payload["items"][0]["lineDiffs"]

    decision_create = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/compare/decisions",
        json={
            "baseRunId": "transcription-run-1",
            "candidateRunId": fallback_run_id,
            "items": [
                {
                    "pageId": "page-1",
                    "lineId": "line-1",
                    "decision": "KEEP_BASE",
                    "decisionReason": "Primary transcription remains clearer.",
                }
            ],
        },
    )
    assert decision_create.status_code == 200
    created_decision = decision_create.json()["items"][0]
    assert created_decision["decision"] == "KEEP_BASE"
    decision_etag = created_decision["decisionEtag"]

    decision_update = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/compare/decisions",
        json={
            "baseRunId": "transcription-run-1",
            "candidateRunId": fallback_run_id,
            "items": [
                {
                    "pageId": "page-1",
                    "lineId": "line-1",
                    "decision": "PROMOTE_CANDIDATE",
                    "decisionReason": "Fallback variant improves readability.",
                    "decisionEtag": decision_etag,
                }
            ],
        },
    )
    assert decision_update.status_code == 200
    updated_decision = decision_update.json()["items"][0]
    assert updated_decision["decision"] == "PROMOTE_CANDIDATE"
    assert updated_decision["decisionEtag"] != decision_etag

    stale_update = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/compare/decisions",
        json={
            "baseRunId": "transcription-run-1",
            "candidateRunId": fallback_run_id,
            "items": [
                {
                    "pageId": "page-1",
                    "lineId": "line-1",
                    "decision": "KEEP_BASE",
                    "decisionEtag": decision_etag,
                }
            ],
        },
    )
    assert stale_update.status_code == 409

    cancel_response = client.post(
        f"/projects/project-1/documents/doc-2/transcription-runs/{fallback_run_id}/cancel"
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "CANCELED"

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "TRANSCRIPTION_FALLBACK_RUN_CREATED" in event_types
    assert "TRANSCRIPTION_FALLBACK_RUN_STATUS_VIEWED" in event_types
    assert "TRANSCRIPTION_RUN_COMPARE_VIEWED" in event_types
    assert "TRANSCRIPTION_COMPARE_DECISION_RECORDED" in event_types
    assert "TRANSCRIPTION_FALLBACK_RUN_CANCELED" in event_types


def test_transcription_compare_supports_page_line_token_filters_and_audit_metadata() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")

    response = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/compare",
        params={
            "baseRunId": "transcription-run-1",
            "candidateRunId": "transcription-run-2",
            "page": 1,
            "lineId": "line-1",
            "tokenId": "token-1",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert all(item["pageIndex"] == 0 for item in payload["items"])
    assert all(
        diff["lineId"] == "line-1"
        for item in payload["items"]
        for diff in item["lineDiffs"]
    )
    assert all(
        diff["tokenId"] == "token-1"
        for item in payload["items"]
        for diff in item["tokenDiffs"]
    )
    assert isinstance(payload["compareDecisionSnapshotHash"], str)
    assert payload["compareDecisionCount"] == 0
    assert payload["compareDecisionEventCount"] == 0

    compare_event = next(
        entry
        for entry in spy.recorded
        if entry.get("event_type") == "TRANSCRIPTION_RUN_COMPARE_VIEWED"
    )
    assert compare_event["metadata"]["page"] == 1
    assert compare_event["metadata"]["line_id"] == "line-1"
    assert compare_event["metadata"]["token_id"] == "token-1"
    assert compare_event["metadata"]["compare_decision_count"] == 0
    assert compare_event["metadata"]["compare_decision_event_count"] == 0


def test_transcription_line_version_routes_return_lineage_and_emit_audit_events() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")

    history = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/pages/page-1/lines/line-1/versions"
    )
    assert history.status_code == 200
    history_payload = history.json()
    assert history_payload["lineId"] == "line-1"
    assert len(history_payload["versions"]) == 1
    assert history_payload["versions"][0]["sourceType"] == "ENGINE_OUTPUT"
    assert history_payload["versions"][0]["isActive"] is True

    version_id = history_payload["versions"][0]["version"]["id"]
    version = client.get(
        (
            "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1/"
            f"pages/page-1/lines/line-1/versions/{version_id}"
        )
    )
    assert version.status_code == 200
    version_payload = version.json()
    assert version_payload["version"]["id"] == version_id
    assert version_payload["sourceType"] == "ENGINE_OUTPUT"

    event_types = [entry.get("event_type") for entry in spy.recorded]
    assert "TRANSCRIPT_LINE_VERSION_HISTORY_VIEWED" in event_types
    assert "TRANSCRIPT_LINE_VERSION_VIEWED" in event_types
    history_event = next(
        entry
        for entry in spy.recorded
        if entry.get("event_type") == "TRANSCRIPT_LINE_VERSION_HISTORY_VIEWED"
    )
    assert history_event["metadata"]["line_id"] == "line-1"
    version_event = next(
        entry
        for entry in spy.recorded
        if entry.get("event_type") == "TRANSCRIPT_LINE_VERSION_VIEWED"
    )
    assert version_event["metadata"]["version_id"] == version_id
    assert version_event["metadata"]["source_type"] == "ENGINE_OUTPUT"


def test_transcription_compare_finalize_creates_review_composed_run_and_keeps_sources_immutable() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")

    before_runs = client.get("/projects/project-1/documents/doc-2/transcription-runs")
    assert before_runs.status_code == 200
    before_items = before_runs.json()["items"]
    before_ids = [item["id"] for item in before_items]

    decision = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/compare/decisions",
        json={
            "baseRunId": "transcription-run-1",
            "candidateRunId": "transcription-run-2",
            "items": [
                {
                    "pageId": "page-1",
                    "lineId": "line-1",
                    "decision": "PROMOTE_CANDIDATE",
                    "decisionReason": "Candidate line is clearer.",
                }
            ],
        },
    )
    assert decision.status_code == 200

    compare = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/compare",
        params={
            "baseRunId": "transcription-run-1",
            "candidateRunId": "transcription-run-2",
        },
    )
    assert compare.status_code == 200
    compare_hash = compare.json()["compareDecisionSnapshotHash"]

    finalize = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/compare/finalize",
        json={
            "baseRunId": "transcription-run-1",
            "candidateRunId": "transcription-run-2",
            "pageIds": ["page-1"],
            "expectedCompareDecisionSnapshotHash": compare_hash,
        },
    )
    assert finalize.status_code == 200
    finalize_payload = finalize.json()
    assert finalize_payload["baseRunId"] == "transcription-run-1"
    assert finalize_payload["candidateRunId"] == "transcription-run-2"
    assert finalize_payload["pageScope"] == ["page-1"]
    assert finalize_payload["compareDecisionSnapshotHash"] == compare_hash
    assert finalize_payload["composedRun"]["engine"] == "REVIEW_COMPOSED"

    composed_run_id = finalize_payload["composedRun"]["id"]
    assert composed_run_id not in before_ids

    after_runs = client.get("/projects/project-1/documents/doc-2/transcription-runs")
    assert after_runs.status_code == 200
    after_items = after_runs.json()["items"]
    after_ids = [item["id"] for item in after_items]
    assert len(after_items) == len(before_items) + 1
    for run_id in before_ids:
        assert run_id in after_ids

    base_run = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-1"
    )
    candidate_run = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/transcription-run-2"
    )
    composed_run = client.get(
        f"/projects/project-1/documents/doc-2/transcription-runs/{composed_run_id}"
    )
    assert base_run.status_code == 200
    assert candidate_run.status_code == 200
    assert composed_run.status_code == 200
    assert base_run.json()["engine"] == "VLM_LINE_CONTEXT"
    assert candidate_run.json()["engine"] == "VLM_LINE_CONTEXT"
    assert composed_run.json()["engine"] == "REVIEW_COMPOSED"
    assert composed_run.json()["paramsJson"]["baseRunId"] == "transcription-run-1"
    assert composed_run.json()["paramsJson"]["candidateRunId"] == "transcription-run-2"
    assert (
        composed_run.json()["paramsJson"]["compareDecisionSnapshotHash"] == compare_hash
    )

    finalize_event = next(
        entry
        for entry in spy.recorded
        if entry.get("event_type") == "TRANSCRIPTION_COMPARE_FINALIZED"
    )
    assert finalize_event["object_id"] == composed_run_id
    assert finalize_event["metadata"]["base_run_id"] == "transcription-run-1"
    assert finalize_event["metadata"]["candidate_run_id"] == "transcription-run-2"
    assert finalize_event["metadata"]["page_scope_count"] == 1


def test_transcription_compare_finalize_rejects_stale_snapshot_hash() -> None:
    fake = FakeDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")

    before_runs = client.get("/projects/project-1/documents/doc-2/transcription-runs")
    assert before_runs.status_code == 200
    before_count = len(before_runs.json()["items"])

    decision = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/compare/decisions",
        json={
            "baseRunId": "transcription-run-1",
            "candidateRunId": "transcription-run-2",
            "items": [
                {
                    "pageId": "page-1",
                    "lineId": "line-1",
                    "decision": "KEEP_BASE",
                }
            ],
        },
    )
    assert decision.status_code == 200

    finalize = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/compare/finalize",
        json={
            "baseRunId": "transcription-run-1",
            "candidateRunId": "transcription-run-2",
            "expectedCompareDecisionSnapshotHash": "deadbeef",
        },
    )
    assert finalize.status_code == 409
    assert "stale" in finalize.json()["detail"].lower()

    after_runs = client.get("/projects/project-1/documents/doc-2/transcription-runs")
    assert after_runs.status_code == 200
    assert len(after_runs.json()["items"]) == before_count


def test_transcription_compare_rejects_basis_mismatch() -> None:
    fake = FakeDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")

    created = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs",
        json={
            "inputPreprocessRunId": "pre-run-1",
            "inputLayoutRunId": "layout-run-1",
            "engine": "VLM_LINE_CONTEXT",
        },
    )
    assert created.status_code == 201
    mismatched_run_id = created.json()["id"]

    compare = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/compare",
        params={
            "baseRunId": "transcription-run-1",
            "candidateRunId": mismatched_run_id,
        },
    )
    assert compare.status_code == 409
    assert "share preprocess/layout basis" in compare.json()["detail"]


def test_transcription_fallback_and_compare_mutations_enforce_rbac() -> None:
    fake = FakeDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    fallback_denied = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/fallback",
        json={"baseRunId": "transcription-run-1"},
    )
    assert fallback_denied.status_code == 403

    compare_allowed = client.get(
        "/projects/project-1/documents/doc-2/transcription-runs/compare",
        params={
            "baseRunId": "transcription-run-1",
            "candidateRunId": "transcription-run-2",
        },
    )
    assert compare_allowed.status_code == 200

    compare_decision_denied = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/compare/decisions",
        json={
            "baseRunId": "transcription-run-1",
            "candidateRunId": "transcription-run-2",
            "items": [
                {
                    "pageId": "page-1",
                    "lineId": "line-1",
                    "decision": "KEEP_BASE",
                }
            ],
        },
    )
    assert compare_decision_denied.status_code == 403

    compare_finalize_denied = client.post(
        "/projects/project-1/documents/doc-2/transcription-runs/compare/finalize",
        json={
            "baseRunId": "transcription-run-1",
            "candidateRunId": "transcription-run-2",
        },
    )
    assert compare_finalize_denied.status_code == 403

def test_retry_extraction_enforces_access_and_creates_lineage() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    retry_response = client.post("/projects/project-1/documents/doc-3/retry-extraction")
    assert retry_response.status_code == 200
    payload = retry_response.json()
    assert payload["documentId"] == "doc-3"
    assert payload["runKind"] == "EXTRACTION"
    assert payload["attemptNumber"] == 2
    assert payload["supersedesProcessingRunId"] == "run-6"
    assert payload["supersededByProcessingRunId"] is None
    assert payload["active"] is True

    previous = client.get("/projects/project-1/documents/doc-3/processing-runs/run-6")
    assert previous.status_code == 200
    assert previous.json()["supersededByProcessingRunId"] == payload["id"]

    denied_principal = lambda: _principal(user_id="user-2")
    app.dependency_overrides[require_authenticated_user] = denied_principal
    denied = client.post("/projects/project-1/documents/doc-3/retry-extraction")
    assert denied.status_code == 403

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "DOCUMENT_PAGE_EXTRACTION_RETRY_REQUESTED" in event_types


def test_resumable_upload_session_endpoints_resume_complete_and_cancel() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake
    app.dependency_overrides[get_job_service] = lambda: FakeJobService()

    create_response = client.post(
        "/projects/project-1/documents/import-sessions",
        json={
            "originalFilename": "chunked.pdf",
            "expectedTotalBytes": 8,
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    session_id = created["sessionId"]
    assert created["uploadStatus"] == "ACTIVE"
    assert created["nextChunkIndex"] == 0

    first_chunk = client.post(
        f"/projects/project-1/documents/import-sessions/{session_id}/chunks",
        params={"chunkIndex": 0},
        files={"file": ("chunk-0.bin", b"ABCD", "application/octet-stream")},
    )
    assert first_chunk.status_code == 200
    assert first_chunk.json()["lastChunkIndex"] == 0
    assert first_chunk.json()["nextChunkIndex"] == 1
    assert first_chunk.json()["bytesReceived"] == 4

    resume_chunk = client.post(
        f"/projects/project-1/documents/import-sessions/{session_id}/chunks",
        params={"chunkIndex": 0},
        files={"file": ("chunk-0.bin", b"ABCD", "application/octet-stream")},
    )
    assert resume_chunk.status_code == 200
    assert resume_chunk.json()["bytesReceived"] == 4

    out_of_order = client.post(
        f"/projects/project-1/documents/import-sessions/{session_id}/chunks",
        params={"chunkIndex": 2},
        files={"file": ("chunk-2.bin", b"ZZZZ", "application/octet-stream")},
    )
    assert out_of_order.status_code == 409

    second_chunk = client.post(
        f"/projects/project-1/documents/import-sessions/{session_id}/chunks",
        params={"chunkIndex": 1},
        files={"file": ("chunk-1.bin", b"EFGH", "application/octet-stream")},
    )
    assert second_chunk.status_code == 200
    assert second_chunk.json()["bytesReceived"] == 8

    complete = client.post(
        f"/projects/project-1/documents/import-sessions/{session_id}/complete"
    )
    assert complete.status_code == 200
    completed_payload = complete.json()
    assert completed_payload["uploadStatus"] == "COMPLETED"
    assert completed_payload["importStatus"] == "QUEUED"
    assert completed_payload["documentStatus"] == "QUEUED"
    assert completed_payload["cancelAllowed"] is False

    second_create = client.post(
        "/projects/project-1/documents/import-sessions",
        json={"originalFilename": "cancelled.pdf"},
    )
    second_session_id = second_create.json()["sessionId"]
    cancel_response = client.post(
        f"/projects/project-1/documents/import-sessions/{second_session_id}/cancel"
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["uploadStatus"] == "CANCELED"
    assert cancel_response.json()["importStatus"] == "CANCELED"
    assert cancel_response.json()["documentStatus"] == "CANCELED"

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "DOCUMENT_UPLOAD_STARTED" in event_types
    assert "DOCUMENT_STORED" in event_types


def test_page_routes_return_metadata_patch_rotation_and_stream_images() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    list_response = client.get("/projects/project-1/documents/doc-2/pages")
    assert list_response.status_code == 200
    assert [item["pageIndex"] for item in list_response.json()["items"]] == [0, 1]

    detail_response = client.get("/projects/project-1/documents/doc-2/pages/page-1")
    assert detail_response.status_code == 200
    assert detail_response.json()["derivedImageAvailable"] is True
    assert detail_response.json()["thumbnailAvailable"] is True

    patch_response = client.patch(
        "/projects/project-1/documents/doc-2/pages/page-1",
        json={"viewerRotation": 90},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["viewerRotation"] == 90

    readback_response = client.get("/projects/project-1/documents/doc-2/pages/page-1")
    assert readback_response.status_code == 200
    assert readback_response.json()["viewerRotation"] == 90

    full_image_response = client.get(
        "/projects/project-1/documents/doc-2/pages/page-1/image?variant=full"
    )
    assert full_image_response.status_code == 200
    assert full_image_response.headers["cache-control"] == "private, no-cache, max-age=0, must-revalidate"
    assert full_image_response.headers["content-type"] == "image/png"
    assert full_image_response.headers["etag"] == '"sha-page-0"'
    assert "content-disposition" not in full_image_response.headers
    assert full_image_response.headers["x-content-type-options"] == "nosniff"
    assert (
        full_image_response.headers["cross-origin-resource-policy"] == "same-origin"
    )
    assert "authorization" in full_image_response.headers["vary"].lower()
    assert full_image_response.content == b"fixture-page-image"

    revalidated_full_image = client.get(
        "/projects/project-1/documents/doc-2/pages/page-1/image?variant=full",
        headers={"If-None-Match": full_image_response.headers["etag"]},
    )
    assert revalidated_full_image.status_code == 304
    assert revalidated_full_image.content == b""
    assert revalidated_full_image.headers["etag"] == '"sha-page-0"'

    thumb_image_response = client.get(
        "/projects/project-1/documents/doc-2/pages/page-1/image?variant=thumb"
    )
    assert thumb_image_response.status_code == 200
    assert thumb_image_response.headers["cache-control"] == "private, no-cache, max-age=0, must-revalidate"
    assert thumb_image_response.headers["content-type"] == "image/jpeg"
    assert thumb_image_response.headers["etag"] == '"sha-thumb-0"'
    assert "content-disposition" not in thumb_image_response.headers
    assert thumb_image_response.headers["x-content-type-options"] == "nosniff"
    assert (
        thumb_image_response.headers["cross-origin-resource-policy"] == "same-origin"
    )
    assert "authorization" in thumb_image_response.headers["vary"].lower()
    assert thumb_image_response.content == b"fixture-page-thumb"

    variants_response = client.get(
        "/projects/project-1/documents/doc-2/pages/page-1/variants"
    )
    assert variants_response.status_code == 200
    variants_payload = variants_response.json()
    assert variants_payload["requestedRunId"] is None
    assert variants_payload["resolvedRunId"] == "pre-run-2"
    assert variants_payload["run"]["id"] == "pre-run-2"
    variant_index = {item["variant"]: item for item in variants_payload["variants"]}
    assert variant_index["ORIGINAL"]["available"] is True
    assert variant_index["PREPROCESSED_GRAY"]["available"] is True
    assert variant_index["PREPROCESSED_GRAY"]["runId"] == "pre-run-2"
    assert variant_index["PREPROCESSED_GRAY"]["qualityGateStatus"] == "PASS"
    assert variant_index["PREPROCESSED_BIN"]["available"] is False

    preprocessed_gray_response = client.get(
        "/projects/project-1/documents/doc-2/pages/page-1/image?variant=preprocessed_gray&runId=pre-run-2"
    )
    assert preprocessed_gray_response.status_code == 200
    assert preprocessed_gray_response.headers["content-type"] == "image/png"
    assert preprocessed_gray_response.content == b"fixture-preprocess-gray"

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "PAGE_METADATA_VIEWED" in event_types
    assert "PAGE_IMAGE_VIEWED" in event_types
    assert "PAGE_THUMBNAIL_VIEWED" in event_types
    assert "PREPROCESS_VARIANT_ACCESSED" in event_types


def test_page_image_route_denies_cross_project_access() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    response = client.get(
        "/projects/project-denied/documents/doc-2/pages/page-1/image?variant=full"
    )

    assert response.status_code == 403


def test_page_variants_route_fails_without_active_or_selected_run() -> None:
    fake = FakeDocumentService()
    fake._preprocess_projection.pop("doc-2", None)
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    response = client.get("/projects/project-1/documents/doc-2/pages/page-1/variants")

    assert response.status_code == 409


def test_raw_original_download_route_is_not_exposed() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    response = client.get("/projects/project-1/documents/doc-2/original")
    assert response.status_code == 404


def test_page_route_returns_not_found_for_unknown_page() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    response = client.get("/projects/project-1/documents/doc-2/pages/page-missing")
    assert response.status_code == 404


def test_document_route_returns_not_found_for_unknown_document() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    response = client.get("/projects/project-1/documents/missing-document")
    assert response.status_code == 404


def test_document_route_returns_forbidden_for_non_member_project() -> None:
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()

    response = client.get("/projects/project-denied/documents")

    assert response.status_code == 403
    assert any(entry.get("event_type") == "ACCESS_DENIED" for entry in spy.recorded)


def test_upload_route_rejects_unsupported_extension() -> None:
    fake = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    response = client.post(
        "/projects/project-1/documents/import",
        files={"file": ("malware.exe", b"MZ\x00\x00", "application/octet-stream")},
    )

    assert response.status_code == 422


def test_upload_route_rejects_mismatched_magic_type() -> None:
    fake = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    response = client.post(
        "/projects/project-1/documents/import",
        files={
            "file": (
                "not-a-pdf.pdf",
                b"\x89PNG\r\n\x1a\nthis-is-a-png",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422


def test_upload_route_enforces_max_file_size() -> None:
    fake = FakeDocumentService(max_upload_bytes=16)
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    response = client.post(
        "/projects/project-1/documents/import",
        files={"file": ("large.pdf", b"%PDF-1.7 " + b"A" * 100, "application/pdf")},
    )

    assert response.status_code == 422


def test_upload_route_enforces_project_quota() -> None:
    fake = FakeDocumentService(project_quota_bytes=125_010)
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    response = client.post(
        "/projects/project-1/documents/import",
        files={"file": ("quota.pdf", b"%PDF-1.7\n1234567890", "application/pdf")},
    )

    assert response.status_code == 413


def test_upload_route_denies_non_member() -> None:
    spy = SpyAuditService()
    fake = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    response = client.post(
        "/projects/project-denied/documents/import",
        files={"file": ("doc.pdf", b"%PDF-1.7\nok", "application/pdf")},
    )

    assert response.status_code == 403
    assert any(entry.get("event_type") == "ACCESS_DENIED" for entry in spy.recorded)


def test_upload_status_and_cancel_flow() -> None:
    fake = FakeDocumentService(auto_scan=False)
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    upload_response = client.post(
        "/projects/project-1/documents/import",
        files={"file": ("diary.pdf", b"%PDF-1.7\nentry", "application/pdf")},
    )
    assert upload_response.status_code == 200
    payload = upload_response.json()
    assert payload["importStatus"] == "QUEUED"
    assert payload["cancelAllowed"] is True

    import_id = payload["importId"]
    status_response = client.get(f"/projects/project-1/document-imports/{import_id}")
    assert status_response.status_code == 200
    assert status_response.json()["importStatus"] == "QUEUED"

    cancel_response = client.post(f"/projects/project-1/document-imports/{import_id}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["importStatus"] == "CANCELED"
    assert cancel_response.json()["documentStatus"] == "CANCELED"

    second_cancel_response = client.post(
        f"/projects/project-1/document-imports/{import_id}/cancel"
    )
    assert second_cancel_response.status_code == 409
    assert any(
        entry.get("event_type") == "DOCUMENT_UPLOAD_CANCELED" for entry in spy.recorded
    )


def test_upload_background_scan_progression_and_audit() -> None:
    fake = FakeDocumentService(auto_scan=True)
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake
    app.dependency_overrides[get_job_service] = lambda: FakeJobService()

    upload_response = client.post(
        "/projects/project-1/documents/import",
        files={"file": ("scan.pdf", b"%PDF-1.7\nscan", "application/pdf")},
    )

    assert upload_response.status_code == 200
    import_id = upload_response.json()["importId"]
    status_response = client.get(f"/projects/project-1/document-imports/{import_id}")
    assert status_response.status_code == 200
    assert status_response.json()["importStatus"] == "ACCEPTED"
    assert fake.scan_transitions[import_id] == ["QUEUED", "SCANNING", "ACCEPTED"]

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "DOCUMENT_UPLOAD_STARTED" in event_types
    assert "DOCUMENT_STORED" in event_types
    assert "DOCUMENT_SCAN_STARTED" in event_types
    assert "DOCUMENT_SCAN_PASSED" in event_types
