from __future__ import annotations

from datetime import date, datetime, time, timezone
from time import sleep
from typing import Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.documents.models import (
    DocumentTranscriptionProjectionRecord,
    LineTranscriptionResultRecord,
    PageTranscriptionResultRecord,
    TranscriptVersionRecord,
    TranscriptVariantLayerRecord,
    TranscriptVariantSuggestionEventRecord,
    TranscriptVariantSuggestionRecord,
    TranscriptionOutputProjectionRecord,
    TranscriptionCompareDecisionRecord,
    TokenTranscriptionResultRecord,
    TranscriptionRunRecord,
    DocumentLayoutProjectionRecord,
    LayoutActivationGateRecord,
    DocumentPreprocessProjectionRecord,
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
    DocumentRecord,
)
from app.documents.service import (
    DocumentTranscriptionAccessDeniedError,
    DocumentTranscriptionCompareSnapshot,
    DocumentTranscriptionConflictError,
    DocumentTranscriptionLineCorrectionSnapshot,
    DocumentTranscriptionMetricsSnapshot,
    DocumentTranscriptionOverviewSnapshot,
    DocumentTranscriptionRunNotFoundError,
    DocumentTranscriptionTriagePageSnapshot,
    DocumentTranscriptionVariantLayersSnapshot,
    DocumentTranscriptionVariantSuggestionDecisionSnapshot,
    DocumentLayoutAccessDeniedError,
    DocumentLayoutConflictError,
    DocumentLayoutContextWindowAsset,
    DocumentLayoutElementsSnapshot,
    DocumentLayoutLineArtifactsSnapshot,
    DocumentLayoutReadingOrderSnapshot,
    DocumentLayoutPageRecallStatusSnapshot,
    DocumentLayoutPageXmlAsset,
    DocumentLayoutOverlayAsset,
    DocumentLayoutRunNotFoundError,
    DocumentPageVariantAvailability,
    DocumentPreprocessConflictError,
    DocumentPreprocessRunNotFoundError,
    DocumentPreprocessAccessDeniedError,
    DocumentImportConflictError,
    DocumentImportNotFoundError,
    DocumentNotFoundError,
    DocumentPageAssetNotReadyError,
    DocumentPageNotFoundError,
    DocumentProcessingRunNotFoundError,
    DocumentQuotaExceededError,
    DocumentRetryAccessDeniedError,
    DocumentRetryConflictError,
    DocumentScannerUnavailableError,
    DocumentService,
    DocumentStoreUnavailableError,
    DocumentUploadSessionSnapshot,
    DocumentUploadAccessDeniedError,
    DocumentValidationError,
    get_document_service,
)
from app.documents.store import (
    DocumentUploadSessionConflictError,
    DocumentUploadSessionNotFoundError,
)
from app.jobs.service import JobService, get_job_service
from app.projects.service import ProjectAccessDeniedError
from app.projects.store import ProjectNotFoundError

router = APIRouter(
    prefix="/projects/{project_id}",
    dependencies=[Depends(require_authenticated_user)],
)

DocumentStatusLiteral = Literal[
    "UPLOADING",
    "QUEUED",
    "SCANNING",
    "EXTRACTING",
    "READY",
    "FAILED",
    "CANCELED",
]

DocumentImportStatusLiteral = Literal[
    "UPLOADING",
    "QUEUED",
    "SCANNING",
    "ACCEPTED",
    "REJECTED",
    "FAILED",
    "CANCELED",
]

DocumentProcessingRunKindLiteral = Literal[
    "UPLOAD",
    "SCAN",
    "EXTRACTION",
    "THUMBNAIL_RENDER",
]

DocumentProcessingRunStatusLiteral = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
]

DocumentPageStatusLiteral = Literal["PENDING", "READY", "FAILED", "CANCELED"]
DocumentPageImageVariantLiteral = Literal[
    "full",
    "thumb",
    "preprocessed_gray",
    "preprocessed_bin",
]
LayoutLineArtifactCropVariantLiteral = Literal["line", "region"]
DocumentPageVariantLiteral = Literal[
    "ORIGINAL",
    "PREPROCESSED_GRAY",
    "PREPROCESSED_BIN",
]
DocumentUploadSessionStatusLiteral = Literal[
    "ACTIVE",
    "ASSEMBLING",
    "FAILED",
    "CANCELED",
    "COMPLETED",
]
PreprocessRunStatusLiteral = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
]
PreprocessRunScopeLiteral = Literal[
    "FULL_DOCUMENT",
    "PAGE_SUBSET",
    "COMPOSED_FULL_DOCUMENT",
]
PreprocessPageResultStatusLiteral = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
]
PreprocessQualityGateStatusLiteral = Literal["PASS", "REVIEW_REQUIRED", "BLOCKED"]
LayoutRunKindLiteral = Literal["AUTO"]
LayoutRunStatusLiteral = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
]
PageLayoutResultStatusLiteral = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
]
PageRecallStatusLiteral = Literal[
    "COMPLETE",
    "NEEDS_RESCUE",
    "NEEDS_MANUAL_REVIEW",
]
LayoutRescueCandidateKindLiteral = Literal["LINE_EXPANSION", "PAGE_WINDOW"]
LayoutRescueCandidateStatusLiteral = Literal[
    "PENDING",
    "ACCEPTED",
    "REJECTED",
    "RESOLVED",
]
LayoutActivationBlockerCodeLiteral = Literal[
    "LAYOUT_RUN_NOT_SUCCEEDED",
    "LAYOUT_RECALL_PAGE_RESULTS_MISSING",
    "LAYOUT_RECALL_STATUS_MISSING",
    "LAYOUT_RECALL_STATUS_UNRESOLVED",
    "LAYOUT_RECALL_CHECK_MISSING",
    "LAYOUT_RESCUE_PENDING",
    "LAYOUT_RESCUE_ACCEPTANCE_MISSING",
]
LayoutReadingOrderModeLiteral = Literal["ORDERED", "UNORDERED", "WITHHELD"]
DownstreamBasisStateLiteral = Literal["NOT_STARTED", "CURRENT", "STALE"]
TranscriptionRunEngineLiteral = Literal[
    "VLM_LINE_CONTEXT",
    "REVIEW_COMPOSED",
    "KRAKEN_LINE",
    "TROCR_LINE",
    "DAN_PAGE",
]
TranscriptionRunStatusLiteral = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
]
TranscriptionConfidenceBasisLiteral = Literal[
    "MODEL_NATIVE",
    "READ_AGREEMENT",
    "FALLBACK_DISAGREEMENT",
]
TranscriptionConfidenceBandLiteral = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
TranscriptionTokenSourceKindLiteral = Literal[
    "LINE",
    "RESCUE_CANDIDATE",
    "PAGE_WINDOW",
]
TranscriptionProjectionBasisLiteral = Literal["ENGINE_OUTPUT", "REVIEW_CORRECTED"]
TranscriptionLineSchemaValidationStatusLiteral = Literal[
    "VALID",
    "FALLBACK_USED",
    "INVALID",
]
TranscriptionFallbackReasonLiteral = Literal[
    "SCHEMA_VALIDATION_FAILED",
    "ANCHOR_RESOLUTION_FAILED",
    "CONFIDENCE_BELOW_THRESHOLD",
]
TranscriptionCompareDecisionLiteral = Literal["KEEP_BASE", "PROMOTE_CANDIDATE"]
TokenAnchorStatusLiteral = Literal["CURRENT", "STALE", "REFRESH_REQUIRED"]
TranscriptVariantKindLiteral = Literal["NORMALISED"]
TranscriptVariantSuggestionStatusLiteral = Literal["PENDING", "ACCEPTED", "REJECTED"]
TranscriptVariantSuggestionDecisionLiteral = Literal["ACCEPT", "REJECT"]
SourceColorModeLiteral = Literal["RGB", "RGBA", "GRAY", "CMYK", "UNKNOWN"]
PAGE_IMAGE_CACHE_VARY_HEADER = "Authorization"


class DocumentResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    original_filename: str = Field(serialization_alias="originalFilename")
    stored_filename: str | None = Field(default=None, serialization_alias="storedFilename")
    content_type_detected: str | None = Field(
        default=None,
        serialization_alias="contentTypeDetected",
    )
    bytes: int | None = None
    sha256: str | None = None
    page_count: int | None = Field(default=None, serialization_alias="pageCount")
    status: DocumentStatusLiteral
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class DocumentTimelineEventResponse(BaseModel):
    id: str
    attempt_number: int = Field(serialization_alias="attemptNumber")
    run_kind: DocumentProcessingRunKindLiteral = Field(serialization_alias="runKind")
    supersedes_processing_run_id: str | None = Field(
        default=None,
        serialization_alias="supersedesProcessingRunId",
    )
    superseded_by_processing_run_id: str | None = Field(
        default=None,
        serialization_alias="supersededByProcessingRunId",
    )
    status: DocumentProcessingRunStatusLiteral
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    created_by: str = Field(serialization_alias="createdBy")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    created_at: datetime = Field(serialization_alias="createdAt")


class DocumentTimelineResponse(BaseModel):
    items: list[DocumentTimelineEventResponse]


class DocumentProcessingRunStatusResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    document_id: str = Field(serialization_alias="documentId")
    attempt_number: int = Field(serialization_alias="attemptNumber")
    run_kind: DocumentProcessingRunKindLiteral = Field(serialization_alias="runKind")
    supersedes_processing_run_id: str | None = Field(
        default=None,
        serialization_alias="supersedesProcessingRunId",
    )
    superseded_by_processing_run_id: str | None = Field(
        default=None,
        serialization_alias="supersededByProcessingRunId",
    )
    status: DocumentProcessingRunStatusLiteral
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    active: bool


class DocumentProcessingRunDetailResponse(DocumentTimelineEventResponse):
    document_id: str = Field(serialization_alias="documentId")
    active: bool


class CreateUploadSessionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    original_filename: str = Field(
        alias="originalFilename",
        serialization_alias="originalFilename",
        min_length=1,
        max_length=240,
    )
    expected_sha256: str | None = Field(
        default=None,
        alias="expectedSha256",
        serialization_alias="expectedSha256",
        min_length=64,
        max_length=64,
    )
    expected_total_bytes: int | None = Field(
        default=None,
        alias="expectedTotalBytes",
        serialization_alias="expectedTotalBytes",
        gt=0,
    )


class DocumentUploadSessionResponse(BaseModel):
    session_id: str = Field(serialization_alias="sessionId")
    import_id: str = Field(serialization_alias="importId")
    document_id: str = Field(serialization_alias="documentId")
    original_filename: str = Field(serialization_alias="originalFilename")
    upload_status: DocumentUploadSessionStatusLiteral = Field(serialization_alias="uploadStatus")
    import_status: DocumentImportStatusLiteral = Field(serialization_alias="importStatus")
    document_status: DocumentStatusLiteral = Field(serialization_alias="documentStatus")
    bytes_received: int = Field(serialization_alias="bytesReceived")
    expected_total_bytes: int | None = Field(default=None, serialization_alias="expectedTotalBytes")
    expected_sha256: str | None = Field(default=None, serialization_alias="expectedSha256")
    last_chunk_index: int = Field(serialization_alias="lastChunkIndex")
    next_chunk_index: int = Field(serialization_alias="nextChunkIndex")
    chunk_size_limit_bytes: int = Field(serialization_alias="chunkSizeLimitBytes")
    upload_limit_bytes: int = Field(serialization_alias="uploadLimitBytes")
    cancel_allowed: bool = Field(serialization_alias="cancelAllowed")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class DocumentImportStatusResponse(BaseModel):
    import_id: str = Field(serialization_alias="importId")
    document_id: str = Field(serialization_alias="documentId")
    import_status: DocumentImportStatusLiteral = Field(serialization_alias="importStatus")
    document_status: DocumentStatusLiteral = Field(serialization_alias="documentStatus")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    cancel_allowed: bool = Field(serialization_alias="cancelAllowed")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class DocumentPageResponse(BaseModel):
    id: str
    document_id: str = Field(serialization_alias="documentId")
    page_index: int = Field(serialization_alias="pageIndex")
    width: int
    height: int
    dpi: int | None = None
    source_width: int = Field(serialization_alias="sourceWidth")
    source_height: int = Field(serialization_alias="sourceHeight")
    source_dpi: int | None = Field(default=None, serialization_alias="sourceDpi")
    source_color_mode: SourceColorModeLiteral = Field(
        serialization_alias="sourceColorMode"
    )
    status: DocumentPageStatusLiteral
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    viewer_rotation: int = Field(serialization_alias="viewerRotation")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class DocumentPageDetailResponse(DocumentPageResponse):
    derived_image_available: bool = Field(serialization_alias="derivedImageAvailable")
    thumbnail_available: bool = Field(serialization_alias="thumbnailAvailable")


class DocumentPageListResponse(BaseModel):
    items: list[DocumentPageResponse]


class DocumentPageVariantAvailabilityResponse(BaseModel):
    variant: DocumentPageVariantLiteral
    image_variant: DocumentPageImageVariantLiteral = Field(
        serialization_alias="imageVariant"
    )
    available: bool
    media_type: Literal["image/png", "image/jpeg"] = Field(
        serialization_alias="mediaType"
    )
    run_id: str | None = Field(default=None, serialization_alias="runId")
    result_status: PreprocessPageResultStatusLiteral | None = Field(
        default=None,
        serialization_alias="resultStatus",
    )
    quality_gate_status: PreprocessQualityGateStatusLiteral | None = Field(
        default=None,
        serialization_alias="qualityGateStatus",
    )
    warnings_json: list[str] = Field(serialization_alias="warningsJson")
    metrics_json: dict[str, object] = Field(serialization_alias="metricsJson")


class DocumentPageVariantsResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    page_id: str = Field(serialization_alias="pageId")
    requested_run_id: str | None = Field(default=None, serialization_alias="requestedRunId")
    resolved_run_id: str | None = Field(default=None, serialization_alias="resolvedRunId")
    run: PreprocessRunResponse | None = None
    variants: list[DocumentPageVariantAvailabilityResponse]


class DocumentPagePatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    viewer_rotation: int = Field(
        alias="viewerRotation",
        serialization_alias="viewerRotation",
        ge=-360,
        le=360,
    )


class CreatePreprocessRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    profile_id: str | None = Field(
        default=None,
        alias="profileId",
        serialization_alias="profileId",
        min_length=1,
        max_length=80,
    )
    params_json: dict[str, object] | None = Field(
        default=None,
        alias="paramsJson",
        serialization_alias="paramsJson",
    )
    pipeline_version: str | None = Field(
        default=None,
        alias="pipelineVersion",
        serialization_alias="pipelineVersion",
        min_length=1,
        max_length=120,
    )
    container_digest: str | None = Field(
        default=None,
        alias="containerDigest",
        serialization_alias="containerDigest",
        min_length=1,
        max_length=180,
    )
    parent_run_id: str | None = Field(
        default=None,
        alias="parentRunId",
        serialization_alias="parentRunId",
    )
    supersedes_run_id: str | None = Field(
        default=None,
        alias="supersedesRunId",
        serialization_alias="supersedesRunId",
    )
    advanced_risk_confirmed: bool | None = Field(
        default=None,
        alias="advancedRiskConfirmed",
        serialization_alias="advancedRiskConfirmed",
    )
    advanced_risk_acknowledgement: str | None = Field(
        default=None,
        alias="advancedRiskAcknowledgement",
        serialization_alias="advancedRiskAcknowledgement",
        min_length=1,
        max_length=400,
    )


class RerunPreprocessRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    profile_id: str | None = Field(
        default=None,
        alias="profileId",
        serialization_alias="profileId",
        min_length=1,
        max_length=80,
    )
    params_json: dict[str, object] | None = Field(
        default=None,
        alias="paramsJson",
        serialization_alias="paramsJson",
    )
    pipeline_version: str | None = Field(
        default=None,
        alias="pipelineVersion",
        serialization_alias="pipelineVersion",
        min_length=1,
        max_length=120,
    )
    container_digest: str | None = Field(
        default=None,
        alias="containerDigest",
        serialization_alias="containerDigest",
        min_length=1,
        max_length=180,
    )
    target_page_ids: list[str] | None = Field(
        default=None,
        alias="targetPageIds",
        serialization_alias="targetPageIds",
    )
    advanced_risk_confirmed: bool | None = Field(
        default=None,
        alias="advancedRiskConfirmed",
        serialization_alias="advancedRiskConfirmed",
    )
    advanced_risk_acknowledgement: str | None = Field(
        default=None,
        alias="advancedRiskAcknowledgement",
        serialization_alias="advancedRiskAcknowledgement",
        min_length=1,
        max_length=400,
    )


class PreprocessDownstreamImpactResponse(BaseModel):
    resolved_against_run_id: str | None = Field(
        default=None,
        serialization_alias="resolvedAgainstRunId",
    )
    layout_basis_state: DownstreamBasisStateLiteral = Field(
        serialization_alias="layoutBasisState"
    )
    layout_basis_run_id: str | None = Field(
        default=None,
        serialization_alias="layoutBasisRunId",
    )
    transcription_basis_state: DownstreamBasisStateLiteral = Field(
        serialization_alias="transcriptionBasisState"
    )
    transcription_basis_run_id: str | None = Field(
        default=None,
        serialization_alias="transcriptionBasisRunId",
    )


class PreprocessRunResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    document_id: str = Field(serialization_alias="documentId")
    parent_run_id: str | None = Field(default=None, serialization_alias="parentRunId")
    attempt_number: int = Field(serialization_alias="attemptNumber")
    run_scope: PreprocessRunScopeLiteral = Field(serialization_alias="runScope")
    target_page_ids_json: list[str] | None = Field(
        default=None,
        serialization_alias="targetPageIdsJson",
    )
    composed_from_run_ids_json: list[str] | None = Field(
        default=None,
        serialization_alias="composedFromRunIdsJson",
    )
    superseded_by_run_id: str | None = Field(
        default=None,
        serialization_alias="supersededByRunId",
    )
    profile_id: str = Field(serialization_alias="profileId")
    profile_version: str = Field(serialization_alias="profileVersion")
    profile_revision: int = Field(serialization_alias="profileRevision")
    profile_label: str = Field(serialization_alias="profileLabel")
    profile_description: str = Field(serialization_alias="profileDescription")
    profile_params_hash: str = Field(serialization_alias="profileParamsHash")
    profile_is_advanced: bool = Field(serialization_alias="profileIsAdvanced")
    profile_is_gated: bool = Field(serialization_alias="profileIsGated")
    params_json: dict[str, object] = Field(serialization_alias="paramsJson")
    params_hash: str = Field(serialization_alias="paramsHash")
    pipeline_version: str = Field(serialization_alias="pipelineVersion")
    container_digest: str = Field(serialization_alias="containerDigest")
    manifest_object_key: str | None = Field(
        default=None,
        serialization_alias="manifestObjectKey",
    )
    manifest_sha256: str | None = Field(
        default=None,
        serialization_alias="manifestSha256",
    )
    manifest_schema_version: int = Field(serialization_alias="manifestSchemaVersion")
    status: PreprocessRunStatusLiteral
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    is_active_projection: bool = Field(
        default=False,
        serialization_alias="isActiveProjection",
    )
    is_superseded: bool = Field(default=False, serialization_alias="isSuperseded")
    is_current_attempt: bool = Field(
        default=False,
        serialization_alias="isCurrentAttempt",
    )
    is_historical_attempt: bool = Field(
        default=False,
        serialization_alias="isHistoricalAttempt",
    )
    downstream_impact: PreprocessDownstreamImpactResponse = Field(
        serialization_alias="downstreamImpact"
    )


