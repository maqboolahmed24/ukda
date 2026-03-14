from dataclasses import dataclass
from datetime import datetime
from typing import Literal

DocumentStatus = Literal[
    "UPLOADING",
    "QUEUED",
    "SCANNING",
    "EXTRACTING",
    "READY",
    "FAILED",
    "CANCELED",
]

DocumentImportStatus = Literal[
    "UPLOADING",
    "QUEUED",
    "SCANNING",
    "ACCEPTED",
    "REJECTED",
    "FAILED",
    "CANCELED",
]

DocumentSort = Literal["updated", "created", "name"]
SortDirection = Literal["asc", "desc"]
DocumentProcessingRunKind = Literal["UPLOAD", "SCAN", "EXTRACTION", "THUMBNAIL_RENDER"]
DocumentProcessingRunStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
DocumentUploadSessionStatus = Literal[
    "ACTIVE",
    "ASSEMBLING",
    "FAILED",
    "CANCELED",
    "COMPLETED",
]
PageStatus = Literal["PENDING", "READY", "FAILED", "CANCELED"]
PreprocessRunStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
PreprocessRunScope = Literal["FULL_DOCUMENT", "PAGE_SUBSET", "COMPOSED_FULL_DOCUMENT"]
PreprocessPageResultStatus = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
]
PreprocessQualityGateStatus = Literal["PASS", "REVIEW_REQUIRED", "BLOCKED"]
LayoutRunKind = Literal["AUTO"]
LayoutRunStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
PageLayoutResultStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
PageRecallStatus = Literal["COMPLETE", "NEEDS_RESCUE", "NEEDS_MANUAL_REVIEW"]
LayoutVersionKind = Literal["SEGMENTATION_EDIT", "READING_ORDER_EDIT"]
LayoutRescueCandidateKind = Literal["LINE_EXPANSION", "PAGE_WINDOW"]
LayoutRescueCandidateStatus = Literal["PENDING", "ACCEPTED", "REJECTED", "RESOLVED"]
LayoutActivationBlockerCode = Literal[
    "LAYOUT_RUN_NOT_SUCCEEDED",
    "LAYOUT_RECALL_PAGE_RESULTS_MISSING",
    "LAYOUT_RECALL_STATUS_MISSING",
    "LAYOUT_RECALL_STATUS_UNRESOLVED",
    "LAYOUT_RECALL_CHECK_MISSING",
    "LAYOUT_RESCUE_PENDING",
    "LAYOUT_RESCUE_ACCEPTANCE_MISSING",
]
LayoutReadingOrderMode = Literal["ORDERED", "UNORDERED", "WITHHELD"]
TranscriptionRunEngine = Literal[
    "VLM_LINE_CONTEXT",
    "REVIEW_COMPOSED",
    "KRAKEN_LINE",
    "TROCR_LINE",
    "DAN_PAGE",
]
TranscriptionRunStatus = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
]
TranscriptionConfidenceBasis = Literal[
    "MODEL_NATIVE",
    "READ_AGREEMENT",
    "FALLBACK_DISAGREEMENT",
]
TranscriptionLineSchemaValidationStatus = Literal[
    "VALID",
    "FALLBACK_USED",
    "INVALID",
]
TokenAnchorStatus = Literal["CURRENT", "STALE", "REFRESH_REQUIRED"]
TranscriptionTokenSourceKind = Literal["LINE", "RESCUE_CANDIDATE", "PAGE_WINDOW"]
TranscriptionProjectionBasis = Literal["ENGINE_OUTPUT", "REVIEW_CORRECTED"]
ApprovedModelType = Literal["VLM", "LLM", "HTR"]
ApprovedModelRole = Literal[
    "TRANSCRIPTION_PRIMARY",
    "TRANSCRIPTION_FALLBACK",
    "ASSIST",
]
ApprovedModelServingInterface = Literal[
    "OPENAI_CHAT",
    "OPENAI_EMBEDDING",
    "ENGINE_NATIVE",
    "RULES_NATIVE",
]
ApprovedModelStatus = Literal["APPROVED", "DEPRECATED", "ROLLED_BACK"]
ProjectModelAssignmentStatus = Literal["DRAFT", "ACTIVE", "RETIRED"]
TrainingDatasetKind = Literal["TRANSCRIPTION_TRAINING"]
SourceColorMode = Literal["RGB", "RGBA", "GRAY", "CMYK", "UNKNOWN"]
DownstreamBasisState = Literal["NOT_STARTED", "CURRENT", "STALE"]


