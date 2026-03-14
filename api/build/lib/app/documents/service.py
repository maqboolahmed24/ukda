from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass, field, replace
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Mapping, Sequence
from uuid import uuid4

from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.documents.models import (
    ApprovedModelRecord,
    ApprovedModelRole,
    ApprovedModelServingInterface,
    ApprovedModelStatus,
    ApprovedModelType,
    ProjectModelAssignmentRecord,
    TrainingDatasetRecord,
    DocumentTranscriptionProjectionRecord,
    LineTranscriptionResultRecord,
    PageTranscriptionResultRecord,
    TokenTranscriptionResultRecord,
    TranscriptionConfidenceBasis,
    TranscriptionRunEngine,
    TranscriptionRunRecord,
    TranscriptionRunStatus,
    TranscriptionTokenSourceKind,
    DocumentLayoutProjectionRecord,
    LayoutActivationGateRecord,
    DocumentPreprocessProjectionRecord,
    DocumentImportRecord,
    DocumentImportSnapshot,
    DocumentListFilters,
    DocumentPageRecord,
    LayoutRecallCheckRecord,
    LayoutRescueCandidateRecord,
    LayoutRunRecord,
    LayoutLineArtifactRecord,
    PageLayoutResultRecord,
    PageLayoutResultStatus,
    PageRecallStatus,
    PagePreprocessResultRecord,
    PreprocessDownstreamBasisReferencesRecord,
    PreprocessPageResultStatus,
    PreprocessQualityGateStatus,
    PreprocessRunScope,
    PreprocessRunRecord,
    PreprocessRunStatus,
    DocumentProcessingRunRecord,
    DocumentUploadSessionRecord,
    DocumentRecord,
)
from app.documents.layout_contract import (
    LayoutCanonicalPage,
    LayoutLine,
    LayoutRegion,
    LayoutContractValidationError,
    build_layout_canonical_page,
    canonical_json_bytes,
    derive_layout_overlay,
    parse_layout_pagexml,
    serialize_layout_pagexml,
    validate_layout_overlay_payload,
)
from app.documents.reading_order import (
    ReadingOrderGroup,
    build_reading_order_edges,
    infer_reading_order,
    normalize_reading_order_groups,
)
from app.documents.preprocessing import (
    PreprocessPipelineError,
    canonicalize_params_dict,
    expand_profile_params,
    get_preprocess_profile_definition,
    normalize_profile_id,
)
from app.documents.extraction import (
    placeholder_jpeg_bytes,
    placeholder_png_bytes,
    resolve_source_metadata,
)
from app.documents.scanner import (
    DocumentScanner,
    DocumentScannerUnavailableError,
    get_document_scanner,
)
from app.documents.storage import DocumentStorage, DocumentStorageError, get_document_storage
from app.documents.store import (
    DocumentLayoutRunConflictError,
    DocumentModelAssignmentConflictError as DocumentStoreModelAssignmentConflictError,
    DocumentModelCatalogConflictError as DocumentStoreModelCatalogConflictError,
    DocumentNotFoundError,
    DocumentPreprocessRunConflictError,
    DocumentProcessingRunConflictError,
    DocumentTranscriptionRunConflictError,
    DocumentStore,
    DocumentStoreUnavailableError,
    DocumentUploadSessionConflictError,
    DocumentUploadSessionNotFoundError,
)
from app.documents.validation import (
    DocumentUploadValidationError,
    parse_allowed_extension,
    validate_extension_matches_magic,
)
from app.projects.service import ProjectAccessDeniedError, ProjectService, get_project_service

_UPLOAD_CHUNK_BYTES = 1024 * 1024
_MAGIC_PROBE_BYTES = 64
_ALLOWED_UPLOAD_ROLES = {"PROJECT_LEAD", "RESEARCHER", "REVIEWER"}
_ALLOWED_RETRY_EXTRACTION_ROLES = {"PROJECT_LEAD"}
_ALLOWED_PREPROCESS_VIEW_ROLES = {"PROJECT_LEAD", "RESEARCHER", "REVIEWER"}
_ALLOWED_PREPROCESS_MUTATION_ROLES = {"PROJECT_LEAD", "REVIEWER"}
_ALLOWED_PREPROCESS_ADVANCED_CONFIRMATION_ROLES = {"PROJECT_LEAD", "REVIEWER", "ADMIN"}
_ALLOWED_LAYOUT_VIEW_ROLES = {"PROJECT_LEAD", "RESEARCHER", "REVIEWER"}
_ALLOWED_LAYOUT_MUTATION_ROLES = {"PROJECT_LEAD", "REVIEWER", "ADMIN"}
_ALLOWED_TRANSCRIPTION_VIEW_ROLES = {"PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"}
_ALLOWED_TRANSCRIPTION_MUTATION_ROLES = {"PROJECT_LEAD", "REVIEWER", "ADMIN"}
_ALLOWED_MODEL_CATALOG_READ_MEMBERSHIP_ROLES = {"PROJECT_LEAD", "REVIEWER"}
_ALLOWED_MODEL_CATALOG_MUTATION_MEMBERSHIP_ROLES = {"PROJECT_LEAD"}
_ALLOWED_MODEL_ASSIGNMENT_VIEW_ROLES = {"PROJECT_LEAD", "REVIEWER"}
_ALLOWED_MODEL_ASSIGNMENT_MUTATION_ROLES = {"PROJECT_LEAD"}
_CONTROLLED_STORAGE_FAILURE_MESSAGE = "Controlled storage write failed."
_PAGE_ASSET_CACHE_CONTROL = "private, no-cache, max-age=0, must-revalidate"
_PREPROCESS_DEFAULT_PIPELINE_VERSION = "preprocess-v1"
_PREPROCESS_DEFAULT_CONTAINER_DIGEST = "ukde/preprocess:v1"
_LAYOUT_DEFAULT_PIPELINE_VERSION = "layout-v1"
_LAYOUT_DEFAULT_CONTAINER_DIGEST = "ukde/layout:v1"
_TRANSCRIPTION_DEFAULT_PIPELINE_VERSION = "transcription-v1"
_TRANSCRIPTION_DEFAULT_CONTAINER_DIGEST = "ukde/transcription:v1"
_TRANSCRIPTION_DEFAULT_REVIEW_CONFIDENCE_THRESHOLD = 0.85
_TRANSCRIPTION_DEFAULT_FALLBACK_CONFIDENCE_THRESHOLD = 0.72
_PREPROCESS_ADVANCED_BULK_CONFIRMATION_COPY = (
    "Advanced full-document preprocessing can remove faint handwriting details. "
    "Confirm only when stronger cleanup is necessary and compare review will follow."
)
_PREPROCESS_RUN_SCOPE_VALUES: set[PreprocessRunScope] = {
    "FULL_DOCUMENT",
    "PAGE_SUBSET",
    "COMPOSED_FULL_DOCUMENT",
}
_COMPARE_METRIC_DELTA_KEYS = (
    "background_variance",
    "blur_score",
    "contrast_score",
    "dpi_estimate",
    "noise_score",
    "processing_time_ms",
    "skew_angle_deg",
)


class DocumentValidationError(RuntimeError):
    """Document payload validation failed before persistence."""


class DocumentImportNotFoundError(RuntimeError):
    """Document import was not found in project scope."""


class DocumentImportConflictError(RuntimeError):
    """Document import state does not permit requested transition."""


class DocumentPageNotFoundError(RuntimeError):
    """Document page was not found in project scope."""


class DocumentPageAssetNotReadyError(RuntimeError):
    """Requested page asset has not been materialized yet."""


class DocumentQuotaExceededError(DocumentValidationError):
    """Project upload quota would be exceeded."""


class DocumentUploadAccessDeniedError(ProjectAccessDeniedError):
    """Current user cannot upload documents in this workspace."""


class DocumentProcessingRunNotFoundError(RuntimeError):
    """Document processing run was not found in project scope."""


class DocumentRetryAccessDeniedError(ProjectAccessDeniedError):
    """Current role cannot retry extraction in this workspace."""


class DocumentRetryConflictError(RuntimeError):
    """Retry request conflicts with current document processing lineage."""


class DocumentPreprocessAccessDeniedError(ProjectAccessDeniedError):
    """Current role cannot access preprocessing routes for this project."""


class DocumentPreprocessRunNotFoundError(RuntimeError):
    """Preprocessing run was not found in project scope."""


class DocumentPreprocessConflictError(RuntimeError):
    """Preprocessing mutation conflicts with run lineage or current state."""


class DocumentLayoutAccessDeniedError(ProjectAccessDeniedError):
    """Current role cannot access layout routes for this project."""


class DocumentLayoutRunNotFoundError(RuntimeError):
    """Layout run was not found in project scope."""


class DocumentLayoutConflictError(RuntimeError):
    """Layout mutation conflicts with run lineage or current state."""

    def __init__(
        self,
        message: str,
        *,
        activation_gate: LayoutActivationGateRecord | None = None,
    ) -> None:
        super().__init__(message)
        self.activation_gate = activation_gate


class DocumentTranscriptionAccessDeniedError(ProjectAccessDeniedError):
    """Current role cannot access transcription routes for this project."""


class DocumentTranscriptionRunNotFoundError(RuntimeError):
    """Transcription run was not found in project scope."""


class DocumentTranscriptionConflictError(RuntimeError):
    """Transcription mutation conflicts with run lineage or current state."""


class DocumentModelCatalogAccessDeniedError(ProjectAccessDeniedError):
    """Current role cannot access approved model catalog routes."""


class DocumentModelCatalogConflictError(RuntimeError):
    """Approved-model catalog mutation violates compatibility or integrity rules."""


class DocumentModelAssignmentAccessDeniedError(ProjectAccessDeniedError):
    """Current role cannot access model-assignment routes for this project."""


class DocumentModelAssignmentNotFoundError(RuntimeError):
    """Model assignment was not found in project scope."""


class DocumentModelAssignmentConflictError(RuntimeError):
    """Model-assignment mutation conflicts with lifecycle or compatibility rules."""


@dataclass(frozen=True)
class PreparedUpload:
    temp_path: Path
    byte_count: int
    sha256: str
    magic_prefix: bytes


@dataclass(frozen=True)
class DocumentPageImageAsset:
    payload: bytes
    media_type: str
    etag_seed: str | None
    cache_control: str


@dataclass(frozen=True)
class DocumentLayoutOverlayAsset:
    payload: dict[str, object]
    etag_seed: str | None


@dataclass(frozen=True)
class DocumentLayoutPageXmlAsset:
    payload: bytes
    media_type: str
    etag_seed: str | None


@dataclass(frozen=True)
class DocumentLayoutLineArtifactsSnapshot:
    run_id: str
    page_id: str
    page_index: int
    line_id: str
    region_id: str | None
    artifacts_sha256: str
    line_crop_path: str
    region_crop_path: str | None
    page_thumbnail_path: str
    context_window_path: str
    context_window: dict[str, object]


@dataclass(frozen=True)
class DocumentLayoutPageRecallStatusSnapshot:
    run_id: str
    page_id: str
    page_index: int
    page_recall_status: PageRecallStatus
    recall_check_version: str | None
    missed_text_risk_score: float | None
    signals_json: dict[str, object]
    rescue_candidate_counts: dict[str, int]
    blocker_reason_codes: list[str]
    unresolved_count: int


@dataclass(frozen=True)
class DocumentLayoutReadingOrderGroupSnapshot:
    group_id: str
    ordered: bool
    region_ids: tuple[str, ...]


@dataclass(frozen=True)
class DocumentLayoutReadingOrderSnapshot:
    run_id: str
    page_id: str
    page_index: int
    layout_version_id: str
    version_etag: str
    mode: str
    groups: tuple[DocumentLayoutReadingOrderGroupSnapshot, ...]
    edges: tuple[dict[str, str], ...]
    signals_json: dict[str, object]


@dataclass(frozen=True)
class DocumentLayoutElementsSnapshot:
    run_id: str
    page_id: str
    page_index: int
    layout_version_id: str
    version_etag: str
    operations_applied: int
    overlay_payload: dict[str, object]
    downstream_transcription_invalidated: bool
    downstream_transcription_state: str | None
    downstream_transcription_invalidated_reason: str | None


@dataclass(frozen=True)
class DocumentLayoutContextWindowAsset:
    payload: dict[str, object]
    etag_seed: str | None


@dataclass(frozen=True)
class DocumentPageVariantAvailability:
    variant: str
    image_variant: str
    available: bool
    media_type: str
    run_id: str | None
    result_status: PreprocessPageResultStatus | None
    quality_gate_status: PreprocessQualityGateStatus | None
    warnings_json: list[str]
    metrics_json: dict[str, object]


@dataclass(frozen=True)
class DocumentPageVariantsSnapshot:
    document: DocumentRecord
    page: DocumentPageRecord
    requested_run_id: str | None
    resolved_run: PreprocessRunRecord | None
    variants: list[DocumentPageVariantAvailability]


@dataclass(frozen=True)
class DocumentUploadSessionSnapshot:
    session_record: DocumentUploadSessionRecord
    import_record: DocumentImportRecord
    document_record: DocumentRecord

    @property
    def next_chunk_index(self) -> int:
        return self.session_record.last_chunk_index + 1


@dataclass(frozen=True)
class DocumentPreprocessOverviewSnapshot:
    document: DocumentRecord
    projection: DocumentPreprocessProjectionRecord | None
    active_run: PreprocessRunRecord | None
    latest_run: PreprocessRunRecord | None
    total_runs: int
    page_count: int
    active_status_counts: dict[PreprocessPageResultStatus, int]
    active_quality_gate_counts: dict[PreprocessQualityGateStatus, int]
    active_warning_count: int


@dataclass(frozen=True)
class DocumentLayoutSummarySnapshot:
    regions_detected: int | None
    lines_detected: int | None
    pages_with_issues: int
    coverage_percent: float | None
    structure_confidence: float | None


@dataclass(frozen=True)
class DocumentLayoutOverviewSnapshot:
    document: DocumentRecord
    projection: DocumentLayoutProjectionRecord | None
    active_run: LayoutRunRecord | None
    latest_run: LayoutRunRecord | None
    total_runs: int
    page_count: int
    active_status_counts: dict[PageLayoutResultStatus, int]
    active_recall_counts: dict[PageRecallStatus, int]
    summary: DocumentLayoutSummarySnapshot


@dataclass(frozen=True)
class DocumentPreprocessComparePageSnapshot:
    page_id: str
    page_index: int
    base_result: PagePreprocessResultRecord | None
    candidate_result: PagePreprocessResultRecord | None
    warning_delta: int = 0
    added_warnings: list[str] = field(default_factory=list)
    removed_warnings: list[str] = field(default_factory=list)
    metric_deltas: dict[str, float | None] = field(default_factory=dict)
    output_availability: dict[str, bool] = field(
        default_factory=lambda: {
            "baseGray": False,
            "baseBin": False,
            "candidateGray": False,
            "candidateBin": False,
        }
    )


@dataclass(frozen=True)
class DocumentPreprocessCompareSnapshot:
    document: DocumentRecord
    base_run: PreprocessRunRecord
    candidate_run: PreprocessRunRecord
    page_pairs: list[DocumentPreprocessComparePageSnapshot]
    base_warning_count: int
    candidate_warning_count: int
    base_blocked_count: int
    candidate_blocked_count: int


@dataclass(frozen=True)
class DocumentTranscriptionTriagePageSnapshot:
    run_id: str
    page_id: str
    page_index: int
    status: TranscriptionRunStatus
    line_count: int
    token_count: int
    anchor_refresh_required: int
    low_confidence_lines: int
    min_confidence: float | None
    avg_confidence: float | None
    warnings_json: list[str]


@dataclass(frozen=True)
class DocumentTranscriptionOverviewSnapshot:
    document: DocumentRecord
    projection: DocumentTranscriptionProjectionRecord | None
    active_run: TranscriptionRunRecord | None
    latest_run: TranscriptionRunRecord | None
    total_runs: int
    page_count: int
    active_status_counts: dict[TranscriptionRunStatus, int]
    active_line_count: int
    active_token_count: int
    active_anchor_refresh_required: int
    active_low_confidence_lines: int