class PreprocessRunListResponse(BaseModel):
    items: list[PreprocessRunResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class PreprocessRunStatusResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    document_id: str = Field(serialization_alias="documentId")
    status: PreprocessRunStatusLiteral
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    active: bool


class PreprocessProjectionResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    active_preprocess_run_id: str | None = Field(
        default=None,
        serialization_alias="activePreprocessRunId",
    )
    active_profile_id: str | None = Field(default=None, serialization_alias="activeProfileId")
    active_profile_version: str | None = Field(
        default=None,
        serialization_alias="activeProfileVersion",
    )
    active_profile_revision: int | None = Field(
        default=None,
        serialization_alias="activeProfileRevision",
    )
    active_params_hash: str | None = Field(default=None, serialization_alias="activeParamsHash")
    active_pipeline_version: str | None = Field(
        default=None,
        serialization_alias="activePipelineVersion",
    )
    active_container_digest: str | None = Field(
        default=None,
        serialization_alias="activeContainerDigest",
    )
    selection_mode: str = Field(default="EXPLICIT_ACTIVATION", serialization_alias="selectionMode")
    downstream_default_consumer: str = Field(
        default="LAYOUT_ANALYSIS_PHASE_3",
        serialization_alias="downstreamDefaultConsumer",
    )
    downstream_default_run_id: str | None = Field(
        default=None,
        serialization_alias="downstreamDefaultRunId",
    )
    downstream_impact: PreprocessDownstreamImpactResponse = Field(
        serialization_alias="downstreamImpact"
    )
    updated_at: datetime = Field(serialization_alias="updatedAt")


class PreprocessActiveRunResponse(BaseModel):
    projection: PreprocessProjectionResponse | None
    run: PreprocessRunResponse | None


class PreprocessPageResultResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    status: PreprocessPageResultStatusLiteral
    quality_gate_status: PreprocessQualityGateStatusLiteral = Field(
        serialization_alias="qualityGateStatus"
    )
    input_object_key: str | None = Field(default=None, serialization_alias="inputObjectKey")
    input_sha256: str | None = Field(default=None, serialization_alias="inputSha256")
    source_result_run_id: str | None = Field(
        default=None,
        serialization_alias="sourceResultRunId",
    )
    output_object_key_gray: str | None = Field(
        default=None,
        serialization_alias="outputObjectKeyGray",
    )
    output_object_key_bin: str | None = Field(
        default=None,
        serialization_alias="outputObjectKeyBin",
    )
    metrics_object_key: str | None = Field(
        default=None,
        serialization_alias="metricsObjectKey",
    )
    metrics_sha256: str | None = Field(default=None, serialization_alias="metricsSha256")
    metrics_json: dict[str, object] = Field(serialization_alias="metricsJson")
    sha256_gray: str | None = Field(default=None, serialization_alias="sha256Gray")
    sha256_bin: str | None = Field(default=None, serialization_alias="sha256Bin")
    warnings_json: list[str] = Field(serialization_alias="warningsJson")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class PreprocessRunPageListResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    items: list[PreprocessPageResultResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class PreprocessQualityResponse(BaseModel):
    projection: PreprocessProjectionResponse | None
    run: PreprocessRunResponse | None
    items: list[PreprocessPageResultResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class PreprocessOverviewResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    projection: PreprocessProjectionResponse | None
    active_run: PreprocessRunResponse | None = Field(
        default=None,
        serialization_alias="activeRun",
    )
    latest_run: PreprocessRunResponse | None = Field(
        default=None,
        serialization_alias="latestRun",
    )
    total_runs: int = Field(serialization_alias="totalRuns")
    page_count: int = Field(serialization_alias="pageCount")
    active_status_counts: dict[PreprocessPageResultStatusLiteral, int] = Field(
        serialization_alias="activeStatusCounts"
    )
    active_quality_gate_counts: dict[PreprocessQualityGateStatusLiteral, int] = Field(
        serialization_alias="activeQualityGateCounts"
    )
    active_warning_count: int = Field(serialization_alias="activeWarningCount")


class PreprocessComparePageResponse(BaseModel):
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    warning_delta: int = Field(serialization_alias="warningDelta")
    added_warnings: list[str] = Field(serialization_alias="addedWarnings")
    removed_warnings: list[str] = Field(serialization_alias="removedWarnings")
    metric_deltas: dict[str, float | None] = Field(serialization_alias="metricDeltas")
    output_availability: dict[str, bool] = Field(serialization_alias="outputAvailability")
    base: PreprocessPageResultResponse | None = None
    candidate: PreprocessPageResultResponse | None = None


class PreprocessCompareResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    base_run: PreprocessRunResponse = Field(serialization_alias="baseRun")
    candidate_run: PreprocessRunResponse = Field(serialization_alias="candidateRun")
    base_warning_count: int = Field(serialization_alias="baseWarningCount")
    candidate_warning_count: int = Field(serialization_alias="candidateWarningCount")
    base_blocked_count: int = Field(serialization_alias="baseBlockedCount")
    candidate_blocked_count: int = Field(serialization_alias="candidateBlockedCount")
    items: list[PreprocessComparePageResponse]


class ActivatePreprocessRunResponse(BaseModel):
    projection: PreprocessProjectionResponse
    run: PreprocessRunResponse


class CreateLayoutRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    input_preprocess_run_id: str | None = Field(
        default=None,
        alias="inputPreprocessRunId",
        serialization_alias="inputPreprocessRunId",
        min_length=1,
        max_length=120,
    )
    model_id: str | None = Field(
        default=None,
        alias="modelId",
        serialization_alias="modelId",
        min_length=1,
        max_length=120,
    )
    profile_id: str | None = Field(
        default=None,
        alias="profileId",
        serialization_alias="profileId",
        min_length=1,
        max_length=120,
    )
    params_json: dict[str, object] | None = Field(
        default=None,
        alias="paramsJson",
        serialization_alias="paramsJson",
    )
    pipeline_version: str | None = Field(
        default=None,
        alias="pipelineVersion",
        serialization_alias="pipelineVersion",
        min_length=1,
        max_length=120,
    )
    container_digest: str | None = Field(
        default=None,
        alias="containerDigest",
        serialization_alias="containerDigest",
        min_length=1,
        max_length=180,
    )
    parent_run_id: str | None = Field(
        default=None,
        alias="parentRunId",
        serialization_alias="parentRunId",
        min_length=1,
        max_length=120,
    )
    supersedes_run_id: str | None = Field(
        default=None,
        alias="supersedesRunId",
        serialization_alias="supersedesRunId",
        min_length=1,
        max_length=120,
    )


class LayoutActivationBlockerResponse(BaseModel):
    code: LayoutActivationBlockerCodeLiteral
    message: str
    count: int
    page_ids: list[str] = Field(default_factory=list, serialization_alias="pageIds")
    page_numbers: list[int] = Field(
        default_factory=list,
        serialization_alias="pageNumbers",
    )


class LayoutActivationDownstreamImpactResponse(BaseModel):
    transcription_state_after_activation: DownstreamBasisStateLiteral = Field(
        serialization_alias="transcriptionStateAfterActivation"
    )
    invalidates_existing_transcription_basis: bool = Field(
        serialization_alias="invalidatesExistingTranscriptionBasis"
    )
    reason: str | None = None
    has_active_transcription_projection: bool = Field(
        serialization_alias="hasActiveTranscriptionProjection"
    )
    active_transcription_run_id: str | None = Field(
        default=None,
        serialization_alias="activeTranscriptionRunId",
    )


class LayoutActivationGateResponse(BaseModel):
    eligible: bool
    blocker_count: int = Field(serialization_alias="blockerCount")
    blockers: list[LayoutActivationBlockerResponse]
    evaluated_at: datetime = Field(serialization_alias="evaluatedAt")
    downstream_impact: LayoutActivationDownstreamImpactResponse = Field(
        serialization_alias="downstreamImpact"
    )


class LayoutRunResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    document_id: str = Field(serialization_alias="documentId")
    input_preprocess_run_id: str = Field(serialization_alias="inputPreprocessRunId")
    run_kind: LayoutRunKindLiteral = Field(serialization_alias="runKind")
    parent_run_id: str | None = Field(default=None, serialization_alias="parentRunId")
    attempt_number: int = Field(serialization_alias="attemptNumber")
    superseded_by_run_id: str | None = Field(
        default=None,
        serialization_alias="supersededByRunId",
    )
    model_id: str | None = Field(default=None, serialization_alias="modelId")
    profile_id: str | None = Field(default=None, serialization_alias="profileId")
    params_json: dict[str, object] = Field(serialization_alias="paramsJson")
    params_hash: str = Field(serialization_alias="paramsHash")
    pipeline_version: str = Field(serialization_alias="pipelineVersion")
    container_digest: str = Field(serialization_alias="containerDigest")
    status: LayoutRunStatusLiteral
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    is_active_projection: bool = Field(
        default=False,
        serialization_alias="isActiveProjection",
    )
    is_superseded: bool = Field(default=False, serialization_alias="isSuperseded")
    is_current_attempt: bool = Field(
        default=False,
        serialization_alias="isCurrentAttempt",
    )
    is_historical_attempt: bool = Field(
        default=False,
        serialization_alias="isHistoricalAttempt",
    )
    activation_gate: LayoutActivationGateResponse | None = Field(
        default=None,
        serialization_alias="activationGate",
    )


class LayoutRunListResponse(BaseModel):
    items: list[LayoutRunResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class LayoutRunStatusResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    document_id: str = Field(serialization_alias="documentId")
    status: LayoutRunStatusLiteral
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    active: bool


class LayoutProjectionResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    active_layout_run_id: str | None = Field(
        default=None,
        serialization_alias="activeLayoutRunId",
    )
    active_input_preprocess_run_id: str | None = Field(
        default=None,
        serialization_alias="activeInputPreprocessRunId",
    )
    active_layout_snapshot_hash: str | None = Field(
        default=None,
        serialization_alias="activeLayoutSnapshotHash",
    )
    downstream_transcription_state: DownstreamBasisStateLiteral = Field(
        default="NOT_STARTED",
        serialization_alias="downstreamTranscriptionState",
    )
    downstream_transcription_invalidated_at: datetime | None = Field(
        default=None,
        serialization_alias="downstreamTranscriptionInvalidatedAt",
    )
    downstream_transcription_invalidated_reason: str | None = Field(
        default=None,
        serialization_alias="downstreamTranscriptionInvalidatedReason",
    )
    updated_at: datetime = Field(serialization_alias="updatedAt")


class LayoutActiveRunResponse(BaseModel):
    projection: LayoutProjectionResponse | None
    run: LayoutRunResponse | None


class LayoutPageResultResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    status: PageLayoutResultStatusLiteral
    page_recall_status: PageRecallStatusLiteral = Field(
        serialization_alias="pageRecallStatus"
    )
    active_layout_version_id: str | None = Field(
        default=None,
        serialization_alias="activeLayoutVersionId",
    )
    page_xml_key: str | None = Field(default=None, serialization_alias="pageXmlKey")
    overlay_json_key: str | None = Field(default=None, serialization_alias="overlayJsonKey")
    page_xml_sha256: str | None = Field(default=None, serialization_alias="pageXmlSha256")
    overlay_json_sha256: str | None = Field(
        default=None,
        serialization_alias="overlayJsonSha256",
    )
    metrics_json: dict[str, object] = Field(serialization_alias="metricsJson")
    warnings_json: list[str] = Field(serialization_alias="warningsJson")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class LayoutRunPageListResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    items: list[LayoutPageResultResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class LayoutReadingOrderGroupResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    ordered: bool = True
    region_ids: list[str] = Field(alias="regionIds", serialization_alias="regionIds")


class LayoutReadingOrderUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    version_etag: str = Field(
        alias="versionEtag",
        serialization_alias="versionEtag",
        min_length=1,
        max_length=128,
    )
    mode: LayoutReadingOrderModeLiteral | None = None
    groups: list[LayoutReadingOrderGroupResponse] = Field(default_factory=list)


class LayoutReadingOrderUpdateResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    layout_version_id: str = Field(serialization_alias="layoutVersionId")
    version_etag: str = Field(serialization_alias="versionEtag")
    mode: LayoutReadingOrderModeLiteral
    groups: list[LayoutReadingOrderGroupResponse]
    edges: list[dict[str, str]]
    signals_json: dict[str, object] = Field(serialization_alias="signalsJson")


LayoutElementsOperationKindLiteral = Literal[
    "ADD_REGION",
    "ADD_LINE",
    "MOVE_REGION",
    "MOVE_LINE",
    "MOVE_BASELINE",
    "DELETE_REGION",
    "DELETE_LINE",
    "RETAG_REGION",
    "ASSIGN_LINE_REGION",
    "REORDER_REGION_LINES",
    "SET_REGION_READING_ORDER_INCLUDED",
]


class LayoutElementsOperationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    kind: LayoutElementsOperationKindLiteral
    region_id: str | None = Field(default=None, alias="regionId", serialization_alias="regionId")
    line_id: str | None = Field(default=None, alias="lineId", serialization_alias="lineId")
    parent_region_id: str | None = Field(
        default=None, alias="parentRegionId", serialization_alias="parentRegionId"
    )
    before_line_id: str | None = Field(
        default=None, alias="beforeLineId", serialization_alias="beforeLineId"
    )
    after_line_id: str | None = Field(
        default=None, alias="afterLineId", serialization_alias="afterLineId"
    )
    polygon: list[dict[str, float]] | None = None
    baseline: list[dict[str, float]] | None = None
    region_type: str | None = Field(
        default=None, alias="regionType", serialization_alias="regionType"
    )
    include_in_reading_order: bool | None = Field(
        default=None,
        alias="includeInReadingOrder",
        serialization_alias="includeInReadingOrder",
    )
    line_ids: list[str] | None = Field(
        default=None, alias="lineIds", serialization_alias="lineIds"
    )


class LayoutElementsUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    version_etag: str = Field(
        alias="versionEtag",
        serialization_alias="versionEtag",
        min_length=1,
        max_length=128,
    )
    operations: list[LayoutElementsOperationRequest] = Field(default_factory=list)


class LayoutElementsUpdateResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    layout_version_id: str = Field(serialization_alias="layoutVersionId")
    version_etag: str = Field(serialization_alias="versionEtag")
    operations_applied: int = Field(serialization_alias="operationsApplied")
    overlay: dict[str, object]
    downstream_transcription_invalidated: bool = Field(
        serialization_alias="downstreamTranscriptionInvalidated"
    )
    downstream_transcription_state: str | None = Field(
        default=None, serialization_alias="downstreamTranscriptionState"
    )
    downstream_transcription_invalidated_reason: str | None = Field(
        default=None, serialization_alias="downstreamTranscriptionInvalidatedReason"
    )


class LayoutLineArtifactsResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    line_id: str = Field(serialization_alias="lineId")
    region_id: str | None = Field(default=None, serialization_alias="regionId")
    artifacts_sha256: str = Field(serialization_alias="artifactsSha256")
    line_crop_path: str = Field(serialization_alias="lineCropPath")
    region_crop_path: str | None = Field(default=None, serialization_alias="regionCropPath")
    page_thumbnail_path: str = Field(serialization_alias="pageThumbnailPath")
    context_window_path: str = Field(serialization_alias="contextWindowPath")
    context_window: dict[str, object] = Field(serialization_alias="contextWindow")


class LayoutPageRecallStatusResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    page_recall_status: PageRecallStatusLiteral = Field(
        serialization_alias="pageRecallStatus"
    )
    recall_check_version: str | None = Field(
        default=None,
        serialization_alias="recallCheckVersion",
    )
    missed_text_risk_score: float | None = Field(
        default=None,
        serialization_alias="missedTextRiskScore",
    )
    signals_json: dict[str, object] = Field(serialization_alias="signalsJson")
    rescue_candidate_counts: dict[LayoutRescueCandidateStatusLiteral, int] = Field(
        serialization_alias="rescueCandidateCounts"
    )
    blocker_reason_codes: list[str] = Field(
        serialization_alias="blockerReasonCodes"
    )
    unresolved_count: int = Field(serialization_alias="unresolvedCount")


class LayoutRescueCandidateResponse(BaseModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    candidate_kind: LayoutRescueCandidateKindLiteral = Field(
        serialization_alias="candidateKind"
    )
    geometry_json: dict[str, object] = Field(serialization_alias="geometryJson")
    confidence: float | None = None
    source_signal: str | None = Field(default=None, serialization_alias="sourceSignal")
    status: LayoutRescueCandidateStatusLiteral
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class LayoutRescueCandidateListResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    items: list[LayoutRescueCandidateResponse]


class LayoutSummaryResponse(BaseModel):
    regions_detected: int | None = Field(default=None, serialization_alias="regionsDetected")
    lines_detected: int | None = Field(default=None, serialization_alias="linesDetected")
    pages_with_issues: int = Field(serialization_alias="pagesWithIssues")
    coverage_percent: float | None = Field(default=None, serialization_alias="coveragePercent")
    structure_confidence: float | None = Field(
        default=None,
        serialization_alias="structureConfidence",
    )


class LayoutOverviewResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    projection: LayoutProjectionResponse | None
    active_run: LayoutRunResponse | None = Field(
        default=None,
        serialization_alias="activeRun",
    )
    latest_run: LayoutRunResponse | None = Field(
        default=None,
        serialization_alias="latestRun",
    )
    total_runs: int = Field(serialization_alias="totalRuns")
    page_count: int = Field(serialization_alias="pageCount")
    active_status_counts: dict[PageLayoutResultStatusLiteral, int] = Field(
        serialization_alias="activeStatusCounts"
    )
    active_recall_counts: dict[PageRecallStatusLiteral, int] = Field(
        serialization_alias="activeRecallCounts"
    )
    summary: LayoutSummaryResponse


class ActivateLayoutRunResponse(BaseModel):
    projection: LayoutProjectionResponse
    run: LayoutRunResponse
    activation_gate: LayoutActivationGateResponse = Field(
        serialization_alias="activationGate"
    )


class CreateTranscriptionRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    input_preprocess_run_id: str | None = Field(
        default=None,
        alias="inputPreprocessRunId",
        serialization_alias="inputPreprocessRunId",
        min_length=1,
        max_length=120,
    )
    input_layout_run_id: str | None = Field(
        default=None,
        alias="inputLayoutRunId",
        serialization_alias="inputLayoutRunId",
        min_length=1,
        max_length=120,
    )
    engine: TranscriptionRunEngineLiteral | None = None
    model_id: str | None = Field(
        default=None,
        alias="modelId",
        serialization_alias="modelId",
        min_length=1,
        max_length=160,
    )
    project_model_assignment_id: str | None = Field(
        default=None,
        alias="projectModelAssignmentId",
        serialization_alias="projectModelAssignmentId",
        min_length=1,
        max_length=160,
    )
    prompt_template_id: str | None = Field(
        default=None,
        alias="promptTemplateId",
        serialization_alias="promptTemplateId",
        min_length=1,
        max_length=160,
    )
    prompt_template_sha256: str | None = Field(
        default=None,
        alias="promptTemplateSha256",
        serialization_alias="promptTemplateSha256",
        min_length=1,
        max_length=128,
    )
    response_schema_version: int | None = Field(
        default=None,
        alias="responseSchemaVersion",
        serialization_alias="responseSchemaVersion",
        ge=1,
    )
    confidence_basis: TranscriptionConfidenceBasisLiteral | None = Field(
        default=None,
        alias="confidenceBasis",
        serialization_alias="confidenceBasis",
    )
    confidence_calibration_version: str | None = Field(
        default=None,
        alias="confidenceCalibrationVersion",
        serialization_alias="confidenceCalibrationVersion",
        min_length=1,
        max_length=80,
    )
    params_json: dict[str, object] | None = Field(
        default=None,
        alias="paramsJson",
        serialization_alias="paramsJson",
    )
    pipeline_version: str | None = Field(
        default=None,
        alias="pipelineVersion",
        serialization_alias="pipelineVersion",
        min_length=1,
        max_length=120,
    )
    container_digest: str | None = Field(
        default=None,
        alias="containerDigest",
        serialization_alias="containerDigest",
        min_length=1,
        max_length=180,
    )
    supersedes_transcription_run_id: str | None = Field(
        default=None,
        alias="supersedesTranscriptionRunId",
        serialization_alias="supersedesTranscriptionRunId",
        min_length=1,
        max_length=120,
    )


class CreateTranscriptionFallbackRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    base_run_id: str | None = Field(
        default=None,
        alias="baseRunId",
        serialization_alias="baseRunId",
        min_length=1,
        max_length=120,
    )
    engine: TranscriptionRunEngineLiteral = "KRAKEN_LINE"
    model_id: str | None = Field(
        default=None,
        alias="modelId",
        serialization_alias="modelId",
        min_length=1,
        max_length=160,
    )
    project_model_assignment_id: str | None = Field(
        default=None,
        alias="projectModelAssignmentId",
        serialization_alias="projectModelAssignmentId",
        min_length=1,
        max_length=160,
    )
    prompt_template_id: str | None = Field(
        default=None,
        alias="promptTemplateId",
        serialization_alias="promptTemplateId",
        min_length=1,
        max_length=160,
    )
    prompt_template_sha256: str | None = Field(
        default=None,
        alias="promptTemplateSha256",
        serialization_alias="promptTemplateSha256",
        min_length=1,
        max_length=128,
    )
    response_schema_version: int | None = Field(
        default=None,
        alias="responseSchemaVersion",
        serialization_alias="responseSchemaVersion",
        ge=1,
    )
    confidence_calibration_version: str | None = Field(
        default=None,
        alias="confidenceCalibrationVersion",
        serialization_alias="confidenceCalibrationVersion",
        min_length=1,
        max_length=80,
    )
    params_json: dict[str, object] | None = Field(
        default=None,
        alias="paramsJson",
        serialization_alias="paramsJson",
    )
    pipeline_version: str | None = Field(
        default=None,
        alias="pipelineVersion",
        serialization_alias="pipelineVersion",
        min_length=1,
        max_length=120,
    )
    container_digest: str | None = Field(
        default=None,
        alias="containerDigest",
        serialization_alias="containerDigest",
        min_length=1,
        max_length=180,
    )
    fallback_reason_codes: list[TranscriptionFallbackReasonLiteral] = Field(
        default_factory=list,
        alias="fallbackReasonCodes",
        serialization_alias="fallbackReasonCodes",
    )
    fallback_confidence_threshold: float | None = Field(
        default=None,
        alias="fallbackConfidenceThreshold",
        serialization_alias="fallbackConfidenceThreshold",
        ge=0,
        le=1,
    )


class TranscriptionRunResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    document_id: str = Field(serialization_alias="documentId")
    input_preprocess_run_id: str = Field(serialization_alias="inputPreprocessRunId")
    input_layout_run_id: str = Field(serialization_alias="inputLayoutRunId")
    input_layout_snapshot_hash: str = Field(serialization_alias="inputLayoutSnapshotHash")
    engine: TranscriptionRunEngineLiteral
    model_id: str = Field(serialization_alias="modelId")
    project_model_assignment_id: str | None = Field(
        default=None,
        serialization_alias="projectModelAssignmentId",
    )
    prompt_template_id: str | None = Field(
        default=None,
        serialization_alias="promptTemplateId",
    )
    prompt_template_sha256: str | None = Field(
        default=None,
        serialization_alias="promptTemplateSha256",
    )
    response_schema_version: int = Field(serialization_alias="responseSchemaVersion")
    confidence_basis: TranscriptionConfidenceBasisLiteral = Field(
        serialization_alias="confidenceBasis"
    )
    confidence_calibration_version: str = Field(
        serialization_alias="confidenceCalibrationVersion"
    )
    params_json: dict[str, object] = Field(serialization_alias="paramsJson")
    pipeline_version: str = Field(serialization_alias="pipelineVersion")
    container_digest: str = Field(serialization_alias="containerDigest")
    attempt_number: int = Field(serialization_alias="attemptNumber")
    supersedes_transcription_run_id: str | None = Field(
        default=None,
        serialization_alias="supersedesTranscriptionRunId",
    )
    superseded_by_transcription_run_id: str | None = Field(
        default=None,
        serialization_alias="supersededByTranscriptionRunId",
    )
    status: TranscriptionRunStatusLiteral
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    is_active_projection: bool = Field(serialization_alias="isActiveProjection")
    is_superseded: bool = Field(serialization_alias="isSuperseded")
    is_current_attempt: bool = Field(serialization_alias="isCurrentAttempt")
    is_historical_attempt: bool = Field(serialization_alias="isHistoricalAttempt")


class TranscriptionRunListResponse(BaseModel):
    items: list[TranscriptionRunResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class TranscriptionRunStatusResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    document_id: str = Field(serialization_alias="documentId")
    status: TranscriptionRunStatusLiteral
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    active: bool


class TranscriptionProjectionResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    active_transcription_run_id: str | None = Field(
        default=None,
        serialization_alias="activeTranscriptionRunId",
    )
    active_layout_run_id: str | None = Field(
        default=None,
        serialization_alias="activeLayoutRunId",
    )
    active_layout_snapshot_hash: str | None = Field(
        default=None,
        serialization_alias="activeLayoutSnapshotHash",
    )
    active_preprocess_run_id: str | None = Field(
        default=None,
        serialization_alias="activePreprocessRunId",
    )
    downstream_redaction_state: DownstreamBasisStateLiteral = Field(
        serialization_alias="downstreamRedactionState"
    )
    downstream_redaction_invalidated_at: datetime | None = Field(
        default=None,
        serialization_alias="downstreamRedactionInvalidatedAt",
    )
    downstream_redaction_invalidated_reason: str | None = Field(
        default=None,
        serialization_alias="downstreamRedactionInvalidatedReason",
    )
    updated_at: datetime = Field(serialization_alias="updatedAt")


class TranscriptionActiveRunResponse(BaseModel):
    projection: TranscriptionProjectionResponse | None
    run: TranscriptionRunResponse | None


class TranscriptionPageResultResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    status: TranscriptionRunStatusLiteral
    pagexml_out_key: str | None = Field(default=None, serialization_alias="pagexmlOutKey")
    pagexml_out_sha256: str | None = Field(
        default=None,
        serialization_alias="pagexmlOutSha256",
    )
    raw_model_response_key: str | None = Field(
        default=None,
        serialization_alias="rawModelResponseKey",
    )
    raw_model_response_sha256: str | None = Field(
        default=None,
        serialization_alias="rawModelResponseSha256",
    )
    hocr_out_key: str | None = Field(default=None, serialization_alias="hocrOutKey")
    hocr_out_sha256: str | None = Field(default=None, serialization_alias="hocrOutSha256")
    metrics_json: dict[str, object] = Field(serialization_alias="metricsJson")
    warnings_json: list[str] = Field(serialization_alias="warningsJson")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class TranscriptionRunPageListResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    items: list[TranscriptionPageResultResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class TranscriptionLineResultResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    line_id: str = Field(serialization_alias="lineId")
    text_diplomatic: str = Field(serialization_alias="textDiplomatic")
    conf_line: float | None = Field(default=None, serialization_alias="confLine")
    confidence_band: TranscriptionConfidenceBandLiteral = Field(
        serialization_alias="confidenceBand"
    )
    confidence_basis: TranscriptionConfidenceBasisLiteral = Field(
        serialization_alias="confidenceBasis"
    )
    confidence_calibration_version: str = Field(
        serialization_alias="confidenceCalibrationVersion"
    )
    alignment_json_key: str | None = Field(default=None, serialization_alias="alignmentJsonKey")
    char_boxes_key: str | None = Field(default=None, serialization_alias="charBoxesKey")
    schema_validation_status: TranscriptionLineSchemaValidationStatusLiteral = Field(
        serialization_alias="schemaValidationStatus"
    )
    flags_json: dict[str, object] = Field(serialization_alias="flagsJson")
    machine_output_sha256: str | None = Field(
        default=None,
        serialization_alias="machineOutputSha256",
    )
    active_transcript_version_id: str | None = Field(
        default=None,
        serialization_alias="activeTranscriptVersionId",
    )
    version_etag: str = Field(serialization_alias="versionEtag")
    token_anchor_status: TokenAnchorStatusLiteral = Field(
        serialization_alias="tokenAnchorStatus"
    )
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class TranscriptionLineResultListResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    items: list[TranscriptionLineResultResponse]


class TranscriptionTokenResultResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    line_id: str | None = Field(default=None, serialization_alias="lineId")
    token_id: str = Field(serialization_alias="tokenId")
    token_index: int = Field(serialization_alias="tokenIndex")
    token_text: str = Field(serialization_alias="tokenText")
    token_confidence: float | None = Field(default=None, serialization_alias="tokenConfidence")
    bbox_json: dict[str, object] | None = Field(default=None, serialization_alias="bboxJson")
    polygon_json: dict[str, object] | None = Field(
        default=None,
        serialization_alias="polygonJson",
    )
    source_kind: TranscriptionTokenSourceKindLiteral = Field(serialization_alias="sourceKind")
    source_ref_id: str = Field(serialization_alias="sourceRefId")
    projection_basis: TranscriptionProjectionBasisLiteral = Field(
        serialization_alias="projectionBasis"
    )
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class TranscriptionTokenResultListResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    items: list[TranscriptionTokenResultResponse]


class TranscriptVersionResponse(BaseModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    line_id: str = Field(serialization_alias="lineId")
    base_version_id: str | None = Field(
        default=None,
        serialization_alias="baseVersionId",
    )
    superseded_by_version_id: str | None = Field(
        default=None,
        serialization_alias="supersededByVersionId",
    )
    version_etag: str = Field(serialization_alias="versionEtag")
    text_diplomatic: str = Field(serialization_alias="textDiplomatic")
    editor_user_id: str = Field(serialization_alias="editorUserId")
    edit_reason: str | None = Field(default=None, serialization_alias="editReason")
    created_at: datetime = Field(serialization_alias="createdAt")


class TranscriptionOutputProjectionResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    document_id: str = Field(serialization_alias="documentId")
    page_id: str = Field(serialization_alias="pageId")
    corrected_pagexml_key: str = Field(serialization_alias="correctedPagexmlKey")
    corrected_pagexml_sha256: str = Field(serialization_alias="correctedPagexmlSha256")
    corrected_text_sha256: str = Field(serialization_alias="correctedTextSha256")
    source_pagexml_sha256: str = Field(serialization_alias="sourcePagexmlSha256")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class CorrectTranscriptionLineRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    text_diplomatic: str = Field(
        alias="textDiplomatic",
        serialization_alias="textDiplomatic",
        min_length=1,
    )
    version_etag: str = Field(
        alias="versionEtag",
        serialization_alias="versionEtag",
        min_length=1,
        max_length=128,
    )
    edit_reason: str | None = Field(
        default=None,
        alias="editReason",
        serialization_alias="editReason",
        max_length=600,
    )


class CorrectTranscriptionLineResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    line_id: str = Field(serialization_alias="lineId")
    text_changed: bool = Field(serialization_alias="textChanged")
    line: TranscriptionLineResultResponse
    active_version: TranscriptVersionResponse = Field(serialization_alias="activeVersion")
    output_projection: TranscriptionOutputProjectionResponse = Field(
        serialization_alias="outputProjection"
    )
    downstream_redaction_invalidated: bool = Field(
        serialization_alias="downstreamRedactionInvalidated"
    )
    downstream_redaction_state: DownstreamBasisStateLiteral | None = Field(
        default=None,
        serialization_alias="downstreamRedactionState",
    )
    downstream_redaction_invalidated_at: datetime | None = Field(
        default=None,
        serialization_alias="downstreamRedactionInvalidatedAt",
    )
    downstream_redaction_invalidated_reason: str | None = Field(
        default=None,
        serialization_alias="downstreamRedactionInvalidatedReason",
    )


class TranscriptVariantSuggestionResponse(BaseModel):
    id: str
    variant_layer_id: str = Field(serialization_alias="variantLayerId")
    line_id: str | None = Field(default=None, serialization_alias="lineId")
    suggestion_text: str = Field(serialization_alias="suggestionText")
    confidence: float | None = None
    status: TranscriptVariantSuggestionStatusLiteral
    decided_by: str | None = Field(default=None, serialization_alias="decidedBy")
    decided_at: datetime | None = Field(default=None, serialization_alias="decidedAt")
    decision_reason: str | None = Field(default=None, serialization_alias="decisionReason")
    metadata_json: dict[str, object] = Field(serialization_alias="metadataJson")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class TranscriptVariantSuggestionEventResponse(BaseModel):
    id: str
    suggestion_id: str = Field(serialization_alias="suggestionId")
    variant_layer_id: str = Field(serialization_alias="variantLayerId")
    actor_user_id: str = Field(serialization_alias="actorUserId")
    decision: TranscriptVariantSuggestionDecisionLiteral
    from_status: TranscriptVariantSuggestionStatusLiteral = Field(
        serialization_alias="fromStatus"
    )
    to_status: TranscriptVariantSuggestionStatusLiteral = Field(
        serialization_alias="toStatus"
    )
    reason: str | None = None
    created_at: datetime = Field(serialization_alias="createdAt")


class TranscriptVariantLayerResponse(BaseModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    variant_kind: TranscriptVariantKindLiteral = Field(serialization_alias="variantKind")
    base_transcript_version_id: str | None = Field(
        default=None,
        serialization_alias="baseTranscriptVersionId",
    )
    base_version_set_sha256: str | None = Field(
        default=None,
        serialization_alias="baseVersionSetSha256",
    )
    base_projection_sha256: str = Field(serialization_alias="baseProjectionSha256")
    variant_text_key: str = Field(serialization_alias="variantTextKey")
    variant_text_sha256: str = Field(serialization_alias="variantTextSha256")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    suggestions: list[TranscriptVariantSuggestionResponse] = Field(default_factory=list)


class TranscriptVariantLayerListResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    variant_kind: TranscriptVariantKindLiteral = Field(serialization_alias="variantKind")
    items: list[TranscriptVariantLayerResponse]


class RecordTranscriptVariantSuggestionDecisionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    decision: TranscriptVariantSuggestionDecisionLiteral
    reason: str | None = Field(default=None, max_length=600)


class RecordTranscriptVariantSuggestionDecisionResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    variant_kind: TranscriptVariantKindLiteral = Field(serialization_alias="variantKind")
    suggestion: TranscriptVariantSuggestionResponse
    event: TranscriptVariantSuggestionEventResponse


class TranscriptionCompareDecisionResponse(BaseModel):
    id: str
    document_id: str = Field(serialization_alias="documentId")
    base_run_id: str = Field(serialization_alias="baseRunId")
    candidate_run_id: str = Field(serialization_alias="candidateRunId")
    page_id: str = Field(serialization_alias="pageId")
    line_id: str | None = Field(default=None, serialization_alias="lineId")
    token_id: str | None = Field(default=None, serialization_alias="tokenId")
    decision: TranscriptionCompareDecisionLiteral
    decision_etag: str = Field(serialization_alias="decisionEtag")
    decided_by: str = Field(serialization_alias="decidedBy")
    decided_at: datetime = Field(serialization_alias="decidedAt")
    decision_reason: str | None = Field(default=None, serialization_alias="decisionReason")


class TranscriptionCompareLineDiffResponse(BaseModel):
    line_id: str = Field(serialization_alias="lineId")
    changed: bool
    confidence_delta: float | None = Field(
        default=None,
        serialization_alias="confidenceDelta",
    )
    base: TranscriptionLineResultResponse | None = None
    candidate: TranscriptionLineResultResponse | None = None
    decision: TranscriptionCompareDecisionResponse | None = None


class TranscriptionCompareTokenDiffResponse(BaseModel):
    token_id: str = Field(serialization_alias="tokenId")
    token_index: int | None = Field(default=None, serialization_alias="tokenIndex")
    line_id: str | None = Field(default=None, serialization_alias="lineId")
    changed: bool
    confidence_delta: float | None = Field(
        default=None,
        serialization_alias="confidenceDelta",
    )
    base: TranscriptionTokenResultResponse | None = None
    candidate: TranscriptionTokenResultResponse | None = None
    decision: TranscriptionCompareDecisionResponse | None = None


class TranscriptionComparePageResponse(BaseModel):
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    changed_line_count: int = Field(serialization_alias="changedLineCount")
    changed_token_count: int = Field(serialization_alias="changedTokenCount")
    changed_confidence_count: int = Field(serialization_alias="changedConfidenceCount")
    output_availability: dict[str, bool] = Field(serialization_alias="outputAvailability")
    base: TranscriptionPageResultResponse | None = None
    candidate: TranscriptionPageResultResponse | None = None
    line_diffs: list[TranscriptionCompareLineDiffResponse] = Field(
        default_factory=list,
        serialization_alias="lineDiffs",
    )
    token_diffs: list[TranscriptionCompareTokenDiffResponse] = Field(
        default_factory=list,
        serialization_alias="tokenDiffs",
    )


class TranscriptionCompareResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    base_run: TranscriptionRunResponse = Field(serialization_alias="baseRun")
    candidate_run: TranscriptionRunResponse = Field(serialization_alias="candidateRun")
    changed_line_count: int = Field(serialization_alias="changedLineCount")
    changed_token_count: int = Field(serialization_alias="changedTokenCount")
    changed_confidence_count: int = Field(serialization_alias="changedConfidenceCount")
    base_engine_metadata: dict[str, object] = Field(
        serialization_alias="baseEngineMetadata"
    )
    candidate_engine_metadata: dict[str, object] = Field(
        serialization_alias="candidateEngineMetadata"
    )
    items: list[TranscriptionComparePageResponse]


class RecordTranscriptionCompareDecisionRequestItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    page_id: str = Field(alias="pageId", serialization_alias="pageId", min_length=1)
    line_id: str | None = Field(
        default=None,
        alias="lineId",
        serialization_alias="lineId",
        min_length=1,
        max_length=200,
    )
    token_id: str | None = Field(
        default=None,
        alias="tokenId",
        serialization_alias="tokenId",
        min_length=1,
        max_length=200,
    )
    decision: TranscriptionCompareDecisionLiteral
    decision_reason: str | None = Field(
        default=None,
        alias="decisionReason",
        serialization_alias="decisionReason",
        max_length=600,
    )
    decision_etag: str | None = Field(
        default=None,
        alias="decisionEtag",
        serialization_alias="decisionEtag",
        min_length=1,
        max_length=128,
    )


class RecordTranscriptionCompareDecisionsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    base_run_id: str = Field(
        alias="baseRunId",
        serialization_alias="baseRunId",
        min_length=1,
        max_length=120,
    )
    candidate_run_id: str = Field(
        alias="candidateRunId",
        serialization_alias="candidateRunId",
        min_length=1,
        max_length=120,
    )
    items: list[RecordTranscriptionCompareDecisionRequestItem] = Field(
        default_factory=list
    )


class RecordTranscriptionCompareDecisionsResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    base_run_id: str = Field(serialization_alias="baseRunId")
    candidate_run_id: str = Field(serialization_alias="candidateRunId")
    items: list[TranscriptionCompareDecisionResponse]


class TranscriptionTriagePageResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    status: TranscriptionRunStatusLiteral
    line_count: int = Field(serialization_alias="lineCount")
    token_count: int = Field(serialization_alias="tokenCount")
    anchor_refresh_required: int = Field(serialization_alias="anchorRefreshRequired")
    low_confidence_lines: int = Field(serialization_alias="lowConfidenceLines")
    min_confidence: float | None = Field(default=None, serialization_alias="minConfidence")
    avg_confidence: float | None = Field(default=None, serialization_alias="avgConfidence")
    warnings_json: list[str] = Field(serialization_alias="warningsJson")
    confidence_bands: dict[TranscriptionConfidenceBandLiteral, int] = Field(
        serialization_alias="confidenceBands"
    )
    issues: list[str]
    ranking_score: float = Field(serialization_alias="rankingScore")
    ranking_rationale: str = Field(serialization_alias="rankingRationale")
    reviewer_assignment_user_id: str | None = Field(
        default=None,
        serialization_alias="reviewerAssignmentUserId",
    )
    reviewer_assignment_updated_by: str | None = Field(
        default=None,
        serialization_alias="reviewerAssignmentUpdatedBy",
    )
    reviewer_assignment_updated_at: datetime | None = Field(
        default=None,
        serialization_alias="reviewerAssignmentUpdatedAt",
    )


class TranscriptionTriageResponse(BaseModel):
    projection: TranscriptionProjectionResponse | None
    run: TranscriptionRunResponse | None
    items: list[TranscriptionTriagePageResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class TranscriptionMetricsLowConfidencePageResponse(BaseModel):
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    low_confidence_lines: int = Field(serialization_alias="lowConfidenceLines")


class TranscriptionMetricsResponse(BaseModel):
    projection: TranscriptionProjectionResponse | None
    run: TranscriptionRunResponse | None
    review_confidence_threshold: float = Field(
        serialization_alias="reviewConfidenceThreshold"
    )
    fallback_confidence_threshold: float = Field(
        serialization_alias="fallbackConfidenceThreshold"
    )
    page_count: int = Field(serialization_alias="pageCount")
    line_count: int = Field(serialization_alias="lineCount")
    token_count: int = Field(serialization_alias="tokenCount")
    low_confidence_line_count: int = Field(serialization_alias="lowConfidenceLineCount")
    percent_lines_below_threshold: float = Field(
        serialization_alias="percentLinesBelowThreshold"
    )
    low_confidence_page_count: int = Field(serialization_alias="lowConfidencePageCount")
    low_confidence_page_distribution: list[TranscriptionMetricsLowConfidencePageResponse] = Field(
        serialization_alias="lowConfidencePageDistribution"
    )
    segmentation_mismatch_warning_count: int = Field(
        serialization_alias="segmentationMismatchWarningCount"
    )
    structured_validation_failure_count: int = Field(
        serialization_alias="structuredValidationFailureCount"
    )
    fallback_invocation_count: int = Field(serialization_alias="fallbackInvocationCount")
    confidence_bands: dict[TranscriptionConfidenceBandLiteral, int] = Field(
        serialization_alias="confidenceBands"
    )


class UpdateTranscriptionTriageAssignmentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    run_id: str | None = Field(
        default=None,
        alias="runId",
        serialization_alias="runId",
        min_length=1,
        max_length=120,
    )
    reviewer_user_id: str | None = Field(
        default=None,
        alias="reviewerUserId",
        serialization_alias="reviewerUserId",
        min_length=1,
        max_length=160,
    )


class UpdateTranscriptionTriageAssignmentResponse(BaseModel):
    projection: TranscriptionProjectionResponse | None
    run: TranscriptionRunResponse
    item: TranscriptionTriagePageResponse


class TranscriptionOverviewResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    projection: TranscriptionProjectionResponse | None
    active_run: TranscriptionRunResponse | None = Field(
        default=None,
        serialization_alias="activeRun",
    )
    latest_run: TranscriptionRunResponse | None = Field(
        default=None,
        serialization_alias="latestRun",
    )
    total_runs: int = Field(serialization_alias="totalRuns")
    page_count: int = Field(serialization_alias="pageCount")
    active_status_counts: dict[TranscriptionRunStatusLiteral, int] = Field(
        serialization_alias="activeStatusCounts"
    )
    active_line_count: int = Field(serialization_alias="activeLineCount")
    active_token_count: int = Field(serialization_alias="activeTokenCount")
    active_anchor_refresh_required: int = Field(
        serialization_alias="activeAnchorRefreshRequired"
    )
    active_low_confidence_lines: int = Field(
        serialization_alias="activeLowConfidenceLines"
    )


class ActivateTranscriptionRunResponse(BaseModel):
    projection: TranscriptionProjectionResponse
    run: TranscriptionRunResponse


def _as_document_response(record: DocumentRecord) -> DocumentResponse:
    return DocumentResponse(
        id=record.id,
        project_id=record.project_id,
        original_filename=record.original_filename,
        stored_filename=record.stored_filename,
        content_type_detected=record.content_type_detected,
        bytes=record.bytes,
        sha256=record.sha256,
        page_count=record.page_count,
        status=record.status,
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_timeline_response_item(record: DocumentProcessingRunRecord) -> DocumentTimelineEventResponse:
    return DocumentTimelineEventResponse(
        id=record.id,
        attempt_number=record.attempt_number,
        run_kind=record.run_kind,
        supersedes_processing_run_id=record.supersedes_processing_run_id,
        superseded_by_processing_run_id=record.superseded_by_processing_run_id,
        status=record.status,
        failure_reason=record.failure_reason,
        created_by=record.created_by,
        started_at=record.started_at,
        finished_at=record.finished_at,
        canceled_by=record.canceled_by,
        canceled_at=record.canceled_at,
        created_at=record.created_at,
    )


def _as_processing_run_status_response(
    record: DocumentProcessingRunRecord,
) -> DocumentProcessingRunStatusResponse:
    return DocumentProcessingRunStatusResponse(
        run_id=record.id,
        document_id=record.document_id,
        attempt_number=record.attempt_number,
        run_kind=record.run_kind,
        supersedes_processing_run_id=record.supersedes_processing_run_id,
        superseded_by_processing_run_id=record.superseded_by_processing_run_id,
        status=record.status,
        failure_reason=record.failure_reason,
        started_at=record.started_at,
        finished_at=record.finished_at,
        canceled_at=record.canceled_at,
        created_at=record.created_at,
        active=record.status in {"QUEUED", "RUNNING"},
    )


def _as_processing_run_detail_response(
    record: DocumentProcessingRunRecord,
) -> DocumentProcessingRunDetailResponse:
    return DocumentProcessingRunDetailResponse(
        id=record.id,
        document_id=record.document_id,
        attempt_number=record.attempt_number,
        run_kind=record.run_kind,
        supersedes_processing_run_id=record.supersedes_processing_run_id,
        superseded_by_processing_run_id=record.superseded_by_processing_run_id,
        status=record.status,
        failure_reason=record.failure_reason,
        created_by=record.created_by,
        started_at=record.started_at,
        finished_at=record.finished_at,
        canceled_by=record.canceled_by,
        canceled_at=record.canceled_at,
        created_at=record.created_at,
        active=record.status in {"QUEUED", "RUNNING"},
    )


def _as_import_status_response(snapshot: DocumentImportSnapshot) -> DocumentImportStatusResponse:
    import_record = snapshot.import_record
    return DocumentImportStatusResponse(
        import_id=import_record.id,
        document_id=import_record.document_id,
        import_status=import_record.status,
        document_status=snapshot.document_record.status,
        failure_reason=import_record.failure_reason,
        cancel_allowed=import_record.status in {"UPLOADING", "QUEUED"},
        created_at=import_record.created_at,
        updated_at=import_record.updated_at,
    )


def _as_upload_session_response(
    *,
    session_snapshot: DocumentUploadSessionSnapshot,
    chunk_size_limit_bytes: int,
    upload_limit_bytes: int,
) -> DocumentUploadSessionResponse:
    session_record = session_snapshot.session_record
    return DocumentUploadSessionResponse(
        session_id=session_record.id,
        import_id=session_snapshot.import_record.id,
        document_id=session_snapshot.document_record.id,
        original_filename=session_record.original_filename,
        upload_status=session_record.status,
        import_status=session_snapshot.import_record.status,
        document_status=session_snapshot.document_record.status,
        bytes_received=session_record.bytes_received,
        expected_total_bytes=session_record.expected_total_bytes,
        expected_sha256=session_record.expected_sha256,
        last_chunk_index=session_record.last_chunk_index,
        next_chunk_index=session_snapshot.next_chunk_index,
        chunk_size_limit_bytes=chunk_size_limit_bytes,
        upload_limit_bytes=upload_limit_bytes,
        cancel_allowed=session_record.status == "ACTIVE"
        and session_snapshot.import_record.status in {"UPLOADING", "QUEUED"},
        failure_reason=session_record.failure_reason
        or session_snapshot.import_record.failure_reason,
        created_at=session_record.created_at,
        updated_at=session_record.updated_at,
    )


def _as_page_response(record: DocumentPageRecord) -> DocumentPageResponse:
    return DocumentPageResponse(
        id=record.id,
        document_id=record.document_id,
        page_index=record.page_index,
        width=record.width,
        height=record.height,
        dpi=record.dpi,
        source_width=record.source_width,
        source_height=record.source_height,
        source_dpi=record.source_dpi,
        source_color_mode=record.source_color_mode,
        status=record.status,
        failure_reason=record.failure_reason,
        viewer_rotation=record.viewer_rotation,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_page_detail_response(record: DocumentPageRecord) -> DocumentPageDetailResponse:
    return DocumentPageDetailResponse(
        id=record.id,
        document_id=record.document_id,
        page_index=record.page_index,
        width=record.width,
        height=record.height,
        dpi=record.dpi,
        source_width=record.source_width,
        source_height=record.source_height,
        source_dpi=record.source_dpi,
        source_color_mode=record.source_color_mode,
        status=record.status,
        failure_reason=record.failure_reason,
        viewer_rotation=record.viewer_rotation,
        created_at=record.created_at,
        updated_at=record.updated_at,
        derived_image_available=bool(record.derived_image_key),
        thumbnail_available=bool(record.thumbnail_key),
    )


def _as_page_variant_availability_response(
    variant: DocumentPageVariantAvailability,
) -> DocumentPageVariantAvailabilityResponse:
    return DocumentPageVariantAvailabilityResponse(
        variant=variant.variant,
        image_variant=variant.image_variant,
        available=bool(variant.available),
        media_type=variant.media_type,
        run_id=variant.run_id,
        result_status=variant.result_status,
        quality_gate_status=variant.quality_gate_status,
        warnings_json=list(variant.warnings_json),
        metrics_json=dict(variant.metrics_json),
    )


def _resolve_downstream_basis_state(
    *,
    has_projection: bool,
    basis_run_id: str | None,
    resolved_against_run_id: str | None,
) -> DownstreamBasisStateLiteral:
    if not has_projection:
        return "NOT_STARTED"
    if basis_run_id is None:
        return "NOT_STARTED"
    if resolved_against_run_id == basis_run_id:
        return "CURRENT"
    return "STALE"


def _as_preprocess_downstream_impact_response(
    *,
    resolved_against_run_id: str | None,
    basis_references: PreprocessDownstreamBasisReferencesRecord | None,
) -> PreprocessDownstreamImpactResponse:
    references = basis_references or PreprocessDownstreamBasisReferencesRecord(
        has_layout_projection=False,
        layout_active_input_preprocess_run_id=None,
        has_transcription_projection=False,
        transcription_active_preprocess_run_id=None,
    )
    return PreprocessDownstreamImpactResponse(
        resolved_against_run_id=resolved_against_run_id,
        layout_basis_state=_resolve_downstream_basis_state(
            has_projection=references.has_layout_projection,
            basis_run_id=references.layout_active_input_preprocess_run_id,
            resolved_against_run_id=resolved_against_run_id,
        ),
        layout_basis_run_id=references.layout_active_input_preprocess_run_id,
        transcription_basis_state=_resolve_downstream_basis_state(
            has_projection=references.has_transcription_projection,
            basis_run_id=references.transcription_active_preprocess_run_id,
            resolved_against_run_id=resolved_against_run_id,
        ),
        transcription_basis_run_id=references.transcription_active_preprocess_run_id,
    )


def _as_preprocess_run_response(
    record: PreprocessRunRecord,
    *,
    active_run_id: str | None = None,
    basis_references: PreprocessDownstreamBasisReferencesRecord | None = None,
) -> PreprocessRunResponse:
    is_superseded = record.superseded_by_run_id is not None
    return PreprocessRunResponse(
        id=record.id,
        project_id=record.project_id,
        document_id=record.document_id,
        parent_run_id=record.parent_run_id,
        attempt_number=record.attempt_number,
        run_scope=record.run_scope,
        target_page_ids_json=record.target_page_ids_json,
        composed_from_run_ids_json=record.composed_from_run_ids_json,
        superseded_by_run_id=record.superseded_by_run_id,
        profile_id=record.profile_id,
        profile_version=record.profile_version,
        profile_revision=record.profile_revision,
        profile_label=record.profile_label,
        profile_description=record.profile_description,
        profile_params_hash=record.profile_params_hash,
        profile_is_advanced=record.profile_is_advanced,
        profile_is_gated=record.profile_is_gated,
        params_json=record.params_json,
        params_hash=record.params_hash,
        pipeline_version=record.pipeline_version,
        container_digest=record.container_digest,
        manifest_object_key=record.manifest_object_key,
        manifest_sha256=record.manifest_sha256,
        manifest_schema_version=record.manifest_schema_version,
        status=record.status,
        created_by=record.created_by,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        failure_reason=record.failure_reason,
        is_active_projection=active_run_id == record.id,
        is_superseded=is_superseded,
        is_current_attempt=not is_superseded,
        is_historical_attempt=is_superseded,
        downstream_impact=_as_preprocess_downstream_impact_response(
            resolved_against_run_id=record.id,
            basis_references=basis_references,
        ),
    )


def _as_preprocess_projection_response(
    record: DocumentPreprocessProjectionRecord,
    *,
    basis_references: PreprocessDownstreamBasisReferencesRecord | None = None,
) -> PreprocessProjectionResponse:
    return PreprocessProjectionResponse(
        document_id=record.document_id,
        project_id=record.project_id,
        active_preprocess_run_id=record.active_preprocess_run_id,
        active_profile_id=record.active_profile_id,
        active_profile_version=record.active_profile_version,
        active_profile_revision=record.active_profile_revision,
        active_params_hash=record.active_params_hash,
        active_pipeline_version=record.active_pipeline_version,
        active_container_digest=record.active_container_digest,
        downstream_default_run_id=record.active_preprocess_run_id,
        downstream_impact=_as_preprocess_downstream_impact_response(
            resolved_against_run_id=record.active_preprocess_run_id,
            basis_references=basis_references,
        ),
        updated_at=record.updated_at,
    )


def _as_preprocess_run_status_response(
    record: PreprocessRunRecord,
) -> PreprocessRunStatusResponse:
    return PreprocessRunStatusResponse(
        run_id=record.id,
        document_id=record.document_id,
        status=record.status,
        failure_reason=record.failure_reason,
        started_at=record.started_at,
        finished_at=record.finished_at,
        created_at=record.created_at,
        active=record.status in {"QUEUED", "RUNNING"},
    )


def _as_preprocess_page_result_response(
    record: PagePreprocessResultRecord,
) -> PreprocessPageResultResponse:
    return PreprocessPageResultResponse(
        run_id=record.run_id,
        page_id=record.page_id,
        page_index=record.page_index,
        status=record.status,
        quality_gate_status=record.quality_gate_status,
        input_object_key=record.input_object_key,
        input_sha256=record.input_sha256,
        source_result_run_id=record.source_result_run_id,
        output_object_key_gray=record.output_object_key_gray,
        output_object_key_bin=record.output_object_key_bin,
        metrics_object_key=record.metrics_object_key,
        metrics_sha256=record.metrics_sha256,
        metrics_json=record.metrics_json,
        sha256_gray=record.sha256_gray,
        sha256_bin=record.sha256_bin,
        warnings_json=record.warnings_json,
        failure_reason=record.failure_reason,
        created_at=record.created_at,
        updated_at=record.updated_at,
        )


def _as_layout_activation_gate_response(
    gate: LayoutActivationGateRecord,
) -> LayoutActivationGateResponse:
    blockers = []
    for blocker in gate.blockers:
        blockers.append(
            LayoutActivationBlockerResponse(
                code=blocker.code,
                message=blocker.message,
                count=blocker.count,
                page_ids=list(blocker.page_ids),
                page_numbers=list(blocker.page_numbers),
            )
        )
    downstream_impact = gate.downstream_impact
    return LayoutActivationGateResponse(
        eligible=gate.eligible,
        blocker_count=gate.blocker_count,
        blockers=blockers,
        evaluated_at=gate.evaluated_at,
        downstream_impact=LayoutActivationDownstreamImpactResponse(
            transcription_state_after_activation=(
                downstream_impact.transcription_state_after_activation
            ),
            invalidates_existing_transcription_basis=(
                downstream_impact.invalidates_existing_transcription_basis
            ),
            reason=downstream_impact.reason,
            has_active_transcription_projection=(
                downstream_impact.has_active_transcription_projection
            ),
            active_transcription_run_id=downstream_impact.active_transcription_run_id,
        ),
    )


def _as_layout_run_response(
    record: LayoutRunRecord,
    *,
    active_run_id: str | None = None,
) -> LayoutRunResponse:
    is_superseded = record.superseded_by_run_id is not None
    return LayoutRunResponse(
        id=record.id,
        project_id=record.project_id,
        document_id=record.document_id,
        input_preprocess_run_id=record.input_preprocess_run_id,
        run_kind=record.run_kind,
        parent_run_id=record.parent_run_id,
        attempt_number=record.attempt_number,
        superseded_by_run_id=record.superseded_by_run_id,
        model_id=record.model_id,
        profile_id=record.profile_id,
        params_json=record.params_json,
        params_hash=record.params_hash,
        pipeline_version=record.pipeline_version,
        container_digest=record.container_digest,
        status=record.status,
        created_by=record.created_by,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        failure_reason=record.failure_reason,
        is_active_projection=active_run_id == record.id,
        is_superseded=is_superseded,
        is_current_attempt=not is_superseded,
        is_historical_attempt=is_superseded,
        activation_gate=(
            _as_layout_activation_gate_response(record.activation_gate)
            if record.activation_gate is not None
            else None
        ),
    )


def _as_layout_projection_response(
    record: DocumentLayoutProjectionRecord,
) -> LayoutProjectionResponse:
    return LayoutProjectionResponse(
        document_id=record.document_id,
        project_id=record.project_id,
        active_layout_run_id=record.active_layout_run_id,
        active_input_preprocess_run_id=record.active_input_preprocess_run_id,
        active_layout_snapshot_hash=record.active_layout_snapshot_hash,
        downstream_transcription_state=record.downstream_transcription_state,
        downstream_transcription_invalidated_at=(
            record.downstream_transcription_invalidated_at
        ),
        downstream_transcription_invalidated_reason=(
            record.downstream_transcription_invalidated_reason
        ),
        updated_at=record.updated_at,
    )


def _as_layout_run_status_response(
    record: LayoutRunRecord,
) -> LayoutRunStatusResponse:
    return LayoutRunStatusResponse(
        run_id=record.id,
        document_id=record.document_id,
        status=record.status,
        failure_reason=record.failure_reason,
        started_at=record.started_at,
        finished_at=record.finished_at,
        created_at=record.created_at,
        active=record.status in {"QUEUED", "RUNNING"},
    )


def _as_layout_page_result_response(
    record: PageLayoutResultRecord,
) -> LayoutPageResultResponse:
    return LayoutPageResultResponse(
        run_id=record.run_id,
        page_id=record.page_id,
        page_index=record.page_index,
        status=record.status,
        page_recall_status=record.page_recall_status,
        active_layout_version_id=record.active_layout_version_id,
        page_xml_key=record.page_xml_key,
        overlay_json_key=record.overlay_json_key,
        page_xml_sha256=record.page_xml_sha256,
        overlay_json_sha256=record.overlay_json_sha256,
        metrics_json=record.metrics_json,
        warnings_json=record.warnings_json,
        failure_reason=record.failure_reason,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_layout_reading_order_update_response(
    snapshot: DocumentLayoutReadingOrderSnapshot,
) -> LayoutReadingOrderUpdateResponse:
    return LayoutReadingOrderUpdateResponse(
        run_id=snapshot.run_id,
        page_id=snapshot.page_id,
        page_index=snapshot.page_index,
        layout_version_id=snapshot.layout_version_id,
        version_etag=snapshot.version_etag,
        mode=snapshot.mode,  # type: ignore[arg-type]
        groups=[
            LayoutReadingOrderGroupResponse(
                id=group.group_id,
                ordered=group.ordered,
                region_ids=list(group.region_ids),
            )
            for group in snapshot.groups
        ],
        edges=[dict(edge) for edge in snapshot.edges],
        signals_json=snapshot.signals_json,
    )


def _as_layout_elements_update_response(
    snapshot: DocumentLayoutElementsSnapshot,
) -> LayoutElementsUpdateResponse:
    return LayoutElementsUpdateResponse(
        run_id=snapshot.run_id,
        page_id=snapshot.page_id,
        page_index=snapshot.page_index,
        layout_version_id=snapshot.layout_version_id,
        version_etag=snapshot.version_etag,
        operations_applied=snapshot.operations_applied,
        overlay=snapshot.overlay_payload,
        downstream_transcription_invalidated=snapshot.downstream_transcription_invalidated,
        downstream_transcription_state=snapshot.downstream_transcription_state,
        downstream_transcription_invalidated_reason=(
            snapshot.downstream_transcription_invalidated_reason
        ),
    )


def _as_layout_line_artifacts_response(
    snapshot: DocumentLayoutLineArtifactsSnapshot,
) -> LayoutLineArtifactsResponse:
    return LayoutLineArtifactsResponse(
        run_id=snapshot.run_id,
        page_id=snapshot.page_id,
        page_index=snapshot.page_index,
        line_id=snapshot.line_id,
        region_id=snapshot.region_id,
        artifacts_sha256=snapshot.artifacts_sha256,
        line_crop_path=snapshot.line_crop_path,
        region_crop_path=snapshot.region_crop_path,
        page_thumbnail_path=snapshot.page_thumbnail_path,
        context_window_path=snapshot.context_window_path,
        context_window=snapshot.context_window,
    )


def _as_layout_page_recall_status_response(
    snapshot: DocumentLayoutPageRecallStatusSnapshot,
) -> LayoutPageRecallStatusResponse:
    return LayoutPageRecallStatusResponse(
        run_id=snapshot.run_id,
        page_id=snapshot.page_id,
        page_index=snapshot.page_index,
        page_recall_status=snapshot.page_recall_status,
        recall_check_version=snapshot.recall_check_version,
        missed_text_risk_score=snapshot.missed_text_risk_score,
        signals_json=snapshot.signals_json,
        rescue_candidate_counts=snapshot.rescue_candidate_counts,  # type: ignore[arg-type]
        blocker_reason_codes=snapshot.blocker_reason_codes,
        unresolved_count=snapshot.unresolved_count,
    )


def _as_layout_rescue_candidate_response(
    record: LayoutRescueCandidateRecord,
) -> LayoutRescueCandidateResponse:
    return LayoutRescueCandidateResponse(
        id=record.id,
        run_id=record.run_id,
        page_id=record.page_id,
        candidate_kind=record.candidate_kind,
        geometry_json=record.geometry_json,
        confidence=record.confidence,
        source_signal=record.source_signal,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_transcription_run_response(
    record: TranscriptionRunRecord,
    *,
    active_run_id: str | None = None,
) -> TranscriptionRunResponse:
    is_superseded = record.superseded_by_transcription_run_id is not None
    return TranscriptionRunResponse(
        id=record.id,
        project_id=record.project_id,
        document_id=record.document_id,
        input_preprocess_run_id=record.input_preprocess_run_id,
        input_layout_run_id=record.input_layout_run_id,
        input_layout_snapshot_hash=record.input_layout_snapshot_hash,
        engine=record.engine,
        model_id=record.model_id,
        project_model_assignment_id=record.project_model_assignment_id,
        prompt_template_id=record.prompt_template_id,
        prompt_template_sha256=record.prompt_template_sha256,
        response_schema_version=record.response_schema_version,
        confidence_basis=record.confidence_basis,
        confidence_calibration_version=record.confidence_calibration_version,
        params_json=record.params_json,
        pipeline_version=record.pipeline_version,
        container_digest=record.container_digest,
        attempt_number=record.attempt_number,
        supersedes_transcription_run_id=record.supersedes_transcription_run_id,
        superseded_by_transcription_run_id=record.superseded_by_transcription_run_id,
        status=record.status,
        created_by=record.created_by,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        canceled_by=record.canceled_by,
        canceled_at=record.canceled_at,
        failure_reason=record.failure_reason,
        is_active_projection=active_run_id == record.id,
        is_superseded=is_superseded,
        is_current_attempt=not is_superseded,
        is_historical_attempt=is_superseded,
    )


def _as_transcription_projection_response(
    record: DocumentTranscriptionProjectionRecord,
) -> TranscriptionProjectionResponse:
    return TranscriptionProjectionResponse(
        document_id=record.document_id,
        project_id=record.project_id,
        active_transcription_run_id=record.active_transcription_run_id,
        active_layout_run_id=record.active_layout_run_id,
        active_layout_snapshot_hash=record.active_layout_snapshot_hash,
        active_preprocess_run_id=record.active_preprocess_run_id,
        downstream_redaction_state=record.downstream_redaction_state,
        downstream_redaction_invalidated_at=record.downstream_redaction_invalidated_at,
        downstream_redaction_invalidated_reason=record.downstream_redaction_invalidated_reason,
        updated_at=record.updated_at,
    )


def _as_transcription_run_status_response(
    record: TranscriptionRunRecord,
) -> TranscriptionRunStatusResponse:
    return TranscriptionRunStatusResponse(
        run_id=record.id,
        document_id=record.document_id,
        status=record.status,
        failure_reason=record.failure_reason,
        started_at=record.started_at,
        finished_at=record.finished_at,
        created_at=record.created_at,
        active=record.status in {"QUEUED", "RUNNING"},
    )


def _as_transcription_page_result_response(
    record: PageTranscriptionResultRecord,
) -> TranscriptionPageResultResponse:
    return TranscriptionPageResultResponse(
        run_id=record.run_id,
        page_id=record.page_id,
        page_index=record.page_index,
        status=record.status,
        pagexml_out_key=record.pagexml_out_key,
        pagexml_out_sha256=record.pagexml_out_sha256,
        raw_model_response_key=None,
        raw_model_response_sha256=record.raw_model_response_sha256,
        hocr_out_key=record.hocr_out_key,
        hocr_out_sha256=record.hocr_out_sha256,
        metrics_json=record.metrics_json,
        warnings_json=record.warnings_json,
        failure_reason=record.failure_reason,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_transcription_line_result_response(
    record: LineTranscriptionResultRecord,
) -> TranscriptionLineResultResponse:
    return TranscriptionLineResultResponse(
        run_id=record.run_id,
        page_id=record.page_id,
        line_id=record.line_id,
        text_diplomatic=record.text_diplomatic,
        conf_line=record.conf_line,
        confidence_band=record.confidence_band,
        confidence_basis=record.confidence_basis,
        confidence_calibration_version=record.confidence_calibration_version,
        alignment_json_key=record.alignment_json_key,
        char_boxes_key=record.char_boxes_key,
        schema_validation_status=record.schema_validation_status,
        flags_json=record.flags_json,
        machine_output_sha256=record.machine_output_sha256,
        active_transcript_version_id=record.active_transcript_version_id,
        version_etag=record.version_etag,
        token_anchor_status=record.token_anchor_status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_transcription_token_result_response(
    record: TokenTranscriptionResultRecord,
) -> TranscriptionTokenResultResponse:
    return TranscriptionTokenResultResponse(
        run_id=record.run_id,
        page_id=record.page_id,
        line_id=record.line_id,
        token_id=record.token_id,
        token_index=record.token_index,
        token_text=record.token_text,
        token_confidence=record.token_confidence,
        bbox_json=record.bbox_json,
        polygon_json=record.polygon_json,
        source_kind=record.source_kind,
        source_ref_id=record.source_ref_id,
        projection_basis=record.projection_basis,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_transcript_version_response(
    record: TranscriptVersionRecord,
) -> TranscriptVersionResponse:
    return TranscriptVersionResponse(
        id=record.id,
        run_id=record.run_id,
        page_id=record.page_id,
        line_id=record.line_id,
        base_version_id=record.base_version_id,
        superseded_by_version_id=record.superseded_by_version_id,
        version_etag=record.version_etag,
        text_diplomatic=record.text_diplomatic,
        editor_user_id=record.editor_user_id,
        edit_reason=record.edit_reason,
        created_at=record.created_at,
    )


def _as_transcription_output_projection_response(
    record: TranscriptionOutputProjectionRecord,
) -> TranscriptionOutputProjectionResponse:
    return TranscriptionOutputProjectionResponse(
        run_id=record.run_id,
        document_id=record.document_id,
        page_id=record.page_id,
        corrected_pagexml_key=record.corrected_pagexml_key,
        corrected_pagexml_sha256=record.corrected_pagexml_sha256,
        corrected_text_sha256=record.corrected_text_sha256,
        source_pagexml_sha256=record.source_pagexml_sha256,
        updated_at=record.updated_at,
    )


def _as_transcript_variant_suggestion_response(
    record: TranscriptVariantSuggestionRecord,
) -> TranscriptVariantSuggestionResponse:
    return TranscriptVariantSuggestionResponse(
        id=record.id,
        variant_layer_id=record.variant_layer_id,
        line_id=record.line_id,
        suggestion_text=record.suggestion_text,
        confidence=record.confidence,
        status=record.status,
        decided_by=record.decided_by,
        decided_at=record.decided_at,
        decision_reason=record.decision_reason,
        metadata_json=dict(record.metadata_json),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_transcript_variant_suggestion_event_response(
    record: TranscriptVariantSuggestionEventRecord,
) -> TranscriptVariantSuggestionEventResponse:
    return TranscriptVariantSuggestionEventResponse(
        id=record.id,
        suggestion_id=record.suggestion_id,
        variant_layer_id=record.variant_layer_id,
        actor_user_id=record.actor_user_id,
        decision=record.decision,
        from_status=record.from_status,
        to_status=record.to_status,
        reason=record.reason,
        created_at=record.created_at,
    )


def _as_transcript_variant_layer_response(
    record: TranscriptVariantLayerRecord,
    *,
    suggestions: list[TranscriptVariantSuggestionRecord],
) -> TranscriptVariantLayerResponse:
    return TranscriptVariantLayerResponse(
        id=record.id,
        run_id=record.run_id,
        page_id=record.page_id,
        variant_kind=record.variant_kind,
        base_transcript_version_id=record.base_transcript_version_id,
        base_version_set_sha256=record.base_version_set_sha256,
        base_projection_sha256=record.base_projection_sha256,
        variant_text_key=record.variant_text_key,
        variant_text_sha256=record.variant_text_sha256,
        created_by=record.created_by,
        created_at=record.created_at,
        suggestions=[
            _as_transcript_variant_suggestion_response(item) for item in suggestions
        ],
    )


def _as_correct_transcription_line_response(
    snapshot: DocumentTranscriptionLineCorrectionSnapshot,
) -> CorrectTranscriptionLineResponse:
    return CorrectTranscriptionLineResponse(
        run_id=snapshot.run.id,
        page_id=snapshot.page.id,
        line_id=snapshot.line.line_id,
        text_changed=snapshot.text_changed,
        line=_as_transcription_line_result_response(snapshot.line),
        active_version=_as_transcript_version_response(snapshot.active_version),
        output_projection=_as_transcription_output_projection_response(snapshot.projection),
        downstream_redaction_invalidated=snapshot.downstream_projection is not None,
        downstream_redaction_state=(
            snapshot.downstream_projection.downstream_redaction_state
            if snapshot.downstream_projection is not None
            else None
        ),
        downstream_redaction_invalidated_at=(
            snapshot.downstream_projection.downstream_redaction_invalidated_at
            if snapshot.downstream_projection is not None
            else None
        ),
        downstream_redaction_invalidated_reason=(
            snapshot.downstream_projection.downstream_redaction_invalidated_reason
            if snapshot.downstream_projection is not None
            else None
        ),
    )


def _as_transcription_compare_decision_response(
    record: TranscriptionCompareDecisionRecord,
) -> TranscriptionCompareDecisionResponse:
    return TranscriptionCompareDecisionResponse(
        id=record.id,
        document_id=record.document_id,
        base_run_id=record.base_run_id,
        candidate_run_id=record.candidate_run_id,
        page_id=record.page_id,
        line_id=record.line_id,
        token_id=record.token_id,
        decision=record.decision,
        decision_etag=record.decision_etag,
        decided_by=record.decided_by,
        decided_at=record.decided_at,
        decision_reason=record.decision_reason,
    )


def _as_transcription_compare_response(
    *,
    snapshot: DocumentTranscriptionCompareSnapshot,
    active_run_id: str | None,
) -> TranscriptionCompareResponse:
    return TranscriptionCompareResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        base_run=_as_transcription_run_response(
            snapshot.base_run,
            active_run_id=active_run_id,
        ),
        candidate_run=_as_transcription_run_response(
            snapshot.candidate_run,
            active_run_id=active_run_id,
        ),
        changed_line_count=snapshot.changed_line_count,
        changed_token_count=snapshot.changed_token_count,
        changed_confidence_count=snapshot.changed_confidence_count,
        base_engine_metadata=dict(snapshot.base_engine_metadata),
        candidate_engine_metadata=dict(snapshot.candidate_engine_metadata),
        items=[
            TranscriptionComparePageResponse(
                page_id=item.page_id,
                page_index=item.page_index,
                changed_line_count=item.changed_line_count,
                changed_token_count=item.changed_token_count,
                changed_confidence_count=item.changed_confidence_count,
                output_availability=dict(item.output_availability),
                base=(
                    _as_transcription_page_result_response(item.base_page)
                    if item.base_page is not None
                    else None
                ),
                candidate=(
                    _as_transcription_page_result_response(item.candidate_page)
                    if item.candidate_page is not None
                    else None
                ),
                line_diffs=[
                    TranscriptionCompareLineDiffResponse(
                        line_id=line.line_id,
                        changed=line.changed,
                        confidence_delta=line.confidence_delta,
                        base=(
                            _as_transcription_line_result_response(line.base_line)
                            if line.base_line is not None
                            else None
                        ),
                        candidate=(
                            _as_transcription_line_result_response(line.candidate_line)
                            if line.candidate_line is not None
                            else None
                        ),
                        decision=(
                            _as_transcription_compare_decision_response(
                                line.current_decision
                            )
                            if line.current_decision is not None
                            else None
                        ),
                    )
                    for line in item.line_diffs
                ],
                token_diffs=[
                    TranscriptionCompareTokenDiffResponse(
                        token_id=token.token_id,
                        token_index=token.token_index,
                        line_id=token.line_id,
                        changed=token.changed,
                        confidence_delta=token.confidence_delta,
                        base=(
                            _as_transcription_token_result_response(token.base_token)
                            if token.base_token is not None
                            else None
                        ),
                        candidate=(
                            _as_transcription_token_result_response(
                                token.candidate_token
                            )
                            if token.candidate_token is not None
                            else None
                        ),
                        decision=(
                            _as_transcription_compare_decision_response(
                                token.current_decision
                            )
                            if token.current_decision is not None
                            else None
                        ),
                    )
                    for token in item.token_diffs
                ],
            )
            for item in snapshot.pages
        ],
    )


def _as_transcription_triage_page_response(
    record: DocumentTranscriptionTriagePageSnapshot,
) -> TranscriptionTriagePageResponse:
    return TranscriptionTriagePageResponse(
        run_id=record.run_id,
        page_id=record.page_id,
        page_index=record.page_index,
        status=record.status,
        line_count=record.line_count,
        token_count=record.token_count,
        anchor_refresh_required=record.anchor_refresh_required,
        low_confidence_lines=record.low_confidence_lines,
        min_confidence=record.min_confidence,
        avg_confidence=record.avg_confidence,
        warnings_json=record.warnings_json,
        confidence_bands=record.confidence_bands,
        issues=record.issues,
        ranking_score=record.ranking_score,
        ranking_rationale=record.ranking_rationale,
        reviewer_assignment_user_id=record.reviewer_assignment_user_id,
        reviewer_assignment_updated_by=record.reviewer_assignment_updated_by,
        reviewer_assignment_updated_at=record.reviewer_assignment_updated_at,
    )


def _as_transcription_metrics_response(
    *,
    projection: DocumentTranscriptionProjectionRecord | None,
    run: TranscriptionRunRecord | None,
    metrics: DocumentTranscriptionMetricsSnapshot,
    active_run_id: str | None,
) -> TranscriptionMetricsResponse:
    return TranscriptionMetricsResponse(
        projection=(
            _as_transcription_projection_response(projection)
            if projection is not None
            else None
        ),
        run=(
            _as_transcription_run_response(run, active_run_id=active_run_id)
            if run is not None
            else None
        ),
        review_confidence_threshold=metrics.review_confidence_threshold,
        fallback_confidence_threshold=metrics.fallback_confidence_threshold,
        page_count=metrics.page_count,
        line_count=metrics.line_count,
        token_count=metrics.token_count,
        low_confidence_line_count=metrics.low_confidence_line_count,
        percent_lines_below_threshold=metrics.percent_lines_below_threshold,
        low_confidence_page_count=metrics.low_confidence_page_count,
        low_confidence_page_distribution=[
            TranscriptionMetricsLowConfidencePageResponse(
                page_id=item.page_id,
                page_index=item.page_index,
                low_confidence_lines=item.low_confidence_lines,
            )
            for item in metrics.low_confidence_page_distribution
        ],
        segmentation_mismatch_warning_count=metrics.segmentation_mismatch_warning_count,
        structured_validation_failure_count=metrics.structured_validation_failure_count,
        fallback_invocation_count=metrics.fallback_invocation_count,
        confidence_bands=metrics.confidence_bands,
    )


def _resolve_transcription_context(
    *,
    current_user: SessionPrincipal,
    project_id: str,
    document_id: str,
    document_service: DocumentService,
) -> tuple[DocumentTranscriptionProjectionRecord | None, str | None]:
    projection = document_service.get_transcription_projection(
        current_user=current_user,
        project_id=project_id,
        document_id=document_id,
    )
    active_run_id = (
        projection.active_transcription_run_id if projection is not None else None
    )
    return projection, active_run_id


def _resolve_preprocess_context(
    *,
    current_user: SessionPrincipal,
    project_id: str,
    document_id: str,
    document_service: DocumentService,
) -> tuple[
    DocumentPreprocessProjectionRecord | None,
    str | None,
    PreprocessDownstreamBasisReferencesRecord,
]:
    projection = document_service.get_preprocess_projection(
        current_user=current_user,
        project_id=project_id,
        document_id=document_id,
    )
    basis_references = document_service.get_preprocess_downstream_basis_references(
        current_user=current_user,
        project_id=project_id,
        document_id=document_id,
    )
    active_run_id = (
        projection.active_preprocess_run_id if projection is not None else None
    )
    return projection, active_run_id, basis_references


def _resolve_layout_context(
    *,
    current_user: SessionPrincipal,
    project_id: str,
    document_id: str,
    document_service: DocumentService,
) -> tuple[DocumentLayoutProjectionRecord | None, str | None]:
    projection = document_service.get_layout_projection(
        current_user=current_user,
        project_id=project_id,
        document_id=document_id,
    )
    active_run_id = projection.active_layout_run_id if projection is not None else None
    return projection, active_run_id


def _parse_datetime_filter(
    raw_value: str | None,
    *,
    param_name: str,
    upper_bound: bool = False,
) -> datetime | None:
    if not isinstance(raw_value, str):
        return None
    trimmed = raw_value.strip()
    if not trimmed:
        return None

    try:
        if "T" in trimmed:
            normalized = trimmed.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed

        parsed_date = date.fromisoformat(trimmed)
        return datetime.combine(
            parsed_date,
            time.max if upper_bound else time.min,
            tzinfo=timezone.utc,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid '{param_name}' filter. Use YYYY-MM-DD or ISO-8601 datetime.",
        ) from error


def _raise_http_from_error(
    *,
    error: Exception,
    current_user: SessionPrincipal,
    project_id: str,
    audit_service: AuditService,
    request_context: AuditRequestContext,
    required_roles: list[str] | None = None,
) -> None:
    if isinstance(error, ProjectNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(
        error,
        (
            ProjectAccessDeniedError,
            DocumentUploadAccessDeniedError,
            DocumentRetryAccessDeniedError,
            DocumentPreprocessAccessDeniedError,
            DocumentLayoutAccessDeniedError,
            DocumentTranscriptionAccessDeniedError,
        ),
    ):
        audit_service.record_event_best_effort(
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": required_roles or ["PROJECT_MEMBER"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            request_context=request_context,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(
        error,
        (
            DocumentNotFoundError,
            DocumentImportNotFoundError,
            DocumentPageNotFoundError,
            DocumentProcessingRunNotFoundError,
            DocumentPreprocessRunNotFoundError,
            DocumentLayoutRunNotFoundError,
            DocumentTranscriptionRunNotFoundError,
            DocumentUploadSessionNotFoundError,
        ),
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(
        error,
        (
            DocumentImportConflictError,
            DocumentRetryConflictError,
            DocumentPreprocessConflictError,
            DocumentLayoutConflictError,
            DocumentTranscriptionConflictError,
            DocumentUploadSessionConflictError,
        ),
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    if isinstance(error, DocumentPageAssetNotReadyError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    if isinstance(error, DocumentQuotaExceededError):
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(error),
        ) from error
    if isinstance(error, DocumentValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    if isinstance(error, DocumentScannerUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    if isinstance(error, DocumentStoreUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Documents service is unavailable.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected document route failure.",
    ) from error


def _format_etag(seed: str | None) -> str | None:
    if not isinstance(seed, str):
        return None
    normalized = seed.strip().replace('"', "")
    if not normalized:
        return None
    return f'"{normalized}"'


def _if_none_match_matches(if_none_match: str | None, etag: str | None) -> bool:
    if not isinstance(if_none_match, str) or not isinstance(etag, str):
        return False
    candidate = etag.strip().removeprefix("W/").strip().strip('"')
    if not candidate:
        return False
    for token in if_none_match.split(","):
        normalized_token = token.strip()
        if normalized_token == "*":
            return True
        normalized_token = normalized_token.removeprefix("W/").strip().strip('"')
        if normalized_token == candidate:
            return True
    return False


def _run_scan_background(
    *,
    project_id: str,
    import_id: str,
    actor_user_id: str,
    audit_service: AuditService,
    document_service: DocumentService,
    job_service: JobService,
) -> None:
    sleep(0.35)
    started = document_service.begin_scan(project_id=project_id, import_id=import_id)
    if started is None:
        return

    audit_service.record_event_best_effort(
        event_type="DOCUMENT_SCAN_STARTED",
        actor_user_id=actor_user_id,
        project_id=project_id,
        object_type="document_import",
        object_id=import_id,
        metadata={
            "import_id": import_id,
            "document_id": started.document_record.id,
        },
    )

    try:
        completed = document_service.complete_scan(project_id=project_id, import_id=import_id)
    except Exception as error:  # noqa: BLE001
        audit_service.record_event_best_effort(
            event_type="DOCUMENT_IMPORT_FAILED",
            actor_user_id=actor_user_id,
            project_id=project_id,
            object_type="document_import",
            object_id=import_id,
            metadata={
                "import_id": import_id,
                "stage": "scan",
                "reason": str(error),
            },
        )
        return

    if completed.import_record.status == "ACCEPTED":
        audit_service.record_event_best_effort(
            event_type="DOCUMENT_SCAN_PASSED",
            actor_user_id=actor_user_id,
            project_id=project_id,
            object_type="document_import",
            object_id=import_id,
            metadata={
                "import_id": import_id,
                "document_id": completed.document_record.id,
            },
        )
        try:
            _, created, _ = job_service.enqueue_document_processing_job(
                project_id=project_id,
                document_id=completed.document_record.id,
                job_type="EXTRACT_PAGES",
                created_by=actor_user_id,
            )
            if created:
                for attempt in range(2):
                    processed = job_service.run_worker_once(
                        worker_id=f"doc-import-bg-{import_id}-{attempt + 1}",
                        lease_seconds=60,
                    )
                    if processed is None:
                        break
        except Exception as error:  # noqa: BLE001
            audit_service.record_event_best_effort(
                event_type="DOCUMENT_IMPORT_FAILED",
                actor_user_id=actor_user_id,
                project_id=project_id,
                object_type="document_import",
                object_id=import_id,
                metadata={
                    "import_id": import_id,
                    "document_id": completed.document_record.id,
                    "stage": "extraction_enqueue",
                    "reason": str(error),
                },
            )
        return

    if completed.import_record.status == "REJECTED":
        audit_service.record_event_best_effort(
            event_type="DOCUMENT_SCAN_REJECTED",
            actor_user_id=actor_user_id,
            project_id=project_id,
            object_type="document_import",
            object_id=import_id,
            metadata={
                "import_id": import_id,
                "document_id": completed.document_record.id,
                "reason": completed.import_record.failure_reason,
            },
        )
        return

    if completed.import_record.status == "FAILED":
        audit_service.record_event_best_effort(
            event_type="DOCUMENT_IMPORT_FAILED",
            actor_user_id=actor_user_id,
            project_id=project_id,
            object_type="document_import",
            object_id=import_id,
            metadata={
                "import_id": import_id,
                "document_id": completed.document_record.id,
                "stage": "scan",
                "reason": completed.import_record.failure_reason,
            },
        )


@router.post("/documents/import-sessions", response_model=DocumentUploadSessionResponse)
def create_project_document_upload_session(
    project_id: str,
    payload: CreateUploadSessionRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentUploadSessionResponse:
    try:
        session_snapshot = document_service.start_upload_session(
            current_user=current_user,
            project_id=project_id,
            original_filename=payload.original_filename,
            expected_sha256=payload.expected_sha256,
            expected_total_bytes=payload.expected_total_bytes,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER"],
        )

    audit_service.record_event_best_effort(
        event_type="DOCUMENT_UPLOAD_STARTED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document_import",
        object_id=session_snapshot.import_record.id,
        metadata={
            "route": request_context.route_template,
            "import_id": session_snapshot.import_record.id,
            "document_id": session_snapshot.document_record.id,
            "original_filename": session_snapshot.document_record.original_filename,
        },
        request_context=request_context,
    )

    return _as_upload_session_response(
        session_snapshot=session_snapshot,
        chunk_size_limit_bytes=document_service._settings.documents_resumable_chunk_bytes,
        upload_limit_bytes=document_service._settings.documents_max_upload_bytes,
    )


@router.get(
    "/documents/import-sessions/{session_id}",
    response_model=DocumentUploadSessionResponse,
)
def get_project_document_upload_session(
    project_id: str,
    session_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentUploadSessionResponse:
    try:
        session_snapshot = document_service.get_upload_session(
            current_user=current_user,
            project_id=project_id,
            session_id=session_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_MEMBER"],
        )

    return _as_upload_session_response(
        session_snapshot=session_snapshot,
        chunk_size_limit_bytes=document_service._settings.documents_resumable_chunk_bytes,
        upload_limit_bytes=document_service._settings.documents_max_upload_bytes,
    )


@router.post(
    "/documents/import-sessions/{session_id}/chunks",
    response_model=DocumentUploadSessionResponse,
)
def append_project_document_upload_chunk(
    project_id: str,
    session_id: str,
    chunk_index: int = Query(alias="chunkIndex", ge=0),
    file: UploadFile = File(...),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentUploadSessionResponse:
    try:
        session_snapshot = document_service.append_upload_session_chunk(
            current_user=current_user,
            project_id=project_id,
            session_id=session_id,
            chunk_index=chunk_index,
            file_stream=file.file,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER"],
        )
    finally:
        file.file.close()

    return _as_upload_session_response(
        session_snapshot=session_snapshot,
        chunk_size_limit_bytes=document_service._settings.documents_resumable_chunk_bytes,
        upload_limit_bytes=document_service._settings.documents_max_upload_bytes,
    )


@router.post(
    "/documents/import-sessions/{session_id}/complete",
    response_model=DocumentUploadSessionResponse,
)
def complete_project_document_upload_session(
    project_id: str,
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
    job_service: JobService = Depends(get_job_service),
) -> DocumentUploadSessionResponse:
    try:
        session_snapshot = document_service.complete_upload_session(
            current_user=current_user,
            project_id=project_id,
            session_id=session_id,
        )
    except Exception as error:  # noqa: BLE001
        audit_service.record_event_best_effort(
            event_type="DOCUMENT_IMPORT_FAILED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="route",
            object_id=request_context.route_template,
            metadata={
                "stage": "upload",
                "reason": str(error),
            },
            request_context=request_context,
        )
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER"],
        )

    audit_service.record_event_best_effort(
        event_type="DOCUMENT_STORED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=session_snapshot.document_record.id,
        metadata={
            "import_id": session_snapshot.import_record.id,
            "document_id": session_snapshot.document_record.id,
            "stored_filename": session_snapshot.document_record.stored_filename,
            "source_meta_key": (
                f"{session_snapshot.document_record.stored_filename.rsplit('/', 1)[0]}/source-meta.json"
                if isinstance(session_snapshot.document_record.stored_filename, str)
                and "/" in session_snapshot.document_record.stored_filename
                else None
            ),
            "detected_type": session_snapshot.document_record.content_type_detected,
            "byte_count": session_snapshot.document_record.bytes,
            "sha256_prefix": (
                session_snapshot.document_record.sha256[:16]
                if isinstance(session_snapshot.document_record.sha256, str)
                else None
            ),
        },
        request_context=request_context,
    )

    background_tasks.add_task(
        _run_scan_background,
        project_id=project_id,
        import_id=session_snapshot.import_record.id,
        actor_user_id=current_user.user_id,
        audit_service=audit_service,
        document_service=document_service,
        job_service=job_service,
    )

    return _as_upload_session_response(
        session_snapshot=session_snapshot,
        chunk_size_limit_bytes=document_service._settings.documents_resumable_chunk_bytes,
        upload_limit_bytes=document_service._settings.documents_max_upload_bytes,
    )


@router.post(
    "/documents/import-sessions/{session_id}/cancel",
    response_model=DocumentUploadSessionResponse,
)
def cancel_project_document_upload_session(
    project_id: str,
    session_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentUploadSessionResponse:
    try:
        session_snapshot = document_service.cancel_upload_session(
            current_user=current_user,
            project_id=project_id,
            session_id=session_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER"],
        )
    return _as_upload_session_response(
        session_snapshot=session_snapshot,
        chunk_size_limit_bytes=document_service._settings.documents_resumable_chunk_bytes,
        upload_limit_bytes=document_service._settings.documents_max_upload_bytes,
    )


@router.post("/documents/import", response_model=DocumentImportStatusResponse)
def upload_project_document(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
    job_service: JobService = Depends(get_job_service),
) -> DocumentImportStatusResponse:
    if not isinstance(file.filename, str) or not file.filename.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A filename is required for upload.",
        )

    try:
        snapshot = document_service.upload_document(
            current_user=current_user,
            project_id=project_id,
            original_filename=file.filename,
            file_stream=file.file,
        )
    except Exception as error:  # noqa: BLE001
        audit_service.record_event_best_effort(
            event_type="DOCUMENT_IMPORT_FAILED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="route",
            object_id=request_context.route_template,
            metadata={
                "stage": "upload",
                "reason": str(error),
            },
            request_context=request_context,
        )
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER"],
        )
    finally:
        file.file.close()

    audit_service.record_event_best_effort(
        event_type="DOCUMENT_UPLOAD_STARTED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document_import",
        object_id=snapshot.import_record.id,
        metadata={
            "route": request_context.route_template,
            "import_id": snapshot.import_record.id,
            "document_id": snapshot.document_record.id,
            "original_filename": snapshot.document_record.original_filename,
        },
        request_context=request_context,
    )
    audit_service.record_event_best_effort(
        event_type="DOCUMENT_STORED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=snapshot.document_record.id,
        metadata={
            "import_id": snapshot.import_record.id,
            "document_id": snapshot.document_record.id,
            "stored_filename": snapshot.document_record.stored_filename,
            "source_meta_key": (
                f"{snapshot.document_record.stored_filename.rsplit('/', 1)[0]}/source-meta.json"
                if isinstance(snapshot.document_record.stored_filename, str)
                and "/" in snapshot.document_record.stored_filename
                else None
            ),
            "detected_type": snapshot.document_record.content_type_detected,
            "byte_count": snapshot.document_record.bytes,
            "sha256_prefix": (
                snapshot.document_record.sha256[:16]
                if isinstance(snapshot.document_record.sha256, str)
                else None
            ),
        },
        request_context=request_context,
    )

    background_tasks.add_task(
        _run_scan_background,
        project_id=project_id,
        import_id=snapshot.import_record.id,
        actor_user_id=current_user.user_id,
        audit_service=audit_service,
        document_service=document_service,
        job_service=job_service,
    )
    return _as_import_status_response(snapshot)


@router.get("/document-imports/{import_id}", response_model=DocumentImportStatusResponse)
def get_project_document_import(
    project_id: str,
    import_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentImportStatusResponse:
    try:
        snapshot = document_service.get_document_import(
            current_user=current_user,
            project_id=project_id,
            import_id=import_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )
    return _as_import_status_response(snapshot)


@router.post("/document-imports/{import_id}/cancel", response_model=DocumentImportStatusResponse)
def cancel_project_document_import(
    project_id: str,
    import_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentImportStatusResponse:
    try:
        snapshot = document_service.cancel_document_import(
            current_user=current_user,
            project_id=project_id,
            import_id=import_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    audit_service.record_event_best_effort(
        event_type="DOCUMENT_UPLOAD_CANCELED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document_import",
        object_id=import_id,
        metadata={
            "route": request_context.route_template,
            "import_id": import_id,
            "document_id": snapshot.document_record.id,
        },
        request_context=request_context,
    )
    return _as_import_status_response(snapshot)


@router.get("/documents", response_model=DocumentListResponse)
def list_project_documents(
    project_id: str,
    q: str | None = Query(default=None, max_length=240, deprecated=True),
    search: str | None = Query(default=None, max_length=240),
    status_filter: DocumentStatusLiteral | None = Query(default=None, alias="status"),
    uploader: str | None = Query(default=None, max_length=120),
    from_raw: str | None = Query(default=None, alias="from"),
    to_raw: str | None = Query(default=None, alias="to"),
    sort: Literal["updated", "created", "name"] = "updated",
    direction: Literal["asc", "desc"] = "desc",
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    query_text = search if isinstance(search, str) and search.strip() else q
    from_timestamp = _parse_datetime_filter(from_raw, param_name="from")
    to_timestamp = _parse_datetime_filter(to_raw, param_name="to", upper_bound=True)
    if from_timestamp and to_timestamp and from_timestamp > to_timestamp:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="'from' must be less than or equal to 'to'.",
        )

    try:
        items, next_cursor = document_service.list_documents(
            current_user=current_user,
            project_id=project_id,
            filters=DocumentListFilters(
                q=query_text,
                status=status_filter,
                uploader=uploader,
                from_timestamp=from_timestamp,
                to_timestamp=to_timestamp,
                sort=sort,
                direction=direction,
                cursor=cursor,
                page_size=page_size,
            ),
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    audit_service.record_event_best_effort(
        event_type="DOCUMENT_LIBRARY_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="route",
        object_id=request_context.route_template,
        metadata={
            "cursor": cursor,
            "returned_count": len(items),
            "status_filter": status_filter,
            "sort": sort,
            "direction": direction,
            "search": query_text,
            "uploader": uploader,
            "from": from_timestamp.isoformat() if from_timestamp else None,
            "to": to_timestamp.isoformat() if to_timestamp else None,
            "page_size": page_size,
        },
        request_context=request_context,
    )
    return DocumentListResponse(
        items=[_as_document_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_project_document(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    try:
        document = document_service.get_document(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    audit_service.record_event_best_effort(
        event_type="DOCUMENT_DETAIL_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document.id,
        metadata={"route": request_context.route_template},
        request_context=request_context,
    )
    return _as_document_response(document)


@router.get("/documents/{document_id}/timeline", response_model=DocumentTimelineResponse)
def get_project_document_timeline(
    project_id: str,
    document_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentTimelineResponse:
    try:
        items = document_service.list_document_timeline(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            limit=limit,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    audit_service.record_event_best_effort(
        event_type="DOCUMENT_TIMELINE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={"returned_count": len(items), "limit": limit},
        request_context=request_context,
    )
    return DocumentTimelineResponse(
        items=[_as_timeline_response_item(item) for item in items]
    )


@router.get("/documents/{document_id}/processing-runs", response_model=DocumentTimelineResponse)
def list_project_document_processing_runs(
    project_id: str,
    document_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentTimelineResponse:
    try:
        items = document_service.list_document_timeline(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            limit=limit,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    audit_service.record_event_best_effort(
        event_type="DOCUMENT_TIMELINE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(items),
            "limit": limit,
        },
        request_context=request_context,
    )
    return DocumentTimelineResponse(
        items=[_as_timeline_response_item(item) for item in items]
    )


@router.get(
    "/documents/{document_id}/processing-runs/{run_id}",
    response_model=DocumentProcessingRunDetailResponse,
)
def get_project_document_processing_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentProcessingRunDetailResponse:
    try:
        run = document_service.get_document_processing_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    audit_service.record_event_best_effort(
        event_type="DOCUMENT_PROCESSING_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document_processing_run",
        object_id=run.id,
        metadata={"route": request_context.route_template},
        request_context=request_context,
    )
    return _as_processing_run_detail_response(run)


@router.get(
    "/documents/{document_id}/processing-runs/{run_id}/status",
    response_model=DocumentProcessingRunStatusResponse,
)
def get_project_document_processing_run_status(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentProcessingRunStatusResponse:
    try:
        run = document_service.get_document_processing_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    audit_service.record_event_best_effort(
        event_type="DOCUMENT_PROCESSING_RUN_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document_processing_run",
        object_id=run.id,
        metadata={"route": request_context.route_template},
        request_context=request_context,
    )
    return _as_processing_run_status_response(run)


@router.get(
    "/documents/{document_id}/preprocessing/overview",
    response_model=PreprocessOverviewResponse,
)
def get_project_document_preprocessing_overview(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PreprocessOverviewResponse:
    try:
        snapshot = document_service.get_preprocessing_overview(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        _, active_projection_run_id, basis_references = _resolve_preprocess_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="PREPROCESS_OVERVIEW_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "active_run_id": snapshot.active_run.id if snapshot.active_run else None,
            "returned_count": snapshot.page_count,
        },
        request_context=request_context,
    )
    return PreprocessOverviewResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        projection=(
            _as_preprocess_projection_response(
                snapshot.projection,
                basis_references=basis_references,
            )
            if snapshot.projection is not None
            else None
        ),
        active_run=(
            _as_preprocess_run_response(
                snapshot.active_run,
                active_run_id=active_projection_run_id,
                basis_references=basis_references,
            )
            if snapshot.active_run is not None
            else None
        ),
        latest_run=(
            _as_preprocess_run_response(
                snapshot.latest_run,
                active_run_id=active_projection_run_id,
                basis_references=basis_references,
            )
            if snapshot.latest_run is not None
            else None
        ),
        total_runs=snapshot.total_runs,
        page_count=snapshot.page_count,
        active_status_counts=snapshot.active_status_counts,
        active_quality_gate_counts=snapshot.active_quality_gate_counts,
        active_warning_count=snapshot.active_warning_count,
    )


@router.get(
    "/documents/{document_id}/preprocessing/quality",
    response_model=PreprocessQualityResponse,
)
def get_project_document_preprocessing_quality(
    project_id: str,
    document_id: str,
    run_id: str | None = Query(default=None, alias="runId"),
    warning: str | None = Query(default=None),
    status_filter: PreprocessPageResultStatusLiteral | None = Query(
        default=None,
        alias="status",
    ),
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=100, alias="pageSize", ge=1, le=500),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PreprocessQualityResponse:
    try:
        projection, selected_run, items, next_cursor = document_service.list_preprocessing_quality(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            warning=warning,
            status=status_filter,
            cursor=cursor,
            page_size=page_size,
        )
        projection_context, active_projection_run_id, basis_references = _resolve_preprocess_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="PREPROCESS_QUALITY_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "run_id": selected_run.id if selected_run else None,
            "warning_filter": warning,
            "status_filter": status_filter,
            "cursor": cursor,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    projection_record = projection if projection is not None else projection_context
    return PreprocessQualityResponse(
        projection=(
            _as_preprocess_projection_response(
                projection_record,
                basis_references=basis_references,
            )
            if projection_record is not None
            else None
        ),
        run=(
            _as_preprocess_run_response(
                selected_run,
                active_run_id=active_projection_run_id,
                basis_references=basis_references,
            )
            if selected_run is not None
            else None
        ),
        items=[_as_preprocess_page_result_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.post(
    "/documents/{document_id}/preprocess-runs",
    response_model=PreprocessRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_document_preprocess_run(
    project_id: str,
    document_id: str,
    payload: CreatePreprocessRunRequest = Body(
        default_factory=CreatePreprocessRunRequest
    ),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PreprocessRunResponse:
    try:
        run = document_service.create_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            profile_id=payload.profile_id,
            params_json=payload.params_json,
            pipeline_version=payload.pipeline_version,
            container_digest=payload.container_digest,
            parent_run_id=payload.parent_run_id,
            supersedes_run_id=payload.supersedes_run_id,
            advanced_risk_confirmed=payload.advanced_risk_confirmed,
            advanced_risk_acknowledgement=payload.advanced_risk_acknowledgement,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="PREPROCESS_RUN_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="preprocess_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
            "profile_id": run.profile_id,
            "params_hash": run.params_hash,
            "pipeline_version": run.pipeline_version,
            "profile_risk_posture": run.params_json.get("profile_risk_posture"),
            "advanced_risk_confirmation_required": run.params_json.get(
                "advanced_risk_confirmation_required"
            ),
            "advanced_risk_confirmation": run.params_json.get(
                "advanced_risk_confirmation"
            ),
        },
        request_context=request_context,
    )
    return _as_preprocess_run_response(run)


@router.get(
    "/documents/{document_id}/preprocess-runs/active",
    response_model=PreprocessActiveRunResponse,
)
def get_project_document_active_preprocess_run(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PreprocessActiveRunResponse:
    try:
        projection, run = document_service.get_active_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        _, active_projection_run_id, basis_references = _resolve_preprocess_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="PREPROCESS_ACTIVE_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id if run else None,
        },
        request_context=request_context,
    )
    return PreprocessActiveRunResponse(
        projection=(
            _as_preprocess_projection_response(
                projection,
                basis_references=basis_references,
            )
            if projection is not None
            else None
        ),
        run=(
            _as_preprocess_run_response(
                run,
                active_run_id=active_projection_run_id,
                basis_references=basis_references,
            )
            if run is not None
            else None
        ),
    )


@router.get(
    "/documents/{document_id}/preprocess-runs",
    response_model=PreprocessRunListResponse,
)
def list_project_document_preprocess_runs(
    project_id: str,
    document_id: str,
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=50, alias="pageSize", ge=1, le=200),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PreprocessRunListResponse:
    try:
        items, next_cursor = document_service.list_preprocess_runs(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            cursor=cursor,
            page_size=page_size,
        )
        _, active_projection_run_id, basis_references = _resolve_preprocess_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="PREPROCESS_RUNS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "cursor": cursor,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return PreprocessRunListResponse(
        items=[
            _as_preprocess_run_response(
                item,
                active_run_id=active_projection_run_id,
                basis_references=basis_references,
            )
            for item in items
        ],
        next_cursor=next_cursor,
    )


@router.get(
    "/documents/{document_id}/preprocess-runs/compare",
    response_model=PreprocessCompareResponse,
)
def compare_project_document_preprocess_runs(
    project_id: str,
    document_id: str,
    base_run_id: str = Query(alias="baseRunId"),
    candidate_run_id: str = Query(alias="candidateRunId"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PreprocessCompareResponse:
    try:
        snapshot = document_service.compare_preprocess_runs(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            base_run_id=base_run_id,
            candidate_run_id=candidate_run_id,
        )
        _, active_projection_run_id, basis_references = _resolve_preprocess_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="PREPROCESS_COMPARE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "base_run_id": base_run_id,
            "candidate_run_id": candidate_run_id,
            "returned_count": len(snapshot.page_pairs),
        },
        request_context=request_context,
    )
    return PreprocessCompareResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        base_run=_as_preprocess_run_response(
            snapshot.base_run,
            active_run_id=active_projection_run_id,
            basis_references=basis_references,
        ),
        candidate_run=_as_preprocess_run_response(
            snapshot.candidate_run,
            active_run_id=active_projection_run_id,
            basis_references=basis_references,
        ),
        base_warning_count=snapshot.base_warning_count,
        candidate_warning_count=snapshot.candidate_warning_count,
        base_blocked_count=snapshot.base_blocked_count,
        candidate_blocked_count=snapshot.candidate_blocked_count,
        items=[
            PreprocessComparePageResponse(
                page_id=item.page_id,
                page_index=item.page_index,
                warning_delta=item.warning_delta,
                added_warnings=list(item.added_warnings),
                removed_warnings=list(item.removed_warnings),
                metric_deltas=dict(item.metric_deltas),
                output_availability=dict(item.output_availability),
                base=(
                    _as_preprocess_page_result_response(item.base_result)
                    if item.base_result is not None
                    else None
                ),
                candidate=(
                    _as_preprocess_page_result_response(item.candidate_result)
                    if item.candidate_result is not None
                    else None
                ),
            )
            for item in snapshot.page_pairs
        ],
    )


@router.get(
    "/documents/{document_id}/preprocess-runs/{run_id}",
    response_model=PreprocessRunResponse,
)
def get_project_document_preprocess_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PreprocessRunResponse:
    try:
        run = document_service.get_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _, active_projection_run_id, basis_references = _resolve_preprocess_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="PREPROCESS_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="preprocess_run",
        object_id=run.id,
        metadata={"route": request_context.route_template},
        request_context=request_context,
    )
    return _as_preprocess_run_response(
        run,
        active_run_id=active_projection_run_id,
        basis_references=basis_references,
    )


@router.get(
    "/documents/{document_id}/preprocess-runs/{run_id}/status",
    response_model=PreprocessRunStatusResponse,
)
def get_project_document_preprocess_run_status(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PreprocessRunStatusResponse:
    try:
        run = document_service.get_preprocess_run_status(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="PREPROCESS_RUN_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="preprocess_run",
        object_id=run.id,
        metadata={"route": request_context.route_template},
        request_context=request_context,
    )
    return _as_preprocess_run_status_response(run)


@router.get(
    "/documents/{document_id}/preprocess-runs/{run_id}/pages",
    response_model=PreprocessRunPageListResponse,
)
def list_project_document_preprocess_run_pages(
    project_id: str,
    document_id: str,
    run_id: str,
    warning: str | None = Query(default=None),
    status_filter: PreprocessPageResultStatusLiteral | None = Query(
        default=None,
        alias="status",
    ),
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=100, alias="pageSize", ge=1, le=500),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PreprocessRunPageListResponse:
    try:
        items, next_cursor = document_service.list_preprocess_run_pages(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            warning=warning,
            status=status_filter,
            cursor=cursor,
            page_size=page_size,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="PREPROCESS_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="preprocess_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "cursor": cursor,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return PreprocessRunPageListResponse(
        run_id=run_id,
        items=[_as_preprocess_page_result_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get(
    "/documents/{document_id}/preprocess-runs/{run_id}/pages/{page_id}",
    response_model=PreprocessPageResultResponse,
)
def get_project_document_preprocess_run_page(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PreprocessPageResultResponse:
    try:
        page = document_service.get_preprocess_run_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )
    return _as_preprocess_page_result_response(page)


@router.post(
    "/documents/{document_id}/preprocess-runs/{run_id}/rerun",
    response_model=PreprocessRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def rerun_project_document_preprocess_run(
    project_id: str,
    document_id: str,
    run_id: str,
    payload: RerunPreprocessRunRequest = Body(
        default_factory=RerunPreprocessRunRequest
    ),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PreprocessRunResponse:
    try:
        run = document_service.rerun_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            profile_id=payload.profile_id,
            params_json=payload.params_json,
            pipeline_version=payload.pipeline_version,
            container_digest=payload.container_digest,
            target_page_ids=payload.target_page_ids,
            advanced_risk_confirmed=payload.advanced_risk_confirmed,
            advanced_risk_acknowledgement=payload.advanced_risk_acknowledgement,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="PREPROCESS_RUN_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="preprocess_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
            "profile_id": run.profile_id,
            "params_hash": run.params_hash,
            "pipeline_version": run.pipeline_version,
            "profile_risk_posture": run.params_json.get("profile_risk_posture"),
            "advanced_risk_confirmation_required": run.params_json.get(
                "advanced_risk_confirmation_required"
            ),
            "advanced_risk_confirmation": run.params_json.get(
                "advanced_risk_confirmation"
            ),
        },
        request_context=request_context,
    )
    return _as_preprocess_run_response(run)


@router.post(
    "/documents/{document_id}/preprocess-runs/{run_id}/cancel",
    response_model=PreprocessRunResponse,
)
def cancel_project_document_preprocess_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PreprocessRunResponse:
    try:
        run = document_service.cancel_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="PREPROCESS_RUN_CANCELED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="preprocess_run",
        object_id=run.id,
        metadata={"route": request_context.route_template, "run_id": run.id},
        request_context=request_context,
    )
    return _as_preprocess_run_response(run)


@router.post(
    "/documents/{document_id}/preprocess-runs/{run_id}/activate",
    response_model=ActivatePreprocessRunResponse,
)
def activate_project_document_preprocess_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> ActivatePreprocessRunResponse:
    try:
        projection = document_service.activate_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        run = document_service.get_preprocess_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _, active_projection_run_id, basis_references = _resolve_preprocess_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="PREPROCESS_RUN_ACTIVATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="preprocess_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
        },
        request_context=request_context,
    )
    return ActivatePreprocessRunResponse(
        projection=_as_preprocess_projection_response(
            projection,
            basis_references=basis_references,
        ),
        run=_as_preprocess_run_response(
            run,
            active_run_id=active_projection_run_id,
            basis_references=basis_references,
        ),
    )


@router.get(
    "/documents/{document_id}/layout/overview",
    response_model=LayoutOverviewResponse,
)
def get_project_document_layout_overview(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutOverviewResponse:
    try:
        snapshot = document_service.get_layout_overview(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        _, active_projection_run_id = _resolve_layout_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_OVERVIEW_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "active_run_id": snapshot.active_run.id if snapshot.active_run else None,
            "returned_count": snapshot.page_count,
        },
        request_context=request_context,
    )
    return LayoutOverviewResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        projection=(
            _as_layout_projection_response(snapshot.projection)
            if snapshot.projection is not None
            else None
        ),
        active_run=(
            _as_layout_run_response(
                snapshot.active_run,
                active_run_id=active_projection_run_id,
            )
            if snapshot.active_run is not None
            else None
        ),
        latest_run=(
            _as_layout_run_response(
                snapshot.latest_run,
                active_run_id=active_projection_run_id,
            )
            if snapshot.latest_run is not None
            else None
        ),
        total_runs=snapshot.total_runs,
        page_count=snapshot.page_count,
        active_status_counts=snapshot.active_status_counts,
        active_recall_counts=snapshot.active_recall_counts,
        summary=LayoutSummaryResponse(
            regions_detected=snapshot.summary.regions_detected,
            lines_detected=snapshot.summary.lines_detected,
            pages_with_issues=snapshot.summary.pages_with_issues,
            coverage_percent=snapshot.summary.coverage_percent,
            structure_confidence=snapshot.summary.structure_confidence,
        ),
    )


@router.post(
    "/documents/{document_id}/layout-runs",
    response_model=LayoutRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_document_layout_run(
    project_id: str,
    document_id: str,
    payload: CreateLayoutRunRequest = Body(default_factory=CreateLayoutRunRequest),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutRunResponse:
    try:
        run = document_service.create_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            input_preprocess_run_id=payload.input_preprocess_run_id,
            model_id=payload.model_id,
            profile_id=payload.profile_id,
            params_json=payload.params_json,
            pipeline_version=payload.pipeline_version,
            container_digest=payload.container_digest,
            parent_run_id=payload.parent_run_id,
            supersedes_run_id=payload.supersedes_run_id,
        )
        _, active_projection_run_id = _resolve_layout_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_RUN_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="layout_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
            "input_preprocess_run_id": run.input_preprocess_run_id,
            "params_hash": run.params_hash,
            "pipeline_version": run.pipeline_version,
        },
        request_context=request_context,
    )
    if run.status == "RUNNING":
        audit_service.record_event_best_effort(
            event_type="LAYOUT_RUN_STARTED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="layout_run",
            object_id=run.id,
            metadata={
                "run_id": run.id,
                "document_id": run.document_id,
                "pipeline_version": run.pipeline_version,
            },
            request_context=request_context,
        )
    elif run.status == "SUCCEEDED":
        audit_service.record_event_best_effort(
            event_type="LAYOUT_RUN_FINISHED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="layout_run",
            object_id=run.id,
            metadata={
                "run_id": run.id,
                "document_id": run.document_id,
                "status": run.status,
            },
            request_context=request_context,
        )
    elif run.status == "FAILED":
        audit_service.record_event_best_effort(
            event_type="LAYOUT_RUN_FAILED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="layout_run",
            object_id=run.id,
            metadata={
                "run_id": run.id,
                "document_id": run.document_id,
                "reason": run.failure_reason,
            },
            request_context=request_context,
        )
    return _as_layout_run_response(run, active_run_id=active_projection_run_id)


@router.get(
    "/documents/{document_id}/layout-runs/active",
    response_model=LayoutActiveRunResponse,
)
def get_project_document_active_layout_run(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutActiveRunResponse:
    try:
        projection, run = document_service.get_active_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        _, active_projection_run_id = _resolve_layout_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_ACTIVE_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id if run else None,
        },
        request_context=request_context,
    )
    return LayoutActiveRunResponse(
        projection=(
            _as_layout_projection_response(projection)
            if projection is not None
            else None
        ),
        run=(
            _as_layout_run_response(
                run,
                active_run_id=active_projection_run_id,
            )
            if run is not None
            else None
        ),
    )


@router.get(
    "/documents/{document_id}/layout-runs",
    response_model=LayoutRunListResponse,
)
def list_project_document_layout_runs(
    project_id: str,
    document_id: str,
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=50, alias="pageSize", ge=1, le=200),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutRunListResponse:
    try:
        items, next_cursor = document_service.list_layout_runs(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            cursor=cursor,
            page_size=page_size,
        )
        _, active_projection_run_id = _resolve_layout_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_RUNS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "cursor": cursor,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return LayoutRunListResponse(
        items=[
            _as_layout_run_response(
                item,
                active_run_id=active_projection_run_id,
            )
            for item in items
        ],
        next_cursor=next_cursor,
    )


@router.get(
    "/documents/{document_id}/layout-runs/{run_id}",
    response_model=LayoutRunResponse,
)
def get_project_document_layout_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutRunResponse:
    try:
        run = document_service.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _, active_projection_run_id = _resolve_layout_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_RUNS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="layout_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "cursor": 0,
            "returned_count": 1,
        },
        request_context=request_context,
    )
    return _as_layout_run_response(run, active_run_id=active_projection_run_id)


@router.get(
    "/documents/{document_id}/layout-runs/{run_id}/status",
    response_model=LayoutRunStatusResponse,
)
def get_project_document_layout_run_status(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutRunStatusResponse:
    try:
        run = document_service.get_layout_run_status(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_RUNS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="layout_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "cursor": 0,
            "returned_count": 1,
        },
        request_context=request_context,
    )
    return _as_layout_run_status_response(run)


@router.get(
    "/documents/{document_id}/layout-runs/{run_id}/pages",
    response_model=LayoutRunPageListResponse,
)
def list_project_document_layout_run_pages(
    project_id: str,
    document_id: str,
    run_id: str,
    status_filter: PageLayoutResultStatusLiteral | None = Query(
        default=None,
        alias="status",
    ),
    page_recall_status_filter: PageRecallStatusLiteral | None = Query(
        default=None,
        alias="pageRecallStatus",
    ),
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=100, alias="pageSize", ge=1, le=500),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutRunPageListResponse:
    try:
        items, next_cursor = document_service.list_layout_run_pages(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            status=status_filter,
            page_recall_status=page_recall_status_filter,
            cursor=cursor,
            page_size=page_size,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_TRIAGE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="layout_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "cursor": cursor,
            "status_filter": status_filter,
            "page_recall_status_filter": page_recall_status_filter,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return LayoutRunPageListResponse(
        run_id=run_id,
        items=[_as_layout_page_result_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get(
    "/documents/{document_id}/layout-runs/{run_id}/pages/{page_id}/recall-status",
    response_model=LayoutPageRecallStatusResponse,
)
def get_project_document_layout_page_recall_status(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutPageRecallStatusResponse:
    try:
        snapshot = document_service.get_layout_page_recall_status(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_RECALL_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "page_recall_status": snapshot.page_recall_status,
            "unresolved_count": snapshot.unresolved_count,
        },
        request_context=request_context,
    )
    return _as_layout_page_recall_status_response(snapshot)


@router.get(
    "/documents/{document_id}/layout-runs/{run_id}/pages/{page_id}/rescue-candidates",
    response_model=LayoutRescueCandidateListResponse,
)
def list_project_document_layout_page_rescue_candidates(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutRescueCandidateListResponse:
    try:
        status_snapshot = document_service.get_layout_page_recall_status(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        candidates = document_service.list_layout_page_rescue_candidates(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_RESCUE_CANDIDATES_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "returned_count": len(candidates),
        },
        request_context=request_context,
    )
    return LayoutRescueCandidateListResponse(
        run_id=run_id,
        page_id=page_id,
        page_index=status_snapshot.page_index,
        items=[_as_layout_rescue_candidate_response(item) for item in candidates],
    )


@router.get("/documents/{document_id}/layout-runs/{run_id}/pages/{page_id}/overlay")
def get_project_document_layout_page_overlay(
    request: Request,
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        overlay_asset: DocumentLayoutOverlayAsset = (
            document_service.read_layout_page_overlay(
                current_user=current_user,
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
            )
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_OVERLAY_ACCESSED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "document_id": document_id,
            "page_id": page_id,
            "run_id": run_id,
        },
        request_context=request_context,
    )
    etag = _format_etag(overlay_asset.etag_seed)
    response_headers = {
        "Cache-Control": "private, no-cache, max-age=0, must-revalidate",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Vary": PAGE_IMAGE_CACHE_VARY_HEADER,
        "X-Content-Type-Options": "nosniff",
    }
    if etag:
        response_headers["ETag"] = etag
    if _if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers=response_headers,
        )
    return JSONResponse(
        content=overlay_asset.payload,
        status_code=status.HTTP_200_OK,
        headers=response_headers,
    )


@router.patch(
    "/documents/{document_id}/layout-runs/{run_id}/pages/{page_id}/elements",
    response_model=LayoutElementsUpdateResponse,
)
def patch_project_document_layout_page_elements(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    payload: LayoutElementsUpdateRequest = Body(...),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutElementsUpdateResponse:
    try:
        snapshot = document_service.update_layout_page_elements(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            version_etag=payload.version_etag,
            operations=[
                {
                    key: value
                    for key, value in {
                        "kind": operation.kind,
                        "regionId": operation.region_id,
                        "lineId": operation.line_id,
                        "parentRegionId": operation.parent_region_id,
                        "beforeLineId": operation.before_line_id,
                        "afterLineId": operation.after_line_id,
                        "polygon": operation.polygon,
                        "baseline": operation.baseline,
                        "regionType": operation.region_type,
                        "includeInReadingOrder": operation.include_in_reading_order,
                        "lineIds": operation.line_ids,
                    }.items()
                    if value is not None
                }
                for operation in payload.operations
            ],
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    operation_kinds = sorted({operation.kind for operation in payload.operations})
    audit_service.record_event_best_effort(
        event_type="LAYOUT_EDIT_APPLIED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "layout_version_id": snapshot.layout_version_id,
            "version_etag": snapshot.version_etag,
            "operations_applied": snapshot.operations_applied,
            "operation_kinds": operation_kinds,
        },
        request_context=request_context,
    )
    if snapshot.downstream_transcription_invalidated:
        audit_service.record_event_best_effort(
            event_type="LAYOUT_DOWNSTREAM_INVALIDATED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="page",
            object_id=page_id,
            metadata={
                "route": request_context.route_template,
                "document_id": document_id,
                "run_id": run_id,
                "page_id": page_id,
                "layout_version_id": snapshot.layout_version_id,
                "downstream_state": (
                    snapshot.downstream_transcription_state or "STALE"
                ),
                "reason": snapshot.downstream_transcription_invalidated_reason
                or "Layout edit changed active transcription basis.",
            },
            request_context=request_context,
        )
    return _as_layout_elements_update_response(snapshot)


@router.patch(
    "/documents/{document_id}/layout-runs/{run_id}/pages/{page_id}/reading-order",
    response_model=LayoutReadingOrderUpdateResponse,
)
def patch_project_document_layout_page_reading_order(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    payload: LayoutReadingOrderUpdateRequest = Body(...),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutReadingOrderUpdateResponse:
    try:
        snapshot = document_service.update_layout_page_reading_order(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            version_etag=payload.version_etag,
            mode=payload.mode,
            groups=[
                {
                    "id": group.id,
                    "ordered": group.ordered,
                    "regionIds": list(group.region_ids),
                }
                for group in payload.groups
            ],
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )
    audit_service.record_event_best_effort(
        event_type="LAYOUT_READING_ORDER_UPDATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "layout_version_id": snapshot.layout_version_id,
            "version_etag": snapshot.version_etag,
            "mode": snapshot.mode,
            "group_count": len(snapshot.groups),
            "order_withheld": bool(snapshot.signals_json.get("orderWithheld")),
            "ambiguity_score": snapshot.signals_json.get("ambiguityScore"),
            "source": snapshot.signals_json.get("source"),
        },
        request_context=request_context,
    )
    return _as_layout_reading_order_update_response(snapshot)


@router.get("/documents/{document_id}/layout-runs/{run_id}/pages/{page_id}/pagexml")
def get_project_document_layout_pagexml(
    request: Request,
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        pagexml_asset: DocumentLayoutPageXmlAsset = document_service.read_layout_page_xml(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_PAGEXML_ACCESSED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "document_id": document_id,
            "page_id": page_id,
            "run_id": run_id,
        },
        request_context=request_context,
    )
    etag = _format_etag(pagexml_asset.etag_seed)
    response_headers = {
        "Cache-Control": "private, no-cache, max-age=0, must-revalidate",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Vary": PAGE_IMAGE_CACHE_VARY_HEADER,
        "X-Content-Type-Options": "nosniff",
    }
    if etag:
        response_headers["ETag"] = etag
    if _if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers=response_headers,
        )
    return Response(
        content=pagexml_asset.payload,
        media_type=pagexml_asset.media_type,
        headers=response_headers,
    )


@router.get(
    "/documents/{document_id}/layout-runs/{run_id}/pages/{page_id}/lines/{line_id}/artifacts",
    response_model=LayoutLineArtifactsResponse,
)
def get_project_document_layout_line_artifacts(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    line_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutLineArtifactsResponse:
    try:
        snapshot = document_service.get_layout_line_artifacts(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_LINE_ARTIFACTS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="line",
        object_id=line_id,
        metadata={
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "line_id": line_id,
        },
        request_context=request_context,
    )
    return _as_layout_line_artifacts_response(snapshot)


@router.get("/documents/{document_id}/layout-runs/{run_id}/pages/{page_id}/lines/{line_id}/crop")
def get_project_document_layout_line_crop(
    request: Request,
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    line_id: str,
    variant: LayoutLineArtifactCropVariantLiteral = Query(default="line"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        image_asset = document_service.read_layout_line_crop_image(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
            variant=variant,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_LINE_CROP_ACCESSED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="line",
        object_id=line_id,
        metadata={
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "line_id": line_id,
            "variant": variant,
        },
        request_context=request_context,
    )
    etag = _format_etag(image_asset.etag_seed)
    response_headers = {
        "Cache-Control": image_asset.cache_control,
        "Cross-Origin-Resource-Policy": "same-origin",
        "Vary": PAGE_IMAGE_CACHE_VARY_HEADER,
        "X-Content-Type-Options": "nosniff",
    }
    if etag:
        response_headers["ETag"] = etag
    if _if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers=response_headers,
        )
    return Response(
        content=image_asset.payload,
        media_type=image_asset.media_type,
        headers=response_headers,
    )


@router.get(
    "/documents/{document_id}/layout-runs/{run_id}/pages/{page_id}/lines/{line_id}/context"
)
def get_project_document_layout_line_context_window(
    request: Request,
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    line_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        context_asset: DocumentLayoutContextWindowAsset = (
            document_service.read_layout_line_context_window(
                current_user=current_user,
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
                line_id=line_id,
            )
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_CONTEXT_WINDOW_ACCESSED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="line",
        object_id=line_id,
        metadata={
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "line_id": line_id,
        },
        request_context=request_context,
    )
    etag = _format_etag(context_asset.etag_seed)
    response_headers = {
        "Cache-Control": "private, no-cache, max-age=0, must-revalidate",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Vary": PAGE_IMAGE_CACHE_VARY_HEADER,
        "X-Content-Type-Options": "nosniff",
    }
    if etag:
        response_headers["ETag"] = etag
    if _if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers=response_headers,
        )
    return JSONResponse(
        content=context_asset.payload,
        status_code=status.HTTP_200_OK,
        headers=response_headers,
    )


@router.get("/documents/{document_id}/layout-runs/{run_id}/pages/{page_id}/thumbnail")
def get_project_document_layout_page_thumbnail(
    request: Request,
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        image_asset = document_service.read_layout_page_thumbnail(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_THUMBNAIL_ACCESSED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
        },
        request_context=request_context,
    )
    etag = _format_etag(image_asset.etag_seed)
    response_headers = {
        "Cache-Control": image_asset.cache_control,
        "Cross-Origin-Resource-Policy": "same-origin",
        "Vary": PAGE_IMAGE_CACHE_VARY_HEADER,
        "X-Content-Type-Options": "nosniff",
    }
    if etag:
        response_headers["ETag"] = etag
    if _if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers=response_headers,
        )
    return Response(
        content=image_asset.payload,
        media_type=image_asset.media_type,
        headers=response_headers,
    )


@router.post(
    "/documents/{document_id}/layout-runs/{run_id}/cancel",
    response_model=LayoutRunResponse,
)
def cancel_project_document_layout_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> LayoutRunResponse:
    try:
        run = document_service.cancel_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _, active_projection_run_id = _resolve_layout_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_RUN_CANCELED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="layout_run",
        object_id=run.id,
        metadata={"route": request_context.route_template, "run_id": run.id},
        request_context=request_context,
    )
    return _as_layout_run_response(run, active_run_id=active_projection_run_id)


@router.post(
    "/documents/{document_id}/layout-runs/{run_id}/activate",
    response_model=ActivateLayoutRunResponse,
)
def activate_project_document_layout_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> ActivateLayoutRunResponse:
    try:
        projection = document_service.activate_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        run = document_service.get_layout_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _, active_projection_run_id = _resolve_layout_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except DocumentLayoutConflictError as error:
        activation_gate = getattr(error, "activation_gate", None)
        audit_service.record_event_best_effort(
            event_type="LAYOUT_ACTIVATION_BLOCKED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="layout_run",
            object_id=run_id,
            metadata={
                "route": request_context.route_template,
                "run_id": run_id,
                "document_id": document_id,
                "reason": str(error),
            },
            request_context=request_context,
        )
        payload: dict[str, object] = {"detail": str(error)}
        if activation_gate is not None:
            gate_response = _as_layout_activation_gate_response(activation_gate)
            payload["activationGate"] = gate_response.model_dump(
                by_alias=True,
                mode="json",
            )
            payload["blockers"] = [
                blocker.model_dump(by_alias=True, mode="json")
                for blocker in gate_response.blockers
            ]
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=payload,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="LAYOUT_RUN_ACTIVATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="layout_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
        },
        request_context=request_context,
    )
    return ActivateLayoutRunResponse(
        projection=_as_layout_projection_response(projection),
        run=_as_layout_run_response(
            run,
            active_run_id=active_projection_run_id,
        ),
        activation_gate=(
            _as_layout_activation_gate_response(run.activation_gate)
            if run.activation_gate is not None
            else LayoutActivationGateResponse(
                eligible=True,
                blocker_count=0,
                blockers=[],
                evaluated_at=datetime.now(timezone.utc),
                downstream_impact=LayoutActivationDownstreamImpactResponse(
                    transcription_state_after_activation=projection.downstream_transcription_state,
                    invalidates_existing_transcription_basis=(
                        projection.downstream_transcription_state == "STALE"
                    ),
                    reason=projection.downstream_transcription_invalidated_reason,
                    has_active_transcription_projection=(
                        projection.downstream_transcription_state != "NOT_STARTED"
                    ),
                    active_transcription_run_id=None,
                ),
            )
        ),
    )


@router.get(
    "/documents/{document_id}/transcription/overview",
    response_model=TranscriptionOverviewResponse,
)
def get_project_document_transcription_overview(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionOverviewResponse:
    try:
        snapshot = document_service.get_transcription_overview(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        _, active_projection_run_id = _resolve_transcription_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_OVERVIEW_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "active_run_id": snapshot.active_run.id if snapshot.active_run else None,
            "returned_count": snapshot.page_count,
        },
        request_context=request_context,
    )
    return TranscriptionOverviewResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        projection=(
            _as_transcription_projection_response(snapshot.projection)
            if snapshot.projection is not None
            else None
        ),
        active_run=(
            _as_transcription_run_response(
                snapshot.active_run,
                active_run_id=active_projection_run_id,
            )
            if snapshot.active_run is not None
            else None
        ),
        latest_run=(
            _as_transcription_run_response(
                snapshot.latest_run,
                active_run_id=active_projection_run_id,
            )
            if snapshot.latest_run is not None
            else None
        ),
        total_runs=snapshot.total_runs,
        page_count=snapshot.page_count,
        active_status_counts=snapshot.active_status_counts,
        active_line_count=snapshot.active_line_count,
        active_token_count=snapshot.active_token_count,
        active_anchor_refresh_required=snapshot.active_anchor_refresh_required,
        active_low_confidence_lines=snapshot.active_low_confidence_lines,
    )


@router.get(
    "/documents/{document_id}/transcription/triage",
    response_model=TranscriptionTriageResponse,
)
def get_project_document_transcription_triage(
    project_id: str,
    document_id: str,
    run_id: str | None = Query(default=None, alias="runId"),
    status_filter: TranscriptionRunStatusLiteral | None = Query(
        default=None,
        alias="status",
    ),
    confidence_below: float | None = Query(default=None, alias="confidenceBelow"),
    page_number: int | None = Query(default=None, alias="page", ge=1),
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=100, alias="pageSize", ge=1, le=500),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionTriageResponse:
    try:
        projection, run, items, next_cursor = document_service.list_transcription_triage(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            status=status_filter,
            confidence_below=confidence_below,
            page_number=page_number,
            cursor=cursor,
            page_size=page_size,
        )
        _, active_projection_run_id = _resolve_transcription_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_TRIAGE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id if run else None,
            "cursor": cursor,
            "status_filter": status_filter,
            "confidence_below": confidence_below,
            "page": page_number,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return TranscriptionTriageResponse(
        projection=(
            _as_transcription_projection_response(projection)
            if projection is not None
            else None
        ),
        run=(
            _as_transcription_run_response(
                run,
                active_run_id=active_projection_run_id,
            )
            if run is not None
            else None
        ),
        items=[_as_transcription_triage_page_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get(
    "/documents/{document_id}/transcription/metrics",
    response_model=TranscriptionMetricsResponse,
)
def get_project_document_transcription_metrics(
    project_id: str,
    document_id: str,
    run_id: str | None = Query(default=None, alias="runId"),
    confidence_below: float | None = Query(default=None, alias="confidenceBelow"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionMetricsResponse:
    try:
        projection, run, metrics = document_service.get_transcription_metrics(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            confidence_below=confidence_below,
        )
        _, active_projection_run_id = _resolve_transcription_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_TRIAGE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id if run else None,
            "confidence_below": confidence_below,
            "returned_count": metrics.page_count,
            "surface": "metrics",
        },
        request_context=request_context,
    )
    return _as_transcription_metrics_response(
        projection=projection,
        run=run,
        metrics=metrics,
        active_run_id=active_projection_run_id,
    )


@router.patch(
    "/documents/{document_id}/transcription/triage/pages/{page_id}/assignment",
    response_model=UpdateTranscriptionTriageAssignmentResponse,
)
def patch_project_document_transcription_triage_assignment(
    project_id: str,
    document_id: str,
    page_id: str,
    payload: UpdateTranscriptionTriageAssignmentRequest = Body(
        default_factory=UpdateTranscriptionTriageAssignmentRequest
    ),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> UpdateTranscriptionTriageAssignmentResponse:
    try:
        projection, run, item = document_service.update_transcription_triage_page_assignment(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
            reviewer_user_id=payload.reviewer_user_id,
            run_id=payload.run_id,
        )
        _, active_projection_run_id = _resolve_transcription_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_TRIAGE_ASSIGNMENT_UPDATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document_page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "page_id": page_id,
            "reviewer_user_id": item.reviewer_assignment_user_id,
        },
        request_context=request_context,
    )
    return UpdateTranscriptionTriageAssignmentResponse(
        projection=(
            _as_transcription_projection_response(projection)
            if projection is not None
            else None
        ),
        run=_as_transcription_run_response(
            run,
            active_run_id=active_projection_run_id,
        ),
        item=_as_transcription_triage_page_response(item),
    )


@router.post(
    "/documents/{document_id}/transcription-runs",
    response_model=TranscriptionRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_document_transcription_run(
    project_id: str,
    document_id: str,
    payload: CreateTranscriptionRunRequest = Body(
        default_factory=CreateTranscriptionRunRequest
    ),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionRunResponse:
    try:
        run = document_service.create_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            input_preprocess_run_id=payload.input_preprocess_run_id,
            input_layout_run_id=payload.input_layout_run_id,
            engine=payload.engine,
            model_id=payload.model_id,
            project_model_assignment_id=payload.project_model_assignment_id,
            prompt_template_id=payload.prompt_template_id,
            prompt_template_sha256=payload.prompt_template_sha256,
            response_schema_version=payload.response_schema_version or 1,
            confidence_basis=payload.confidence_basis,
            confidence_calibration_version=payload.confidence_calibration_version,
            params_json=payload.params_json,
            pipeline_version=payload.pipeline_version,
            container_digest=payload.container_digest,
            supersedes_transcription_run_id=payload.supersedes_transcription_run_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_RUN_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="transcription_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
            "engine": run.engine,
            "model_id": run.model_id,
            "pipeline_version": run.pipeline_version,
        },
        request_context=request_context,
    )
    return _as_transcription_run_response(run)


@router.post(
    "/documents/{document_id}/transcription-runs/fallback",
    response_model=TranscriptionRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_document_fallback_transcription_run(
    project_id: str,
    document_id: str,
    payload: CreateTranscriptionFallbackRunRequest = Body(
        default_factory=CreateTranscriptionFallbackRunRequest
    ),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionRunResponse:
    try:
        run, reason_codes = document_service.create_fallback_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            base_run_id=payload.base_run_id,
            engine=payload.engine,
            model_id=payload.model_id,
            project_model_assignment_id=payload.project_model_assignment_id,
            prompt_template_id=payload.prompt_template_id,
            prompt_template_sha256=payload.prompt_template_sha256,
            response_schema_version=payload.response_schema_version or 1,
            confidence_calibration_version=payload.confidence_calibration_version,
            params_json=payload.params_json,
            pipeline_version=payload.pipeline_version,
            container_digest=payload.container_digest,
            fallback_reason_codes=payload.fallback_reason_codes,
            fallback_confidence_threshold=payload.fallback_confidence_threshold,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_FALLBACK_RUN_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="transcription_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
            "engine": run.engine,
            "model_id": run.model_id,
            "reason_codes": list(reason_codes),
        },
        request_context=request_context,
    )
    return _as_transcription_run_response(run)


@router.get(
    "/documents/{document_id}/transcription-runs/active",
    response_model=TranscriptionActiveRunResponse,
)
def get_project_document_active_transcription_run(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionActiveRunResponse:
    try:
        projection, run = document_service.get_active_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        _, active_projection_run_id = _resolve_transcription_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_ACTIVE_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id if run else None,
        },
        request_context=request_context,
    )
    return TranscriptionActiveRunResponse(
        projection=(
            _as_transcription_projection_response(projection)
            if projection is not None
            else None
        ),
        run=(
            _as_transcription_run_response(
                run,
                active_run_id=active_projection_run_id,
            )
            if run is not None
            else None
        ),
    )


@router.get(
    "/documents/{document_id}/transcription-runs",
    response_model=TranscriptionRunListResponse,
)
def list_project_document_transcription_runs(
    project_id: str,
    document_id: str,
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=50, alias="pageSize", ge=1, le=200),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionRunListResponse:
    try:
        items, next_cursor = document_service.list_transcription_runs(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            cursor=cursor,
            page_size=page_size,
        )
        _, active_projection_run_id = _resolve_transcription_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "cursor": cursor,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return TranscriptionRunListResponse(
        items=[
            _as_transcription_run_response(
                item,
                active_run_id=active_projection_run_id,
            )
            for item in items
        ],
        next_cursor=next_cursor,
    )


@router.get(
    "/documents/{document_id}/transcription-runs/compare",
    response_model=TranscriptionCompareResponse,
)
def compare_project_document_transcription_runs(
    project_id: str,
    document_id: str,
    base_run_id: str = Query(alias="baseRunId"),
    candidate_run_id: str = Query(alias="candidateRunId"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionCompareResponse:
    try:
        snapshot = document_service.compare_transcription_runs(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            base_run_id=base_run_id,
            candidate_run_id=candidate_run_id,
        )
        _, active_projection_run_id = _resolve_transcription_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_RUN_COMPARE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "base_run_id": base_run_id,
            "candidate_run_id": candidate_run_id,
            "page_count": len(snapshot.pages),
        },
        request_context=request_context,
    )
    return _as_transcription_compare_response(
        snapshot=snapshot,
        active_run_id=active_projection_run_id,
    )


@router.post(
    "/documents/{document_id}/transcription-runs/compare/decisions",
    response_model=RecordTranscriptionCompareDecisionsResponse,
)
def record_project_document_transcription_compare_decisions(
    project_id: str,
    document_id: str,
    payload: RecordTranscriptionCompareDecisionsRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RecordTranscriptionCompareDecisionsResponse:
    try:
        persisted_items = document_service.record_transcription_compare_decisions(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            base_run_id=payload.base_run_id,
            candidate_run_id=payload.candidate_run_id,
            items=[
                {
                    "pageId": item.page_id,
                    "lineId": item.line_id,
                    "tokenId": item.token_id,
                    "decision": item.decision,
                    "decisionReason": item.decision_reason,
                    "decisionEtag": item.decision_etag,
                }
                for item in payload.items
            ],
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    for persisted in persisted_items:
        audit_service.record_event_best_effort(
            event_type="TRANSCRIPTION_COMPARE_DECISION_RECORDED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="transcription_compare_decision",
            object_id=persisted.id,
            metadata={
                "route": request_context.route_template,
                "document_id": document_id,
                "base_run_id": persisted.base_run_id,
                "candidate_run_id": persisted.candidate_run_id,
                "page_id": persisted.page_id,
                "line_id": persisted.line_id,
                "token_id": persisted.token_id,
                "decision": persisted.decision,
                "decision_etag": persisted.decision_etag,
            },
            request_context=request_context,
        )
    return RecordTranscriptionCompareDecisionsResponse(
        document_id=document_id,
        project_id=project_id,
        base_run_id=payload.base_run_id,
        candidate_run_id=payload.candidate_run_id,
        items=[
            _as_transcription_compare_decision_response(item)
            for item in persisted_items
        ],
    )


@router.get(
    "/documents/{document_id}/transcription-runs/{run_id}",
    response_model=TranscriptionRunResponse,
)
def get_project_document_transcription_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionRunResponse:
    try:
        run = document_service.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _, active_projection_run_id = _resolve_transcription_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="transcription_run",
        object_id=run.id,
        metadata={"route": request_context.route_template},
        request_context=request_context,
    )
    return _as_transcription_run_response(run, active_run_id=active_projection_run_id)


@router.get(
    "/documents/{document_id}/transcription-runs/{run_id}/status",
    response_model=TranscriptionRunStatusResponse,
)
def get_project_document_transcription_run_status(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionRunStatusResponse:
    try:
        run = document_service.get_transcription_run_status(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type=(
            "TRANSCRIPTION_FALLBACK_RUN_STATUS_VIEWED"
            if run.engine in {"KRAKEN_LINE", "TROCR_LINE", "DAN_PAGE"}
            else "TRANSCRIPTION_RUN_STATUS_VIEWED"
        ),
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="transcription_run",
        object_id=run.id,
        metadata={"route": request_context.route_template},
        request_context=request_context,
    )
    return _as_transcription_run_status_response(run)


@router.get(
    "/documents/{document_id}/transcription-runs/{run_id}/pages",
    response_model=TranscriptionRunPageListResponse,
)
def list_project_document_transcription_run_pages(
    project_id: str,
    document_id: str,
    run_id: str,
    status_filter: TranscriptionRunStatusLiteral | None = Query(
        default=None,
        alias="status",
    ),
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=100, alias="pageSize", ge=1, le=500),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionRunPageListResponse:
    try:
        items, next_cursor = document_service.list_transcription_run_pages(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            status=status_filter,
            cursor=cursor,
            page_size=page_size,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="transcription_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "cursor": cursor,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return TranscriptionRunPageListResponse(
        run_id=run_id,
        items=[_as_transcription_page_result_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.post(
    "/documents/{document_id}/transcription-runs/{run_id}/activate",
    response_model=ActivateTranscriptionRunResponse,
)
def activate_project_document_transcription_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> ActivateTranscriptionRunResponse:
    try:
        projection = document_service.activate_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        run = document_service.get_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _, active_projection_run_id = _resolve_transcription_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_RUN_ACTIVATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="transcription_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
        },
        request_context=request_context,
    )
    return ActivateTranscriptionRunResponse(
        projection=_as_transcription_projection_response(projection),
        run=_as_transcription_run_response(
            run,
            active_run_id=active_projection_run_id,
        ),
    )


@router.post(
    "/documents/{document_id}/transcription-runs/{run_id}/cancel",
    response_model=TranscriptionRunResponse,
)
def cancel_project_document_transcription_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionRunResponse:
    try:
        run = document_service.cancel_transcription_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _, active_projection_run_id = _resolve_transcription_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type=(
            "TRANSCRIPTION_FALLBACK_RUN_CANCELED"
            if run.engine in {"KRAKEN_LINE", "TROCR_LINE", "DAN_PAGE"}
            else "TRANSCRIPTION_RUN_CANCELED"
        ),
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="transcription_run",
        object_id=run.id,
        metadata={"route": request_context.route_template, "run_id": run.id},
        request_context=request_context,
    )
    return _as_transcription_run_response(run, active_run_id=active_projection_run_id)


@router.get(
    "/documents/{document_id}/transcription-runs/{run_id}/pages/{page_id}/lines",
    response_model=TranscriptionLineResultListResponse,
)
def list_project_document_transcription_run_page_lines(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    workspace_view: bool = Query(default=False, alias="workspaceView"),
    line_id: str | None = Query(default=None, alias="lineId", min_length=1, max_length=200),
    token_id: str | None = Query(default=None, alias="tokenId", min_length=1, max_length=200),
    source_kind: TranscriptionTokenSourceKindLiteral | None = Query(
        default=None,
        alias="sourceKind",
    ),
    source_ref_id: str | None = Query(
        default=None,
        alias="sourceRefId",
        min_length=1,
        max_length=200,
    ),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionLineResultListResponse:
    try:
        items = document_service.list_transcription_run_page_lines(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "document_id": document_id,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    if workspace_view:
        workspace_metadata: dict[str, object] = {
            "route": request_context.route_template,
            "run_id": run_id,
            "document_id": document_id,
            "page_id": page_id,
        }
        if line_id is not None:
            workspace_metadata["line_id"] = line_id
        if token_id is not None:
            workspace_metadata["token_id"] = token_id
        if source_kind is not None:
            workspace_metadata["source_kind"] = source_kind
        if source_ref_id is not None:
            workspace_metadata["source_ref_id"] = source_ref_id
        audit_service.record_event_best_effort(
            event_type="TRANSCRIPTION_WORKSPACE_VIEWED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="page",
            object_id=page_id,
            metadata=workspace_metadata,
            request_context=request_context,
        )
    return TranscriptionLineResultListResponse(
        run_id=run_id,
        page_id=page_id,
        items=[_as_transcription_line_result_response(item) for item in items],
    )


@router.patch(
    "/documents/{document_id}/transcription-runs/{run_id}/pages/{page_id}/lines/{line_id}",
    response_model=CorrectTranscriptionLineResponse,
)
def correct_project_document_transcription_line(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    line_id: str,
    payload: CorrectTranscriptionLineRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> CorrectTranscriptionLineResponse:
    try:
        snapshot = document_service.correct_transcription_line(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
            text_diplomatic=payload.text_diplomatic,
            version_etag=payload.version_etag,
            edit_reason=payload.edit_reason,
        )
    except Exception as error:  # noqa: BLE001
        if isinstance(error, DocumentTranscriptionConflictError):
            audit_service.record_event_best_effort(
                event_type="TRANSCRIPT_EDIT_CONFLICT_DETECTED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                object_type="transcription_line",
                object_id=line_id,
                metadata={
                    "route": request_context.route_template,
                    "document_id": document_id,
                    "run_id": run_id,
                    "page_id": page_id,
                    "line_id": line_id,
                    "version_etag": payload.version_etag,
                },
                request_context=request_context,
            )
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPT_LINE_CORRECTED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="transcript_version",
        object_id=snapshot.active_version.id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "line_id": line_id,
            "transcript_version_id": snapshot.active_version.id,
            "version_etag": snapshot.active_version.version_etag,
            "token_anchor_status": snapshot.line.token_anchor_status,
        },
        request_context=request_context,
    )
    if snapshot.downstream_projection is not None:
        audit_service.record_event_best_effort(
            event_type="TRANSCRIPT_DOWNSTREAM_INVALIDATED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="document",
            object_id=document_id,
            metadata={
                "route": request_context.route_template,
                "document_id": document_id,
                "run_id": run_id,
                "page_id": page_id,
                "line_id": line_id,
                "downstream_state": snapshot.downstream_projection.downstream_redaction_state,
                "reason": snapshot.downstream_projection.downstream_redaction_invalidated_reason,
            },
            request_context=request_context,
        )
    return _as_correct_transcription_line_response(snapshot)


@router.get(
    "/documents/{document_id}/transcription-runs/{run_id}/pages/{page_id}/variant-layers",
    response_model=TranscriptVariantLayerListResponse,
)
def list_project_document_transcription_variant_layers(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    variant_kind: TranscriptVariantKindLiteral = Query(
        default="NORMALISED",
        alias="variantKind",
    ),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptVariantLayerListResponse:
    try:
        snapshot = document_service.list_transcription_variant_layers(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            variant_kind=variant_kind,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPT_VARIANT_LAYER_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "variant_kind": snapshot.variant_kind,
            "returned_count": len(snapshot.layers),
        },
        request_context=request_context,
    )
    return TranscriptVariantLayerListResponse(
        run_id=snapshot.run.id,
        page_id=snapshot.page.id,
        variant_kind=snapshot.variant_kind,
        items=[
            _as_transcript_variant_layer_response(
                item.layer,
                suggestions=list(item.suggestions),
            )
            for item in snapshot.layers
        ],
    )


@router.post(
    "/documents/{document_id}/transcription-runs/{run_id}/pages/{page_id}/variant-layers/NORMALISED/suggestions/{suggestion_id}/decision",
    response_model=RecordTranscriptVariantSuggestionDecisionResponse,
)
def record_project_document_transcription_variant_suggestion_decision(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    suggestion_id: str,
    payload: RecordTranscriptVariantSuggestionDecisionRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RecordTranscriptVariantSuggestionDecisionResponse:
    try:
        snapshot = document_service.record_transcription_variant_suggestion_decision(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            variant_kind="NORMALISED",
            suggestion_id=suggestion_id,
            decision=payload.decision,
            reason=payload.reason,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPT_ASSIST_DECISION_RECORDED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="transcript_variant_suggestion",
        object_id=snapshot.suggestion.id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "suggestion_id": snapshot.suggestion.id,
            "variant_layer_id": snapshot.suggestion.variant_layer_id,
            "decision": snapshot.event.decision,
            "from_status": snapshot.event.from_status,
            "to_status": snapshot.event.to_status,
        },
        request_context=request_context,
    )
    return RecordTranscriptVariantSuggestionDecisionResponse(
        run_id=snapshot.run.id,
        page_id=snapshot.page.id,
        variant_kind=snapshot.variant_kind,
        suggestion=_as_transcript_variant_suggestion_response(snapshot.suggestion),
        event=_as_transcript_variant_suggestion_event_response(snapshot.event),
    )


@router.get(
    "/documents/{document_id}/transcription-runs/{run_id}/pages/{page_id}/tokens",
    response_model=TranscriptionTokenResultListResponse,
)
def list_project_document_transcription_run_page_tokens(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionTokenResultListResponse:
    try:
        items = document_service.list_transcription_run_page_tokens(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="TRANSCRIPTION_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "document_id": document_id,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return TranscriptionTokenResultListResponse(
        run_id=run_id,
        page_id=page_id,
        items=[_as_transcription_token_result_response(item) for item in items],
    )


@router.post(
    "/documents/{document_id}/retry-extraction",
    response_model=DocumentProcessingRunDetailResponse,
)
def retry_project_document_extraction(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentProcessingRunDetailResponse:
    try:
        run = document_service.retry_document_extraction(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="DOCUMENT_PAGE_EXTRACTION_RETRY_REQUESTED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document_processing_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "run_id": run.id,
            "supersedes_processing_run_id": run.supersedes_processing_run_id,
            "attempt_number": run.attempt_number,
        },
        request_context=request_context,
    )
    return _as_processing_run_detail_response(run)


@router.get("/documents/{document_id}/pages", response_model=DocumentPageListResponse)
def list_project_document_pages(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentPageListResponse:
    try:
        pages = document_service.list_document_pages(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    return DocumentPageListResponse(items=[_as_page_response(page) for page in pages])


@router.get(
    "/documents/{document_id}/pages/{page_id}",
    response_model=DocumentPageDetailResponse,
)
def get_project_document_page(
    project_id: str,
    document_id: str,
    page_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentPageDetailResponse:
    try:
        page = document_service.get_document_page(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    audit_service.record_event_best_effort(
        event_type="PAGE_METADATA_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page.id,
        metadata={"document_id": document_id, "page_id": page.id},
        request_context=request_context,
    )
    return _as_page_detail_response(page)


@router.get(
    "/documents/{document_id}/pages/{page_id}/variants",
    response_model=DocumentPageVariantsResponse,
)
def get_project_document_page_variants(
    project_id: str,
    document_id: str,
    page_id: str,
    run_id: str | None = Query(default=None, alias="runId"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentPageVariantsResponse:
    active_projection_run_id: str | None = None
    basis_references: PreprocessDownstreamBasisReferencesRecord | None = None
    try:
        snapshot = document_service.get_document_page_variants(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
            run_id=run_id,
        )
        if snapshot.resolved_run is not None:
            _, active_projection_run_id, basis_references = _resolve_preprocess_context(
                current_user=current_user,
                project_id=project_id,
                document_id=document_id,
                document_service=document_service,
            )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    return DocumentPageVariantsResponse(
        document_id=snapshot.document.id,
        page_id=snapshot.page.id,
        requested_run_id=snapshot.requested_run_id,
        resolved_run_id=snapshot.resolved_run.id if snapshot.resolved_run else None,
        run=(
            _as_preprocess_run_response(
                snapshot.resolved_run,
                active_run_id=active_projection_run_id,
                basis_references=basis_references,
            )
            if snapshot.resolved_run is not None
            else None
        ),
        variants=[
            _as_page_variant_availability_response(variant)
            for variant in snapshot.variants
        ],
    )


@router.patch(
    "/documents/{document_id}/pages/{page_id}",
    response_model=DocumentPageDetailResponse,
)
def patch_project_document_page(
    project_id: str,
    document_id: str,
    page_id: str,
    payload: DocumentPagePatchRequest = Body(...),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentPageDetailResponse:
    try:
        page = document_service.update_document_page_rotation(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
            viewer_rotation=payload.viewer_rotation,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )
    return _as_page_detail_response(page)


@router.get("/documents/{document_id}/pages/{page_id}/image")
def get_project_document_page_image(
    request: Request,
    project_id: str,
    document_id: str,
    page_id: str,
    variant: DocumentPageImageVariantLiteral = Query(default="full"),
    run_id: str | None = Query(default=None, alias="runId"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        image_asset = document_service.read_document_page_image(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            page_id=page_id,
            variant=variant,
            run_id=run_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
        )

    if variant in {"preprocessed_gray", "preprocessed_bin"}:
        event_type = "PREPROCESS_VARIANT_ACCESSED"
    else:
        event_type = "PAGE_IMAGE_VIEWED" if variant == "full" else "PAGE_THUMBNAIL_VIEWED"
    audit_service.record_event_best_effort(
        event_type=event_type,
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "document_id": document_id,
            "page_id": page_id,
            "variant": variant,
            "run_id": run_id,
        },
        request_context=request_context,
    )
    etag = _format_etag(image_asset.etag_seed)
    response_headers = {
        "Cache-Control": image_asset.cache_control,
        "Cross-Origin-Resource-Policy": "same-origin",
        "Vary": PAGE_IMAGE_CACHE_VARY_HEADER,
        "X-Content-Type-Options": "nosniff",
    }
    if etag:
        response_headers["ETag"] = etag

    if _if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers=response_headers,
        )
    return Response(
        content=image_asset.payload,
        media_type=image_asset.media_type,
        headers=response_headers,
    )