@dataclass(frozen=True)
class DocumentRecord:
    id: str
    project_id: str
    original_filename: str
    stored_filename: str | None
    content_type_detected: str | None
    bytes: int | None
    sha256: str | None
    page_count: int | None
    status: DocumentStatus
    created_by: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DocumentImportRecord:
    id: str
    document_id: str
    status: DocumentImportStatus
    failure_reason: str | None
    created_by: str
    accepted_at: datetime | None
    rejected_at: datetime | None
    canceled_by: str | None
    canceled_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DocumentListFilters:
    q: str | None = None
    status: DocumentStatus | None = None
    uploader: str | None = None
    from_timestamp: datetime | None = None
    to_timestamp: datetime | None = None
    sort: DocumentSort = "updated"
    direction: SortDirection = "desc"
    cursor: int = 0
    page_size: int = 50


@dataclass(frozen=True)
class DocumentImportSnapshot:
    import_record: DocumentImportRecord
    document_record: DocumentRecord


@dataclass(frozen=True)
class DocumentProcessingRunRecord:
    id: str
    document_id: str
    attempt_number: int
    run_kind: DocumentProcessingRunKind
    supersedes_processing_run_id: str | None
    superseded_by_processing_run_id: str | None
    status: DocumentProcessingRunStatus
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    canceled_by: str | None
    canceled_at: datetime | None
    failure_reason: str | None


@dataclass(frozen=True)
class DocumentPageRecord:
    id: str
    document_id: str
    page_index: int
    width: int
    height: int
    dpi: int | None
    source_width: int
    source_height: int
    source_dpi: int | None
    source_color_mode: SourceColorMode
    status: PageStatus
    derived_image_key: str | None
    derived_image_sha256: str | None
    thumbnail_key: str | None
    thumbnail_sha256: str | None
    failure_reason: str | None
    canceled_by: str | None
    canceled_at: datetime | None
    viewer_rotation: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DocumentUploadSessionRecord:
    id: str
    project_id: str
    document_id: str
    import_id: str
    original_filename: str
    status: DocumentUploadSessionStatus
    expected_sha256: str | None
    expected_total_bytes: int | None
    bytes_received: int
    last_chunk_index: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    canceled_at: datetime | None
    failure_reason: str | None


@dataclass(frozen=True)
class PreprocessRunRecord:
    id: str
    project_id: str
    document_id: str
    parent_run_id: str | None
    attempt_number: int
    superseded_by_run_id: str | None
    profile_id: str
    params_json: dict[str, object]
    params_hash: str
    pipeline_version: str
    container_digest: str
    status: PreprocessRunStatus
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None
    profile_version: str = "v1"
    profile_revision: int = 1
    profile_label: str = ""
    profile_description: str = ""
    profile_params_hash: str = ""
    profile_is_advanced: bool = False
    profile_is_gated: bool = False
    manifest_object_key: str | None = None
    manifest_sha256: str | None = None
    manifest_schema_version: int = 1
    run_scope: PreprocessRunScope = "FULL_DOCUMENT"
    target_page_ids_json: list[str] | None = None
    composed_from_run_ids_json: list[str] | None = None


@dataclass(frozen=True)
class PagePreprocessResultRecord:
    run_id: str
    page_id: str
    page_index: int
    status: PreprocessPageResultStatus
    quality_gate_status: PreprocessQualityGateStatus
    input_object_key: str | None
    output_object_key_gray: str | None
    output_object_key_bin: str | None
    metrics_json: dict[str, object]
    sha256_gray: str | None
    sha256_bin: str | None
    warnings_json: list[str]
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
    input_sha256: str | None = None
    source_result_run_id: str | None = None
    metrics_object_key: str | None = None
    metrics_sha256: str | None = None


@dataclass(frozen=True)
class LayoutRunRecord:
    id: str
    project_id: str
    document_id: str
    input_preprocess_run_id: str
    run_kind: LayoutRunKind
    parent_run_id: str | None
    attempt_number: int
    superseded_by_run_id: str | None
    model_id: str | None
    profile_id: str | None
    params_json: dict[str, object]
    params_hash: str
    pipeline_version: str
    container_digest: str
    status: LayoutRunStatus
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None
    activation_gate: "LayoutActivationGateRecord | None" = None