class DocumentService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: DocumentStore | None = None,
        project_service: ProjectService | None = None,
        storage: DocumentStorage | None = None,
        scanner: DocumentScanner | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or DocumentStore(settings)
        self._project_service = project_service or get_project_service()
        self._storage = storage or get_document_storage()
        self._scanner = scanner or get_document_scanner()

    @staticmethod
    def _normalize_filters(filters: DocumentListFilters) -> DocumentListFilters:
        normalized_q = filters.q.strip() if isinstance(filters.q, str) else None
        normalized_q = normalized_q if normalized_q else None
        normalized_uploader = (
            filters.uploader.strip() if isinstance(filters.uploader, str) else None
        )
        normalized_uploader = normalized_uploader if normalized_uploader else None
        if normalized_q and len(normalized_q) > 240:
            raise DocumentValidationError("Search query must be 240 characters or fewer.")
        if normalized_uploader and len(normalized_uploader) > 120:
            raise DocumentValidationError("Uploader filter must be 120 characters or fewer.")
        if filters.page_size < 1 or filters.page_size > 200:
            raise DocumentValidationError("Page size must be between 1 and 200.")
        if filters.cursor < 0:
            raise DocumentValidationError("Cursor must be zero or greater.")
        if (
            filters.from_timestamp
            and filters.to_timestamp
            and filters.from_timestamp > filters.to_timestamp
        ):
            raise DocumentValidationError("From timestamp must be before to timestamp.")

        return replace(filters, q=normalized_q, uploader=normalized_uploader)

    @staticmethod
    def _normalize_original_filename(filename: str) -> str:
        normalized = Path(filename).name.strip()
        if not normalized:
            raise DocumentValidationError("Filename is required.")
        if len(normalized) > 240:
            raise DocumentValidationError("Filename must be 240 characters or fewer.")
        return normalized

    def _require_upload_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        workspace = self._project_service.require_member_workspace(
            current_user=current_user,
            project_id=project_id,
        )
        role = workspace.summary.current_user_role
        if role not in _ALLOWED_UPLOAD_ROLES:
            raise DocumentUploadAccessDeniedError(
                "Current role cannot upload documents in this project."
            )

    @staticmethod
    def _is_admin(current_user: SessionPrincipal) -> bool:
        return "ADMIN" in set(current_user.platform_roles)

    @staticmethod
    def _sha256_hex(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _require_image_lib():
        try:
            from PIL import Image, UnidentifiedImageError
        except ModuleNotFoundError as error:  # pragma: no cover - dependency guard
            raise DocumentValidationError(
                "Pillow dependency is required for layout artifact generation."
            ) from error
        return Image, UnidentifiedImageError

    @staticmethod
    def _line_sort_key(line: LayoutLine) -> tuple[float, float, str]:
        if not line.polygon:
            return (0.0, 0.0, line.line_id)
        y_center = sum(point.y for point in line.polygon) / float(len(line.polygon))
        x_center = sum(point.x for point in line.polygon) / float(len(line.polygon))
        return (round(y_center, 4), round(x_center, 4), line.line_id)

    @staticmethod
    def _points_payload(points: tuple[object, ...]) -> list[dict[str, float]]:
        payload: list[dict[str, float]] = []
        for point in points:
            x = getattr(point, "x", None)
            y = getattr(point, "y", None)
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                payload.append({"x": float(x), "y": float(y)})
        return payload

    @staticmethod
    def _polygon_bounds(
        *,
        points: tuple[object, ...],
        page_width: int,
        page_height: int,
        padding: int = 0,
    ) -> tuple[int, int, int, int] | None:
        if not points:
            return None
        xs: list[float] = []
        ys: list[float] = []
        for point in points:
            x = getattr(point, "x", None)
            y = getattr(point, "y", None)
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                continue
            xs.append(float(x))
            ys.append(float(y))
        if not xs or not ys:
            return None
        x0 = max(0, int(min(xs)) - padding)
        y0 = max(0, int(min(ys)) - padding)
        x1 = min(page_width, int(max(xs) + 0.9999) + padding)
        y1 = min(page_height, int(max(ys) + 0.9999) + padding)
        if x1 <= x0 or y1 <= y0:
            return None
        return (x0, y0, x1, y1)

    @staticmethod
    def _encode_png_bytes(image: object) -> bytes:
        payload = BytesIO()
        image.save(payload, format="PNG", optimize=False, compress_level=9)
        return payload.getvalue()

    @staticmethod
    def _compute_layout_artifacts_sha256(
        *,
        line_crop_bytes: bytes,
        region_crop_bytes: bytes | None,
        page_thumbnail_bytes: bytes,
        context_window_bytes: bytes,
    ) -> str:
        digest = hashlib.sha256()
        parts: tuple[tuple[str, bytes], ...] = (
            ("line", line_crop_bytes),
            ("region", region_crop_bytes or b""),
            ("thumbnail", page_thumbnail_bytes),
            ("context", context_window_bytes),
        )
        for label, payload in parts:
            digest.update(label.encode("utf-8"))
            digest.update(b":")
            digest.update(len(payload).to_bytes(8, byteorder="big", signed=False))
            digest.update(payload)
        return digest.hexdigest()

    def _build_line_context_window_payload(
        self,
        *,
        canonical_page: LayoutCanonicalPage,
        line: LayoutLine,
        region: LayoutRegion,
        region_line_ids: list[str],
        line_index_within_region: int,
    ) -> dict[str, object]:
        previous_line_id = (
            region_line_ids[line_index_within_region - 1]
            if line_index_within_region > 0
            else None
        )
        next_line_id = (
            region_line_ids[line_index_within_region + 1]
            if line_index_within_region < (len(region_line_ids) - 1)
            else None
        )
        incoming_reading_order = sorted(
            edge.from_id
            for edge in canonical_page.reading_order_edges
            if edge.to_id == line.line_id
        )
        outgoing_reading_order = sorted(
            edge.to_id
            for edge in canonical_page.reading_order_edges
            if edge.from_id == line.line_id
        )
        return {
            "schemaVersion": 1,
            "runId": canonical_page.run_id,
            "pageId": canonical_page.page_id,
            "pageIndex": canonical_page.page_index,
            "lineId": line.line_id,
            "regionId": region.region_id,
            "page": {
                "width": canonical_page.page_width,
                "height": canonical_page.page_height,
            },
            "regionLineIds": region_line_ids,
            "lineIndexWithinRegion": line_index_within_region,
            "previousLineId": previous_line_id,
            "nextLineId": next_line_id,
            "incomingReadingOrderFromIds": incoming_reading_order,
            "outgoingReadingOrderToIds": outgoing_reading_order,
            "linePolygon": self._points_payload(line.polygon),
            "lineBaseline": (
                self._points_payload(line.baseline) if line.baseline is not None else None
            ),
            "regionPolygon": self._points_payload(region.polygon),
        }

    def _materialize_layout_line_artifacts(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page: DocumentPageRecord,
        canonical_page: LayoutCanonicalPage,
        source_image_payload: bytes,
        layout_version_id: str | None = None,
    ) -> list[dict[str, object]]:
        Image, UnidentifiedImageError = self._require_image_lib()
        try:
            with Image.open(BytesIO(source_image_payload)) as opened:
                grayscale = opened.convert("L")
                width, height = grayscale.size
        except UnidentifiedImageError as error:
            raise DocumentValidationError(
                "Layout artifacts could not decode preprocess image payload."
            ) from error
        if width != page.width or height != page.height:
            raise DocumentValidationError(
                "Layout artifacts require preprocess image dimensions to match page metadata."
            )

        thumbnail_image = grayscale.copy()
        thumbnail_image.thumbnail((512, 512), resample=Image.Resampling.LANCZOS)
        thumbnail_bytes = self._encode_png_bytes(thumbnail_image)
        thumbnail_object = self._storage.write_layout_page_thumbnail(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page.page_index,
            layout_version_id=layout_version_id,
            payload=thumbnail_bytes,
        )

        regions_by_id: dict[str, LayoutRegion] = {
            region.region_id: region for region in canonical_page.regions
        }
        lines_by_id: dict[str, LayoutLine] = {
            line.line_id: line for line in canonical_page.lines
        }
        sorted_lines_by_region: dict[str, list[LayoutLine]] = {}
        for region in canonical_page.regions:
            ordered_lines: list[LayoutLine] = []
            seen_line_ids: set[str] = set()
            for line_id in region.line_ids:
                line = lines_by_id.get(line_id)
                if line is None or line.parent_region_id != region.region_id:
                    continue
                ordered_lines.append(line)
                seen_line_ids.add(line.line_id)
            overflow_lines = sorted(
                [
                    line
                    for line in canonical_page.lines
                    if line.parent_region_id == region.region_id
                    and line.line_id not in seen_line_ids
                ],
                key=self._line_sort_key,
            )
            ordered_lines.extend(overflow_lines)
            sorted_lines_by_region[region.region_id] = ordered_lines

        artifacts: list[dict[str, object]] = []
        for line in sorted(canonical_page.lines, key=lambda item: item.line_id):
            line_bounds = self._polygon_bounds(
                points=line.polygon,
                page_width=canonical_page.page_width,
                page_height=canonical_page.page_height,
                padding=2,
            )
            if line_bounds is None:
                raise DocumentValidationError(
                    f"Layout line '{line.line_id}' cannot produce a valid crop window."
                )
            line_crop_image = grayscale.crop(line_bounds)
            line_crop_bytes = self._encode_png_bytes(line_crop_image)
            line_crop_object = self._storage.write_layout_line_crop(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_index=page.page_index,
                line_id=line.line_id,
                layout_version_id=layout_version_id,
                payload=line_crop_bytes,
            )

            region = regions_by_id.get(line.parent_region_id)
            if region is None:
                raise DocumentValidationError(
                    f"Layout line '{line.line_id}' references unknown region."
                )
            region_crop_key: str | None = None
            region_crop_bytes: bytes | None = None
            region_bounds = self._polygon_bounds(
                points=region.polygon,
                page_width=canonical_page.page_width,
                page_height=canonical_page.page_height,
                padding=4,
            )
            if region_bounds is not None:
                region_crop_image = grayscale.crop(region_bounds)
                region_crop_bytes = self._encode_png_bytes(region_crop_image)
                region_crop_object = self._storage.write_layout_region_crop(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    page_index=page.page_index,
                    region_id=region.region_id,
                    layout_version_id=layout_version_id,
                    payload=region_crop_bytes,
                )
                region_crop_key = region_crop_object.object_key

            region_lines = sorted_lines_by_region.get(region.region_id, [])
            region_line_ids = [entry.line_id for entry in region_lines]
            try:
                line_index_within_region = region_line_ids.index(line.line_id)
            except ValueError as error:
                raise DocumentValidationError(
                    f"Layout line '{line.line_id}' is missing from region line order."
                ) from error
            context_payload = self._build_line_context_window_payload(
                canonical_page=canonical_page,
                line=line,
                region=region,
                region_line_ids=region_line_ids,
                line_index_within_region=line_index_within_region,
            )
            context_window_bytes = canonical_json_bytes(context_payload)
            context_window_object = self._storage.write_layout_context_window(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_index=page.page_index,
                line_id=line.line_id,
                layout_version_id=layout_version_id,
                payload=context_window_bytes,
            )
            artifacts.append(
                {
                    "run_id": run_id,
                    "page_id": page.id,
                    "line_id": line.line_id,
                    "region_id": region.region_id,
                    "line_crop_key": line_crop_object.object_key,
                    "region_crop_key": region_crop_key,
                    "page_thumbnail_key": thumbnail_object.object_key,
                    "context_window_json_key": context_window_object.object_key,
                    "artifacts_sha256": self._compute_layout_artifacts_sha256(
                        line_crop_bytes=line_crop_bytes,
                        region_crop_bytes=region_crop_bytes,
                        page_thumbnail_bytes=thumbnail_bytes,
                        context_window_bytes=context_window_bytes,
                    ),
                }
            )
        return artifacts

    def _read_layout_context_window_payload(
        self,
        *,
        object_key: str,
    ) -> dict[str, object]:
        try:
            payload_bytes = self._storage.read_object_bytes(object_key)
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError(
                "Layout context-window payload could not be read."
            ) from error
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DocumentStoreUnavailableError(
                "Layout context-window payload is invalid."
            ) from error
        if not isinstance(payload, dict):
            raise DocumentStoreUnavailableError("Layout context-window payload is invalid.")
        return payload

    @staticmethod
    def _new_layout_version_id() -> str:
        return str(uuid4())

    @staticmethod
    def _bootstrap_layout_version_id(
        *,
        run_id: str,
        page_id: str,
        page_xml_sha256: str,
        overlay_json_sha256: str,
    ) -> str:
        seed = f"{run_id}|{page_id}|{page_xml_sha256}|{overlay_json_sha256}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return f"layoutv-{digest[:24]}"

    @staticmethod
    def _compute_layout_version_etag(
        *,
        run_id: str,
        page_id: str,
        version_id: str,
        page_xml_sha256: str,
        overlay_json_sha256: str,
    ) -> str:
        etag_seed = (
            f"{run_id}|{page_id}|{version_id}|{page_xml_sha256}|{overlay_json_sha256}"
        )
        return hashlib.sha256(etag_seed.encode("utf-8")).hexdigest()

    def _layout_canonical_payload(
        self,
        *,
        canonical_page: LayoutCanonicalPage,
    ) -> dict[str, object]:
        reading_order_meta: dict[str, object] = {
            "schemaVersion": 1,
            "mode": canonical_page.reading_order_meta.mode,
            "source": canonical_page.reading_order_meta.source,
            "ambiguityScore": canonical_page.reading_order_meta.ambiguity_score,
            "columnCertainty": canonical_page.reading_order_meta.column_certainty,
            "overlapConflictScore": canonical_page.reading_order_meta.overlap_conflict_score,
            "orphanLineCount": canonical_page.reading_order_meta.orphan_line_count,
            "nonTextComplexityScore": canonical_page.reading_order_meta.non_text_complexity_score,
            "orderWithheld": canonical_page.reading_order_meta.order_withheld,
        }
        if canonical_page.reading_order_meta.version_etag is not None:
            reading_order_meta["versionEtag"] = canonical_page.reading_order_meta.version_etag
        if canonical_page.reading_order_meta.layout_version_id is not None:
            reading_order_meta["layoutVersionId"] = canonical_page.reading_order_meta.layout_version_id

        return {
            "schemaVersion": canonical_page.schema_version,
            "runId": canonical_page.run_id,
            "pageId": canonical_page.page_id,
            "pageIndex": canonical_page.page_index,
            "page": {
                "width": canonical_page.page_width,
                "height": canonical_page.page_height,
            },
            "regions": [
                {
                    "id": region.region_id,
                    "type": region.region_type,
                    "polygon": self._points_payload(region.polygon),
                    "lineIds": list(region.line_ids),
                    "includeInReadingOrder": region.include_in_reading_order,
                }
                for region in canonical_page.regions
            ],
            "lines": [
                {
                    "id": line.line_id,
                    "parentRegionId": line.parent_region_id,
                    "polygon": self._points_payload(line.polygon),
                    "baseline": (
                        self._points_payload(line.baseline)
                        if line.baseline is not None
                        else None
                    ),
                }
                for line in canonical_page.lines
            ],
            "readingOrder": [
                {"fromId": edge.from_id, "toId": edge.to_id}
                for edge in canonical_page.reading_order_edges
            ],
            "readingOrderGroups": [
                {
                    "id": group.group_id,
                    "ordered": group.ordered,
                    "regionIds": list(group.region_ids),
                }
                for group in canonical_page.reading_order_groups
            ],
            "readingOrderMeta": reading_order_meta,
        }

    def _refresh_layout_context_windows_for_page(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page: DocumentPageRecord,
        canonical_page: LayoutCanonicalPage,
        source_layout_version_id: str,
        layout_version_id: str,
    ) -> None:
        existing_artifacts = self._store.list_layout_line_artifacts(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page.id,
            layout_version_id=source_layout_version_id,
        )
        if not existing_artifacts:
            return

        regions_by_id: dict[str, LayoutRegion] = {
            region.region_id: region for region in canonical_page.regions
        }
        lines_by_id: dict[str, LayoutLine] = {
            line.line_id: line for line in canonical_page.lines
        }
        sorted_lines_by_region: dict[str, list[LayoutLine]] = {}
        for region in canonical_page.regions:
            ordered_lines: list[LayoutLine] = []
            seen_line_ids: set[str] = set()
            for line_id in region.line_ids:
                line = lines_by_id.get(line_id)
                if line is None or line.parent_region_id != region.region_id:
                    continue
                ordered_lines.append(line)
                seen_line_ids.add(line.line_id)
            overflow_lines = sorted(
                [
                    line
                    for line in canonical_page.lines
                    if line.parent_region_id == region.region_id
                    and line.line_id not in seen_line_ids
                ],
                key=self._line_sort_key,
            )
            ordered_lines.extend(overflow_lines)
            sorted_lines_by_region[region.region_id] = ordered_lines

        artifacts_by_line_id = {artifact.line_id: artifact for artifact in existing_artifacts}
        byte_cache: dict[str, bytes] = {}

        def read_cached_bytes(object_key: str) -> bytes:
            cached = byte_cache.get(object_key)
            if cached is not None:
                return cached
            payload = self._storage.read_object_bytes(object_key)
            byte_cache[object_key] = payload
            return payload

        has_changes = False
        replacement_rows: list[dict[str, object]] = []
        for line in sorted(canonical_page.lines, key=lambda item: item.line_id):
            artifact = artifacts_by_line_id.get(line.line_id)
            if artifact is None:
                raise DocumentStoreUnavailableError(
                    "Layout line artifacts are inconsistent with canonical line IDs."
                )
            region = regions_by_id.get(line.parent_region_id)
            if region is None:
                raise DocumentStoreUnavailableError(
                    f"Layout line '{line.line_id}' references unknown region."
                )
            region_lines = sorted_lines_by_region.get(region.region_id, [])
            region_line_ids = [entry.line_id for entry in region_lines]
            try:
                line_index_within_region = region_line_ids.index(line.line_id)
            except ValueError as error:
                raise DocumentStoreUnavailableError(
                    "Layout line ordering for context-window refresh is invalid."
                ) from error

            next_context_payload = self._build_line_context_window_payload(
                canonical_page=canonical_page,
                line=line,
                region=region,
                region_line_ids=region_line_ids,
                line_index_within_region=line_index_within_region,
            )
            next_context_bytes = canonical_json_bytes(next_context_payload)
            current_context_payload = self._read_layout_context_window_payload(
                object_key=artifact.context_window_json_key
            )
            current_context_bytes = canonical_json_bytes(current_context_payload)
            if next_context_bytes == current_context_bytes:
                replacement_rows.append(
                    {
                        "run_id": artifact.run_id,
                        "page_id": artifact.page_id,
                        "line_id": artifact.line_id,
                        "region_id": artifact.region_id,
                        "line_crop_key": artifact.line_crop_key,
                        "region_crop_key": artifact.region_crop_key,
                        "page_thumbnail_key": artifact.page_thumbnail_key,
                        "context_window_json_key": artifact.context_window_json_key,
                        "artifacts_sha256": artifact.artifacts_sha256,
                    }
                )
                continue

            has_changes = True
            context_object = self._storage.write_layout_context_window(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_index=page.page_index,
                line_id=line.line_id,
                layout_version_id=layout_version_id,
                payload=next_context_bytes,
            )
            line_crop_bytes = read_cached_bytes(artifact.line_crop_key)
            region_crop_bytes = (
                read_cached_bytes(artifact.region_crop_key)
                if artifact.region_crop_key is not None
                else None
            )
            page_thumbnail_bytes = read_cached_bytes(artifact.page_thumbnail_key)
            replacement_rows.append(
                {
                    "run_id": artifact.run_id,
                    "page_id": artifact.page_id,
                    "line_id": artifact.line_id,
                    "region_id": artifact.region_id,
                    "line_crop_key": artifact.line_crop_key,
                    "region_crop_key": artifact.region_crop_key,
                    "page_thumbnail_key": artifact.page_thumbnail_key,
                    "context_window_json_key": context_object.object_key,
                    "artifacts_sha256": self._compute_layout_artifacts_sha256(
                        line_crop_bytes=line_crop_bytes,
                        region_crop_bytes=region_crop_bytes,
                        page_thumbnail_bytes=page_thumbnail_bytes,
                        context_window_bytes=next_context_bytes,
                    ),
                }
            )

        _ = has_changes
        self._store.replace_layout_line_artifacts(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page.id,
            layout_version_id=layout_version_id,
            artifacts=replacement_rows,
        )

    def _assert_layout_page_mapping(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page: DocumentPageRecord,
        page_result: PageLayoutResultRecord,
    ) -> tuple[str, str]:
        if page_result.page_index != page.page_index:
            raise DocumentStoreUnavailableError(
                "Layout page mapping is inconsistent with document page index."
            )
        expected_active_xml_key = self._storage.build_layout_page_xml_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page.page_index,
            layout_version_id=page_result.active_layout_version_id,
        )
        expected_base_xml_key = self._storage.build_layout_page_xml_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page.page_index,
        )
        expected_active_overlay_key = self._storage.build_layout_page_overlay_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page.page_index,
            layout_version_id=page_result.active_layout_version_id,
        )
        expected_base_overlay_key = self._storage.build_layout_page_overlay_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page.page_index,
        )
        if (
            page_result.page_xml_key is not None
            and page_result.page_xml_key
            not in {expected_active_xml_key, expected_base_xml_key}
        ):
            raise DocumentStoreUnavailableError(
                "Layout PAGE-XML key violates deterministic page mapping."
            )
        if (
            page_result.overlay_json_key is not None
            and page_result.overlay_json_key
            not in {expected_active_overlay_key, expected_base_overlay_key}
        ):
            raise DocumentStoreUnavailableError(
                "Layout overlay key violates deterministic page mapping."
            )
        return expected_active_xml_key, expected_active_overlay_key

    def _load_layout_page_result(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> tuple[LayoutRunRecord, DocumentPageRecord, PageLayoutResultRecord]:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        run = self._store.get_layout_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentLayoutRunNotFoundError("Layout run not found.")
        page = self._store.get_document_page(
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        if page is None:
            raise DocumentPageNotFoundError("Page not found.")
        page_result = self._store.get_layout_page_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page_id,
        )
        if page_result is None:
            raise DocumentPageNotFoundError("Layout page result not found.")
        self._assert_layout_page_mapping(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page=page,
            page_result=page_result,
        )
        return run, page, page_result

    def _invalidate_layout_downstream_transcription_basis(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        layout_version_id: str,
        run_snapshot_hash: str,
    ) -> DocumentLayoutProjectionRecord | None:
        reason = (
            "LAYOUT_MANUAL_EDIT_SUPERSEDED: "
            f"Layout page {page_id} changed on active layout run {run_id}; "
            f"transcription basis is stale at layout version {layout_version_id}."
        )
        return self._store.mark_layout_downstream_transcription_stale(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            reason=reason,
            active_layout_snapshot_hash=run_snapshot_hash,
        )

    def _build_layout_manifest_payload(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_results: list[PageLayoutResultRecord],
    ) -> bytes:
        pages: list[dict[str, object]] = []
        for page_result in sorted(
            page_results,
            key=lambda item: (item.page_index, item.page_id),
        ):
            if (
                page_result.page_xml_key is None
                or page_result.overlay_json_key is None
                or page_result.page_xml_sha256 is None
                or page_result.overlay_json_sha256 is None
            ):
                continue
            pages.append(
                {
                    "pageId": page_result.page_id,
                    "pageIndex": page_result.page_index,
                    "pageXmlKey": page_result.page_xml_key,
                    "overlayJsonKey": page_result.overlay_json_key,
                    "pageXmlSha256": page_result.page_xml_sha256,
                    "overlayJsonSha256": page_result.overlay_json_sha256,
                }
            )
        return canonical_json_bytes(
            {
                "schemaVersion": 1,
                "projectId": project_id,
                "documentId": document_id,
                "runId": run_id,
                "pages": pages,
            }
        )

    def _assert_layout_manifest_mapping(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page: DocumentPageRecord,
        page_result: PageLayoutResultRecord,
    ) -> None:
        if (
            page_result.active_layout_version_id is not None
            and (
                (
                    page_result.page_xml_key is not None
                    and "/versions/" in page_result.page_xml_key
                )
                or (
                    page_result.overlay_json_key is not None
                    and "/versions/" in page_result.overlay_json_key
                )
            )
        ):
            return
        manifest_key = self._storage.build_layout_manifest_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        try:
            manifest_bytes = self._storage.read_object_bytes(manifest_key)
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError("Layout manifest could not be read.") from error
        try:
            manifest_payload = json.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DocumentStoreUnavailableError("Layout manifest payload is invalid.") from error
        if not isinstance(manifest_payload, Mapping):
            raise DocumentStoreUnavailableError("Layout manifest payload is invalid.")
        pages = manifest_payload.get("pages")
        if not isinstance(pages, list):
            raise DocumentStoreUnavailableError("Layout manifest payload is invalid.")
        matches = [
            entry
            for entry in pages
            if isinstance(entry, Mapping) and str(entry.get("pageId")) == page.id
        ]
        if len(matches) != 1:
            raise DocumentStoreUnavailableError("Layout manifest page mapping is invalid.")
        match = matches[0]
        raw_page_index = match.get("pageIndex")
        if not isinstance(raw_page_index, int):
            raise DocumentStoreUnavailableError("Layout manifest page mapping is invalid.")
        if raw_page_index != page.page_index:
            raise DocumentStoreUnavailableError("Layout manifest page index mapping is invalid.")
        if (
            page_result.page_xml_key is not None
            and str(match.get("pageXmlKey")) != page_result.page_xml_key
        ):
            raise DocumentStoreUnavailableError("Layout manifest PAGE-XML key mapping is invalid.")
        if (
            page_result.overlay_json_key is not None
            and str(match.get("overlayJsonKey")) != page_result.overlay_json_key
        ):
            raise DocumentStoreUnavailableError("Layout manifest overlay key mapping is invalid.")
        if (
            page_result.page_xml_sha256 is not None
            and str(match.get("pageXmlSha256")) != page_result.page_xml_sha256
        ):
            raise DocumentStoreUnavailableError("Layout manifest PAGE-XML hash mapping is invalid.")
        if (
            page_result.overlay_json_sha256 is not None
            and str(match.get("overlayJsonSha256")) != page_result.overlay_json_sha256
        ):
            raise DocumentStoreUnavailableError("Layout manifest overlay hash mapping is invalid.")

    def _require_retry_extraction_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if self._is_admin(current_user):
            return
        if not context.is_member:
            raise DocumentRetryAccessDeniedError(
                "Membership is required to retry extraction."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_RETRY_EXTRACTION_ROLES:
            raise DocumentRetryAccessDeniedError(
                "Current role cannot retry extraction in this project."
            )

    def _require_preprocess_view_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if self._is_admin(current_user):
            return
        if not context.is_member:
            raise DocumentPreprocessAccessDeniedError(
                "Membership is required for preprocessing access."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_PREPROCESS_VIEW_ROLES:
            raise DocumentPreprocessAccessDeniedError(
                "Current role cannot view preprocessing runs in this project."
            )

    def _require_preprocess_mutation_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> str:
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if self._is_admin(current_user):
            return "ADMIN"
        if not context.is_member:
            raise DocumentPreprocessAccessDeniedError(
                "Membership is required for preprocessing administration."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_PREPROCESS_MUTATION_ROLES:
            raise DocumentPreprocessAccessDeniedError(
                "Current role cannot create, rerun, cancel, or activate preprocessing runs."
            )
        return str(role)

    def _require_layout_view_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if self._is_admin(current_user):
            return
        if not context.is_member:
            raise DocumentLayoutAccessDeniedError(
                "Membership is required for layout analysis access."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_LAYOUT_VIEW_ROLES:
            raise DocumentLayoutAccessDeniedError(
                "Current role cannot view layout analysis routes in this project."
            )

    def _require_layout_mutation_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> str:
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if self._is_admin(current_user):
            return "ADMIN"
        if not context.is_member:
            raise DocumentLayoutAccessDeniedError(
                "Membership is required for layout run administration."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_LAYOUT_MUTATION_ROLES:
            raise DocumentLayoutAccessDeniedError(
                "Current role cannot create, cancel, or activate layout runs."
            )
        return str(role)

    def _require_transcription_view_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if self._is_admin(current_user):
            return
        if not context.is_member:
            raise DocumentTranscriptionAccessDeniedError(
                "Membership is required for transcription access."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_TRANSCRIPTION_VIEW_ROLES:
            raise DocumentTranscriptionAccessDeniedError(
                "Current role cannot view transcription routes in this project."
            )

    def _require_transcription_mutation_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> str:
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if self._is_admin(current_user):
            return "ADMIN"
        if not context.is_member:
            raise DocumentTranscriptionAccessDeniedError(
                "Membership is required for transcription run administration."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_TRANSCRIPTION_MUTATION_ROLES:
            raise DocumentTranscriptionAccessDeniedError(
                "Current role cannot create, cancel, or activate transcription runs."
            )
        return str(role)

    def _require_model_catalog_view_access(
        self,
        *,
        current_user: SessionPrincipal,
    ) -> None:
        if self._is_admin(current_user):
            return
        summaries = self._project_service.list_my_projects(current_user=current_user)
        if any(
            summary.current_user_role in _ALLOWED_MODEL_CATALOG_READ_MEMBERSHIP_ROLES
            for summary in summaries
        ):
            return
        raise DocumentModelCatalogAccessDeniedError(
            "Current role cannot view approved model catalog routes."
        )

    def _require_model_catalog_mutation_access(
        self,
        *,
        current_user: SessionPrincipal,
    ) -> None:
        if self._is_admin(current_user):
            return
        summaries = self._project_service.list_my_projects(current_user=current_user)
        if any(
            summary.current_user_role in _ALLOWED_MODEL_CATALOG_MUTATION_MEMBERSHIP_ROLES
            for summary in summaries
        ):
            return
        raise DocumentModelCatalogAccessDeniedError(
            "Current role cannot create approved model catalog entries."
        )

    def _require_model_assignment_view_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if self._is_admin(current_user):
            return
        if not context.is_member:
            raise DocumentModelAssignmentAccessDeniedError(
                "Membership is required for model-assignment access."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_MODEL_ASSIGNMENT_VIEW_ROLES:
            raise DocumentModelAssignmentAccessDeniedError(
                "Current role cannot view model-assignment routes in this project."
            )

    def _require_model_assignment_mutation_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> str:
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if self._is_admin(current_user):
            return "ADMIN"
        if not context.is_member:
            raise DocumentModelAssignmentAccessDeniedError(
                "Membership is required for model-assignment administration."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_MODEL_ASSIGNMENT_MUTATION_ROLES:
            raise DocumentModelAssignmentAccessDeniedError(
                "Current role cannot create, activate, or retire model assignments."
            )
        return str(role)

    @staticmethod
    def _normalize_layout_model_id(value: str | None) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 120:
            raise DocumentValidationError("modelId must be 120 characters or fewer.")
        return normalized

    @staticmethod
    def _normalize_layout_profile_id(value: str | None) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 120:
            raise DocumentValidationError("profileId must be 120 characters or fewer.")
        return normalized

    @staticmethod
    def _normalize_layout_pipeline_version(value: str | None) -> str:
        if not isinstance(value, str):
            return _LAYOUT_DEFAULT_PIPELINE_VERSION
        normalized = value.strip()
        if not normalized:
            return _LAYOUT_DEFAULT_PIPELINE_VERSION
        if len(normalized) > 120:
            raise DocumentValidationError("pipelineVersion must be 120 characters or fewer.")
        return normalized

    @staticmethod
    def _normalize_layout_container_digest(value: str | None) -> str:
        if not isinstance(value, str):
            return _LAYOUT_DEFAULT_CONTAINER_DIGEST
        normalized = value.strip()
        if not normalized:
            return _LAYOUT_DEFAULT_CONTAINER_DIGEST
        if len(normalized) > 180:
            raise DocumentValidationError("containerDigest must be 180 characters or fewer.")
        return normalized

    @staticmethod
    def _normalize_layout_params_json(
        value: dict[str, object] | None,
    ) -> dict[str, object]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise DocumentValidationError("paramsJson must be a JSON object.")
        try:
            return canonicalize_params_dict(value)
        except PreprocessPipelineError as error:
            raise DocumentValidationError("paramsJson must contain JSON-serializable values.") from error

    @staticmethod
    def _normalize_layout_run_reference(
        value: str | None,
        *,
        field_name: str,
    ) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 120:
            raise DocumentValidationError(f"{field_name} must be 120 characters or fewer.")
        return normalized

    def _resolve_layout_input_preprocess_run_id(
        self,
        *,
        project_id: str,
        document_id: str,
        explicit_input_preprocess_run_id: str | None,
    ) -> str:
        normalized_input_run_id = self._normalize_layout_run_reference(
            explicit_input_preprocess_run_id,
            field_name="inputPreprocessRunId",
        )
        if normalized_input_run_id is not None:
            return normalized_input_run_id

        projection = self._store.get_preprocess_projection(
            project_id=project_id,
            document_id=document_id,
        )
        if projection is None or not projection.active_preprocess_run_id:
            raise DocumentLayoutConflictError(
                "Layout run creation requires inputPreprocessRunId or an active preprocess projection."
            )
        return projection.active_preprocess_run_id

    @staticmethod
    def _normalize_transcription_engine(value: str | None) -> TranscriptionRunEngine:
        if not isinstance(value, str):
            return "VLM_LINE_CONTEXT"
        normalized = value.strip()
        if normalized not in {
            "VLM_LINE_CONTEXT",
            "REVIEW_COMPOSED",
            "KRAKEN_LINE",
            "TROCR_LINE",
            "DAN_PAGE",
        }:
            raise DocumentValidationError("engine is not supported.")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _normalize_transcription_confidence_basis(
        value: str | None,
    ) -> TranscriptionConfidenceBasis:
        if not isinstance(value, str):
            return "MODEL_NATIVE"
        normalized = value.strip()
        if normalized not in {"MODEL_NATIVE", "READ_AGREEMENT", "FALLBACK_DISAGREEMENT"}:
            raise DocumentValidationError("confidenceBasis is not supported.")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _normalize_transcription_pipeline_version(value: str | None) -> str:
        if not isinstance(value, str):
            return _TRANSCRIPTION_DEFAULT_PIPELINE_VERSION
        normalized = value.strip()
        if not normalized:
            return _TRANSCRIPTION_DEFAULT_PIPELINE_VERSION
        if len(normalized) > 120:
            raise DocumentValidationError("pipelineVersion must be 120 characters or fewer.")
        return normalized

    @staticmethod
    def _normalize_transcription_container_digest(value: str | None) -> str:
        if not isinstance(value, str):
            return _TRANSCRIPTION_DEFAULT_CONTAINER_DIGEST
        normalized = value.strip()
        if not normalized:
            return _TRANSCRIPTION_DEFAULT_CONTAINER_DIGEST
        if len(normalized) > 180:
            raise DocumentValidationError("containerDigest must be 180 characters or fewer.")
        return normalized

    @staticmethod
    def _normalize_transcription_reference(
        value: str | None,
        *,
        field_name: str,
        max_length: int = 160,
    ) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > max_length:
            raise DocumentValidationError(f"{field_name} must be {max_length} characters or fewer.")
        return normalized

    @staticmethod
    def _normalize_transcription_params_json(
        value: dict[str, object] | None,
    ) -> dict[str, object]:
        if value is None:
            normalized: dict[str, object] = {}
        elif isinstance(value, dict):
            try:
                normalized = canonicalize_params_dict(value)
            except PreprocessPipelineError as error:
                raise DocumentValidationError(
                    "paramsJson must contain JSON-serializable values."
                ) from error
        else:
            raise DocumentValidationError("paramsJson must be a JSON object.")
        normalized.setdefault(
            "review_confidence_threshold",
            _TRANSCRIPTION_DEFAULT_REVIEW_CONFIDENCE_THRESHOLD,
        )
        normalized.setdefault(
            "fallback_confidence_threshold",
            _TRANSCRIPTION_DEFAULT_FALLBACK_CONFIDENCE_THRESHOLD,
        )
        return normalized

    @staticmethod
    def _resolve_transcription_model_role(
        engine: TranscriptionRunEngine,
    ) -> ApprovedModelRole:
        if engine in {"KRAKEN_LINE", "TROCR_LINE", "DAN_PAGE"}:
            return "TRANSCRIPTION_FALLBACK"
        return "TRANSCRIPTION_PRIMARY"

    @staticmethod
    def _normalize_approved_model_type(value: str) -> ApprovedModelType:
        normalized = value.strip().upper()
        if normalized not in {"VLM", "LLM", "HTR"}:
            raise DocumentValidationError("modelType must be VLM, LLM, or HTR.")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _normalize_approved_model_role(value: str) -> ApprovedModelRole:
        normalized = value.strip().upper()
        if normalized not in {"TRANSCRIPTION_PRIMARY", "TRANSCRIPTION_FALLBACK", "ASSIST"}:
            raise DocumentValidationError(
                "modelRole must be TRANSCRIPTION_PRIMARY, TRANSCRIPTION_FALLBACK, or ASSIST."
            )
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _normalize_approved_model_serving_interface(
        value: str,
    ) -> ApprovedModelServingInterface:
        normalized = value.strip().upper()
        if normalized not in {
            "OPENAI_CHAT",
            "OPENAI_EMBEDDING",
            "ENGINE_NATIVE",
            "RULES_NATIVE",
        }:
            raise DocumentValidationError(
                "servingInterface must be OPENAI_CHAT, OPENAI_EMBEDDING, ENGINE_NATIVE, or RULES_NATIVE."
            )
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _normalize_approved_model_status(value: str | None) -> ApprovedModelStatus | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized not in {"APPROVED", "DEPRECATED", "ROLLED_BACK"}:
            raise DocumentValidationError(
                "status must be APPROVED, DEPRECATED, or ROLLED_BACK."
            )
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _normalize_optional_json_object(value: dict[str, object] | None) -> dict[str, object]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise DocumentValidationError("metadataJson must be a JSON object.")
        try:
            return canonicalize_params_dict(value)
        except PreprocessPipelineError as error:
            raise DocumentValidationError(
                "metadataJson must contain JSON-serializable values."
            ) from error

    @staticmethod
    def _normalize_assignment_reason(value: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 800:
            raise DocumentValidationError(
                "assignmentReason must be between 1 and 800 characters."
            )
        return normalized

    def _resolve_transcription_input_preprocess_run_id(
        self,
        *,
        project_id: str,
        document_id: str,
        explicit_input_preprocess_run_id: str | None,
    ) -> str:
        normalized = self._normalize_transcription_reference(
            explicit_input_preprocess_run_id,
            field_name="inputPreprocessRunId",
        )
        if normalized is not None:
            return normalized
        projection = self._store.get_preprocess_projection(
            project_id=project_id,
            document_id=document_id,
        )
        if projection is None or not projection.active_preprocess_run_id:
            raise DocumentTranscriptionConflictError(
                "Transcription run creation requires inputPreprocessRunId or an active preprocess projection."
            )
        return projection.active_preprocess_run_id

    def _resolve_transcription_layout_basis(
        self,
        *,
        project_id: str,
        document_id: str,
        explicit_layout_run_id: str | None,
    ) -> tuple[str, str]:
        normalized_layout_run_id = self._normalize_transcription_reference(
            explicit_layout_run_id,
            field_name="inputLayoutRunId",
        )
        projection = self._store.get_layout_projection(
            project_id=project_id,
            document_id=document_id,
        )
        if projection is None:
            raise DocumentTranscriptionConflictError(
                "Transcription run creation requires an active layout projection."
            )
        if (
            normalized_layout_run_id is not None
            and projection.active_layout_run_id is not None
            and normalized_layout_run_id != projection.active_layout_run_id
        ):
            raise DocumentTranscriptionConflictError(
                "Transcription run creation must target the currently active layout basis."
            )
        layout_run_id = normalized_layout_run_id or projection.active_layout_run_id
        if not layout_run_id:
            raise DocumentTranscriptionConflictError(
                "Transcription run creation requires inputLayoutRunId or an active layout projection."
            )
        if projection.active_layout_snapshot_hash is None:
            raise DocumentTranscriptionConflictError(
                "Active layout projection must include a snapshot hash before transcription runs can be created."
            )
        return layout_run_id, projection.active_layout_snapshot_hash

    @staticmethod
    def _normalize_preprocess_profile_id(value: str | None) -> str:
        try:
            return normalize_profile_id(value)
        except PreprocessPipelineError as error:
            raise DocumentValidationError(str(error)) from error

    @staticmethod
    def _normalize_preprocess_pipeline_version(value: str | None) -> str:
        if not isinstance(value, str):
            return _PREPROCESS_DEFAULT_PIPELINE_VERSION
        normalized = value.strip()
        if not normalized:
            return _PREPROCESS_DEFAULT_PIPELINE_VERSION
        if len(normalized) > 120:
            raise DocumentValidationError("pipelineVersion must be 120 characters or fewer.")
        return normalized

    @staticmethod
    def _normalize_preprocess_container_digest(value: str | None) -> str:
        if not isinstance(value, str):
            return _PREPROCESS_DEFAULT_CONTAINER_DIGEST
        normalized = value.strip()
        if not normalized:
            return _PREPROCESS_DEFAULT_CONTAINER_DIGEST
        if len(normalized) > 180:
            raise DocumentValidationError("containerDigest must be 180 characters or fewer.")
        return normalized

    @staticmethod
    def _normalize_preprocess_params_json(
        value: dict[str, object] | None,
    ) -> dict[str, object]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise DocumentValidationError("paramsJson must be a JSON object.")
        try:
            return canonicalize_params_dict(value)
        except PreprocessPipelineError as error:
            raise DocumentValidationError("paramsJson must contain JSON-serializable values.") from error

    @staticmethod
    def _normalize_preprocess_target_page_ids(
        value: list[str] | None,
    ) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise DocumentValidationError("targetPageIds must be an array of page IDs.")
        normalized: list[str] = []
        seen: set[str] = set()
        for candidate in value:
            page_id = candidate.strip() if isinstance(candidate, str) else str(candidate).strip()
            if not page_id or page_id in seen:
                continue
            seen.add(page_id)
            normalized.append(page_id)
        if not normalized:
            raise DocumentValidationError("targetPageIds must include at least one page.")
        return normalized

    @staticmethod
    def _resolve_preprocess_run_scope(
        *,
        target_page_ids: list[str] | None,
    ) -> PreprocessRunScope:
        if target_page_ids:
            return "PAGE_SUBSET"
        return "FULL_DOCUMENT"

    @staticmethod
    def _normalize_advanced_risk_acknowledgement(value: str | None) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 400:
            raise DocumentValidationError(
                "advancedRiskAcknowledgement must be 400 characters or fewer."
            )
        return normalized

    @staticmethod
    def _coerce_metric_number(value: object) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return float(value)
        if isinstance(value, float):
            return value
        return None

    @classmethod
    def _extract_layout_metric(
        cls,
        *,
        metrics_json: dict[str, object],
        keys: tuple[str, ...],
    ) -> float | None:
        for key in keys:
            value = cls._coerce_metric_number(metrics_json.get(key))
            if value is not None:
                return value
        return None

    @classmethod
    def _build_compare_metric_deltas(
        cls,
        *,
        base_result: PagePreprocessResultRecord | None,
        candidate_result: PagePreprocessResultRecord | None,
    ) -> dict[str, float | None]:
        deltas: dict[str, float | None] = {}
        base_metrics = base_result.metrics_json if base_result is not None else {}
        candidate_metrics = (
            candidate_result.metrics_json if candidate_result is not None else {}
        )
        for metric_key in _COMPARE_METRIC_DELTA_KEYS:
            base_value = cls._coerce_metric_number(base_metrics.get(metric_key))
            candidate_value = cls._coerce_metric_number(candidate_metrics.get(metric_key))
            if base_value is None and candidate_value is None:
                continue
            if base_value is None or candidate_value is None:
                deltas[metric_key] = None
                continue
            deltas[metric_key] = round(candidate_value - base_value, 6)
        return deltas

    @staticmethod
    def _is_output_available(
        result: PagePreprocessResultRecord | None,
        *,
        variant: str,
    ) -> bool:
        if result is None or result.status != "SUCCEEDED":
            return False
        if variant == "gray":
            return bool(result.output_object_key_gray)
        if variant == "bin":
            return bool(result.output_object_key_bin)
        return False

    def _apply_preprocess_risk_posture(
        self,
        *,
        expanded_params_json: dict[str, object],
        profile_is_advanced: bool,
        profile_is_gated: bool,
        run_scope: PreprocessRunScope,
        mutation_role: str,
        actor_user_id: str,
        advanced_risk_confirmed: bool | None,
        advanced_risk_acknowledgement: str | None,
    ) -> dict[str, object]:
        confirmation_required = run_scope == "FULL_DOCUMENT" and profile_is_gated
        risk_posture = "ADVANCED_GATED" if profile_is_advanced else "SAFE_DEFAULT"
        enriched = dict(expanded_params_json)
        enriched["profile_risk_posture"] = risk_posture
        enriched["advanced_risk_confirmation_required"] = confirmation_required
        if confirmation_required:
            if mutation_role not in _ALLOWED_PREPROCESS_ADVANCED_CONFIRMATION_ROLES:
                raise DocumentPreprocessAccessDeniedError(
                    "Current role cannot confirm advanced bulk preprocessing."
                )
            if advanced_risk_confirmed is not True:
                raise DocumentPreprocessConflictError(
                    "Advanced full-document preprocessing requires explicit risk confirmation."
                )
            normalized_ack = self._normalize_advanced_risk_acknowledgement(
                advanced_risk_acknowledgement
            )
            if normalized_ack is None:
                normalized_ack = _PREPROCESS_ADVANCED_BULK_CONFIRMATION_COPY
            enriched["advanced_risk_confirmation"] = {
                "confirmed": True,
                "confirmed_by_role": mutation_role,
                "confirmed_by_user_id": actor_user_id,
                "acknowledgement": normalized_ack,
            }
        else:
            enriched["advanced_risk_confirmation"] = {
                "confirmed": False,
                "confirmed_by_role": None,
                "confirmed_by_user_id": None,
                "acknowledgement": None,
            }
        return canonicalize_params_dict(enriched)

    def _prepare_upload(self, *, file_stream: BinaryIO) -> PreparedUpload:
        hasher = hashlib.sha256()
        byte_count = 0
        magic = bytearray()
        temp_handle = tempfile.NamedTemporaryFile(prefix="ukde-upload-", suffix=".bin", delete=False)
        temp_path = Path(temp_handle.name)
        try:
            while True:
                chunk = file_stream.read(_UPLOAD_CHUNK_BYTES)
                if chunk in (b"", None):
                    break
                if isinstance(chunk, bytearray):
                    chunk = bytes(chunk)
                if not isinstance(chunk, bytes):
                    raise DocumentValidationError("Upload stream produced an unsupported chunk type.")
                byte_count += len(chunk)
                if byte_count > self._settings.documents_max_upload_bytes:
                    raise DocumentValidationError(
                        "File exceeds the configured maximum upload size."
                    )
                if len(magic) < _MAGIC_PROBE_BYTES:
                    missing = _MAGIC_PROBE_BYTES - len(magic)
                    magic.extend(chunk[:missing])
                hasher.update(chunk)
                temp_handle.write(chunk)
        except Exception:
            temp_handle.close()
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        finally:
            temp_handle.close()

        if byte_count < 1:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise DocumentValidationError("Uploaded file is empty.")

        return PreparedUpload(
            temp_path=temp_path,
            byte_count=byte_count,
            sha256=hasher.hexdigest(),
            magic_prefix=bytes(magic),
        )

    def _require_project_quota(
        self,
        *,
        project_id: str,
        byte_count: int,
        check_document_count: bool = True,
    ) -> None:
        current_usage = self._store.get_project_byte_usage(project_id=project_id)
        projected_usage = current_usage + byte_count
        if projected_usage > self._settings.documents_project_quota_bytes:
            raise DocumentQuotaExceededError(
                "Project storage quota exceeded for this upload."
            )
        if check_document_count:
            current_document_count = self._store.get_project_document_count(
                project_id=project_id
            )
            if current_document_count + 1 > self._settings.documents_project_quota_documents:
                raise DocumentQuotaExceededError(
                    "Project document count quota exceeded for this upload."
                )

    def _require_project_page_quota(
        self,
        *,
        project_id: str,
        additional_pages: int,
    ) -> None:
        if additional_pages < 0:
            raise DocumentValidationError("additional_pages must be zero or greater.")
        current_page_usage = self._store.get_project_page_usage(project_id=project_id)
        projected_page_usage = current_page_usage + additional_pages
        if projected_page_usage > self._settings.documents_project_quota_pages:
            raise DocumentQuotaExceededError(
                "Project page quota exceeded for this document processing run."
            )

    def _mark_import_failed_best_effort(
        self,
        *,
        project_id: str,
        import_id: str,
        failure_reason: str,
    ) -> None:
        try:
            self._store.mark_import_failed(
                project_id=project_id,
                import_id=import_id,
                failure_reason=failure_reason,
            )
        except DocumentStoreUnavailableError:
            return

    def _record_upload_processing_run_failure_best_effort(
        self,
        *,
        project_id: str,
        import_id: str,
        failure_reason: str,
    ) -> None:
        try:
            snapshot = self._load_snapshot(project_id=project_id, import_id=import_id)
        except Exception:  # noqa: BLE001
            return
        try:
            self._record_upload_processing_run(
                snapshot=snapshot,
                status="FAILED",
                failure_reason=failure_reason,
            )
        except Exception:  # noqa: BLE001
            return

    @staticmethod
    def _to_iso8601(timestamp: datetime) -> str:
        return timestamp.isoformat()

    @staticmethod
    def _build_source_metadata(snapshot: DocumentImportSnapshot) -> dict[str, object]:
        document = snapshot.document_record
        import_record = snapshot.import_record
        if (
            not document.stored_filename
            or not document.content_type_detected
            or document.bytes is None
            or not document.sha256
        ):
            raise DocumentValidationError("Stored upload metadata was incomplete.")

        return {
            "schemaVersion": 1,
            "projectId": document.project_id,
            "documentId": document.id,
            "importId": import_record.id,
            "documentStatus": document.status,
            "importStatus": import_record.status,
            "originalFilename": document.original_filename,
            "storedFilename": document.stored_filename,
            "contentTypeDetected": document.content_type_detected,
            "bytes": document.bytes,
            "sha256": document.sha256,
            "createdBy": document.created_by,
            "uploadCreatedAt": DocumentService._to_iso8601(import_record.created_at),
            "uploadStoredAt": DocumentService._to_iso8601(import_record.updated_at),
            "documentCreatedAt": DocumentService._to_iso8601(document.created_at),
            "documentUpdatedAt": DocumentService._to_iso8601(document.updated_at),
        }

    @staticmethod
    def _verify_stored_payload_integrity(
        *,
        file_path: Path,
        expected_sha256: str,
        expected_bytes: int,
    ) -> None:
        hasher = hashlib.sha256()
        byte_count = 0
        try:
            with file_path.open("rb") as handle:
                while True:
                    chunk = handle.read(_UPLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    byte_count += len(chunk)
                    hasher.update(chunk)
        except OSError as error:
            raise DocumentStorageError(
                "Stored upload payload could not be read for integrity verification."
            ) from error

        if byte_count != expected_bytes or hasher.hexdigest() != expected_sha256:
            raise DocumentStorageError("Stored upload integrity verification failed.")

    @staticmethod
    def _resolve_file_integrity(
        *,
        file_path: Path,
    ) -> tuple[int, str, bytes]:
        hasher = hashlib.sha256()
        byte_count = 0
        magic = bytearray()
        try:
            with file_path.open("rb") as handle:
                while True:
                    chunk = handle.read(_UPLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    byte_count += len(chunk)
                    hasher.update(chunk)
                    if len(magic) < _MAGIC_PROBE_BYTES:
                        missing = _MAGIC_PROBE_BYTES - len(magic)
                        magic.extend(chunk[:missing])
        except OSError as error:
            raise DocumentStorageError("Stored upload payload could not be hashed.") from error

        return byte_count, hasher.hexdigest(), bytes(magic)

    def _record_upload_processing_run(
        self,
        *,
        snapshot: DocumentImportSnapshot,
        status: str,
        failure_reason: str | None = None,
    ) -> None:
        run = self._store.create_processing_run(
            project_id=snapshot.document_record.project_id,
            document_id=snapshot.document_record.id,
            run_kind="UPLOAD",
            created_by=snapshot.document_record.created_by,
            status="RUNNING",
        )
        if status == "SUCCEEDED":
            self._store.transition_processing_run(
                project_id=snapshot.document_record.project_id,
                run_id=run.id,
                status="SUCCEEDED",
            )
        elif status == "FAILED":
            self._store.transition_processing_run(
                project_id=snapshot.document_record.project_id,
                run_id=run.id,
                status="FAILED",
                failure_reason=failure_reason,
            )

    def _start_scan_processing_run(self, *, project_id: str, document_id: str, created_by: str) -> None:
        self._store.create_processing_run(
            project_id=project_id,
            document_id=document_id,
            run_kind="SCAN",
            created_by=created_by,
            status="RUNNING",
        )

    def _finish_latest_scan_processing_run(
        self,
        *,
        project_id: str,
        document_id: str,
        status: str,
        failure_reason: str | None = None,
    ) -> None:
        runs = self._store.list_document_timeline(
            project_id=project_id,
            document_id=document_id,
            limit=200,
        )
        target = next(
            (
                run
                for run in runs
                if run.run_kind == "SCAN" and run.status == "RUNNING"
            ),
            None,
        )
        if target is None:
            return
        if status == "SUCCEEDED":
            self._store.transition_processing_run(
                project_id=project_id,
                run_id=target.id,
                status="SUCCEEDED",
            )
            return
        if status == "FAILED":
            self._store.transition_processing_run(
                project_id=project_id,
                run_id=target.id,
                status="FAILED",
                failure_reason=failure_reason,
            )
            return
        if status == "CANCELED":
            self._store.transition_processing_run(
                project_id=project_id,
                run_id=target.id,
                status="CANCELED",
            )

    def _build_extracted_page_records(
        self,
        *,
        project_id: str,
        document_id: str,
        source_content_type: str,
        source_payload: bytes,
    ) -> list[dict[str, object]]:
        metadata = resolve_source_metadata(
            content_type=source_content_type,
            payload=source_payload,
        )
        placeholder = placeholder_png_bytes()
        placeholder_sha = hashlib.sha256(placeholder).hexdigest()
        rows: list[dict[str, object]] = []
        for page_index in range(metadata.page_count):
            stored = self._storage.write_derived_page_image(
                project_id=project_id,
                document_id=document_id,
                page_index=page_index,
                payload=placeholder,
            )
            rows.append(
                {
                    "id": str(uuid4()),
                    "page_index": page_index,
                    "width": metadata.width,
                    "height": metadata.height,
                    "dpi": metadata.dpi,
                    "status": "PENDING",
                    "derived_image_key": stored.object_key,
                    "derived_image_sha256": placeholder_sha,
                    "viewer_rotation": 0,
                }
            )
        return rows

    def run_extraction_job(
        self,
        *,
        project_id: str,
        document_id: str,
        created_by: str,
    ) -> int:
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        if not document.stored_filename or not document.content_type_detected:
            raise DocumentValidationError("Stored upload metadata was incomplete.")
        source_payload = self._storage.read_object_bytes(document.stored_filename)
        pages = self._build_extracted_page_records(
            project_id=project_id,
            document_id=document_id,
            source_content_type=document.content_type_detected,
            source_payload=source_payload,
        )
        existing_pages = self._store.list_document_pages(
            project_id=project_id,
            document_id=document_id,
        )
        additional_pages = max(0, len(pages) - len(existing_pages))
        self._require_project_page_quota(
            project_id=project_id,
            additional_pages=additional_pages,
        )
        self._store.replace_document_pages(
            project_id=project_id,
            document_id=document_id,
            pages=pages,
        )
        self._store.set_document_status(
            project_id=project_id,
            document_id=document_id,
            status="EXTRACTING",
        )
        return len(pages)

    def run_thumbnail_job(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> int:
        pages = self._store.list_document_pages(
            project_id=project_id,
            document_id=document_id,
        )
        thumbnail_payload = placeholder_jpeg_bytes()
        thumbnail_sha = hashlib.sha256(thumbnail_payload).hexdigest()
        for page in pages:
            stored = self._storage.write_derived_thumbnail(
                project_id=project_id,
                document_id=document_id,
                page_index=page.page_index,
                payload=thumbnail_payload,
            )
            self._store.update_page_thumbnail(
                project_id=project_id,
                document_id=document_id,
                page_id=page.id,
                thumbnail_key=stored.object_key,
                thumbnail_sha256=thumbnail_sha,
            )
        self._store.set_document_status(
            project_id=project_id,
            document_id=document_id,
            status="READY",
        )
        return len(pages)

    def _load_snapshot(self, *, project_id: str, import_id: str) -> DocumentImportSnapshot:
        snapshot = self._store.get_import_snapshot(project_id=project_id, import_id=import_id)
        if snapshot is None:
            raise DocumentImportNotFoundError("Document import not found.")
        document_record, import_record = snapshot
        return DocumentImportSnapshot(
            import_record=import_record,
            document_record=document_record,
        )

    def _load_upload_session_snapshot(
        self,
        *,
        project_id: str,
        session_id: str,
    ) -> DocumentUploadSessionSnapshot:
        session = self._store.get_upload_session(
            project_id=project_id,
            session_id=session_id,
        )
        if session is None:
            raise DocumentUploadSessionNotFoundError("Upload session not found.")
        snapshot = self._store.get_import_snapshot(
            project_id=project_id,
            import_id=session.import_id,
        )
        if snapshot is None:
            raise DocumentImportNotFoundError("Document import not found.")
        document_record, import_record = snapshot
        return DocumentUploadSessionSnapshot(
            session_record=session,
            import_record=import_record,
            document_record=document_record,
        )

    @staticmethod
    def _normalize_expected_sha256(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise DocumentValidationError("expectedSha256 must be a 64-character hex digest.")
        return normalized

    def start_upload_session(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        original_filename: str,
        expected_sha256: str | None = None,
        expected_total_bytes: int | None = None,
    ) -> DocumentUploadSessionSnapshot:
        self._require_upload_access(current_user=current_user, project_id=project_id)
        normalized_filename = self._normalize_original_filename(original_filename)
        try:
            parse_allowed_extension(normalized_filename)
        except DocumentUploadValidationError as error:
            raise DocumentValidationError(str(error)) from error

        normalized_expected_sha = self._normalize_expected_sha256(expected_sha256)
        if expected_total_bytes is not None:
            if expected_total_bytes < 1:
                raise DocumentValidationError("expectedTotalBytes must be greater than zero.")
            if expected_total_bytes > self._settings.documents_max_upload_bytes:
                raise DocumentValidationError(
                    "expectedTotalBytes exceeds the configured maximum upload size."
                )

        self._require_project_quota(
            project_id=project_id,
            byte_count=0,
            check_document_count=True,
        )
        session_id = str(uuid4())
        document_id = str(uuid4())
        import_id = str(uuid4())
        self._store.create_upload_session(
            project_id=project_id,
            session_id=session_id,
            document_id=document_id,
            import_id=import_id,
            original_filename=normalized_filename,
            created_by=current_user.user_id,
            expected_sha256=normalized_expected_sha,
            expected_total_bytes=expected_total_bytes,
        )
        return self._load_upload_session_snapshot(
            project_id=project_id,
            session_id=session_id,
        )

    def get_upload_session(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        session_id: str,
    ) -> DocumentUploadSessionSnapshot:
        self._project_service.require_member_workspace(
            current_user=current_user,
            project_id=project_id,
        )
        return self._load_upload_session_snapshot(
            project_id=project_id,
            session_id=session_id,
        )

    def append_upload_session_chunk(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        session_id: str,
        chunk_index: int,
        file_stream: BinaryIO,
    ) -> DocumentUploadSessionSnapshot:
        self._require_upload_access(current_user=current_user, project_id=project_id)
        session_snapshot = self._load_upload_session_snapshot(
            project_id=project_id,
            session_id=session_id,
        )
        session = session_snapshot.session_record
        if session.status != "ACTIVE":
            raise DocumentUploadSessionConflictError(
                f"Upload session is {session.status} and cannot accept chunks."
            )
        if chunk_index < 0:
            raise DocumentValidationError("chunkIndex must be zero or greater.")

        payload = file_stream.read()
        if isinstance(payload, bytearray):
            payload = bytes(payload)
        if not isinstance(payload, bytes):
            raise DocumentValidationError("Upload chunk stream produced an unsupported payload.")
        if len(payload) < 1:
            raise DocumentValidationError("Upload chunk payload is empty.")
        if len(payload) > self._settings.documents_resumable_chunk_bytes:
            raise DocumentValidationError(
                "Upload chunk exceeds DOCUMENTS_RESUMABLE_CHUNK_BYTES."
            )

        expected_next_chunk = session.last_chunk_index + 1
        if chunk_index > expected_next_chunk:
            raise DocumentUploadSessionConflictError(
                f"Chunk index gap detected. Resume from chunk {expected_next_chunk}."
            )

        projected_bytes = (
            session.bytes_received
            if chunk_index <= session.last_chunk_index
            else session.bytes_received + len(payload)
        )
        if projected_bytes > self._settings.documents_max_upload_bytes:
            raise DocumentValidationError(
                "File exceeds the configured maximum upload size."
            )
        if (
            session.expected_total_bytes is not None
            and projected_bytes > session.expected_total_bytes
        ):
            raise DocumentUploadSessionConflictError(
                "Chunk would exceed expectedTotalBytes for this upload session."
            )

        chunk_sha256 = hashlib.sha256(payload).hexdigest()
        wrote_chunk_path: Path | None = None
        try:
            wrote_chunk_path = self._storage.append_upload_session_chunk(
                project_id=project_id,
                session_id=session_id,
                chunk_index=chunk_index,
                payload=payload,
            )
            self._store.append_upload_session_chunk(
                project_id=project_id,
                session_id=session_id,
                chunk_index=chunk_index,
                byte_length=len(payload),
                sha256=chunk_sha256,
            )
        except DocumentUploadSessionConflictError:
            if chunk_index == expected_next_chunk and wrote_chunk_path is not None:
                wrote_chunk_path.unlink(missing_ok=True)
            raise
        except DocumentUploadSessionNotFoundError:
            raise
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError(_CONTROLLED_STORAGE_FAILURE_MESSAGE) from error

        return self._load_upload_session_snapshot(
            project_id=project_id,
            session_id=session_id,
        )

    def complete_upload_session(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        session_id: str,
    ) -> DocumentUploadSessionSnapshot:
        self._require_upload_access(current_user=current_user, project_id=project_id)
        session_snapshot = self._load_upload_session_snapshot(
            project_id=project_id,
            session_id=session_id,
        )
        session = session_snapshot.session_record
        if session.status != "ACTIVE":
            raise DocumentUploadSessionConflictError(
                f"Upload session is {session.status} and cannot be completed."
            )
        if session.last_chunk_index < 0 or session.bytes_received < 1:
            raise DocumentUploadSessionConflictError("Upload session has no persisted chunks.")
        if (
            session.expected_total_bytes is not None
            and session.bytes_received != session.expected_total_bytes
        ):
            raise DocumentUploadSessionConflictError(
                "Upload session byte count does not match expectedTotalBytes."
            )

        self._store.mark_upload_session_status(
            project_id=project_id,
            session_id=session_id,
            status="ASSEMBLING",
        )

        import_snapshot: DocumentImportSnapshot | None = None
        try:
            stored = self._storage.move_upload_session_into_original(
                project_id=project_id,
                document_id=session.document_id,
                session_id=session_id,
                last_chunk_index=session.last_chunk_index,
            )
            byte_count, sha256, magic_prefix = self._resolve_file_integrity(
                file_path=stored.absolute_path
            )
            if byte_count < 1:
                raise DocumentValidationError("Uploaded file is empty.")
            if byte_count > self._settings.documents_max_upload_bytes:
                raise DocumentValidationError(
                    "File exceeds the configured maximum upload size."
                )
            if (
                session.expected_total_bytes is not None
                and session.expected_total_bytes != byte_count
            ):
                raise DocumentValidationError(
                    "Assembled upload size did not match expectedTotalBytes."
                )
            if session.expected_sha256 and session.expected_sha256 != sha256:
                raise DocumentValidationError(
                    "Upload checksum mismatch for assembled payload."
                )

            type_result = validate_extension_matches_magic(
                filename=session.original_filename,
                prefix_bytes=magic_prefix,
            )
            self._require_project_quota(
                project_id=project_id,
                byte_count=byte_count,
                check_document_count=False,
            )
            self._store.mark_upload_queued(
                project_id=project_id,
                import_id=session.import_id,
                stored_filename=stored.object_key,
                content_type_detected=type_result.detected_content_type,
                byte_count=byte_count,
                sha256=sha256,
            )
            import_snapshot = self._load_snapshot(
                project_id=project_id,
                import_id=session.import_id,
            )
            self._storage.write_source_metadata(
                project_id=project_id,
                document_id=session.document_id,
                metadata=self._build_source_metadata(import_snapshot),
            )
            self._record_upload_processing_run(
                snapshot=import_snapshot,
                status="SUCCEEDED",
            )
            self._store.mark_upload_session_status(
                project_id=project_id,
                session_id=session_id,
                status="COMPLETED",
            )
            try:
                self._storage.clear_upload_session_chunks(
                    project_id=project_id,
                    session_id=session_id,
                )
            except DocumentStorageError:
                pass
        except (
            DocumentValidationError,
            DocumentQuotaExceededError,
            DocumentUploadValidationError,
            DocumentStorageError,
        ) as error:
            self._mark_import_failed_best_effort(
                project_id=project_id,
                import_id=session.import_id,
                failure_reason=str(error),
            )
            self._record_upload_processing_run_failure_best_effort(
                project_id=project_id,
                import_id=session.import_id,
                failure_reason=str(error),
            )
            self._store.mark_upload_session_status(
                project_id=project_id,
                session_id=session_id,
                status="FAILED",
                failure_reason=str(error),
            )
            if isinstance(error, DocumentStorageError):
                raise DocumentStoreUnavailableError(
                    _CONTROLLED_STORAGE_FAILURE_MESSAGE
                ) from error
            raise

        return self._load_upload_session_snapshot(
            project_id=project_id,
            session_id=session_id,
        )

    def cancel_upload_session(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        session_id: str,
    ) -> DocumentUploadSessionSnapshot:
        self._require_upload_access(current_user=current_user, project_id=project_id)
        session_snapshot = self._load_upload_session_snapshot(
            project_id=project_id,
            session_id=session_id,
        )
        session = session_snapshot.session_record
        if session.status in {"FAILED", "CANCELED", "COMPLETED"}:
            raise DocumentUploadSessionConflictError(
                f"Upload session is already {session.status}."
            )
        self._store.mark_upload_session_status(
            project_id=project_id,
            session_id=session_id,
            status="CANCELED",
        )
        self._store.cancel_import(
            project_id=project_id,
            import_id=session.import_id,
            canceled_by=current_user.user_id,
        )
        try:
            self._storage.clear_upload_session_chunks(
                project_id=project_id,
                session_id=session_id,
            )
        except DocumentStorageError:
            pass
        return self._load_upload_session_snapshot(
            project_id=project_id,
            session_id=session_id,
        )

    def list_documents(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        filters: DocumentListFilters,
    ) -> tuple[list[DocumentRecord], int | None]:
        self._project_service.require_member_workspace(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_filters = self._normalize_filters(filters)
        return self._store.list_documents(project_id=project_id, filters=normalized_filters)

    def get_document(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentRecord:
        self._project_service.require_member_workspace(
            current_user=current_user,
            project_id=project_id,
        )
        record = self._store.get_document(project_id=project_id, document_id=document_id)
        if record is None:
            raise DocumentNotFoundError("Document not found.")
        return record

    def list_document_timeline(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        limit: int = 100,
    ) -> list[DocumentProcessingRunRecord]:
        self._project_service.require_member_workspace(
            current_user=current_user,
            project_id=project_id,
        )
        return self._store.list_document_timeline(
            project_id=project_id,
            document_id=document_id,
            limit=limit,
        )

    def get_document_processing_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentProcessingRunRecord:
        self._project_service.require_member_workspace(
            current_user=current_user,
            project_id=project_id,
        )
        run = self._store.get_processing_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentProcessingRunNotFoundError("Processing run not found.")
        return run

    def retry_document_extraction(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentProcessingRunRecord:
        self._require_retry_extraction_access(
            current_user=current_user,
            project_id=project_id,
        )
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")

        target = self._store.get_latest_processing_run_by_kind(
            project_id=project_id,
            document_id=document_id,
            run_kind="EXTRACTION",
            include_superseded=False,
        )
        if target is None:
            raise DocumentRetryConflictError(
                "No extraction attempt is available for retry."
            )
        if target.status not in {"FAILED", "CANCELED"}:
            raise DocumentRetryConflictError(
                "Retry is allowed only when the latest extraction attempt is FAILED or CANCELED."
            )

        try:
            retry_run = self._store.create_processing_run(
                project_id=project_id,
                document_id=document_id,
                run_kind="EXTRACTION",
                created_by=current_user.user_id,
                status="QUEUED",
                supersedes_processing_run_id=target.id,
            )
        except DocumentProcessingRunConflictError as error:
            raise DocumentRetryConflictError(str(error)) from error

        from app.jobs.service import get_job_service

        job_service = get_job_service()
        _, created, reason = job_service.enqueue_document_processing_job(
            project_id=project_id,
            document_id=document_id,
            job_type="EXTRACT_PAGES",
            created_by=current_user.user_id,
            processing_run_id=retry_run.id,
        )
        if not created:
            self._store.transition_processing_run(
                project_id=project_id,
                run_id=retry_run.id,
                status="FAILED",
                failure_reason=f"Retry enqueue skipped due to existing job state: {reason}.",
            )
            raise DocumentRetryConflictError(
                "Extraction retry was not queued because an equivalent job is already active or succeeded."
            )

        self._store.set_document_status(
            project_id=project_id,
            document_id=document_id,
            status="EXTRACTING",
        )
        return retry_run

    def _list_all_preprocess_page_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        status: PreprocessPageResultStatus | None = None,
        warning: str | None = None,
    ) -> list[PagePreprocessResultRecord]:
        items: list[PagePreprocessResultRecord] = []
        cursor = 0
        while True:
            batch, next_cursor = self._store.list_preprocess_page_results(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                status=status,
                warning=warning,
                cursor=cursor,
                page_size=500,
            )
            items.extend(batch)
            if next_cursor is None:
                break
            cursor = next_cursor
        return items

    def _list_all_layout_page_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        status: PageLayoutResultStatus | None = None,
        page_recall_status: PageRecallStatus | None = None,
    ) -> list[PageLayoutResultRecord]:
        items: list[PageLayoutResultRecord] = []
        cursor = 0
        while True:
            batch, next_cursor = self._store.list_page_layout_results(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                status=status,
                page_recall_status=page_recall_status,
                cursor=cursor,
                page_size=500,
            )
            items.extend(batch)
            if next_cursor is None:
                break
            cursor = next_cursor
        return items

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
        if cursor < 0:
            raise DocumentValidationError("Cursor must be zero or greater.")
        if page_size < 1 or page_size > 200:
            raise DocumentValidationError("Page size must be between 1 and 200.")
        return self._store.list_preprocess_runs(
            project_id=project_id,
            document_id=document_id,
            cursor=cursor,
            page_size=page_size,
        )

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
        run = self._store.get_preprocess_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentPreprocessRunNotFoundError("Preprocessing run not found.")
        return run

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
        return self._store.get_preprocess_projection(
            project_id=project_id,
            document_id=document_id,
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
        return self._store.get_preprocess_downstream_basis_references(
            project_id=project_id,
            document_id=document_id,
        )

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
        projection = self._store.get_preprocess_projection(
            project_id=project_id,
            document_id=document_id,
        )
        run = self._store.get_active_preprocess_run(
            project_id=project_id,
            document_id=document_id,
        )
        return projection, run

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
        mutation_role = self._require_preprocess_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_profile_id = self._normalize_preprocess_profile_id(profile_id)
        normalized_params_json = self._normalize_preprocess_params_json(params_json)
        normalized_target_page_ids = self._normalize_preprocess_target_page_ids(
            target_page_ids
        )
        run_scope = self._resolve_preprocess_run_scope(
            target_page_ids=normalized_target_page_ids
        )
        try:
            expanded_profile_id, expanded_params_json = expand_profile_params(
                profile_id=normalized_profile_id,
                params_json=normalized_params_json,
            )
            profile_definition = get_preprocess_profile_definition(expanded_profile_id)
        except PreprocessPipelineError as error:
            raise DocumentValidationError(str(error)) from error
        persisted_profile = self._store.get_latest_preprocess_profile(
            profile_id=profile_definition.profile_id
        )
        if persisted_profile is None:
            raise DocumentStoreUnavailableError(
                "Preprocess profile registry is not initialized."
            )
        normalized_params_json = self._apply_preprocess_risk_posture(
            expanded_params_json=expanded_params_json,
            profile_is_advanced=persisted_profile.is_advanced,
            profile_is_gated=persisted_profile.is_gated,
            run_scope=run_scope,
            mutation_role=mutation_role,
            actor_user_id=current_user.user_id,
            advanced_risk_confirmed=advanced_risk_confirmed,
            advanced_risk_acknowledgement=advanced_risk_acknowledgement,
        )
        normalized_pipeline_version = self._normalize_preprocess_pipeline_version(
            pipeline_version
        )
        normalized_container_digest = self._normalize_preprocess_container_digest(
            container_digest
        )
        try:
            run = self._store.create_preprocess_run(
                project_id=project_id,
                document_id=document_id,
                created_by=current_user.user_id,
                profile_id=expanded_profile_id,
                profile_version=persisted_profile.profile_version,
                profile_revision=persisted_profile.profile_revision,
                profile_label=persisted_profile.label,
                profile_description=persisted_profile.description,
                profile_params_hash=persisted_profile.params_hash,
                profile_is_advanced=persisted_profile.is_advanced,
                profile_is_gated=persisted_profile.is_gated,
                params_json=normalized_params_json,
                pipeline_version=normalized_pipeline_version,
                container_digest=normalized_container_digest,
                manifest_schema_version=2,
                parent_run_id=parent_run_id,
                supersedes_run_id=supersedes_run_id,
                run_scope=run_scope,
                target_page_ids_json=normalized_target_page_ids,
            )
            from app.jobs.service import get_job_service

            try:
                get_job_service().enqueue_preprocess_document_job(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run.id,
                    created_by=current_user.user_id,
                )
            except Exception as error:  # noqa: BLE001
                raise DocumentStoreUnavailableError(
                    "Preprocess run queueing failed."
                ) from error
            return run
        except DocumentPreprocessRunConflictError as error:
            raise DocumentPreprocessConflictError(str(error)) from error

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
        self._require_preprocess_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        source_run = self._store.get_preprocess_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if source_run is None:
            raise DocumentPreprocessRunNotFoundError("Preprocessing run not found.")
        if source_run.status in {"QUEUED", "RUNNING"}:
            raise DocumentPreprocessConflictError(
                "Rerun requires a terminal source run."
            )
        normalized_target_page_ids = self._normalize_preprocess_target_page_ids(
            target_page_ids
        )
        if normalized_target_page_ids is not None:
            source_page_results = self._list_all_preprocess_page_results(
                project_id=project_id,
                document_id=document_id,
                run_id=source_run.id,
            )
            source_page_ids = {result.page_id for result in source_page_results}
            unknown_page_ids = [
                page_id
                for page_id in normalized_target_page_ids
                if page_id not in source_page_ids
            ]
            if unknown_page_ids:
                raise DocumentValidationError(
                    "targetPageIds must reference pages present in the source run."
                )
        resolved_profile_id = (
            profile_id if profile_id is not None else source_run.profile_id
        )
        source_params = params_json if params_json is not None else source_run.params_json
        resolved_params = dict(source_params)
        if normalized_target_page_ids is None:
            resolved_params.pop("target_page_ids", None)
        else:
            resolved_params["target_page_ids"] = list(normalized_target_page_ids)
        resolved_pipeline_version = (
            pipeline_version
            if pipeline_version is not None
            else source_run.pipeline_version
        )
        resolved_container_digest = (
            container_digest
            if container_digest is not None
            else source_run.container_digest
        )
        return self.create_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            profile_id=resolved_profile_id,
            params_json=resolved_params,
            pipeline_version=resolved_pipeline_version,
            container_digest=resolved_container_digest,
            parent_run_id=source_run.parent_run_id or source_run.id,
            supersedes_run_id=source_run.id,
            target_page_ids=normalized_target_page_ids,
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
        try:
            return self._store.cancel_preprocess_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                canceled_by=current_user.user_id,
            )
        except DocumentPreprocessRunConflictError as error:
            raise DocumentPreprocessConflictError(str(error)) from error

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
        try:
            return self._store.activate_preprocess_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except DocumentPreprocessRunConflictError as error:
            raise DocumentPreprocessConflictError(str(error)) from error

    def list_preprocess_run_pages(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        status: PreprocessPageResultStatus | None = None,
        warning: str | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[list[PagePreprocessResultRecord], int | None]:
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        if cursor < 0:
            raise DocumentValidationError("Cursor must be zero or greater.")
        if page_size < 1 or page_size > 500:
            raise DocumentValidationError("Page size must be between 1 and 500.")
        run = self._store.get_preprocess_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentPreprocessRunNotFoundError("Preprocessing run not found.")
        return self._store.list_preprocess_page_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            status=status,
            warning=warning,
            cursor=cursor,
            page_size=page_size,
        )

    def get_preprocess_run_page(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PagePreprocessResultRecord:
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        run = self._store.get_preprocess_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentPreprocessRunNotFoundError("Preprocessing run not found.")
        page_result = self._store.get_preprocess_page_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if page_result is None:
            raise DocumentPageNotFoundError("Preprocessing page result not found.")
        return page_result

    def list_preprocessing_quality(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str | None = None,
        status: PreprocessPageResultStatus | None = None,
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
        if cursor < 0:
            raise DocumentValidationError("Cursor must be zero or greater.")
        if page_size < 1 or page_size > 500:
            raise DocumentValidationError("Page size must be between 1 and 500.")

        projection = self._store.get_preprocess_projection(
            project_id=project_id,
            document_id=document_id,
        )
        target_run: PreprocessRunRecord | None = None
        if isinstance(run_id, str) and run_id.strip():
            target_run = self._store.get_preprocess_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id.strip(),
            )
            if target_run is None:
                raise DocumentPreprocessRunNotFoundError("Preprocessing run not found.")
        elif projection is not None and projection.active_preprocess_run_id:
            target_run = self._store.get_preprocess_run(
                project_id=project_id,
                document_id=document_id,
                run_id=projection.active_preprocess_run_id,
            )
        if target_run is None:
            return projection, None, [], None

        items, next_cursor = self._store.list_preprocess_page_results(
            project_id=project_id,
            document_id=document_id,
            run_id=target_run.id,
            status=status,
            warning=warning,
            cursor=cursor,
            page_size=page_size,
        )
        return projection, target_run, items, next_cursor

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
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        projection = self._store.get_preprocess_projection(
            project_id=project_id,
            document_id=document_id,
        )
        active_run = self._store.get_active_preprocess_run(
            project_id=project_id,
            document_id=document_id,
        )
        all_runs: list[PreprocessRunRecord] = []
        list_cursor = 0
        while True:
            batch, next_cursor = self._store.list_preprocess_runs(
                project_id=project_id,
                document_id=document_id,
                cursor=list_cursor,
                page_size=200,
            )
            all_runs.extend(batch)
            if next_cursor is None:
                break
            list_cursor = next_cursor
        latest_run = all_runs[0] if all_runs else None

        page_count = len(
            self._store.list_document_pages(
                project_id=project_id,
                document_id=document_id,
            )
        )
        status_counts: dict[PreprocessPageResultStatus, int] = {
            "QUEUED": 0,
            "RUNNING": 0,
            "SUCCEEDED": 0,
            "FAILED": 0,
            "CANCELED": 0,
        }
        quality_counts: dict[PreprocessQualityGateStatus, int] = {
            "PASS": 0,
            "REVIEW_REQUIRED": 0,
            "BLOCKED": 0,
        }
        warning_count = 0
        if active_run is not None:
            active_results = self._list_all_preprocess_page_results(
                project_id=project_id,
                document_id=document_id,
                run_id=active_run.id,
            )
            for result in active_results:
                status_counts[result.status] += 1
                quality_counts[result.quality_gate_status] += 1
                warning_count += len(result.warnings_json)

        return DocumentPreprocessOverviewSnapshot(
            document=document,
            projection=projection,
            active_run=active_run,
            latest_run=latest_run,
            total_runs=len(all_runs),
            page_count=page_count,
            active_status_counts=status_counts,
            active_quality_gate_counts=quality_counts,
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
        self._require_preprocess_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        if base_run_id == candidate_run_id:
            raise DocumentValidationError(
                "baseRunId and candidateRunId must reference different runs."
            )
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        base_run = self._store.get_preprocess_run(
            project_id=project_id,
            document_id=document_id,
            run_id=base_run_id,
        )
        if base_run is None:
            raise DocumentPreprocessRunNotFoundError("Base preprocessing run not found.")
        candidate_run = self._store.get_preprocess_run(
            project_id=project_id,
            document_id=document_id,
            run_id=candidate_run_id,
        )
        if candidate_run is None:
            raise DocumentPreprocessRunNotFoundError(
                "Candidate preprocessing run not found."
            )
        base_results = self._list_all_preprocess_page_results(
            project_id=project_id,
            document_id=document_id,
            run_id=base_run.id,
        )
        candidate_results = self._list_all_preprocess_page_results(
            project_id=project_id,
            document_id=document_id,
            run_id=candidate_run.id,
        )

        base_warning_count = sum(len(item.warnings_json) for item in base_results)
        candidate_warning_count = sum(len(item.warnings_json) for item in candidate_results)
        base_blocked_count = sum(
            1 for item in base_results if item.quality_gate_status == "BLOCKED"
        )
        candidate_blocked_count = sum(
            1 for item in candidate_results if item.quality_gate_status == "BLOCKED"
        )

        index: dict[str, dict[str, object]] = {}
        for item in base_results:
            index[item.page_id] = {
                "page_index": item.page_index,
                "base": item,
                "candidate": None,
            }
        for item in candidate_results:
            if item.page_id in index:
                index[item.page_id]["candidate"] = item
            else:
                index[item.page_id] = {
                    "page_index": item.page_index,
                    "base": None,
                    "candidate": item,
                }

        page_pairs: list[DocumentPreprocessComparePageSnapshot] = []
        for page_id, entry in sorted(
            index.items(),
            key=lambda item: (int(item[1]["page_index"]), item[0]),
        ):
            base_result = entry["base"]  # type: ignore[assignment]
            candidate_result = entry["candidate"]  # type: ignore[assignment]
            base_warning_set = (
                set(base_result.warnings_json) if base_result is not None else set()
            )
            candidate_warning_set = (
                set(candidate_result.warnings_json)
                if candidate_result is not None
                else set()
            )
            page_pairs.append(
                DocumentPreprocessComparePageSnapshot(
                    page_id=page_id,
                    page_index=int(entry["page_index"]),
                    base_result=base_result,
                    candidate_result=candidate_result,
                    warning_delta=len(candidate_warning_set) - len(base_warning_set),
                    added_warnings=sorted(candidate_warning_set - base_warning_set),
                    removed_warnings=sorted(base_warning_set - candidate_warning_set),
                    metric_deltas=self._build_compare_metric_deltas(
                        base_result=base_result,
                        candidate_result=candidate_result,
                    ),
                    output_availability={
                        "baseGray": self._is_output_available(
                            base_result,
                            variant="gray",
                        ),
                        "baseBin": self._is_output_available(
                            base_result,
                            variant="bin",
                        ),
                        "candidateGray": self._is_output_available(
                            candidate_result,
                            variant="gray",
                        ),
                        "candidateBin": self._is_output_available(
                            candidate_result,
                            variant="bin",
                        ),
                    },
                )
            )

        return DocumentPreprocessCompareSnapshot(
            document=document,
            base_run=base_run,
            candidate_run=candidate_run,
            page_pairs=page_pairs,
            base_warning_count=base_warning_count,
            candidate_warning_count=candidate_warning_count,
            base_blocked_count=base_blocked_count,
            candidate_blocked_count=candidate_blocked_count,
        )

    def _attach_layout_activation_gate(
        self,
        *,
        project_id: str,
        document_id: str,
        run: LayoutRunRecord,
    ) -> LayoutRunRecord:
        evaluate_gate = getattr(self._store, "evaluate_layout_activation_gate", None)
        if not callable(evaluate_gate):
            return run
        gate = evaluate_gate(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
        )
        return replace(run, activation_gate=gate)

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
        if cursor < 0:
            raise DocumentValidationError("Cursor must be zero or greater.")
        if page_size < 1 or page_size > 200:
            raise DocumentValidationError("Page size must be between 1 and 200.")
        return self._store.list_layout_runs(
            project_id=project_id,
            document_id=document_id,
            cursor=cursor,
            page_size=page_size,
        )

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
        run = self._store.get_layout_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentLayoutRunNotFoundError("Layout run not found.")
        return self._attach_layout_activation_gate(
            project_id=project_id,
            document_id=document_id,
            run=run,
        )

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
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        return self._store.get_layout_projection(
            project_id=project_id,
            document_id=document_id,
        )

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
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        projection = self._store.get_layout_projection(
            project_id=project_id,
            document_id=document_id,
        )
        run = self._store.get_active_layout_run(
            project_id=project_id,
            document_id=document_id,
        )
        if run is not None:
            run = self._attach_layout_activation_gate(
                project_id=project_id,
                document_id=document_id,
                run=run,
            )
        return projection, run

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
        _ = self._require_layout_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_input_preprocess_run_id = self._resolve_layout_input_preprocess_run_id(
            project_id=project_id,
            document_id=document_id,
            explicit_input_preprocess_run_id=input_preprocess_run_id,
        )
        normalized_model_id = self._normalize_layout_model_id(model_id)
        normalized_profile_id = self._normalize_layout_profile_id(profile_id)
        normalized_params_json = self._normalize_layout_params_json(params_json)
        normalized_pipeline_version = self._normalize_layout_pipeline_version(
            pipeline_version
        )
        normalized_container_digest = self._normalize_layout_container_digest(
            container_digest
        )
        normalized_parent_run_id = self._normalize_layout_run_reference(
            parent_run_id,
            field_name="parentRunId",
        )
        normalized_supersedes_run_id = self._normalize_layout_run_reference(
            supersedes_run_id,
            field_name="supersedesRunId",
        )
        try:
            run = self._store.create_layout_run(
                project_id=project_id,
                document_id=document_id,
                created_by=current_user.user_id,
                input_preprocess_run_id=normalized_input_preprocess_run_id,
                model_id=normalized_model_id,
                profile_id=normalized_profile_id,
                params_json=normalized_params_json,
                pipeline_version=normalized_pipeline_version,
                container_digest=normalized_container_digest,
                parent_run_id=normalized_parent_run_id,
                supersedes_run_id=normalized_supersedes_run_id,
                run_kind="AUTO",
            )
            from app.jobs.service import get_job_service

            try:
                get_job_service().enqueue_layout_document_job(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run.id,
                    created_by=current_user.user_id,
                )
            except Exception as error:  # noqa: BLE001
                raise DocumentStoreUnavailableError(
                    "Layout run queueing failed."
                ) from error
            return run
        except DocumentLayoutRunConflictError as error:
            raise DocumentLayoutConflictError(
                str(error),
                activation_gate=getattr(error, "activation_gate", None),
            ) from error

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
        try:
            return self._store.cancel_layout_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                canceled_by=current_user.user_id,
            )
        except DocumentLayoutRunConflictError as error:
            raise DocumentLayoutConflictError(
                str(error),
                activation_gate=getattr(error, "activation_gate", None),
            ) from error

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
        try:
            return self._store.activate_layout_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except DocumentLayoutRunConflictError as error:
            raise DocumentLayoutConflictError(
                str(error),
                activation_gate=getattr(error, "activation_gate", None),
            ) from error

    def list_layout_run_pages(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        status: PageLayoutResultStatus | None = None,
        page_recall_status: PageRecallStatus | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[list[PageLayoutResultRecord], int | None]:
        self._require_layout_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        if cursor < 0:
            raise DocumentValidationError("Cursor must be zero or greater.")
        if page_size < 1 or page_size > 500:
            raise DocumentValidationError("Page size must be between 1 and 500.")
        run = self._store.get_layout_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentLayoutRunNotFoundError("Layout run not found.")
        return self._store.list_page_layout_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            status=status,
            page_recall_status=page_recall_status,
            cursor=cursor,
            page_size=page_size,
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
        if cursor < 0:
            raise DocumentValidationError("Cursor must be zero or greater.")
        if page_size < 1 or page_size > 200:
            raise DocumentValidationError("Page size must be between 1 and 200.")
        return self._store.list_transcription_runs(
            project_id=project_id,
            document_id=document_id,
            cursor=cursor,
            page_size=page_size,
        )

    def list_approved_models(
        self,
        *,
        current_user: SessionPrincipal,
        model_role: str | None = None,
        status: str | None = None,
    ) -> list[ApprovedModelRecord]:
        self._require_model_catalog_view_access(current_user=current_user)
        normalized_model_role = (
            self._normalize_approved_model_role(model_role) if isinstance(model_role, str) else None
        )
        normalized_status = self._normalize_approved_model_status(status)
        return self._store.list_approved_models(
            model_role=normalized_model_role,
            status=normalized_status,
        )

    def create_approved_model(
        self,
        *,
        current_user: SessionPrincipal,
        model_type: str,
        model_role: str,
        model_family: str,
        model_version: str,
        serving_interface: str,
        engine_family: str,
        deployment_unit: str,
        artifact_subpath: str,
        checksum_sha256: str,
        runtime_profile: str,
        response_contract_version: str,
        metadata_json: dict[str, object] | None = None,
    ) -> ApprovedModelRecord:
        self._require_model_catalog_mutation_access(current_user=current_user)
        normalized_model_type = self._normalize_approved_model_type(model_type)
        normalized_model_role = self._normalize_approved_model_role(model_role)
        normalized_serving_interface = self._normalize_approved_model_serving_interface(
            serving_interface
        )
        normalized_metadata_json = self._normalize_optional_json_object(metadata_json)
        try:
            return self._store.create_approved_model(
                model_type=normalized_model_type,
                model_role=normalized_model_role,
                model_family=model_family,
                model_version=model_version,
                serving_interface=normalized_serving_interface,
                engine_family=engine_family,
                deployment_unit=deployment_unit,
                artifact_subpath=artifact_subpath,
                checksum_sha256=checksum_sha256,
                runtime_profile=runtime_profile,
                response_contract_version=response_contract_version,
                metadata_json=normalized_metadata_json,
                created_by=current_user.user_id,
            )
        except DocumentStoreModelCatalogConflictError as error:
            raise DocumentModelCatalogConflictError(str(error)) from error

    def list_project_model_assignments(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> list[ProjectModelAssignmentRecord]:
        self._require_model_assignment_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        return self._store.list_project_model_assignments(project_id=project_id)

    def create_project_model_assignment(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        model_role: str,
        approved_model_id: str,
        assignment_reason: str,
    ) -> ProjectModelAssignmentRecord:
        self._require_model_assignment_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_model_role = self._normalize_approved_model_role(model_role)
        normalized_assignment_reason = self._normalize_assignment_reason(assignment_reason)
        normalized_model_id = self._normalize_transcription_reference(
            approved_model_id,
            field_name="approvedModelId",
            max_length=160,
        )
        if normalized_model_id is None:
            raise DocumentValidationError("approvedModelId is required.")
        try:
            return self._store.create_project_model_assignment(
                project_id=project_id,
                model_role=normalized_model_role,
                approved_model_id=normalized_model_id,
                assignment_reason=normalized_assignment_reason,
                created_by=current_user.user_id,
            )
        except DocumentStoreModelAssignmentConflictError as error:
            raise DocumentModelAssignmentConflictError(str(error)) from error

    def get_project_model_assignment(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        assignment_id: str,
    ) -> ProjectModelAssignmentRecord:
        self._require_model_assignment_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        assignment = self._store.get_project_model_assignment(
            project_id=project_id,
            assignment_id=assignment_id,
        )
        if assignment is None:
            raise DocumentModelAssignmentNotFoundError("Model assignment not found.")
        return assignment

    def list_training_datasets_for_assignment(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        assignment_id: str,
    ) -> list[TrainingDatasetRecord]:
        self._require_model_assignment_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        assignment = self._store.get_project_model_assignment(
            project_id=project_id,
            assignment_id=assignment_id,
        )
        if assignment is None:
            raise DocumentModelAssignmentNotFoundError("Model assignment not found.")
        return self._store.list_training_datasets_for_assignment(
            project_id=project_id,
            assignment_id=assignment.id,
        )

    def activate_project_model_assignment(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        assignment_id: str,
    ) -> ProjectModelAssignmentRecord:
        self._require_model_assignment_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        try:
            assignment = self._store.activate_project_model_assignment(
                project_id=project_id,
                assignment_id=assignment_id,
                activated_by=current_user.user_id,
            )
        except DocumentStoreModelAssignmentConflictError as error:
            raise DocumentModelAssignmentConflictError(str(error)) from error
        if assignment is None:
            raise DocumentModelAssignmentNotFoundError("Model assignment not found.")
        return assignment

    def retire_project_model_assignment(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        assignment_id: str,
    ) -> ProjectModelAssignmentRecord:
        self._require_model_assignment_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        assignment = self._store.retire_project_model_assignment(
            project_id=project_id,
            assignment_id=assignment_id,
            retired_by=current_user.user_id,
        )
        if assignment is None:
            raise DocumentModelAssignmentNotFoundError("Model assignment not found.")
        return assignment

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
        run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        return run

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
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        return self._store.get_transcription_projection(
            project_id=project_id,
            document_id=document_id,
        )

    def get_active_transcription_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> tuple[
        DocumentTranscriptionProjectionRecord | None,
        TranscriptionRunRecord | None,
    ]:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        projection = self._store.get_transcription_projection(
            project_id=project_id,
            document_id=document_id,
        )
        run = self._store.get_active_transcription_run(
            project_id=project_id,
            document_id=document_id,
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
        _ = self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_input_preprocess_run_id = self._resolve_transcription_input_preprocess_run_id(
            project_id=project_id,
            document_id=document_id,
            explicit_input_preprocess_run_id=input_preprocess_run_id,
        )
        normalized_input_layout_run_id, normalized_layout_snapshot_hash = (
            self._resolve_transcription_layout_basis(
                project_id=project_id,
                document_id=document_id,
                explicit_layout_run_id=input_layout_run_id,
            )
        )
        normalized_engine = self._normalize_transcription_engine(engine)
        normalized_confidence_basis = self._normalize_transcription_confidence_basis(
            confidence_basis
        )
        normalized_params_json = self._normalize_transcription_params_json(params_json)
        normalized_pipeline_version = self._normalize_transcription_pipeline_version(
            pipeline_version
        )
        normalized_container_digest = self._normalize_transcription_container_digest(
            container_digest
        )
        normalized_project_model_assignment_id = self._normalize_transcription_reference(
            project_model_assignment_id,
            field_name="projectModelAssignmentId",
            max_length=160,
        )
        normalized_model_id = self._normalize_transcription_reference(
            model_id,
            field_name="modelId",
            max_length=160,
        )
        normalized_prompt_template_id = self._normalize_transcription_reference(
            prompt_template_id,
            field_name="promptTemplateId",
            max_length=160,
        )
        normalized_prompt_template_sha256 = self._normalize_transcription_reference(
            prompt_template_sha256,
            field_name="promptTemplateSha256",
            max_length=128,
        )
        normalized_supersedes_run_id = self._normalize_transcription_reference(
            supersedes_transcription_run_id,
            field_name="supersedesTranscriptionRunId",
            max_length=120,
        )
        normalized_confidence_calibration_version = (
            confidence_calibration_version.strip()
            if isinstance(confidence_calibration_version, str)
            and confidence_calibration_version.strip()
            else "v1"
        )
        expected_model_role = self._resolve_transcription_model_role(normalized_engine)
        resolved_assignment: ProjectModelAssignmentRecord | None = None
        resolved_model: ApprovedModelRecord | None = None

        if normalized_project_model_assignment_id is not None:
            resolved_assignment = self._store.get_project_model_assignment(
                project_id=project_id,
                assignment_id=normalized_project_model_assignment_id,
            )
            if resolved_assignment is None:
                raise DocumentTranscriptionConflictError(
                    "Project model assignment was not found."
                )
            if resolved_assignment.status != "ACTIVE":
                raise DocumentTranscriptionConflictError(
                    "Only ACTIVE project model assignments can launch transcription runs."
                )
            if resolved_assignment.model_role != expected_model_role:
                raise DocumentTranscriptionConflictError(
                    "Project model assignment role is incompatible with engine."
                )
            resolved_model = self._store.get_approved_model(
                model_id=resolved_assignment.approved_model_id
            )
            if resolved_model is None or resolved_model.status != "APPROVED":
                raise DocumentTranscriptionConflictError(
                    "Project model assignment does not resolve to an APPROVED model."
                )
            if resolved_model.model_role != expected_model_role:
                raise DocumentTranscriptionConflictError(
                    "Project model assignment model role is incompatible with engine."
                )
            if (
                normalized_model_id is not None
                and normalized_model_id != resolved_model.id
            ):
                raise DocumentTranscriptionConflictError(
                    "modelId must match projectModelAssignmentId when both are provided."
                )
        elif normalized_model_id is not None:
            resolved_model = self._store.get_approved_model(model_id=normalized_model_id)
            if resolved_model is None or resolved_model.status != "APPROVED":
                raise DocumentTranscriptionConflictError(
                    "Selected modelId must resolve to an APPROVED model."
                )
            if resolved_model.model_role != expected_model_role:
                raise DocumentTranscriptionConflictError(
                    "Transcription engine and approved model role are incompatible."
                )
        else:
            resolved_assignment = self._store.get_active_project_model_assignment(
                project_id=project_id,
                model_role=expected_model_role,
            )
            if resolved_assignment is not None:
                resolved_model = self._store.get_approved_model(
                    model_id=resolved_assignment.approved_model_id
                )
                if resolved_model is None or resolved_model.status != "APPROVED":
                    raise DocumentTranscriptionConflictError(
                        "Active project model assignment must resolve to an APPROVED model."
                    )
                if resolved_model.model_role != expected_model_role:
                    raise DocumentTranscriptionConflictError(
                        "Active project model assignment role is incompatible with engine."
                    )
            if resolved_model is None:
                resolved_model = self._store.get_approved_transcription_model(
                    preferred_model_role=expected_model_role
                )

        if resolved_model is None:
            raise DocumentTranscriptionConflictError(
                "No APPROVED transcription model is available."
            )

        try:
            return self._store.create_transcription_run(
                project_id=project_id,
                document_id=document_id,
                created_by=current_user.user_id,
                input_preprocess_run_id=normalized_input_preprocess_run_id,
                input_layout_run_id=normalized_input_layout_run_id,
                input_layout_snapshot_hash=normalized_layout_snapshot_hash,
                engine=normalized_engine,
                model_id=resolved_model.id,
                project_model_assignment_id=(
                    resolved_assignment.id if resolved_assignment is not None else None
                ),
                prompt_template_id=normalized_prompt_template_id,
                prompt_template_sha256=normalized_prompt_template_sha256,
                response_schema_version=max(1, int(response_schema_version)),
                confidence_basis=normalized_confidence_basis,
                confidence_calibration_version=normalized_confidence_calibration_version,
                params_json=normalized_params_json,
                pipeline_version=normalized_pipeline_version,
                container_digest=normalized_container_digest,
                supersedes_transcription_run_id=normalized_supersedes_run_id,
            )
        except DocumentTranscriptionRunConflictError as error:
            raise DocumentTranscriptionConflictError(str(error)) from error

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
        try:
            return self._store.cancel_transcription_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                canceled_by=current_user.user_id,
            )
        except DocumentTranscriptionRunConflictError as error:
            raise DocumentTranscriptionConflictError(str(error)) from error

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
        try:
            return self._store.activate_transcription_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except DocumentTranscriptionRunConflictError as error:
            raise DocumentTranscriptionConflictError(str(error)) from error

    def list_transcription_run_pages(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        status: TranscriptionRunStatus | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[list[PageTranscriptionResultRecord], int | None]:
        self._require_transcription_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        if cursor < 0:
            raise DocumentValidationError("Cursor must be zero or greater.")
        if page_size < 1 or page_size > 500:
            raise DocumentValidationError("Page size must be between 1 and 500.")
        run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        return self._store.list_page_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            status=status,
            cursor=cursor,
            page_size=page_size,
        )

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
        run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        page_row = self._store.get_page_transcription_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if page_row is None:
            raise DocumentPageNotFoundError("Transcription page result not found.")
        return self._store.list_line_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )

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
        run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        page_row = self._store.get_page_transcription_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if page_row is None:
            raise DocumentPageNotFoundError("Transcription page result not found.")
        return self._store.list_token_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )

    def _list_all_transcription_page_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        status: TranscriptionRunStatus | None = None,
    ) -> list[PageTranscriptionResultRecord]:
        items: list[PageTranscriptionResultRecord] = []
        cursor = 0
        while True:
            batch, next_cursor = self._store.list_page_transcription_results(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                status=status,
                cursor=cursor,
                page_size=500,
            )
            items.extend(batch)
            if next_cursor is None:
                break
            cursor = next_cursor
        return items

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
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        projection = self._store.get_transcription_projection(
            project_id=project_id,
            document_id=document_id,
        )
        active_run = self._store.get_active_transcription_run(
            project_id=project_id,
            document_id=document_id,
        )
        all_runs: list[TranscriptionRunRecord] = []
        list_cursor = 0
        while True:
            batch, next_cursor = self._store.list_transcription_runs(
                project_id=project_id,
                document_id=document_id,
                cursor=list_cursor,
                page_size=200,
            )
            all_runs.extend(batch)
            if next_cursor is None:
                break
            list_cursor = next_cursor
        latest_run = all_runs[0] if all_runs else None
        page_count = len(
            self._store.list_document_pages(
                project_id=project_id,
                document_id=document_id,
            )
        )
        status_counts: dict[TranscriptionRunStatus, int] = {
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
            page_results = self._list_all_transcription_page_results(
                project_id=project_id,
                document_id=document_id,
                run_id=active_run.id,
            )
            for result in page_results:
                status_counts[result.status] += 1
                line_rows = self._store.list_line_transcription_results(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=active_run.id,
                    page_id=result.page_id,
                )
                token_rows = self._store.list_token_transcription_results(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=active_run.id,
                    page_id=result.page_id,
                )
                line_count += len(line_rows)
                token_count += len(token_rows)
                anchor_refresh_required += sum(
                    1 for line in line_rows if line.token_anchor_status != "CURRENT"
                )
                low_confidence_lines += sum(
                    1
                    for line in line_rows
                    if isinstance(line.conf_line, float)
                    and line.conf_line < _TRANSCRIPTION_DEFAULT_REVIEW_CONFIDENCE_THRESHOLD
                )
        return DocumentTranscriptionOverviewSnapshot(
            document=document,
            projection=projection,
            active_run=active_run,
            latest_run=latest_run,
            total_runs=len(all_runs),
            page_count=page_count,
            active_status_counts=status_counts,
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
        status: TranscriptionRunStatus | None = None,
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
        if cursor < 0:
            raise DocumentValidationError("Cursor must be zero or greater.")
        if page_size < 1 or page_size > 500:
            raise DocumentValidationError("Page size must be between 1 and 500.")
        if confidence_below is not None:
            if confidence_below < 0 or confidence_below > 1:
                raise DocumentValidationError("confidenceBelow must be between 0 and 1.")
        if page_number is not None and page_number < 1:
            raise DocumentValidationError("page must be 1 or greater.")

        projection = self._store.get_transcription_projection(
            project_id=project_id,
            document_id=document_id,
        )
        target_run: TranscriptionRunRecord | None = None
        if isinstance(run_id, str) and run_id.strip():
            target_run = self._store.get_transcription_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id.strip(),
            )
            if target_run is None:
                raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        elif projection is not None and projection.active_transcription_run_id:
            target_run = self._store.get_transcription_run(
                project_id=project_id,
                document_id=document_id,
                run_id=projection.active_transcription_run_id,
            )
        if target_run is None:
            return projection, None, [], None

        page_results, next_cursor = self._store.list_page_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=target_run.id,
            status=status,
            cursor=cursor,
            page_size=page_size,
        )
        rows: list[DocumentTranscriptionTriagePageSnapshot] = []
        for page_result in page_results:
            if page_number is not None and page_result.page_index + 1 != page_number:
                continue
            line_rows = self._store.list_line_transcription_results(
                project_id=project_id,
                document_id=document_id,
                run_id=target_run.id,
                page_id=page_result.page_id,
            )
            token_rows = self._store.list_token_transcription_results(
                project_id=project_id,
                document_id=document_id,
                run_id=target_run.id,
                page_id=page_result.page_id,
            )
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
            threshold = (
                confidence_below
                if confidence_below is not None
                else _TRANSCRIPTION_DEFAULT_REVIEW_CONFIDENCE_THRESHOLD
            )
            low_confidence_lines = sum(
                1
                for line in line_rows
                if isinstance(line.conf_line, float) and line.conf_line < threshold
            )
            if (
                confidence_below is not None
                and low_confidence_lines == 0
                and (
                    min_confidence is None
                    or min_confidence >= confidence_below
                )
            ):
                continue
            rows.append(
                DocumentTranscriptionTriagePageSnapshot(
                    run_id=page_result.run_id,
                    page_id=page_result.page_id,
                    page_index=page_result.page_index,
                    status=page_result.status,
                    line_count=len(line_rows),
                    token_count=len(token_rows),
                    anchor_refresh_required=sum(
                        1 for line in line_rows if line.token_anchor_status != "CURRENT"
                    ),
                    low_confidence_lines=low_confidence_lines,
                    min_confidence=min_confidence,
                    avg_confidence=avg_confidence,
                    warnings_json=list(page_result.warnings_json),
                )
            )
        return projection, target_run, rows, next_cursor

    def read_layout_page_overlay(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> DocumentLayoutOverlayAsset:
        _, page, page_result = self._load_layout_page_result(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if page_result.overlay_json_key is None:
            raise DocumentPageAssetNotReadyError("Layout overlay is not ready.")
        self._assert_layout_manifest_mapping(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page=page,
            page_result=page_result,
        )
        try:
            payload_bytes = self._storage.read_object_bytes(page_result.overlay_json_key)
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError("Layout overlay could not be read.") from error

        try:
            raw_payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DocumentStoreUnavailableError("Layout overlay payload is invalid.") from error
        if not isinstance(raw_payload, Mapping):
            raise DocumentStoreUnavailableError("Layout overlay payload must be an object.")

        try:
            normalized_payload = validate_layout_overlay_payload(
                raw_payload,
                expected_run_id=run_id,
                expected_page_id=page_id,
                expected_page_index=page.page_index,
            )
        except LayoutContractValidationError as error:
            raise DocumentStoreUnavailableError("Layout overlay payload is invalid.") from error
        normalized_sha = self._sha256_hex(canonical_json_bytes(normalized_payload))
        if (
            page_result.overlay_json_sha256 is not None
            and page_result.overlay_json_sha256 != normalized_sha
        ):
            raise DocumentStoreUnavailableError("Layout overlay integrity verification failed.")
        reading_order_meta = normalized_payload.get("readingOrderMeta")
        if isinstance(reading_order_meta, Mapping):
            resolved_meta = dict(reading_order_meta)
        else:
            resolved_meta = {}
        active_layout_version = self._store.get_layout_active_version(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if active_layout_version is not None:
            resolved_meta["versionEtag"] = active_layout_version.version_etag
            resolved_meta["layoutVersionId"] = active_layout_version.id
        elif (
            page_result.page_xml_sha256 is not None
            and page_result.overlay_json_sha256 is not None
        ):
            bootstrap_version_id = self._bootstrap_layout_version_id(
                run_id=run_id,
                page_id=page_id,
                page_xml_sha256=page_result.page_xml_sha256,
                overlay_json_sha256=page_result.overlay_json_sha256,
            )
            resolved_meta["versionEtag"] = self._compute_layout_version_etag(
                run_id=run_id,
                page_id=page_id,
                version_id=bootstrap_version_id,
                page_xml_sha256=page_result.page_xml_sha256,
                overlay_json_sha256=page_result.overlay_json_sha256,
            )
            resolved_meta["layoutVersionId"] = bootstrap_version_id

        enriched_payload = dict(normalized_payload)
        enriched_payload["readingOrderMeta"] = resolved_meta
        enriched_sha = self._sha256_hex(canonical_json_bytes(enriched_payload))
        return DocumentLayoutOverlayAsset(
            payload=enriched_payload,
            etag_seed=enriched_sha,
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
        _, page, page_result = self._load_layout_page_result(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if page_result.page_xml_key is None:
            raise DocumentPageAssetNotReadyError("Layout PAGE-XML is not ready.")
        self._assert_layout_manifest_mapping(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page=page,
            page_result=page_result,
        )
        try:
            xml_bytes = self._storage.read_object_bytes(page_result.page_xml_key)
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError("Layout PAGE-XML could not be read.") from error

        try:
            canonical_page = parse_layout_pagexml(xml_bytes)
        except LayoutContractValidationError as error:
            raise DocumentStoreUnavailableError("Layout PAGE-XML payload is invalid.") from error
        if canonical_page.run_id != run_id:
            raise DocumentStoreUnavailableError("Layout PAGE-XML run mapping is invalid.")
        if canonical_page.page_id != page_id:
            raise DocumentStoreUnavailableError("Layout PAGE-XML page mapping is invalid.")
        if canonical_page.page_index != page.page_index:
            raise DocumentStoreUnavailableError(
                "Layout PAGE-XML page index mapping is invalid."
            )
        canonical_xml = serialize_layout_pagexml(canonical_page)
        canonical_sha = self._sha256_hex(canonical_xml)
        if (
            page_result.page_xml_sha256 is not None
            and page_result.page_xml_sha256 != canonical_sha
        ):
            raise DocumentStoreUnavailableError("Layout PAGE-XML integrity verification failed.")
        return DocumentLayoutPageXmlAsset(
            payload=canonical_xml,
            media_type="application/xml",
            etag_seed=canonical_sha,
        )

    @staticmethod
    def _coerce_overlay_points(
        value: object,
        *,
        field_name: str,
        minimum_points: int,
    ) -> list[dict[str, float]]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise DocumentValidationError(f"{field_name} must be an array of points.")
        points: list[dict[str, float]] = []
        for index, raw_point in enumerate(value):
            if not isinstance(raw_point, Mapping):
                raise DocumentValidationError(
                    f"{field_name}[{index}] must be an object with x/y."
                )
            raw_x = raw_point.get("x")
            raw_y = raw_point.get("y")
            if not isinstance(raw_x, (int, float)) or not isinstance(raw_y, (int, float)):
                raise DocumentValidationError(
                    f"{field_name}[{index}] must contain numeric x/y."
                )
            x = float(raw_x)
            y = float(raw_y)
            if not (x == x and y == y):
                raise DocumentValidationError(
                    f"{field_name}[{index}] must contain finite coordinates."
                )
            points.append({"x": x, "y": y})
        if len(points) < minimum_points:
            raise DocumentValidationError(
                f"{field_name} must contain at least {minimum_points} points."
            )
        return points

    def _apply_layout_element_operations(
        self,
        *,
        base_payload: Mapping[str, object],
        operations: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        if not operations:
            raise DocumentValidationError("At least one layout edit operation is required.")

        base_regions = base_payload.get("regions")
        base_lines = base_payload.get("lines")
        if not isinstance(base_regions, Sequence) or isinstance(base_regions, (str, bytes)):
            raise DocumentStoreUnavailableError("Layout canonical payload is invalid.")
        if not isinstance(base_lines, Sequence) or isinstance(base_lines, (str, bytes)):
            raise DocumentStoreUnavailableError("Layout canonical payload is invalid.")

        regions: list[dict[str, object]] = []
        for index, raw_region in enumerate(base_regions):
            if not isinstance(raw_region, Mapping):
                raise DocumentStoreUnavailableError("Layout canonical payload is invalid.")
            region_id = str(raw_region.get("id") or "").strip()
            if not region_id:
                raise DocumentStoreUnavailableError("Layout canonical payload is invalid.")
            region_type = str(raw_region.get("type") or "TEXT").strip() or "TEXT"
            polygon = self._coerce_overlay_points(
                raw_region.get("polygon"),
                field_name=f"regions[{index}].polygon",
                minimum_points=3,
            )
            raw_line_ids = raw_region.get("lineIds")
            line_ids = (
                [
                    str(line_id).strip()
                    for line_id in raw_line_ids
                    if isinstance(line_id, str) and line_id.strip()
                ]
                if isinstance(raw_line_ids, Sequence) and not isinstance(raw_line_ids, (str, bytes))
                else []
            )
            regions.append(
                {
                    "id": region_id,
                    "type": region_type,
                    "polygon": polygon,
                    "lineIds": line_ids,
                    "includeInReadingOrder": bool(
                        raw_region.get("includeInReadingOrder", True)
                    ),
                }
            )

        lines: list[dict[str, object]] = []
        for index, raw_line in enumerate(base_lines):
            if not isinstance(raw_line, Mapping):
                raise DocumentStoreUnavailableError("Layout canonical payload is invalid.")
            line_id = str(raw_line.get("id") or "").strip()
            parent_region_id = str(raw_line.get("parentRegionId") or "").strip()
            if not line_id or not parent_region_id:
                raise DocumentStoreUnavailableError("Layout canonical payload is invalid.")
            polygon = self._coerce_overlay_points(
                raw_line.get("polygon"),
                field_name=f"lines[{index}].polygon",
                minimum_points=3,
            )
            baseline: list[dict[str, float]] | None
            if raw_line.get("baseline") is None:
                baseline = None
            else:
                baseline = self._coerce_overlay_points(
                    raw_line.get("baseline"),
                    field_name=f"lines[{index}].baseline",
                    minimum_points=2,
                )
            lines.append(
                {
                    "id": line_id,
                    "parentRegionId": parent_region_id,
                    "polygon": polygon,
                    "baseline": baseline,
                }
            )

        reading_order: list[dict[str, str]] = []
        raw_reading_order = base_payload.get("readingOrder", [])
        if isinstance(raw_reading_order, Sequence) and not isinstance(raw_reading_order, (str, bytes)):
            for raw_edge in raw_reading_order:
                if not isinstance(raw_edge, Mapping):
                    continue
                from_id = str(raw_edge.get("fromId") or "").strip()
                to_id = str(raw_edge.get("toId") or "").strip()
                if from_id and to_id:
                    reading_order.append({"fromId": from_id, "toId": to_id})

        reading_order_groups: list[dict[str, object]] = []
        raw_groups = base_payload.get("readingOrderGroups", [])
        if isinstance(raw_groups, Sequence) and not isinstance(raw_groups, (str, bytes)):
            for index, raw_group in enumerate(raw_groups):
                if not isinstance(raw_group, Mapping):
                    continue
                group_id = str(raw_group.get("id") or f"g-{index + 1:04d}").strip()
                if not group_id:
                    group_id = f"g-{index + 1:04d}"
                raw_region_ids = raw_group.get("regionIds")
                if not isinstance(raw_region_ids, Sequence) or isinstance(
                    raw_region_ids, (str, bytes)
                ):
                    continue
                region_ids = [
                    str(region_id).strip()
                    for region_id in raw_region_ids
                    if isinstance(region_id, str) and region_id.strip()
                ]
                if not region_ids:
                    continue
                reading_order_groups.append(
                    {
                        "id": group_id,
                        "ordered": bool(raw_group.get("ordered", True)),
                        "regionIds": region_ids,
                    }
                )

        reading_order_meta = (
            dict(base_payload.get("readingOrderMeta"))
            if isinstance(base_payload.get("readingOrderMeta"), Mapping)
            else {"schemaVersion": 1}
        )

        def find_region(region_id: str) -> dict[str, object]:
            for region in regions:
                if region.get("id") == region_id:
                    return region
            raise DocumentValidationError(f"Unknown region id '{region_id}'.")

        def find_line(line_id: str) -> dict[str, object]:
            for line in lines:
                if line.get("id") == line_id:
                    return line
            raise DocumentValidationError(f"Unknown line id '{line_id}'.")

        def region_ids_set() -> set[str]:
            return {
                str(region["id"])
                for region in regions
                if isinstance(region.get("id"), str) and str(region["id"]).strip()
            }

        def line_ids_set() -> set[str]:
            return {
                str(line["id"])
                for line in lines
                if isinstance(line.get("id"), str) and str(line["id"]).strip()
            }

        def ensure_region_line_membership_consistent() -> None:
            by_region: dict[str, list[str]] = {}
            for line in lines:
                line_id = str(line["id"])
                parent = str(line["parentRegionId"])
                by_region.setdefault(parent, []).append(line_id)
            for region in regions:
                region_id = str(region["id"])
                current = [
                    str(line_id)
                    for line_id in region.get("lineIds", [])
                    if isinstance(line_id, str) and line_id in by_region.get(region_id, [])
                ]
                missing = [
                    line_id
                    for line_id in by_region.get(region_id, [])
                    if line_id not in current
                ]
                region["lineIds"] = current + missing

        ensure_region_line_membership_consistent()

        def next_region_id() -> str:
            existing = region_ids_set()
            index = 1
            while True:
                candidate = f"region-manual-{index:04d}"
                if candidate not in existing:
                    return candidate
                index += 1

        def next_line_id() -> str:
            existing = line_ids_set()
            index = 1
            while True:
                candidate = f"line-manual-{index:04d}"
                if candidate not in existing:
                    return candidate
                index += 1

        for operation_index, operation in enumerate(operations):
            kind = str(operation.get("kind") or "").strip().upper()
            if not kind:
                raise DocumentValidationError(
                    f"operations[{operation_index}].kind is required."
                )

            if kind == "ADD_REGION":
                region_id = (
                    str(operation.get("regionId")).strip()
                    if isinstance(operation.get("regionId"), str)
                    and str(operation.get("regionId")).strip()
                    else next_region_id()
                )
                if region_id in region_ids_set():
                    raise DocumentValidationError(
                        f"Region '{region_id}' already exists."
                    )
                polygon = self._coerce_overlay_points(
                    operation.get("polygon"),
                    field_name=f"operations[{operation_index}].polygon",
                    minimum_points=3,
                )
                regions.append(
                    {
                        "id": region_id,
                        "type": str(operation.get("regionType") or "TEXT").strip() or "TEXT",
                        "polygon": polygon,
                        "lineIds": [],
                        "includeInReadingOrder": bool(
                            operation.get("includeInReadingOrder", True)
                        ),
                    }
                )
                continue

            if kind == "ADD_LINE":
                parent_region_id = str(operation.get("parentRegionId") or "").strip()
                if not parent_region_id:
                    raise DocumentValidationError(
                        f"operations[{operation_index}].parentRegionId is required."
                    )
                _ = find_region(parent_region_id)
                line_id = (
                    str(operation.get("lineId")).strip()
                    if isinstance(operation.get("lineId"), str)
                    and str(operation.get("lineId")).strip()
                    else next_line_id()
                )
                if line_id in line_ids_set():
                    raise DocumentValidationError(f"Line '{line_id}' already exists.")
                polygon = self._coerce_overlay_points(
                    operation.get("polygon"),
                    field_name=f"operations[{operation_index}].polygon",
                    minimum_points=3,
                )
                baseline: list[dict[str, float]] | None
                if operation.get("baseline") is None:
                    baseline = None
                else:
                    baseline = self._coerce_overlay_points(
                        operation.get("baseline"),
                        field_name=f"operations[{operation_index}].baseline",
                        minimum_points=2,
                    )
                lines.append(
                    {
                        "id": line_id,
                        "parentRegionId": parent_region_id,
                        "polygon": polygon,
                        "baseline": baseline,
                    }
                )
                ensure_region_line_membership_consistent()
                insert_region = find_region(parent_region_id)
                line_ids = list(insert_region.get("lineIds", []))
                if line_id not in line_ids:
                    line_ids.append(line_id)
                before_line_id = (
                    str(operation.get("beforeLineId")).strip()
                    if isinstance(operation.get("beforeLineId"), str)
                    and str(operation.get("beforeLineId")).strip()
                    else None
                )
                after_line_id = (
                    str(operation.get("afterLineId")).strip()
                    if isinstance(operation.get("afterLineId"), str)
                    and str(operation.get("afterLineId")).strip()
                    else None
                )
                if before_line_id and before_line_id in line_ids:
                    line_ids.remove(line_id)
                    line_ids.insert(line_ids.index(before_line_id), line_id)
                elif after_line_id and after_line_id in line_ids:
                    line_ids.remove(line_id)
                    line_ids.insert(line_ids.index(after_line_id) + 1, line_id)
                insert_region["lineIds"] = line_ids
                continue

            if kind == "MOVE_REGION":
                region_id = str(operation.get("regionId") or "").strip()
                region = find_region(region_id)
                region["polygon"] = self._coerce_overlay_points(
                    operation.get("polygon"),
                    field_name=f"operations[{operation_index}].polygon",
                    minimum_points=3,
                )
                continue

            if kind == "MOVE_LINE":
                line_id = str(operation.get("lineId") or "").strip()
                line = find_line(line_id)
                line["polygon"] = self._coerce_overlay_points(
                    operation.get("polygon"),
                    field_name=f"operations[{operation_index}].polygon",
                    minimum_points=3,
                )
                continue

            if kind == "MOVE_BASELINE":
                line_id = str(operation.get("lineId") or "").strip()
                line = find_line(line_id)
                if operation.get("baseline") is None:
                    line["baseline"] = None
                else:
                    line["baseline"] = self._coerce_overlay_points(
                        operation.get("baseline"),
                        field_name=f"operations[{operation_index}].baseline",
                        minimum_points=2,
                    )
                continue

            if kind == "DELETE_LINE":
                line_id = str(operation.get("lineId") or "").strip()
                _ = find_line(line_id)
                lines = [
                    line for line in lines if str(line.get("id")) != line_id
                ]
                ensure_region_line_membership_consistent()
                continue

            if kind == "DELETE_REGION":
                region_id = str(operation.get("regionId") or "").strip()
                _ = find_region(region_id)
                removed_line_ids = {
                    str(line["id"])
                    for line in lines
                    if str(line.get("parentRegionId")) == region_id
                }
                lines = [
                    line
                    for line in lines
                    if str(line.get("parentRegionId")) != region_id
                ]
                regions = [
                    region
                    for region in regions
                    if str(region.get("id")) != region_id
                ]
                reading_order = [
                    edge
                    for edge in reading_order
                    if str(edge.get("fromId")) not in removed_line_ids
                    and str(edge.get("toId")) not in removed_line_ids
                    and str(edge.get("fromId")) != region_id
                    and str(edge.get("toId")) != region_id
                ]
                next_groups: list[dict[str, object]] = []
                for group in reading_order_groups:
                    group_region_ids = [
                        str(region_ref)
                        for region_ref in group.get("regionIds", [])
                        if isinstance(region_ref, str) and region_ref != region_id
                    ]
                    if not group_region_ids:
                        continue
                    next_groups.append(
                        {
                            "id": str(group.get("id") or ""),
                            "ordered": bool(group.get("ordered", True)),
                            "regionIds": group_region_ids,
                        }
                    )
                reading_order_groups = next_groups
                ensure_region_line_membership_consistent()
                continue

            if kind == "RETAG_REGION":
                region_id = str(operation.get("regionId") or "").strip()
                region = find_region(region_id)
                region_type = str(operation.get("regionType") or "").strip()
                if not region_type:
                    raise DocumentValidationError(
                        f"operations[{operation_index}].regionType is required."
                    )
                region["type"] = region_type
                continue

            if kind == "ASSIGN_LINE_REGION":
                line_id = str(operation.get("lineId") or "").strip()
                target_region_id = str(operation.get("parentRegionId") or "").strip()
                if not target_region_id:
                    raise DocumentValidationError(
                        f"operations[{operation_index}].parentRegionId is required."
                    )
                line = find_line(line_id)
                _ = find_region(target_region_id)
                line["parentRegionId"] = target_region_id
                ensure_region_line_membership_consistent()
                target_region = find_region(target_region_id)
                region_line_ids = list(target_region.get("lineIds", []))
                if line_id not in region_line_ids:
                    region_line_ids.append(line_id)
                before_line_id = (
                    str(operation.get("beforeLineId")).strip()
                    if isinstance(operation.get("beforeLineId"), str)
                    and str(operation.get("beforeLineId")).strip()
                    else None
                )
                after_line_id = (
                    str(operation.get("afterLineId")).strip()
                    if isinstance(operation.get("afterLineId"), str)
                    and str(operation.get("afterLineId")).strip()
                    else None
                )
                if before_line_id and before_line_id in region_line_ids:
                    region_line_ids.remove(line_id)
                    region_line_ids.insert(region_line_ids.index(before_line_id), line_id)
                elif after_line_id and after_line_id in region_line_ids:
                    region_line_ids.remove(line_id)
                    region_line_ids.insert(region_line_ids.index(after_line_id) + 1, line_id)
                target_region["lineIds"] = region_line_ids
                continue

            if kind == "REORDER_REGION_LINES":
                region_id = str(operation.get("regionId") or "").strip()
                region = find_region(region_id)
                raw_line_ids = operation.get("lineIds")
                if not isinstance(raw_line_ids, Sequence) or isinstance(
                    raw_line_ids, (str, bytes)
                ):
                    raise DocumentValidationError(
                        f"operations[{operation_index}].lineIds must be an array."
                    )
                next_line_ids = [
                    str(line_id).strip()
                    for line_id in raw_line_ids
                    if isinstance(line_id, str) and line_id.strip()
                ]
                current_line_ids = [
                    str(line["id"])
                    for line in lines
                    if str(line.get("parentRegionId")) == region_id
                ]
                if set(next_line_ids) != set(current_line_ids):
                    raise DocumentValidationError(
                        f"operations[{operation_index}].lineIds must match region lines."
                    )
                region["lineIds"] = next_line_ids
                continue

            if kind == "SET_REGION_READING_ORDER_INCLUDED":
                region_id = str(operation.get("regionId") or "").strip()
                region = find_region(region_id)
                include = operation.get("includeInReadingOrder")
                if not isinstance(include, bool):
                    raise DocumentValidationError(
                        "includeInReadingOrder must be boolean."
                    )
                region["includeInReadingOrder"] = include
                continue

            raise DocumentValidationError(
                f"Unsupported layout edit operation kind '{kind}'."
            )

        ensure_region_line_membership_consistent()
        valid_region_ids = region_ids_set()
        excluded_region_ids = {
            str(region["id"])
            for region in regions
            if not bool(region.get("includeInReadingOrder", True))
        }
        valid_line_ids = line_ids_set()
        excluded_line_ids = {
            str(line["id"])
            for line in lines
            if str(line.get("parentRegionId")) in excluded_region_ids
        }
        allowed_element_ids = (
            (valid_region_ids - excluded_region_ids)
            | (valid_line_ids - excluded_line_ids)
        )

        normalized_groups: list[dict[str, object]] = []
        seen_grouped_regions: set[str] = set()
        for group in reading_order_groups:
            group_id = str(group.get("id") or "").strip()
            if not group_id:
                continue
            region_ids = [
                str(region_id)
                for region_id in group.get("regionIds", [])
                if isinstance(region_id, str)
                and region_id in valid_region_ids
                and region_id not in excluded_region_ids
                and region_id not in seen_grouped_regions
            ]
            if not region_ids:
                continue
            seen_grouped_regions.update(region_ids)
            normalized_groups.append(
                {
                    "id": group_id,
                    "ordered": bool(group.get("ordered", True)),
                    "regionIds": region_ids,
                }
            )

        filtered_reading_order = [
            {"fromId": str(edge["fromId"]), "toId": str(edge["toId"])}
            for edge in reading_order
            if isinstance(edge.get("fromId"), str)
            and isinstance(edge.get("toId"), str)
            and str(edge["fromId"]) in allowed_element_ids
            and str(edge["toId"]) in allowed_element_ids
        ]

        reading_order_meta["schemaVersion"] = 1
        reading_order_meta["source"] = "MANUAL_OVERRIDE"
        reading_order_meta.pop("versionEtag", None)
        reading_order_meta.pop("layoutVersionId", None)
        if not normalized_groups:
            reading_order_meta["mode"] = "WITHHELD"
            reading_order_meta["orderWithheld"] = True
        elif all(bool(group.get("ordered", True)) for group in normalized_groups):
            reading_order_meta["mode"] = "ORDERED"
            reading_order_meta["orderWithheld"] = False
        else:
            reading_order_meta["mode"] = "UNORDERED"
            reading_order_meta["orderWithheld"] = False

        return {
            "schemaVersion": int(base_payload.get("schemaVersion", 1)),
            "runId": str(base_payload.get("runId") or ""),
            "pageId": str(base_payload.get("pageId") or ""),
            "pageIndex": int(base_payload.get("pageIndex") or 0),
            "page": dict(base_payload.get("page") or {}),
            "regions": regions,
            "lines": lines,
            "readingOrder": filtered_reading_order,
            "readingOrderGroups": normalized_groups,
            "readingOrderMeta": reading_order_meta,
        }

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
        run, page, page_result = self._load_layout_page_result(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if page_result.status != "SUCCEEDED":
            raise DocumentLayoutConflictError(
                "Layout edits require a SUCCEEDED page layout result."
            )
        if (
            page_result.page_xml_key is None
            or page_result.overlay_json_key is None
            or page_result.page_xml_sha256 is None
            or page_result.overlay_json_sha256 is None
        ):
            raise DocumentLayoutConflictError(
                "Layout edits require persisted PAGE-XML and overlay outputs."
            )
        normalized_version_etag = (
            version_etag.strip() if isinstance(version_etag, str) else ""
        )
        if not normalized_version_etag:
            raise DocumentValidationError("versionEtag is required.")
        if not operations:
            raise DocumentValidationError("At least one layout edit operation is required.")

        active_layout_version = self._store.get_layout_active_version(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page.id,
        )
        if active_layout_version is None:
            bootstrap_version_id = self._bootstrap_layout_version_id(
                run_id=run.id,
                page_id=page.id,
                page_xml_sha256=page_result.page_xml_sha256,
                overlay_json_sha256=page_result.overlay_json_sha256,
            )
            bootstrap_version_etag = self._compute_layout_version_etag(
                run_id=run.id,
                page_id=page.id,
                version_id=bootstrap_version_id,
                page_xml_sha256=page_result.page_xml_sha256,
                overlay_json_sha256=page_result.overlay_json_sha256,
            )
            if normalized_version_etag != bootstrap_version_etag:
                raise DocumentLayoutConflictError(
                    "Layout update conflicts with a newer saved layout version."
                )
            try:
                base_pagexml_bytes = self._storage.read_object_bytes(page_result.page_xml_key)
                base_canonical_page = parse_layout_pagexml(base_pagexml_bytes)
            except (DocumentStorageError, LayoutContractValidationError) as error:
                raise DocumentStoreUnavailableError(
                    "Layout PAGE-XML payload is invalid."
                ) from error
            bootstrap_payload = self._layout_canonical_payload(
                canonical_page=base_canonical_page
            )
            try:
                active_layout_version, page_result = self._store.bootstrap_layout_page_version(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run.id,
                    page_id=page.id,
                    version_id=bootstrap_version_id,
                    version_etag=bootstrap_version_etag,
                    page_xml_key=page_result.page_xml_key,
                    overlay_json_key=page_result.overlay_json_key,
                    page_xml_sha256=page_result.page_xml_sha256,
                    overlay_json_sha256=page_result.overlay_json_sha256,
                    version_kind="SEGMENTATION_EDIT",
                    canonical_payload_json=bootstrap_payload,
                    reading_order_groups_json=list(bootstrap_payload["readingOrderGroups"]),
                    reading_order_meta_json=dict(bootstrap_payload["readingOrderMeta"]),
                    created_by=current_user.user_id,
                )
            except DocumentLayoutRunConflictError as error:
                raise DocumentLayoutConflictError(
                    str(error),
                    activation_gate=getattr(error, "activation_gate", None),
                ) from error

        if active_layout_version is None:
            raise DocumentStoreUnavailableError("Layout active version bootstrap failed.")
        if active_layout_version.version_etag != normalized_version_etag:
            raise DocumentLayoutConflictError(
                "Layout update conflicts with a newer saved layout version."
            )

        canonical_payload_seed = (
            dict(active_layout_version.canonical_payload_json)
            if isinstance(active_layout_version.canonical_payload_json, dict)
            else {}
        )
        if not canonical_payload_seed:
            try:
                active_pagexml_bytes = self._storage.read_object_bytes(
                    active_layout_version.page_xml_key
                )
                active_canonical_page = parse_layout_pagexml(active_pagexml_bytes)
            except (DocumentStorageError, LayoutContractValidationError) as error:
                raise DocumentStoreUnavailableError(
                    "Layout PAGE-XML payload is invalid."
                ) from error
            canonical_payload_seed = self._layout_canonical_payload(
                canonical_page=active_canonical_page
            )

        updated_payload = self._apply_layout_element_operations(
            base_payload=canonical_payload_seed,
            operations=operations,
        )
        try:
            updated_canonical_page = build_layout_canonical_page(
                updated_payload,
                expected_run_id=run.id,
                expected_page_id=page.id,
                expected_page_index=page.page_index,
                expected_page_width=page.width,
                expected_page_height=page.height,
            )
            page_xml_bytes = serialize_layout_pagexml(updated_canonical_page)
            updated_overlay_payload = validate_layout_overlay_payload(
                derive_layout_overlay(updated_canonical_page),
                expected_run_id=run.id,
                expected_page_id=page.id,
                expected_page_index=page.page_index,
            )
            overlay_json_bytes = canonical_json_bytes(updated_overlay_payload)
        except LayoutContractValidationError as error:
            raise DocumentValidationError(str(error)) from error

        preprocess_result = self._store.get_preprocess_page_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_preprocess_run_id,
            page_id=page.id,
        )
        if (
            preprocess_result is None
            or preprocess_result.status != "SUCCEEDED"
            or not preprocess_result.output_object_key_gray
        ):
            raise DocumentLayoutConflictError(
                "Layout edits require a SUCCEEDED preprocess gray input for artifact regeneration."
            )

        new_layout_version_id = self._new_layout_version_id()
        try:
            source_image_payload = self._storage.read_object_bytes(
                preprocess_result.output_object_key_gray
            )
            artifact_rows = self._materialize_layout_line_artifacts(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page=page,
                canonical_page=updated_canonical_page,
                source_image_payload=source_image_payload,
                layout_version_id=new_layout_version_id,
            )
            page_xml_object = self._storage.write_layout_page_xml(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page_index=page.page_index,
                layout_version_id=new_layout_version_id,
                payload=page_xml_bytes,
            )
            overlay_object = self._storage.write_layout_page_overlay(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page_index=page.page_index,
                layout_version_id=new_layout_version_id,
                payload=overlay_json_bytes,
            )
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError(_CONTROLLED_STORAGE_FAILURE_MESSAGE) from error

        try:
            created_version, _ = self._store.append_layout_page_version(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page_id=page.id,
                version_id=new_layout_version_id,
                expected_version_etag=normalized_version_etag,
                page_xml_key=page_xml_object.object_key,
                overlay_json_key=overlay_object.object_key,
                page_xml_sha256=self._sha256_hex(page_xml_bytes),
                overlay_json_sha256=self._sha256_hex(overlay_json_bytes),
                version_kind="SEGMENTATION_EDIT",
                canonical_payload_json=updated_payload,
                reading_order_groups_json=list(updated_payload["readingOrderGroups"]),
                reading_order_meta_json=dict(updated_payload["readingOrderMeta"]),
                created_by=current_user.user_id,
            )
            self._store.replace_layout_line_artifacts(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page_id=page.id,
                layout_version_id=created_version.id,
                artifacts=artifact_rows,
            )
        except DocumentLayoutRunConflictError as error:
            raise DocumentLayoutConflictError(
                str(error),
                activation_gate=getattr(error, "activation_gate", None),
            ) from error

        downstream_projection = self._invalidate_layout_downstream_transcription_basis(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page.id,
            layout_version_id=created_version.id,
            run_snapshot_hash=created_version.run_snapshot_hash,
        )
        enriched_overlay = dict(updated_overlay_payload)
        resolved_meta = (
            dict(enriched_overlay.get("readingOrderMeta"))
            if isinstance(enriched_overlay.get("readingOrderMeta"), Mapping)
            else {}
        )
        resolved_meta["versionEtag"] = created_version.version_etag
        resolved_meta["layoutVersionId"] = created_version.id
        enriched_overlay["readingOrderMeta"] = resolved_meta
        return DocumentLayoutElementsSnapshot(
            run_id=run.id,
            page_id=page.id,
            page_index=page.page_index,
            layout_version_id=created_version.id,
            version_etag=created_version.version_etag,
            operations_applied=len(operations),
            overlay_payload=enriched_overlay,
            downstream_transcription_invalidated=downstream_projection is not None,
            downstream_transcription_state=(
                downstream_projection.downstream_transcription_state
                if downstream_projection is not None
                else None
            ),
            downstream_transcription_invalidated_reason=(
                downstream_projection.downstream_transcription_invalidated_reason
                if downstream_projection is not None
                else None
            ),
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
        run, page, page_result = self._load_layout_page_result(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if page_result.status != "SUCCEEDED":
            raise DocumentLayoutConflictError(
                "Reading-order updates require a SUCCEEDED page layout result."
            )
        if (
            page_result.page_xml_key is None
            or page_result.overlay_json_key is None
            or page_result.page_xml_sha256 is None
            or page_result.overlay_json_sha256 is None
        ):
            raise DocumentLayoutConflictError(
                "Reading-order updates require persisted PAGE-XML and overlay outputs."
            )
        normalized_version_etag = (
            version_etag.strip() if isinstance(version_etag, str) else ""
        )
        if not normalized_version_etag:
            raise DocumentValidationError("versionEtag is required.")

        active_layout_version = self._store.get_layout_active_version(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page.id,
        )
        if active_layout_version is None:
            bootstrap_version_id = self._bootstrap_layout_version_id(
                run_id=run.id,
                page_id=page.id,
                page_xml_sha256=page_result.page_xml_sha256,
                overlay_json_sha256=page_result.overlay_json_sha256,
            )
            bootstrap_version_etag = self._compute_layout_version_etag(
                run_id=run.id,
                page_id=page.id,
                version_id=bootstrap_version_id,
                page_xml_sha256=page_result.page_xml_sha256,
                overlay_json_sha256=page_result.overlay_json_sha256,
            )
            if normalized_version_etag != bootstrap_version_etag:
                raise DocumentLayoutConflictError(
                    "Reading-order update conflicts with a newer saved layout version."
                )
            try:
                base_pagexml_bytes = self._storage.read_object_bytes(page_result.page_xml_key)
                base_canonical_page = parse_layout_pagexml(base_pagexml_bytes)
            except (DocumentStorageError, LayoutContractValidationError) as error:
                raise DocumentStoreUnavailableError(
                    "Layout PAGE-XML payload is invalid."
                ) from error
            bootstrap_payload = self._layout_canonical_payload(
                canonical_page=base_canonical_page
            )
            try:
                active_layout_version, page_result = self._store.bootstrap_layout_page_version(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run.id,
                    page_id=page.id,
                    version_id=bootstrap_version_id,
                    version_etag=bootstrap_version_etag,
                    page_xml_key=page_result.page_xml_key,
                    overlay_json_key=page_result.overlay_json_key,
                    page_xml_sha256=page_result.page_xml_sha256,
                    overlay_json_sha256=page_result.overlay_json_sha256,
                    version_kind="READING_ORDER_EDIT",
                    canonical_payload_json=bootstrap_payload,
                    reading_order_groups_json=list(bootstrap_payload["readingOrderGroups"]),
                    reading_order_meta_json=dict(bootstrap_payload["readingOrderMeta"]),
                    created_by=current_user.user_id,
                )
            except DocumentLayoutRunConflictError as error:
                raise DocumentLayoutConflictError(
                    str(error),
                    activation_gate=getattr(error, "activation_gate", None),
                ) from error

        if active_layout_version is None:
            raise DocumentStoreUnavailableError("Layout active version bootstrap failed.")
        if active_layout_version.version_etag != normalized_version_etag:
            raise DocumentLayoutConflictError(
                "Reading-order update conflicts with a newer saved layout version."
            )

        canonical_payload_seed = (
            dict(active_layout_version.canonical_payload_json)
            if isinstance(active_layout_version.canonical_payload_json, dict)
            else {}
        )
        if not canonical_payload_seed:
            try:
                active_pagexml_bytes = self._storage.read_object_bytes(
                    active_layout_version.page_xml_key
                )
                active_canonical_page = parse_layout_pagexml(active_pagexml_bytes)
            except (DocumentStorageError, LayoutContractValidationError) as error:
                raise DocumentStoreUnavailableError(
                    "Layout PAGE-XML payload is invalid."
                ) from error
            canonical_payload_seed = self._layout_canonical_payload(
                canonical_page=active_canonical_page
            )

        try:
            canonical_page = build_layout_canonical_page(
                canonical_payload_seed,
                expected_run_id=run.id,
                expected_page_id=page.id,
                expected_page_index=page.page_index,
                expected_page_width=page.width,
                expected_page_height=page.height,
            )
        except LayoutContractValidationError as error:
            raise DocumentStoreUnavailableError("Layout canonical payload is invalid.") from error

        known_region_ids = {region.region_id for region in canonical_page.regions}
        try:
            normalized_groups = normalize_reading_order_groups(
                groups=groups,
                known_region_ids=known_region_ids,
            )
        except ValueError as error:
            raise DocumentValidationError(str(error)) from error

        requested_mode = mode.strip().upper() if isinstance(mode, str) else None
        if requested_mode not in {None, "ORDERED", "UNORDERED", "WITHHELD"}:
            raise DocumentValidationError(
                "mode must be ORDERED, UNORDERED, or WITHHELD when provided."
            )
        if requested_mode is None:
            if not normalized_groups:
                resolved_mode = "WITHHELD"
            elif all(group.ordered for group in normalized_groups):
                resolved_mode = "ORDERED"
            else:
                resolved_mode = "UNORDERED"
        else:
            resolved_mode = requested_mode

        if resolved_mode == "WITHHELD":
            normalized_groups = tuple()
        elif not normalized_groups:
            raise DocumentValidationError(
                "readingOrder groups are required unless mode is WITHHELD."
            )
        elif resolved_mode == "ORDERED" and any(
            not group.ordered for group in normalized_groups
        ):
            raise DocumentValidationError(
                "ORDERED mode requires each reading-order group to be ordered."
            )

        regions_payload = [
            {
                "id": region.region_id,
                "type": region.region_type,
                "polygon": self._points_payload(region.polygon),
                "lineIds": list(region.line_ids),
            }
            for region in canonical_page.regions
        ]
        lines_payload = [
            {
                "id": line.line_id,
                "parentRegionId": line.parent_region_id,
                "polygon": self._points_payload(line.polygon),
                "baseline": (
                    self._points_payload(line.baseline)
                    if line.baseline is not None
                    else None
                ),
            }
            for line in canonical_page.lines
        ]
        inferred_reading_order = infer_reading_order(
            regions=regions_payload,
            lines=lines_payload,
        )
        if resolved_mode == "WITHHELD":
            reading_order_edges: tuple[dict[str, str], ...] = tuple()
        else:
            reading_order_edges = build_reading_order_edges(
                groups=normalized_groups,
                lines=lines_payload,
            )
        reading_order_meta_payload = inferred_reading_order.to_meta_payload(
            source="MANUAL_OVERRIDE"
        )
        reading_order_meta_payload["mode"] = resolved_mode
        reading_order_meta_payload["orderWithheld"] = resolved_mode == "WITHHELD"

        updated_payload = self._layout_canonical_payload(canonical_page=canonical_page)
        updated_payload["readingOrder"] = list(reading_order_edges)
        updated_payload["readingOrderGroups"] = [
            {
                "id": group.group_id,
                "ordered": group.ordered,
                "regionIds": list(group.region_ids),
            }
            for group in normalized_groups
        ]
        updated_payload["readingOrderMeta"] = dict(reading_order_meta_payload)
        try:
            updated_canonical_page = build_layout_canonical_page(
                updated_payload,
                expected_run_id=run.id,
                expected_page_id=page.id,
                expected_page_index=page.page_index,
                expected_page_width=page.width,
                expected_page_height=page.height,
            )
            page_xml_bytes = serialize_layout_pagexml(updated_canonical_page)
            updated_overlay_payload = validate_layout_overlay_payload(
                derive_layout_overlay(updated_canonical_page),
                expected_run_id=run.id,
                expected_page_id=page.id,
                expected_page_index=page.page_index,
            )
            overlay_json_bytes = canonical_json_bytes(updated_overlay_payload)
        except LayoutContractValidationError as error:
            raise DocumentValidationError(str(error)) from error

        new_layout_version_id = self._new_layout_version_id()
        try:
            page_xml_object = self._storage.write_layout_page_xml(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page_index=page.page_index,
                layout_version_id=new_layout_version_id,
                payload=page_xml_bytes,
            )
            overlay_object = self._storage.write_layout_page_overlay(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page_index=page.page_index,
                layout_version_id=new_layout_version_id,
                payload=overlay_json_bytes,
            )
            self._refresh_layout_context_windows_for_page(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page=page,
                canonical_page=updated_canonical_page,
                source_layout_version_id=active_layout_version.id,
                layout_version_id=new_layout_version_id,
            )
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError(_CONTROLLED_STORAGE_FAILURE_MESSAGE) from error

        try:
            created_version, _ = self._store.append_layout_page_version(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page_id=page.id,
                version_id=new_layout_version_id,
                expected_version_etag=normalized_version_etag,
                page_xml_key=page_xml_object.object_key,
                overlay_json_key=overlay_object.object_key,
                page_xml_sha256=self._sha256_hex(page_xml_bytes),
                overlay_json_sha256=self._sha256_hex(overlay_json_bytes),
                version_kind="READING_ORDER_EDIT",
                canonical_payload_json=updated_payload,
                reading_order_groups_json=list(updated_payload["readingOrderGroups"]),
                reading_order_meta_json=dict(updated_payload["readingOrderMeta"]),
                created_by=current_user.user_id,
            )
        except DocumentLayoutRunConflictError as error:
            raise DocumentLayoutConflictError(
                str(error),
                activation_gate=getattr(error, "activation_gate", None),
            ) from error
        _ = self._invalidate_layout_downstream_transcription_basis(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page.id,
            layout_version_id=created_version.id,
            run_snapshot_hash=created_version.run_snapshot_hash,
        )

        response_groups: list[DocumentLayoutReadingOrderGroupSnapshot] = []
        for raw_group in created_version.reading_order_groups_json:
            group_id = str(raw_group.get("id") or "").strip()
            region_ids = raw_group.get("regionIds")
            if not group_id or not isinstance(region_ids, list):
                continue
            normalized_region_ids = tuple(
                str(region_id).strip()
                for region_id in region_ids
                if isinstance(region_id, str) and region_id.strip()
            )
            if not normalized_region_ids:
                continue
            response_groups.append(
                DocumentLayoutReadingOrderGroupSnapshot(
                    group_id=group_id,
                    ordered=bool(raw_group.get("ordered", True)),
                    region_ids=normalized_region_ids,
                )
            )
        reading_order_signals = dict(reading_order_meta_payload)
        reading_order_signals["versionEtag"] = created_version.version_etag
        reading_order_signals["layoutVersionId"] = created_version.id
        return DocumentLayoutReadingOrderSnapshot(
            run_id=run.id,
            page_id=page.id,
            page_index=page.page_index,
            layout_version_id=created_version.id,
            version_etag=created_version.version_etag,
            mode=resolved_mode,
            groups=tuple(response_groups),
            edges=tuple(reading_order_edges),
            signals_json=reading_order_signals,
        )

    @staticmethod
    def _build_layout_line_crop_path(
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
    ) -> str:
        return (
            f"/projects/{project_id}/documents/{document_id}/layout-runs/{run_id}/pages/"
            f"{page_id}/lines/{line_id}/crop"
        )

    @staticmethod
    def _build_layout_page_thumbnail_path(
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> str:
        return (
            f"/projects/{project_id}/documents/{document_id}/layout-runs/{run_id}/pages/"
            f"{page_id}/thumbnail"
        )

    @staticmethod
    def _build_layout_line_context_path(
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
    ) -> str:
        return (
            f"/projects/{project_id}/documents/{document_id}/layout-runs/{run_id}/pages/"
            f"{page_id}/lines/{line_id}/context"
        )

    def _load_layout_line_artifact_record(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
    ) -> tuple[LayoutRunRecord, DocumentPageRecord, LayoutLineArtifactRecord]:
        run, page, page_result = self._load_layout_page_result(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        artifact = self._store.get_layout_line_artifact(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page.id,
            line_id=line_id,
        )
        if artifact is None:
            if page_result.status != "SUCCEEDED":
                raise DocumentPageAssetNotReadyError(
                    "Layout line artifacts are not ready."
                )
            raise DocumentPageNotFoundError("Layout line artifact not found.")
        return run, page, artifact

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
        _, page, artifact = self._load_layout_line_artifact_record(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
        )
        context_window = self._read_layout_context_window_payload(
            object_key=artifact.context_window_json_key
        )
        return DocumentLayoutLineArtifactsSnapshot(
            run_id=artifact.run_id,
            page_id=artifact.page_id,
            page_index=page.page_index,
            line_id=artifact.line_id,
            region_id=artifact.region_id,
            artifacts_sha256=artifact.artifacts_sha256,
            line_crop_path=self._build_layout_line_crop_path(
                project_id=project_id,
                document_id=document_id,
                run_id=artifact.run_id,
                page_id=artifact.page_id,
                line_id=artifact.line_id,
            ),
            region_crop_path=(
                self._build_layout_line_crop_path(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=artifact.run_id,
                    page_id=artifact.page_id,
                    line_id=artifact.line_id,
                )
                + "?variant=region"
                if artifact.region_crop_key is not None
                else None
            ),
            page_thumbnail_path=self._build_layout_page_thumbnail_path(
                project_id=project_id,
                document_id=document_id,
                run_id=artifact.run_id,
                page_id=artifact.page_id,
            ),
            context_window_path=self._build_layout_line_context_path(
                project_id=project_id,
                document_id=document_id,
                run_id=artifact.run_id,
                page_id=artifact.page_id,
                line_id=artifact.line_id,
            ),
            context_window=context_window,
        )

    @staticmethod
    def _compute_layout_recall_blockers(
        *,
        page_result: PageLayoutResultRecord,
        recall_check: LayoutRecallCheckRecord | None,
        rescue_candidates: list[LayoutRescueCandidateRecord],
    ) -> tuple[list[str], int]:
        blocker_codes: list[str] = []
        unresolved_count = 0
        if page_result.status != "SUCCEEDED":
            blocker_codes.append("PAGE_NOT_SUCCEEDED")
            unresolved_count += 1
        if recall_check is None:
            blocker_codes.append("RECALL_CHECK_MISSING")
            unresolved_count += 1
        pending_count = sum(1 for candidate in rescue_candidates if candidate.status == "PENDING")
        if pending_count > 0:
            blocker_codes.append("RESCUE_PENDING")
            unresolved_count += pending_count
        accepted_count = sum(
            1 for candidate in rescue_candidates if candidate.status == "ACCEPTED"
        )
        if page_result.page_recall_status == "NEEDS_RESCUE" and accepted_count == 0:
            blocker_codes.append("ACCEPTED_RESCUE_MISSING")
            unresolved_count += 1
        return blocker_codes, unresolved_count

    def get_layout_page_recall_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> DocumentLayoutPageRecallStatusSnapshot:
        _, page, page_result = self._load_layout_page_result(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        recall_check = self._store.get_layout_recall_check(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        rescue_candidates = self._store.list_layout_rescue_candidates(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        blocker_codes, unresolved_count = self._compute_layout_recall_blockers(
            page_result=page_result,
            recall_check=recall_check,
            rescue_candidates=rescue_candidates,
        )
        rescue_candidate_counts = {
            "PENDING": sum(1 for row in rescue_candidates if row.status == "PENDING"),
            "ACCEPTED": sum(1 for row in rescue_candidates if row.status == "ACCEPTED"),
            "REJECTED": sum(1 for row in rescue_candidates if row.status == "REJECTED"),
            "RESOLVED": sum(1 for row in rescue_candidates if row.status == "RESOLVED"),
        }
        return DocumentLayoutPageRecallStatusSnapshot(
            run_id=page_result.run_id,
            page_id=page_result.page_id,
            page_index=page.page_index,
            page_recall_status=page_result.page_recall_status,
            recall_check_version=(
                recall_check.recall_check_version if recall_check is not None else None
            ),
            missed_text_risk_score=(
                recall_check.missed_text_risk_score if recall_check is not None else None
            ),
            signals_json=(
                dict(recall_check.signals_json) if recall_check is not None else {}
            ),
            rescue_candidate_counts=rescue_candidate_counts,
            blocker_reason_codes=blocker_codes,
            unresolved_count=unresolved_count,
        )

    def list_layout_page_rescue_candidates(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[LayoutRescueCandidateRecord]:
        _ = self._load_layout_page_result(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        return self._store.list_layout_rescue_candidates(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )

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
        _, _, artifact = self._load_layout_line_artifact_record(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
        )
        normalized_variant = variant.strip().lower()
        if normalized_variant not in {"line", "region"}:
            raise DocumentValidationError("variant must be 'line' or 'region'.")
        if normalized_variant == "line":
            object_key = artifact.line_crop_key
        else:
            object_key = artifact.region_crop_key
            if object_key is None:
                raise DocumentPageAssetNotReadyError("Layout region crop is not ready.")
        try:
            payload = self._storage.read_object_bytes(object_key)
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError("Layout crop payload could not be read.") from error
        return DocumentPageImageAsset(
            payload=payload,
            media_type="image/png",
            etag_seed=self._sha256_hex(payload),
            cache_control=_PAGE_ASSET_CACHE_CONTROL,
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
        _, page, page_result = self._load_layout_page_result(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        artifacts = self._store.list_layout_line_artifacts(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            layout_version_id=page_result.active_layout_version_id,
        )
        if artifacts:
            object_key = artifacts[0].page_thumbnail_key
        else:
            object_key = self._storage.build_layout_page_thumbnail_key(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_index=page.page_index,
                layout_version_id=page_result.active_layout_version_id,
            )
        try:
            payload = self._storage.read_object_bytes(object_key)
        except DocumentStorageError as error:
            raise DocumentPageAssetNotReadyError("Layout page thumbnail is not ready.") from error
        return DocumentPageImageAsset(
            payload=payload,
            media_type="image/png",
            etag_seed=self._sha256_hex(payload),
            cache_control=_PAGE_ASSET_CACHE_CONTROL,
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
        _, _, artifact = self._load_layout_line_artifact_record(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
        )
        context_payload = self._read_layout_context_window_payload(
            object_key=artifact.context_window_json_key
        )
        return DocumentLayoutContextWindowAsset(
            payload=context_payload,
            etag_seed=self._sha256_hex(canonical_json_bytes(context_payload)),
        )

    def materialize_layout_page_outputs(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        canonical_page_payload: Mapping[str, object],
        page_recall_status: PageRecallStatus = "COMPLETE",
        metrics_json: dict[str, object] | None = None,
        warnings_json: list[str] | None = None,
        recall_check_version: str | None = None,
        missed_text_risk_score: float | None = None,
        recall_signals_json: dict[str, object] | None = None,
        rescue_candidates: list[dict[str, object]] | None = None,
    ) -> PageLayoutResultRecord:
        run = self._store.get_layout_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentLayoutRunNotFoundError("Layout run not found.")
        page = self._store.get_document_page(
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        if page is None:
            raise DocumentPageNotFoundError("Page not found.")
        try:
            canonical_page = build_layout_canonical_page(
                canonical_page_payload,
                expected_run_id=run.id,
                expected_page_id=page.id,
                expected_page_index=page.page_index,
                expected_page_width=page.width,
                expected_page_height=page.height,
            )
            page_xml_bytes = serialize_layout_pagexml(canonical_page)
            overlay_payload = validate_layout_overlay_payload(
                derive_layout_overlay(canonical_page),
                expected_run_id=run.id,
                expected_page_id=page.id,
                expected_page_index=page.page_index,
            )
            overlay_json_bytes = canonical_json_bytes(overlay_payload)
        except LayoutContractValidationError as error:
            raise DocumentValidationError(str(error)) from error
        page_xml_sha256 = self._sha256_hex(page_xml_bytes)
        overlay_json_sha256 = self._sha256_hex(overlay_json_bytes)
        bootstrap_version_id = self._bootstrap_layout_version_id(
            run_id=run.id,
            page_id=page.id,
            page_xml_sha256=page_xml_sha256,
            overlay_json_sha256=overlay_json_sha256,
        )

        preprocess_result = self._store.get_preprocess_page_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_preprocess_run_id,
            page_id=page.id,
        )
        if (
            preprocess_result is None
            or preprocess_result.status != "SUCCEEDED"
            or not preprocess_result.output_object_key_gray
        ):
            raise DocumentLayoutConflictError(
                "Layout outputs require a SUCCEEDED preprocess gray input for artifact generation."
            )

        try:
            source_image_payload = self._storage.read_object_bytes(
                preprocess_result.output_object_key_gray
            )
            artifact_rows = self._materialize_layout_line_artifacts(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page=page,
                canonical_page=canonical_page,
                source_image_payload=source_image_payload,
                layout_version_id=bootstrap_version_id,
            )
            page_xml_object = self._storage.write_layout_page_xml(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page_index=page.page_index,
                payload=page_xml_bytes,
            )
            overlay_object = self._storage.write_layout_page_overlay(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page_index=page.page_index,
                payload=overlay_json_bytes,
            )
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError(_CONTROLLED_STORAGE_FAILURE_MESSAGE) from error

        self._store.replace_layout_line_artifacts(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page.id,
            layout_version_id=bootstrap_version_id,
            artifacts=artifact_rows,
        )
        normalized_metrics_json = dict(metrics_json or {})
        normalized_warnings_json = list(warnings_json or [])
        normalized_recall_check_version = (
            recall_check_version
            if isinstance(recall_check_version, str) and recall_check_version.strip()
            else str(normalized_metrics_json.get("recall_check_version") or "layout-recall-v1")
        )
        normalized_missed_text_risk_score = missed_text_risk_score
        if normalized_missed_text_risk_score is None:
            raw_metric_risk = normalized_metrics_json.get("missed_text_risk_score")
            if isinstance(raw_metric_risk, (int, float)):
                normalized_missed_text_risk_score = float(raw_metric_risk)
        if normalized_missed_text_risk_score is not None and (
            normalized_missed_text_risk_score < 0
            or normalized_missed_text_risk_score > 1
        ):
            raise DocumentValidationError(
                "missedTextRiskScore must be between 0 and 1."
            )
        normalized_signals_json = (
            dict(recall_signals_json) if isinstance(recall_signals_json, dict) else {}
        )
        if not normalized_signals_json:
            raw_signals = normalized_metrics_json.get("recall_signals_json")
            if isinstance(raw_signals, dict):
                normalized_signals_json = dict(raw_signals)
        if normalized_signals_json and (
            "algorithm_version" not in normalized_signals_json
        ):
            normalized_signals_json["algorithm_version"] = normalized_recall_check_version
        normalized_rescue_candidates = list(rescue_candidates or [])
        self._store.upsert_layout_recall_check(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page.id,
            recall_check_version=normalized_recall_check_version,
            missed_text_risk_score=normalized_missed_text_risk_score,
            signals_json=normalized_signals_json,
        )
        self._store.replace_layout_rescue_candidates(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page.id,
            candidates=normalized_rescue_candidates,
        )

        page_result = self._store.complete_layout_page_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page.id,
            page_xml_key=page_xml_object.object_key,
            overlay_json_key=overlay_object.object_key,
            page_xml_sha256=page_xml_sha256,
            overlay_json_sha256=overlay_json_sha256,
            metrics_json=normalized_metrics_json,
            warnings_json=normalized_warnings_json,
            page_recall_status=page_recall_status,
        )
        bootstrap_page_xml_sha = (
            page_result.page_xml_sha256
            if page_result.page_xml_sha256 is not None
            else page_xml_sha256
        )
        bootstrap_overlay_sha = (
            page_result.overlay_json_sha256
            if page_result.overlay_json_sha256 is not None
            else overlay_json_sha256
        )
        bootstrap_version_etag = self._compute_layout_version_etag(
            run_id=run.id,
            page_id=page.id,
            version_id=bootstrap_version_id,
            page_xml_sha256=bootstrap_page_xml_sha,
            overlay_json_sha256=bootstrap_overlay_sha,
        )
        bootstrap_payload = self._layout_canonical_payload(
            canonical_page=canonical_page
        )
        try:
            _, page_result = self._store.bootstrap_layout_page_version(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page_id=page.id,
                version_id=bootstrap_version_id,
                version_etag=bootstrap_version_etag,
                page_xml_key=page_result.page_xml_key
                if page_result.page_xml_key is not None
                else page_xml_object.object_key,
                overlay_json_key=page_result.overlay_json_key
                if page_result.overlay_json_key is not None
                else overlay_object.object_key,
                page_xml_sha256=bootstrap_page_xml_sha,
                overlay_json_sha256=bootstrap_overlay_sha,
                version_kind="SEGMENTATION_EDIT",
                canonical_payload_json=bootstrap_payload,
                reading_order_groups_json=list(bootstrap_payload["readingOrderGroups"]),
                reading_order_meta_json=dict(bootstrap_payload["readingOrderMeta"]),
                created_by=run.created_by,
            )
        except DocumentLayoutRunConflictError as error:
            raise DocumentLayoutConflictError(
                str(error),
                activation_gate=getattr(error, "activation_gate", None),
            ) from error
        manifest_payload = self._build_layout_manifest_payload(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_results=self._list_all_layout_page_results(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
            ),
        )
        try:
            self._storage.write_layout_manifest(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                payload=manifest_payload,
            )
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError(_CONTROLLED_STORAGE_FAILURE_MESSAGE) from error
        return page_result

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
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        projection = self._store.get_layout_projection(
            project_id=project_id,
            document_id=document_id,
        )
        active_run = self._store.get_active_layout_run(
            project_id=project_id,
            document_id=document_id,
        )
        all_runs: list[LayoutRunRecord] = []
        list_cursor = 0
        while True:
            batch, next_cursor = self._store.list_layout_runs(
                project_id=project_id,
                document_id=document_id,
                cursor=list_cursor,
                page_size=200,
            )
            all_runs.extend(batch)
            if next_cursor is None:
                break
            list_cursor = next_cursor
        latest_run = all_runs[0] if all_runs else None

        page_count = len(
            self._store.list_document_pages(
                project_id=project_id,
                document_id=document_id,
            )
        )
        status_counts: dict[PageLayoutResultStatus, int] = {
            "QUEUED": 0,
            "RUNNING": 0,
            "SUCCEEDED": 0,
            "FAILED": 0,
            "CANCELED": 0,
        }
        recall_counts: dict[PageRecallStatus, int] = {
            "COMPLETE": 0,
            "NEEDS_RESCUE": 0,
            "NEEDS_MANUAL_REVIEW": 0,
        }
        pages_with_issues = 0
        regions_detected_total = 0
        lines_detected_total = 0
        region_metric_count = 0
        line_metric_count = 0
        coverage_samples: list[float] = []
        structure_confidence_samples: list[float] = []
        if active_run is not None:
            active_results = self._list_all_layout_page_results(
                project_id=project_id,
                document_id=document_id,
                run_id=active_run.id,
            )
            for result in active_results:
                status_counts[result.status] += 1
                recall_counts[result.page_recall_status] += 1
                if (
                    result.status != "SUCCEEDED"
                    or result.page_recall_status != "COMPLETE"
                    or bool(result.failure_reason)
                    or len(result.warnings_json) > 0
                ):
                    pages_with_issues += 1

                region_count_metric = self._extract_layout_metric(
                    metrics_json=result.metrics_json,
                    keys=("num_regions", "region_count", "regions_detected"),
                )
                if region_count_metric is not None:
                    regions_detected_total += max(0, int(round(region_count_metric)))
                    region_metric_count += 1

                line_count_metric = self._extract_layout_metric(
                    metrics_json=result.metrics_json,
                    keys=("num_lines", "line_count", "lines_detected"),
                )
                if line_count_metric is not None:
                    lines_detected_total += max(0, int(round(line_count_metric)))
                    line_metric_count += 1

                coverage_metric = self._extract_layout_metric(
                    metrics_json=result.metrics_json,
                    keys=(
                        "region_coverage_percent",
                        "line_coverage_percent",
                        "coverage_percent",
                        "coverage",
                    ),
                )
                if coverage_metric is not None:
                    coverage_samples.append(
                        max(0.0, min(100.0, float(coverage_metric)))
                    )

                structure_confidence_metric = self._extract_layout_metric(
                    metrics_json=result.metrics_json,
                    keys=(
                        "structure_confidence",
                        "reading_order_confidence",
                    ),
                )
                if structure_confidence_metric is not None:
                    structure_confidence_samples.append(
                        max(0.0, min(1.0, float(structure_confidence_metric)))
                    )

        active_run_with_gate = (
            self._attach_layout_activation_gate(
                project_id=project_id,
                document_id=document_id,
                run=active_run,
            )
            if active_run is not None
            else None
        )
        latest_run_with_gate: LayoutRunRecord | None = None
        if latest_run is not None:
            if active_run_with_gate is not None and latest_run.id == active_run_with_gate.id:
                latest_run_with_gate = active_run_with_gate
            else:
                latest_run_with_gate = self._attach_layout_activation_gate(
                    project_id=project_id,
                    document_id=document_id,
                    run=latest_run,
                )

        return DocumentLayoutOverviewSnapshot(
            document=document,
            projection=projection,
            active_run=active_run_with_gate,
            latest_run=latest_run_with_gate,
            total_runs=len(all_runs),
            page_count=page_count,
            active_status_counts=status_counts,
            active_recall_counts=recall_counts,
            summary=DocumentLayoutSummarySnapshot(
                regions_detected=(
                    regions_detected_total if region_metric_count > 0 else None
                ),
                lines_detected=(
                    lines_detected_total if line_metric_count > 0 else None
                ),
                pages_with_issues=pages_with_issues,
                coverage_percent=(
                    round(sum(coverage_samples) / len(coverage_samples), 2)
                    if coverage_samples
                    else None
                ),
                structure_confidence=(
                    round(
                        sum(structure_confidence_samples)
                        / len(structure_confidence_samples),
                        4,
                    )
                    if structure_confidence_samples
                    else None
                ),
            ),
        )

    def list_document_pages(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> list[DocumentPageRecord]:
        self._project_service.require_member_workspace(
            current_user=current_user,
            project_id=project_id,
        )
        return self._store.list_document_pages(
            project_id=project_id,
            document_id=document_id,
        )

    def get_document_page(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        page_id: str,
    ) -> DocumentPageRecord:
        self._project_service.require_member_workspace(
            current_user=current_user,
            project_id=project_id,
        )
        page = self._store.get_document_page(
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        if page is None:
            raise DocumentPageNotFoundError("Page not found.")
        return page

    def update_document_page_rotation(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        page_id: str,
        viewer_rotation: int,
    ) -> DocumentPageRecord:
        self._project_service.require_member_workspace(
            current_user=current_user,
            project_id=project_id,
        )
        normalized = int(viewer_rotation)
        if normalized < -360 or normalized > 360:
            raise DocumentValidationError("viewerRotation must be between -360 and 360.")
        return self._store.update_page_rotation(
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
            viewer_rotation=normalized,
        )

    def _resolve_preprocess_variant_run(
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
        requested_run_id = run_id.strip() if isinstance(run_id, str) and run_id.strip() else None
        if requested_run_id is not None:
            resolved_run = self._store.get_preprocess_run(
                project_id=project_id,
                document_id=document_id,
                run_id=requested_run_id,
            )
            if resolved_run is None:
                raise DocumentPreprocessRunNotFoundError("Preprocessing run not found.")
            return requested_run_id, resolved_run

        projection = self._store.get_preprocess_projection(
            project_id=project_id,
            document_id=document_id,
        )
        if projection is None or not projection.active_preprocess_run_id:
            raise DocumentPreprocessConflictError(
                "No active preprocess run exists for this document."
            )

        resolved_run = self._store.get_preprocess_run(
            project_id=project_id,
            document_id=document_id,
            run_id=projection.active_preprocess_run_id,
        )
        if resolved_run is None:
            raise DocumentPreprocessConflictError(
                "Active preprocess projection references a missing run."
            )
        return None, resolved_run

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
        requested_run_id, resolved_run = self._resolve_preprocess_variant_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page_result = self._store.get_preprocess_page_result(
            project_id=project_id,
            document_id=document_id,
            run_id=resolved_run.id,
            page_id=page_id,
        )
        metrics_json = page_result.metrics_json if page_result is not None else {}
        warnings_json = (
            list(page_result.warnings_json) if page_result is not None else []
        )
        result_status = page_result.status if page_result is not None else None
        quality_gate_status = (
            page_result.quality_gate_status if page_result is not None else None
        )
        preprocessed_gray_available = bool(
            page_result is not None
            and page_result.status == "SUCCEEDED"
            and page_result.output_object_key_gray
        )
        preprocessed_bin_available = bool(
            page_result is not None
            and page_result.status == "SUCCEEDED"
            and page_result.output_object_key_bin
        )

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
                available=preprocessed_gray_available,
                media_type="image/png",
                run_id=resolved_run.id,
                result_status=result_status,
                quality_gate_status=quality_gate_status,
                warnings_json=warnings_json,
                metrics_json=metrics_json,
            ),
            DocumentPageVariantAvailability(
                variant="PREPROCESSED_BIN",
                image_variant="preprocessed_bin",
                available=preprocessed_bin_available,
                media_type="image/png",
                run_id=resolved_run.id,
                result_status=result_status,
                quality_gate_status=quality_gate_status,
                warnings_json=warnings_json,
                metrics_json=metrics_json,
            ),
        ]
        return DocumentPageVariantsSnapshot(
            document=document,
            page=page,
            requested_run_id=requested_run_id,
            resolved_run=resolved_run,
            variants=variants,
        )

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
        normalized_variant = variant.strip().lower()
        if normalized_variant not in {
            "full",
            "thumb",
            "preprocessed_gray",
            "preprocessed_bin",
        }:
            raise DocumentValidationError(
                "variant must be 'full', 'thumb', 'preprocessed_gray', or 'preprocessed_bin'."
            )
        if normalized_variant == "full":
            if not page.derived_image_key:
                raise DocumentPageAssetNotReadyError("Page image is not ready.")
            return DocumentPageImageAsset(
                payload=self._storage.read_object_bytes(page.derived_image_key),
                media_type="image/png",
                etag_seed=page.derived_image_sha256,
                cache_control=_PAGE_ASSET_CACHE_CONTROL,
            )
        if normalized_variant == "thumb":
            if not page.thumbnail_key:
                raise DocumentPageAssetNotReadyError("Page thumbnail is not ready.")
            return DocumentPageImageAsset(
                payload=self._storage.read_object_bytes(page.thumbnail_key),
                media_type="image/jpeg",
                etag_seed=page.thumbnail_sha256,
                cache_control=_PAGE_ASSET_CACHE_CONTROL,
            )

        _, resolved_run = self._resolve_preprocess_variant_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page_result = self._store.get_preprocess_page_result(
            project_id=project_id,
            document_id=document_id,
            run_id=resolved_run.id,
            page_id=page_id,
        )
        if page_result is None:
            raise DocumentPageAssetNotReadyError("Preprocessed page variant is not ready.")
        if normalized_variant == "preprocessed_gray":
            if not page_result.output_object_key_gray:
                raise DocumentPageAssetNotReadyError(
                    "Preprocessed grayscale image is not ready."
                )
            return DocumentPageImageAsset(
                payload=self._storage.read_object_bytes(page_result.output_object_key_gray),
                media_type="image/png",
                etag_seed=page_result.sha256_gray,
                cache_control=_PAGE_ASSET_CACHE_CONTROL,
            )
        if not page_result.output_object_key_bin:
            raise DocumentPageAssetNotReadyError(
                "Preprocessed binary image is not ready."
            )
        return DocumentPageImageAsset(
            payload=self._storage.read_object_bytes(page_result.output_object_key_bin),
            media_type="image/png",
            etag_seed=page_result.sha256_bin,
            cache_control=_PAGE_ASSET_CACHE_CONTROL,
        )

    def upload_document(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        original_filename: str,
        file_stream: BinaryIO,
    ) -> DocumentImportSnapshot:
        self._require_upload_access(current_user=current_user, project_id=project_id)
        normalized_filename = self._normalize_original_filename(original_filename)

        try:
            parse_allowed_extension(normalized_filename)
        except DocumentUploadValidationError as error:
            raise DocumentValidationError(str(error)) from error

        document_id = str(uuid4())
        import_id = str(uuid4())
        self._store.create_upload_records(
            project_id=project_id,
            document_id=document_id,
            import_id=import_id,
            original_filename=normalized_filename,
            created_by=current_user.user_id,
        )

        prepared_upload: PreparedUpload | None = None
        upload_snapshot: DocumentImportSnapshot | None = None
        try:
            prepared_upload = self._prepare_upload(file_stream=file_stream)
            type_result = validate_extension_matches_magic(
                filename=normalized_filename,
                prefix_bytes=prepared_upload.magic_prefix,
            )
            self._require_project_quota(
                project_id=project_id,
                byte_count=prepared_upload.byte_count,
            )
            stored = self._storage.write_original(
                project_id=project_id,
                document_id=document_id,
                source_path=prepared_upload.temp_path,
            )
            self._verify_stored_payload_integrity(
                file_path=stored.absolute_path,
                expected_sha256=prepared_upload.sha256,
                expected_bytes=prepared_upload.byte_count,
            )
            self._store.mark_upload_queued(
                project_id=project_id,
                import_id=import_id,
                stored_filename=stored.object_key,
                content_type_detected=type_result.detected_content_type,
                byte_count=prepared_upload.byte_count,
                sha256=prepared_upload.sha256,
            )
            upload_snapshot = self._load_snapshot(project_id=project_id, import_id=import_id)
            self._storage.write_source_metadata(
                project_id=project_id,
                document_id=document_id,
                metadata=self._build_source_metadata(upload_snapshot),
            )
            self._record_upload_processing_run(
                snapshot=upload_snapshot,
                status="SUCCEEDED",
            )
        except DocumentQuotaExceededError:
            self._mark_import_failed_best_effort(
                project_id=project_id,
                import_id=import_id,
                failure_reason="Project upload quota exceeded.",
            )
            self._record_upload_processing_run_failure_best_effort(
                project_id=project_id,
                import_id=import_id,
                failure_reason="Project upload quota exceeded.",
            )
            raise
        except DocumentValidationError as error:
            self._mark_import_failed_best_effort(
                project_id=project_id,
                import_id=import_id,
                failure_reason=str(error),
            )
            self._record_upload_processing_run_failure_best_effort(
                project_id=project_id,
                import_id=import_id,
                failure_reason=str(error),
            )
            raise
        except DocumentUploadValidationError as error:
            self._mark_import_failed_best_effort(
                project_id=project_id,
                import_id=import_id,
                failure_reason=str(error),
            )
            self._record_upload_processing_run_failure_best_effort(
                project_id=project_id,
                import_id=import_id,
                failure_reason=str(error),
            )
            raise DocumentValidationError(str(error)) from error
        except DocumentStorageError as error:
            self._mark_import_failed_best_effort(
                project_id=project_id,
                import_id=import_id,
                failure_reason=str(error),
            )
            self._record_upload_processing_run_failure_best_effort(
                project_id=project_id,
                import_id=import_id,
                failure_reason=str(error),
            )
            raise DocumentStoreUnavailableError(
                _CONTROLLED_STORAGE_FAILURE_MESSAGE
            ) from error
        finally:
            if prepared_upload is not None and prepared_upload.temp_path.exists():
                try:
                    prepared_upload.temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

        return upload_snapshot or self._load_snapshot(project_id=project_id, import_id=import_id)

    def get_document_import(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        import_id: str,
    ) -> DocumentImportSnapshot:
        self._project_service.require_member_workspace(
            current_user=current_user,
            project_id=project_id,
        )
        return self._load_snapshot(project_id=project_id, import_id=import_id)

    def cancel_document_import(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        import_id: str,
    ) -> DocumentImportSnapshot:
        self._project_service.require_member_workspace(
            current_user=current_user,
            project_id=project_id,
        )
        snapshot = self._load_snapshot(project_id=project_id, import_id=import_id)
        if snapshot.import_record.status not in {"UPLOADING", "QUEUED"}:
            raise DocumentImportConflictError(
                "Cancel is only allowed while status is UPLOADING or QUEUED."
            )

        canceled = self._store.cancel_import(
            project_id=project_id,
            import_id=import_id,
            canceled_by=current_user.user_id,
        )
        if not canceled:
            refreshed = self._load_snapshot(project_id=project_id, import_id=import_id)
            raise DocumentImportConflictError(
                f"Cancel was rejected because import is {refreshed.import_record.status}."
            )
        return self._load_snapshot(project_id=project_id, import_id=import_id)

    def begin_scan(
        self,
        *,
        project_id: str,
        import_id: str,
    ) -> DocumentImportSnapshot | None:
        moved = self._store.transition_import_to_scanning(
            project_id=project_id,
            import_id=import_id,
        )
        if not moved:
            snapshot = self._store.get_import_snapshot(project_id=project_id, import_id=import_id)
            if snapshot is None:
                return None
            _, import_record = snapshot
            if import_record.status in {
                "CANCELED",
                "FAILED",
                "REJECTED",
                "ACCEPTED",
            }:
                return None
            return None
        snapshot = self._load_snapshot(project_id=project_id, import_id=import_id)
        self._start_scan_processing_run(
            project_id=project_id,
            document_id=snapshot.document_record.id,
            created_by=snapshot.import_record.created_by,
        )
        return snapshot

    def complete_scan(
        self,
        *,
        project_id: str,
        import_id: str,
    ) -> DocumentImportSnapshot:
        snapshot = self._load_snapshot(project_id=project_id, import_id=import_id)
        if snapshot.import_record.status != "SCANNING":
            raise DocumentImportConflictError(
                "Scan completion requires SCANNING status."
            )
        document = snapshot.document_record
        if (
            not document.stored_filename
            or not document.content_type_detected
            or not document.sha256
        ):
            self._mark_import_failed_best_effort(
                project_id=project_id,
                import_id=import_id,
                failure_reason="Stored upload metadata was incomplete.",
            )
            raise DocumentValidationError("Stored upload metadata was incomplete.")

        file_path = self._storage.resolve_object_path(document.stored_filename)
        try:
            scan_result = self._scanner.scan_file(
                file_path=file_path,
                content_type=document.content_type_detected,
                sha256=document.sha256,
            )
        except DocumentScannerUnavailableError as error:
            self._mark_import_failed_best_effort(
                project_id=project_id,
                import_id=import_id,
                failure_reason="Malware scanner backend is unavailable.",
            )
            self._finish_latest_scan_processing_run(
                project_id=project_id,
                document_id=document.id,
                status="FAILED",
                failure_reason="Malware scanner backend is unavailable.",
            )
            raise
        except OSError as error:
            self._mark_import_failed_best_effort(
                project_id=project_id,
                import_id=import_id,
                failure_reason="Stored upload payload could not be scanned.",
            )
            self._finish_latest_scan_processing_run(
                project_id=project_id,
                document_id=document.id,
                status="FAILED",
                failure_reason="Stored upload payload could not be scanned.",
            )
            raise DocumentStoreUnavailableError(
                "Stored upload payload could not be scanned."
            ) from error

        if scan_result.verdict == "CLEAN":
            self._store.mark_scan_passed(project_id=project_id, import_id=import_id)
            self._finish_latest_scan_processing_run(
                project_id=project_id,
                document_id=document.id,
                status="SUCCEEDED",
            )
        else:
            self._store.mark_scan_rejected(
                project_id=project_id,
                import_id=import_id,
                failure_reason=scan_result.reason or "Scanner rejected the upload.",
            )
            self._finish_latest_scan_processing_run(
                project_id=project_id,
                document_id=document.id,
                status="FAILED",
                failure_reason=scan_result.reason or "Scanner rejected the upload.",
            )
        return self._load_snapshot(project_id=project_id, import_id=import_id)


@lru_cache
def get_document_service() -> DocumentService:
    settings = get_settings()
    return DocumentService(settings=settings)


__all__ = [
    "DocumentPreprocessAccessDeniedError",
    "DocumentPreprocessCompareSnapshot",
    "DocumentPreprocessConflictError",
    "DocumentPreprocessOverviewSnapshot",
    "DocumentPreprocessRunNotFoundError",
    "DocumentImportConflictError",
    "DocumentImportNotFoundError",
    "DocumentPageAssetNotReadyError",
    "DocumentPageNotFoundError",
    "DocumentProcessingRunNotFoundError",
    "DocumentNotFoundError",
    "DocumentQuotaExceededError",
    "DocumentRetryAccessDeniedError",
    "DocumentRetryConflictError",
    "DocumentScannerUnavailableError",
    "DocumentService",
    "DocumentStoreUnavailableError",
    "DocumentUploadAccessDeniedError",
    "DocumentUploadSessionSnapshot",
    "DocumentValidationError",
    "get_document_service",
]
