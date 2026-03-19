from __future__ import annotations

import hashlib
import json
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import BinaryIO, Literal, Mapping, Sequence
from uuid import uuid4

from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.documents.governance import (
    ExportCandidateSnapshotContractRecord,
    GovernanceReadinessProjectionRecord,
    GovernanceRunConflictError,
    GovernanceRunEventRecord,
    GovernanceRunEventType,
    GovernanceRunNotFoundError,
    GovernanceRunSummaryRecord,
    GovernanceStore,
    GovernanceStoreUnavailableError,
    LedgerVerificationRunRecord,
    RedactionEvidenceLedgerRecord,
    RedactionManifestRecord,
    get_governance_store,
)
from app.documents.models import (
    ApprovedModelRecord,
    ApprovedModelRole,
    ApprovedModelServingInterface,
    ApprovedModelStatus,
    ApprovedModelType,
    ProjectModelAssignmentRecord,
    TrainingDatasetRecord,
    DocumentRedactionProjectionRecord,
    DocumentTranscriptionProjectionRecord,
    RedactionAreaMaskRecord,
    RedactionDecisionActionType,
    RedactionDecisionEventRecord,
    RedactionDecisionStatus,
    RedactionFindingRecord,
    RedactionOutputRecord,
    RedactionOutputStatus,
    RedactionPageReviewEventRecord,
    RedactionPageReviewRecord,
    RedactionPageReviewStatus,
    RedactionSecondReviewStatus,
    RedactionRunKind,
    RedactionRunOutputRecord,
    RedactionRunOutputReadinessState,
    RedactionRunRecord,
    RedactionRunReviewEventRecord,
    RedactionRunReviewRecord,
    RedactionRunReviewStatus,
    RedactionRunStatus,
    LineTranscriptionResultRecord,
    PageTranscriptionResultRecord,
    TokenTranscriptionResultRecord,
    TranscriptionRescueResolutionRecord,
    TranscriptVersionRecord,
    TranscriptVariantKind,
    TranscriptVariantLayerRecord,
    TranscriptVariantSuggestionDecision,
    TranscriptVariantSuggestionEventRecord,
    TranscriptVariantSuggestionRecord,
    TranscriptionCompareDecision,
    TranscriptionCompareDecisionEventRecord,
    TranscriptionCompareDecisionRecord,
    TranscriptionConfidenceBasis,
    TranscriptionConfidenceBand,
    TranscriptionFallbackReasonCode,
    TranscriptionOutputProjectionRecord,
    TranscriptionRescueResolutionStatus,
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
from app.documents.redaction_detection import (
    BoundedAssistExplainer,
    LocalNERDetector,
    RedactionDetectionLine,
    RedactionDetectionToken,
    detect_direct_identifier_findings,
    resolve_direct_identifier_policy_config,
)
from app.documents.redaction_generalization import (
    detect_indirect_identifier_findings,
    extract_transformation_value,
)
from app.documents.redaction_preview import (
    PreviewFinding,
    PreviewLine,
    PreviewToken,
    SafeguardedPreviewArtifact,
    build_safeguarded_preview_artifact,
    canonical_preview_manifest_bytes,
)
from app.documents.evidence_ledger import (
    canonical_evidence_ledger_bytes,
    extract_ledger_rows,
    verify_canonical_evidence_ledger_payload,
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
    DocumentRedactionRunConflictError,
    DocumentTranscriptionRunConflictError,
    DocumentStore,
    DocumentStoreUnavailableError,
    DocumentUploadSessionConflictError,
    DocumentUploadSessionNotFoundError,
)
from app.policies.models import RedactionPolicyRecord
from app.policies.store import PolicyStore, PolicyStoreUnavailableError
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
_ALLOWED_REDACTION_VIEW_ROLES = {"PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"}
_ALLOWED_REDACTION_COMPARE_VIEW_ROLES = {"PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"}
_ALLOWED_REDACTION_REVIEWED_OUTPUT_VIEW_ROLES = {"PROJECT_LEAD", "REVIEWER"}
_ALLOWED_REDACTION_MUTATION_ROLES = {"PROJECT_LEAD", "REVIEWER", "ADMIN"}
_ALLOWED_REDACTION_POLICY_RERUN_ROLES = {"PROJECT_LEAD", "ADMIN"}
_ALLOWED_MODEL_CATALOG_READ_MEMBERSHIP_ROLES = {"PROJECT_LEAD", "REVIEWER"}
_ALLOWED_MODEL_CATALOG_MUTATION_MEMBERSHIP_ROLES = {"PROJECT_LEAD"}
_ALLOWED_MODEL_ASSIGNMENT_VIEW_ROLES = {"PROJECT_LEAD", "REVIEWER"}
_ALLOWED_MODEL_ASSIGNMENT_MUTATION_ROLES = {"PROJECT_LEAD"}
_ALLOWED_GOVERNANCE_VIEW_ROLES = {"PROJECT_LEAD", "REVIEWER"}
_ALLOWED_GOVERNANCE_LEDGER_VIEW_ROLES = {"ADMIN", "AUDITOR"}
_CONTROLLED_STORAGE_FAILURE_MESSAGE = "Controlled storage write failed."
_PAGE_ASSET_CACHE_CONTROL = "private, no-cache, max-age=0, must-revalidate"
_PAGE_ASSET_CACHE_TTL_SECONDS = 32
_PAGE_ASSET_CACHE_MAX_ENTRIES = 256
_PREPROCESS_DEFAULT_PIPELINE_VERSION = "preprocess-v1"
_PREPROCESS_DEFAULT_CONTAINER_DIGEST = "ukde/preprocess:v1"
_LAYOUT_DEFAULT_PIPELINE_VERSION = "layout-v1"
_LAYOUT_DEFAULT_CONTAINER_DIGEST = "ukde/layout:v1"
_TRANSCRIPTION_DEFAULT_PIPELINE_VERSION = "transcription-v1"
_TRANSCRIPTION_DEFAULT_CONTAINER_DIGEST = "ukde/transcription:v1"
_TRANSCRIPTION_DEFAULT_REVIEW_CONFIDENCE_THRESHOLD = 0.85
_TRANSCRIPTION_DEFAULT_FALLBACK_CONFIDENCE_THRESHOLD = 0.72
_REDACTION_PREVIEW_MEDIA_TYPE = "image/png"
_TRANSCRIPTION_TRIAGE_FAILED_STATUS_WEIGHT = 1_000.0
_TRANSCRIPTION_TRIAGE_LOW_CONFIDENCE_WEIGHT = 120.0
_TRANSCRIPTION_TRIAGE_MIN_CONFIDENCE_WEIGHT = 80.0
_TRANSCRIPTION_TRIAGE_VALIDATION_WARNING_WEIGHT = 60.0
_TRANSCRIPTION_TRIAGE_SEGMENTATION_MISMATCH_WEIGHT = 40.0
_TRANSCRIPTION_TRIAGE_ANCHOR_REFRESH_WEIGHT = 10.0
_TRANSCRIPTION_PRIMARY_PROMPT_TEMPLATE_ID = "ukde.transcription.v1.line-context"
_TRANSCRIPTION_PRIMARY_PROMPT_TEMPLATE_SOURCE = (
    "UKDE Phase 4 primary transcription line-context prompt v1; "
    "structured JSON output only; anchor-aware source metadata required."
)
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
_TRANSCRIPTION_FALLBACK_ENGINES: set[TranscriptionRunEngine] = {
    "KRAKEN_LINE",
    "TROCR_LINE",
    "DAN_PAGE",
}
_TRANSCRIPTION_GOVERNED_FALLBACK_ENGINES: set[TranscriptionRunEngine] = {"KRAKEN_LINE"}
_TRANSCRIPTION_FALLBACK_REASONS: set[TranscriptionFallbackReasonCode] = {
    "SCHEMA_VALIDATION_FAILED",
    "ANCHOR_RESOLUTION_FAILED",
    "CONFIDENCE_BELOW_THRESHOLD",
}
_REDACTION_MASKABLE_DECISION_STATUSES: set[RedactionDecisionStatus] = {
    "AUTO_APPLIED",
    "APPROVED",
    "OVERRIDDEN",
}
_TRANSCRIPTION_RESCUE_ELIGIBLE_CANDIDATE_STATUSES = {"ACCEPTED", "RESOLVED"}
_TRANSCRIPTION_RESCUE_MANUAL_OVERRIDE_STATUS = "MANUAL_REVIEW_RESOLVED"
_PAGE_XML_NAMESPACE = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
_PAGE_XML_NS = {"pc": _PAGE_XML_NAMESPACE}

TranscriptionRescueReadinessState = Literal[
    "READY",
    "BLOCKED_RESCUE",
    "BLOCKED_MANUAL_REVIEW",
    "BLOCKED_PAGE_STATUS",
]
TranscriptionRescueBlockerReasonCode = Literal[
    "PAGE_TRANSCRIPTION_NOT_SUCCEEDED",
    "RESCUE_SOURCE_MISSING",
    "RESCUE_SOURCE_UNTRANSCRIBED",
    "MANUAL_REVIEW_RESOLUTION_REQUIRED",
]
TranscriptionRunActivationBlockerCode = Literal[
    "RUN_NOT_SUCCEEDED",
    "RUN_LAYOUT_BASIS_STALE",
    "RUN_LAYOUT_SNAPSHOT_STALE",
    "RUN_LAYOUT_PROJECTION_MISSING",
    "TOKEN_ANCHOR_MISSING",
    "TOKEN_ANCHOR_INVALID",
    "TOKEN_ANCHOR_STALE",
    "PAGE_TRANSCRIPTION_NOT_SUCCEEDED",
    "RESCUE_SOURCE_MISSING",
    "RESCUE_SOURCE_UNTRANSCRIBED",
    "MANUAL_REVIEW_RESOLUTION_REQUIRED",
]


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

    def __init__(
        self,
        message: str,
        *,
        rescue_status: DocumentTranscriptionRunRescueStatusSnapshot | None = None,
        blocker_codes: tuple[TranscriptionRunActivationBlockerCode, ...] = (),
    ) -> None:
        super().__init__(message)
        self.rescue_status = rescue_status
        self.blocker_codes = blocker_codes


class DocumentRedactionAccessDeniedError(ProjectAccessDeniedError):
    """Current role cannot access privacy-review routes for this project."""


class DocumentRedactionRunNotFoundError(RuntimeError):
    """Redaction run was not found in project scope."""


class DocumentRedactionConflictError(RuntimeError):
    """Privacy-review mutation conflicts with run lineage or current state."""


class DocumentGovernanceAccessDeniedError(ProjectAccessDeniedError):
    """Current role cannot access governance routes for this project."""


class DocumentGovernanceRunNotFoundError(RuntimeError):
    """Governance run was not found in project scope."""


class DocumentGovernanceConflictError(RuntimeError):
    """Governance mutation conflicts with run lineage or current state."""


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
class DocumentRedactionPreviewAsset:
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
    confidence_bands: dict[TranscriptionConfidenceBand, int]
    issues: list[str]
    ranking_score: float
    ranking_rationale: str
    reviewer_assignment_user_id: str | None
    reviewer_assignment_updated_by: str | None
    reviewer_assignment_updated_at: datetime | None


@dataclass(frozen=True)
class DocumentTranscriptionLowConfidencePageSnapshot:
    page_id: str
    page_index: int
    low_confidence_lines: int


@dataclass(frozen=True)
class DocumentTranscriptionMetricsSnapshot:
    run_id: str | None
    review_confidence_threshold: float
    fallback_confidence_threshold: float
    page_count: int
    line_count: int
    token_count: int
    low_confidence_line_count: int
    percent_lines_below_threshold: float
    low_confidence_page_count: int
    low_confidence_page_distribution: list[DocumentTranscriptionLowConfidencePageSnapshot]
    segmentation_mismatch_warning_count: int
    structured_validation_failure_count: int
    fallback_invocation_count: int
    confidence_bands: dict[TranscriptionConfidenceBand, int]


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


@dataclass(frozen=True)
class DocumentRedactionRunPageSnapshot:
    run_id: str
    page_id: str
    page_index: int
    finding_count: int
    unresolved_count: int
    review_status: RedactionPageReviewStatus
    review_etag: str
    requires_second_review: bool
    second_review_status: RedactionSecondReviewStatus
    second_reviewed_by: str | None
    second_reviewed_at: datetime | None
    last_reviewed_by: str | None
    last_reviewed_at: datetime | None
    preview_status: RedactionOutputStatus | None
    top_findings: tuple[RedactionFindingRecord, ...]


@dataclass(frozen=True)
class DocumentRedactionPreviewStatusSnapshot:
    run_id: str
    page_id: str
    status: RedactionOutputStatus
    preview_sha256: str | None
    generated_at: datetime | None
    failure_reason: str | None
    run_output_status: RedactionOutputStatus | None
    run_output_manifest_sha256: str | None
    run_output_readiness_state: RedactionRunOutputReadinessState | None
    downstream_ready: bool


@dataclass(frozen=True)
class DocumentRedactionRunOutputSnapshot:
    run_output: RedactionRunOutputRecord
    review_status: RedactionRunReviewStatus
    readiness_state: RedactionRunOutputReadinessState
    downstream_ready: bool


@dataclass(frozen=True)
class DocumentRedactionRunTimelineEventSnapshot:
    source_table: str
    source_table_precedence: int
    event_id: str
    run_id: str
    page_id: str | None
    finding_id: str | None
    event_type: str
    actor_user_id: str | None
    reason: str | None
    created_at: datetime
    details_json: dict[str, object]


@dataclass(frozen=True)
class DocumentRedactionOverviewSnapshot:
    document: DocumentRecord
    projection: DocumentRedactionProjectionRecord | None
    active_run: RedactionRunRecord | None
    latest_run: RedactionRunRecord | None
    total_runs: int
    page_count: int
    findings_by_category: dict[str, int]
    unresolved_findings: int
    auto_applied_findings: int
    needs_review_findings: int
    overridden_findings: int
    pages_blocked_for_review: int
    preview_ready_pages: int
    preview_total_pages: int
    preview_failed_pages: int


@dataclass(frozen=True)
class DocumentRedactionComparePageSnapshot:
    page_id: str
    page_index: int
    base_finding_count: int
    candidate_finding_count: int
    changed_decision_count: int
    changed_action_count: int
    base_decision_counts: dict[RedactionDecisionStatus, int]
    candidate_decision_counts: dict[RedactionDecisionStatus, int]
    decision_status_deltas: dict[RedactionDecisionStatus, int]
    base_action_counts: dict[RedactionDecisionActionType, int]
    candidate_action_counts: dict[RedactionDecisionActionType, int]
    action_type_deltas: dict[RedactionDecisionActionType, int]
    action_compare_state: Literal["AVAILABLE", "NOT_YET_AVAILABLE"]
    changed_review_status: bool
    changed_second_review_status: bool
    base_review: RedactionPageReviewRecord | None
    candidate_review: RedactionPageReviewRecord | None
    base_preview_status: RedactionOutputStatus | None
    candidate_preview_status: RedactionOutputStatus | None
    preview_ready_delta: int


RedactionPolicyWarningCode = Literal[
    "BROAD_ALLOW_RULE",
    "INCONSISTENT_THRESHOLD",
]
RedactionPolicyWarningSeverity = Literal["WARNING"]


@dataclass(frozen=True)
class DocumentRedactionPolicyWarningSnapshot:
    code: RedactionPolicyWarningCode
    severity: RedactionPolicyWarningSeverity
    message: str
    affected_categories: tuple[str, ...]


@dataclass(frozen=True)
class DocumentRedactionCompareSnapshot:
    document: DocumentRecord
    base_run: RedactionRunRecord
    candidate_run: RedactionRunRecord
    pages: tuple[DocumentRedactionComparePageSnapshot, ...]
    changed_page_count: int
    changed_decision_count: int
    changed_action_count: int
    compare_action_state: Literal["AVAILABLE", "NOT_YET_RERUN", "NOT_YET_AVAILABLE"]
    candidate_policy_status: str | None
    comparison_only_candidate: bool
    pre_activation_warnings: tuple[DocumentRedactionPolicyWarningSnapshot, ...]


@dataclass(frozen=True)
class DocumentGovernanceOverviewSnapshot:
    document: DocumentRecord
    active_run_id: str | None
    total_runs: int
    approved_runs: int
    ready_runs: int
    pending_runs: int
    failed_runs: int
    latest_run_id: str | None
    latest_ready_run_id: str | None
    latest_run: GovernanceRunSummaryRecord | None
    latest_ready_run: GovernanceRunSummaryRecord | None


@dataclass(frozen=True)
class DocumentGovernanceRunsSnapshot:
    document: DocumentRecord
    active_run_id: str | None
    runs: tuple[GovernanceRunSummaryRecord, ...]


@dataclass(frozen=True)
class DocumentGovernanceRunOverviewSnapshot:
    document: DocumentRecord
    active_run_id: str | None
    run: GovernanceRunSummaryRecord
    readiness: GovernanceReadinessProjectionRecord
    manifest_attempts: tuple[RedactionManifestRecord, ...]
    ledger_attempts: tuple[RedactionEvidenceLedgerRecord, ...]


@dataclass(frozen=True)
class DocumentGovernanceEventSnapshot:
    id: str
    run_id: str
    event_type: GovernanceRunEventType
    actor_user_id: str | None
    from_status: str | None
    to_status: str | None
    reason: str | None
    created_at: datetime
    screening_safe: bool


@dataclass(frozen=True)
class DocumentGovernanceManifestSnapshot:
    overview: DocumentGovernanceRunOverviewSnapshot
    latest_attempt: RedactionManifestRecord | None
    manifest_payload: dict[str, object] | None
    stream_sha256: str | None
    hash_matches: bool
    internal_only: bool
    export_approved: bool
    not_export_approved: bool


@dataclass(frozen=True)
class DocumentGovernanceManifestStatusSnapshot:
    run_id: str
    status: Literal["UNAVAILABLE", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
    latest_attempt: RedactionManifestRecord | None
    attempt_count: int
    ready_manifest_id: str | None
    latest_manifest_sha256: str | None
    generation_status: Literal["IDLE", "RUNNING", "FAILED", "CANCELED"]
    readiness_status: Literal["PENDING", "READY", "FAILED"]
    updated_at: datetime


@dataclass(frozen=True)
class DocumentGovernanceManifestEntriesSnapshot:
    run_id: str
    status: Literal["UNAVAILABLE", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
    manifest_id: str | None
    manifest_sha256: str | None
    source_review_snapshot_sha256: str | None
    items: tuple[dict[str, object], ...]
    next_cursor: int | None
    total_count: int
    internal_only: bool
    export_approved: bool
    not_export_approved: bool


@dataclass(frozen=True)
class DocumentGovernanceManifestHashSnapshot:
    run_id: str
    status: Literal["UNAVAILABLE", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
    manifest_id: str | None
    manifest_sha256: str | None
    stream_sha256: str | None
    hash_matches: bool
    internal_only: bool
    export_approved: bool
    not_export_approved: bool


@dataclass(frozen=True)
class DocumentGovernanceLedgerSnapshot:
    overview: DocumentGovernanceRunOverviewSnapshot
    latest_attempt: RedactionEvidenceLedgerRecord | None
    ledger_payload: dict[str, object] | None
    stream_sha256: str | None
    hash_matches: bool
    internal_only: bool


@dataclass(frozen=True)
class DocumentGovernanceLedgerStatusSnapshot:
    run_id: str
    status: Literal["UNAVAILABLE", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
    latest_attempt: RedactionEvidenceLedgerRecord | None
    attempt_count: int
    ready_ledger_id: str | None
    latest_ledger_sha256: str | None
    generation_status: Literal["IDLE", "RUNNING", "FAILED", "CANCELED"]
    readiness_status: Literal["PENDING", "READY", "FAILED"]
    ledger_verification_status: Literal["PENDING", "VALID", "INVALID"]
    updated_at: datetime


@dataclass(frozen=True)
class DocumentGovernanceLedgerEntriesSnapshot:
    run_id: str
    status: Literal["UNAVAILABLE", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
    view: Literal["list", "timeline"]
    ledger_id: str | None
    ledger_sha256: str | None
    hash_chain_version: str | None
    total_count: int
    next_cursor: int | None
    verification_status: Literal["PENDING", "VALID", "INVALID"]
    items: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class DocumentGovernanceLedgerSummarySnapshot:
    run_id: str
    status: Literal["UNAVAILABLE", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
    ledger_id: str | None
    ledger_sha256: str | None
    hash_chain_version: str | None
    row_count: int
    hash_chain_head: str | None
    hash_chain_valid: bool
    verification_status: Literal["PENDING", "VALID", "INVALID"]
    category_counts: dict[str, int]
    action_counts: dict[str, int]
    override_count: int
    assist_reference_count: int
    internal_only: bool


@dataclass(frozen=True)
class DocumentGovernanceLedgerVerificationStatusSnapshot:
    run_id: str
    verification_status: Literal["PENDING", "VALID", "INVALID"]
    attempt_count: int
    latest_attempt: LedgerVerificationRunRecord | None
    latest_completed_attempt: LedgerVerificationRunRecord | None
    ready_ledger_id: str | None
    latest_ledger_sha256: str | None
    last_verified_at: datetime | None


@dataclass(frozen=True)
class DocumentGovernanceLedgerVerificationRunsSnapshot:
    run_id: str
    verification_status: Literal["PENDING", "VALID", "INVALID"]
    items: tuple[LedgerVerificationRunRecord, ...]


@dataclass(frozen=True)
class DocumentGovernanceLedgerVerificationDetailSnapshot:
    run_id: str
    verification_status: Literal["PENDING", "VALID", "INVALID"]
    attempt: LedgerVerificationRunRecord


@dataclass(frozen=True)
class DocumentExportCandidateSnapshotContractsSnapshot:
    project_id: str
    items: tuple[ExportCandidateSnapshotContractRecord, ...]


@dataclass(frozen=True)
class DocumentTranscriptionRescueSourceSnapshot:
    source_ref_id: str
    source_kind: TranscriptionTokenSourceKind
    candidate_kind: str
    candidate_status: str
    token_count: int
    has_transcription_output: bool
    confidence: float | None
    source_signal: str | None
    geometry_json: dict[str, object]


@dataclass(frozen=True)
class DocumentTranscriptionRescuePageStatusSnapshot:
    run_id: str
    page_id: str
    page_index: int
    page_recall_status: PageRecallStatus
    rescue_source_count: int
    rescue_transcribed_source_count: int
    rescue_unresolved_source_count: int
    readiness_state: TranscriptionRescueReadinessState
    blocker_reason_codes: tuple[TranscriptionRescueBlockerReasonCode, ...]
    resolution_status: TranscriptionRescueResolutionStatus | None
    resolution_reason: str | None
    resolution_updated_by: str | None
    resolution_updated_at: datetime | None


@dataclass(frozen=True)
class DocumentTranscriptionRunRescueStatusSnapshot:
    document: DocumentRecord
    run: TranscriptionRunRecord
    ready_for_activation: bool
    blocker_count: int
    run_blocker_reason_codes: tuple[TranscriptionRunActivationBlockerCode, ...]
    pages: tuple[DocumentTranscriptionRescuePageStatusSnapshot, ...]


@dataclass(frozen=True)
class DocumentTranscriptionPageRescueSourcesSnapshot:
    document: DocumentRecord
    run: TranscriptionRunRecord
    page: DocumentPageRecord
    page_recall_status: PageRecallStatus
    readiness_state: TranscriptionRescueReadinessState
    blocker_reason_codes: tuple[TranscriptionRescueBlockerReasonCode, ...]
    rescue_sources: tuple[DocumentTranscriptionRescueSourceSnapshot, ...]
    resolution_status: TranscriptionRescueResolutionStatus | None
    resolution_reason: str | None
    resolution_updated_by: str | None
    resolution_updated_at: datetime | None


@dataclass(frozen=True)
class DocumentTranscriptionCompareTokenDiffSnapshot:
    token_id: str
    token_index: int | None
    line_id: str | None
    base_token: TokenTranscriptionResultRecord | None
    candidate_token: TokenTranscriptionResultRecord | None
    changed: bool
    confidence_delta: float | None
    current_decision: TranscriptionCompareDecisionRecord | None


@dataclass(frozen=True)
class DocumentTranscriptionCompareLineDiffSnapshot:
    line_id: str
    base_line: LineTranscriptionResultRecord | None
    candidate_line: LineTranscriptionResultRecord | None
    changed: bool
    confidence_delta: float | None
    current_decision: TranscriptionCompareDecisionRecord | None


@dataclass(frozen=True)
class DocumentTranscriptionComparePageSnapshot:
    page_id: str
    page_index: int
    base_page: PageTranscriptionResultRecord | None
    candidate_page: PageTranscriptionResultRecord | None
    line_diffs: list[DocumentTranscriptionCompareLineDiffSnapshot]
    token_diffs: list[DocumentTranscriptionCompareTokenDiffSnapshot]
    changed_line_count: int
    changed_token_count: int
    changed_confidence_count: int
    output_availability: dict[str, bool]


@dataclass(frozen=True)
class DocumentTranscriptionCompareSnapshot:
    document: DocumentRecord
    base_run: TranscriptionRunRecord
    candidate_run: TranscriptionRunRecord
    pages: list[DocumentTranscriptionComparePageSnapshot]
    changed_line_count: int
    changed_token_count: int
    changed_confidence_count: int
    base_engine_metadata: dict[str, object]
    candidate_engine_metadata: dict[str, object]
    compare_decision_snapshot_hash: str
    compare_decision_count: int
    compare_decision_event_count: int


@dataclass(frozen=True)
class DocumentTranscriptVersionLineageSnapshot:
    version: TranscriptVersionRecord
    is_active: bool
    source_type: str


@dataclass(frozen=True)
class DocumentTranscriptionLineVersionHistorySnapshot:
    run: TranscriptionRunRecord
    page: DocumentPageRecord
    line: LineTranscriptionResultRecord
    versions: tuple[DocumentTranscriptVersionLineageSnapshot, ...]


@dataclass(frozen=True)
class DocumentTranscriptionCompareFinalizeSnapshot:
    document: DocumentRecord
    base_run: TranscriptionRunRecord
    candidate_run: TranscriptionRunRecord
    composed_run: TranscriptionRunRecord
    compare_decision_snapshot_hash: str
    page_scope: tuple[str, ...]


@dataclass(frozen=True)
class DocumentTranscriptionLineCorrectionSnapshot:
    run: TranscriptionRunRecord
    page: DocumentPageRecord
    line: LineTranscriptionResultRecord
    active_version: TranscriptVersionRecord
    projection: TranscriptionOutputProjectionRecord
    text_changed: bool
    downstream_projection: DocumentTranscriptionProjectionRecord | None


@dataclass(frozen=True)
class DocumentTranscriptionVariantLayerSnapshot:
    layer: TranscriptVariantLayerRecord
    suggestions: tuple[TranscriptVariantSuggestionRecord, ...]


@dataclass(frozen=True)
class DocumentTranscriptionVariantLayersSnapshot:
    run: TranscriptionRunRecord
    page: DocumentPageRecord
    variant_kind: TranscriptVariantKind
    layers: tuple[DocumentTranscriptionVariantLayerSnapshot, ...]


@dataclass(frozen=True)
class DocumentTranscriptionVariantSuggestionDecisionSnapshot:
    run: TranscriptionRunRecord
    page: DocumentPageRecord
    variant_kind: TranscriptVariantKind
    suggestion: TranscriptVariantSuggestionRecord
    event: TranscriptVariantSuggestionEventRecord


class DocumentService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: DocumentStore | None = None,
        governance_store: GovernanceStore | None = None,
        policy_store: PolicyStore | None = None,
        project_service: ProjectService | None = None,
        storage: DocumentStorage | None = None,
        scanner: DocumentScanner | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or DocumentStore(settings)
        self._governance_store = governance_store or get_governance_store()
        self._policy_store = policy_store or PolicyStore(settings)
        self._project_service = project_service or get_project_service()
        self._storage = storage or get_document_storage()
        self._scanner = scanner or get_document_scanner()
        self._asset_cache_lock = Lock()
        self._asset_cache_ttl_seconds = _PAGE_ASSET_CACHE_TTL_SECONDS
        self._asset_cache_max_entries = _PAGE_ASSET_CACHE_MAX_ENTRIES
        self._overlay_asset_cache: dict[str, tuple[float, DocumentLayoutOverlayAsset]] = {}
        self._thumbnail_asset_cache: dict[str, tuple[float, bytes]] = {}

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
    def _is_auditor(current_user: SessionPrincipal) -> bool:
        return "AUDITOR" in set(current_user.platform_roles)

    @staticmethod
    def _sha256_hex(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _cache_key_parts(*parts: str | None) -> str:
        return "|".join((part if isinstance(part, str) and part else "-") for part in parts)

    def _prune_asset_cache_unlocked(self, *, now_monotonic: float) -> None:
        ttl = float(self._asset_cache_ttl_seconds)
        for cache in (self._overlay_asset_cache, self._thumbnail_asset_cache):
            stale_keys = [
                cache_key
                for cache_key, (cached_at, _) in cache.items()
                if (now_monotonic - cached_at) > ttl
            ]
            for cache_key in stale_keys:
                cache.pop(cache_key, None)
            while len(cache) > self._asset_cache_max_entries:
                cache.pop(next(iter(cache)))

    def _get_cached_overlay_asset(
        self,
        *,
        cache_key: str,
    ) -> DocumentLayoutOverlayAsset | None:
        now_monotonic = time.monotonic()
        with self._asset_cache_lock:
            self._prune_asset_cache_unlocked(now_monotonic=now_monotonic)
            entry = self._overlay_asset_cache.get(cache_key)
            if entry is None:
                return None
            cached_at, value = entry
            if (now_monotonic - cached_at) > float(self._asset_cache_ttl_seconds):
                self._overlay_asset_cache.pop(cache_key, None)
                return None
            self._overlay_asset_cache.pop(cache_key, None)
            self._overlay_asset_cache[cache_key] = (cached_at, value)
            return value

    def _set_cached_overlay_asset(
        self,
        *,
        cache_key: str,
        value: DocumentLayoutOverlayAsset,
    ) -> None:
        now_monotonic = time.monotonic()
        with self._asset_cache_lock:
            self._overlay_asset_cache.pop(cache_key, None)
            self._overlay_asset_cache[cache_key] = (now_monotonic, value)
            self._prune_asset_cache_unlocked(now_monotonic=now_monotonic)

    def _get_cached_thumbnail_bytes(self, *, cache_key: str) -> bytes | None:
        now_monotonic = time.monotonic()
        with self._asset_cache_lock:
            self._prune_asset_cache_unlocked(now_monotonic=now_monotonic)
            entry = self._thumbnail_asset_cache.get(cache_key)
            if entry is None:
                return None
            cached_at, payload = entry
            if (now_monotonic - cached_at) > float(self._asset_cache_ttl_seconds):
                self._thumbnail_asset_cache.pop(cache_key, None)
                return None
            self._thumbnail_asset_cache.pop(cache_key, None)
            self._thumbnail_asset_cache[cache_key] = (cached_at, payload)
            return payload

    def _set_cached_thumbnail_bytes(self, *, cache_key: str, payload: bytes) -> None:
        now_monotonic = time.monotonic()
        with self._asset_cache_lock:
            self._thumbnail_asset_cache.pop(cache_key, None)
            self._thumbnail_asset_cache[cache_key] = (now_monotonic, payload)
            self._prune_asset_cache_unlocked(now_monotonic=now_monotonic)

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

    def _require_redaction_view_access(
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
            raise DocumentRedactionAccessDeniedError(
                "Membership is required for privacy-review access."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_REDACTION_VIEW_ROLES:
            raise DocumentRedactionAccessDeniedError(
                "Current role cannot view privacy-review routes in this project."
            )

    def _require_redaction_compare_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        if self._is_admin(current_user) or self._is_auditor(current_user):
            return
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if not context.is_member:
            raise DocumentRedactionAccessDeniedError(
                "Membership is required for privacy compare access."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_REDACTION_COMPARE_VIEW_ROLES:
            raise DocumentRedactionAccessDeniedError(
                "Current role cannot view privacy compare routes in this project."
            )

    def _require_redaction_mutation_access(
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
            raise DocumentRedactionAccessDeniedError(
                "Membership is required for privacy-review administration."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_REDACTION_MUTATION_ROLES:
            raise DocumentRedactionAccessDeniedError(
                "Current role cannot create, cancel, activate, or review privacy runs."
            )
        return str(role)

    def _require_redaction_policy_rerun_access(
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
            raise DocumentRedactionAccessDeniedError(
                "Membership is required for policy rerun administration."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_REDACTION_POLICY_RERUN_ROLES:
            raise DocumentRedactionAccessDeniedError(
                "Current role cannot request policy reruns in this project."
            )
        return str(role)

    def _require_redaction_reviewed_output_read_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        review_status: RedactionRunReviewStatus,
    ) -> None:
        if self._is_admin(current_user):
            return
        if self._is_auditor(current_user):
            if review_status != "APPROVED":
                raise DocumentRedactionAccessDeniedError(
                    "Auditor access to reviewed outputs is available only for APPROVED runs."
                )
            return
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if not context.is_member:
            raise DocumentRedactionAccessDeniedError(
                "Membership is required for reviewed-output access."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_REDACTION_REVIEWED_OUTPUT_VIEW_ROLES:
            raise DocumentRedactionAccessDeniedError(
                "Current role cannot access reviewed output artefacts."
            )

    def _require_governance_view_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> str:
        if self._is_admin(current_user):
            return "ADMIN"
        if self._is_auditor(current_user):
            return "AUDITOR"
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if not context.is_member:
            raise DocumentGovernanceAccessDeniedError(
                "Membership is required for governance access."
            )
        role = context.summary.current_user_role
        if role not in _ALLOWED_GOVERNANCE_VIEW_ROLES:
            raise DocumentGovernanceAccessDeniedError(
                "Current role cannot access governance routes in this project."
            )
        return str(role)

    def _require_governance_ledger_view_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> str:
        role = self._require_governance_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        if role not in _ALLOWED_GOVERNANCE_LEDGER_VIEW_ROLES:
            raise DocumentGovernanceAccessDeniedError(
                "Current role cannot access controlled evidence-ledger routes."
            )
        return role

    def _require_governance_ledger_verify_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> None:
        role = self._require_governance_ledger_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        if role != "ADMIN":
            raise DocumentGovernanceAccessDeniedError(
                "Current role cannot trigger ledger verification mutations."
            )

    @staticmethod
    def _is_governance_ledger_event(event_type: str) -> bool:
        return event_type.startswith("LEDGER_")

    def _resolve_governance_event_reason(
        self,
        *,
        event: GovernanceRunEventRecord,
        role: str,
    ) -> str | None:
        if role in _ALLOWED_GOVERNANCE_LEDGER_VIEW_ROLES:
            return event.reason
        if not self._is_governance_ledger_event(event.event_type):
            return event.reason
        return "Controlled ledger transition recorded."

    @staticmethod
    def _derive_redaction_run_output_readiness_state(
        *,
        review_status: RedactionRunReviewStatus,
        run_output: RedactionRunOutputRecord,
    ) -> RedactionRunOutputReadinessState:
        if review_status != "APPROVED":
            return "APPROVAL_REQUIRED"
        if run_output.status == "READY":
            return "OUTPUT_READY"
        if run_output.status == "FAILED":
            return "OUTPUT_FAILED"
        if run_output.status == "CANCELED":
            return "OUTPUT_CANCELED"
        if isinstance(run_output.started_at, datetime):
            return "OUTPUT_GENERATING"
        return "APPROVED_OUTPUT_PENDING"

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
    def _is_fallback_engine(engine: TranscriptionRunEngine) -> bool:
        return engine in _TRANSCRIPTION_FALLBACK_ENGINES

    @staticmethod
    def _normalize_transcription_compare_decision(
        value: str,
    ) -> TranscriptionCompareDecision:
        normalized = value.strip().upper()
        if normalized not in {"KEEP_BASE", "PROMOTE_CANDIDATE"}:
            raise DocumentValidationError(
                "decision must be KEEP_BASE or PROMOTE_CANDIDATE."
            )
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _normalize_transcript_variant_kind(value: str | None) -> TranscriptVariantKind:
        normalized = value.strip().upper() if isinstance(value, str) else "NORMALISED"
        if normalized not in {"NORMALISED"}:
            raise DocumentValidationError("variantKind must be NORMALISED.")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _normalize_transcript_variant_suggestion_decision(
        value: str,
    ) -> TranscriptVariantSuggestionDecision:
        normalized = value.strip().upper()
        if normalized not in {"ACCEPT", "REJECT"}:
            raise DocumentValidationError("decision must be ACCEPT or REJECT.")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _normalize_fallback_reason_codes(
        value: Sequence[str] | None,
    ) -> list[TranscriptionFallbackReasonCode]:
        if value is None:
            return []
        normalized: list[TranscriptionFallbackReasonCode] = []
        seen: set[str] = set()
        for item in value:
            token = item.strip().upper() if isinstance(item, str) else ""
            if not token or token in seen:
                continue
            if token not in _TRANSCRIPTION_FALLBACK_REASONS:
                raise DocumentValidationError(
                    "fallbackReasonCodes must use supported fallback trigger codes."
                )
            seen.add(token)
            normalized.append(token)  # type: ignore[arg-type]
        return normalized

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
    def _default_transcription_prompt_template() -> tuple[str, str]:
        return (
            _TRANSCRIPTION_PRIMARY_PROMPT_TEMPLATE_ID,
            hashlib.sha256(
                _TRANSCRIPTION_PRIMARY_PROMPT_TEMPLATE_SOURCE.encode("utf-8")
            ).hexdigest(),
        )

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

    @staticmethod
    def _normalize_redaction_run_kind(value: str | None) -> RedactionRunKind:
        if not isinstance(value, str):
            return "BASELINE"
        normalized = value.strip().upper()
        if not normalized:
            return "BASELINE"
        if normalized in {"BASELINE", "POLICY_RERUN"}:
            return normalized
        raise DocumentValidationError("runKind must be BASELINE or POLICY_RERUN.")

    @staticmethod
    def _normalize_redaction_reference(
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
    def _canonical_policy_rules_sha256(rules_json: Mapping[str, object]) -> str:
        payload = json.dumps(
            dict(rules_json),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _coerce_probability(value: object) -> float | None:
        if not isinstance(value, (int, float)):
            return None
        numeric = float(value)
        if numeric < 0.0 or numeric > 1.0:
            return None
        return numeric

    @staticmethod
    def _normalized_category_label(value: object, *, fallback: str) -> str:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
        return fallback

    def _build_policy_pre_activation_warnings(
        self,
        *,
        policy_snapshot_json: Mapping[str, object],
    ) -> tuple[DocumentRedactionPolicyWarningSnapshot, ...]:
        categories_raw = policy_snapshot_json.get("categories")
        categories = (
            [item for item in categories_raw if isinstance(item, Mapping)]
            if isinstance(categories_raw, Sequence)
            and not isinstance(categories_raw, (str, bytes))
            else []
        )

        broad_allow_categories: set[str] = set()
        inconsistent_threshold_categories: set[str] = set()

        for index, category_item in enumerate(categories):
            category = dict(category_item)
            category_label = self._normalized_category_label(
                category.get("id"),
                fallback=f"categories[{index}]",
            )
            action = (
                str(category.get("action")).strip().upper()
                if isinstance(category.get("action"), str)
                else ""
            )
            if action == "ALLOW":
                broad_allow_categories.add(category_label)

            review_required_below = self._coerce_probability(category.get("review_required_below"))
            auto_apply_above = self._coerce_probability(category.get("auto_apply_above"))
            confidence_threshold = self._coerce_probability(category.get("confidence_threshold"))

            has_inconsistent_threshold = (
                review_required_below is not None
                and auto_apply_above is not None
                and auto_apply_above < review_required_below
            ) or (
                review_required_below is not None
                and confidence_threshold is not None
                and confidence_threshold < review_required_below
            ) or (
                auto_apply_above is not None
                and confidence_threshold is not None
                and confidence_threshold < auto_apply_above
            )
            if has_inconsistent_threshold:
                inconsistent_threshold_categories.add(category_label)

        warnings: list[DocumentRedactionPolicyWarningSnapshot] = []
        if broad_allow_categories:
            sorted_categories = tuple(sorted(broad_allow_categories))
            warnings.append(
                DocumentRedactionPolicyWarningSnapshot(
                    code="BROAD_ALLOW_RULE",
                    severity="WARNING",
                    message=(
                        "Policy contains broad allow action(s) that may bypass redaction for"
                        f" high-risk categories: {', '.join(sorted_categories)}."
                    ),
                    affected_categories=sorted_categories,
                )
            )
        if inconsistent_threshold_categories:
            sorted_categories = tuple(sorted(inconsistent_threshold_categories))
            warnings.append(
                DocumentRedactionPolicyWarningSnapshot(
                    code="INCONSISTENT_THRESHOLD",
                    severity="WARNING",
                    message=(
                        "Policy contains inconsistent confidence thresholds that can create"
                        f" ambiguous reviewer gates: {', '.join(sorted_categories)}."
                    ),
                    affected_categories=sorted_categories,
                )
            )
        return tuple(warnings)

    def _load_policy_for_redaction_rerun(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> RedactionPolicyRecord:
        try:
            target_policy = self._policy_store.get_policy(
                project_id=project_id,
                policy_id=policy_id,
            )
            if target_policy is None:
                raise DocumentValidationError(
                    "policyId was not found in the requested project."
                )
            if target_policy.status not in {"ACTIVE", "DRAFT"}:
                raise DocumentRedactionConflictError(
                    "Policy reruns require an ACTIVE or validated DRAFT target policy revision."
                )
            if target_policy.validation_status != "VALID":
                raise DocumentRedactionConflictError(
                    "Policy reruns require target policy validation_status=VALID."
                )
            rules_hash = self._canonical_policy_rules_sha256(target_policy.rules_json)
            if target_policy.validated_rules_sha256 != rules_hash:
                raise DocumentRedactionConflictError(
                    "Policy reruns reject stale validated revisions whose rules no longer match validated hash."
                )
            if target_policy.status == "DRAFT":
                projection = self._policy_store.get_projection(project_id=project_id)
                if (
                    projection is not None
                    and isinstance(projection.active_policy_family_id, str)
                    and projection.active_policy_family_id
                    and projection.active_policy_family_id != target_policy.policy_family_id
                ):
                    raise DocumentRedactionConflictError(
                        "Policy reruns require DRAFT revisions in the active project policy lineage."
                    )
        except PolicyStoreUnavailableError as error:
            raise DocumentStoreUnavailableError("Policy lookup for rerun failed.") from error
        return target_policy

    @staticmethod
    def _normalize_redaction_decision_status(value: str) -> RedactionDecisionStatus:
        normalized = value.strip().upper()
        if normalized in {
            "AUTO_APPLIED",
            "NEEDS_REVIEW",
            "APPROVED",
            "OVERRIDDEN",
            "FALSE_POSITIVE",
        }:
            return normalized
        raise DocumentValidationError(
            "decisionStatus must be AUTO_APPLIED, NEEDS_REVIEW, APPROVED, OVERRIDDEN, or FALSE_POSITIVE."
        )

    @staticmethod
    def _normalize_redaction_page_review_status(value: str) -> RedactionPageReviewStatus:
        normalized = value.strip().upper()
        if normalized in {"NOT_STARTED", "IN_REVIEW", "APPROVED", "CHANGES_REQUESTED"}:
            return normalized
        raise DocumentValidationError(
            "reviewStatus must be NOT_STARTED, IN_REVIEW, APPROVED, or CHANGES_REQUESTED."
        )

    @staticmethod
    def _normalize_redaction_run_review_status(value: str) -> RedactionRunReviewStatus:
        normalized = value.strip().upper()
        if normalized in {"APPROVED", "CHANGES_REQUESTED"}:
            return normalized
        raise DocumentValidationError(
            "reviewStatus must be APPROVED or CHANGES_REQUESTED."
        )

    @staticmethod
    def _normalize_redaction_action_type(value: str | None) -> RedactionDecisionActionType:
        if not isinstance(value, str):
            return "MASK"
        normalized = value.strip().upper()
        if not normalized:
            return "MASK"
        if normalized in {"MASK", "PSEUDONYMIZE", "GENERALIZE"}:
            return normalized  # type: ignore[return-value]
        raise DocumentValidationError(
            "actionType must be MASK, PSEUDONYMIZE, or GENERALIZE."
        )

    @staticmethod
    def _is_unresolved_redaction_decision(status: RedactionDecisionStatus) -> bool:
        return status in {"NEEDS_REVIEW", "OVERRIDDEN", "FALSE_POSITIVE"}

    @staticmethod
    def _is_direct_identifier_category(category: str) -> bool:
        normalized = category.strip().upper()
        if not normalized:
            return False
        direct_categories = {
            "DIRECT_IDENTIFIER",
            "PERSON_NAME",
            "ORGANIZATION",
            "LOCATION",
            "EMAIL",
            "PHONE",
            "URL",
            "POSTCODE",
            "ID_NUMBER",
            "NATIONAL_ID",
            "NI_NUMBER",
            "NHS_NUMBER",
        }
        return normalized in direct_categories or normalized.startswith("DIRECT_")

    def _load_redaction_document(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> DocumentRecord:
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        return document

    def _load_redaction_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunRecord:
        run = self._store.get_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentRedactionRunNotFoundError("Redaction run not found.")
        return run

    def _list_all_redaction_findings(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str | None = None,
        category: str | None = None,
        unresolved_only: bool = False,
    ) -> list[RedactionFindingRecord]:
        return self._store.list_redaction_findings(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            category=category,
            unresolved_only=unresolved_only,
        )

    def _list_all_redaction_page_reviews(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> list[RedactionPageReviewRecord]:
        items: list[RedactionPageReviewRecord] = []
        list_cursor = 0
        while True:
            batch, next_cursor = self._store.list_redaction_page_reviews(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                cursor=list_cursor,
                page_size=500,
            )
            items.extend(batch)
            if next_cursor is None:
                break
            list_cursor = next_cursor
        return items

    def _list_all_redaction_runs(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> list[RedactionRunRecord]:
        items: list[RedactionRunRecord] = []
        list_cursor = 0
        while True:
            batch, next_cursor = self._store.list_redaction_runs(
                project_id=project_id,
                document_id=document_id,
                cursor=list_cursor,
                page_size=200,
            )
            items.extend(batch)
            if next_cursor is None:
                break
            list_cursor = next_cursor
        return items

    def _build_redaction_detection_lines_for_page(
        self,
        *,
        project_id: str,
        document_id: str,
        run: RedactionRunRecord,
        page: DocumentPageRecord,
    ) -> list[RedactionDetectionLine]:
        line_rows = self._store.list_line_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_transcription_run_id,
            page_id=page.id,
        )
        hydrated_lines = self._hydrate_transcription_lines_with_active_versions(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_transcription_run_id,
            page_id=page.id,
            rows=line_rows,
        )
        token_rows = self._store.list_token_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_transcription_run_id,
            page_id=page.id,
        )
        tokens_by_line: dict[str, list[RedactionDetectionToken]] = {}
        for token in token_rows:
            if (
                not isinstance(token.line_id, str)
                or not token.line_id
                or token.source_ref_id != token.line_id
            ):
                continue
            tokens_by_line.setdefault(token.line_id, []).append(
                RedactionDetectionToken(
                    token_id=token.token_id,
                    token_index=token.token_index,
                    token_text=token.token_text,
                    line_id=token.line_id,
                    source_ref_id=token.source_ref_id,
                    bbox_json=token.bbox_json,
                    polygon_json=token.polygon_json,
                )
            )
        for line_id in list(tokens_by_line):
            tokens_by_line[line_id] = sorted(
                tokens_by_line[line_id],
                key=lambda item: (item.token_index, item.token_id),
            )

        rows: list[RedactionDetectionLine] = []
        for line in hydrated_lines:
            rows.append(
                RedactionDetectionLine(
                    page_id=page.id,
                    page_index=page.page_index,
                    line_id=line.line_id,
                    text=line.text_diplomatic,
                    tokens=tuple(tokens_by_line.get(line.line_id, [])),
                )
            )
        return rows

    def _build_redaction_page_preview_artifact(
        self,
        *,
        project_id: str,
        document_id: str,
        run: RedactionRunRecord,
        page_id: str,
    ) -> SafeguardedPreviewArtifact:
        line_rows = self._store.list_line_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_transcription_run_id,
            page_id=page_id,
        )
        hydrated_lines = self._hydrate_transcription_lines_with_active_versions(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_transcription_run_id,
            page_id=page_id,
            rows=line_rows,
        )
        preview_lines = [
            PreviewLine(
                line_id=line.line_id,
                text=line.text_diplomatic,
            )
            for line in hydrated_lines
        ]
        token_rows = self._store.list_token_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_transcription_run_id,
            page_id=page_id,
        )
        preview_tokens = [
            PreviewToken(
                token_id=token.token_id,
                line_id=token.line_id,
                token_index=token.token_index,
                token_text=token.token_text,
            )
            for token in token_rows
            if isinstance(token.line_id, str) and token.line_id.strip()
        ]
        findings = self._list_all_redaction_findings(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page_id,
        )
        decision_events = self._store.list_redaction_decision_events(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page_id,
        )
        latest_action_by_finding_id: dict[str, RedactionDecisionActionType] = {}
        for event in decision_events:
            latest_action_by_finding_id[event.finding_id] = event.action_type
        preview_findings = [
            PreviewFinding(
                finding_id=finding.id,
                decision_status=finding.decision_status,
                line_id=finding.line_id,
                span_start=finding.span_start,
                span_end=finding.span_end,
                token_refs_json=(
                    [dict(item) for item in finding.token_refs_json]
                    if isinstance(finding.token_refs_json, Sequence)
                    and not isinstance(finding.token_refs_json, (str, bytes))
                    else None
                ),
                area_mask_id=finding.area_mask_id,
                action_type=latest_action_by_finding_id.get(finding.id, "MASK"),
                replacement_text=extract_transformation_value(
                    finding.basis_secondary_json
                    if isinstance(finding.basis_secondary_json, Mapping)
                    else None
                ),
            )
            for finding in findings
        ]
        return build_safeguarded_preview_artifact(
            lines=preview_lines,
            tokens=preview_tokens,
            findings=preview_findings,
        )

    def _load_redaction_approved_snapshot_payload(
        self,
        *,
        snapshot_bytes: bytes,
        expected_run_id: str,
        expected_snapshot_sha256: str | None,
    ) -> dict[str, object]:
        if expected_snapshot_sha256 is not None:
            actual_snapshot_sha256 = self._sha256_hex(snapshot_bytes)
            if actual_snapshot_sha256 != expected_snapshot_sha256:
                raise DocumentStoreUnavailableError(
                    "Approved snapshot artifact hash mismatch."
                )
        try:
            payload = json.loads(snapshot_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DocumentStoreUnavailableError(
                "Approved snapshot artifact payload is invalid JSON."
            ) from error
        if not isinstance(payload, dict):
            raise DocumentStoreUnavailableError("Approved snapshot payload is invalid.")
        run_id = payload.get("runId")
        if not isinstance(run_id, str) or run_id.strip() != expected_run_id:
            raise DocumentStoreUnavailableError("Approved snapshot run id mismatch.")
        return payload

    @staticmethod
    def _extract_snapshot_findings_for_page(
        *,
        approved_snapshot_payload: Mapping[str, object],
        page_id: str,
    ) -> list[PreviewFinding]:
        findings_payload = approved_snapshot_payload.get("findings")
        if not isinstance(findings_payload, list):
            return []
        findings: list[PreviewFinding] = []
        for item in findings_payload:
            if not isinstance(item, Mapping):
                continue
            page_id_value = item.get("pageId")
            if not isinstance(page_id_value, str) or page_id_value != page_id:
                continue
            finding_id = item.get("id")
            decision_status = item.get("decisionStatus")
            if not isinstance(finding_id, str) or not finding_id.strip():
                continue
            if not isinstance(decision_status, str) or not decision_status.strip():
                continue
            token_refs_json: list[dict[str, object]] | None = None
            token_refs_payload = item.get("tokenRefsJson")
            if isinstance(token_refs_payload, list):
                token_refs_json = [
                    dict(entry)
                    for entry in token_refs_payload
                    if isinstance(entry, Mapping)
                ]
            findings.append(
                PreviewFinding(
                    finding_id=finding_id.strip(),
                    decision_status=decision_status.strip().upper(),
                    line_id=(
                        str(item["lineId"])
                        if isinstance(item.get("lineId"), str)
                        and str(item["lineId"]).strip()
                        else None
                    ),
                    span_start=(
                        int(item["spanStart"])
                        if isinstance(item.get("spanStart"), int)
                        else None
                    ),
                    span_end=(
                        int(item["spanEnd"])
                        if isinstance(item.get("spanEnd"), int)
                        else None
                    ),
                    token_refs_json=token_refs_json,
                    area_mask_id=(
                        str(item["areaMaskId"])
                        if isinstance(item.get("areaMaskId"), str)
                        and str(item["areaMaskId"]).strip()
                        else None
                    ),
                    action_type=(
                        str(item["actionType"]).strip().upper()
                        if isinstance(item.get("actionType"), str)
                        and str(item["actionType"]).strip()
                        else "MASK"
                    ),
                    replacement_text=extract_transformation_value(
                        dict(item["basisSecondaryJson"])
                        if isinstance(item.get("basisSecondaryJson"), Mapping)
                        else None
                    ),
                )
            )
        return findings

    def _build_redaction_page_preview_artifact_from_approved_snapshot(
        self,
        *,
        project_id: str,
        document_id: str,
        run: RedactionRunRecord,
        approved_snapshot_payload: Mapping[str, object],
        page_id: str,
    ) -> SafeguardedPreviewArtifact:
        snapshot_run = approved_snapshot_payload.get("run")
        if isinstance(snapshot_run, Mapping):
            snapshot_input_run = snapshot_run.get("inputTranscriptionRunId")
            if (
                isinstance(snapshot_input_run, str)
                and snapshot_input_run.strip()
                and snapshot_input_run.strip() != run.input_transcription_run_id
            ):
                raise DocumentStoreUnavailableError(
                    "Approved snapshot transcription basis does not match run lineage."
                )
        line_rows = self._store.list_line_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_transcription_run_id,
            page_id=page_id,
        )
        hydrated_lines = self._hydrate_transcription_lines_with_active_versions(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_transcription_run_id,
            page_id=page_id,
            rows=line_rows,
        )
        preview_lines = [
            PreviewLine(
                line_id=line.line_id,
                text=line.text_diplomatic,
            )
            for line in hydrated_lines
        ]
        token_rows = self._store.list_token_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_transcription_run_id,
            page_id=page_id,
        )
        preview_tokens = [
            PreviewToken(
                token_id=token.token_id,
                line_id=token.line_id,
                token_index=token.token_index,
                token_text=token.token_text,
            )
            for token in token_rows
            if isinstance(token.line_id, str) and token.line_id.strip()
        ]
        preview_findings = self._extract_snapshot_findings_for_page(
            approved_snapshot_payload=approved_snapshot_payload,
            page_id=page_id,
        )
        return build_safeguarded_preview_artifact(
            lines=preview_lines,
            tokens=preview_tokens,
            findings=preview_findings,
        )

    def _persist_redaction_approved_snapshot_artifact(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        review: RedactionRunReviewRecord,
    ) -> bytes:
        if (
            not isinstance(review.approved_snapshot_key, str)
            or not review.approved_snapshot_key.strip()
            or not isinstance(review.approved_snapshot_sha256, str)
            or not review.approved_snapshot_sha256.strip()
        ):
            raise DocumentStoreUnavailableError(
                "Approved review snapshot metadata is incomplete."
            )
        snapshot_bytes, snapshot_sha256 = self._store.get_redaction_approval_snapshot_artifact(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if snapshot_sha256 != review.approved_snapshot_sha256:
            raise DocumentStoreUnavailableError(
                "Approved snapshot hash changed unexpectedly."
            )
        try:
            stored = self._storage.write_redaction_approved_snapshot(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                approved_snapshot_sha256=snapshot_sha256,
                payload=snapshot_bytes,
            )
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError(_CONTROLLED_STORAGE_FAILURE_MESSAGE) from error
        if stored.object_key != review.approved_snapshot_key:
            raise DocumentStoreUnavailableError(
                "Approved snapshot storage key mismatch."
            )
        return snapshot_bytes

    def _refresh_redaction_reviewed_outputs_from_approved_snapshot(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run: RedactionRunRecord,
        review: RedactionRunReviewRecord,
    ) -> None:
        if (
            not isinstance(review.approved_snapshot_key, str)
            or not review.approved_snapshot_key.strip()
            or not isinstance(review.approved_snapshot_sha256, str)
            or not review.approved_snapshot_sha256.strip()
        ):
            raise DocumentStoreUnavailableError(
                "Approved review snapshot metadata is incomplete."
            )
        try:
            snapshot_bytes = self._storage.read_object_bytes(review.approved_snapshot_key)
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError(
                "Approved snapshot artifact could not be loaded."
            ) from error
        approved_snapshot_payload = self._load_redaction_approved_snapshot_payload(
            snapshot_bytes=snapshot_bytes,
            expected_run_id=run.id,
            expected_snapshot_sha256=review.approved_snapshot_sha256,
        )
        self._store.reset_redaction_outputs_for_reviewed_generation(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
        )
        pages = self._store.list_document_pages(
            project_id=project_id,
            document_id=document_id,
        )
        for page in pages:
            try:
                artifact = self._build_redaction_page_preview_artifact_from_approved_snapshot(
                    project_id=project_id,
                    document_id=document_id,
                    run=run,
                    approved_snapshot_payload=approved_snapshot_payload,
                    page_id=page.id,
                )
                try:
                    stored_preview = self._storage.write_redaction_preview(
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run.id,
                        page_id=page.id,
                        preview_sha256=artifact.sha256,
                        payload=artifact.png_bytes,
                    )
                except DocumentStorageError as error:
                    raise DocumentStoreUnavailableError(
                        _CONTROLLED_STORAGE_FAILURE_MESSAGE
                    ) from error
                self._store.set_redaction_output_projection(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run.id,
                    page_id=page.id,
                    status="READY",
                    safeguarded_preview_key=stored_preview.object_key,
                    preview_sha256=artifact.sha256,
                    failure_reason=None,
                )
            except Exception as error:  # noqa: BLE001
                failure_reason = f"Reviewed preview generation failed: {error}"
                if len(failure_reason) > 600:
                    failure_reason = failure_reason[:600]
                self._store.set_redaction_output_projection(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run.id,
                    page_id=page.id,
                    status="FAILED",
                    safeguarded_preview_key=None,
                    preview_sha256=None,
                    failure_reason=failure_reason,
                )
        run_output = self._store.get_redaction_run_output(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
        )
        if run_output is None:
            raise DocumentStoreUnavailableError("Reviewed run output projection is missing.")
        if run_output.status != "READY":
            return

        outputs = self._store.list_redaction_outputs(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
        )
        if not outputs:
            self._store.set_redaction_run_output_status(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                status="FAILED",
                failure_reason="Reviewed manifest generation requires at least one page preview.",
                actor_user_id=current_user.user_id,
            )
            raise DocumentStoreUnavailableError(
                "Reviewed manifest generation requires at least one page preview."
            )
        page_rows: list[tuple[str, str]] = []
        for output in outputs:
            if output.status != "READY":
                self._store.set_redaction_run_output_status(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run.id,
                    status="FAILED",
                    failure_reason="Reviewed manifest generation requires READY preview outputs.",
                    actor_user_id=current_user.user_id,
                )
                raise DocumentStoreUnavailableError(
                    "Reviewed manifest generation requires READY preview outputs."
                )
            if (
                not isinstance(output.preview_sha256, str)
                or not output.preview_sha256.strip()
                or not isinstance(output.safeguarded_preview_key, str)
                or not output.safeguarded_preview_key.strip()
            ):
                self._store.set_redaction_run_output_status(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run.id,
                    status="FAILED",
                    failure_reason="Reviewed preview projection is missing immutable key or hash.",
                    actor_user_id=current_user.user_id,
                )
                raise DocumentStoreUnavailableError(
                    "Reviewed preview projection is missing immutable key or hash."
                )
            page_rows.append((output.page_id, output.preview_sha256))
        manifest_bytes = canonical_preview_manifest_bytes(
            run_id=run.id,
            page_rows=page_rows,
            approved_snapshot_sha256=review.approved_snapshot_sha256,
            approved_snapshot_payload=approved_snapshot_payload,
        )
        manifest_sha256 = self._sha256_hex(manifest_bytes)
        if run_output.output_manifest_sha256 != manifest_sha256:
            self._store.set_redaction_run_output_status(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                status="FAILED",
                failure_reason="Run output manifest hash projection mismatch.",
                actor_user_id=current_user.user_id,
            )
            raise DocumentStoreUnavailableError(
                "Run output manifest hash projection mismatch."
            )
        expected_manifest_key = self._storage.build_redaction_run_manifest_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            output_manifest_sha256=manifest_sha256,
        )
        if run_output.output_manifest_key != expected_manifest_key:
            self._store.set_redaction_run_output_status(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                status="FAILED",
                failure_reason="Run output manifest key projection mismatch.",
                actor_user_id=current_user.user_id,
            )
            raise DocumentStoreUnavailableError(
                "Run output manifest key projection mismatch."
            )
        try:
            stored_manifest = self._storage.write_redaction_run_manifest(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                output_manifest_sha256=manifest_sha256,
                payload=manifest_bytes,
            )
        except DocumentStorageError as error:
            self._store.set_redaction_run_output_status(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                status="FAILED",
                failure_reason=_CONTROLLED_STORAGE_FAILURE_MESSAGE,
                actor_user_id=current_user.user_id,
            )
            raise DocumentStoreUnavailableError(_CONTROLLED_STORAGE_FAILURE_MESSAGE) from error
        if stored_manifest.object_key != run_output.output_manifest_key:
            self._store.set_redaction_run_output_status(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                status="FAILED",
                failure_reason="Run output manifest object key mismatch.",
                actor_user_id=current_user.user_id,
            )
            raise DocumentStoreUnavailableError(
                "Run output manifest object key mismatch."
            )

    def _refresh_redaction_page_preview_output(
        self,
        *,
        project_id: str,
        document_id: str,
        run: RedactionRunRecord,
        page_id: str,
    ) -> RedactionOutputRecord:
        try:
            artifact = self._build_redaction_page_preview_artifact(
                project_id=project_id,
                document_id=document_id,
                run=run,
                page_id=page_id,
            )
        except Exception as error:  # noqa: BLE001
            failure_reason = f"Preview generation failed: {error}"
            if len(failure_reason) > 600:
                failure_reason = failure_reason[:600]
            return self._store.set_redaction_output_projection(
                project_id=project_id,
                document_id=document_id,
                run_id=run.id,
                page_id=page_id,
                status="FAILED",
                safeguarded_preview_key=None,
                preview_sha256=None,
                failure_reason=failure_reason,
            )
        return self._store.set_redaction_output_projection(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page_id,
            status="READY",
            safeguarded_preview_key=f"redaction://{run.id}/{page_id}",
            preview_sha256=artifact.sha256,
            failure_reason=None,
        )

    def _refresh_redaction_run_preview_outputs(
        self,
        *,
        project_id: str,
        document_id: str,
        run: RedactionRunRecord,
        page_id: str | None = None,
    ) -> list[RedactionOutputRecord]:
        pages = self._store.list_document_pages(
            project_id=project_id,
            document_id=document_id,
        )
        target_page_ids = (
            {page_id}
            if isinstance(page_id, str) and page_id.strip()
            else {page.id for page in pages}
        )
        refreshed: list[RedactionOutputRecord] = []
        for page in pages:
            if page.id not in target_page_ids:
                continue
            refreshed.append(
                self._refresh_redaction_page_preview_output(
                    project_id=project_id,
                    document_id=document_id,
                    run=run,
                    page_id=page.id,
                )
            )
        return refreshed

    def _materialize_redaction_findings_for_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run: RedactionRunRecord,
    ) -> list[RedactionFindingRecord]:
        policy_config = resolve_direct_identifier_policy_config(
            policy_snapshot_json=run.policy_snapshot_json,
            pinned_recall_floor=self._settings.redaction_direct_identifier_recall_floor,
            pinned_default_threshold=self._settings.redaction_default_auto_apply_threshold,
            pinned_ner_timeout_seconds=self._settings.redaction_ner_timeout_seconds,
            pinned_assist_timeout_seconds=self._settings.redaction_assist_timeout_seconds,
            pinned_assist_enabled=self._settings.redaction_assist_enabled,
        )
        ner_detector = LocalNERDetector(timeout_seconds=policy_config.ner_timeout_seconds)
        assist_explainer = (
            BoundedAssistExplainer(timeout_seconds=policy_config.assist_timeout_seconds)
            if policy_config.assist_enabled
            else None
        )

        pages = self._store.list_document_pages(
            project_id=project_id,
            document_id=document_id,
        )
        write_rows: list[dict[str, object]] = []
        for page in pages:
            detection_lines = self._build_redaction_detection_lines_for_page(
                project_id=project_id,
                document_id=document_id,
                run=run,
                page=page,
            )
            findings = detect_direct_identifier_findings(
                lines=detection_lines,
                policy_config=policy_config,
                ner_detector=ner_detector,
                assist_explainer=assist_explainer,
            )
            indirect_findings = detect_indirect_identifier_findings(
                lines=detection_lines,
                policy_snapshot_json=run.policy_snapshot_json,
            )
            place_generalization_spans = {
                (finding.line_id, finding.span_start, finding.span_end)
                for finding in indirect_findings
                if finding.category == "INDIRECT_TOWN"
            }
            for finding in findings:
                if (
                    finding.line_id is not None
                    and isinstance(finding.span_start, int)
                    and isinstance(finding.span_end, int)
                    and (finding.line_id, finding.span_start, finding.span_end)
                    in place_generalization_spans
                    and finding.category.strip().upper() in {"LOCATION", "ADDRESS", "PLACE"}
                ):
                    continue
                basis_secondary_json = (
                    dict(finding.basis_secondary_json)
                    if isinstance(finding.basis_secondary_json, Mapping)
                    else None
                )
                if finding.assist_summary is not None:
                    if basis_secondary_json is None:
                        basis_secondary_json = {}
                    basis_secondary_json["assistSummary"] = finding.assist_summary
                write_rows.append(
                    {
                        "page_id": finding.page_id,
                        "line_id": finding.line_id,
                        "category": finding.category,
                        "span_start": finding.span_start,
                        "span_end": finding.span_end,
                        "span_basis_kind": "LINE_TEXT",
                        "span_basis_ref": finding.line_id,
                        "confidence": finding.confidence,
                        "basis_primary": finding.basis_primary,
                        "basis_secondary_json": basis_secondary_json,
                        "assist_explanation_key": None,
                        "assist_explanation_sha256": None,
                        "bbox_refs": dict(finding.bbox_refs),
                        "token_refs_json": (
                            [dict(item) for item in finding.token_refs_json]
                            if isinstance(finding.token_refs_json, Sequence)
                            and not isinstance(finding.token_refs_json, (str, bytes))
                            else None
                        ),
                        "area_mask_id": None,
                        "decision_status": finding.decision_status,
                        "decision_reason": finding.decision_reason,
                        "action_type": "MASK",
                    }
                )
            for finding in indirect_findings:
                write_rows.append(
                    {
                        "page_id": finding.page_id,
                        "line_id": finding.line_id,
                        "category": finding.category,
                        "span_start": finding.span_start,
                        "span_end": finding.span_end,
                        "span_basis_kind": "LINE_TEXT",
                        "span_basis_ref": finding.line_id,
                        "confidence": finding.confidence,
                        "basis_primary": finding.basis_primary,
                        "basis_secondary_json": dict(finding.basis_secondary_json),
                        "assist_explanation_key": None,
                        "assist_explanation_sha256": None,
                        "bbox_refs": dict(finding.bbox_refs),
                        "token_refs_json": (
                            [dict(item) for item in finding.token_refs_json]
                            if isinstance(finding.token_refs_json, Sequence)
                            and not isinstance(finding.token_refs_json, (str, bytes))
                            else None
                        ),
                        "area_mask_id": None,
                        "decision_status": finding.decision_status,
                        "decision_reason": finding.decision_reason,
                        "action_type": finding.action_type,
                    }
                )
        return self._store.replace_redaction_findings(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            findings=write_rows,
        )

    def get_redaction_projection(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentRedactionProjectionRecord | None:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_document(project_id=project_id, document_id=document_id)
        return self._store.get_redaction_projection(
            project_id=project_id,
            document_id=document_id,
        )

    def list_redaction_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        cursor: int = 0,
        page_size: int = 50,
    ) -> tuple[list[RedactionRunRecord], int | None]:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        if cursor < 0:
            raise DocumentValidationError("Cursor must be zero or greater.")
        if page_size < 1 or page_size > 200:
            raise DocumentValidationError("Page size must be between 1 and 200.")
        _ = self._load_redaction_document(project_id=project_id, document_id=document_id)
        return self._store.list_redaction_runs(
            project_id=project_id,
            document_id=document_id,
            cursor=cursor,
            page_size=page_size,
        )

    def get_redaction_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunRecord:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_document(project_id=project_id, document_id=document_id)
        return self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )

    def get_redaction_run_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunRecord:
        return self.get_redaction_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )

    def get_active_redaction_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> tuple[DocumentRedactionProjectionRecord | None, RedactionRunRecord | None]:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_document(project_id=project_id, document_id=document_id)
        projection = self._store.get_redaction_projection(
            project_id=project_id,
            document_id=document_id,
        )
        run = self._store.get_active_redaction_run(
            project_id=project_id,
            document_id=document_id,
        )
        return projection, run

    def create_redaction_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        input_transcription_run_id: str | None = None,
        input_layout_run_id: str | None = None,
        run_kind: str | None = None,
        supersedes_redaction_run_id: str | None = None,
        detectors_version: str | None = None,
    ) -> RedactionRunRecord:
        _ = self._require_redaction_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_document(project_id=project_id, document_id=document_id)
        normalized_run_kind = self._normalize_redaction_run_kind(run_kind)
        normalized_input_transcription_run_id = self._normalize_redaction_reference(
            input_transcription_run_id,
            field_name="inputTranscriptionRunId",
            max_length=120,
        )
        normalized_input_layout_run_id = self._normalize_redaction_reference(
            input_layout_run_id,
            field_name="inputLayoutRunId",
            max_length=120,
        )
        normalized_supersedes_run_id = self._normalize_redaction_reference(
            supersedes_redaction_run_id,
            field_name="supersedesRedactionRunId",
            max_length=120,
        )
        normalized_detectors_version = (
            detectors_version.strip()
            if isinstance(detectors_version, str) and detectors_version.strip()
            else "phase-5.0-scaffold"
        )
        created_run: RedactionRunRecord
        try:
            created_run = self._store.create_redaction_run(
                project_id=project_id,
                document_id=document_id,
                created_by=current_user.user_id,
                input_transcription_run_id=normalized_input_transcription_run_id,
                input_layout_run_id=normalized_input_layout_run_id,
                run_kind=normalized_run_kind,
                supersedes_redaction_run_id=normalized_supersedes_run_id,
                detectors_version=normalized_detectors_version,
            )
        except DocumentRedactionRunConflictError as error:
            raise DocumentRedactionConflictError(str(error)) from error
        try:
            self._materialize_redaction_findings_for_run(
                project_id=project_id,
                document_id=document_id,
                run=created_run,
            )
        except Exception as error:  # noqa: BLE001
            try:
                self._store.cancel_redaction_run(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=created_run.id,
                    canceled_by=current_user.user_id,
                )
            except Exception:  # noqa: BLE001
                pass
            raise DocumentStoreUnavailableError(
                "Redaction run detection pipeline failed."
            ) from error
        hydrated_run = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=created_run.id,
        )
        self._refresh_redaction_run_preview_outputs(
            project_id=project_id,
            document_id=document_id,
            run=hydrated_run,
        )
        return hydrated_run

    def request_policy_rerun(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        source_run_id: str,
        policy_id: str,
    ) -> RedactionRunRecord:
        self._require_redaction_policy_rerun_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_policy_id = self._normalize_redaction_reference(
            policy_id,
            field_name="policyId",
            max_length=120,
        )
        if normalized_policy_id is None:
            raise DocumentValidationError("policyId is required.")
        source_run = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=source_run_id,
        )
        if source_run.status != "SUCCEEDED":
            raise DocumentRedactionConflictError(
                "Policy rerun source run must be SUCCEEDED."
            )
        source_review = self._store.get_redaction_run_review(
            project_id=project_id,
            document_id=document_id,
            run_id=source_run.id,
        )
        if source_review is None or source_review.review_status != "APPROVED":
            raise DocumentRedactionConflictError(
                "Policy rerun source run must be APPROVED under run review."
            )
        try:
            readiness = self._governance_store.get_readiness_projection(
                project_id=project_id,
                document_id=document_id,
                run_id=source_run.id,
            )
        except GovernanceRunNotFoundError as error:
            raise DocumentRedactionConflictError(str(error)) from error
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error
        if readiness.status != "READY":
            raise DocumentRedactionConflictError(
                "Policy rerun source run must be governance-ready."
            )
        target_policy = self._load_policy_for_redaction_rerun(
            project_id=project_id,
            policy_id=normalized_policy_id,
        )
        target_policy_hash = self._canonical_policy_rules_sha256(target_policy.rules_json)
        try:
            created_run = self._store.create_redaction_run(
                project_id=project_id,
                document_id=document_id,
                created_by=current_user.user_id,
                input_transcription_run_id=source_run.input_transcription_run_id,
                input_layout_run_id=source_run.input_layout_run_id,
                run_kind="POLICY_RERUN",
                supersedes_redaction_run_id=source_run.id,
                detectors_version=source_run.detectors_version,
                policy_snapshot_id=target_policy.id,
                policy_snapshot_json=target_policy.rules_json,
                policy_snapshot_hash=target_policy_hash,
                policy_id=target_policy.id,
                policy_family_id=target_policy.policy_family_id,
                policy_version=str(target_policy.version),
            )
        except DocumentRedactionRunConflictError as error:
            raise DocumentRedactionConflictError(str(error)) from error

        try:
            self._materialize_redaction_findings_for_run(
                project_id=project_id,
                document_id=document_id,
                run=created_run,
            )
        except Exception as error:  # noqa: BLE001
            try:
                self._store.cancel_redaction_run(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=created_run.id,
                    canceled_by=current_user.user_id,
                )
            except Exception:  # noqa: BLE001
                pass
            raise DocumentStoreUnavailableError(
                "Policy rerun detection pipeline failed."
            ) from error

        hydrated_run = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=created_run.id,
        )
        self._refresh_redaction_run_preview_outputs(
            project_id=project_id,
            document_id=document_id,
            run=hydrated_run,
        )
        return hydrated_run

    def cancel_redaction_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunRecord:
        self._require_redaction_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        try:
            return self._store.cancel_redaction_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                canceled_by=current_user.user_id,
            )
        except DocumentNotFoundError as error:
            raise DocumentRedactionRunNotFoundError(str(error)) from error
        except DocumentRedactionRunConflictError as error:
            raise DocumentRedactionConflictError(str(error)) from error

    def activate_redaction_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentRedactionProjectionRecord:
        self._require_redaction_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        try:
            return self._store.activate_redaction_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except DocumentNotFoundError as error:
            raise DocumentRedactionRunNotFoundError(str(error)) from error
        except DocumentRedactionRunConflictError as error:
            raise DocumentRedactionConflictError(str(error)) from error

    def get_redaction_run_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunReviewRecord:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        review = self._store.get_redaction_run_review(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if review is None:
            raise DocumentRedactionRunNotFoundError("Redaction run review not found.")
        return review

    def start_redaction_run_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunReviewRecord:
        self._require_redaction_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        page_reviews = self._list_all_redaction_page_reviews(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if not page_reviews:
            raise DocumentRedactionConflictError(
                "Run review cannot start before page-review projections exist."
            )
        if any(item.review_status == "NOT_STARTED" for item in page_reviews):
            raise DocumentRedactionConflictError(
                "Run review start requires every page to be reviewed at least once."
            )
        try:
            return self._store.start_redaction_run_review(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                actor_user_id=current_user.user_id,
            )
        except DocumentNotFoundError as error:
            raise DocumentRedactionRunNotFoundError(str(error)) from error
        except DocumentRedactionRunConflictError as error:
            raise DocumentRedactionConflictError(str(error)) from error

    def complete_redaction_run_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        review_status: str,
        reason: str | None = None,
    ) -> RedactionRunReviewRecord:
        self._require_redaction_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_status = self._normalize_redaction_run_review_status(review_status)
        normalized_reason = (
            reason.strip() if isinstance(reason, str) and reason.strip() else None
        )
        if normalized_reason is not None and len(normalized_reason) > 600:
            raise DocumentValidationError("reason must be 600 characters or fewer.")
        try:
            review = self._store.complete_redaction_run_review(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                actor_user_id=current_user.user_id,
                review_status=normalized_status,
                reason=normalized_reason,
            )
        except DocumentNotFoundError as error:
            raise DocumentRedactionRunNotFoundError(str(error)) from error
        except DocumentRedactionRunConflictError as error:
            raise DocumentRedactionConflictError(str(error)) from error
        if normalized_status == "APPROVED":
            run = self._load_redaction_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            try:
                self._persist_redaction_approved_snapshot_artifact(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    review=review,
                )
                self._refresh_redaction_reviewed_outputs_from_approved_snapshot(
                    current_user=current_user,
                    project_id=project_id,
                    document_id=document_id,
                    run=run,
                    review=review,
                )
            except Exception as error:  # noqa: BLE001
                failure_reason = f"Reviewed output generation failed: {error}"
                if len(failure_reason) > 600:
                    failure_reason = failure_reason[:600]
                try:
                    self._store.set_redaction_run_output_status(
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                        status="FAILED",
                        failure_reason=failure_reason,
                        actor_user_id=current_user.user_id,
                    )
                except Exception:  # noqa: BLE001
                    pass
                raise DocumentStoreUnavailableError(
                    "Redaction reviewed output generation failed."
                ) from error
            refreshed_review = self._store.get_redaction_run_review(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            if refreshed_review is not None:
                return refreshed_review
        return review

    def list_redaction_run_page_findings(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        category: str | None = None,
        unresolved_only: bool = False,
        direct_identifiers_only: bool = False,
    ) -> list[RedactionFindingRecord]:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        normalized_category = (
            category.strip() if isinstance(category, str) and category.strip() else None
        )
        rows = self._list_all_redaction_findings(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            category=normalized_category,
            unresolved_only=unresolved_only,
        )
        if direct_identifiers_only:
            rows = [row for row in rows if self._is_direct_identifier_category(row.category)]
        return rows

    def get_redaction_run_page_finding(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        finding_id: str,
    ) -> RedactionFindingRecord:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        finding = self._store.get_redaction_finding(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            finding_id=finding_id,
        )
        if finding is None or finding.page_id != page_id:
            raise DocumentPageNotFoundError("Redaction finding not found.")
        return finding

    def list_redaction_area_masks(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[RedactionAreaMaskRecord]:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        return self._store.list_redaction_area_masks(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )

    def get_redaction_area_mask_by_id(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        mask_id: str,
    ) -> RedactionAreaMaskRecord:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        mask = self._store.get_redaction_area_mask_by_id(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            mask_id=mask_id,
        )
        if mask is None:
            raise DocumentPageNotFoundError("Redaction area mask not found.")
        return mask

    def get_redaction_run_page_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> RedactionPageReviewRecord:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        review = self._store.get_redaction_page_review(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if review is None:
            raise DocumentPageNotFoundError("Redaction page review not found.")
        return review

    def list_redaction_run_pages(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        category: str | None = None,
        unresolved_only: bool = False,
        direct_identifiers_only: bool = False,
        cursor: int = 0,
        page_size: int = 200,
    ) -> tuple[list[DocumentRedactionRunPageSnapshot], int | None]:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        if cursor < 0:
            raise DocumentValidationError("Cursor must be zero or greater.")
        if page_size < 1 or page_size > 500:
            raise DocumentValidationError("Page size must be between 1 and 500.")
        run = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        pages = self._store.list_document_pages(
            project_id=project_id,
            document_id=document_id,
        )
        findings = self._list_all_redaction_findings(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            category=category,
            unresolved_only=unresolved_only,
        )
        if direct_identifiers_only:
            findings = [row for row in findings if self._is_direct_identifier_category(row.category)]
        findings_by_page: dict[str, list[RedactionFindingRecord]] = {}
        for finding in findings:
            findings_by_page.setdefault(finding.page_id, []).append(finding)
        page_reviews = self._list_all_redaction_page_reviews(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
        )
        reviews_by_page = {row.page_id: row for row in page_reviews}
        outputs = self._store.list_redaction_outputs(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
        )
        outputs_by_page = {row.page_id: row for row in outputs}
        rows: list[DocumentRedactionRunPageSnapshot] = []
        for page in pages:
            page_findings = findings_by_page.get(page.id, [])
            unresolved_count = sum(
                1
                for item in page_findings
                if self._is_unresolved_redaction_decision(item.decision_status)
            )
            review = reviews_by_page.get(page.id)
            output = outputs_by_page.get(page.id)
            if unresolved_only and unresolved_count <= 0:
                continue
            rows.append(
                DocumentRedactionRunPageSnapshot(
                    run_id=run.id,
                    page_id=page.id,
                    page_index=page.page_index,
                    finding_count=len(page_findings),
                    unresolved_count=unresolved_count,
                    review_status=review.review_status if review is not None else "NOT_STARTED",
                    review_etag=review.review_etag if review is not None else "",
                    requires_second_review=(
                        review.requires_second_review if review is not None else False
                    ),
                    second_review_status=(
                        review.second_review_status if review is not None else "NOT_REQUIRED"
                    ),
                    second_reviewed_by=(
                        review.second_reviewed_by if review is not None else None
                    ),
                    second_reviewed_at=(
                        review.second_reviewed_at if review is not None else None
                    ),
                    last_reviewed_by=review.first_reviewed_by if review is not None else None,
                    last_reviewed_at=review.first_reviewed_at if review is not None else None,
                    preview_status=output.status if output is not None else None,
                    top_findings=tuple(page_findings[:5]),
                )
            )
        ordered_rows = sorted(rows, key=lambda item: (item.page_index, item.page_id))
        start = max(0, cursor)
        end = start + page_size
        next_cursor = end if end < len(ordered_rows) else None
        return ordered_rows[start:end], next_cursor

    def update_redaction_finding_decision(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        finding_id: str,
        expected_decision_etag: str,
        decision_status: str,
        reason: str | None = None,
        action_type: str | None = None,
    ) -> RedactionFindingRecord:
        self._require_redaction_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_decision_etag = (
            expected_decision_etag.strip()
            if isinstance(expected_decision_etag, str)
            else ""
        )
        if not normalized_decision_etag:
            raise DocumentValidationError("decisionEtag is required.")
        normalized_decision_status = self._normalize_redaction_decision_status(
            decision_status
        )
        normalized_reason = (
            reason.strip() if isinstance(reason, str) and reason.strip() else None
        )
        if normalized_reason is not None and len(normalized_reason) > 600:
            raise DocumentValidationError("reason must be 600 characters or fewer.")
        normalized_action_type = self._normalize_redaction_action_type(action_type)
        run = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        try:
            finding = self._store.update_redaction_finding_decision(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                finding_id=finding_id,
                expected_decision_etag=normalized_decision_etag,
                to_decision_status=normalized_decision_status,
                actor_user_id=current_user.user_id,
                reason=normalized_reason,
                action_type=normalized_action_type,
            )
        except DocumentNotFoundError as error:
            raise DocumentPageNotFoundError(str(error)) from error
        except DocumentRedactionRunConflictError as error:
            raise DocumentRedactionConflictError(str(error)) from error
        self._refresh_redaction_run_preview_outputs(
            project_id=project_id,
            document_id=document_id,
            run=run,
            page_id=finding.page_id,
        )
        return finding

    def update_redaction_page_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        expected_review_etag: str,
        review_status: str,
        reason: str | None = None,
    ) -> RedactionPageReviewRecord:
        self._require_redaction_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_review_etag = (
            expected_review_etag.strip()
            if isinstance(expected_review_etag, str)
            else ""
        )
        if not normalized_review_etag:
            raise DocumentValidationError("reviewEtag is required.")
        normalized_review_status = self._normalize_redaction_page_review_status(
            review_status
        )
        normalized_reason = (
            reason.strip() if isinstance(reason, str) and reason.strip() else None
        )
        if normalized_reason is not None and len(normalized_reason) > 600:
            raise DocumentValidationError("reason must be 600 characters or fewer.")
        try:
            return self._store.update_redaction_page_review(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                expected_review_etag=normalized_review_etag,
                review_status=normalized_review_status,
                actor_user_id=current_user.user_id,
                reason=normalized_reason,
            )
        except DocumentNotFoundError as error:
            raise DocumentPageNotFoundError(str(error)) from error
        except DocumentRedactionRunConflictError as error:
            raise DocumentRedactionConflictError(str(error)) from error

    def revise_redaction_area_mask(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        mask_id: str,
        expected_version_etag: str,
        geometry_json: dict[str, object],
        mask_reason: str,
        finding_id: str | None = None,
        expected_finding_decision_etag: str | None = None,
    ) -> tuple[RedactionAreaMaskRecord, RedactionFindingRecord | None]:
        self._require_redaction_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_version_etag = (
            expected_version_etag.strip()
            if isinstance(expected_version_etag, str)
            else ""
        )
        if not normalized_version_etag:
            raise DocumentValidationError("versionEtag is required.")
        normalized_mask_reason = mask_reason.strip() if isinstance(mask_reason, str) else ""
        if not normalized_mask_reason:
            raise DocumentValidationError("maskReason is required.")
        if len(normalized_mask_reason) > 600:
            raise DocumentValidationError("maskReason must be 600 characters or fewer.")
        normalized_finding_id = self._normalize_redaction_reference(
            finding_id,
            field_name="findingId",
            max_length=160,
        )
        normalized_finding_etag = self._normalize_redaction_reference(
            expected_finding_decision_etag,
            field_name="findingDecisionEtag",
            max_length=128,
        )
        run = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        try:
            area_mask, finding = self._store.revise_redaction_area_mask(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                mask_id=mask_id,
                expected_version_etag=normalized_version_etag,
                geometry_json=dict(geometry_json),
                mask_reason=normalized_mask_reason,
                actor_user_id=current_user.user_id,
                finding_id=normalized_finding_id,
                expected_finding_decision_etag=normalized_finding_etag,
            )
        except DocumentNotFoundError as error:
            raise DocumentPageNotFoundError(str(error)) from error
        except DocumentRedactionRunConflictError as error:
            raise DocumentRedactionConflictError(str(error)) from error
        self._refresh_redaction_run_preview_outputs(
            project_id=project_id,
            document_id=document_id,
            run=run,
            page_id=page_id,
        )
        return area_mask, finding

    def create_redaction_area_mask(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        geometry_json: dict[str, object],
        mask_reason: str,
        finding_id: str | None = None,
        expected_finding_decision_etag: str | None = None,
    ) -> tuple[RedactionAreaMaskRecord, RedactionFindingRecord | None]:
        self._require_redaction_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_mask_reason = mask_reason.strip() if isinstance(mask_reason, str) else ""
        if not normalized_mask_reason:
            raise DocumentValidationError("maskReason is required.")
        if len(normalized_mask_reason) > 600:
            raise DocumentValidationError("maskReason must be 600 characters or fewer.")
        normalized_finding_id = self._normalize_redaction_reference(
            finding_id,
            field_name="findingId",
            max_length=160,
        )
        normalized_finding_etag = self._normalize_redaction_reference(
            expected_finding_decision_etag,
            field_name="findingDecisionEtag",
            max_length=128,
        )
        run = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        try:
            area_mask, finding = self._store.create_redaction_area_mask(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                geometry_json=dict(geometry_json),
                mask_reason=normalized_mask_reason,
                actor_user_id=current_user.user_id,
                finding_id=normalized_finding_id,
                expected_finding_decision_etag=normalized_finding_etag,
            )
        except DocumentNotFoundError as error:
            raise DocumentPageNotFoundError(str(error)) from error
        except DocumentRedactionRunConflictError as error:
            raise DocumentRedactionConflictError(str(error)) from error
        self._refresh_redaction_run_preview_outputs(
            project_id=project_id,
            document_id=document_id,
            run=run,
            page_id=page_id,
        )
        return area_mask, finding

    def revise_redaction_area_mask_by_id(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        mask_id: str,
        expected_version_etag: str,
        geometry_json: dict[str, object],
        mask_reason: str,
        finding_id: str | None = None,
        expected_finding_decision_etag: str | None = None,
    ) -> tuple[RedactionAreaMaskRecord, RedactionFindingRecord | None]:
        mask = self.get_redaction_area_mask_by_id(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            mask_id=mask_id,
        )
        return self.revise_redaction_area_mask(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=mask.page_id,
            mask_id=mask_id,
            expected_version_etag=expected_version_etag,
            geometry_json=geometry_json,
            mask_reason=mask_reason,
            finding_id=finding_id,
            expected_finding_decision_etag=expected_finding_decision_etag,
        )

    def list_redaction_run_page_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[DocumentRedactionRunTimelineEventSnapshot]:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        decision_events = self._store.list_redaction_decision_events(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        page_review_events = self._store.list_redaction_page_review_events(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        timeline: list[DocumentRedactionRunTimelineEventSnapshot] = []
        for event in decision_events:
            timeline.append(
                DocumentRedactionRunTimelineEventSnapshot(
                    source_table="redaction_decision_events",
                    source_table_precedence=0,
                    event_id=event.id,
                    run_id=event.run_id,
                    page_id=event.page_id,
                    finding_id=event.finding_id,
                    event_type=event.action_type,
                    actor_user_id=event.actor_user_id,
                    reason=event.reason,
                    created_at=event.created_at,
                    details_json={
                        "fromDecisionStatus": event.from_decision_status,
                        "toDecisionStatus": event.to_decision_status,
                        "actionType": event.action_type,
                        "areaMaskId": event.area_mask_id,
                    },
                )
            )
        for event in page_review_events:
            timeline.append(
                DocumentRedactionRunTimelineEventSnapshot(
                    source_table="redaction_page_review_events",
                    source_table_precedence=1,
                    event_id=event.id,
                    run_id=event.run_id,
                    page_id=event.page_id,
                    finding_id=None,
                    event_type=event.event_type,
                    actor_user_id=event.actor_user_id,
                    reason=event.reason,
                    created_at=event.created_at,
                    details_json={},
                )
            )
        return sorted(
            timeline,
            key=lambda item: (
                item.created_at,
                item.source_table_precedence,
                item.event_id,
            ),
        )

    def list_redaction_run_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> list[DocumentRedactionRunTimelineEventSnapshot]:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        decision_events = self._store.list_redaction_decision_events(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        page_review_events = self._store.list_redaction_page_review_events(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        run_review_events = self._store.list_redaction_run_review_events(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        run_output_events = self._store.list_redaction_run_output_events(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        timeline: list[DocumentRedactionRunTimelineEventSnapshot] = []
        for event in decision_events:
            timeline.append(
                DocumentRedactionRunTimelineEventSnapshot(
                    source_table="redaction_decision_events",
                    source_table_precedence=0,
                    event_id=event.id,
                    run_id=event.run_id,
                    page_id=event.page_id,
                    finding_id=event.finding_id,
                    event_type=event.action_type,
                    actor_user_id=event.actor_user_id,
                    reason=event.reason,
                    created_at=event.created_at,
                    details_json={
                        "fromDecisionStatus": event.from_decision_status,
                        "toDecisionStatus": event.to_decision_status,
                        "actionType": event.action_type,
                        "areaMaskId": event.area_mask_id,
                    },
                )
            )
        for event in page_review_events:
            timeline.append(
                DocumentRedactionRunTimelineEventSnapshot(
                    source_table="redaction_page_review_events",
                    source_table_precedence=1,
                    event_id=event.id,
                    run_id=event.run_id,
                    page_id=event.page_id,
                    finding_id=None,
                    event_type=event.event_type,
                    actor_user_id=event.actor_user_id,
                    reason=event.reason,
                    created_at=event.created_at,
                    details_json={},
                )
            )
        for event in run_review_events:
            timeline.append(
                DocumentRedactionRunTimelineEventSnapshot(
                    source_table="redaction_run_review_events",
                    source_table_precedence=2,
                    event_id=event.id,
                    run_id=event.run_id,
                    page_id=None,
                    finding_id=None,
                    event_type=event.event_type,
                    actor_user_id=event.actor_user_id,
                    reason=event.reason,
                    created_at=event.created_at,
                    details_json={},
                )
            )
        for event in run_output_events:
            timeline.append(
                DocumentRedactionRunTimelineEventSnapshot(
                    source_table="redaction_run_output_events",
                    source_table_precedence=3,
                    event_id=event.id,
                    run_id=event.run_id,
                    page_id=None,
                    finding_id=None,
                    event_type=event.event_type,
                    actor_user_id=event.actor_user_id,
                    reason=event.reason,
                    created_at=event.created_at,
                    details_json={
                        "fromStatus": event.from_status,
                        "toStatus": event.to_status,
                    },
                )
            )
        return sorted(
            timeline,
            key=lambda item: (
                item.created_at,
                item.source_table_precedence,
                item.event_id,
            ),
        )

    def get_redaction_page_preview_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> DocumentRedactionPreviewStatusSnapshot:
        run = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        review = self._store.get_redaction_run_review(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
        )
        if review is None:
            raise DocumentRedactionRunNotFoundError("Redaction run review not found.")
        self._require_redaction_reviewed_output_read_access(
            current_user=current_user,
            project_id=project_id,
            review_status=review.review_status,
        )
        output = self._store.get_redaction_output(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if output is None:
            raise DocumentPageNotFoundError("Redaction preview status was not found.")
        run_output = self._store.get_redaction_run_output(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        readiness_state: RedactionRunOutputReadinessState | None = None
        downstream_ready = False
        if run_output is not None:
            readiness_state = self._derive_redaction_run_output_readiness_state(
                review_status=review.review_status,
                run_output=run_output,
            )
            downstream_ready = readiness_state == "OUTPUT_READY"
        return DocumentRedactionPreviewStatusSnapshot(
            run_id=run_id,
            page_id=page_id,
            status=output.status,
            preview_sha256=output.preview_sha256,
            generated_at=output.generated_at,
            failure_reason=output.failure_reason,
            run_output_status=run_output.status if run_output is not None else None,
            run_output_manifest_sha256=(
                run_output.output_manifest_sha256 if run_output is not None else None
            ),
            run_output_readiness_state=readiness_state,
            downstream_ready=downstream_ready,
        )

    def read_redaction_page_preview(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> DocumentRedactionPreviewAsset:
        status_snapshot = self.get_redaction_page_preview_status(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if status_snapshot.status != "READY":
            raise DocumentPageAssetNotReadyError(
                "Safeguarded preview is not ready for this page."
            )
        output = self._store.get_redaction_output(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if (
            output is None
            or not isinstance(output.safeguarded_preview_key, str)
            or not output.safeguarded_preview_key.strip()
        ):
            raise DocumentPageAssetNotReadyError(
                "Safeguarded preview artifact is not available for this page."
            )
        try:
            preview_bytes = self._storage.read_object_bytes(output.safeguarded_preview_key)
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError(
                "Safeguarded preview artifact could not be loaded."
            ) from error
        return DocumentRedactionPreviewAsset(
            payload=preview_bytes,
            media_type=_REDACTION_PREVIEW_MEDIA_TYPE,
            etag_seed=status_snapshot.preview_sha256,
            cache_control=_PAGE_ASSET_CACHE_CONTROL,
        )

    def get_redaction_run_output(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentRedactionRunOutputSnapshot:
        run = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        review = self._store.get_redaction_run_review(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
        )
        if review is None:
            raise DocumentRedactionRunNotFoundError("Redaction run review not found.")
        self._require_redaction_reviewed_output_read_access(
            current_user=current_user,
            project_id=project_id,
            review_status=review.review_status,
        )
        output = self._store.get_redaction_run_output(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if output is None:
            raise DocumentRedactionRunNotFoundError("Redaction run output not found.")
        readiness_state = self._derive_redaction_run_output_readiness_state(
            review_status=review.review_status,
            run_output=output,
        )
        return DocumentRedactionRunOutputSnapshot(
            run_output=output,
            review_status=review.review_status,
            readiness_state=readiness_state,
            downstream_ready=readiness_state == "OUTPUT_READY",
        )

    def get_redaction_run_output_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentRedactionRunOutputSnapshot:
        return self.get_redaction_run_output(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )

    def get_redaction_overview(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentRedactionOverviewSnapshot:
        self._require_redaction_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        document = self._load_redaction_document(project_id=project_id, document_id=document_id)
        projection = self._store.get_redaction_projection(
            project_id=project_id,
            document_id=document_id,
        )
        active_run = self._store.get_active_redaction_run(
            project_id=project_id,
            document_id=document_id,
        )
        all_runs = self._list_all_redaction_runs(
            project_id=project_id,
            document_id=document_id,
        )
        latest_run = all_runs[0] if all_runs else None
        page_count = len(
            self._store.list_document_pages(
                project_id=project_id,
                document_id=document_id,
            )
        )
        findings_by_category: dict[str, int] = {}
        unresolved_findings = 0
        auto_applied_findings = 0
        needs_review_findings = 0
        overridden_findings = 0
        pages_blocked_for_review = 0
        preview_ready_pages = 0
        preview_total_pages = 0
        preview_failed_pages = 0

        if active_run is not None:
            findings = self._list_all_redaction_findings(
                project_id=project_id,
                document_id=document_id,
                run_id=active_run.id,
            )
            for finding in findings:
                findings_by_category[finding.category] = (
                    findings_by_category.get(finding.category, 0) + 1
                )
                if finding.decision_status == "AUTO_APPLIED":
                    auto_applied_findings += 1
                elif finding.decision_status == "NEEDS_REVIEW":
                    needs_review_findings += 1
                elif finding.decision_status == "OVERRIDDEN":
                    overridden_findings += 1
                if self._is_unresolved_redaction_decision(finding.decision_status):
                    unresolved_findings += 1
            page_reviews = self._list_all_redaction_page_reviews(
                project_id=project_id,
                document_id=document_id,
                run_id=active_run.id,
            )
            pages_blocked_for_review = sum(
                1
                for review in page_reviews
                if review.review_status != "APPROVED"
                or (
                    review.requires_second_review
                    and review.second_review_status != "APPROVED"
                )
            )
            outputs = self._store.list_redaction_outputs(
                project_id=project_id,
                document_id=document_id,
                run_id=active_run.id,
            )
            preview_total_pages = len(outputs)
            preview_ready_pages = sum(1 for output in outputs if output.status == "READY")
            preview_failed_pages = sum(1 for output in outputs if output.status == "FAILED")

        return DocumentRedactionOverviewSnapshot(
            document=document,
            projection=projection,
            active_run=active_run,
            latest_run=latest_run,
            total_runs=len(all_runs),
            page_count=page_count,
            findings_by_category=findings_by_category,
            unresolved_findings=unresolved_findings,
            auto_applied_findings=auto_applied_findings,
            needs_review_findings=needs_review_findings,
            overridden_findings=overridden_findings,
            pages_blocked_for_review=pages_blocked_for_review,
            preview_ready_pages=preview_ready_pages,
            preview_total_pages=preview_total_pages,
            preview_failed_pages=preview_failed_pages,
        )

    def compare_redaction_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        base_run_id: str,
        candidate_run_id: str,
    ) -> DocumentRedactionCompareSnapshot:
        self._require_redaction_compare_access(
            current_user=current_user,
            project_id=project_id,
        )
        if base_run_id == candidate_run_id:
            raise DocumentValidationError(
                "baseRunId and candidateRunId must reference different runs."
            )
        document = self._load_redaction_document(project_id=project_id, document_id=document_id)
        base_run = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=base_run_id,
        )
        candidate_run = self._load_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=candidate_run_id,
        )
        pages = self._store.list_document_pages(
            project_id=project_id,
            document_id=document_id,
        )
        base_findings = self._list_all_redaction_findings(
            project_id=project_id,
            document_id=document_id,
            run_id=base_run.id,
        )
        candidate_findings = self._list_all_redaction_findings(
            project_id=project_id,
            document_id=document_id,
            run_id=candidate_run.id,
        )
        base_reviews = {
            review.page_id: review
            for review in self._list_all_redaction_page_reviews(
                project_id=project_id,
                document_id=document_id,
                run_id=base_run.id,
            )
        }
        candidate_reviews = {
            review.page_id: review
            for review in self._list_all_redaction_page_reviews(
                project_id=project_id,
                document_id=document_id,
                run_id=candidate_run.id,
            )
        }
        base_outputs = {
            output.page_id: output
            for output in self._store.list_redaction_outputs(
                project_id=project_id,
                document_id=document_id,
                run_id=base_run.id,
            )
        }
        candidate_outputs = {
            output.page_id: output
            for output in self._store.list_redaction_outputs(
                project_id=project_id,
                document_id=document_id,
                run_id=candidate_run.id,
            )
        }
        base_decision_events = self._store.list_redaction_decision_events(
            project_id=project_id,
            document_id=document_id,
            run_id=base_run.id,
        )
        candidate_decision_events = self._store.list_redaction_decision_events(
            project_id=project_id,
            document_id=document_id,
            run_id=candidate_run.id,
        )
        base_action_by_finding_id: dict[str, RedactionDecisionActionType] = {}
        candidate_action_by_finding_id: dict[str, RedactionDecisionActionType] = {}
        for event in base_decision_events:
            base_action_by_finding_id[event.finding_id] = event.action_type
        for event in candidate_decision_events:
            candidate_action_by_finding_id[event.finding_id] = event.action_type
        base_findings_by_page: dict[str, list[RedactionFindingRecord]] = {}
        candidate_findings_by_page: dict[str, list[RedactionFindingRecord]] = {}
        for row in base_findings:
            base_findings_by_page.setdefault(row.page_id, []).append(row)
        for row in candidate_findings:
            candidate_findings_by_page.setdefault(row.page_id, []).append(row)

        changed_page_count = 0
        changed_decision_count = 0
        changed_action_count = 0
        page_snapshots: list[DocumentRedactionComparePageSnapshot] = []
        for page in pages:
            page_base = base_findings_by_page.get(page.id, [])
            page_candidate = candidate_findings_by_page.get(page.id, [])
            base_decision_counts: dict[RedactionDecisionStatus, int] = {}
            candidate_decision_counts: dict[RedactionDecisionStatus, int] = {}
            base_action_counts: dict[RedactionDecisionActionType, int] = {}
            candidate_action_counts: dict[RedactionDecisionActionType, int] = {}
            for finding in page_base:
                base_decision_counts[finding.decision_status] = (
                    base_decision_counts.get(finding.decision_status, 0) + 1
                )
                action_type = base_action_by_finding_id.get(finding.id, "MASK")
                base_action_counts[action_type] = base_action_counts.get(action_type, 0) + 1
            for finding in page_candidate:
                candidate_decision_counts[finding.decision_status] = (
                    candidate_decision_counts.get(finding.decision_status, 0) + 1
                )
                action_type = candidate_action_by_finding_id.get(finding.id, "MASK")
                candidate_action_counts[action_type] = (
                    candidate_action_counts.get(action_type, 0) + 1
                )
            page_changed_decision_count = 0
            for status_key in set(base_decision_counts) | set(candidate_decision_counts):
                page_changed_decision_count += abs(
                    base_decision_counts.get(status_key, 0)
                    - candidate_decision_counts.get(status_key, 0)
                )
            page_changed_action_count = 0
            for action_key in {"MASK", "PSEUDONYMIZE", "GENERALIZE"}:
                page_changed_action_count += abs(
                    base_action_counts.get(action_key, 0)
                    - candidate_action_counts.get(action_key, 0)
                )
            decision_status_deltas: dict[RedactionDecisionStatus, int] = {}
            for status_key in {
                "AUTO_APPLIED",
                "NEEDS_REVIEW",
                "APPROVED",
                "OVERRIDDEN",
                "FALSE_POSITIVE",
            }:
                delta = candidate_decision_counts.get(status_key, 0) - base_decision_counts.get(
                    status_key, 0
                )
                decision_status_deltas[status_key] = delta
            action_type_deltas: dict[RedactionDecisionActionType, int] = {}
            for action_key in {"MASK", "PSEUDONYMIZE", "GENERALIZE"}:
                action_type_deltas[action_key] = (
                    candidate_action_counts.get(action_key, 0)
                    - base_action_counts.get(action_key, 0)
                )
            base_review = base_reviews.get(page.id)
            candidate_review = candidate_reviews.get(page.id)
            changed_review_status = (
                (base_review.review_status if base_review is not None else None)
                != (candidate_review.review_status if candidate_review is not None else None)
            )
            changed_second_review_status = (
                (base_review.second_review_status if base_review is not None else None)
                != (
                    candidate_review.second_review_status
                    if candidate_review is not None
                    else None
                )
            )
            base_preview_status = base_outputs.get(page.id).status if base_outputs.get(page.id) else None
            candidate_preview_status = (
                candidate_outputs.get(page.id).status
                if candidate_outputs.get(page.id)
                else None
            )
            preview_ready_delta = int(candidate_preview_status == "READY") - int(
                base_preview_status == "READY"
            )
            action_compare_state: Literal["AVAILABLE", "NOT_YET_AVAILABLE"] = (
                "AVAILABLE"
                if base_preview_status == "READY" and candidate_preview_status == "READY"
                else "NOT_YET_AVAILABLE"
            )
            if (
                page_changed_decision_count > 0
                or page_changed_action_count > 0
                or changed_review_status
                or changed_second_review_status
                or (
                    base_preview_status != candidate_preview_status
                )
            ):
                changed_page_count += 1
            changed_decision_count += page_changed_decision_count
            changed_action_count += page_changed_action_count
            page_snapshots.append(
                DocumentRedactionComparePageSnapshot(
                    page_id=page.id,
                    page_index=page.page_index,
                    base_finding_count=len(page_base),
                    candidate_finding_count=len(page_candidate),
                    changed_decision_count=page_changed_decision_count,
                    changed_action_count=page_changed_action_count,
                    base_decision_counts=base_decision_counts,
                    candidate_decision_counts=candidate_decision_counts,
                    decision_status_deltas=decision_status_deltas,
                    base_action_counts=base_action_counts,
                    candidate_action_counts=candidate_action_counts,
                    action_type_deltas=action_type_deltas,
                    action_compare_state=action_compare_state,
                    changed_review_status=changed_review_status,
                    changed_second_review_status=changed_second_review_status,
                    base_review=base_review,
                    candidate_review=candidate_review,
                    base_preview_status=base_preview_status,
                    candidate_preview_status=candidate_preview_status,
                    preview_ready_delta=preview_ready_delta,
                )
            )
        has_policy_rerun_context = (
            base_run.run_kind == "POLICY_RERUN"
            or candidate_run.run_kind == "POLICY_RERUN"
            or candidate_run.supersedes_redaction_run_id == base_run.id
            or base_run.supersedes_redaction_run_id == candidate_run.id
        )
        compare_action_state: Literal["AVAILABLE", "NOT_YET_RERUN", "NOT_YET_AVAILABLE"]
        if not has_policy_rerun_context:
            compare_action_state = "NOT_YET_RERUN"
        elif any(item.action_compare_state != "AVAILABLE" for item in page_snapshots):
            compare_action_state = "NOT_YET_AVAILABLE"
        else:
            compare_action_state = "AVAILABLE"

        candidate_policy_status: str | None = None
        comparison_only_candidate = False
        if isinstance(candidate_run.policy_id, str) and candidate_run.policy_id:
            try:
                candidate_policy = self._policy_store.get_policy(
                    project_id=project_id,
                    policy_id=candidate_run.policy_id,
                )
            except PolicyStoreUnavailableError as error:
                raise DocumentStoreUnavailableError(
                    "Policy lookup for compare context failed."
                ) from error
            if candidate_policy is not None:
                candidate_policy_status = candidate_policy.status
                comparison_only_candidate = candidate_policy.status == "DRAFT"
        pre_activation_warnings = self._build_policy_pre_activation_warnings(
            policy_snapshot_json=candidate_run.policy_snapshot_json
        )

        return DocumentRedactionCompareSnapshot(
            document=document,
            base_run=base_run,
            candidate_run=candidate_run,
            pages=tuple(sorted(page_snapshots, key=lambda item: (item.page_index, item.page_id))),
            changed_page_count=changed_page_count,
            changed_decision_count=changed_decision_count,
            changed_action_count=changed_action_count,
            compare_action_state=compare_action_state,
            candidate_policy_status=candidate_policy_status,
            comparison_only_candidate=comparison_only_candidate,
            pre_activation_warnings=pre_activation_warnings,
        )

    def _raise_governance_lookup_error(
        self,
        *,
        error: GovernanceRunNotFoundError,
    ) -> None:
        message = str(error)
        if "Document not found" in message:
            raise DocumentNotFoundError(message) from error
        raise DocumentGovernanceRunNotFoundError(message) from error

    def _resolve_governance_active_run_id(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> str | None:
        projection = self._store.get_redaction_projection(
            project_id=project_id,
            document_id=document_id,
        )
        if projection is None:
            return None
        return projection.active_redaction_run_id

    @staticmethod
    def _truncate_governance_failure_reason(reason: str) -> str:
        message = reason.strip() or "Governance operation failed."
        if len(message) > 600:
            return message[:600]
        return message

    @staticmethod
    def _resolve_governance_ledger_status(
        *,
        latest_attempt: RedactionEvidenceLedgerRecord | None,
    ) -> Literal["UNAVAILABLE", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]:
        if latest_attempt is None:
            return "UNAVAILABLE"
        return latest_attempt.status

    def _load_governance_ledger_payload(
        self,
        *,
        run_id: str,
        latest_attempt: RedactionEvidenceLedgerRecord | None,
    ) -> tuple[dict[str, object] | None, str | None, bool]:
        if (
            latest_attempt is None
            or latest_attempt.status != "SUCCEEDED"
            or not isinstance(latest_attempt.ledger_key, str)
            or not latest_attempt.ledger_key.strip()
        ):
            return None, None, False
        try:
            payload_bytes = self._storage.read_object_bytes(latest_attempt.ledger_key)
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError("Governance ledger artifact could not be loaded.") from error
        stream_sha256 = self._sha256_hex(payload_bytes)
        expected_sha256 = (
            latest_attempt.ledger_sha256.strip()
            if isinstance(latest_attempt.ledger_sha256, str)
            and latest_attempt.ledger_sha256.strip()
            else None
        )
        hash_matches = expected_sha256 == stream_sha256 if expected_sha256 is not None else False
        if expected_sha256 is not None and not hash_matches:
            raise DocumentStoreUnavailableError("Governance ledger artifact hash mismatch.")
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DocumentStoreUnavailableError("Governance ledger artifact payload is invalid JSON.") from error
        if not isinstance(payload, dict):
            raise DocumentStoreUnavailableError("Governance ledger payload is invalid.")
        payload_run_id = payload.get("runId")
        if isinstance(payload_run_id, str) and payload_run_id.strip() != run_id:
            raise DocumentStoreUnavailableError("Governance ledger run id mismatch.")
        return payload, stream_sha256, hash_matches

    @staticmethod
    def _latest_completed_verification_attempt(
        attempts: Sequence[LedgerVerificationRunRecord],
    ) -> LedgerVerificationRunRecord | None:
        for attempt in attempts:
            if attempt.status == "SUCCEEDED":
                return attempt
        return None

    @staticmethod
    def _verification_attempt_targets_ledger(
        *,
        attempt: LedgerVerificationRunRecord,
        ledger_sha256: str,
    ) -> bool:
        result_json = attempt.result_json
        if not isinstance(result_json, Mapping):
            return False
        result_sha = result_json.get("ledgerSha256")
        return isinstance(result_sha, str) and result_sha.strip() == ledger_sha256

    def _run_governance_ledger_verification(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        actor_user_id: str,
    ) -> LedgerVerificationRunRecord:
        try:
            ledger_attempts = self._governance_store.list_ledger_attempts(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except GovernanceRunNotFoundError as error:
            self._raise_governance_lookup_error(error=error)
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error
        latest_succeeded = next(
            (
                attempt
                for attempt in ledger_attempts
                if attempt.status == "SUCCEEDED"
                and isinstance(attempt.ledger_key, str)
                and attempt.ledger_key.strip()
                and isinstance(attempt.ledger_sha256, str)
                and attempt.ledger_sha256.strip()
            ),
            None,
        )
        if latest_succeeded is None:
            raise DocumentGovernanceConflictError(
                "Ledger verification requires a successful evidence-ledger attempt."
            )

        try:
            created = self._governance_store.create_ledger_verification_attempt(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                actor_user_id=actor_user_id,
            )
            running = self._governance_store.start_ledger_verification_attempt(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                verification_run_id=created.id,
            )
        except GovernanceRunNotFoundError as error:
            self._raise_governance_lookup_error(error=error)
        except GovernanceRunConflictError as error:
            raise DocumentGovernanceConflictError(str(error)) from error
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error

        try:
            assert latest_succeeded.ledger_key is not None
            assert latest_succeeded.ledger_sha256 is not None
            ledger_bytes = self._storage.read_object_bytes(latest_succeeded.ledger_key)
            stream_sha256 = self._sha256_hex(ledger_bytes)
            if stream_sha256 != latest_succeeded.ledger_sha256:
                raise DocumentStoreUnavailableError("Evidence-ledger stream hash mismatch.")
            try:
                ledger_payload = json.loads(ledger_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise DocumentStoreUnavailableError("Evidence-ledger payload is invalid JSON.") from error
            if not isinstance(ledger_payload, Mapping):
                raise DocumentStoreUnavailableError("Evidence-ledger payload is invalid.")
            verification = verify_canonical_evidence_ledger_payload(
                ledger_payload,
                expected_run_id=run_id,
                expected_snapshot_sha256=latest_succeeded.source_review_snapshot_sha256,
            )
            verification["ledgerId"] = latest_succeeded.id
            verification["ledgerSha256"] = latest_succeeded.ledger_sha256
            verification_result: Literal["VALID", "INVALID"] = (
                "VALID" if bool(verification.get("isValid")) else "INVALID"
            )
            return self._governance_store.complete_ledger_verification_attempt(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                verification_run_id=running.id,
                verification_result=verification_result,
                result_json=dict(verification),
            )
        except (DocumentStorageError, DocumentStoreUnavailableError, ValueError) as error:
            failure_reason = self._truncate_governance_failure_reason(str(error))
            try:
                self._governance_store.fail_ledger_verification_attempt(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    verification_run_id=running.id,
                    failure_reason=failure_reason,
                )
            except (GovernanceRunNotFoundError, GovernanceRunConflictError, GovernanceStoreUnavailableError):
                pass
            raise DocumentStoreUnavailableError(failure_reason) from error
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error

    def _ensure_governance_ledger_generated(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        actor_user_id: str,
    ) -> None:
        run = self._store.get_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentGovernanceRunNotFoundError("Governance run was not found in project scope.")
        review = self._store.get_redaction_run_review(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        run_output = self._store.get_redaction_run_output(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if (
            review is None
            or review.review_status != "APPROVED"
            or review.locked_at is None
            or not isinstance(review.approved_snapshot_key, str)
            or not review.approved_snapshot_key.strip()
            or not isinstance(review.approved_snapshot_sha256, str)
            or not review.approved_snapshot_sha256.strip()
            or run_output is None
            or run_output.status != "READY"
            or not isinstance(run_output.output_manifest_key, str)
            or not run_output.output_manifest_key.strip()
            or not isinstance(run_output.output_manifest_sha256, str)
            or not run_output.output_manifest_sha256.strip()
        ):
            try:
                self._governance_store.sync_governance_run(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                )
            except (GovernanceRunNotFoundError, GovernanceStoreUnavailableError):
                pass
            return

        try:
            ledger_attempts = self._governance_store.list_ledger_attempts(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            verification_attempts = self._governance_store.list_ledger_verification_runs(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except GovernanceRunNotFoundError as error:
            self._raise_governance_lookup_error(error=error)
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error

        latest_attempt = ledger_attempts[0] if ledger_attempts else None
        snapshot_matches = (
            latest_attempt is not None
            and latest_attempt.source_review_snapshot_key == review.approved_snapshot_key
            and latest_attempt.source_review_snapshot_sha256 == review.approved_snapshot_sha256
        )
        latest_completed_verification = self._latest_completed_verification_attempt(
            verification_attempts
        )
        has_completed_verification_for_latest = (
            snapshot_matches
            and latest_attempt is not None
            and latest_attempt.status == "SUCCEEDED"
            and isinstance(latest_attempt.ledger_sha256, str)
            and latest_attempt.ledger_sha256.strip()
            and latest_completed_verification is not None
            and self._verification_attempt_targets_ledger(
                attempt=latest_completed_verification,
                ledger_sha256=latest_attempt.ledger_sha256,
            )
        )
        if (
            snapshot_matches
            and latest_attempt is not None
            and latest_attempt.status == "SUCCEEDED"
            and isinstance(latest_attempt.ledger_key, str)
            and latest_attempt.ledger_key.strip()
            and isinstance(latest_attempt.ledger_sha256, str)
            and latest_attempt.ledger_sha256.strip()
            and has_completed_verification_for_latest
        ):
            return

        force_new_attempt = (
            latest_attempt is not None
            and (
                latest_attempt.status in {"FAILED", "CANCELED"}
                or not snapshot_matches
            )
        )
        try:
            started_attempt = self._governance_store.begin_ledger_attempt(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                source_review_snapshot_key=review.approved_snapshot_key,
                source_review_snapshot_sha256=review.approved_snapshot_sha256,
                actor_user_id=actor_user_id,
                force_new_attempt=force_new_attempt,
            )
        except GovernanceRunNotFoundError as error:
            self._raise_governance_lookup_error(error=error)
        except GovernanceRunConflictError as error:
            raise DocumentGovernanceConflictError(str(error)) from error
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error

        if (
            started_attempt.status == "SUCCEEDED"
            and isinstance(started_attempt.ledger_key, str)
            and started_attempt.ledger_key.strip()
            and isinstance(started_attempt.ledger_sha256, str)
            and started_attempt.ledger_sha256.strip()
        ):
            if has_completed_verification_for_latest:
                return
            try:
                self._run_governance_ledger_verification(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    actor_user_id=actor_user_id,
                )
            except (DocumentGovernanceConflictError, DocumentStoreUnavailableError):
                pass
            return

        try:
            snapshot_bytes = self._storage.read_object_bytes(review.approved_snapshot_key)
            approved_snapshot_payload = self._load_redaction_approved_snapshot_payload(
                snapshot_bytes=snapshot_bytes,
                expected_run_id=run_id,
                expected_snapshot_sha256=review.approved_snapshot_sha256,
            )
            ledger_bytes = canonical_evidence_ledger_bytes(
                run_id=run_id,
                approved_snapshot_sha256=review.approved_snapshot_sha256,
                approved_snapshot_payload=approved_snapshot_payload,
            )
            ledger_sha256 = self._sha256_hex(ledger_bytes)
            expected_ledger_key = self._storage.build_governance_evidence_ledger_key(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                ledger_sha256=ledger_sha256,
            )
            stored_ledger = self._storage.write_governance_evidence_ledger(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                ledger_sha256=ledger_sha256,
                payload=ledger_bytes,
            )
            if stored_ledger.object_key != expected_ledger_key:
                raise DocumentStoreUnavailableError("Evidence-ledger storage key mismatch.")
            self._governance_store.complete_ledger_attempt(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                ledger_id=started_attempt.id,
                ledger_key=stored_ledger.object_key,
                ledger_sha256=ledger_sha256,
                actor_user_id=actor_user_id,
            )
        except (
            DocumentStorageError,
            DocumentStoreUnavailableError,
            ValueError,
            GovernanceRunConflictError,
            GovernanceStoreUnavailableError,
        ) as error:
            failure_reason = self._truncate_governance_failure_reason(str(error))
            try:
                self._governance_store.fail_ledger_attempt(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    ledger_id=started_attempt.id,
                    failure_reason=failure_reason,
                    actor_user_id=actor_user_id,
                )
            except (GovernanceRunNotFoundError, GovernanceRunConflictError, GovernanceStoreUnavailableError):
                pass
            return

        try:
            self._run_governance_ledger_verification(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                actor_user_id=actor_user_id,
            )
        except (DocumentGovernanceConflictError, DocumentStoreUnavailableError):
            pass

    def _build_governance_run_overview_snapshot(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        actor_user_id: str,
    ) -> DocumentGovernanceRunOverviewSnapshot:
        document = self._load_redaction_document(project_id=project_id, document_id=document_id)
        active_run_id = self._resolve_governance_active_run_id(
            project_id=project_id,
            document_id=document_id,
        )
        self._ensure_governance_ledger_generated(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            actor_user_id=actor_user_id,
        )
        try:
            run = self._governance_store.get_governance_run_overview(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            readiness = self._governance_store.get_readiness_projection(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            manifest_attempts = tuple(
                self._governance_store.list_manifest_attempts(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                )
            )
            ledger_attempts = tuple(
                self._governance_store.list_ledger_attempts(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                )
            )
        except GovernanceRunNotFoundError as error:
            self._raise_governance_lookup_error(error=error)
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error
        return DocumentGovernanceRunOverviewSnapshot(
            document=document,
            active_run_id=active_run_id,
            run=run,
            readiness=readiness,
            manifest_attempts=manifest_attempts,
            ledger_attempts=ledger_attempts,
        )

    def get_governance_overview(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentGovernanceOverviewSnapshot:
        _ = self._require_governance_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        document = self._load_redaction_document(project_id=project_id, document_id=document_id)
        try:
            runs = tuple(
                self._governance_store.list_governance_runs(
                    project_id=project_id,
                    document_id=document_id,
                )
            )
        except GovernanceRunNotFoundError as error:
            self._raise_governance_lookup_error(error=error)
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error

        for row in runs:
            if row.review_status != "APPROVED":
                continue
            self._ensure_governance_ledger_generated(
                project_id=project_id,
                document_id=document_id,
                run_id=row.run_id,
                actor_user_id=current_user.user_id,
            )
        if runs:
            try:
                runs = tuple(
                    self._governance_store.list_governance_runs(
                        project_id=project_id,
                        document_id=document_id,
                    )
                )
            except GovernanceRunNotFoundError as error:
                self._raise_governance_lookup_error(error=error)
            except GovernanceStoreUnavailableError as error:
                raise DocumentStoreUnavailableError(str(error)) from error

        total_runs = len(runs)
        approved_runs = sum(1 for row in runs if row.review_status == "APPROVED")
        ready_runs = sum(1 for row in runs if row.readiness_status == "READY")
        failed_runs = sum(1 for row in runs if row.readiness_status == "FAILED")
        pending_runs = max(0, total_runs - ready_runs - failed_runs)
        latest_run = runs[0] if runs else None
        latest_ready_run = next(
            (row for row in runs if row.readiness_status == "READY"),
            None,
        )
        active_run_id = self._resolve_governance_active_run_id(
            project_id=project_id,
            document_id=document_id,
        )
        return DocumentGovernanceOverviewSnapshot(
            document=document,
            active_run_id=active_run_id,
            total_runs=total_runs,
            approved_runs=approved_runs,
            ready_runs=ready_runs,
            pending_runs=pending_runs,
            failed_runs=failed_runs,
            latest_run_id=latest_run.run_id if latest_run is not None else None,
            latest_ready_run_id=(latest_ready_run.run_id if latest_ready_run is not None else None),
            latest_run=latest_run,
            latest_ready_run=latest_ready_run,
        )

    def list_governance_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentGovernanceRunsSnapshot:
        _ = self._require_governance_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        document = self._load_redaction_document(project_id=project_id, document_id=document_id)
        active_run_id = self._resolve_governance_active_run_id(
            project_id=project_id,
            document_id=document_id,
        )
        try:
            runs = tuple(
                self._governance_store.list_governance_runs(
                    project_id=project_id,
                    document_id=document_id,
                )
            )
        except GovernanceRunNotFoundError as error:
            self._raise_governance_lookup_error(error=error)
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error
        for row in runs:
            if row.review_status != "APPROVED":
                continue
            self._ensure_governance_ledger_generated(
                project_id=project_id,
                document_id=document_id,
                run_id=row.run_id,
                actor_user_id=current_user.user_id,
            )
        if runs:
            try:
                runs = tuple(
                    self._governance_store.list_governance_runs(
                        project_id=project_id,
                        document_id=document_id,
                    )
                )
            except GovernanceRunNotFoundError as error:
                self._raise_governance_lookup_error(error=error)
            except GovernanceStoreUnavailableError as error:
                raise DocumentStoreUnavailableError(str(error)) from error
        return DocumentGovernanceRunsSnapshot(
            document=document,
            active_run_id=active_run_id,
            runs=runs,
        )

    def get_governance_run_overview(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentGovernanceRunOverviewSnapshot:
        _ = self._require_governance_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        return self._build_governance_run_overview_snapshot(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            actor_user_id=current_user.user_id,
        )

    def list_governance_run_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> tuple[DocumentGovernanceEventSnapshot, ...]:
        role = self._require_governance_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_document(project_id=project_id, document_id=document_id)
        try:
            _ = self._governance_store.get_governance_run_overview(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            events = self._governance_store.list_governance_run_events(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except GovernanceRunNotFoundError as error:
            self._raise_governance_lookup_error(error=error)
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error
        projected: list[DocumentGovernanceEventSnapshot] = []
        for event in events:
            reason = self._resolve_governance_event_reason(event=event, role=role)
            screening_safe = not self._is_governance_ledger_event(event.event_type)
            projected.append(
                DocumentGovernanceEventSnapshot(
                    id=event.id,
                    run_id=event.run_id,
                    event_type=event.event_type,
                    actor_user_id=event.actor_user_id,
                    from_status=event.from_status,
                    to_status=event.to_status,
                    reason=reason,
                    created_at=event.created_at,
                    screening_safe=screening_safe,
                )
            )
        return tuple(projected)

    @staticmethod
    def _resolve_governance_manifest_status(
        *,
        latest_attempt: RedactionManifestRecord | None,
    ) -> Literal["UNAVAILABLE", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]:
        if latest_attempt is None:
            return "UNAVAILABLE"
        return latest_attempt.status

    def _load_governance_manifest_payload(
        self,
        *,
        run_id: str,
        latest_attempt: RedactionManifestRecord | None,
    ) -> tuple[dict[str, object] | None, str | None, bool]:
        if (
            latest_attempt is None
            or latest_attempt.status != "SUCCEEDED"
            or not isinstance(latest_attempt.manifest_key, str)
            or not latest_attempt.manifest_key.strip()
        ):
            return None, None, False
        try:
            payload_bytes = self._storage.read_object_bytes(latest_attempt.manifest_key)
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError("Governance manifest artifact could not be loaded.") from error
        stream_sha256 = self._sha256_hex(payload_bytes)
        expected_sha256 = (
            latest_attempt.manifest_sha256.strip()
            if isinstance(latest_attempt.manifest_sha256, str)
            and latest_attempt.manifest_sha256.strip()
            else None
        )
        hash_matches = expected_sha256 == stream_sha256 if expected_sha256 is not None else False
        if expected_sha256 is not None and not hash_matches:
            raise DocumentStoreUnavailableError("Governance manifest artifact hash mismatch.")
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DocumentStoreUnavailableError("Governance manifest artifact payload is invalid JSON.") from error
        if not isinstance(payload, dict):
            raise DocumentStoreUnavailableError("Governance manifest payload is invalid.")
        payload_run_id = payload.get("runId")
        if isinstance(payload_run_id, str) and payload_run_id.strip() != run_id:
            raise DocumentStoreUnavailableError("Governance manifest run id mismatch.")
        return payload, stream_sha256, hash_matches

    @staticmethod
    def _resolve_manifest_access_flags(
        payload: Mapping[str, object] | None,
    ) -> tuple[bool, bool, bool]:
        if not isinstance(payload, Mapping):
            return True, False, True
        internal_only = bool(payload.get("internalOnly", True))
        export_approved = bool(payload.get("exportApproved", False))
        export_status = payload.get("exportApprovalStatus")
        not_export_approved = (
            not export_approved
            or (
                isinstance(export_status, str)
                and export_status.strip().upper() == "NOT_EXPORT_APPROVED"
            )
        )
        return internal_only, export_approved, not_export_approved

    @staticmethod
    def _parse_manifest_entry_timestamp(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        normalized = trimmed.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _filter_manifest_entries(
        *,
        entries: Sequence[Mapping[str, object]],
        category: str | None,
        page: int | None,
        review_state: str | None,
        from_timestamp: datetime | None,
        to_timestamp: datetime | None,
    ) -> list[dict[str, object]]:
        normalized_category = (
            category.strip().upper() if isinstance(category, str) and category.strip() else None
        )
        normalized_review_state = (
            review_state.strip().upper()
            if isinstance(review_state, str) and review_state.strip()
            else None
        )
        filtered: list[dict[str, object]] = []
        for item in entries:
            if normalized_category is not None:
                entry_category = item.get("category")
                if (
                    not isinstance(entry_category, str)
                    or entry_category.strip().upper() != normalized_category
                ):
                    continue
            if isinstance(page, int):
                entry_page = item.get("pageIndex")
                if not isinstance(entry_page, int) or entry_page != page:
                    continue
            if normalized_review_state is not None:
                entry_review_state = item.get("reviewState")
                if (
                    not isinstance(entry_review_state, str)
                    or entry_review_state.strip().upper() != normalized_review_state
                ):
                    continue
            if from_timestamp is not None or to_timestamp is not None:
                entry_timestamp = DocumentService._parse_manifest_entry_timestamp(
                    item.get("decisionTimestamp")
                )
                if entry_timestamp is None:
                    continue
                if from_timestamp is not None and entry_timestamp < from_timestamp:
                    continue
                if to_timestamp is not None and entry_timestamp > to_timestamp:
                    continue
            filtered.append(dict(item))
        return filtered

    def get_governance_run_manifest(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentGovernanceManifestSnapshot:
        _ = self._require_governance_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        overview = self._build_governance_run_overview_snapshot(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            actor_user_id=current_user.user_id,
        )
        latest_attempt = overview.manifest_attempts[0] if overview.manifest_attempts else None
        manifest_payload, stream_sha256, hash_matches = self._load_governance_manifest_payload(
            run_id=run_id,
            latest_attempt=latest_attempt,
        )
        internal_only, export_approved, not_export_approved = self._resolve_manifest_access_flags(
            manifest_payload
        )
        return DocumentGovernanceManifestSnapshot(
            overview=overview,
            latest_attempt=latest_attempt,
            manifest_payload=manifest_payload,
            stream_sha256=stream_sha256,
            hash_matches=hash_matches,
            internal_only=internal_only,
            export_approved=export_approved,
            not_export_approved=not_export_approved,
        )

    def get_governance_run_manifest_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentGovernanceManifestStatusSnapshot:
        manifest = self.get_governance_run_manifest(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        status = self._resolve_governance_manifest_status(
            latest_attempt=manifest.latest_attempt,
        )
        return DocumentGovernanceManifestStatusSnapshot(
            run_id=run_id,
            status=status,
            latest_attempt=manifest.latest_attempt,
            attempt_count=len(manifest.overview.manifest_attempts),
            ready_manifest_id=manifest.overview.readiness.manifest_id,
            latest_manifest_sha256=manifest.overview.readiness.last_manifest_sha256,
            generation_status=manifest.overview.readiness.generation_status,
            readiness_status=manifest.overview.readiness.status,
            updated_at=manifest.overview.readiness.updated_at,
        )

    def list_governance_run_manifest_entries(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        category: str | None = None,
        page: int | None = None,
        review_state: str | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
        cursor: int = 0,
        limit: int = 100,
    ) -> DocumentGovernanceManifestEntriesSnapshot:
        manifest = self.get_governance_run_manifest(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        status = self._resolve_governance_manifest_status(
            latest_attempt=manifest.latest_attempt,
        )
        payload_entries = (
            manifest.manifest_payload.get("entries")
            if isinstance(manifest.manifest_payload, Mapping)
            else None
        )
        entries = (
            [item for item in payload_entries if isinstance(item, Mapping)]
            if isinstance(payload_entries, Sequence)
            and not isinstance(payload_entries, (str, bytes))
            else []
        )
        filtered = self._filter_manifest_entries(
            entries=entries,
            category=category,
            page=page,
            review_state=review_state,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
        )
        safe_cursor = max(0, int(cursor))
        safe_limit = max(1, min(int(limit), 200))
        page_slice = tuple(filtered[safe_cursor : safe_cursor + safe_limit])
        next_cursor = (
            safe_cursor + safe_limit
            if safe_cursor + safe_limit < len(filtered)
            else None
        )
        return DocumentGovernanceManifestEntriesSnapshot(
            run_id=run_id,
            status=status,
            manifest_id=manifest.latest_attempt.id if manifest.latest_attempt is not None else None,
            manifest_sha256=(
                manifest.latest_attempt.manifest_sha256
                if manifest.latest_attempt is not None
                else None
            ),
            source_review_snapshot_sha256=(
                manifest.latest_attempt.source_review_snapshot_sha256
                if manifest.latest_attempt is not None
                else None
            ),
            items=page_slice,
            next_cursor=next_cursor,
            total_count=len(filtered),
            internal_only=manifest.internal_only,
            export_approved=manifest.export_approved,
            not_export_approved=manifest.not_export_approved,
        )

    def get_governance_run_manifest_hash(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentGovernanceManifestHashSnapshot:
        manifest = self.get_governance_run_manifest(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        status = self._resolve_governance_manifest_status(
            latest_attempt=manifest.latest_attempt,
        )
        return DocumentGovernanceManifestHashSnapshot(
            run_id=run_id,
            status=status,
            manifest_id=manifest.latest_attempt.id if manifest.latest_attempt is not None else None,
            manifest_sha256=(
                manifest.latest_attempt.manifest_sha256
                if manifest.latest_attempt is not None
                else None
            ),
            stream_sha256=manifest.stream_sha256,
            hash_matches=manifest.hash_matches,
            internal_only=manifest.internal_only,
            export_approved=manifest.export_approved,
            not_export_approved=manifest.not_export_approved,
        )

    def get_governance_run_ledger(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentGovernanceLedgerSnapshot:
        _ = self._require_governance_ledger_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        overview = self._build_governance_run_overview_snapshot(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            actor_user_id=current_user.user_id,
        )
        latest_attempt = overview.ledger_attempts[0] if overview.ledger_attempts else None
        ledger_payload, stream_sha256, hash_matches = self._load_governance_ledger_payload(
            run_id=run_id,
            latest_attempt=latest_attempt,
        )
        return DocumentGovernanceLedgerSnapshot(
            overview=overview,
            latest_attempt=latest_attempt,
            ledger_payload=ledger_payload,
            stream_sha256=stream_sha256,
            hash_matches=hash_matches,
            internal_only=True,
        )

    def get_governance_run_ledger_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentGovernanceLedgerStatusSnapshot:
        ledger = self.get_governance_run_ledger(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        status = self._resolve_governance_ledger_status(
            latest_attempt=ledger.latest_attempt,
        )
        return DocumentGovernanceLedgerStatusSnapshot(
            run_id=run_id,
            status=status,
            latest_attempt=ledger.latest_attempt,
            attempt_count=len(ledger.overview.ledger_attempts),
            ready_ledger_id=ledger.overview.readiness.ledger_id,
            latest_ledger_sha256=ledger.overview.readiness.last_ledger_sha256,
            generation_status=ledger.overview.readiness.generation_status,
            readiness_status=ledger.overview.readiness.status,
            ledger_verification_status=ledger.overview.readiness.ledger_verification_status,
            updated_at=ledger.overview.readiness.updated_at,
        )

    def list_governance_run_ledger_entries(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        view: Literal["list", "timeline"] = "list",
        cursor: int = 0,
        limit: int = 100,
    ) -> DocumentGovernanceLedgerEntriesSnapshot:
        ledger = self.get_governance_run_ledger(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        status = self._resolve_governance_ledger_status(
            latest_attempt=ledger.latest_attempt,
        )
        rows = (
            extract_ledger_rows(ledger.ledger_payload)
            if isinstance(ledger.ledger_payload, Mapping)
            else []
        )
        projected_rows = rows if view == "list" else list(reversed(rows))
        safe_cursor = max(0, int(cursor))
        safe_limit = max(1, min(int(limit), 200))
        page_slice = tuple(projected_rows[safe_cursor : safe_cursor + safe_limit])
        next_cursor = (
            safe_cursor + safe_limit
            if safe_cursor + safe_limit < len(projected_rows)
            else None
        )
        return DocumentGovernanceLedgerEntriesSnapshot(
            run_id=run_id,
            status=status,
            view=view,
            ledger_id=ledger.latest_attempt.id if ledger.latest_attempt is not None else None,
            ledger_sha256=(
                ledger.latest_attempt.ledger_sha256 if ledger.latest_attempt is not None else None
            ),
            hash_chain_version=(
                ledger.latest_attempt.hash_chain_version if ledger.latest_attempt is not None else None
            ),
            total_count=len(projected_rows),
            next_cursor=next_cursor,
            verification_status=ledger.overview.readiness.ledger_verification_status,
            items=page_slice,
        )

    def get_governance_run_ledger_summary(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentGovernanceLedgerSummarySnapshot:
        ledger = self.get_governance_run_ledger(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        status = self._resolve_governance_ledger_status(
            latest_attempt=ledger.latest_attempt,
        )
        rows = (
            extract_ledger_rows(ledger.ledger_payload)
            if isinstance(ledger.ledger_payload, Mapping)
            else []
        )
        category_counts: dict[str, int] = {}
        action_counts: dict[str, int] = {}
        override_count = 0
        assist_reference_count = 0
        for row in rows:
            category = str(row.get("category") or "").strip().upper()
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1
            action_type = str(row.get("actionType") or "").strip().upper()
            if action_type:
                action_counts[action_type] = action_counts.get(action_type, 0) + 1
            override_reason = row.get("overrideReason")
            if isinstance(override_reason, str) and override_reason.strip():
                override_count += 1
            assist_key = row.get("assistExplanationKey")
            assist_sha256 = row.get("assistExplanationSha256")
            if (
                isinstance(assist_key, str)
                and assist_key.strip()
                and isinstance(assist_sha256, str)
                and assist_sha256.strip()
            ):
                assist_reference_count += 1
        verification = (
            verify_canonical_evidence_ledger_payload(
                ledger.ledger_payload,
                expected_run_id=run_id,
                expected_snapshot_sha256=(
                    ledger.latest_attempt.source_review_snapshot_sha256
                    if ledger.latest_attempt is not None
                    else None
                ),
            )
            if isinstance(ledger.ledger_payload, Mapping)
            else {"isValid": False, "headHash": None}
        )
        return DocumentGovernanceLedgerSummarySnapshot(
            run_id=run_id,
            status=status,
            ledger_id=ledger.latest_attempt.id if ledger.latest_attempt is not None else None,
            ledger_sha256=(
                ledger.latest_attempt.ledger_sha256 if ledger.latest_attempt is not None else None
            ),
            hash_chain_version=(
                ledger.latest_attempt.hash_chain_version if ledger.latest_attempt is not None else None
            ),
            row_count=len(rows),
            hash_chain_head=(
                str(verification.get("headHash"))
                if isinstance(verification.get("headHash"), str)
                else None
            ),
            hash_chain_valid=bool(verification.get("isValid")),
            verification_status=ledger.overview.readiness.ledger_verification_status,
            category_counts=category_counts,
            action_counts=action_counts,
            override_count=override_count,
            assist_reference_count=assist_reference_count,
            internal_only=ledger.internal_only,
        )

    def request_governance_run_ledger_verification(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentGovernanceLedgerVerificationDetailSnapshot:
        self._require_governance_ledger_verify_access(
            current_user=current_user,
            project_id=project_id,
        )
        self._ensure_governance_ledger_generated(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            actor_user_id=current_user.user_id,
        )
        attempt = self._run_governance_ledger_verification(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            actor_user_id=current_user.user_id,
        )
        readiness = self._governance_store.get_readiness_projection(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        return DocumentGovernanceLedgerVerificationDetailSnapshot(
            run_id=run_id,
            verification_status=readiness.ledger_verification_status,
            attempt=attempt,
        )

    def get_governance_run_ledger_verification_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentGovernanceLedgerVerificationStatusSnapshot:
        _ = self._require_governance_ledger_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        _ = self._load_redaction_document(project_id=project_id, document_id=document_id)
        self._ensure_governance_ledger_generated(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            actor_user_id=current_user.user_id,
        )
        try:
            readiness = self._governance_store.get_readiness_projection(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            attempts = tuple(
                self._governance_store.list_ledger_verification_runs(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                )
            )
        except GovernanceRunNotFoundError as error:
            self._raise_governance_lookup_error(error=error)
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error
        latest_attempt = attempts[0] if attempts else None
        latest_completed_attempt = self._latest_completed_verification_attempt(attempts)
        return DocumentGovernanceLedgerVerificationStatusSnapshot(
            run_id=run_id,
            verification_status=readiness.ledger_verification_status,
            attempt_count=len(attempts),
            latest_attempt=latest_attempt,
            latest_completed_attempt=latest_completed_attempt,
            ready_ledger_id=readiness.ledger_id,
            latest_ledger_sha256=readiness.last_ledger_sha256,
            last_verified_at=readiness.ledger_verified_at,
        )

    def list_governance_run_ledger_verification_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentGovernanceLedgerVerificationRunsSnapshot:
        status_snapshot = self.get_governance_run_ledger_verification_status(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        try:
            attempts = tuple(
                self._governance_store.list_ledger_verification_runs(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                )
            )
        except GovernanceRunNotFoundError as error:
            self._raise_governance_lookup_error(error=error)
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error
        return DocumentGovernanceLedgerVerificationRunsSnapshot(
            run_id=run_id,
            verification_status=status_snapshot.verification_status,
            items=attempts,
        )

    def get_governance_run_ledger_verification_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        verification_run_id: str,
    ) -> DocumentGovernanceLedgerVerificationDetailSnapshot:
        status_snapshot = self.get_governance_run_ledger_verification_status(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        try:
            attempt = self._governance_store.get_ledger_verification_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                verification_run_id=verification_run_id,
            )
        except GovernanceRunNotFoundError as error:
            self._raise_governance_lookup_error(error=error)
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error
        return DocumentGovernanceLedgerVerificationDetailSnapshot(
            run_id=run_id,
            verification_status=status_snapshot.verification_status,
            attempt=attempt,
        )

    def cancel_governance_run_ledger_verification_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        verification_run_id: str,
    ) -> DocumentGovernanceLedgerVerificationDetailSnapshot:
        self._require_governance_ledger_verify_access(
            current_user=current_user,
            project_id=project_id,
        )
        try:
            attempt = self._governance_store.cancel_ledger_verification_attempt(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                verification_run_id=verification_run_id,
                actor_user_id=current_user.user_id,
            )
            readiness = self._governance_store.get_readiness_projection(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except GovernanceRunNotFoundError as error:
            self._raise_governance_lookup_error(error=error)
        except GovernanceRunConflictError as error:
            raise DocumentGovernanceConflictError(str(error)) from error
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error
        return DocumentGovernanceLedgerVerificationDetailSnapshot(
            run_id=run_id,
            verification_status=readiness.ledger_verification_status,
            attempt=attempt,
        )

    def list_export_candidate_snapshot_contracts(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> DocumentExportCandidateSnapshotContractsSnapshot:
        _ = self._require_governance_view_access(
            current_user=current_user,
            project_id=project_id,
        )
        try:
            items = tuple(
                self._governance_store.list_candidate_snapshot_contracts(
                    project_id=project_id,
                )
            )
        except GovernanceStoreUnavailableError as error:
            raise DocumentStoreUnavailableError(str(error)) from error
        return DocumentExportCandidateSnapshotContractsSnapshot(
            project_id=project_id,
            items=items,
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
        requires_active_assignment = normalized_engine == "VLM_LINE_CONTEXT"
        requires_optional_fallback_assignment = normalized_engine in {
            "TROCR_LINE",
            "DAN_PAGE",
        }
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
        elif requires_active_assignment or requires_optional_fallback_assignment:
            resolved_assignment = self._store.get_active_project_model_assignment(
                project_id=project_id,
                model_role=expected_model_role,
            )
            if resolved_assignment is None:
                if requires_optional_fallback_assignment:
                    raise DocumentTranscriptionConflictError(
                        "TROCR_LINE and DAN_PAGE require an ACTIVE TRANSCRIPTION_FALLBACK project model assignment."
                    )
                raise DocumentTranscriptionConflictError(
                    "Primary transcription runs require an ACTIVE project model assignment."
                )
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
            if normalized_model_id is not None and normalized_model_id != resolved_model.id:
                if requires_optional_fallback_assignment:
                    raise DocumentTranscriptionConflictError(
                        "modelId must match the ACTIVE project model assignment for TROCR_LINE and DAN_PAGE."
                    )
                raise DocumentTranscriptionConflictError(
                    "modelId must match the ACTIVE project model assignment for primary runs."
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

        if normalized_engine == "VLM_LINE_CONTEXT":
            default_prompt_template_id, default_prompt_template_sha = (
                self._default_transcription_prompt_template()
            )
            if normalized_prompt_template_id is None:
                normalized_prompt_template_id = default_prompt_template_id
            if normalized_prompt_template_sha256 is None:
                normalized_prompt_template_sha256 = default_prompt_template_sha

        try:
            run = self._store.create_transcription_run(
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
            from app.jobs.service import get_job_service

            try:
                get_job_service().enqueue_transcription_document_job(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run.id,
                    created_by=current_user.user_id,
                )
            except Exception as error:  # noqa: BLE001
                raise DocumentStoreUnavailableError(
                    "Transcription run queueing failed."
                ) from error
            return run
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
        run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        rescue_status = self._build_transcription_run_rescue_status_snapshot(
            document=document,
            run=run,
        )
        if not rescue_status.ready_for_activation:
            blocked_pages = [
                page.page_index + 1
                for page in rescue_status.pages
                if page.blocker_reason_codes
            ]
            blocker_codes = self._derive_transcription_activation_blocker_codes(
                rescue_status
            )
            blocked_page_text = (
                ", ".join(str(number) for number in blocked_pages)
                if blocked_pages
                else "unknown"
            )
            raise DocumentTranscriptionConflictError(
                "RESCUE_UNRESOLVED: Activation requires resolved rescue/manual-review "
                f"readiness before promotion. Blocked pages: {blocked_page_text}.",
                rescue_status=rescue_status,
                blocker_codes=blocker_codes,
            )
        try:
            return self._store.activate_transcription_run(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
        except DocumentTranscriptionRunConflictError as error:
            raise DocumentTranscriptionConflictError(
                str(error),
                rescue_status=rescue_status,
                blocker_codes=self._map_transcription_activation_blocker_codes(str(error)),
            ) from error

    @staticmethod
    def _normalize_transcription_rescue_resolution_status(
        value: str,
    ) -> TranscriptionRescueResolutionStatus:
        normalized = value.strip().upper()
        if normalized in {"RESCUE_VERIFIED", "MANUAL_REVIEW_RESOLVED"}:
            return normalized
        raise DocumentValidationError(
            "resolutionStatus must be RESCUE_VERIFIED or MANUAL_REVIEW_RESOLVED."
        )

    @staticmethod
    def _coerce_rescue_source_kind(
        candidate_kind: str,
    ) -> TranscriptionTokenSourceKind:
        if candidate_kind == "LINE_EXPANSION":
            return "RESCUE_CANDIDATE"
        return "PAGE_WINDOW"

    @staticmethod
    def _dedupe_activation_codes(
        codes: Sequence[TranscriptionRunActivationBlockerCode],
    ) -> tuple[TranscriptionRunActivationBlockerCode, ...]:
        ordered: list[TranscriptionRunActivationBlockerCode] = []
        seen: set[TranscriptionRunActivationBlockerCode] = set()
        for code in codes:
            if code in seen:
                continue
            ordered.append(code)
            seen.add(code)
        return tuple(ordered)

    @staticmethod
    def _map_transcription_activation_blocker_codes(
        message: str,
    ) -> tuple[TranscriptionRunActivationBlockerCode, ...]:
        normalized = message.strip().upper()
        codes: list[TranscriptionRunActivationBlockerCode] = []
        if "ONLY SUCCEEDED TRANSCRIPTION RUNS CAN BE ACTIVATED" in normalized:
            codes.append("RUN_NOT_SUCCEEDED")
        if "ACTIVE LAYOUT PROJECTION" in normalized:
            codes.append("RUN_LAYOUT_PROJECTION_MISSING")
        if "LAYOUT BASIS IS STALE" in normalized:
            codes.append("RUN_LAYOUT_BASIS_STALE")
        if "SNAPSHOT HASH NO LONGER MATCHES ACTIVE LAYOUT BASIS" in normalized:
            codes.append("RUN_LAYOUT_SNAPSHOT_STALE")
        if "TOKEN_ANCHOR_INVALID" in normalized:
            codes.append("TOKEN_ANCHOR_INVALID")
        if "CURRENT TOKEN-ANCHOR STATUS" in normalized:
            codes.append("TOKEN_ANCHOR_STALE")
        if "TOKEN ANCHORS FOR ALL ELIGIBLE PAGES" in normalized:
            codes.append("TOKEN_ANCHOR_MISSING")
        return DocumentService._dedupe_activation_codes(codes)

    @staticmethod
    def _derive_transcription_activation_blocker_codes(
        rescue_status: DocumentTranscriptionRunRescueStatusSnapshot,
    ) -> tuple[TranscriptionRunActivationBlockerCode, ...]:
        codes: list[TranscriptionRunActivationBlockerCode] = list(
            rescue_status.run_blocker_reason_codes
        )
        for page in rescue_status.pages:
            codes.extend(page.blocker_reason_codes)
        return DocumentService._dedupe_activation_codes(codes)

    def _build_transcription_rescue_source_snapshots(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        layout_run_id: str,
        page_id: str,
    ) -> tuple[DocumentTranscriptionRescueSourceSnapshot, ...]:
        rescue_candidates = self._store.list_layout_rescue_candidates(
            project_id=project_id,
            document_id=document_id,
            run_id=layout_run_id,
            page_id=page_id,
        )
        token_rows = self._store.list_token_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        token_counts_by_source: dict[tuple[str, str], int] = {}
        for token in token_rows:
            if token.source_kind not in {"RESCUE_CANDIDATE", "PAGE_WINDOW"}:
                continue
            key = (token.source_kind, token.source_ref_id)
            token_counts_by_source[key] = token_counts_by_source.get(key, 0) + 1

        snapshots: list[DocumentTranscriptionRescueSourceSnapshot] = []
        for candidate in rescue_candidates:
            source_kind = self._coerce_rescue_source_kind(candidate.candidate_kind)
            token_count = token_counts_by_source.get((source_kind, candidate.id), 0)
            snapshots.append(
                DocumentTranscriptionRescueSourceSnapshot(
                    source_ref_id=candidate.id,
                    source_kind=source_kind,
                    candidate_kind=candidate.candidate_kind,
                    candidate_status=candidate.status,
                    token_count=token_count,
                    has_transcription_output=token_count > 0,
                    confidence=candidate.confidence,
                    source_signal=candidate.source_signal,
                    geometry_json=dict(candidate.geometry_json),
                )
            )
        return tuple(snapshots)

    @staticmethod
    def _compute_transcription_rescue_page_readiness(
        *,
        page_recall_status: PageRecallStatus,
        page_transcription_status: TranscriptionRunStatus | None,
        rescue_sources: Sequence[DocumentTranscriptionRescueSourceSnapshot],
        resolution: TranscriptionRescueResolutionRecord | None,
    ) -> tuple[
        TranscriptionRescueReadinessState,
        tuple[TranscriptionRescueBlockerReasonCode, ...],
        int,
        int,
        int,
    ]:
        blocker_codes: list[TranscriptionRescueBlockerReasonCode] = []
        if page_transcription_status != "SUCCEEDED":
            blocker_codes.append("PAGE_TRANSCRIPTION_NOT_SUCCEEDED")

        eligible_sources = [
            source
            for source in rescue_sources
            if source.candidate_status in _TRANSCRIPTION_RESCUE_ELIGIBLE_CANDIDATE_STATUSES
        ]
        transcribed_sources = [
            source for source in eligible_sources if source.has_transcription_output
        ]
        rescue_source_count = len(eligible_sources)
        rescue_transcribed_source_count = len(transcribed_sources)
        rescue_unresolved_source_count = max(
            0, rescue_source_count - rescue_transcribed_source_count
        )
        manual_override_applied = (
            resolution is not None
            and resolution.resolution_status == _TRANSCRIPTION_RESCUE_MANUAL_OVERRIDE_STATUS
        )

        if page_recall_status == "NEEDS_RESCUE":
            if rescue_source_count <= 0 and not manual_override_applied:
                blocker_codes.append("RESCUE_SOURCE_MISSING")
            elif rescue_unresolved_source_count > 0 and not manual_override_applied:
                blocker_codes.append("RESCUE_SOURCE_UNTRANSCRIBED")
        elif (
            page_recall_status == "NEEDS_MANUAL_REVIEW"
            and not manual_override_applied
        ):
            blocker_codes.append("MANUAL_REVIEW_RESOLUTION_REQUIRED")

        deduped_blockers: list[TranscriptionRescueBlockerReasonCode] = []
        seen_blockers: set[TranscriptionRescueBlockerReasonCode] = set()
        for code in blocker_codes:
            if code in seen_blockers:
                continue
            deduped_blockers.append(code)
            seen_blockers.add(code)

        readiness_state: TranscriptionRescueReadinessState = "READY"
        if deduped_blockers:
            if "MANUAL_REVIEW_RESOLUTION_REQUIRED" in deduped_blockers:
                readiness_state = "BLOCKED_MANUAL_REVIEW"
            elif any(
                code in {"RESCUE_SOURCE_MISSING", "RESCUE_SOURCE_UNTRANSCRIBED"}
                for code in deduped_blockers
            ):
                readiness_state = "BLOCKED_RESCUE"
            else:
                readiness_state = "BLOCKED_PAGE_STATUS"

        return (
            readiness_state,
            tuple(deduped_blockers),
            rescue_source_count,
            rescue_transcribed_source_count,
            rescue_unresolved_source_count,
        )

    def _build_transcription_page_rescue_status_snapshot(
        self,
        *,
        run: TranscriptionRunRecord,
        layout_page: PageLayoutResultRecord,
        page_transcription: PageTranscriptionResultRecord | None,
        resolution: TranscriptionRescueResolutionRecord | None,
    ) -> tuple[
        DocumentTranscriptionRescuePageStatusSnapshot,
        tuple[DocumentTranscriptionRescueSourceSnapshot, ...],
    ]:
        rescue_sources = self._build_transcription_rescue_source_snapshots(
            project_id=run.project_id,
            document_id=run.document_id,
            run_id=run.id,
            layout_run_id=run.input_layout_run_id,
            page_id=layout_page.page_id,
        )
        (
            readiness_state,
            blocker_reason_codes,
            rescue_source_count,
            rescue_transcribed_source_count,
            rescue_unresolved_source_count,
        ) = self._compute_transcription_rescue_page_readiness(
            page_recall_status=layout_page.page_recall_status,
            page_transcription_status=(
                page_transcription.status if page_transcription is not None else None
            ),
            rescue_sources=rescue_sources,
            resolution=resolution,
        )
        snapshot = DocumentTranscriptionRescuePageStatusSnapshot(
            run_id=run.id,
            page_id=layout_page.page_id,
            page_index=layout_page.page_index,
            page_recall_status=layout_page.page_recall_status,
            rescue_source_count=rescue_source_count,
            rescue_transcribed_source_count=rescue_transcribed_source_count,
            rescue_unresolved_source_count=rescue_unresolved_source_count,
            readiness_state=readiness_state,
            blocker_reason_codes=blocker_reason_codes,
            resolution_status=(
                resolution.resolution_status if resolution is not None else None
            ),
            resolution_reason=(resolution.resolution_reason if resolution else None),
            resolution_updated_by=(resolution.updated_by if resolution else None),
            resolution_updated_at=(resolution.updated_at if resolution else None),
        )
        return snapshot, rescue_sources

    def _build_transcription_run_rescue_status_snapshot(
        self,
        *,
        document: DocumentRecord,
        run: TranscriptionRunRecord,
    ) -> DocumentTranscriptionRunRescueStatusSnapshot:
        layout_pages = self._list_all_layout_page_results(
            project_id=run.project_id,
            document_id=run.document_id,
            run_id=run.input_layout_run_id,
        )
        transcription_pages = {
            row.page_id: row
            for row in self._list_all_transcription_page_results(
                project_id=run.project_id,
                document_id=run.document_id,
                run_id=run.id,
            )
        }
        resolutions = {
            row.page_id: row
            for row in self._store.list_transcription_rescue_resolutions(
                project_id=run.project_id,
                document_id=run.document_id,
                run_id=run.id,
                page_ids=[row.page_id for row in layout_pages],
            )
        }

        page_snapshots: list[DocumentTranscriptionRescuePageStatusSnapshot] = []
        run_blockers: list[TranscriptionRunActivationBlockerCode] = []
        if run.status != "SUCCEEDED":
            run_blockers.append("RUN_NOT_SUCCEEDED")

        for layout_page in layout_pages:
            page_snapshot, _ = self._build_transcription_page_rescue_status_snapshot(
                run=run,
                layout_page=layout_page,
                page_transcription=transcription_pages.get(layout_page.page_id),
                resolution=resolutions.get(layout_page.page_id),
            )
            page_snapshots.append(page_snapshot)
            run_blockers.extend(page_snapshot.blocker_reason_codes)

        run_blocker_reason_codes = self._dedupe_activation_codes(run_blockers)
        blocker_count = (
            len(run_blocker_reason_codes)
            + sum(1 for page in page_snapshots if page.blocker_reason_codes)
        )
        return DocumentTranscriptionRunRescueStatusSnapshot(
            document=document,
            run=run,
            ready_for_activation=(len(run_blocker_reason_codes) == 0),
            blocker_count=blocker_count,
            run_blocker_reason_codes=run_blocker_reason_codes,
            pages=tuple(page_snapshots),
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
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        return self._build_transcription_run_rescue_status_snapshot(
            document=document,
            run=run,
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
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        page = self._store.get_document_page(
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        if page is None:
            raise DocumentPageNotFoundError("Page not found.")
        layout_page = self._store.get_layout_page_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_layout_run_id,
            page_id=page_id,
        )
        if layout_page is None:
            raise DocumentPageNotFoundError(
                "Layout page result backing this transcription run was not found."
            )
        page_transcription = self._store.get_page_transcription_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        resolution = self._store.get_transcription_rescue_resolution(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page_id,
        )
        page_status, rescue_sources = self._build_transcription_page_rescue_status_snapshot(
            run=run,
            layout_page=layout_page,
            page_transcription=page_transcription,
            resolution=resolution,
        )
        return DocumentTranscriptionPageRescueSourcesSnapshot(
            document=document,
            run=run,
            page=page,
            page_recall_status=page_status.page_recall_status,
            readiness_state=page_status.readiness_state,
            blocker_reason_codes=page_status.blocker_reason_codes,
            rescue_sources=rescue_sources,
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
        run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        layout_page = self._store.get_layout_page_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run.input_layout_run_id,
            page_id=page_id,
        )
        if layout_page is None:
            raise DocumentPageNotFoundError("Layout page result not found.")
        if layout_page.page_recall_status == "COMPLETE":
            raise DocumentTranscriptionConflictError(
                "Rescue resolution is only valid for NEEDS_RESCUE or NEEDS_MANUAL_REVIEW pages.",
            )
        normalized_status = self._normalize_transcription_rescue_resolution_status(
            resolution_status
        )
        normalized_reason = (
            resolution_reason.strip()
            if isinstance(resolution_reason, str) and resolution_reason.strip()
            else None
        )
        if normalized_reason is not None and len(normalized_reason) > 600:
            raise DocumentValidationError(
                "resolutionReason must be 600 characters or fewer."
            )
        self._store.upsert_transcription_rescue_resolution(
            project_id=project_id,
            document_id=document_id,
            run_id=run.id,
            page_id=page_id,
            resolution_status=normalized_status,
            resolution_reason=normalized_reason,
            updated_by=current_user.user_id,
        )
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
        normalized_text = text_diplomatic if isinstance(text_diplomatic, str) else ""
        if not normalized_text.strip():
            raise DocumentValidationError("textDiplomatic must not be empty.")
        normalized_version_etag = version_etag.strip() if isinstance(version_etag, str) else ""
        if not normalized_version_etag:
            raise DocumentValidationError("versionEtag is required.")
        normalized_edit_reason = (
            edit_reason.strip()
            if isinstance(edit_reason, str) and edit_reason.strip()
            else None
        )
        if normalized_edit_reason is not None and len(normalized_edit_reason) > 600:
            raise DocumentValidationError("editReason must be 600 characters or fewer.")

        run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        page = self._store.get_document_page(
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        if page is None:
            raise DocumentPageNotFoundError("Document page was not found.")
        page_result = self._store.get_page_transcription_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if page_result is None:
            raise DocumentPageNotFoundError("Transcription page result not found.")
        if (
            page_result.status != "SUCCEEDED"
            or page_result.pagexml_out_key is None
            or page_result.pagexml_out_sha256 is None
        ):
            raise DocumentTranscriptionConflictError(
                "Line correction requires a SUCCEEDED transcription page with PAGE-XML output."
            )
        if not line_id.strip():
            raise DocumentValidationError("lineId is required.")
        line_rows = self._store.list_line_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if not any(row.line_id == line_id for row in line_rows):
            raise DocumentPageNotFoundError("Transcription line result not found.")

        try:
            active_version, updated_line, text_changed = self._store.append_transcript_line_version(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                line_id=line_id,
                text_diplomatic=normalized_text,
                editor_user_id=current_user.user_id,
                expected_version_etag=normalized_version_etag,
                edit_reason=normalized_edit_reason,
            )
        except DocumentTranscriptionRunConflictError as error:
            raise DocumentTranscriptionConflictError(str(error)) from error

        existing_projection = self._store.get_transcription_output_projection(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        source_pagexml_key = (
            existing_projection.corrected_pagexml_key
            if existing_projection is not None
            else page_result.pagexml_out_key
        )
        source_pagexml_sha256 = (
            existing_projection.source_pagexml_sha256
            if existing_projection is not None
            else page_result.pagexml_out_sha256
        )
        if source_pagexml_key is None or source_pagexml_sha256 is None:
            raise DocumentStoreUnavailableError(
                "Transcription correction source projection is unavailable."
            )
        try:
            source_pagexml_bytes = self._storage.read_object_bytes(source_pagexml_key)
            corrected_pagexml_bytes = self._build_corrected_transcription_pagexml(
                base_pagexml_bytes=source_pagexml_bytes,
                line_id=line_id,
                text_diplomatic=normalized_text,
            )
            corrected_object = self._storage.write_transcription_corrected_page_xml(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_index=page.page_index,
                transcript_version_id=active_version.id,
                payload=corrected_pagexml_bytes,
            )
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError(_CONTROLLED_STORAGE_FAILURE_MESSAGE) from error

        projection = self._store.upsert_transcription_output_projection(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            corrected_pagexml_key=corrected_object.object_key,
            corrected_pagexml_sha256=self._sha256_hex(corrected_pagexml_bytes),
            corrected_text_sha256=self._compute_transcription_page_text_sha256(
                corrected_pagexml_bytes
            ),
            source_pagexml_sha256=source_pagexml_sha256,
        )
        downstream_projection: DocumentTranscriptionProjectionRecord | None = None
        if text_changed:
            try:
                downstream_projection = self._store.mark_transcription_downstream_redaction_stale(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=run_id,
                    reason=self._build_transcription_downstream_invalidation_reason(
                        run_id=run_id,
                        page_id=page_id,
                        line_id=line_id,
                        transcript_version_id=active_version.id,
                    ),
                )
            except DocumentTranscriptionRunConflictError as error:
                raise DocumentTranscriptionConflictError(str(error)) from error

        return DocumentTranscriptionLineCorrectionSnapshot(
            run=run,
            page=page,
            line=updated_line,
            active_version=active_version,
            projection=projection,
            text_changed=text_changed,
            downstream_projection=downstream_projection,
        )

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
        run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        page = self._store.get_document_page(
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        if page is None:
            raise DocumentPageNotFoundError("Document page was not found.")
        line_rows = self._store.list_line_transcription_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        line = next((item for item in line_rows if item.line_id == line_id), None)
        if line is None:
            raise DocumentPageNotFoundError("Transcription line result not found.")
        versions = self._store.list_transcript_versions(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
        )
        snapshots = tuple(
            DocumentTranscriptVersionLineageSnapshot(
                version=item,
                is_active=item.id == line.active_transcript_version_id,
                source_type=self._resolve_transcript_version_source_type(
                    run=run,
                    version=item,
                ),
            )
            for item in versions
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
        version = self._store.get_transcript_version(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
            version_id=version_id,
        )
        if version is None:
            raise DocumentPageNotFoundError("Transcript version was not found.")
        return DocumentTranscriptVersionLineageSnapshot(
            version=version,
            is_active=version.id == history.line.active_transcript_version_id,
            source_type=self._resolve_transcript_version_source_type(
                run=history.run,
                version=version,
            ),
        )

    def finalize_transcription_compare(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        base_run_id: str,
        candidate_run_id: str,
        page_ids: Sequence[str] | None = None,
        expected_compare_decision_snapshot_hash: str | None = None,
    ) -> DocumentTranscriptionCompareFinalizeSnapshot:
        self._require_transcription_mutation_access(
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
        base_run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=base_run_id,
        )
        if base_run is None:
            raise DocumentTranscriptionRunNotFoundError("Base transcription run not found.")
        candidate_run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=candidate_run_id,
        )
        if candidate_run is None:
            raise DocumentTranscriptionRunNotFoundError(
                "Candidate transcription run not found."
            )
        if base_run.status != "SUCCEEDED" or candidate_run.status != "SUCCEEDED":
            raise DocumentTranscriptionConflictError(
                "Compare finalization requires SUCCEEDED base and candidate runs."
            )
        if not self._transcription_runs_share_compare_basis(
            base_run=base_run,
            candidate_run=candidate_run,
        ):
            raise DocumentTranscriptionConflictError(
                "Compare finalization requires base and candidate runs to share preprocess/layout basis and layout snapshot hash."
            )
        normalized_page_scope = sorted(
            {
                item.strip()
                for item in (page_ids or ())
                if isinstance(item, str) and item.strip()
            }
        )

        base_pages = self._list_all_transcription_page_results(
            project_id=project_id,
            document_id=document_id,
            run_id=base_run.id,
        )
        candidate_pages = self._list_all_transcription_page_results(
            project_id=project_id,
            document_id=document_id,
            run_id=candidate_run.id,
        )
        page_map: dict[str, int] = {}
        for item in base_pages:
            page_map[item.page_id] = item.page_index
        for item in candidate_pages:
            page_map.setdefault(item.page_id, item.page_index)
        if normalized_page_scope:
            missing_page_ids = [
                item for item in normalized_page_scope if item not in page_map
            ]
            if missing_page_ids:
                raise DocumentPageNotFoundError(
                    "One or more requested pageIds were not found in compare scope."
                )
        decisions = self._store.list_transcription_compare_decisions(
            project_id=project_id,
            document_id=document_id,
            base_run_id=base_run.id,
            candidate_run_id=candidate_run.id,
        )
        if normalized_page_scope:
            allowed_page_ids = set(normalized_page_scope)
            decisions = [
                item for item in decisions if item.page_id in allowed_page_ids
            ]
        decision_events = self._store.list_transcription_compare_decision_events(
            project_id=project_id,
            document_id=document_id,
            base_run_id=base_run.id,
            candidate_run_id=candidate_run.id,
            page_ids=normalized_page_scope or None,
        )
        compare_decision_snapshot_hash = (
            self._compute_transcription_compare_decision_snapshot_hash(
                decisions=decisions,
                events=decision_events,
            )
        )
        normalized_expected_hash = (
            expected_compare_decision_snapshot_hash.strip()
            if isinstance(expected_compare_decision_snapshot_hash, str)
            and expected_compare_decision_snapshot_hash.strip()
            else None
        )
        if (
            normalized_expected_hash is not None
            and normalized_expected_hash != compare_decision_snapshot_hash
        ):
            raise DocumentTranscriptionConflictError(
                "Compare decision snapshot is stale; refresh compare before finalizing."
            )
        if not decisions:
            raise DocumentTranscriptionConflictError(
                "Compare finalization requires at least one explicit compare decision."
            )

        preferred_model = self._store.get_approved_transcription_model(
            preferred_model_role="TRANSCRIPTION_PRIMARY"
        )
        if preferred_model is None:
            raise DocumentTranscriptionConflictError(
                "No APPROVED primary transcription model is available for compare finalization."
            )

        composed_params = self._normalize_transcription_params_json(
            dict(base_run.params_json)
        )
        composed_params["baseRunId"] = base_run.id
        composed_params["candidateRunId"] = candidate_run.id
        composed_params["compareDecisionSnapshotHash"] = compare_decision_snapshot_hash
        composed_params["pageScope"] = list(normalized_page_scope)
        composed_params["finalizedBy"] = current_user.user_id
        composed_params["finalizedAt"] = datetime.now(timezone.utc).isoformat()
        composed_params["decisionCount"] = len(decisions)
        composed_params["decisionEventCount"] = len(decision_events)

        try:
            composed_run = self._store.create_transcription_run(
                project_id=project_id,
                document_id=document_id,
                created_by=current_user.user_id,
                input_preprocess_run_id=base_run.input_preprocess_run_id,
                input_layout_run_id=base_run.input_layout_run_id,
                input_layout_snapshot_hash=base_run.input_layout_snapshot_hash,
                engine="REVIEW_COMPOSED",
                model_id=preferred_model.id,
                project_model_assignment_id=None,
                prompt_template_id=None,
                prompt_template_sha256=None,
                response_schema_version=max(1, base_run.response_schema_version),
                confidence_basis="READ_AGREEMENT",
                confidence_calibration_version=base_run.confidence_calibration_version,
                params_json=composed_params,
                pipeline_version=base_run.pipeline_version,
                container_digest=base_run.container_digest,
                supersedes_transcription_run_id=None,
            )
            composed_run = self._store.mark_transcription_run_running(
                project_id=project_id,
                document_id=document_id,
                run_id=composed_run.id,
            )
        except DocumentTranscriptionRunConflictError as error:
            raise DocumentTranscriptionConflictError(str(error)) from error

        base_pages_by_id = {item.page_id: item for item in base_pages}
        candidate_pages_by_id = {item.page_id: item for item in candidate_pages}
        composed_pages = self._list_all_transcription_page_results(
            project_id=project_id,
            document_id=document_id,
            run_id=composed_run.id,
        )
        scope_page_ids = (
            set(normalized_page_scope)
            if normalized_page_scope
            else {item.page_id for item in composed_pages}
        )

        decisions_by_line = {
            (item.page_id, item.line_id): item
            for item in decisions
            if item.line_id is not None and item.token_id is None
        }
        decisions_by_token = {
            (item.page_id, item.line_id, item.token_id): item
            for item in decisions
            if item.token_id is not None
        }

        try:
            for page_result in composed_pages:
                page_id = page_result.page_id
                base_page = base_pages_by_id.get(page_id)
                candidate_page = candidate_pages_by_id.get(page_id)
                if base_page is None and candidate_page is None:
                    raise DocumentTranscriptionConflictError(
                        f"Compare finalization source page '{page_id}' is unavailable."
                    )
                page_in_scope = page_id in scope_page_ids

                base_line_rows = (
                    self._store.list_line_transcription_results(
                        project_id=project_id,
                        document_id=document_id,
                        run_id=base_run.id,
                        page_id=page_id,
                    )
                    if base_page is not None
                    else []
                )
                candidate_line_rows = (
                    self._store.list_line_transcription_results(
                        project_id=project_id,
                        document_id=document_id,
                        run_id=candidate_run.id,
                        page_id=page_id,
                    )
                    if candidate_page is not None
                    else []
                )
                base_lines = self._hydrate_transcription_lines_with_active_versions(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=base_run.id,
                    page_id=page_id,
                    rows=base_line_rows,
                )
                candidate_lines = self._hydrate_transcription_lines_with_active_versions(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=candidate_run.id,
                    page_id=page_id,
                    rows=candidate_line_rows,
                )
                base_lines_by_id = {item.line_id: item for item in base_lines}
                candidate_lines_by_id = {item.line_id: item for item in candidate_lines}
                line_ids = sorted(set(base_lines_by_id) | set(candidate_lines_by_id))
                selected_origin_by_line_id: dict[str, str] = {}
                line_payloads: list[dict[str, object]] = []
                for target_line_id in line_ids:
                    decision = (
                        decisions_by_line.get((page_id, target_line_id))
                        if page_in_scope
                        else None
                    )
                    base_line = base_lines_by_id.get(target_line_id)
                    candidate_line = candidate_lines_by_id.get(target_line_id)
                    selected_line = base_line
                    selected_origin = "BASE"
                    if (
                        decision is not None
                        and decision.decision == "PROMOTE_CANDIDATE"
                        and candidate_line is not None
                    ):
                        selected_line = candidate_line
                        selected_origin = "CANDIDATE"
                    elif selected_line is None and candidate_line is not None:
                        selected_line = candidate_line
                        selected_origin = "CANDIDATE"
                    if selected_line is None:
                        continue
                    flags_json = dict(selected_line.flags_json)
                    flags_json["lineage"] = {
                        "sourceType": (
                            "COMPARE_DECISION_PROMOTE_CANDIDATE"
                            if decision is not None and decision.decision == "PROMOTE_CANDIDATE"
                            else "COMPARE_BASE_INHERITED"
                        ),
                        "sourceRunId": (
                            candidate_run.id if selected_origin == "CANDIDATE" else base_run.id
                        ),
                        "sourceLineId": target_line_id,
                        "sourceActiveTranscriptVersionId": selected_line.active_transcript_version_id,
                        "decisionId": decision.id if decision is not None else None,
                        "decisionEtag": decision.decision_etag if decision is not None else None,
                    }
                    next_line_etag = hashlib.sha256(
                        (
                            f"{composed_run.id}|{page_id}|{target_line_id}|"
                            f"{selected_origin}|{selected_line.version_etag}|"
                            f"{selected_line.text_diplomatic}"
                        ).encode("utf-8")
                    ).hexdigest()
                    line_payloads.append(
                        {
                            "line_id": target_line_id,
                            "text_diplomatic": selected_line.text_diplomatic,
                            "conf_line": selected_line.conf_line,
                            "confidence_band": selected_line.confidence_band,
                            "confidence_basis": selected_line.confidence_basis,
                            "confidence_calibration_version": selected_line.confidence_calibration_version,
                            "alignment_json_key": selected_line.alignment_json_key,
                            "char_boxes_key": selected_line.char_boxes_key,
                            "schema_validation_status": selected_line.schema_validation_status,
                            "flags_json": flags_json,
                            "machine_output_sha256": selected_line.machine_output_sha256,
                            "active_transcript_version_id": None,
                            "version_etag": next_line_etag,
                            "token_anchor_status": selected_line.token_anchor_status,
                        }
                    )
                    selected_origin_by_line_id[target_line_id] = selected_origin

                selected_line_ids = {
                    str(item["line_id"])
                    for item in line_payloads
                    if isinstance(item.get("line_id"), str)
                }
                base_tokens = (
                    self._store.list_token_transcription_results(
                        project_id=project_id,
                        document_id=document_id,
                        run_id=base_run.id,
                        page_id=page_id,
                    )
                    if base_page is not None
                    else None
                )
                if base_tokens is None:
                    base_tokens = []
                candidate_tokens = (
                    self._store.list_token_transcription_results(
                        project_id=project_id,
                        document_id=document_id,
                        run_id=candidate_run.id,
                        page_id=page_id,
                    )
                    if candidate_page is not None
                    else None
                )
                if candidate_tokens is None:
                    candidate_tokens = []
                base_tokens_by_id = {item.token_id: item for item in base_tokens}
                candidate_tokens_by_id = {item.token_id: item for item in candidate_tokens}
                token_ids = sorted(
                    set(base_tokens_by_id) | set(candidate_tokens_by_id),
                    key=lambda token: (
                        (
                            base_tokens_by_id[token].token_index
                            if token in base_tokens_by_id
                            else candidate_tokens_by_id[token].token_index
                        ),
                        token,
                    ),
                )
                token_payloads: list[dict[str, object]] = []
                refresh_required_line_ids: set[str] = set()
                for target_token_id in token_ids:
                    base_token = base_tokens_by_id.get(target_token_id)
                    candidate_token = candidate_tokens_by_id.get(target_token_id)
                    token_line_id = (
                        base_token.line_id
                        if base_token is not None
                        else candidate_token.line_id if candidate_token is not None else None
                    )
                    decision = (
                        decisions_by_token.get((page_id, token_line_id, target_token_id))
                        if page_in_scope
                        else None
                    )
                    selected_token = base_token
                    selected_origin = "BASE"
                    if (
                        decision is not None
                        and decision.decision == "PROMOTE_CANDIDATE"
                        and candidate_token is not None
                    ):
                        selected_token = candidate_token
                        selected_origin = "CANDIDATE"
                    elif (
                        decision is not None
                        and selected_token is None
                        and candidate_token is not None
                    ):
                        selected_token = candidate_token
                        selected_origin = "CANDIDATE"
                    elif (
                        decision is None
                        and isinstance(token_line_id, str)
                        and selected_origin_by_line_id.get(token_line_id) == "CANDIDATE"
                        and candidate_token is not None
                    ):
                        selected_token = candidate_token
                        selected_origin = "CANDIDATE"
                    elif selected_token is None and candidate_token is not None:
                        selected_token = candidate_token
                        selected_origin = "CANDIDATE"
                    if selected_token is None:
                        continue
                    if (
                        not isinstance(selected_token.line_id, str)
                        or selected_token.line_id not in selected_line_ids
                    ):
                        continue
                    if decision is not None:
                        refresh_required_line_ids.add(selected_token.line_id)
                    token_payloads.append(
                        {
                            "line_id": selected_token.line_id,
                            "token_id": selected_token.token_id,
                            "token_index": selected_token.token_index,
                            "token_text": selected_token.token_text,
                            "token_confidence": selected_token.token_confidence,
                            "bbox_json": selected_token.bbox_json,
                            "polygon_json": selected_token.polygon_json,
                            "source_kind": "LINE",
                            "source_ref_id": selected_token.line_id,
                            "projection_basis": selected_token.projection_basis,
                            "lineage_origin": selected_origin,
                        }
                    )

                if refresh_required_line_ids:
                    for row in line_payloads:
                        line_row_id = str(row.get("line_id") or "")
                        if line_row_id in refresh_required_line_ids:
                            row["token_anchor_status"] = "REFRESH_REQUIRED"

                line_text_by_id = {
                    str(item["line_id"]): str(item["text_diplomatic"])
                    for item in line_payloads
                    if isinstance(item.get("line_id"), str)
                    and isinstance(item.get("text_diplomatic"), str)
                }
                base_pagexml = self._read_transcription_pagexml_for_run_page(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=base_run.id,
                    page_id=page_id,
                    page_result=base_page,
                )
                candidate_pagexml = self._read_transcription_pagexml_for_run_page(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=candidate_run.id,
                    page_id=page_id,
                    page_result=candidate_page or base_page,
                )
                composed_pagexml_bytes = self._build_transcription_composed_pagexml(
                    base_pagexml_bytes=base_pagexml,
                    candidate_pagexml_bytes=candidate_pagexml,
                    line_text_by_id=line_text_by_id,
                )
                page_object = self._storage.write_transcription_page_xml(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=composed_run.id,
                    page_index=page_result.page_index,
                    payload=composed_pagexml_bytes,
                )
                page_decisions = [
                    item
                    for item in decisions
                    if item.page_id == page_id
                ]
                raw_payload = {
                    "schemaVersion": 1,
                    "source": "REVIEW_COMPOSED",
                    "baseRunId": base_run.id,
                    "candidateRunId": candidate_run.id,
                    "pageId": page_id,
                    "pageIndex": page_result.page_index,
                    "compareDecisionSnapshotHash": compare_decision_snapshot_hash,
                    "decisions": [
                        {
                            "id": item.id,
                            "lineId": item.line_id,
                            "tokenId": item.token_id,
                            "decision": item.decision,
                            "decisionEtag": item.decision_etag,
                            "decidedBy": item.decided_by,
                            "decidedAt": item.decided_at.isoformat(),
                            "reason": item.decision_reason,
                        }
                        for item in page_decisions
                    ],
                    "pageScopeApplied": page_in_scope,
                }
                raw_bytes = json.dumps(
                    raw_payload,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
                raw_object = self._storage.write_transcription_raw_response(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=composed_run.id,
                    page_index=page_result.page_index,
                    payload=raw_bytes,
                )
                self._store.replace_line_transcription_results(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=composed_run.id,
                    page_id=page_id,
                    rows=line_payloads,
                )
                self._store.replace_token_transcription_results(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=composed_run.id,
                    page_id=page_id,
                    rows=[
                        {
                            "line_id": item["line_id"],
                            "token_id": item["token_id"],
                            "token_index": item["token_index"],
                            "token_text": item["token_text"],
                            "token_confidence": item["token_confidence"],
                            "bbox_json": item["bbox_json"],
                            "polygon_json": item["polygon_json"],
                            "source_kind": item["source_kind"],
                            "source_ref_id": item["source_ref_id"],
                            "projection_basis": item["projection_basis"],
                        }
                        for item in token_payloads
                    ],
                )
                source_page = (
                    candidate_page
                    if any(
                        item.decision == "PROMOTE_CANDIDATE"
                        for item in page_decisions
                    )
                    else base_page
                ) or base_page or candidate_page
                metrics_json = (
                    dict(source_page.metrics_json)
                    if source_page is not None
                    else {}
                )
                metrics_json["compare_decision_count"] = len(page_decisions)
                metrics_json["compare_decision_promote_count"] = sum(
                    1
                    for item in page_decisions
                    if item.decision == "PROMOTE_CANDIDATE"
                )
                warnings_json = (
                    list(source_page.warnings_json)
                    if source_page is not None
                    else []
                )
                if any(
                    str(item.get("token_anchor_status")) != "CURRENT"
                    for item in line_payloads
                ):
                    warning_code = "TOKEN_ANCHOR_REFRESH_REQUIRED"
                    if warning_code not in warnings_json:
                        warnings_json.append(warning_code)
                self._store.complete_transcription_page_result(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=composed_run.id,
                    page_id=page_id,
                    pagexml_out_key=page_object.object_key,
                    pagexml_out_sha256=self._sha256_hex(composed_pagexml_bytes),
                    raw_model_response_key=raw_object.object_key,
                    raw_model_response_sha256=self._sha256_hex(raw_bytes),
                    metrics_json=metrics_json,
                    warnings_json=warnings_json,
                    hocr_out_key=None,
                    hocr_out_sha256=None,
                )

            composed_run = self._store.finalize_transcription_run(
                project_id=project_id,
                document_id=document_id,
                run_id=composed_run.id,
            )
        except DocumentTranscriptionRunConflictError as error:
            raise DocumentTranscriptionConflictError(str(error)) from error
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError(_CONTROLLED_STORAGE_FAILURE_MESSAGE) from error
        return DocumentTranscriptionCompareFinalizeSnapshot(
            document=document,
            base_run=base_run,
            candidate_run=candidate_run,
            composed_run=composed_run,
            compare_decision_snapshot_hash=compare_decision_snapshot_hash,
            page_scope=tuple(normalized_page_scope),
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
        normalized_variant_kind = self._normalize_transcript_variant_kind(variant_kind)
        run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        page = self._store.get_document_page(
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        if page is None:
            raise DocumentPageNotFoundError("Document page was not found.")
        page_result = self._store.get_page_transcription_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if page_result is None:
            raise DocumentPageNotFoundError("Transcription page result not found.")

        layers = self._store.list_transcript_variant_layers(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            variant_kind=normalized_variant_kind,
        )
        layer_snapshots: list[DocumentTranscriptionVariantLayerSnapshot] = []
        for layer in layers:
            suggestions = tuple(
                self._store.list_transcript_variant_suggestions(
                    project_id=project_id,
                    document_id=document_id,
                    variant_layer_id=layer.id,
                )
            )
            layer_snapshots.append(
                DocumentTranscriptionVariantLayerSnapshot(
                    layer=layer,
                    suggestions=suggestions,
                )
            )
        return DocumentTranscriptionVariantLayersSnapshot(
            run=run,
            page=page,
            variant_kind=normalized_variant_kind,
            layers=tuple(layer_snapshots),
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
        normalized_variant_kind = self._normalize_transcript_variant_kind(variant_kind)
        normalized_decision = self._normalize_transcript_variant_suggestion_decision(
            decision
        )
        run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        page = self._store.get_document_page(
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
        if page is None:
            raise DocumentPageNotFoundError("Document page was not found.")
        page_result = self._store.get_page_transcription_result(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if page_result is None:
            raise DocumentPageNotFoundError("Transcription page result not found.")
        try:
            suggestion, event = self._store.record_transcript_variant_suggestion_decision(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                variant_kind=normalized_variant_kind,
                suggestion_id=suggestion_id,
                decision=normalized_decision,
                actor_user_id=current_user.user_id,
                reason=reason,
            )
        except DocumentTranscriptionRunConflictError as error:
            raise DocumentTranscriptionConflictError(str(error)) from error
        return DocumentTranscriptionVariantSuggestionDecisionSnapshot(
            run=run,
            page=page,
            variant_kind=normalized_variant_kind,
            suggestion=suggestion,
            event=event,
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

    def _resolve_transcription_triage_target_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str | None,
    ) -> tuple[
        DocumentTranscriptionProjectionRecord | None,
        TranscriptionRunRecord | None,
    ]:
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
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
        return projection, target_run

    def _resolve_transcription_review_confidence_threshold(
        self,
        *,
        run: TranscriptionRunRecord,
        override_threshold: float | None,
    ) -> float:
        if isinstance(override_threshold, (int, float)):
            threshold = float(override_threshold)
        else:
            threshold = _TRANSCRIPTION_DEFAULT_REVIEW_CONFIDENCE_THRESHOLD
            params_threshold = self._coerce_numeric(
                run.params_json.get("review_confidence_threshold")
            )
            if params_threshold is not None:
                threshold = params_threshold
        if threshold < 0 or threshold > 1:
            raise DocumentValidationError("confidenceBelow must be between 0 and 1.")
        return threshold

    def _resolve_transcription_confidence_band(
        self,
        *,
        line: LineTranscriptionResultRecord,
        review_threshold: float,
        fallback_threshold: float,
    ) -> TranscriptionConfidenceBand:
        if line.confidence_band != "UNKNOWN":
            return line.confidence_band
        if not isinstance(line.conf_line, float):
            return "UNKNOWN"
        if line.conf_line >= review_threshold:
            return "HIGH"
        if line.conf_line >= fallback_threshold:
            return "MEDIUM"
        return "LOW"

    def _build_transcription_triage_page_snapshot(
        self,
        *,
        page_result: PageTranscriptionResultRecord,
        line_rows: Sequence[LineTranscriptionResultRecord],
        token_rows: Sequence[TokenTranscriptionResultRecord],
        review_threshold: float,
        fallback_threshold: float,
    ) -> DocumentTranscriptionTriagePageSnapshot:
        confidence_values = [
            line.conf_line for line in line_rows if isinstance(line.conf_line, float)
        ]
        min_confidence = min(confidence_values) if confidence_values else None
        avg_confidence = (
            sum(confidence_values) / len(confidence_values) if confidence_values else None
        )
        low_confidence_lines = sum(
            1
            for line in line_rows
            if isinstance(line.conf_line, float) and line.conf_line < review_threshold
        )
        anchor_refresh_required = sum(
            1 for line in line_rows if line.token_anchor_status != "CURRENT"
        )
        segmentation_mismatch_count = sum(
            1
            for line in line_rows
            if line.schema_validation_status != "INVALID"
            and not line.text_diplomatic.strip()
        )
        validation_failure_count = sum(
            1 for line in line_rows if line.schema_validation_status == "INVALID"
        )
        if any(warning == "SCHEMA_VALIDATION_FAILED" for warning in page_result.warnings_json):
            validation_failure_count = max(1, validation_failure_count)
        confidence_bands: dict[TranscriptionConfidenceBand, int] = {
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "UNKNOWN": 0,
        }
        for line in line_rows:
            band = self._resolve_transcription_confidence_band(
                line=line,
                review_threshold=review_threshold,
                fallback_threshold=fallback_threshold,
            )
            confidence_bands[band] += 1

        ranking_score = 0.0
        rationale_parts: list[str] = []
        issues: list[str] = []
        if page_result.status == "FAILED":
            ranking_score += _TRANSCRIPTION_TRIAGE_FAILED_STATUS_WEIGHT
            rationale_parts.append("page status FAILED")
            issues.append("FAILED")
        if low_confidence_lines > 0:
            ranking_score += low_confidence_lines * _TRANSCRIPTION_TRIAGE_LOW_CONFIDENCE_WEIGHT
            rationale_parts.append(
                f"{low_confidence_lines} low-confidence line(s) below {review_threshold:.3f}"
            )
            issues.append("LOW_CONFIDENCE")
        if min_confidence is not None:
            ranking_score += (1.0 - min_confidence) * _TRANSCRIPTION_TRIAGE_MIN_CONFIDENCE_WEIGHT
            rationale_parts.append(f"minimum confidence {min_confidence:.3f}")
        if validation_failure_count > 0:
            ranking_score += (
                validation_failure_count * _TRANSCRIPTION_TRIAGE_VALIDATION_WARNING_WEIGHT
            )
            rationale_parts.append(
                f"{validation_failure_count} structured validation failure(s)"
            )
            issues.append("SCHEMA_VALIDATION_FAILED")
        if segmentation_mismatch_count > 0:
            ranking_score += (
                segmentation_mismatch_count
                * _TRANSCRIPTION_TRIAGE_SEGMENTATION_MISMATCH_WEIGHT
            )
            rationale_parts.append(
                f"{segmentation_mismatch_count} segmentation mismatch warning(s)"
            )
            issues.append("SEGMENTATION_MISMATCH")
        if anchor_refresh_required > 0:
            ranking_score += (
                anchor_refresh_required * _TRANSCRIPTION_TRIAGE_ANCHOR_REFRESH_WEIGHT
            )
            rationale_parts.append(f"{anchor_refresh_required} anchor refresh required")
            issues.append("ANCHOR_REFRESH_REQUIRED")
        for warning in page_result.warnings_json:
            if warning not in issues:
                issues.append(warning)
        ranking_rationale = "; ".join(rationale_parts) if rationale_parts else "No elevated risk factors."

        return DocumentTranscriptionTriagePageSnapshot(
            run_id=page_result.run_id,
            page_id=page_result.page_id,
            page_index=page_result.page_index,
            status=page_result.status,
            line_count=len(line_rows),
            token_count=len(token_rows),
            anchor_refresh_required=anchor_refresh_required,
            low_confidence_lines=low_confidence_lines,
            min_confidence=min_confidence,
            avg_confidence=avg_confidence,
            warnings_json=list(page_result.warnings_json),
            confidence_bands=confidence_bands,
            issues=issues,
            ranking_score=round(ranking_score, 6),
            ranking_rationale=ranking_rationale,
            reviewer_assignment_user_id=page_result.reviewer_assignment_user_id,
            reviewer_assignment_updated_by=page_result.reviewer_assignment_updated_by,
            reviewer_assignment_updated_at=page_result.reviewer_assignment_updated_at,
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
            review_threshold = self._resolve_transcription_review_confidence_threshold(
                run=active_run,
                override_threshold=None,
            )
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
                    and line.conf_line < review_threshold
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

        projection, target_run = self._resolve_transcription_triage_target_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if target_run is None:
            return projection, None, [], None

        review_threshold = self._resolve_transcription_review_confidence_threshold(
            run=target_run,
            override_threshold=confidence_below,
        )
        fallback_threshold = self._resolve_fallback_confidence_threshold(
            run=target_run,
            override_threshold=None,
        )
        page_results = self._list_all_transcription_page_results(
            project_id=project_id,
            document_id=document_id,
            run_id=target_run.id,
            status=status,
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
            triage_row = self._build_transcription_triage_page_snapshot(
                page_result=page_result,
                line_rows=line_rows,
                token_rows=token_rows,
                review_threshold=review_threshold,
                fallback_threshold=fallback_threshold,
            )
            if (
                confidence_below is not None
                and triage_row.low_confidence_lines == 0
                and (
                    triage_row.min_confidence is None
                    or triage_row.min_confidence >= confidence_below
                )
            ):
                continue
            rows.append(triage_row)

        ordered_rows = sorted(
            rows,
            key=lambda item: (-item.ranking_score, item.page_index, item.page_id),
        )
        start = max(0, cursor)
        end = start + page_size
        next_cursor = end if end < len(ordered_rows) else None
        return projection, target_run, ordered_rows[start:end], next_cursor

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
        if confidence_below is not None and (confidence_below < 0 or confidence_below > 1):
            raise DocumentValidationError("confidenceBelow must be between 0 and 1.")

        projection, target_run = self._resolve_transcription_triage_target_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if target_run is None:
            empty_metrics = DocumentTranscriptionMetricsSnapshot(
                run_id=None,
                review_confidence_threshold=(
                    float(confidence_below)
                    if isinstance(confidence_below, (int, float))
                    else _TRANSCRIPTION_DEFAULT_REVIEW_CONFIDENCE_THRESHOLD
                ),
                fallback_confidence_threshold=_TRANSCRIPTION_DEFAULT_FALLBACK_CONFIDENCE_THRESHOLD,
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
            return projection, None, empty_metrics

        review_threshold = self._resolve_transcription_review_confidence_threshold(
            run=target_run,
            override_threshold=confidence_below,
        )
        fallback_threshold = self._resolve_fallback_confidence_threshold(
            run=target_run,
            override_threshold=None,
        )
        page_results = self._list_all_transcription_page_results(
            project_id=project_id,
            document_id=document_id,
            run_id=target_run.id,
        )
        line_count = 0
        token_count = 0
        low_confidence_line_count = 0
        segmentation_mismatch_warning_count = 0
        structured_validation_failure_count = 0
        fallback_invocation_count = 0
        confidence_bands: dict[TranscriptionConfidenceBand, int] = {
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "UNKNOWN": 0,
        }
        low_confidence_pages: list[DocumentTranscriptionLowConfidencePageSnapshot] = []

        for page_result in page_results:
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
            line_count += len(line_rows)
            token_count += len(token_rows)
            low_confidence_on_page = 0
            line_validation_failures = 0
            for line in line_rows:
                band = self._resolve_transcription_confidence_band(
                    line=line,
                    review_threshold=review_threshold,
                    fallback_threshold=fallback_threshold,
                )
                confidence_bands[band] += 1
                if line.schema_validation_status != "INVALID" and not line.text_diplomatic.strip():
                    segmentation_mismatch_warning_count += 1
                if line.schema_validation_status == "INVALID":
                    line_validation_failures += 1
                if isinstance(line.conf_line, float) and line.conf_line < review_threshold:
                    low_confidence_line_count += 1
                    low_confidence_on_page += 1
            metric_invalid_count = self._coerce_numeric(
                page_result.metrics_json.get("invalidTargetCount")
                or page_result.metrics_json.get("invalidCount")
            )
            metric_fallback_count = self._coerce_numeric(
                page_result.metrics_json.get("fallbackInvocationCount")
            )
            if metric_fallback_count is not None and metric_fallback_count > 0:
                fallback_invocation_count += int(metric_fallback_count)
            warning_validation_failures = (
                1 if "SCHEMA_VALIDATION_FAILED" in page_result.warnings_json else 0
            )
            structured_validation_failure_count += max(
                line_validation_failures,
                int(metric_invalid_count) if metric_invalid_count is not None else 0,
                warning_validation_failures,
            )
            if low_confidence_on_page > 0:
                low_confidence_pages.append(
                    DocumentTranscriptionLowConfidencePageSnapshot(
                        page_id=page_result.page_id,
                        page_index=page_result.page_index,
                low_confidence_lines=low_confidence_on_page,
                    )
                )

        if fallback_invocation_count == 0 and target_run.confidence_basis == "FALLBACK_DISAGREEMENT":
            fallback_invocation_count = 1
        if (
            fallback_invocation_count == 0
            and isinstance(target_run.params_json.get("fallback_invocation"), dict)
        ):
            fallback_invocation_count = 1

        percent_lines_below_threshold = (
            round((low_confidence_line_count / line_count) * 100, 6)
            if line_count > 0
            else 0.0
        )
        low_confidence_pages.sort(
            key=lambda item: (-item.low_confidence_lines, item.page_index, item.page_id)
        )
        metrics = DocumentTranscriptionMetricsSnapshot(
            run_id=target_run.id,
            review_confidence_threshold=review_threshold,
            fallback_confidence_threshold=fallback_threshold,
            page_count=len(page_results),
            line_count=line_count,
            token_count=token_count,
            low_confidence_line_count=low_confidence_line_count,
            percent_lines_below_threshold=percent_lines_below_threshold,
            low_confidence_page_count=len(low_confidence_pages),
            low_confidence_page_distribution=low_confidence_pages,
            segmentation_mismatch_warning_count=segmentation_mismatch_warning_count,
            structured_validation_failure_count=structured_validation_failure_count,
            fallback_invocation_count=fallback_invocation_count,
            confidence_bands=confidence_bands,
        )
        return projection, target_run, metrics

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
        projection, target_run = self._resolve_transcription_triage_target_run(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if target_run is None:
            raise DocumentTranscriptionRunNotFoundError("Transcription run not found.")
        page_result = self._store.update_page_transcription_assignment(
            project_id=project_id,
            document_id=document_id,
            run_id=target_run.id,
            page_id=page_id,
            reviewer_user_id=reviewer_user_id,
            updated_by=current_user.user_id,
        )
        review_threshold = self._resolve_transcription_review_confidence_threshold(
            run=target_run,
            override_threshold=None,
        )
        fallback_threshold = self._resolve_fallback_confidence_threshold(
            run=target_run,
            override_threshold=None,
        )
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
        triage_row = self._build_transcription_triage_page_snapshot(
            page_result=page_result,
            line_rows=line_rows,
            token_rows=token_rows,
            review_threshold=review_threshold,
            fallback_threshold=fallback_threshold,
        )
        return projection, target_run, triage_row

    @staticmethod
    def _coerce_numeric(value: object) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def _resolve_fallback_confidence_threshold(
        self,
        *,
        run: TranscriptionRunRecord,
        override_threshold: float | None,
    ) -> float:
        if isinstance(override_threshold, (int, float)):
            threshold = float(override_threshold)
        else:
            threshold = _TRANSCRIPTION_DEFAULT_FALLBACK_CONFIDENCE_THRESHOLD
            params_threshold = self._coerce_numeric(
                run.params_json.get("fallback_confidence_threshold")
            )
            if params_threshold is not None:
                threshold = params_threshold
        if threshold < 0 or threshold > 1:
            raise DocumentValidationError(
                "fallbackConfidenceThreshold must be between 0 and 1."
            )
        return threshold

    def _evaluate_transcription_fallback_reasons(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        confidence_threshold: float,
    ) -> list[TranscriptionFallbackReasonCode]:
        reasons: set[TranscriptionFallbackReasonCode] = set()
        page_results = self._list_all_transcription_page_results(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        for page in page_results:
            if any(
                warning == "SCHEMA_VALIDATION_FAILED" for warning in page.warnings_json
            ):
                reasons.add("SCHEMA_VALIDATION_FAILED")
            line_rows = self._store.list_line_transcription_results(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page.page_id,
            )
            for line in line_rows:
                if line.schema_validation_status == "INVALID":
                    reasons.add("SCHEMA_VALIDATION_FAILED")
                if line.token_anchor_status != "CURRENT":
                    reasons.add("ANCHOR_RESOLUTION_FAILED")
                validation_errors = line.flags_json.get("validationErrors")
                if isinstance(validation_errors, list):
                    if any(
                        isinstance(item, str)
                        and (
                            "ANCHOR" in item.upper()
                            or "LINE_ID" in item.upper()
                            or "UNKNOWN_LINE_REFERENCE" in item.upper()
                        )
                        for item in validation_errors
                    ):
                        reasons.add("ANCHOR_RESOLUTION_FAILED")
                if (
                    isinstance(line.conf_line, float)
                    and line.conf_line < confidence_threshold
                ):
                    reasons.add("CONFIDENCE_BELOW_THRESHOLD")
        ordered = [
            reason
            for reason in (
                "SCHEMA_VALIDATION_FAILED",
                "ANCHOR_RESOLUTION_FAILED",
                "CONFIDENCE_BELOW_THRESHOLD",
            )
            if reason in reasons
        ]
        return ordered  # type: ignore[return-value]

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
        fallback_reason_codes: Sequence[str] | None = None,
        fallback_confidence_threshold: float | None = None,
    ) -> tuple[TranscriptionRunRecord, list[TranscriptionFallbackReasonCode]]:
        self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        normalized_base_run_id = self._normalize_transcription_reference(
            base_run_id,
            field_name="baseRunId",
            max_length=120,
        )
        normalized_engine = self._normalize_transcription_engine(engine or "KRAKEN_LINE")
        if not self._is_fallback_engine(normalized_engine):
            raise DocumentTranscriptionConflictError(
                "Fallback run creation requires a fallback engine."
            )
        if (
            normalized_engine in {"TROCR_LINE", "DAN_PAGE"}
            and not isinstance(project_model_assignment_id, str)
        ):
            raise DocumentTranscriptionConflictError(
                "TROCR_LINE and DAN_PAGE remain disabled until an ACTIVE TRANSCRIPTION_FALLBACK assignment is configured."
            )

        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")

        target_base_run: TranscriptionRunRecord | None = None
        if normalized_base_run_id is not None:
            target_base_run = self._store.get_transcription_run(
                project_id=project_id,
                document_id=document_id,
                run_id=normalized_base_run_id,
            )
        else:
            projection = self._store.get_transcription_projection(
                project_id=project_id,
                document_id=document_id,
            )
            if projection is not None and projection.active_transcription_run_id:
                target_base_run = self._store.get_transcription_run(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=projection.active_transcription_run_id,
                )
            if target_base_run is None:
                latest_runs, _ = self._store.list_transcription_runs(
                    project_id=project_id,
                    document_id=document_id,
                    cursor=0,
                    page_size=1,
                )
                target_base_run = latest_runs[0] if latest_runs else None
        if target_base_run is None:
            raise DocumentTranscriptionRunNotFoundError(
                "Fallback run creation requires a base transcription run."
            )
        threshold = self._resolve_fallback_confidence_threshold(
            run=target_base_run,
            override_threshold=fallback_confidence_threshold,
        )
        inferred_reasons = self._evaluate_transcription_fallback_reasons(
            project_id=project_id,
            document_id=document_id,
            run_id=target_base_run.id,
            confidence_threshold=threshold,
        )
        explicit_reasons = self._normalize_fallback_reason_codes(fallback_reason_codes)
        selected_reasons = explicit_reasons if explicit_reasons else inferred_reasons
        if not selected_reasons:
            raise DocumentTranscriptionConflictError(
                "Fallback run creation is gated: no fallback trigger conditions were detected."
            )
        if explicit_reasons:
            inferred_set = set(inferred_reasons)
            unsupported = [reason for reason in explicit_reasons if reason not in inferred_set]
            if unsupported:
                raise DocumentTranscriptionConflictError(
                    "fallbackReasonCodes include triggers not currently detected on the base run."
                )

        merged_params = self._normalize_transcription_params_json(
            params_json if params_json is not None else dict(target_base_run.params_json)
        )
        merged_params["fallback_invocation"] = {
            "base_run_id": target_base_run.id,
            "reason_codes": list(selected_reasons),
            "confidence_threshold": threshold,
            "evaluated_at": datetime.utcnow().isoformat() + "Z",
        }
        merged_params["fallback_source_run_id"] = target_base_run.id

        fallback_run = self.create_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            input_preprocess_run_id=target_base_run.input_preprocess_run_id,
            input_layout_run_id=target_base_run.input_layout_run_id,
            engine=normalized_engine,
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
        return fallback_run, list(selected_reasons)

    @staticmethod
    def _transcription_runs_share_compare_basis(
        *,
        base_run: TranscriptionRunRecord,
        candidate_run: TranscriptionRunRecord,
    ) -> bool:
        return (
            base_run.input_preprocess_run_id == candidate_run.input_preprocess_run_id
            and base_run.input_layout_run_id == candidate_run.input_layout_run_id
            and base_run.input_layout_snapshot_hash
            == candidate_run.input_layout_snapshot_hash
        )

    @staticmethod
    def _build_transcription_engine_metadata(
        run: TranscriptionRunRecord,
    ) -> dict[str, object]:
        return {
            "runId": run.id,
            "engine": run.engine,
            "modelId": run.model_id,
            "projectModelAssignmentId": run.project_model_assignment_id,
            "confidenceBasis": run.confidence_basis,
            "confidenceCalibrationVersion": run.confidence_calibration_version,
            "pipelineVersion": run.pipeline_version,
            "containerDigest": run.container_digest,
        }

    @staticmethod
    def _set_pagexml_text_equiv(line_element: ET.Element, text: str) -> None:
        for text_equiv in list(line_element.findall("pc:TextEquiv", _PAGE_XML_NS)):
            line_element.remove(text_equiv)
        text_equiv = ET.SubElement(line_element, f"{{{_PAGE_XML_NAMESPACE}}}TextEquiv")
        unicode_element = ET.SubElement(text_equiv, f"{{{_PAGE_XML_NAMESPACE}}}Unicode")
        unicode_element.text = text

    def _build_corrected_transcription_pagexml(
        self,
        *,
        base_pagexml_bytes: bytes,
        line_id: str,
        text_diplomatic: str,
    ) -> bytes:
        try:
            root = ET.fromstring(base_pagexml_bytes)
        except ET.ParseError as error:
            raise DocumentStoreUnavailableError(
                "Transcription PAGE-XML payload is invalid."
            ) from error
        target_line: ET.Element | None = None
        for candidate in root.findall(".//pc:TextLine", _PAGE_XML_NS):
            if candidate.get("id") == line_id:
                target_line = candidate
                break
        if target_line is None:
            raise DocumentTranscriptionConflictError(
                f"Transcription PAGE-XML is missing line '{line_id}'."
            )
        self._set_pagexml_text_equiv(target_line, text_diplomatic)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"

    def _compute_transcription_page_text_sha256(self, pagexml_bytes: bytes) -> str:
        try:
            root = ET.fromstring(pagexml_bytes)
        except ET.ParseError as error:
            raise DocumentStoreUnavailableError(
                "Transcription PAGE-XML payload is invalid."
            ) from error
        line_texts: list[str] = []
        for line_element in root.findall(".//pc:TextLine", _PAGE_XML_NS):
            unicode_element = line_element.find("pc:TextEquiv/pc:Unicode", _PAGE_XML_NS)
            line_texts.append((unicode_element.text or "") if unicode_element is not None else "")
        return self._sha256_hex("\n".join(line_texts).encode("utf-8"))

    @staticmethod
    def _build_transcription_downstream_invalidation_reason(
        *,
        run_id: str,
        page_id: str,
        line_id: str,
        transcript_version_id: str,
    ) -> str:
        return (
            "TRANSCRIPT_CORRECTION_ACTIVE_BASIS_CHANGED: "
            f"run={run_id};page={page_id};line={line_id};"
            f"version={transcript_version_id}"
        )

    def _hydrate_transcription_lines_with_active_versions(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        rows: Sequence[LineTranscriptionResultRecord],
    ) -> list[LineTranscriptionResultRecord]:
        hydrated: list[LineTranscriptionResultRecord] = []
        for row in rows:
            active_version_id = (
                row.active_transcript_version_id
                if isinstance(row.active_transcript_version_id, str)
                and row.active_transcript_version_id.strip()
                else None
            )
            if active_version_id is None:
                hydrated.append(row)
                continue
            version = self._store.get_transcript_version(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                line_id=row.line_id,
                version_id=active_version_id,
            )
            if version is None:
                hydrated.append(row)
                continue
            hydrated.append(replace(row, text_diplomatic=version.text_diplomatic))
        return hydrated

    def _resolve_transcript_version_source_type(
        self,
        *,
        run: TranscriptionRunRecord,
        version: TranscriptVersionRecord,
    ) -> str:
        if run.engine == "REVIEW_COMPOSED":
            return "COMPARE_COMPOSED"
        if version.base_version_id is None:
            return "ENGINE_OUTPUT"
        return "REVIEWER_CORRECTION"

    @staticmethod
    def _compute_transcription_compare_decision_snapshot_hash(
        *,
        decisions: Sequence[TranscriptionCompareDecisionRecord],
        events: Sequence[TranscriptionCompareDecisionEventRecord],
    ) -> str:
        payload = {
            "decisions": [
                {
                    "id": item.id,
                    "documentId": item.document_id,
                    "baseRunId": item.base_run_id,
                    "candidateRunId": item.candidate_run_id,
                    "pageId": item.page_id,
                    "lineId": item.line_id,
                    "tokenId": item.token_id,
                    "decision": item.decision,
                    "decisionEtag": item.decision_etag,
                    "decidedBy": item.decided_by,
                    "decidedAt": item.decided_at.isoformat(),
                    "decisionReason": item.decision_reason,
                    "updatedAt": item.updated_at.isoformat(),
                }
                for item in sorted(
                    decisions,
                    key=lambda row: (
                        row.page_id,
                        row.line_id or "",
                        row.token_id or "",
                        row.id,
                    ),
                )
            ],
            "events": [
                {
                    "id": event.id,
                    "decisionId": event.decision_id,
                    "documentId": event.document_id,
                    "baseRunId": event.base_run_id,
                    "candidateRunId": event.candidate_run_id,
                    "pageId": event.page_id,
                    "lineId": event.line_id,
                    "tokenId": event.token_id,
                    "fromDecision": event.from_decision,
                    "toDecision": event.to_decision,
                    "actorUserId": event.actor_user_id,
                    "reason": event.reason,
                    "createdAt": event.created_at.isoformat(),
                }
                for event in sorted(events, key=lambda row: (row.created_at, row.id))
            ],
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _read_transcription_pagexml_for_run_page(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        page_result: PageTranscriptionResultRecord | None,
    ) -> bytes:
        if page_result is None:
            raise DocumentTranscriptionConflictError(
                f"Transcription page result '{page_id}' was not found."
            )
        projection = self._store.get_transcription_output_projection(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        object_key = (
            projection.corrected_pagexml_key
            if projection is not None
            else page_result.pagexml_out_key
        )
        if not isinstance(object_key, str) or not object_key.strip():
            raise DocumentTranscriptionConflictError(
                f"Transcription PAGE-XML is unavailable for page '{page_id}'."
            )
        try:
            return self._storage.read_object_bytes(object_key)
        except DocumentStorageError as error:
            raise DocumentStoreUnavailableError(
                "Transcription PAGE-XML could not be loaded."
            ) from error

    def _build_transcription_composed_pagexml(
        self,
        *,
        base_pagexml_bytes: bytes,
        candidate_pagexml_bytes: bytes,
        line_text_by_id: Mapping[str, str],
    ) -> bytes:
        try:
            base_root = ET.fromstring(base_pagexml_bytes)
            candidate_root = ET.fromstring(candidate_pagexml_bytes)
        except ET.ParseError as error:
            raise DocumentStoreUnavailableError(
                "Transcription PAGE-XML payload is invalid."
            ) from error

        required_line_ids = set(line_text_by_id.keys())
        base_line_ids = {
            str(item.get("id"))
            for item in base_root.findall(".//pc:TextLine", _PAGE_XML_NS)
            if isinstance(item.get("id"), str)
        }
        candidate_line_ids = {
            str(item.get("id"))
            for item in candidate_root.findall(".//pc:TextLine", _PAGE_XML_NS)
            if isinstance(item.get("id"), str)
        }

        if required_line_ids.issubset(base_line_ids):
            target_root = base_root
        elif required_line_ids.issubset(candidate_line_ids):
            target_root = candidate_root
        else:
            missing = sorted(
                required_line_ids - (base_line_ids | candidate_line_ids)
            )
            missing_label = ", ".join(missing[:5]) if missing else "<unknown>"
            raise DocumentTranscriptionConflictError(
                "Compared PAGE-XML payloads are missing one or more composed lines: "
                f"{missing_label}."
            )

        for line_element in target_root.findall(".//pc:TextLine", _PAGE_XML_NS):
            line_id = line_element.get("id")
            if not isinstance(line_id, str):
                continue
            if line_id not in line_text_by_id:
                continue
            self._set_pagexml_text_equiv(line_element, line_text_by_id[line_id])
        return ET.tostring(target_root, encoding="utf-8", xml_declaration=True) + b"\n"

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
        if base_run_id == candidate_run_id:
            raise DocumentValidationError(
                "baseRunId and candidateRunId must reference different runs."
            )
        document = self._store.get_document(project_id=project_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        base_run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=base_run_id,
        )
        if base_run is None:
            raise DocumentTranscriptionRunNotFoundError("Base transcription run not found.")
        candidate_run = self._store.get_transcription_run(
            project_id=project_id,
            document_id=document_id,
            run_id=candidate_run_id,
        )
        if candidate_run is None:
            raise DocumentTranscriptionRunNotFoundError(
                "Candidate transcription run not found."
            )
        if not self._transcription_runs_share_compare_basis(
            base_run=base_run,
            candidate_run=candidate_run,
        ):
            raise DocumentTranscriptionConflictError(
                "Compare requires base and candidate runs to share preprocess/layout basis and layout snapshot hash."
            )
        normalized_page_number = int(page_number) if isinstance(page_number, int) else None
        if normalized_page_number is not None and normalized_page_number < 1:
            raise DocumentValidationError("page must be 1 or greater.")
        normalized_line_id = (
            line_id.strip() if isinstance(line_id, str) and line_id.strip() else None
        )
        normalized_token_id = (
            token_id.strip() if isinstance(token_id, str) and token_id.strip() else None
        )

        base_pages = self._list_all_transcription_page_results(
            project_id=project_id,
            document_id=document_id,
            run_id=base_run.id,
        )
        candidate_pages = self._list_all_transcription_page_results(
            project_id=project_id,
            document_id=document_id,
            run_id=candidate_run.id,
        )
        decisions = self._store.list_transcription_compare_decisions(
            project_id=project_id,
            document_id=document_id,
            base_run_id=base_run.id,
            candidate_run_id=candidate_run.id,
        )
        decisions_by_key = {
            (item.page_id, item.line_id, item.token_id): item for item in decisions
        }

        page_index: dict[str, dict[str, object]] = {}
        for item in base_pages:
            page_index[item.page_id] = {
                "page_index": item.page_index,
                "base": item,
                "candidate": None,
            }
        for item in candidate_pages:
            if item.page_id in page_index:
                page_index[item.page_id]["candidate"] = item
            else:
                page_index[item.page_id] = {
                    "page_index": item.page_index,
                    "base": None,
                    "candidate": item,
                }

        selected_page_ids: set[str] | None = None
        if normalized_page_number is not None:
            selected_page_ids = {
                page_id
                for page_id, page_entry in page_index.items()
                if int(page_entry["page_index"]) + 1 == normalized_page_number
            }
            if not selected_page_ids:
                raise DocumentPageNotFoundError(
                    "Compared page target was not found for selected runs."
                )

        decisions = self._store.list_transcription_compare_decisions(
            project_id=project_id,
            document_id=document_id,
            base_run_id=base_run.id,
            candidate_run_id=candidate_run.id,
        )
        if selected_page_ids is not None:
            decisions = [item for item in decisions if item.page_id in selected_page_ids]
        if normalized_line_id is not None:
            decisions = [
                item for item in decisions if item.line_id == normalized_line_id
            ]
        if normalized_token_id is not None:
            decisions = [
                item for item in decisions if item.token_id == normalized_token_id
            ]
        decisions_by_key = {
            (item.page_id, item.line_id, item.token_id): item for item in decisions
        }
        decision_events = self._store.list_transcription_compare_decision_events(
            project_id=project_id,
            document_id=document_id,
            base_run_id=base_run.id,
            candidate_run_id=candidate_run.id,
            page_ids=(sorted(selected_page_ids) if selected_page_ids is not None else None),
        )
        if normalized_line_id is not None:
            decision_events = [
                event for event in decision_events if event.line_id == normalized_line_id
            ]
        if normalized_token_id is not None:
            decision_events = [
                event for event in decision_events if event.token_id == normalized_token_id
            ]

        page_snapshots: list[DocumentTranscriptionComparePageSnapshot] = []
        total_changed_lines = 0
        total_changed_tokens = 0
        total_changed_confidence = 0
        matched_line_filter = normalized_line_id is None
        matched_token_filter = normalized_token_id is None
        for page_id, page_entry in sorted(
            page_index.items(),
            key=lambda item: (int(item[1]["page_index"]), item[0]),
        ):
            if selected_page_ids is not None and page_id not in selected_page_ids:
                continue
            base_page = page_entry["base"]  # type: ignore[assignment]
            candidate_page = page_entry["candidate"]  # type: ignore[assignment]
            page_number = int(page_entry["page_index"])
            base_lines_raw = (
                self._store.list_line_transcription_results(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=base_run.id,
                    page_id=page_id,
                )
                if base_page is not None
                else []
            )
            candidate_lines_raw = (
                self._store.list_line_transcription_results(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=candidate_run.id,
                    page_id=page_id,
                )
                if candidate_page is not None
                else []
            )
            base_lines = self._hydrate_transcription_lines_with_active_versions(
                project_id=project_id,
                document_id=document_id,
                run_id=base_run.id,
                page_id=page_id,
                rows=base_lines_raw,
            )
            candidate_lines = self._hydrate_transcription_lines_with_active_versions(
                project_id=project_id,
                document_id=document_id,
                run_id=candidate_run.id,
                page_id=page_id,
                rows=candidate_lines_raw,
            )
            base_lines_by_id = {line.line_id: line for line in base_lines}
            candidate_lines_by_id = {line.line_id: line for line in candidate_lines}
            line_ids = sorted(
                set(base_lines_by_id)
                | set(candidate_lines_by_id)
                | {
                    item.line_id
                    for item in decisions
                    if item.page_id == page_id and item.line_id is not None
                }
            )
            if normalized_line_id is not None:
                line_ids = [item for item in line_ids if item == normalized_line_id]
            line_diffs: list[DocumentTranscriptionCompareLineDiffSnapshot] = []
            page_changed_confidence = 0
            for target_line_id in line_ids:
                matched_line_filter = True
                base_line = base_lines_by_id.get(target_line_id)
                candidate_line = candidate_lines_by_id.get(target_line_id)
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
                    or base_line.schema_validation_status
                    != candidate_line.schema_validation_status
                    or base_line.token_anchor_status != candidate_line.token_anchor_status
                    or confidence_delta is not None
                )
                decision_row = decisions_by_key.get((page_id, target_line_id, None))
                if changed or decision_row is not None:
                    line_diffs.append(
                        DocumentTranscriptionCompareLineDiffSnapshot(
                            line_id=target_line_id,
                            base_line=base_line,
                            candidate_line=candidate_line,
                            changed=changed,
                            confidence_delta=confidence_delta,
                            current_decision=decision_row,
                        )
                    )
                if confidence_delta is not None:
                    page_changed_confidence += 1

            base_tokens = (
                self._store.list_token_transcription_results(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=base_run.id,
                    page_id=page_id,
                )
                if base_page is not None
                else []
            )
            candidate_tokens = (
                self._store.list_token_transcription_results(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=candidate_run.id,
                    page_id=page_id,
                )
                if candidate_page is not None
                else []
            )
            base_tokens_by_id = {token.token_id: token for token in base_tokens}
            candidate_tokens_by_id = {token.token_id: token for token in candidate_tokens}
            token_ids = sorted(
                set(base_tokens_by_id)
                | set(candidate_tokens_by_id)
                | {
                    item.token_id
                    for item in decisions
                    if item.page_id == page_id and item.token_id is not None
                }
            )
            if normalized_token_id is not None:
                token_ids = [item for item in token_ids if item == normalized_token_id]
            token_diffs: list[DocumentTranscriptionCompareTokenDiffSnapshot] = []
            for target_token_id in token_ids:
                matched_token_filter = True
                base_token = base_tokens_by_id.get(target_token_id)
                candidate_token = candidate_tokens_by_id.get(target_token_id)
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
                    or base_token.line_id != candidate_token.line_id
                    or base_token.source_kind != candidate_token.source_kind
                    or base_token.source_ref_id != candidate_token.source_ref_id
                    or base_token.token_index != candidate_token.token_index
                    or confidence_delta is not None
                )
                token_line_id = (
                    base_token.line_id
                    if base_token is not None
                    else candidate_token.line_id if candidate_token is not None else None
                )
                if normalized_line_id is not None and token_line_id != normalized_line_id:
                    continue
                decision_row = decisions_by_key.get(
                    (page_id, token_line_id, target_token_id)
                )
                if changed or decision_row is not None:
                    token_diffs.append(
                        DocumentTranscriptionCompareTokenDiffSnapshot(
                            token_id=target_token_id,
                            token_index=(
                                base_token.token_index
                                if base_token is not None
                                else (
                                    candidate_token.token_index
                                    if candidate_token is not None
                                    else None
                                )
                            ),
                            line_id=token_line_id,
                            base_token=base_token,
                            candidate_token=candidate_token,
                            changed=changed,
                            confidence_delta=confidence_delta,
                            current_decision=decision_row,
                        )
                    )
            if (
                (normalized_line_id is not None or normalized_token_id is not None)
                and not line_diffs
                and not token_diffs
            ):
                continue

            base_projection = (
                self._store.get_transcription_output_projection(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=base_run.id,
                    page_id=page_id,
                )
                if base_page is not None
                else None
            )
            candidate_projection = (
                self._store.get_transcription_output_projection(
                    project_id=project_id,
                    document_id=document_id,
                    run_id=candidate_run.id,
                    page_id=page_id,
                )
                if candidate_page is not None
                else None
            )

            page_snapshot = DocumentTranscriptionComparePageSnapshot(
                page_id=page_id,
                page_index=page_number,
                base_page=base_page,
                candidate_page=candidate_page,
                line_diffs=line_diffs,
                token_diffs=token_diffs,
                changed_line_count=sum(1 for item in line_diffs if item.changed),
                changed_token_count=sum(1 for item in token_diffs if item.changed),
                changed_confidence_count=page_changed_confidence,
                output_availability={
                    "basePageXml": bool(
                        base_page is not None
                        and base_page.status == "SUCCEEDED"
                        and (
                            (
                                base_projection is not None
                                and base_projection.corrected_pagexml_key
                            )
                            or base_page.pagexml_out_key
                        )
                    ),
                    "baseRawResponse": bool(
                        base_page is not None and base_page.raw_model_response_sha256
                    ),
                    "baseHocr": bool(base_page is not None and base_page.hocr_out_key),
                    "candidatePageXml": bool(
                        candidate_page is not None
                        and candidate_page.status == "SUCCEEDED"
                        and (
                            (
                                candidate_projection is not None
                                and candidate_projection.corrected_pagexml_key
                            )
                            or candidate_page.pagexml_out_key
                        )
                    ),
                    "candidateRawResponse": bool(
                        candidate_page is not None
                        and candidate_page.raw_model_response_sha256
                    ),
                    "candidateHocr": bool(
                        candidate_page is not None and candidate_page.hocr_out_key
                    ),
                },
            )
            page_snapshots.append(page_snapshot)
            total_changed_lines += page_snapshot.changed_line_count
            total_changed_tokens += page_snapshot.changed_token_count
            total_changed_confidence += page_snapshot.changed_confidence_count

        if not matched_line_filter:
            raise DocumentPageNotFoundError("Compared line target was not found.")
        if not matched_token_filter:
            raise DocumentPageNotFoundError("Compared token target was not found.")

        compare_decision_snapshot_hash = (
            self._compute_transcription_compare_decision_snapshot_hash(
                decisions=decisions,
                events=decision_events,
            )
        )
        return DocumentTranscriptionCompareSnapshot(
            document=document,
            base_run=base_run,
            candidate_run=candidate_run,
            pages=page_snapshots,
            changed_line_count=total_changed_lines,
            changed_token_count=total_changed_tokens,
            changed_confidence_count=total_changed_confidence,
            base_engine_metadata=self._build_transcription_engine_metadata(base_run),
            candidate_engine_metadata=self._build_transcription_engine_metadata(
                candidate_run
            ),
            compare_decision_snapshot_hash=compare_decision_snapshot_hash,
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
        items: Sequence[dict[str, object]],
    ) -> list[TranscriptionCompareDecisionRecord]:
        self._require_transcription_mutation_access(
            current_user=current_user,
            project_id=project_id,
        )
        if not items:
            raise DocumentValidationError("Compare decision payload cannot be empty.")
        compare_snapshot = self.compare_transcription_runs(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            base_run_id=base_run_id,
            candidate_run_id=candidate_run_id,
        )
        page_ids = {page.page_id for page in compare_snapshot.pages}
        persisted: list[TranscriptionCompareDecisionRecord] = []
        for raw_item in items:
            page_id = str(raw_item.get("pageId") or "").strip()
            if not page_id:
                raise DocumentValidationError("Compare decision item requires pageId.")
            if page_id not in page_ids:
                raise DocumentTranscriptionConflictError(
                    "Compare decision pageId does not belong to the selected compare snapshot."
                )
            line_id = (
                str(raw_item["lineId"]).strip()
                if isinstance(raw_item.get("lineId"), str)
                and str(raw_item["lineId"]).strip()
                else None
            )
            token_id = (
                str(raw_item["tokenId"]).strip()
                if isinstance(raw_item.get("tokenId"), str)
                and str(raw_item["tokenId"]).strip()
                else None
            )
            decision_raw = raw_item.get("decision")
            if not isinstance(decision_raw, str):
                raise DocumentValidationError(
                    "Compare decision item requires decision."
                )
            decision = self._normalize_transcription_compare_decision(decision_raw)
            reason = (
                str(raw_item["decisionReason"]).strip()
                if isinstance(raw_item.get("decisionReason"), str)
                and str(raw_item["decisionReason"]).strip()
                else None
            )
            expected_decision_etag = (
                str(raw_item["decisionEtag"]).strip()
                if isinstance(raw_item.get("decisionEtag"), str)
                and str(raw_item["decisionEtag"]).strip()
                else None
            )
            try:
                persisted_item = self._store.record_transcription_compare_decision(
                    project_id=project_id,
                    document_id=document_id,
                    base_run_id=base_run_id,
                    candidate_run_id=candidate_run_id,
                    page_id=page_id,
                    line_id=line_id,
                    token_id=token_id,
                    decision=decision,
                    decided_by=current_user.user_id,
                    decision_reason=reason,
                    expected_decision_etag=expected_decision_etag,
                )
            except DocumentTranscriptionRunConflictError as error:
                raise DocumentTranscriptionConflictError(str(error)) from error
            persisted.append(persisted_item)
        return persisted

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
        active_layout_version = self._store.get_layout_active_version(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        overlay_cache_key = self._cache_key_parts(
            "layout-overlay",
            page_result.overlay_json_key,
            page_result.overlay_json_sha256,
            active_layout_version.id if active_layout_version is not None else None,
            active_layout_version.version_etag if active_layout_version is not None else None,
        )
        cached_overlay = self._get_cached_overlay_asset(cache_key=overlay_cache_key)
        if cached_overlay is not None:
            return cached_overlay
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
        overlay_asset = DocumentLayoutOverlayAsset(
            payload=enriched_payload,
            etag_seed=enriched_sha,
        )
        self._set_cached_overlay_asset(
            cache_key=overlay_cache_key,
            value=overlay_asset,
        )
        return overlay_asset

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
        thumbnail_cache_key = self._cache_key_parts(
            "layout-thumbnail",
            object_key,
            page_result.active_layout_version_id,
        )
        payload = self._get_cached_thumbnail_bytes(cache_key=thumbnail_cache_key)
        if payload is None:
            try:
                payload = self._storage.read_object_bytes(object_key)
            except DocumentStorageError as error:
                raise DocumentPageAssetNotReadyError(
                    "Layout page thumbnail is not ready."
                ) from error
            self._set_cached_thumbnail_bytes(
                cache_key=thumbnail_cache_key,
                payload=payload,
            )
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
            thumbnail_cache_key = self._cache_key_parts(
                "document-thumbnail",
                page.thumbnail_key,
                page.thumbnail_sha256,
            )
            payload = self._get_cached_thumbnail_bytes(cache_key=thumbnail_cache_key)
            if payload is None:
                payload = self._storage.read_object_bytes(page.thumbnail_key)
                self._set_cached_thumbnail_bytes(
                    cache_key=thumbnail_cache_key,
                    payload=payload,
                )
            return DocumentPageImageAsset(
                payload=payload,
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
    "DocumentTranscriptionCompareSnapshot",
    "get_document_service",
]