@dataclass(frozen=True)
class LayoutActivationBlockerRecord:
    code: LayoutActivationBlockerCode
    message: str
    count: int
    page_ids: tuple[str, ...] = ()
    page_numbers: tuple[int, ...] = ()


@dataclass(frozen=True)
class LayoutActivationDownstreamImpactRecord:
    transcription_state_after_activation: DownstreamBasisState
    invalidates_existing_transcription_basis: bool
    reason: str | None
    has_active_transcription_projection: bool
    active_transcription_run_id: str | None


@dataclass(frozen=True)
class LayoutActivationGateRecord:
    eligible: bool
    blocker_count: int
    blockers: tuple[LayoutActivationBlockerRecord, ...]
    evaluated_at: datetime
    downstream_impact: LayoutActivationDownstreamImpactRecord


@dataclass(frozen=True)
class PageLayoutResultRecord:
    run_id: str
    page_id: str
    page_index: int
    status: PageLayoutResultStatus
    page_recall_status: PageRecallStatus
    active_layout_version_id: str | None
    page_xml_key: str | None
    overlay_json_key: str | None
    page_xml_sha256: str | None
    overlay_json_sha256: str | None
    metrics_json: dict[str, object]
    warnings_json: list[str]
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LayoutRecallCheckRecord:
    run_id: str
    page_id: str
    recall_check_version: str
    missed_text_risk_score: float | None
    signals_json: dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class LayoutRescueCandidateRecord:
    id: str
    run_id: str
    page_id: str
    candidate_kind: LayoutRescueCandidateKind
    geometry_json: dict[str, object]
    confidence: float | None
    source_signal: str | None
    status: LayoutRescueCandidateStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LayoutVersionRecord:
    id: str
    run_id: str
    page_id: str
    base_version_id: str | None
    superseded_by_version_id: str | None
    version_kind: LayoutVersionKind
    version_etag: str
    page_xml_key: str
    overlay_json_key: str
    page_xml_sha256: str
    overlay_json_sha256: str
    run_snapshot_hash: str
    canonical_payload_json: dict[str, object]
    reading_order_groups_json: list[dict[str, object]]
    reading_order_meta_json: dict[str, object]
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class LayoutLineArtifactRecord:
    run_id: str
    page_id: str
    layout_version_id: str
    line_id: str
    region_id: str | None
    line_crop_key: str
    region_crop_key: str | None
    page_thumbnail_key: str
    context_window_json_key: str
    artifacts_sha256: str
    created_at: datetime


@dataclass(frozen=True)
class ApprovedModelRecord:
    id: str
    model_type: ApprovedModelType
    model_role: ApprovedModelRole
    model_family: str
    model_version: str
    serving_interface: ApprovedModelServingInterface
    engine_family: str
    deployment_unit: str
    artifact_subpath: str
    checksum_sha256: str
    runtime_profile: str
    response_contract_version: str
    metadata_json: dict[str, object]
    status: ApprovedModelStatus
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ProjectModelAssignmentRecord:
    id: str
    project_id: str
    model_role: ApprovedModelRole
    approved_model_id: str
    status: ProjectModelAssignmentStatus
    assignment_reason: str
    created_by: str
    created_at: datetime
    activated_by: str | None
    activated_at: datetime | None
    retired_by: str | None
    retired_at: datetime | None


@dataclass(frozen=True)
class TrainingDatasetRecord:
    id: str
    project_id: str
    source_approved_model_id: str | None
    project_model_assignment_id: str | None
    dataset_kind: TrainingDatasetKind
    page_count: int
    storage_key: str
    dataset_sha256: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class TranscriptionRunRecord:
    id: str
    project_id: str
    document_id: str
    input_preprocess_run_id: str
    input_layout_run_id: str
    input_layout_snapshot_hash: str
    engine: TranscriptionRunEngine
    model_id: str
    project_model_assignment_id: str | None
    prompt_template_id: str | None
    prompt_template_sha256: str | None
    response_schema_version: int
    confidence_basis: TranscriptionConfidenceBasis
    confidence_calibration_version: str
    params_json: dict[str, object]
    pipeline_version: str
    container_digest: str
    attempt_number: int
    supersedes_transcription_run_id: str | None
    superseded_by_transcription_run_id: str | None
    status: TranscriptionRunStatus
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    canceled_by: str | None
    canceled_at: datetime | None
    failure_reason: str | None


@dataclass(frozen=True)
class PageTranscriptionResultRecord:
    run_id: str
    page_id: str
    page_index: int
    status: TranscriptionRunStatus
    pagexml_out_key: str | None
    pagexml_out_sha256: str | None
    raw_model_response_key: str | None
    raw_model_response_sha256: str | None
    hocr_out_key: str | None
    hocr_out_sha256: str | None
    metrics_json: dict[str, object]
    warnings_json: list[str]
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LineTranscriptionResultRecord:
    run_id: str
    page_id: str
    line_id: str
    text_diplomatic: str
    conf_line: float | None
    confidence_basis: TranscriptionConfidenceBasis
    confidence_calibration_version: str
    alignment_json_key: str | None
    char_boxes_key: str | None
    schema_validation_status: TranscriptionLineSchemaValidationStatus
    flags_json: dict[str, object]
    machine_output_sha256: str | None
    active_transcript_version_id: str | None
    version_etag: str
    token_anchor_status: TokenAnchorStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class TokenTranscriptionResultRecord:
    run_id: str
    page_id: str
    line_id: str | None
    token_id: str
    token_index: int
    token_text: str
    token_confidence: float | None
    bbox_json: dict[str, object] | None
    polygon_json: dict[str, object] | None
    source_kind: TranscriptionTokenSourceKind
    source_ref_id: str
    projection_basis: TranscriptionProjectionBasis
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class TranscriptVersionRecord:
    id: str
    run_id: str
    page_id: str
    line_id: str
    base_version_id: str | None
    superseded_by_version_id: str | None
    version_etag: str
    text_diplomatic: str
    editor_user_id: str
    edit_reason: str | None
    created_at: datetime


@dataclass(frozen=True)
class DocumentTranscriptionProjectionRecord:
    document_id: str
    project_id: str
    active_transcription_run_id: str | None
    active_layout_run_id: str | None
    active_layout_snapshot_hash: str | None
    active_preprocess_run_id: str | None
    downstream_redaction_state: DownstreamBasisState
    downstream_redaction_invalidated_at: datetime | None
    downstream_redaction_invalidated_reason: str | None
    updated_at: datetime


@dataclass(frozen=True)
class TranscriptionOutputProjectionRecord:
    run_id: str
    document_id: str
    page_id: str
    corrected_pagexml_key: str
    corrected_pagexml_sha256: str
    corrected_text_sha256: str
    source_pagexml_sha256: str
    updated_at: datetime


@dataclass(frozen=True)
class DocumentPreprocessProjectionRecord:
    document_id: str
    project_id: str
    active_preprocess_run_id: str | None
    active_profile_id: str | None
    updated_at: datetime
    active_profile_version: str | None = None
    active_profile_revision: int | None = None
    active_params_hash: str | None = None
    active_pipeline_version: str | None = None
    active_container_digest: str | None = None
    layout_basis_state: DownstreamBasisState = "NOT_STARTED"
    layout_basis_run_id: str | None = None
    transcription_basis_state: DownstreamBasisState = "NOT_STARTED"
    transcription_basis_run_id: str | None = None


@dataclass(frozen=True)
class DocumentLayoutProjectionRecord:
    document_id: str
    project_id: str
    active_layout_run_id: str | None
    active_input_preprocess_run_id: str | None
    updated_at: datetime
    active_layout_snapshot_hash: str | None = None
    downstream_transcription_state: DownstreamBasisState = "NOT_STARTED"
    downstream_transcription_invalidated_at: datetime | None = None
    downstream_transcription_invalidated_reason: str | None = None


@dataclass(frozen=True)
class PreprocessDownstreamBasisReferencesRecord:
    has_layout_projection: bool
    layout_active_input_preprocess_run_id: str | None
    has_transcription_projection: bool
    transcription_active_preprocess_run_id: str | None


@dataclass(frozen=True)
class PreprocessProfileRegistryRecord:
    profile_id: str
    profile_version: str
    profile_revision: int
    label: str
    description: str
    params_json: dict[str, object]
    params_hash: str
    is_advanced: bool
    is_gated: bool
    supersedes_profile_id: str | None
    supersedes_profile_revision: int | None
    created_at: datetime
