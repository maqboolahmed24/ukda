from __future__ import annotations

from datetime import date, datetime, time, timezone
from time import sleep
from typing import Literal, Mapping

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
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.documents.models import (
    DocumentRedactionProjectionRecord,
    DocumentTranscriptionProjectionRecord,
    RedactionAreaMaskRecord,
    RedactionFindingRecord,
    RedactionOutputRecord,
    RedactionPageReviewRecord,
    RedactionRunRecord,
    RedactionRunReviewRecord,
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
from app.documents.governance import (
    GovernanceRunSummaryRecord,
    LedgerVerificationRunRecord,
    RedactionEvidenceLedgerRecord,
    RedactionManifestRecord,
)
from app.documents.redaction_geometry import build_finding_geometry_payload
from app.documents.service import (
    DocumentGovernanceAccessDeniedError,
    DocumentGovernanceConflictError,
    DocumentGovernanceEventSnapshot,
    DocumentGovernanceLedgerEntriesSnapshot,
    DocumentGovernanceLedgerSnapshot,
    DocumentGovernanceLedgerStatusSnapshot,
    DocumentGovernanceLedgerSummarySnapshot,
    DocumentGovernanceLedgerVerificationDetailSnapshot,
    DocumentGovernanceLedgerVerificationRunsSnapshot,
    DocumentGovernanceLedgerVerificationStatusSnapshot,
    DocumentGovernanceManifestEntriesSnapshot,
    DocumentGovernanceManifestHashSnapshot,
    DocumentGovernanceManifestSnapshot,
    DocumentGovernanceManifestStatusSnapshot,
    DocumentGovernanceOverviewSnapshot,
    DocumentGovernanceRunNotFoundError,
    DocumentGovernanceRunOverviewSnapshot,
    DocumentGovernanceRunsSnapshot,
    DocumentRedactionAccessDeniedError,
    DocumentRedactionCompareSnapshot,
    DocumentRedactionPolicyWarningSnapshot,
    DocumentRedactionConflictError,
    DocumentRedactionOverviewSnapshot,
    DocumentRedactionPreviewAsset,
    DocumentRedactionPreviewStatusSnapshot,
    DocumentRedactionRunNotFoundError,
    DocumentRedactionRunOutputSnapshot,
    DocumentRedactionRunPageSnapshot,
    DocumentRedactionRunTimelineEventSnapshot,
    DocumentTranscriptionAccessDeniedError,
    DocumentTranscriptionCompareFinalizeSnapshot,
    DocumentTranscriptionCompareSnapshot,
    DocumentTranscriptionConflictError,
    DocumentTranscriptionLineCorrectionSnapshot,
    DocumentTranscriptionLineVersionHistorySnapshot,
    DocumentTranscriptionMetricsSnapshot,
    DocumentTranscriptionOverviewSnapshot,
    DocumentTranscriptionPageRescueSourcesSnapshot,
    DocumentTranscriptionRescuePageStatusSnapshot,
    DocumentTranscriptionRescueSourceSnapshot,
    DocumentTranscriptionRunNotFoundError,
    DocumentTranscriptionRunRescueStatusSnapshot,
    DocumentTranscriptionTriagePageSnapshot,
    DocumentTranscriptionVariantLayersSnapshot,
    DocumentTranscriptionVariantSuggestionDecisionSnapshot,
    DocumentTranscriptVersionLineageSnapshot,
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
RedactionRunKindLiteral = Literal["BASELINE", "POLICY_RERUN"]
RedactionRunStatusLiteral = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
]
RedactionDecisionStatusLiteral = Literal[
    "AUTO_APPLIED",
    "NEEDS_REVIEW",
    "APPROVED",
    "OVERRIDDEN",
    "FALSE_POSITIVE",
]
RedactionDecisionActionTypeLiteral = Literal["MASK", "PSEUDONYMIZE", "GENERALIZE"]
RedactionCompareActionStateLiteral = Literal[
    "AVAILABLE",
    "NOT_YET_RERUN",
    "NOT_YET_AVAILABLE",
]
RedactionComparePageActionStateLiteral = Literal["AVAILABLE", "NOT_YET_AVAILABLE"]
RedactionPolicyStatusLiteral = Literal["DRAFT", "ACTIVE", "RETIRED"]
RedactionPolicyWarningCodeLiteral = Literal[
    "BROAD_ALLOW_RULE",
    "INCONSISTENT_THRESHOLD",
]
RedactionPolicyWarningSeverityLiteral = Literal["WARNING"]
RedactionPageReviewStatusLiteral = Literal[
    "NOT_STARTED",
    "IN_REVIEW",
    "APPROVED",
    "CHANGES_REQUESTED",
]
RedactionSecondReviewStatusLiteral = Literal[
    "NOT_REQUIRED",
    "PENDING",
    "APPROVED",
    "CHANGES_REQUESTED",
]
RedactionRunReviewStatusLiteral = Literal[
    "NOT_READY",
    "IN_REVIEW",
    "APPROVED",
    "CHANGES_REQUESTED",
]
RedactionOutputStatusLiteral = Literal["PENDING", "READY", "FAILED", "CANCELED"]
RedactionRunOutputReadinessStateLiteral = Literal[
    "APPROVAL_REQUIRED",
    "APPROVED_OUTPUT_PENDING",
    "OUTPUT_GENERATING",
    "OUTPUT_FAILED",
    "OUTPUT_CANCELED",
    "OUTPUT_READY",
]
GovernanceArtifactStatusLiteral = Literal[
    "UNAVAILABLE",
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
]
GovernanceReadinessStatusLiteral = Literal["PENDING", "READY", "FAILED"]
GovernanceGenerationStatusLiteral = Literal["IDLE", "RUNNING", "FAILED", "CANCELED"]
GovernanceLedgerVerificationStatusLiteral = Literal["PENDING", "VALID", "INVALID"]
GovernanceLedgerVerificationResultLiteral = Literal["VALID", "INVALID"]
GovernanceLedgerEntriesViewLiteral = Literal["list", "timeline"]
GovernanceRunEventTypeLiteral = Literal[
    "RUN_CREATED",
    "MANIFEST_STARTED",
    "MANIFEST_SUCCEEDED",
    "MANIFEST_FAILED",
    "MANIFEST_CANCELED",
    "LEDGER_STARTED",
    "LEDGER_SUCCEEDED",
    "LEDGER_FAILED",
    "LEDGER_CANCELED",
    "LEDGER_VERIFY_STARTED",
    "LEDGER_VERIFIED_VALID",
    "LEDGER_VERIFIED_INVALID",
    "LEDGER_VERIFY_CANCELED",
    "REGENERATE_REQUESTED",
    "RUN_CANCELED",
    "READY_SET",
    "READY_FAILED",
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
TranscriptionRescueResolutionStatusLiteral = Literal[
    "RESCUE_VERIFIED",
    "MANUAL_REVIEW_RESOLVED",
]
TranscriptionRescueReadinessStateLiteral = Literal[
    "READY",
    "BLOCKED_RESCUE",
    "BLOCKED_MANUAL_REVIEW",
    "BLOCKED_PAGE_STATUS",
]
TranscriptionRescueBlockerReasonCodeLiteral = Literal[
    "PAGE_TRANSCRIPTION_NOT_SUCCEEDED",
    "RESCUE_SOURCE_MISSING",
    "RESCUE_SOURCE_UNTRANSCRIBED",
    "MANUAL_REVIEW_RESOLUTION_REQUIRED",
]
TranscriptionActivationBlockerCodeLiteral = Literal[
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
TranscriptVersionSourceTypeLiteral = Literal[
    "ENGINE_OUTPUT",
    "REVIEWER_CORRECTION",
    "COMPARE_COMPOSED",
]
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


class TranscriptionRescueSourceResponse(BaseModel):
    source_ref_id: str = Field(serialization_alias="sourceRefId")
    source_kind: TranscriptionTokenSourceKindLiteral = Field(serialization_alias="sourceKind")
    candidate_kind: LayoutRescueCandidateKindLiteral = Field(
        serialization_alias="candidateKind"
    )
    candidate_status: LayoutRescueCandidateStatusLiteral = Field(
        serialization_alias="candidateStatus"
    )
    token_count: int = Field(serialization_alias="tokenCount")
    has_transcription_output: bool = Field(
        serialization_alias="hasTranscriptionOutput"
    )
    confidence: float | None = None
    source_signal: str | None = Field(default=None, serialization_alias="sourceSignal")
    geometry_json: dict[str, object] = Field(serialization_alias="geometryJson")


class TranscriptionRescuePageStatusResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    page_recall_status: PageRecallStatusLiteral = Field(
        serialization_alias="pageRecallStatus"
    )
    rescue_source_count: int = Field(serialization_alias="rescueSourceCount")
    rescue_transcribed_source_count: int = Field(
        serialization_alias="rescueTranscribedSourceCount"
    )
    rescue_unresolved_source_count: int = Field(
        serialization_alias="rescueUnresolvedSourceCount"
    )
    readiness_state: TranscriptionRescueReadinessStateLiteral = Field(
        serialization_alias="readinessState"
    )
    blocker_reason_codes: list[TranscriptionRescueBlockerReasonCodeLiteral] = Field(
        serialization_alias="blockerReasonCodes"
    )
    resolution_status: TranscriptionRescueResolutionStatusLiteral | None = Field(
        default=None,
        serialization_alias="resolutionStatus",
    )
    resolution_reason: str | None = Field(
        default=None,
        serialization_alias="resolutionReason",
    )
    resolution_updated_by: str | None = Field(
        default=None,
        serialization_alias="resolutionUpdatedBy",
    )
    resolution_updated_at: datetime | None = Field(
        default=None,
        serialization_alias="resolutionUpdatedAt",
    )


class TranscriptionRunRescueStatusResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    run_id: str = Field(serialization_alias="runId")
    ready_for_activation: bool = Field(serialization_alias="readyForActivation")
    blocker_count: int = Field(serialization_alias="blockerCount")
    run_blocker_reason_codes: list[TranscriptionActivationBlockerCodeLiteral] = Field(
        serialization_alias="runBlockerReasonCodes"
    )
    pages: list[TranscriptionRescuePageStatusResponse]


class TranscriptionPageRescueSourcesResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    page_recall_status: PageRecallStatusLiteral = Field(
        serialization_alias="pageRecallStatus"
    )
    readiness_state: TranscriptionRescueReadinessStateLiteral = Field(
        serialization_alias="readinessState"
    )
    blocker_reason_codes: list[TranscriptionRescueBlockerReasonCodeLiteral] = Field(
        serialization_alias="blockerReasonCodes"
    )
    rescue_sources: list[TranscriptionRescueSourceResponse] = Field(
        serialization_alias="rescueSources"
    )
    resolution_status: TranscriptionRescueResolutionStatusLiteral | None = Field(
        default=None,
        serialization_alias="resolutionStatus",
    )
    resolution_reason: str | None = Field(
        default=None,
        serialization_alias="resolutionReason",
    )
    resolution_updated_by: str | None = Field(
        default=None,
        serialization_alias="resolutionUpdatedBy",
    )
    resolution_updated_at: datetime | None = Field(
        default=None,
        serialization_alias="resolutionUpdatedAt",
    )


class UpdateTranscriptionRescueResolutionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    resolution_status: TranscriptionRescueResolutionStatusLiteral = Field(
        alias="resolutionStatus",
        serialization_alias="resolutionStatus",
    )
    resolution_reason: str | None = Field(
        default=None,
        alias="resolutionReason",
        serialization_alias="resolutionReason",
        max_length=600,
    )


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


class TranscriptVersionLineageResponse(BaseModel):
    version: TranscriptVersionResponse
    is_active: bool = Field(serialization_alias="isActive")
    source_type: TranscriptVersionSourceTypeLiteral = Field(
        serialization_alias="sourceType"
    )


class TranscriptionLineVersionHistoryResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    line_id: str = Field(serialization_alias="lineId")
    line: TranscriptionLineResultResponse
    versions: list[TranscriptVersionLineageResponse]


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
    compare_decision_snapshot_hash: str = Field(
        serialization_alias="compareDecisionSnapshotHash"
    )
    compare_decision_count: int = Field(serialization_alias="compareDecisionCount")
    compare_decision_event_count: int = Field(
        serialization_alias="compareDecisionEventCount"
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


class FinalizeTranscriptionCompareRequest(BaseModel):
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
    page_ids: list[str] = Field(
        default_factory=list,
        alias="pageIds",
        serialization_alias="pageIds",
    )
    expected_compare_decision_snapshot_hash: str | None = Field(
        default=None,
        alias="expectedCompareDecisionSnapshotHash",
        serialization_alias="expectedCompareDecisionSnapshotHash",
        min_length=1,
        max_length=128,
    )


class FinalizeTranscriptionCompareResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    base_run_id: str = Field(serialization_alias="baseRunId")
    candidate_run_id: str = Field(serialization_alias="candidateRunId")
    composed_run: TranscriptionRunResponse = Field(serialization_alias="composedRun")
    compare_decision_snapshot_hash: str = Field(
        serialization_alias="compareDecisionSnapshotHash"
    )
    page_scope: list[str] = Field(serialization_alias="pageScope")


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


class RedactionRunResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    document_id: str = Field(serialization_alias="documentId")
    input_transcription_run_id: str = Field(serialization_alias="inputTranscriptionRunId")
    input_layout_run_id: str | None = Field(
        default=None,
        serialization_alias="inputLayoutRunId",
    )
    run_kind: RedactionRunKindLiteral = Field(serialization_alias="runKind")
    supersedes_redaction_run_id: str | None = Field(
        default=None,
        serialization_alias="supersedesRedactionRunId",
    )
    superseded_by_redaction_run_id: str | None = Field(
        default=None,
        serialization_alias="supersededByRedactionRunId",
    )
    policy_snapshot_id: str = Field(serialization_alias="policySnapshotId")
    policy_snapshot_json: dict[str, object] = Field(serialization_alias="policySnapshotJson")
    policy_snapshot_hash: str = Field(serialization_alias="policySnapshotHash")
    policy_id: str | None = Field(default=None, serialization_alias="policyId")
    policy_family_id: str | None = Field(default=None, serialization_alias="policyFamilyId")
    policy_version: str | None = Field(default=None, serialization_alias="policyVersion")
    detectors_version: str = Field(serialization_alias="detectorsVersion")
    status: RedactionRunStatusLiteral
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    is_active_projection: bool = Field(serialization_alias="isActiveProjection")
    is_superseded: bool = Field(serialization_alias="isSuperseded")
    is_current_attempt: bool = Field(serialization_alias="isCurrentAttempt")
    is_historical_attempt: bool = Field(serialization_alias="isHistoricalAttempt")


class RedactionRunListResponse(BaseModel):
    items: list[RedactionRunResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class RedactionRunStatusResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    document_id: str = Field(serialization_alias="documentId")
    status: RedactionRunStatusLiteral
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    active: bool


class RedactionProjectionResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    active_redaction_run_id: str | None = Field(
        default=None,
        serialization_alias="activeRedactionRunId",
    )
    active_transcription_run_id: str | None = Field(
        default=None,
        serialization_alias="activeTranscriptionRunId",
    )
    active_layout_run_id: str | None = Field(
        default=None,
        serialization_alias="activeLayoutRunId",
    )
    active_policy_snapshot_id: str | None = Field(
        default=None,
        serialization_alias="activePolicySnapshotId",
    )
    updated_at: datetime = Field(serialization_alias="updatedAt")


class RedactionActiveRunResponse(BaseModel):
    projection: RedactionProjectionResponse | None
    run: RedactionRunResponse | None


class CreateRedactionRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    input_transcription_run_id: str | None = Field(
        default=None,
        alias="inputTranscriptionRunId",
        serialization_alias="inputTranscriptionRunId",
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
    run_kind: RedactionRunKindLiteral | None = Field(
        default=None,
        alias="runKind",
        serialization_alias="runKind",
    )
    supersedes_redaction_run_id: str | None = Field(
        default=None,
        alias="supersedesRedactionRunId",
        serialization_alias="supersedesRedactionRunId",
        min_length=1,
        max_length=120,
    )
    detectors_version: str | None = Field(
        default=None,
        alias="detectorsVersion",
        serialization_alias="detectorsVersion",
        min_length=1,
        max_length=160,
    )


class RedactionRunReviewResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    review_status: RedactionRunReviewStatusLiteral = Field(serialization_alias="reviewStatus")
    review_started_by: str | None = Field(default=None, serialization_alias="reviewStartedBy")
    review_started_at: datetime | None = Field(default=None, serialization_alias="reviewStartedAt")
    approved_by: str | None = Field(default=None, serialization_alias="approvedBy")
    approved_at: datetime | None = Field(default=None, serialization_alias="approvedAt")
    approved_snapshot_key: str | None = Field(
        default=None,
        serialization_alias="approvedSnapshotKey",
    )
    approved_snapshot_sha256: str | None = Field(
        default=None,
        serialization_alias="approvedSnapshotSha256",
    )
    locked_at: datetime | None = Field(default=None, serialization_alias="lockedAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class CompleteRedactionRunReviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    review_status: RedactionRunReviewStatusLiteral = Field(
        alias="reviewStatus",
        serialization_alias="reviewStatus",
    )
    reason: str | None = Field(default=None, max_length=600)


class RedactionRunPageResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    finding_count: int = Field(serialization_alias="findingCount")
    unresolved_count: int = Field(serialization_alias="unresolvedCount")
    review_status: RedactionPageReviewStatusLiteral = Field(serialization_alias="reviewStatus")
    review_etag: str = Field(serialization_alias="reviewEtag")
    requires_second_review: bool = Field(serialization_alias="requiresSecondReview")
    second_review_status: RedactionSecondReviewStatusLiteral = Field(
        serialization_alias="secondReviewStatus"
    )
    second_reviewed_by: str | None = Field(default=None, serialization_alias="secondReviewedBy")
    second_reviewed_at: datetime | None = Field(
        default=None,
        serialization_alias="secondReviewedAt",
    )
    last_reviewed_by: str | None = Field(default=None, serialization_alias="lastReviewedBy")
    last_reviewed_at: datetime | None = Field(default=None, serialization_alias="lastReviewedAt")
    preview_status: RedactionOutputStatusLiteral | None = Field(
        default=None,
        serialization_alias="previewStatus",
    )
    top_findings: list["RedactionFindingResponse"] = Field(
        default_factory=list,
        serialization_alias="topFindings",
    )


class RedactionRunPageListResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    items: list[RedactionRunPageResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


RedactionFindingAnchorKindLiteral = Literal[
    "TOKEN_LINKED",
    "AREA_MASK_BACKED",
    "BBOX_ONLY",
    "NONE",
]
RedactionFindingGeometrySourceLiteral = Literal["TOKEN_REF", "BBOX_REF", "AREA_MASK"]


class RedactionFindingGeometryPointResponse(BaseModel):
    x: float
    y: float


class RedactionFindingGeometryBoxResponse(BaseModel):
    x: float
    y: float
    width: float
    height: float
    source: RedactionFindingGeometrySourceLiteral


class RedactionFindingGeometryPolygonResponse(BaseModel):
    points: list[RedactionFindingGeometryPointResponse]
    source: RedactionFindingGeometrySourceLiteral


class RedactionFindingGeometryResponse(BaseModel):
    anchor_kind: RedactionFindingAnchorKindLiteral = Field(serialization_alias="anchorKind")
    line_id: str | None = Field(default=None, serialization_alias="lineId")
    token_ids: list[str] = Field(default_factory=list, serialization_alias="tokenIds")
    boxes: list[RedactionFindingGeometryBoxResponse] = Field(default_factory=list)
    polygons: list[RedactionFindingGeometryPolygonResponse] = Field(default_factory=list)


class RedactionFindingResponse(BaseModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    line_id: str | None = Field(default=None, serialization_alias="lineId")
    category: str
    span_start: int | None = Field(default=None, serialization_alias="spanStart")
    span_end: int | None = Field(default=None, serialization_alias="spanEnd")
    span_basis_kind: str = Field(serialization_alias="spanBasisKind")
    span_basis_ref: str | None = Field(default=None, serialization_alias="spanBasisRef")
    confidence: float | None = None
    basis_primary: str = Field(serialization_alias="basisPrimary")
    basis_secondary_json: dict[str, object] | None = Field(
        default=None,
        serialization_alias="basisSecondaryJson",
    )
    assist_explanation_key: str | None = Field(
        default=None,
        serialization_alias="assistExplanationKey",
    )
    assist_explanation_sha256: str | None = Field(
        default=None,
        serialization_alias="assistExplanationSha256",
    )
    bbox_refs: dict[str, object] = Field(serialization_alias="bboxRefs")
    token_refs_json: list[dict[str, object]] | None = Field(
        default=None,
        serialization_alias="tokenRefsJson",
    )
    area_mask_id: str | None = Field(default=None, serialization_alias="areaMaskId")
    decision_status: RedactionDecisionStatusLiteral = Field(serialization_alias="decisionStatus")
    action_type: RedactionDecisionActionTypeLiteral = Field(
        default="MASK",
        serialization_alias="actionType",
    )
    override_risk_classification: str | None = Field(
        default=None,
        serialization_alias="overrideRiskClassification",
    )
    override_risk_reason_codes_json: list[str] | None = Field(
        default=None,
        serialization_alias="overrideRiskReasonCodesJson",
    )
    decision_by: str | None = Field(default=None, serialization_alias="decisionBy")
    decision_at: datetime | None = Field(default=None, serialization_alias="decisionAt")
    decision_reason: str | None = Field(default=None, serialization_alias="decisionReason")
    decision_etag: str = Field(serialization_alias="decisionEtag")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    geometry: RedactionFindingGeometryResponse
    active_area_mask: "RedactionAreaMaskResponse | None" = Field(
        default=None,
        serialization_alias="activeAreaMask",
    )


class RedactionFindingListResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    items: list[RedactionFindingResponse]


class PatchRedactionFindingRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    decision_status: RedactionDecisionStatusLiteral = Field(
        alias="decisionStatus",
        serialization_alias="decisionStatus",
    )
    decision_etag: str = Field(
        alias="decisionEtag",
        serialization_alias="decisionEtag",
        min_length=1,
        max_length=128,
    )
    reason: str | None = Field(default=None, max_length=600)
    action_type: RedactionDecisionActionTypeLiteral | None = Field(
        default=None,
        alias="actionType",
        serialization_alias="actionType",
    )

    @model_validator(mode="after")
    def validate_override_reason(self) -> "PatchRedactionFindingRequest":
        if self.decision_status in {"OVERRIDDEN", "FALSE_POSITIVE"}:
            reason = self.reason.strip() if isinstance(self.reason, str) else ""
            if not reason:
                raise ValueError(
                    "reason is required when decisionStatus is OVERRIDDEN or FALSE_POSITIVE."
                )
        return self


class RedactionPageReviewResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    review_status: RedactionPageReviewStatusLiteral = Field(serialization_alias="reviewStatus")
    review_etag: str = Field(serialization_alias="reviewEtag")
    first_reviewed_by: str | None = Field(default=None, serialization_alias="firstReviewedBy")
    first_reviewed_at: datetime | None = Field(default=None, serialization_alias="firstReviewedAt")
    requires_second_review: bool = Field(serialization_alias="requiresSecondReview")
    second_review_status: RedactionSecondReviewStatusLiteral = Field(
        serialization_alias="secondReviewStatus"
    )
    second_reviewed_by: str | None = Field(default=None, serialization_alias="secondReviewedBy")
    second_reviewed_at: datetime | None = Field(default=None, serialization_alias="secondReviewedAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class PatchRedactionPageReviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    review_status: RedactionPageReviewStatusLiteral = Field(
        alias="reviewStatus",
        serialization_alias="reviewStatus",
    )
    review_etag: str = Field(
        alias="reviewEtag",
        serialization_alias="reviewEtag",
        min_length=1,
        max_length=128,
    )
    reason: str | None = Field(default=None, max_length=600)


class RedactionAreaMaskResponse(BaseModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    geometry_json: dict[str, object] = Field(serialization_alias="geometryJson")
    mask_reason: str = Field(serialization_alias="maskReason")
    version_etag: str = Field(serialization_alias="versionEtag")
    supersedes_area_mask_id: str | None = Field(
        default=None,
        serialization_alias="supersedesAreaMaskId",
    )
    superseded_by_area_mask_id: str | None = Field(
        default=None,
        serialization_alias="supersededByAreaMaskId",
    )
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class PatchRedactionAreaMaskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    version_etag: str = Field(
        alias="versionEtag",
        serialization_alias="versionEtag",
        min_length=1,
        max_length=128,
    )
    geometry_json: dict[str, object] = Field(
        alias="geometryJson",
        serialization_alias="geometryJson",
    )
    mask_reason: str = Field(
        alias="maskReason",
        serialization_alias="maskReason",
        min_length=1,
        max_length=600,
    )
    finding_id: str | None = Field(
        default=None,
        alias="findingId",
        serialization_alias="findingId",
        min_length=1,
        max_length=160,
    )
    finding_decision_etag: str | None = Field(
        default=None,
        alias="findingDecisionEtag",
        serialization_alias="findingDecisionEtag",
        min_length=1,
        max_length=128,
    )


class CreateRedactionAreaMaskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    geometry_json: dict[str, object] = Field(
        alias="geometryJson",
        serialization_alias="geometryJson",
    )
    mask_reason: str = Field(
        alias="maskReason",
        serialization_alias="maskReason",
        min_length=1,
        max_length=600,
    )
    finding_id: str | None = Field(
        default=None,
        alias="findingId",
        serialization_alias="findingId",
        min_length=1,
        max_length=160,
    )
    finding_decision_etag: str | None = Field(
        default=None,
        alias="findingDecisionEtag",
        serialization_alias="findingDecisionEtag",
        min_length=1,
        max_length=128,
    )


class PatchRedactionAreaMaskResponse(BaseModel):
    area_mask: RedactionAreaMaskResponse = Field(serialization_alias="areaMask")
    finding: RedactionFindingResponse | None = None


class RedactionTimelineEventResponse(BaseModel):
    source_table: str = Field(serialization_alias="sourceTable")
    source_table_precedence: int = Field(serialization_alias="sourceTablePrecedence")
    event_id: str = Field(serialization_alias="eventId")
    run_id: str = Field(serialization_alias="runId")
    page_id: str | None = Field(default=None, serialization_alias="pageId")
    finding_id: str | None = Field(default=None, serialization_alias="findingId")
    event_type: str = Field(serialization_alias="eventType")
    actor_user_id: str | None = Field(default=None, serialization_alias="actorUserId")
    reason: str | None = None
    created_at: datetime = Field(serialization_alias="createdAt")
    details_json: dict[str, object] = Field(serialization_alias="detailsJson")


class RedactionRunEventsResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    items: list[RedactionTimelineEventResponse]


class RedactionPreviewStatusResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    status: RedactionOutputStatusLiteral
    preview_sha256: str | None = Field(default=None, serialization_alias="previewSha256")
    generated_at: datetime | None = Field(default=None, serialization_alias="generatedAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    run_output_status: RedactionOutputStatusLiteral | None = Field(
        default=None,
        serialization_alias="runOutputStatus",
    )
    run_output_manifest_sha256: str | None = Field(
        default=None,
        serialization_alias="runOutputManifestSha256",
    )
    run_output_readiness_state: RedactionRunOutputReadinessStateLiteral | None = Field(
        default=None,
        serialization_alias="runOutputReadinessState",
    )
    downstream_ready: bool = Field(serialization_alias="downstreamReady")


class RedactionRunOutputResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    status: RedactionOutputStatusLiteral
    review_status: RedactionRunReviewStatusLiteral = Field(serialization_alias="reviewStatus")
    readiness_state: RedactionRunOutputReadinessStateLiteral = Field(
        serialization_alias="readinessState"
    )
    downstream_ready: bool = Field(serialization_alias="downstreamReady")
    output_manifest_sha256: str | None = Field(
        default=None,
        serialization_alias="outputManifestSha256",
    )
    page_count: int = Field(serialization_alias="pageCount")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    generated_at: datetime | None = Field(default=None, serialization_alias="generatedAt")
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class RedactionOverviewResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    projection: RedactionProjectionResponse | None
    active_run: RedactionRunResponse | None = Field(default=None, serialization_alias="activeRun")
    latest_run: RedactionRunResponse | None = Field(default=None, serialization_alias="latestRun")
    total_runs: int = Field(serialization_alias="totalRuns")
    page_count: int = Field(serialization_alias="pageCount")
    findings_by_category: dict[str, int] = Field(serialization_alias="findingsByCategory")
    unresolved_findings: int = Field(serialization_alias="unresolvedFindings")
    auto_applied_findings: int = Field(serialization_alias="autoAppliedFindings")
    needs_review_findings: int = Field(serialization_alias="needsReviewFindings")
    overridden_findings: int = Field(serialization_alias="overriddenFindings")
    pages_blocked_for_review: int = Field(serialization_alias="pagesBlockedForReview")
    preview_ready_pages: int = Field(serialization_alias="previewReadyPages")
    preview_total_pages: int = Field(serialization_alias="previewTotalPages")
    preview_failed_pages: int = Field(serialization_alias="previewFailedPages")


class RedactionComparePageResponse(BaseModel):
    page_id: str = Field(serialization_alias="pageId")
    page_index: int = Field(serialization_alias="pageIndex")
    base_finding_count: int = Field(serialization_alias="baseFindingCount")
    candidate_finding_count: int = Field(serialization_alias="candidateFindingCount")
    changed_decision_count: int = Field(serialization_alias="changedDecisionCount")
    changed_action_count: int = Field(serialization_alias="changedActionCount")
    base_decision_counts: dict[RedactionDecisionStatusLiteral, int] = Field(
        serialization_alias="baseDecisionCounts"
    )
    candidate_decision_counts: dict[RedactionDecisionStatusLiteral, int] = Field(
        serialization_alias="candidateDecisionCounts"
    )
    decision_status_deltas: dict[RedactionDecisionStatusLiteral, int] = Field(
        serialization_alias="decisionStatusDeltas"
    )
    base_action_counts: dict[RedactionDecisionActionTypeLiteral, int] = Field(
        serialization_alias="baseActionCounts"
    )
    candidate_action_counts: dict[RedactionDecisionActionTypeLiteral, int] = Field(
        serialization_alias="candidateActionCounts"
    )
    action_type_deltas: dict[RedactionDecisionActionTypeLiteral, int] = Field(
        serialization_alias="actionTypeDeltas"
    )
    action_compare_state: RedactionComparePageActionStateLiteral = Field(
        serialization_alias="actionCompareState"
    )
    changed_review_status: bool = Field(serialization_alias="changedReviewStatus")
    changed_second_review_status: bool = Field(
        serialization_alias="changedSecondReviewStatus"
    )
    base_review: RedactionPageReviewResponse | None = Field(
        default=None,
        serialization_alias="baseReview",
    )
    candidate_review: RedactionPageReviewResponse | None = Field(
        default=None,
        serialization_alias="candidateReview",
    )
    base_preview_status: RedactionOutputStatusLiteral | None = Field(
        default=None,
        serialization_alias="basePreviewStatus",
    )
    candidate_preview_status: RedactionOutputStatusLiteral | None = Field(
        default=None,
        serialization_alias="candidatePreviewStatus",
    )
    preview_ready_delta: int = Field(serialization_alias="previewReadyDelta")


class RedactionPreActivationWarningResponse(BaseModel):
    code: RedactionPolicyWarningCodeLiteral
    severity: RedactionPolicyWarningSeverityLiteral
    message: str
    affected_categories: list[str] = Field(serialization_alias="affectedCategories")


class RedactionCompareResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    base_run: RedactionRunResponse = Field(serialization_alias="baseRun")
    candidate_run: RedactionRunResponse = Field(serialization_alias="candidateRun")
    changed_page_count: int = Field(serialization_alias="changedPageCount")
    changed_decision_count: int = Field(serialization_alias="changedDecisionCount")
    changed_action_count: int = Field(serialization_alias="changedActionCount")
    compare_action_state: RedactionCompareActionStateLiteral = Field(
        serialization_alias="compareActionState"
    )
    candidate_policy_status: RedactionPolicyStatusLiteral | None = Field(
        default=None,
        serialization_alias="candidatePolicyStatus",
    )
    comparison_only_candidate: bool = Field(serialization_alias="comparisonOnlyCandidate")
    pre_activation_warnings: list[RedactionPreActivationWarningResponse] = Field(
        serialization_alias="preActivationWarnings"
    )
    items: list[RedactionComparePageResponse]


class ActivateRedactionRunResponse(BaseModel):
    projection: RedactionProjectionResponse
    run: RedactionRunResponse


class GovernanceRunSummaryResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    project_id: str = Field(serialization_alias="projectId")
    document_id: str = Field(serialization_alias="documentId")
    run_status: RedactionRunStatusLiteral = Field(serialization_alias="runStatus")
    review_status: RedactionRunReviewStatusLiteral | None = Field(
        default=None,
        serialization_alias="reviewStatus",
    )
    approved_snapshot_key: str | None = Field(
        default=None,
        serialization_alias="approvedSnapshotKey",
    )
    approved_snapshot_sha256: str | None = Field(
        default=None,
        serialization_alias="approvedSnapshotSha256",
    )
    run_output_status: RedactionOutputStatusLiteral | None = Field(
        default=None,
        serialization_alias="runOutputStatus",
    )
    run_output_manifest_sha256: str | None = Field(
        default=None,
        serialization_alias="runOutputManifestSha256",
    )
    run_created_at: datetime = Field(serialization_alias="runCreatedAt")
    run_finished_at: datetime | None = Field(default=None, serialization_alias="runFinishedAt")
    readiness_status: GovernanceReadinessStatusLiteral = Field(
        serialization_alias="readinessStatus"
    )
    generation_status: GovernanceGenerationStatusLiteral = Field(
        serialization_alias="generationStatus"
    )
    ready_manifest_id: str | None = Field(default=None, serialization_alias="readyManifestId")
    ready_ledger_id: str | None = Field(default=None, serialization_alias="readyLedgerId")
    latest_manifest_sha256: str | None = Field(
        default=None,
        serialization_alias="latestManifestSha256",
    )
    latest_ledger_sha256: str | None = Field(
        default=None,
        serialization_alias="latestLedgerSha256",
    )
    ledger_verification_status: GovernanceLedgerVerificationStatusLiteral = Field(
        serialization_alias="ledgerVerificationStatus"
    )
    ready_at: datetime | None = Field(default=None, serialization_alias="readyAt")
    last_error_code: str | None = Field(default=None, serialization_alias="lastErrorCode")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class GovernanceReadinessProjectionResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    project_id: str = Field(serialization_alias="projectId")
    document_id: str = Field(serialization_alias="documentId")
    status: GovernanceReadinessStatusLiteral
    generation_status: GovernanceGenerationStatusLiteral = Field(
        serialization_alias="generationStatus"
    )
    manifest_id: str | None = Field(default=None, serialization_alias="manifestId")
    ledger_id: str | None = Field(default=None, serialization_alias="ledgerId")
    last_ledger_verification_run_id: str | None = Field(
        default=None,
        serialization_alias="lastLedgerVerificationRunId",
    )
    last_manifest_sha256: str | None = Field(
        default=None,
        serialization_alias="lastManifestSha256",
    )
    last_ledger_sha256: str | None = Field(
        default=None,
        serialization_alias="lastLedgerSha256",
    )
    ledger_verification_status: GovernanceLedgerVerificationStatusLiteral = Field(
        serialization_alias="ledgerVerificationStatus"
    )
    ledger_verified_at: datetime | None = Field(
        default=None,
        serialization_alias="ledgerVerifiedAt",
    )
    ready_at: datetime | None = Field(default=None, serialization_alias="readyAt")
    last_error_code: str | None = Field(default=None, serialization_alias="lastErrorCode")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class GovernanceManifestAttemptResponse(BaseModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    project_id: str = Field(serialization_alias="projectId")
    document_id: str = Field(serialization_alias="documentId")
    source_review_snapshot_key: str = Field(serialization_alias="sourceReviewSnapshotKey")
    source_review_snapshot_sha256: str = Field(serialization_alias="sourceReviewSnapshotSha256")
    attempt_number: int = Field(serialization_alias="attemptNumber")
    supersedes_manifest_id: str | None = Field(
        default=None,
        serialization_alias="supersedesManifestId",
    )
    superseded_by_manifest_id: str | None = Field(
        default=None,
        serialization_alias="supersededByManifestId",
    )
    status: GovernanceArtifactStatusLiteral
    manifest_key: str | None = Field(default=None, serialization_alias="manifestKey")
    manifest_sha256: str | None = Field(default=None, serialization_alias="manifestSha256")
    format_version: int = Field(serialization_alias="formatVersion")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")


class GovernanceLedgerAttemptResponse(BaseModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    project_id: str = Field(serialization_alias="projectId")
    document_id: str = Field(serialization_alias="documentId")
    source_review_snapshot_key: str = Field(serialization_alias="sourceReviewSnapshotKey")
    source_review_snapshot_sha256: str = Field(serialization_alias="sourceReviewSnapshotSha256")
    attempt_number: int = Field(serialization_alias="attemptNumber")
    supersedes_ledger_id: str | None = Field(
        default=None,
        serialization_alias="supersedesLedgerId",
    )
    superseded_by_ledger_id: str | None = Field(
        default=None,
        serialization_alias="supersededByLedgerId",
    )
    status: GovernanceArtifactStatusLiteral
    ledger_key: str | None = Field(default=None, serialization_alias="ledgerKey")
    ledger_sha256: str | None = Field(default=None, serialization_alias="ledgerSha256")
    hash_chain_version: str = Field(serialization_alias="hashChainVersion")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")


class GovernanceRunOverviewResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    active_run_id: str | None = Field(default=None, serialization_alias="activeRunId")
    run: GovernanceRunSummaryResponse
    readiness: GovernanceReadinessProjectionResponse
    manifest_attempts: list[GovernanceManifestAttemptResponse] = Field(
        serialization_alias="manifestAttempts"
    )
    ledger_attempts: list[GovernanceLedgerAttemptResponse] = Field(
        serialization_alias="ledgerAttempts"
    )


class GovernanceOverviewResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    active_run_id: str | None = Field(default=None, serialization_alias="activeRunId")
    total_runs: int = Field(serialization_alias="totalRuns")
    approved_runs: int = Field(serialization_alias="approvedRuns")
    ready_runs: int = Field(serialization_alias="readyRuns")
    pending_runs: int = Field(serialization_alias="pendingRuns")
    failed_runs: int = Field(serialization_alias="failedRuns")
    latest_run_id: str | None = Field(default=None, serialization_alias="latestRunId")
    latest_ready_run_id: str | None = Field(
        default=None,
        serialization_alias="latestReadyRunId",
    )
    latest_run: GovernanceRunSummaryResponse | None = Field(
        default=None,
        serialization_alias="latestRun",
    )
    latest_ready_run: GovernanceRunSummaryResponse | None = Field(
        default=None,
        serialization_alias="latestReadyRun",
    )


class GovernanceRunsResponse(BaseModel):
    document_id: str = Field(serialization_alias="documentId")
    project_id: str = Field(serialization_alias="projectId")
    active_run_id: str | None = Field(default=None, serialization_alias="activeRunId")
    items: list[GovernanceRunSummaryResponse]


class GovernanceRunEventResponse(BaseModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    event_type: GovernanceRunEventTypeLiteral = Field(serialization_alias="eventType")
    actor_user_id: str | None = Field(default=None, serialization_alias="actorUserId")
    from_status: str | None = Field(default=None, serialization_alias="fromStatus")
    to_status: str | None = Field(default=None, serialization_alias="toStatus")
    reason: str | None = None
    created_at: datetime = Field(serialization_alias="createdAt")
    screening_safe: bool = Field(serialization_alias="screeningSafe")


class GovernanceRunEventsResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    items: list[GovernanceRunEventResponse]


class GovernanceManifestResponse(BaseModel):
    overview: GovernanceRunOverviewResponse
    latest_attempt: GovernanceManifestAttemptResponse | None = Field(
        default=None,
        serialization_alias="latestAttempt",
    )
    manifest_json: dict[str, object] | None = Field(
        default=None,
        serialization_alias="manifestJson",
    )
    stream_sha256: str | None = Field(default=None, serialization_alias="streamSha256")
    hash_matches: bool = Field(serialization_alias="hashMatches")
    internal_only: bool = Field(serialization_alias="internalOnly")
    export_approved: bool = Field(serialization_alias="exportApproved")
    not_export_approved: bool = Field(serialization_alias="notExportApproved")


class GovernanceManifestStatusResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    status: GovernanceArtifactStatusLiteral
    latest_attempt: GovernanceManifestAttemptResponse | None = Field(
        default=None,
        serialization_alias="latestAttempt",
    )
    attempt_count: int = Field(serialization_alias="attemptCount")
    ready_manifest_id: str | None = Field(default=None, serialization_alias="readyManifestId")
    latest_manifest_sha256: str | None = Field(
        default=None,
        serialization_alias="latestManifestSha256",
    )
    generation_status: GovernanceGenerationStatusLiteral = Field(
        serialization_alias="generationStatus"
    )
    readiness_status: GovernanceReadinessStatusLiteral = Field(
        serialization_alias="readinessStatus"
    )
    updated_at: datetime = Field(serialization_alias="updatedAt")


class GovernanceManifestEntryResponse(BaseModel):
    entry_id: str = Field(serialization_alias="entryId")
    applied_action: str = Field(serialization_alias="appliedAction")
    category: str
    page_id: str = Field(serialization_alias="pageId")
    page_index: int | None = Field(default=None, serialization_alias="pageIndex")
    line_id: str | None = Field(default=None, serialization_alias="lineId")
    location_ref: dict[str, object] = Field(serialization_alias="locationRef")
    basis_primary: str = Field(serialization_alias="basisPrimary")
    confidence: float | None = None
    secondary_basis_summary: dict[str, object] | None = Field(
        default=None,
        serialization_alias="secondaryBasisSummary",
    )
    final_decision_state: str = Field(serialization_alias="finalDecisionState")
    review_state: str = Field(serialization_alias="reviewState")
    policy_snapshot_hash: str | None = Field(
        default=None,
        serialization_alias="policySnapshotHash",
    )
    policy_id: str | None = Field(default=None, serialization_alias="policyId")
    policy_family_id: str | None = Field(default=None, serialization_alias="policyFamilyId")
    policy_version: str | None = Field(default=None, serialization_alias="policyVersion")
    decision_timestamp: str | None = Field(default=None, serialization_alias="decisionTimestamp")
    decision_by: str | None = Field(default=None, serialization_alias="decisionBy")
    decision_etag: str | None = Field(default=None, serialization_alias="decisionEtag")


class GovernanceManifestEntriesResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    status: GovernanceArtifactStatusLiteral
    manifest_id: str | None = Field(default=None, serialization_alias="manifestId")
    manifest_sha256: str | None = Field(default=None, serialization_alias="manifestSha256")
    source_review_snapshot_sha256: str | None = Field(
        default=None,
        serialization_alias="sourceReviewSnapshotSha256",
    )
    total_count: int = Field(serialization_alias="totalCount")
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")
    internal_only: bool = Field(serialization_alias="internalOnly")
    export_approved: bool = Field(serialization_alias="exportApproved")
    not_export_approved: bool = Field(serialization_alias="notExportApproved")
    items: list[GovernanceManifestEntryResponse]


class GovernanceManifestHashResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    status: GovernanceArtifactStatusLiteral
    manifest_id: str | None = Field(default=None, serialization_alias="manifestId")
    manifest_sha256: str | None = Field(default=None, serialization_alias="manifestSha256")
    stream_sha256: str | None = Field(default=None, serialization_alias="streamSha256")
    hash_matches: bool = Field(serialization_alias="hashMatches")
    internal_only: bool = Field(serialization_alias="internalOnly")
    export_approved: bool = Field(serialization_alias="exportApproved")
    not_export_approved: bool = Field(serialization_alias="notExportApproved")


class GovernanceLedgerResponse(BaseModel):
    overview: GovernanceRunOverviewResponse
    latest_attempt: GovernanceLedgerAttemptResponse | None = Field(
        default=None,
        serialization_alias="latestAttempt",
    )
    ledger_json: dict[str, object] | None = Field(
        default=None,
        serialization_alias="ledgerJson",
    )
    stream_sha256: str | None = Field(default=None, serialization_alias="streamSha256")
    hash_matches: bool = Field(serialization_alias="hashMatches")
    internal_only: bool = Field(serialization_alias="internalOnly")


class GovernanceLedgerStatusResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    status: GovernanceArtifactStatusLiteral
    latest_attempt: GovernanceLedgerAttemptResponse | None = Field(
        default=None,
        serialization_alias="latestAttempt",
    )
    attempt_count: int = Field(serialization_alias="attemptCount")
    ready_ledger_id: str | None = Field(default=None, serialization_alias="readyLedgerId")
    latest_ledger_sha256: str | None = Field(
        default=None,
        serialization_alias="latestLedgerSha256",
    )
    generation_status: GovernanceGenerationStatusLiteral = Field(
        serialization_alias="generationStatus"
    )
    readiness_status: GovernanceReadinessStatusLiteral = Field(
        serialization_alias="readinessStatus"
    )
    ledger_verification_status: GovernanceLedgerVerificationStatusLiteral = Field(
        serialization_alias="ledgerVerificationStatus"
    )
    updated_at: datetime = Field(serialization_alias="updatedAt")


class GovernanceLedgerEntryResponse(BaseModel):
    row_id: str = Field(serialization_alias="rowId")
    row_index: int = Field(serialization_alias="rowIndex")
    finding_id: str = Field(serialization_alias="findingId")
    page_id: str = Field(serialization_alias="pageId")
    page_index: int | None = Field(default=None, serialization_alias="pageIndex")
    line_id: str | None = Field(default=None, serialization_alias="lineId")
    category: str
    action_type: str = Field(serialization_alias="actionType")
    before_text_ref: dict[str, object] = Field(serialization_alias="beforeTextRef")
    after_text_ref: dict[str, object] = Field(serialization_alias="afterTextRef")
    detector_evidence: dict[str, object] = Field(serialization_alias="detectorEvidence")
    assist_explanation_key: str | None = Field(
        default=None,
        serialization_alias="assistExplanationKey",
    )
    assist_explanation_sha256: str | None = Field(
        default=None,
        serialization_alias="assistExplanationSha256",
    )
    actor_user_id: str | None = Field(default=None, serialization_alias="actorUserId")
    decision_timestamp: str | None = Field(
        default=None,
        serialization_alias="decisionTimestamp",
    )
    override_reason: str | None = Field(default=None, serialization_alias="overrideReason")
    final_decision_state: str | None = Field(
        default=None,
        serialization_alias="finalDecisionState",
    )
    policy_snapshot_hash: str | None = Field(
        default=None,
        serialization_alias="policySnapshotHash",
    )
    policy_id: str | None = Field(default=None, serialization_alias="policyId")
    policy_family_id: str | None = Field(default=None, serialization_alias="policyFamilyId")
    policy_version: str | None = Field(default=None, serialization_alias="policyVersion")
    prev_hash: str = Field(serialization_alias="prevHash")
    row_hash: str = Field(serialization_alias="rowHash")


class GovernanceLedgerEntriesResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    status: GovernanceArtifactStatusLiteral
    view: GovernanceLedgerEntriesViewLiteral
    ledger_id: str | None = Field(default=None, serialization_alias="ledgerId")
    ledger_sha256: str | None = Field(default=None, serialization_alias="ledgerSha256")
    hash_chain_version: str | None = Field(
        default=None,
        serialization_alias="hashChainVersion",
    )
    total_count: int = Field(serialization_alias="totalCount")
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")
    verification_status: GovernanceLedgerVerificationStatusLiteral = Field(
        serialization_alias="verificationStatus"
    )
    items: list[GovernanceLedgerEntryResponse]


class GovernanceLedgerSummaryResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    status: GovernanceArtifactStatusLiteral
    ledger_id: str | None = Field(default=None, serialization_alias="ledgerId")
    ledger_sha256: str | None = Field(default=None, serialization_alias="ledgerSha256")
    hash_chain_version: str | None = Field(
        default=None,
        serialization_alias="hashChainVersion",
    )
    row_count: int = Field(serialization_alias="rowCount")
    hash_chain_head: str | None = Field(default=None, serialization_alias="hashChainHead")
    hash_chain_valid: bool = Field(serialization_alias="hashChainValid")
    verification_status: GovernanceLedgerVerificationStatusLiteral = Field(
        serialization_alias="verificationStatus"
    )
    category_counts: dict[str, int] = Field(serialization_alias="categoryCounts")
    action_counts: dict[str, int] = Field(serialization_alias="actionCounts")
    override_count: int = Field(serialization_alias="overrideCount")
    assist_reference_count: int = Field(serialization_alias="assistReferenceCount")
    internal_only: bool = Field(serialization_alias="internalOnly")


class GovernanceLedgerVerificationRunResponse(BaseModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    attempt_number: int = Field(serialization_alias="attemptNumber")
    supersedes_verification_run_id: str | None = Field(
        default=None,
        serialization_alias="supersedesVerificationRunId",
    )
    superseded_by_verification_run_id: str | None = Field(
        default=None,
        serialization_alias="supersededByVerificationRunId",
    )
    status: GovernanceArtifactStatusLiteral
    verification_result: GovernanceLedgerVerificationResultLiteral | None = Field(
        default=None,
        serialization_alias="verificationResult",
    )
    result_json: dict[str, object] | None = Field(
        default=None,
        serialization_alias="resultJson",
    )
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")


class GovernanceLedgerVerifyStatusResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    verification_status: GovernanceLedgerVerificationStatusLiteral = Field(
        serialization_alias="verificationStatus"
    )
    attempt_count: int = Field(serialization_alias="attemptCount")
    latest_attempt: GovernanceLedgerVerificationRunResponse | None = Field(
        default=None,
        serialization_alias="latestAttempt",
    )
    latest_completed_attempt: GovernanceLedgerVerificationRunResponse | None = Field(
        default=None,
        serialization_alias="latestCompletedAttempt",
    )
    ready_ledger_id: str | None = Field(default=None, serialization_alias="readyLedgerId")
    latest_ledger_sha256: str | None = Field(
        default=None,
        serialization_alias="latestLedgerSha256",
    )
    last_verified_at: datetime | None = Field(default=None, serialization_alias="lastVerifiedAt")


class GovernanceLedgerVerifyRunsResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    verification_status: GovernanceLedgerVerificationStatusLiteral = Field(
        serialization_alias="verificationStatus"
    )
    items: list[GovernanceLedgerVerificationRunResponse]


class GovernanceLedgerVerifyDetailResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    verification_status: GovernanceLedgerVerificationStatusLiteral = Field(
        serialization_alias="verificationStatus"
    )
    attempt: GovernanceLedgerVerificationRunResponse


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


def _as_transcription_rescue_source_response(
    snapshot: DocumentTranscriptionRescueSourceSnapshot,
) -> TranscriptionRescueSourceResponse:
    return TranscriptionRescueSourceResponse(
        source_ref_id=snapshot.source_ref_id,
        source_kind=snapshot.source_kind,
        candidate_kind=snapshot.candidate_kind,  # type: ignore[arg-type]
        candidate_status=snapshot.candidate_status,  # type: ignore[arg-type]
        token_count=snapshot.token_count,
        has_transcription_output=snapshot.has_transcription_output,
        confidence=snapshot.confidence,
        source_signal=snapshot.source_signal,
        geometry_json=dict(snapshot.geometry_json),
    )


def _as_transcription_rescue_page_status_response(
    snapshot: DocumentTranscriptionRescuePageStatusSnapshot,
) -> TranscriptionRescuePageStatusResponse:
    return TranscriptionRescuePageStatusResponse(
        run_id=snapshot.run_id,
        page_id=snapshot.page_id,
        page_index=snapshot.page_index,
        page_recall_status=snapshot.page_recall_status,
        rescue_source_count=snapshot.rescue_source_count,
        rescue_transcribed_source_count=snapshot.rescue_transcribed_source_count,
        rescue_unresolved_source_count=snapshot.rescue_unresolved_source_count,
        readiness_state=snapshot.readiness_state,
        blocker_reason_codes=list(snapshot.blocker_reason_codes),
        resolution_status=snapshot.resolution_status,
        resolution_reason=snapshot.resolution_reason,
        resolution_updated_by=snapshot.resolution_updated_by,
        resolution_updated_at=snapshot.resolution_updated_at,
    )


def _as_transcription_run_rescue_status_response(
    snapshot: DocumentTranscriptionRunRescueStatusSnapshot,
) -> TranscriptionRunRescueStatusResponse:
    return TranscriptionRunRescueStatusResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        run_id=snapshot.run.id,
        ready_for_activation=snapshot.ready_for_activation,
        blocker_count=snapshot.blocker_count,
        run_blocker_reason_codes=list(snapshot.run_blocker_reason_codes),
        pages=[
            _as_transcription_rescue_page_status_response(page)
            for page in snapshot.pages
        ],
    )


def _as_transcription_page_rescue_sources_response(
    snapshot: DocumentTranscriptionPageRescueSourcesSnapshot,
) -> TranscriptionPageRescueSourcesResponse:
    return TranscriptionPageRescueSourcesResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        run_id=snapshot.run.id,
        page_id=snapshot.page.id,
        page_index=snapshot.page.page_index,
        page_recall_status=snapshot.page_recall_status,
        readiness_state=snapshot.readiness_state,
        blocker_reason_codes=list(snapshot.blocker_reason_codes),
        rescue_sources=[
            _as_transcription_rescue_source_response(source)
            for source in snapshot.rescue_sources
        ],
        resolution_status=snapshot.resolution_status,
        resolution_reason=snapshot.resolution_reason,
        resolution_updated_by=snapshot.resolution_updated_by,
        resolution_updated_at=snapshot.resolution_updated_at,
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


def _as_transcript_version_lineage_response(
    snapshot: DocumentTranscriptVersionLineageSnapshot,
) -> TranscriptVersionLineageResponse:
    source_type: TranscriptVersionSourceTypeLiteral
    if snapshot.source_type in {
        "ENGINE_OUTPUT",
        "REVIEWER_CORRECTION",
        "COMPARE_COMPOSED",
    }:
        source_type = snapshot.source_type
    else:
        source_type = "ENGINE_OUTPUT"
    return TranscriptVersionLineageResponse(
        version=_as_transcript_version_response(snapshot.version),
        is_active=snapshot.is_active,
        source_type=source_type,
    )


def _as_transcription_line_version_history_response(
    *,
    snapshot: DocumentTranscriptionLineVersionHistorySnapshot,
) -> TranscriptionLineVersionHistoryResponse:
    return TranscriptionLineVersionHistoryResponse(
        document_id=snapshot.run.document_id,
        project_id=snapshot.run.project_id,
        run_id=snapshot.run.id,
        page_id=snapshot.page.id,
        line_id=snapshot.line.line_id,
        line=_as_transcription_line_result_response(snapshot.line),
        versions=[
            _as_transcript_version_lineage_response(item) for item in snapshot.versions
        ],
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
        compare_decision_snapshot_hash=snapshot.compare_decision_snapshot_hash,
        compare_decision_count=snapshot.compare_decision_count,
        compare_decision_event_count=snapshot.compare_decision_event_count,
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


def _as_transcription_compare_finalize_response(
    *,
    snapshot: DocumentTranscriptionCompareFinalizeSnapshot,
    active_run_id: str | None,
) -> FinalizeTranscriptionCompareResponse:
    return FinalizeTranscriptionCompareResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        base_run_id=snapshot.base_run.id,
        candidate_run_id=snapshot.candidate_run.id,
        composed_run=_as_transcription_run_response(
            snapshot.composed_run,
            active_run_id=active_run_id,
        ),
        compare_decision_snapshot_hash=snapshot.compare_decision_snapshot_hash,
        page_scope=list(snapshot.page_scope),
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


def _as_redaction_run_response(
    record: RedactionRunRecord,
    *,
    active_run_id: str | None = None,
) -> RedactionRunResponse:
    is_superseded = record.superseded_by_redaction_run_id is not None
    return RedactionRunResponse(
        id=record.id,
        project_id=record.project_id,
        document_id=record.document_id,
        input_transcription_run_id=record.input_transcription_run_id,
        input_layout_run_id=record.input_layout_run_id,
        run_kind=record.run_kind,
        supersedes_redaction_run_id=record.supersedes_redaction_run_id,
        superseded_by_redaction_run_id=record.superseded_by_redaction_run_id,
        policy_snapshot_id=record.policy_snapshot_id,
        policy_snapshot_json=record.policy_snapshot_json,
        policy_snapshot_hash=record.policy_snapshot_hash,
        policy_id=record.policy_id,
        policy_family_id=record.policy_family_id,
        policy_version=record.policy_version,
        detectors_version=record.detectors_version,
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
    )


def _as_redaction_projection_response(
    record: DocumentRedactionProjectionRecord,
) -> RedactionProjectionResponse:
    return RedactionProjectionResponse(
        document_id=record.document_id,
        project_id=record.project_id,
        active_redaction_run_id=record.active_redaction_run_id,
        active_transcription_run_id=record.active_transcription_run_id,
        active_layout_run_id=record.active_layout_run_id,
        active_policy_snapshot_id=record.active_policy_snapshot_id,
        updated_at=record.updated_at,
    )


def _as_redaction_run_status_response(
    record: RedactionRunRecord,
) -> RedactionRunStatusResponse:
    return RedactionRunStatusResponse(
        run_id=record.id,
        document_id=record.document_id,
        status=record.status,
        failure_reason=record.failure_reason,
        started_at=record.started_at,
        finished_at=record.finished_at,
        created_at=record.created_at,
        active=record.status in {"QUEUED", "RUNNING"},
    )


def _as_redaction_run_review_response(
    record: RedactionRunReviewRecord,
) -> RedactionRunReviewResponse:
    return RedactionRunReviewResponse(
        run_id=record.run_id,
        review_status=record.review_status,
        review_started_by=record.review_started_by,
        review_started_at=record.review_started_at,
        approved_by=record.approved_by,
        approved_at=record.approved_at,
        approved_snapshot_key=record.approved_snapshot_key,
        approved_snapshot_sha256=record.approved_snapshot_sha256,
        locked_at=record.locked_at,
        updated_at=record.updated_at,
    )


def _as_redaction_finding_response(
    record: RedactionFindingRecord,
    *,
    active_area_mask: RedactionAreaMaskRecord | None = None,
) -> RedactionFindingResponse:
    area_mask_geometry_json: dict[str, object] | None
    if active_area_mask is not None:
        area_mask_geometry_json = dict(active_area_mask.geometry_json)
    elif record.area_mask_id is not None:
        area_mask_geometry_json = {}
    else:
        area_mask_geometry_json = None
    geometry_payload = build_finding_geometry_payload(
        token_refs_json=record.token_refs_json,
        bbox_refs=record.bbox_refs,
        area_mask_geometry_json=area_mask_geometry_json,
    )
    return RedactionFindingResponse(
        id=record.id,
        run_id=record.run_id,
        page_id=record.page_id,
        line_id=record.line_id,
        category=record.category,
        span_start=record.span_start,
        span_end=record.span_end,
        span_basis_kind=record.span_basis_kind,
        span_basis_ref=record.span_basis_ref,
        confidence=record.confidence,
        basis_primary=record.basis_primary,
        basis_secondary_json=record.basis_secondary_json,
        assist_explanation_key=record.assist_explanation_key,
        assist_explanation_sha256=record.assist_explanation_sha256,
        bbox_refs=record.bbox_refs,
        token_refs_json=record.token_refs_json,
        area_mask_id=record.area_mask_id,
        decision_status=record.decision_status,
        action_type=record.action_type,
        override_risk_classification=record.override_risk_classification,
        override_risk_reason_codes_json=record.override_risk_reason_codes_json,
        decision_by=record.decision_by,
        decision_at=record.decision_at,
        decision_reason=record.decision_reason,
        decision_etag=record.decision_etag,
        updated_at=record.updated_at,
        created_at=record.created_at,
        geometry=RedactionFindingGeometryResponse(
            anchor_kind=str(geometry_payload.get("anchorKind") or "NONE"),  # type: ignore[arg-type]
            line_id=(
                str(geometry_payload["lineId"])
                if isinstance(geometry_payload.get("lineId"), str)
                else None
            ),
            token_ids=[
                str(token_id)
                for token_id in geometry_payload.get("tokenIds", [])
                if isinstance(token_id, str)
            ],
            boxes=[
                RedactionFindingGeometryBoxResponse(
                    x=float(box["x"]),
                    y=float(box["y"]),
                    width=float(box["width"]),
                    height=float(box["height"]),
                    source=str(box.get("source") or "BBOX_REF"),  # type: ignore[arg-type]
                )
                for box in geometry_payload.get("boxes", [])
                if isinstance(box, dict)
                and isinstance(box.get("x"), (int, float))
                and isinstance(box.get("y"), (int, float))
                and isinstance(box.get("width"), (int, float))
                and isinstance(box.get("height"), (int, float))
            ],
            polygons=[
                RedactionFindingGeometryPolygonResponse(
                    points=[
                        RedactionFindingGeometryPointResponse(
                            x=float(point["x"]),
                            y=float(point["y"]),
                        )
                        for point in polygon.get("points", [])
                        if isinstance(point, dict)
                        and isinstance(point.get("x"), (int, float))
                        and isinstance(point.get("y"), (int, float))
                    ],
                    source=str(polygon.get("source") or "BBOX_REF"),  # type: ignore[arg-type]
                )
                for polygon in geometry_payload.get("polygons", [])
                if isinstance(polygon, dict)
                and isinstance(polygon.get("points"), list)
            ],
        ),
        active_area_mask=(
            _as_redaction_area_mask_response(active_area_mask)
            if active_area_mask is not None
            else None
        ),
    )


def _as_redaction_page_review_response(
    record: RedactionPageReviewRecord,
) -> RedactionPageReviewResponse:
    return RedactionPageReviewResponse(
        run_id=record.run_id,
        page_id=record.page_id,
        review_status=record.review_status,
        review_etag=record.review_etag,
        first_reviewed_by=record.first_reviewed_by,
        first_reviewed_at=record.first_reviewed_at,
        requires_second_review=record.requires_second_review,
        second_review_status=record.second_review_status,
        second_reviewed_by=record.second_reviewed_by,
        second_reviewed_at=record.second_reviewed_at,
        updated_at=record.updated_at,
    )


def _as_redaction_run_page_response(
    snapshot: DocumentRedactionRunPageSnapshot,
) -> RedactionRunPageResponse:
    return RedactionRunPageResponse(
        run_id=snapshot.run_id,
        page_id=snapshot.page_id,
        page_index=snapshot.page_index,
        finding_count=snapshot.finding_count,
        unresolved_count=snapshot.unresolved_count,
        review_status=snapshot.review_status,
        review_etag=snapshot.review_etag,
        requires_second_review=snapshot.requires_second_review,
        second_review_status=snapshot.second_review_status,
        second_reviewed_by=snapshot.second_reviewed_by,
        second_reviewed_at=snapshot.second_reviewed_at,
        last_reviewed_by=snapshot.last_reviewed_by,
        last_reviewed_at=snapshot.last_reviewed_at,
        preview_status=snapshot.preview_status,
        top_findings=[_as_redaction_finding_response(item) for item in snapshot.top_findings],
    )


def _as_redaction_area_mask_response(
    record: RedactionAreaMaskRecord,
) -> RedactionAreaMaskResponse:
    return RedactionAreaMaskResponse(
        id=record.id,
        run_id=record.run_id,
        page_id=record.page_id,
        geometry_json=record.geometry_json,
        mask_reason=record.mask_reason,
        version_etag=record.version_etag,
        supersedes_area_mask_id=record.supersedes_area_mask_id,
        superseded_by_area_mask_id=record.superseded_by_area_mask_id,
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_redaction_timeline_event_response(
    record: DocumentRedactionRunTimelineEventSnapshot,
) -> RedactionTimelineEventResponse:
    return RedactionTimelineEventResponse(
        source_table=record.source_table,
        source_table_precedence=record.source_table_precedence,
        event_id=record.event_id,
        run_id=record.run_id,
        page_id=record.page_id,
        finding_id=record.finding_id,
        event_type=record.event_type,
        actor_user_id=record.actor_user_id,
        reason=record.reason,
        created_at=record.created_at,
        details_json=record.details_json,
    )


def _as_redaction_preview_status_response(
    snapshot: DocumentRedactionPreviewStatusSnapshot,
) -> RedactionPreviewStatusResponse:
    return RedactionPreviewStatusResponse(
        run_id=snapshot.run_id,
        page_id=snapshot.page_id,
        status=snapshot.status,
        preview_sha256=snapshot.preview_sha256,
        generated_at=snapshot.generated_at,
        failure_reason=snapshot.failure_reason,
        run_output_status=snapshot.run_output_status,
        run_output_manifest_sha256=snapshot.run_output_manifest_sha256,
        run_output_readiness_state=snapshot.run_output_readiness_state,
        downstream_ready=snapshot.downstream_ready,
    )


def _as_redaction_run_output_response(
    snapshot: DocumentRedactionRunOutputSnapshot,
) -> RedactionRunOutputResponse:
    record = snapshot.run_output
    return RedactionRunOutputResponse(
        run_id=record.run_id,
        status=record.status,
        review_status=snapshot.review_status,
        readiness_state=snapshot.readiness_state,
        downstream_ready=snapshot.downstream_ready,
        output_manifest_sha256=record.output_manifest_sha256,
        page_count=record.page_count,
        started_at=record.started_at,
        generated_at=record.generated_at,
        canceled_by=record.canceled_by,
        canceled_at=record.canceled_at,
        failure_reason=record.failure_reason,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_redaction_overview_response(
    *,
    snapshot: DocumentRedactionOverviewSnapshot,
    active_run_id: str | None,
) -> RedactionOverviewResponse:
    return RedactionOverviewResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        projection=(
            _as_redaction_projection_response(snapshot.projection)
            if snapshot.projection is not None
            else None
        ),
        active_run=(
            _as_redaction_run_response(snapshot.active_run, active_run_id=active_run_id)
            if snapshot.active_run is not None
            else None
        ),
        latest_run=(
            _as_redaction_run_response(snapshot.latest_run, active_run_id=active_run_id)
            if snapshot.latest_run is not None
            else None
        ),
        total_runs=snapshot.total_runs,
        page_count=snapshot.page_count,
        findings_by_category=snapshot.findings_by_category,
        unresolved_findings=snapshot.unresolved_findings,
        auto_applied_findings=snapshot.auto_applied_findings,
        needs_review_findings=snapshot.needs_review_findings,
        overridden_findings=snapshot.overridden_findings,
        pages_blocked_for_review=snapshot.pages_blocked_for_review,
        preview_ready_pages=snapshot.preview_ready_pages,
        preview_total_pages=snapshot.preview_total_pages,
        preview_failed_pages=snapshot.preview_failed_pages,
    )


def _as_redaction_compare_page_response(
    snapshot: DocumentRedactionComparePageSnapshot,
) -> RedactionComparePageResponse:
    return RedactionComparePageResponse(
        page_id=snapshot.page_id,
        page_index=snapshot.page_index,
        base_finding_count=snapshot.base_finding_count,
        candidate_finding_count=snapshot.candidate_finding_count,
        changed_decision_count=snapshot.changed_decision_count,
        changed_action_count=snapshot.changed_action_count,
        base_decision_counts=snapshot.base_decision_counts,
        candidate_decision_counts=snapshot.candidate_decision_counts,
        decision_status_deltas=snapshot.decision_status_deltas,
        base_action_counts=snapshot.base_action_counts,
        candidate_action_counts=snapshot.candidate_action_counts,
        action_type_deltas=snapshot.action_type_deltas,
        action_compare_state=snapshot.action_compare_state,
        changed_review_status=snapshot.changed_review_status,
        changed_second_review_status=snapshot.changed_second_review_status,
        base_review=(
            _as_redaction_page_review_response(snapshot.base_review)
            if snapshot.base_review is not None
            else None
        ),
        candidate_review=(
            _as_redaction_page_review_response(snapshot.candidate_review)
            if snapshot.candidate_review is not None
            else None
        ),
        base_preview_status=snapshot.base_preview_status,
        candidate_preview_status=snapshot.candidate_preview_status,
        preview_ready_delta=snapshot.preview_ready_delta,
    )


def _as_redaction_pre_activation_warning_response(
    snapshot: DocumentRedactionPolicyWarningSnapshot,
) -> RedactionPreActivationWarningResponse:
    return RedactionPreActivationWarningResponse(
        code=snapshot.code,
        severity=snapshot.severity,
        message=snapshot.message,
        affected_categories=list(snapshot.affected_categories),
    )


def _as_redaction_compare_response(
    *,
    snapshot: DocumentRedactionCompareSnapshot,
    active_run_id: str | None,
) -> RedactionCompareResponse:
    return RedactionCompareResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        base_run=_as_redaction_run_response(
            snapshot.base_run,
            active_run_id=active_run_id,
        ),
        candidate_run=_as_redaction_run_response(
            snapshot.candidate_run,
            active_run_id=active_run_id,
        ),
        changed_page_count=snapshot.changed_page_count,
        changed_decision_count=snapshot.changed_decision_count,
        changed_action_count=snapshot.changed_action_count,
        compare_action_state=snapshot.compare_action_state,
        candidate_policy_status=snapshot.candidate_policy_status,
        comparison_only_candidate=snapshot.comparison_only_candidate,
        pre_activation_warnings=[
            _as_redaction_pre_activation_warning_response(item)
            for item in snapshot.pre_activation_warnings
        ],
        items=[_as_redaction_compare_page_response(item) for item in snapshot.pages],
    )


def _as_governance_run_summary_response(
    record: GovernanceRunSummaryRecord,
) -> GovernanceRunSummaryResponse:
    return GovernanceRunSummaryResponse(
        run_id=record.run_id,
        project_id=record.project_id,
        document_id=record.document_id,
        run_status=record.run_status,
        review_status=record.review_status,
        approved_snapshot_key=record.approved_snapshot_key,
        approved_snapshot_sha256=record.approved_snapshot_sha256,
        run_output_status=record.run_output_status,
        run_output_manifest_sha256=record.run_output_manifest_sha256,
        run_created_at=record.run_created_at,
        run_finished_at=record.run_finished_at,
        readiness_status=record.readiness_status,
        generation_status=record.generation_status,
        ready_manifest_id=record.ready_manifest_id,
        ready_ledger_id=record.ready_ledger_id,
        latest_manifest_sha256=record.latest_manifest_sha256,
        latest_ledger_sha256=record.latest_ledger_sha256,
        ledger_verification_status=record.ledger_verification_status,
        ready_at=record.ready_at,
        last_error_code=record.last_error_code,
        updated_at=record.updated_at,
    )


def _as_governance_readiness_projection_response(
    snapshot: DocumentGovernanceRunOverviewSnapshot,
) -> GovernanceReadinessProjectionResponse:
    row = snapshot.readiness
    return GovernanceReadinessProjectionResponse(
        run_id=row.run_id,
        project_id=row.project_id,
        document_id=row.document_id,
        status=row.status,
        generation_status=row.generation_status,
        manifest_id=row.manifest_id,
        ledger_id=row.ledger_id,
        last_ledger_verification_run_id=row.last_ledger_verification_run_id,
        last_manifest_sha256=row.last_manifest_sha256,
        last_ledger_sha256=row.last_ledger_sha256,
        ledger_verification_status=row.ledger_verification_status,
        ledger_verified_at=row.ledger_verified_at,
        ready_at=row.ready_at,
        last_error_code=row.last_error_code,
        updated_at=row.updated_at,
    )


def _as_governance_manifest_attempt_response(
    record: RedactionManifestRecord,
) -> GovernanceManifestAttemptResponse:
    return GovernanceManifestAttemptResponse(
        id=record.id,
        run_id=record.run_id,
        project_id=record.project_id,
        document_id=record.document_id,
        source_review_snapshot_key=record.source_review_snapshot_key,
        source_review_snapshot_sha256=record.source_review_snapshot_sha256,
        attempt_number=record.attempt_number,
        supersedes_manifest_id=record.supersedes_manifest_id,
        superseded_by_manifest_id=record.superseded_by_manifest_id,
        status=record.status,
        manifest_key=record.manifest_key,
        manifest_sha256=record.manifest_sha256,
        format_version=record.format_version,
        started_at=record.started_at,
        finished_at=record.finished_at,
        canceled_by=record.canceled_by,
        canceled_at=record.canceled_at,
        failure_reason=record.failure_reason,
        created_by=record.created_by,
        created_at=record.created_at,
    )


def _as_governance_ledger_attempt_response(
    record: RedactionEvidenceLedgerRecord,
) -> GovernanceLedgerAttemptResponse:
    return GovernanceLedgerAttemptResponse(
        id=record.id,
        run_id=record.run_id,
        project_id=record.project_id,
        document_id=record.document_id,
        source_review_snapshot_key=record.source_review_snapshot_key,
        source_review_snapshot_sha256=record.source_review_snapshot_sha256,
        attempt_number=record.attempt_number,
        supersedes_ledger_id=record.supersedes_ledger_id,
        superseded_by_ledger_id=record.superseded_by_ledger_id,
        status=record.status,
        ledger_key=record.ledger_key,
        ledger_sha256=record.ledger_sha256,
        hash_chain_version=record.hash_chain_version,
        started_at=record.started_at,
        finished_at=record.finished_at,
        canceled_by=record.canceled_by,
        canceled_at=record.canceled_at,
        failure_reason=record.failure_reason,
        created_by=record.created_by,
        created_at=record.created_at,
    )


def _as_governance_run_overview_response(
    snapshot: DocumentGovernanceRunOverviewSnapshot,
) -> GovernanceRunOverviewResponse:
    return GovernanceRunOverviewResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        active_run_id=snapshot.active_run_id,
        run=_as_governance_run_summary_response(snapshot.run),
        readiness=_as_governance_readiness_projection_response(snapshot),
        manifest_attempts=[
            _as_governance_manifest_attempt_response(item)
            for item in snapshot.manifest_attempts
        ],
        ledger_attempts=[
            _as_governance_ledger_attempt_response(item)
            for item in snapshot.ledger_attempts
        ],
    )


def _as_governance_overview_response(
    snapshot: DocumentGovernanceOverviewSnapshot,
) -> GovernanceOverviewResponse:
    return GovernanceOverviewResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        active_run_id=snapshot.active_run_id,
        total_runs=snapshot.total_runs,
        approved_runs=snapshot.approved_runs,
        ready_runs=snapshot.ready_runs,
        pending_runs=snapshot.pending_runs,
        failed_runs=snapshot.failed_runs,
        latest_run_id=snapshot.latest_run_id,
        latest_ready_run_id=snapshot.latest_ready_run_id,
        latest_run=(
            _as_governance_run_summary_response(snapshot.latest_run)
            if snapshot.latest_run is not None
            else None
        ),
        latest_ready_run=(
            _as_governance_run_summary_response(snapshot.latest_ready_run)
            if snapshot.latest_ready_run is not None
            else None
        ),
    )


def _as_governance_runs_response(
    snapshot: DocumentGovernanceRunsSnapshot,
) -> GovernanceRunsResponse:
    return GovernanceRunsResponse(
        document_id=snapshot.document.id,
        project_id=snapshot.document.project_id,
        active_run_id=snapshot.active_run_id,
        items=[_as_governance_run_summary_response(row) for row in snapshot.runs],
    )


def _as_governance_events_response(
    *,
    run_id: str,
    items: tuple[DocumentGovernanceEventSnapshot, ...],
) -> GovernanceRunEventsResponse:
    return GovernanceRunEventsResponse(
        run_id=run_id,
        items=[
            GovernanceRunEventResponse(
                id=item.id,
                run_id=item.run_id,
                event_type=item.event_type,
                actor_user_id=item.actor_user_id,
                from_status=item.from_status,
                to_status=item.to_status,
                reason=item.reason,
                created_at=item.created_at,
                screening_safe=item.screening_safe,
            )
            for item in items
        ],
    )


def _as_governance_manifest_response(
    snapshot: DocumentGovernanceManifestSnapshot,
) -> GovernanceManifestResponse:
    return GovernanceManifestResponse(
        overview=_as_governance_run_overview_response(snapshot.overview),
        latest_attempt=(
            _as_governance_manifest_attempt_response(snapshot.latest_attempt)
            if snapshot.latest_attempt is not None
            else None
        ),
        manifest_json=(dict(snapshot.manifest_payload) if snapshot.manifest_payload is not None else None),
        stream_sha256=snapshot.stream_sha256,
        hash_matches=snapshot.hash_matches,
        internal_only=snapshot.internal_only,
        export_approved=snapshot.export_approved,
        not_export_approved=snapshot.not_export_approved,
    )


def _as_governance_manifest_status_response(
    snapshot: DocumentGovernanceManifestStatusSnapshot,
) -> GovernanceManifestStatusResponse:
    return GovernanceManifestStatusResponse(
        run_id=snapshot.run_id,
        status=snapshot.status,
        latest_attempt=(
            _as_governance_manifest_attempt_response(snapshot.latest_attempt)
            if snapshot.latest_attempt is not None
            else None
        ),
        attempt_count=snapshot.attempt_count,
        ready_manifest_id=snapshot.ready_manifest_id,
        latest_manifest_sha256=snapshot.latest_manifest_sha256,
        generation_status=snapshot.generation_status,
        readiness_status=snapshot.readiness_status,
        updated_at=snapshot.updated_at,
    )


def _as_governance_manifest_entry_response(
    record: Mapping[str, object],
) -> GovernanceManifestEntryResponse:
    return GovernanceManifestEntryResponse(
        entry_id=str(record.get("entryId") or ""),
        applied_action=str(record.get("appliedAction") or "MASK"),
        category=str(record.get("category") or ""),
        page_id=str(record.get("pageId") or ""),
        page_index=record.get("pageIndex") if isinstance(record.get("pageIndex"), int) else None,
        line_id=(
            str(record["lineId"])
            if isinstance(record.get("lineId"), str) and str(record["lineId"]).strip()
            else None
        ),
        location_ref=(
            dict(record["locationRef"])
            if isinstance(record.get("locationRef"), Mapping)
            else {}
        ),
        basis_primary=str(record.get("basisPrimary") or "UNKNOWN"),
        confidence=(
            float(record["confidence"])
            if isinstance(record.get("confidence"), (int, float))
            else None
        ),
        secondary_basis_summary=(
            dict(record["secondaryBasisSummary"])
            if isinstance(record.get("secondaryBasisSummary"), Mapping)
            else None
        ),
        final_decision_state=str(record.get("finalDecisionState") or ""),
        review_state=str(record.get("reviewState") or ""),
        policy_snapshot_hash=(
            str(record["policySnapshotHash"])
            if isinstance(record.get("policySnapshotHash"), str)
            else None
        ),
        policy_id=str(record["policyId"]) if isinstance(record.get("policyId"), str) else None,
        policy_family_id=(
            str(record["policyFamilyId"])
            if isinstance(record.get("policyFamilyId"), str)
            else None
        ),
        policy_version=(
            str(record["policyVersion"])
            if isinstance(record.get("policyVersion"), str)
            else None
        ),
        decision_timestamp=(
            str(record["decisionTimestamp"])
            if isinstance(record.get("decisionTimestamp"), str)
            else None
        ),
        decision_by=(
            str(record["decisionBy"])
            if isinstance(record.get("decisionBy"), str)
            else None
        ),
        decision_etag=(
            str(record["decisionEtag"])
            if isinstance(record.get("decisionEtag"), str)
            else None
        ),
    )


def _as_governance_manifest_entries_response(
    snapshot: DocumentGovernanceManifestEntriesSnapshot,
) -> GovernanceManifestEntriesResponse:
    return GovernanceManifestEntriesResponse(
        run_id=snapshot.run_id,
        status=snapshot.status,
        manifest_id=snapshot.manifest_id,
        manifest_sha256=snapshot.manifest_sha256,
        source_review_snapshot_sha256=snapshot.source_review_snapshot_sha256,
        total_count=snapshot.total_count,
        next_cursor=snapshot.next_cursor,
        internal_only=snapshot.internal_only,
        export_approved=snapshot.export_approved,
        not_export_approved=snapshot.not_export_approved,
        items=[_as_governance_manifest_entry_response(item) for item in snapshot.items],
    )


def _as_governance_manifest_hash_response(
    snapshot: DocumentGovernanceManifestHashSnapshot,
) -> GovernanceManifestHashResponse:
    return GovernanceManifestHashResponse(
        run_id=snapshot.run_id,
        status=snapshot.status,
        manifest_id=snapshot.manifest_id,
        manifest_sha256=snapshot.manifest_sha256,
        stream_sha256=snapshot.stream_sha256,
        hash_matches=snapshot.hash_matches,
        internal_only=snapshot.internal_only,
        export_approved=snapshot.export_approved,
        not_export_approved=snapshot.not_export_approved,
    )


def _as_governance_ledger_response(
    snapshot: DocumentGovernanceLedgerSnapshot,
) -> GovernanceLedgerResponse:
    return GovernanceLedgerResponse(
        overview=_as_governance_run_overview_response(snapshot.overview),
        latest_attempt=(
            _as_governance_ledger_attempt_response(snapshot.latest_attempt)
            if snapshot.latest_attempt is not None
            else None
        ),
        ledger_json=(dict(snapshot.ledger_payload) if snapshot.ledger_payload is not None else None),
        stream_sha256=snapshot.stream_sha256,
        hash_matches=snapshot.hash_matches,
        internal_only=snapshot.internal_only,
    )


def _as_governance_ledger_status_response(
    snapshot: DocumentGovernanceLedgerStatusSnapshot,
) -> GovernanceLedgerStatusResponse:
    return GovernanceLedgerStatusResponse(
        run_id=snapshot.run_id,
        status=snapshot.status,
        latest_attempt=(
            _as_governance_ledger_attempt_response(snapshot.latest_attempt)
            if snapshot.latest_attempt is not None
            else None
        ),
        attempt_count=snapshot.attempt_count,
        ready_ledger_id=snapshot.ready_ledger_id,
        latest_ledger_sha256=snapshot.latest_ledger_sha256,
        generation_status=snapshot.generation_status,
        readiness_status=snapshot.readiness_status,
        ledger_verification_status=snapshot.ledger_verification_status,
        updated_at=snapshot.updated_at,
    )


def _as_governance_ledger_entry_response(
    record: Mapping[str, object],
) -> GovernanceLedgerEntryResponse:
    return GovernanceLedgerEntryResponse(
        row_id=str(record.get("rowId") or ""),
        row_index=(
            int(record["rowIndex"]) if isinstance(record.get("rowIndex"), int) else 0
        ),
        finding_id=str(record.get("findingId") or ""),
        page_id=str(record.get("pageId") or ""),
        page_index=record.get("pageIndex") if isinstance(record.get("pageIndex"), int) else None,
        line_id=(
            str(record["lineId"])
            if isinstance(record.get("lineId"), str) and str(record["lineId"]).strip()
            else None
        ),
        category=str(record.get("category") or ""),
        action_type=str(record.get("actionType") or "MASK"),
        before_text_ref=(
            dict(record["beforeTextRef"])
            if isinstance(record.get("beforeTextRef"), Mapping)
            else {}
        ),
        after_text_ref=(
            dict(record["afterTextRef"])
            if isinstance(record.get("afterTextRef"), Mapping)
            else {}
        ),
        detector_evidence=(
            dict(record["detectorEvidence"])
            if isinstance(record.get("detectorEvidence"), Mapping)
            else {}
        ),
        assist_explanation_key=(
            str(record["assistExplanationKey"])
            if isinstance(record.get("assistExplanationKey"), str)
            else None
        ),
        assist_explanation_sha256=(
            str(record["assistExplanationSha256"])
            if isinstance(record.get("assistExplanationSha256"), str)
            else None
        ),
        actor_user_id=(
            str(record["actorUserId"]) if isinstance(record.get("actorUserId"), str) else None
        ),
        decision_timestamp=(
            str(record["decisionTimestamp"])
            if isinstance(record.get("decisionTimestamp"), str)
            else None
        ),
        override_reason=(
            str(record["overrideReason"])
            if isinstance(record.get("overrideReason"), str)
            else None
        ),
        final_decision_state=(
            str(record["finalDecisionState"])
            if isinstance(record.get("finalDecisionState"), str)
            else None
        ),
        policy_snapshot_hash=(
            str(record["policySnapshotHash"])
            if isinstance(record.get("policySnapshotHash"), str)
            else None
        ),
        policy_id=str(record["policyId"]) if isinstance(record.get("policyId"), str) else None,
        policy_family_id=(
            str(record["policyFamilyId"])
            if isinstance(record.get("policyFamilyId"), str)
            else None
        ),
        policy_version=(
            str(record["policyVersion"])
            if isinstance(record.get("policyVersion"), str)
            else None
        ),
        prev_hash=str(record.get("prevHash") or ""),
        row_hash=str(record.get("rowHash") or ""),
    )


def _as_governance_ledger_entries_response(
    snapshot: DocumentGovernanceLedgerEntriesSnapshot,
) -> GovernanceLedgerEntriesResponse:
    return GovernanceLedgerEntriesResponse(
        run_id=snapshot.run_id,
        status=snapshot.status,
        view=snapshot.view,
        ledger_id=snapshot.ledger_id,
        ledger_sha256=snapshot.ledger_sha256,
        hash_chain_version=snapshot.hash_chain_version,
        total_count=snapshot.total_count,
        next_cursor=snapshot.next_cursor,
        verification_status=snapshot.verification_status,
        items=[_as_governance_ledger_entry_response(item) for item in snapshot.items],
    )


def _as_governance_ledger_summary_response(
    snapshot: DocumentGovernanceLedgerSummarySnapshot,
) -> GovernanceLedgerSummaryResponse:
    return GovernanceLedgerSummaryResponse(
        run_id=snapshot.run_id,
        status=snapshot.status,
        ledger_id=snapshot.ledger_id,
        ledger_sha256=snapshot.ledger_sha256,
        hash_chain_version=snapshot.hash_chain_version,
        row_count=snapshot.row_count,
        hash_chain_head=snapshot.hash_chain_head,
        hash_chain_valid=snapshot.hash_chain_valid,
        verification_status=snapshot.verification_status,
        category_counts=dict(snapshot.category_counts),
        action_counts=dict(snapshot.action_counts),
        override_count=snapshot.override_count,
        assist_reference_count=snapshot.assist_reference_count,
        internal_only=snapshot.internal_only,
    )


def _as_governance_ledger_verification_run_response(
    record: LedgerVerificationRunRecord,
) -> GovernanceLedgerVerificationRunResponse:
    return GovernanceLedgerVerificationRunResponse(
        id=record.id,
        run_id=record.run_id,
        attempt_number=record.attempt_number,
        supersedes_verification_run_id=record.supersedes_verification_run_id,
        superseded_by_verification_run_id=record.superseded_by_verification_run_id,
        status=record.status,
        verification_result=record.verification_result,
        result_json=(dict(record.result_json) if record.result_json is not None else None),
        started_at=record.started_at,
        finished_at=record.finished_at,
        canceled_by=record.canceled_by,
        canceled_at=record.canceled_at,
        failure_reason=record.failure_reason,
        created_by=record.created_by,
        created_at=record.created_at,
    )


def _as_governance_ledger_verify_status_response(
    snapshot: DocumentGovernanceLedgerVerificationStatusSnapshot,
) -> GovernanceLedgerVerifyStatusResponse:
    return GovernanceLedgerVerifyStatusResponse(
        run_id=snapshot.run_id,
        verification_status=snapshot.verification_status,
        attempt_count=snapshot.attempt_count,
        latest_attempt=(
            _as_governance_ledger_verification_run_response(snapshot.latest_attempt)
            if snapshot.latest_attempt is not None
            else None
        ),
        latest_completed_attempt=(
            _as_governance_ledger_verification_run_response(snapshot.latest_completed_attempt)
            if snapshot.latest_completed_attempt is not None
            else None
        ),
        ready_ledger_id=snapshot.ready_ledger_id,
        latest_ledger_sha256=snapshot.latest_ledger_sha256,
        last_verified_at=snapshot.last_verified_at,
    )


def _as_governance_ledger_verify_runs_response(
    snapshot: DocumentGovernanceLedgerVerificationRunsSnapshot,
) -> GovernanceLedgerVerifyRunsResponse:
    return GovernanceLedgerVerifyRunsResponse(
        run_id=snapshot.run_id,
        verification_status=snapshot.verification_status,
        items=[_as_governance_ledger_verification_run_response(item) for item in snapshot.items],
    )


def _as_governance_ledger_verify_detail_response(
    snapshot: DocumentGovernanceLedgerVerificationDetailSnapshot,
) -> GovernanceLedgerVerifyDetailResponse:
    return GovernanceLedgerVerifyDetailResponse(
        run_id=snapshot.run_id,
        verification_status=snapshot.verification_status,
        attempt=_as_governance_ledger_verification_run_response(snapshot.attempt),
    )


def _resolve_redaction_context(
    *,
    current_user: SessionPrincipal,
    project_id: str,
    document_id: str,
    document_service: DocumentService,
) -> tuple[DocumentRedactionProjectionRecord | None, str | None]:
    projection = document_service.get_redaction_projection(
        current_user=current_user,
        project_id=project_id,
        document_id=document_id,
    )
    active_run_id = projection.active_redaction_run_id if projection is not None else None
    return projection, active_run_id


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
            DocumentRedactionAccessDeniedError,
            DocumentGovernanceAccessDeniedError,
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
            DocumentRedactionRunNotFoundError,
            DocumentGovernanceRunNotFoundError,
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
            DocumentRedactionConflictError,
            DocumentGovernanceConflictError,
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
                worker_prefix = f"doc-import-bg-{import_id}"
                for attempt in range(8):
                    worker_id = f"{worker_prefix}-{attempt + 1}"
                    claimed = job_service.claim_next_document_ingest_job_for_worker(
                        project_id=project_id,
                        document_id=completed.document_record.id,
                        worker_id=worker_id,
                        lease_seconds=60,
                    )
                    if claimed is None:
                        break
                    processed = job_service.process_claimed_job(
                        worker_id=worker_id,
                        row=claimed,
                    )
                    if processed.type == "RENDER_THUMBNAILS" and processed.status in {
                        "SUCCEEDED",
                        "FAILED",
                        "CANCELED",
                    }:
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
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
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
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
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
    page_number: int | None = Query(default=None, alias="page", ge=1),
    line_id: str | None = Query(default=None, alias="lineId", min_length=1, max_length=200),
    token_id: str | None = Query(default=None, alias="tokenId", min_length=1, max_length=200),
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
            page_number=page_number,
            line_id=line_id,
            token_id=token_id,
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
            "page": page_number,
            "line_id": line_id,
            "token_id": token_id,
            "compare_decision_snapshot_hash": snapshot.compare_decision_snapshot_hash,
            "compare_decision_count": snapshot.compare_decision_count,
            "compare_decision_event_count": snapshot.compare_decision_event_count,
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


@router.post(
    "/documents/{document_id}/transcription-runs/compare/finalize",
    response_model=FinalizeTranscriptionCompareResponse,
)
def finalize_project_document_transcription_compare(
    project_id: str,
    document_id: str,
    payload: FinalizeTranscriptionCompareRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> FinalizeTranscriptionCompareResponse:
    try:
        snapshot = document_service.finalize_transcription_compare(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            base_run_id=payload.base_run_id,
            candidate_run_id=payload.candidate_run_id,
            page_ids=payload.page_ids,
            expected_compare_decision_snapshot_hash=payload.expected_compare_decision_snapshot_hash,
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
        event_type="TRANSCRIPTION_COMPARE_FINALIZED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="transcription_run",
        object_id=snapshot.composed_run.id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "base_run_id": snapshot.base_run.id,
            "candidate_run_id": snapshot.candidate_run.id,
            "composed_run_id": snapshot.composed_run.id,
            "compare_decision_snapshot_hash": snapshot.compare_decision_snapshot_hash,
            "page_scope_count": len(snapshot.page_scope),
        },
        request_context=request_context,
    )
    return _as_transcription_compare_finalize_response(
        snapshot=snapshot,
        active_run_id=active_projection_run_id,
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
    "/documents/{document_id}/transcription-runs/{run_id}/rescue-status",
    response_model=TranscriptionRunRescueStatusResponse,
)
def get_project_document_transcription_run_rescue_status(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionRunRescueStatusResponse:
    try:
        snapshot = document_service.get_transcription_run_rescue_status(
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
        event_type="TRANSCRIPTION_RESCUE_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="transcription_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "run_id": run_id,
            "page_count": len(snapshot.pages),
            "blocker_count": snapshot.blocker_count,
            "ready_for_activation": snapshot.ready_for_activation,
        },
        request_context=request_context,
    )
    return _as_transcription_run_rescue_status_response(snapshot)


@router.get(
    "/documents/{document_id}/transcription-runs/{run_id}/pages/{page_id}/rescue-sources",
    response_model=TranscriptionPageRescueSourcesResponse,
)
def get_project_document_transcription_run_page_rescue_sources(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionPageRescueSourcesResponse:
    try:
        snapshot = document_service.list_transcription_run_page_rescue_sources(
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
        event_type="TRANSCRIPTION_RESCUE_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "rescue_source_count": len(snapshot.rescue_sources),
            "readiness_state": snapshot.readiness_state,
        },
        request_context=request_context,
    )
    return _as_transcription_page_rescue_sources_response(snapshot)


@router.patch(
    "/documents/{document_id}/transcription-runs/{run_id}/pages/{page_id}/rescue-resolution",
    response_model=TranscriptionPageRescueSourcesResponse,
)
def update_project_document_transcription_run_page_rescue_resolution(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    payload: UpdateTranscriptionRescueResolutionRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionPageRescueSourcesResponse:
    try:
        snapshot = document_service.update_transcription_page_rescue_resolution(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            resolution_status=payload.resolution_status,
            resolution_reason=payload.resolution_reason,
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
        event_type="TRANSCRIPTION_RESCUE_RESOLUTION_UPDATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "resolution_status": payload.resolution_status,
            "readiness_state": snapshot.readiness_state,
        },
        request_context=request_context,
    )
    return _as_transcription_page_rescue_sources_response(snapshot)


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
    except DocumentTranscriptionConflictError as error:
        rescue_status = getattr(error, "rescue_status", None)
        blocker_codes = tuple(getattr(error, "blocker_codes", ()))
        blocker_count = (
            rescue_status.blocker_count
            if rescue_status is not None
            else len(blocker_codes)
        )
        audit_service.record_event_best_effort(
            event_type="TRANSCRIPTION_RUN_ACTIVATION_BLOCKED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="transcription_run",
            object_id=run_id,
            metadata={
                "route": request_context.route_template,
                "run_id": run_id,
                "document_id": document_id,
                "reason": str(error),
                "blocker_codes": list(blocker_codes),
                "blocker_count": blocker_count,
            },
            request_context=request_context,
        )
        payload: dict[str, object] = {
            "detail": str(error),
            "blockerCodes": list(blocker_codes),
            "blockerCount": blocker_count,
        }
        if rescue_status is not None:
            payload["rescueStatus"] = _as_transcription_run_rescue_status_response(
                rescue_status
            ).model_dump(by_alias=True, mode="json")
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


@router.get(
    "/documents/{document_id}/transcription-runs/{run_id}/pages/{page_id}/lines/{line_id}/versions",
    response_model=TranscriptionLineVersionHistoryResponse,
)
def list_project_document_transcription_line_versions(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    line_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptionLineVersionHistoryResponse:
    try:
        snapshot = document_service.list_transcription_line_versions(
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
        event_type="TRANSCRIPT_LINE_VERSION_HISTORY_VIEWED",
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
            "version_count": len(snapshot.versions),
        },
        request_context=request_context,
    )
    return _as_transcription_line_version_history_response(snapshot=snapshot)


@router.get(
    "/documents/{document_id}/transcription-runs/{run_id}/pages/{page_id}/lines/{line_id}/versions/{version_id}",
    response_model=TranscriptVersionLineageResponse,
)
def get_project_document_transcription_line_version(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    line_id: str,
    version_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TranscriptVersionLineageResponse:
    try:
        snapshot = document_service.get_transcription_line_version(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            line_id=line_id,
            version_id=version_id,
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
        event_type="TRANSCRIPT_LINE_VERSION_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="transcript_version",
        object_id=version_id,
        metadata={
            "route": request_context.route_template,
            "document_id": document_id,
            "run_id": run_id,
            "page_id": page_id,
            "line_id": line_id,
            "version_id": version_id,
            "source_type": snapshot.source_type,
        },
        request_context=request_context,
    )
    return _as_transcript_version_lineage_response(snapshot)


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


@router.get(
    "/documents/{document_id}/privacy/overview",
    response_model=RedactionOverviewResponse,
)
def get_project_document_redaction_overview(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionOverviewResponse:
    try:
        snapshot = document_service.get_redaction_overview(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        _, active_run_id = _resolve_redaction_context(
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
        event_type="PRIVACY_OVERVIEW_VIEWED",
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
    return _as_redaction_overview_response(
        snapshot=snapshot,
        active_run_id=active_run_id,
    )


@router.get(
    "/documents/{document_id}/redaction-runs",
    response_model=RedactionRunListResponse,
)
def list_project_document_redaction_runs(
    project_id: str,
    document_id: str,
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=50, alias="pageSize", ge=1, le=200),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunListResponse:
    try:
        items, next_cursor = document_service.list_redaction_runs(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            cursor=cursor,
            page_size=page_size,
        )
        _, active_run_id = _resolve_redaction_context(
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
    return RedactionRunListResponse(
        items=[
            _as_redaction_run_response(item, active_run_id=active_run_id)
            for item in items
        ],
        next_cursor=next_cursor,
    )


@router.post(
    "/documents/{document_id}/redaction-runs",
    response_model=RedactionRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_document_redaction_run(
    project_id: str,
    document_id: str,
    payload: CreateRedactionRunRequest = Body(default_factory=CreateRedactionRunRequest),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunResponse:
    try:
        run = document_service.create_redaction_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            input_transcription_run_id=payload.input_transcription_run_id,
            input_layout_run_id=payload.input_layout_run_id,
            run_kind=payload.run_kind,
            supersedes_redaction_run_id=payload.supersedes_redaction_run_id,
            detectors_version=payload.detectors_version,
        )
        _, active_run_id = _resolve_redaction_context(
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
        event_type="REDACTION_RUN_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
            "run_kind": run.run_kind,
            "detectors_version": run.detectors_version,
        },
        request_context=request_context,
    )
    if run.status in {"RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}:
        audit_service.record_event_best_effort(
            event_type="REDACTION_RUN_STARTED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="redaction_run",
            object_id=run.id,
            metadata={
                "run_id": run.id,
                "document_id": run.document_id,
                "pipeline_version": run.detectors_version,
            },
            request_context=request_context,
        )
    if run.status == "SUCCEEDED":
        audit_service.record_event_best_effort(
            event_type="REDACTION_RUN_FINISHED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="redaction_run",
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
            event_type="REDACTION_RUN_FAILED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="redaction_run",
            object_id=run.id,
            metadata={
                "run_id": run.id,
                "document_id": run.document_id,
                "reason": run.failure_reason,
            },
            request_context=request_context,
        )
    elif run.status == "CANCELED":
        audit_service.record_event_best_effort(
            event_type="REDACTION_RUN_CANCELED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="redaction_run",
            object_id=run.id,
            metadata={
                "run_id": run.id,
                "document_id": run.document_id,
            },
            request_context=request_context,
        )
    return _as_redaction_run_response(run, active_run_id=active_run_id)


@router.get(
    "/documents/{document_id}/redaction-runs/active",
    response_model=RedactionActiveRunResponse,
)
def get_project_document_active_redaction_run(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionActiveRunResponse:
    try:
        projection, run = document_service.get_active_redaction_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
        )
        active_run_id = projection.active_redaction_run_id if projection else None
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
        event_type="REDACTION_ACTIVE_RUN_VIEWED",
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
    return RedactionActiveRunResponse(
        projection=(
            _as_redaction_projection_response(projection)
            if projection is not None
            else None
        ),
        run=(
            _as_redaction_run_response(run, active_run_id=active_run_id)
            if run is not None
            else None
        ),
    )


@router.get(
    "/documents/{document_id}/redaction-runs/compare",
    response_model=RedactionCompareResponse,
)
def compare_project_document_redaction_runs(
    project_id: str,
    document_id: str,
    base_run_id: str = Query(alias="baseRunId", min_length=1, max_length=120),
    candidate_run_id: str = Query(
        alias="candidateRunId",
        min_length=1,
        max_length=120,
    ),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionCompareResponse:
    try:
        snapshot = document_service.compare_redaction_runs(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            base_run_id=base_run_id,
            candidate_run_id=candidate_run_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
        )
    active_run_id: str | None = None
    try:
        _, active_run_id = _resolve_redaction_context(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            document_service=document_service,
        )
    except DocumentRedactionAccessDeniedError:
        # Compare readers (e.g. AUDITOR) are allowed without broad privacy-workspace access.
        active_run_id = None
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
        )

    audit_service.record_event_best_effort(
        event_type="POLICY_RUN_COMPARE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "base_run_id": base_run_id,
            "candidate_run_id": candidate_run_id,
            "changed_page_count": snapshot.changed_page_count,
            "changed_decision_count": snapshot.changed_decision_count,
            "comparison_only_candidate": snapshot.comparison_only_candidate,
            "warning_count": len(snapshot.pre_activation_warnings),
        },
        request_context=request_context,
    )
    return _as_redaction_compare_response(
        snapshot=snapshot,
        active_run_id=active_run_id,
    )


@router.post(
    "/documents/{document_id}/redaction-runs/{run_id}/rerun",
    response_model=RedactionRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def rerun_project_document_redaction_run_with_policy(
    project_id: str,
    document_id: str,
    run_id: str,
    policy_id: str = Query(alias="policyId", min_length=1, max_length=120),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunResponse:
    try:
        rerun = document_service.request_policy_rerun(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            source_run_id=run_id,
            policy_id=policy_id,
        )
        _, active_run_id = _resolve_redaction_context(
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
            required_roles=["PROJECT_LEAD", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="POLICY_RERUN_REQUESTED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=rerun.id,
        metadata={
            "route": request_context.route_template,
            "source_run_id": run_id,
            "candidate_run_id": rerun.id,
            "document_id": rerun.document_id,
            "policy_id": rerun.policy_id,
            "policy_family_id": rerun.policy_family_id,
            "policy_version": rerun.policy_version,
        },
        request_context=request_context,
    )
    return _as_redaction_run_response(rerun, active_run_id=active_run_id)


@router.get(
    "/documents/{document_id}/redaction-runs/{run_id}",
    response_model=RedactionRunResponse,
)
def get_project_document_redaction_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunResponse:
    try:
        run = document_service.get_redaction_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _, active_run_id = _resolve_redaction_context(
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
        event_type="PRIVACY_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
        },
        request_context=request_context,
    )
    return _as_redaction_run_response(run, active_run_id=active_run_id)


@router.get(
    "/documents/{document_id}/redaction-runs/{run_id}/status",
    response_model=RedactionRunStatusResponse,
)
def get_project_document_redaction_run_status(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunStatusResponse:
    try:
        run = document_service.get_redaction_run_status(
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
        event_type="REDACTION_RUN_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
            "status": run.status,
        },
        request_context=request_context,
    )
    return _as_redaction_run_status_response(run)


@router.post(
    "/documents/{document_id}/redaction-runs/{run_id}/cancel",
    response_model=RedactionRunResponse,
)
def cancel_project_document_redaction_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunResponse:
    try:
        run = document_service.cancel_redaction_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        _, active_run_id = _resolve_redaction_context(
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
        event_type="REDACTION_RUN_CANCELED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
        },
        request_context=request_context,
    )
    return _as_redaction_run_response(run, active_run_id=active_run_id)


@router.post(
    "/documents/{document_id}/redaction-runs/{run_id}/activate",
    response_model=ActivateRedactionRunResponse,
)
def activate_project_document_redaction_run(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> ActivateRedactionRunResponse:
    try:
        projection = document_service.activate_redaction_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        run = document_service.get_redaction_run(
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
        event_type="REDACTION_RUN_ACTIVATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run.id,
            "document_id": run.document_id,
        },
        request_context=request_context,
    )
    return ActivateRedactionRunResponse(
        projection=_as_redaction_projection_response(projection),
        run=_as_redaction_run_response(
            run,
            active_run_id=projection.active_redaction_run_id,
        ),
    )


@router.get(
    "/documents/{document_id}/redaction-runs/{run_id}/review",
    response_model=RedactionRunReviewResponse,
)
def get_project_document_redaction_run_review(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunReviewResponse:
    try:
        review = document_service.get_redaction_run_review(
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
        event_type="REDACTION_RUN_REVIEW_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "review_status": review.review_status,
        },
        request_context=request_context,
    )
    return _as_redaction_run_review_response(review)


@router.post(
    "/documents/{document_id}/redaction-runs/{run_id}/start-review",
    response_model=RedactionRunReviewResponse,
)
def start_project_document_redaction_run_review(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunReviewResponse:
    try:
        review = document_service.start_redaction_run_review(
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
        event_type="REDACTION_RUN_REVIEW_OPENED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "review_status": review.review_status,
        },
        request_context=request_context,
    )
    return _as_redaction_run_review_response(review)


@router.post(
    "/documents/{document_id}/redaction-runs/{run_id}/complete-review",
    response_model=RedactionRunReviewResponse,
)
def complete_project_document_redaction_run_review(
    project_id: str,
    document_id: str,
    run_id: str,
    payload: CompleteRedactionRunReviewRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunReviewResponse:
    try:
        review = document_service.complete_redaction_run_review(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            review_status=payload.review_status,
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

    completion_event = (
        "REDACTION_RUN_REVIEW_COMPLETED"
        if review.review_status == "APPROVED"
        else "REDACTION_RUN_REVIEW_CHANGES_REQUESTED"
    )
    audit_service.record_event_best_effort(
        event_type=completion_event,
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "review_status": review.review_status,
        },
        request_context=request_context,
    )
    return _as_redaction_run_review_response(review)


@router.get(
    "/documents/{document_id}/redaction-runs/{run_id}/events",
    response_model=RedactionRunEventsResponse,
)
def list_project_document_redaction_run_events(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunEventsResponse:
    try:
        items = document_service.list_redaction_run_events(
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
        event_type="REDACTION_RUN_EVENTS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return RedactionRunEventsResponse(
        run_id=run_id,
        items=[_as_redaction_timeline_event_response(item) for item in items],
    )


@router.get(
    "/documents/{document_id}/redaction-runs/{run_id}/pages",
    response_model=RedactionRunPageListResponse,
)
def list_project_document_redaction_run_pages(
    project_id: str,
    document_id: str,
    run_id: str,
    category: str | None = Query(default=None),
    unresolved_only: bool = Query(default=False, alias="unresolvedOnly"),
    direct_identifiers_only: bool = Query(default=False, alias="directIdentifiersOnly"),
    cursor: int = Query(default=0, ge=0),
    page_size: int = Query(default=200, alias="pageSize", ge=1, le=500),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunPageListResponse:
    try:
        items, next_cursor = document_service.list_redaction_run_pages(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            category=category,
            unresolved_only=unresolved_only,
            direct_identifiers_only=direct_identifiers_only,
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
        event_type="PRIVACY_TRIAGE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "cursor": cursor,
            "returned_count": len(items),
            "category": category,
            "unresolved_only": unresolved_only,
            "direct_identifiers_only": direct_identifiers_only,
        },
        request_context=request_context,
    )
    return RedactionRunPageListResponse(
        run_id=run_id,
        items=[_as_redaction_run_page_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get(
    "/documents/{document_id}/redaction-runs/{run_id}/pages/{page_id}/findings",
    response_model=RedactionFindingListResponse,
)
def list_project_document_redaction_run_page_findings(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    category: str | None = Query(default=None),
    unresolved_only: bool = Query(default=False, alias="unresolvedOnly"),
    direct_identifiers_only: bool = Query(default=False, alias="directIdentifiersOnly"),
    workspace_view: bool = Query(default=False, alias="workspaceView"),
    finding_id: str | None = Query(default=None, alias="findingId"),
    line_id: str | None = Query(default=None, alias="lineId"),
    token_id: str | None = Query(default=None, alias="tokenId"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionFindingListResponse:
    try:
        items = document_service.list_redaction_run_page_findings(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            category=category,
            unresolved_only=unresolved_only,
            direct_identifiers_only=direct_identifiers_only,
        )
        area_masks = document_service.list_redaction_area_masks(
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
    area_masks_by_id = {item.id: item for item in area_masks}

    if workspace_view:
        audit_service.record_event_best_effort(
            event_type="PRIVACY_WORKSPACE_VIEWED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="page",
            object_id=page_id,
            metadata={
                "route": request_context.route_template,
                "run_id": run_id,
                "document_id": document_id,
                "page_id": page_id,
                "finding_id": finding_id,
                "line_id": line_id,
                "token_id": token_id,
            },
            request_context=request_context,
        )
    return RedactionFindingListResponse(
        run_id=run_id,
        page_id=page_id,
        items=[
            _as_redaction_finding_response(
                item,
                active_area_mask=(
                    area_masks_by_id.get(item.area_mask_id) if item.area_mask_id else None
                ),
            )
            for item in items
        ],
    )


@router.get(
    "/documents/{document_id}/redaction-runs/{run_id}/pages/{page_id}/findings/{finding_id}",
    response_model=RedactionFindingResponse,
)
def get_project_document_redaction_run_page_finding(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    finding_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionFindingResponse:
    try:
        finding = document_service.get_redaction_run_page_finding(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            finding_id=finding_id,
        )
        active_area_mask = (
            document_service.get_redaction_area_mask_by_id(
                current_user=current_user,
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                mask_id=finding.area_mask_id,
            )
            if finding.area_mask_id is not None
            else None
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
        event_type="REDACTION_FINDING_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_finding",
        object_id=finding.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": page_id,
            "finding_id": finding.id,
        },
        request_context=request_context,
    )
    return _as_redaction_finding_response(
        finding,
        active_area_mask=active_area_mask,
    )


@router.patch(
    "/documents/{document_id}/redaction-runs/{run_id}/findings/{finding_id}",
    response_model=RedactionFindingResponse,
)
def patch_project_document_redaction_finding(
    project_id: str,
    document_id: str,
    run_id: str,
    finding_id: str,
    payload: PatchRedactionFindingRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionFindingResponse:
    active_area_mask: RedactionAreaMaskRecord | None = None
    try:
        finding = document_service.update_redaction_finding_decision(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            finding_id=finding_id,
            expected_decision_etag=payload.decision_etag,
            decision_status=payload.decision_status,
            reason=payload.reason,
            action_type=payload.action_type,
        )
        if finding.area_mask_id is not None:
            active_area_mask = document_service.get_redaction_area_mask_by_id(
                current_user=current_user,
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                mask_id=finding.area_mask_id,
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
        event_type="REDACTION_FINDING_DECISION_CHANGED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_finding",
        object_id=finding.id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": finding.page_id,
            "finding_id": finding.id,
            "decision_status": finding.decision_status,
            "decision_etag": finding.decision_etag,
        },
        request_context=request_context,
    )
    audit_service.record_event_best_effort(
        event_type="SAFEGUARDED_PREVIEW_REGENERATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=finding.page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": finding.page_id,
            "reason": "finding_decision_changed",
        },
            request_context=request_context,
        )
    return _as_redaction_finding_response(
        finding,
        active_area_mask=active_area_mask,
    )


@router.get(
    "/documents/{document_id}/redaction-runs/{run_id}/pages/{page_id}/review",
    response_model=RedactionPageReviewResponse,
)
def get_project_document_redaction_run_page_review(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionPageReviewResponse:
    try:
        review = document_service.get_redaction_run_page_review(
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
        event_type="REDACTION_PAGE_REVIEW_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": page_id,
            "review_status": review.review_status,
        },
        request_context=request_context,
    )
    return _as_redaction_page_review_response(review)


@router.patch(
    "/documents/{document_id}/redaction-runs/{run_id}/pages/{page_id}/review",
    response_model=RedactionPageReviewResponse,
)
def patch_project_document_redaction_page_review(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    payload: PatchRedactionPageReviewRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionPageReviewResponse:
    try:
        review = document_service.update_redaction_page_review(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            expected_review_etag=payload.review_etag,
            review_status=payload.review_status,
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
        event_type="REDACTION_PAGE_REVIEW_UPDATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": page_id,
            "review_status": review.review_status,
            "review_etag": review.review_etag,
        },
        request_context=request_context,
    )
    audit_service.record_event_best_effort(
        event_type="SAFEGUARDED_PREVIEW_REGENERATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": page_id,
            "reason": "page_review_updated",
        },
        request_context=request_context,
    )
    return _as_redaction_page_review_response(review)


@router.get(
    "/documents/{document_id}/redaction-runs/{run_id}/pages/{page_id}/events",
    response_model=RedactionRunEventsResponse,
)
def list_project_document_redaction_run_page_events(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunEventsResponse:
    try:
        items = document_service.list_redaction_run_page_events(
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
        event_type="REDACTION_PAGE_EVENTS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": page_id,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return RedactionRunEventsResponse(
        run_id=run_id,
        items=[_as_redaction_timeline_event_response(item) for item in items],
    )


@router.get(
    "/documents/{document_id}/redaction-runs/{run_id}/pages/{page_id}/preview-status",
    response_model=RedactionPreviewStatusResponse,
)
def get_project_document_redaction_page_preview_status(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionPreviewStatusResponse:
    try:
        snapshot = document_service.get_redaction_page_preview_status(
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
        event_type="SAFEGUARDED_PREVIEW_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": page_id,
            "status": snapshot.status,
        },
        request_context=request_context,
    )
    return _as_redaction_preview_status_response(snapshot)


@router.get("/documents/{document_id}/redaction-runs/{run_id}/pages/{page_id}/preview")
def read_project_document_redaction_page_preview(
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
        preview_asset = document_service.read_redaction_page_preview(
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

    etag = _format_etag(preview_asset.etag_seed)
    response_headers = {
        "Cache-Control": preview_asset.cache_control,
        "Cross-Origin-Resource-Policy": "same-origin",
        "Vary": PAGE_IMAGE_CACHE_VARY_HEADER,
        "X-Content-Type-Options": "nosniff",
    }
    if etag:
        response_headers["ETag"] = etag
    not_modified = _if_none_match_matches(request.headers.get("if-none-match"), etag)

    audit_service.record_event_best_effort(
        event_type="SAFEGUARDED_PREVIEW_ACCESSED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": page_id,
            "not_modified": not_modified,
        },
        request_context=request_context,
    )
    if not_modified:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers=response_headers,
        )

    audit_service.record_event_best_effort(
        event_type="SAFEGUARDED_PREVIEW_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": page_id,
            "media_type": preview_asset.media_type,
        },
        request_context=request_context,
    )
    return Response(
        content=preview_asset.payload,
        media_type=preview_asset.media_type,
        headers=response_headers,
    )


@router.get(
    "/documents/{document_id}/redaction-runs/{run_id}/output",
    response_model=RedactionRunOutputResponse,
)
def get_project_document_redaction_run_output(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunOutputResponse:
    try:
        output = document_service.get_redaction_run_output(
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
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_RUN_OUTPUT_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "status": output.run_output.status,
            "review_status": output.review_status,
            "readiness_state": output.readiness_state,
            "downstream_ready": output.downstream_ready,
        },
        request_context=request_context,
    )
    return _as_redaction_run_output_response(output)


@router.get(
    "/documents/{document_id}/redaction-runs/{run_id}/output/status",
    response_model=RedactionRunOutputResponse,
)
def get_project_document_redaction_run_output_status(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> RedactionRunOutputResponse:
    try:
        output = document_service.get_redaction_run_output_status(
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
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_RUN_OUTPUT_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "status": output.run_output.status,
            "review_status": output.review_status,
            "readiness_state": output.readiness_state,
            "downstream_ready": output.downstream_ready,
        },
        request_context=request_context,
    )
    return _as_redaction_run_output_response(output)


@router.get(
    "/documents/{document_id}/governance/overview",
    response_model=GovernanceOverviewResponse,
)
def get_project_document_governance_overview(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceOverviewResponse:
    try:
        overview = document_service.get_governance_overview(
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
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="GOVERNANCE_OVERVIEW_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "active_run_id": overview.active_run_id,
            "total_runs": overview.total_runs,
            "ready_runs": overview.ready_runs,
        },
        request_context=request_context,
    )
    return _as_governance_overview_response(overview)


@router.get(
    "/documents/{document_id}/governance/runs",
    response_model=GovernanceRunsResponse,
)
def list_project_document_governance_runs(
    project_id: str,
    document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceRunsResponse:
    try:
        snapshot = document_service.list_governance_runs(
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
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="GOVERNANCE_RUNS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="document",
        object_id=document_id,
        metadata={
            "route": request_context.route_template,
            "active_run_id": snapshot.active_run_id,
            "returned_count": len(snapshot.runs),
        },
        request_context=request_context,
    )
    return _as_governance_runs_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/overview",
    response_model=GovernanceRunOverviewResponse,
)
def get_project_document_governance_run_overview(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceRunOverviewResponse:
    try:
        snapshot = document_service.get_governance_run_overview(
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
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="GOVERNANCE_RUN_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "manifest_attempt_count": len(snapshot.manifest_attempts),
            "ledger_attempt_count": len(snapshot.ledger_attempts),
            "readiness_status": snapshot.readiness.status,
        },
        request_context=request_context,
    )
    return _as_governance_run_overview_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/events",
    response_model=GovernanceRunEventsResponse,
)
def list_project_document_governance_run_events(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceRunEventsResponse:
    try:
        items = document_service.list_governance_run_events(
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
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="GOVERNANCE_EVENTS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return _as_governance_events_response(run_id=run_id, items=items)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/manifest",
    response_model=GovernanceManifestResponse,
)
def get_project_document_governance_run_manifest(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceManifestResponse:
    try:
        snapshot = document_service.get_governance_run_manifest(
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
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_MANIFEST_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "latest_attempt_id": (
                snapshot.latest_attempt.id if snapshot.latest_attempt is not None else None
            ),
            "attempt_count": len(snapshot.overview.manifest_attempts),
            "readiness_status": snapshot.overview.readiness.status,
        },
        request_context=request_context,
    )
    return _as_governance_manifest_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/manifest/status",
    response_model=GovernanceManifestStatusResponse,
)
def get_project_document_governance_run_manifest_status(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceManifestStatusResponse:
    try:
        snapshot = document_service.get_governance_run_manifest_status(
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
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_MANIFEST_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "status": snapshot.status,
            "attempt_count": snapshot.attempt_count,
            "readiness_status": snapshot.readiness_status,
        },
        request_context=request_context,
    )
    return _as_governance_manifest_status_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/manifest/entries",
    response_model=GovernanceManifestEntriesResponse,
)
def list_project_document_governance_run_manifest_entries(
    project_id: str,
    document_id: str,
    run_id: str,
    category: str | None = Query(default=None),
    page: int | None = Query(default=None, ge=1),
    review_state: str | None = Query(default=None, alias="reviewState"),
    from_raw: str | None = Query(default=None, alias="from"),
    to_raw: str | None = Query(default=None, alias="to"),
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceManifestEntriesResponse:
    from_timestamp = _parse_datetime_filter(from_raw, param_name="from")
    to_timestamp = _parse_datetime_filter(to_raw, param_name="to", upper_bound=True)
    if (
        isinstance(from_timestamp, datetime)
        and isinstance(to_timestamp, datetime)
        and from_timestamp > to_timestamp
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="'from' must be less than or equal to 'to'.",
        )
    try:
        snapshot = document_service.list_governance_run_manifest_entries(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            category=category,
            page=page,
            review_state=review_state,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            cursor=cursor,
            limit=limit,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_MANIFEST_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "status": snapshot.status,
            "category_filter": category,
            "page_filter": page,
            "review_state_filter": review_state,
            "from_filter": from_timestamp.isoformat() if from_timestamp else None,
            "to_filter": to_timestamp.isoformat() if to_timestamp else None,
            "cursor": cursor,
            "limit": limit,
            "returned_count": len(snapshot.items),
            "total_count": snapshot.total_count,
        },
        request_context=request_context,
    )
    return _as_governance_manifest_entries_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/manifest/hash",
    response_model=GovernanceManifestHashResponse,
)
def get_project_document_governance_run_manifest_hash(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceManifestHashResponse:
    try:
        snapshot = document_service.get_governance_run_manifest_hash(
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
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_MANIFEST_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "status": snapshot.status,
            "manifest_id": snapshot.manifest_id,
            "hash_matches": snapshot.hash_matches,
        },
        request_context=request_context,
    )
    return _as_governance_manifest_hash_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/ledger",
    response_model=GovernanceLedgerResponse,
)
def get_project_document_governance_run_ledger(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceLedgerResponse:
    try:
        snapshot = document_service.get_governance_run_ledger(
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
            required_roles=["ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_LEDGER_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "latest_attempt_id": (
                snapshot.latest_attempt.id if snapshot.latest_attempt is not None else None
            ),
            "attempt_count": len(snapshot.overview.ledger_attempts),
            "readiness_status": snapshot.overview.readiness.status,
            "ledger_verification_status": snapshot.overview.readiness.ledger_verification_status,
        },
        request_context=request_context,
    )
    return _as_governance_ledger_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/ledger/status",
    response_model=GovernanceLedgerStatusResponse,
)
def get_project_document_governance_run_ledger_status(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceLedgerStatusResponse:
    try:
        snapshot = document_service.get_governance_run_ledger_status(
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
            required_roles=["ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_LEDGER_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "status": snapshot.status,
            "attempt_count": snapshot.attempt_count,
            "readiness_status": snapshot.readiness_status,
            "ledger_verification_status": snapshot.ledger_verification_status,
        },
        request_context=request_context,
    )
    return _as_governance_ledger_status_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/ledger/entries",
    response_model=GovernanceLedgerEntriesResponse,
)
def list_project_document_governance_run_ledger_entries(
    project_id: str,
    document_id: str,
    run_id: str,
    view: GovernanceLedgerEntriesViewLiteral = Query(default="list"),
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceLedgerEntriesResponse:
    try:
        snapshot = document_service.list_governance_run_ledger_entries(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            view=view,
            cursor=cursor,
            limit=limit,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_LEDGER_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "status": snapshot.status,
            "attempt_count": snapshot.total_count,
            "view": snapshot.view,
            "cursor": cursor,
            "limit": limit,
            "returned_count": len(snapshot.items),
            "readiness_status": snapshot.verification_status,
            "ledger_verification_status": snapshot.verification_status,
        },
        request_context=request_context,
    )
    return _as_governance_ledger_entries_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/ledger/summary",
    response_model=GovernanceLedgerSummaryResponse,
)
def get_project_document_governance_run_ledger_summary(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceLedgerSummaryResponse:
    try:
        snapshot = document_service.get_governance_run_ledger_summary(
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
            required_roles=["ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_LEDGER_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "status": snapshot.status,
            "attempt_count": snapshot.row_count,
            "readiness_status": snapshot.verification_status,
            "ledger_verification_status": snapshot.verification_status,
        },
        request_context=request_context,
    )
    return _as_governance_ledger_summary_response(snapshot)


@router.post(
    "/documents/{document_id}/governance/runs/{run_id}/ledger/verify",
    response_model=GovernanceLedgerVerifyDetailResponse,
)
def post_project_document_governance_run_ledger_verify(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceLedgerVerifyDetailResponse:
    try:
        snapshot = document_service.request_governance_run_ledger_verification(
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
            required_roles=["ADMIN"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_LEDGER_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "verification_run_id": snapshot.attempt.id,
            "status": snapshot.attempt.status,
            "readiness_status": snapshot.verification_status,
            "ledger_verification_status": snapshot.verification_status,
        },
        request_context=request_context,
    )
    return _as_governance_ledger_verify_detail_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/ledger/verify/status",
    response_model=GovernanceLedgerVerifyStatusResponse,
)
def get_project_document_governance_run_ledger_verify_status(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceLedgerVerifyStatusResponse:
    try:
        snapshot = document_service.get_governance_run_ledger_verification_status(
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
            required_roles=["ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_LEDGER_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "status": snapshot.latest_attempt.status if snapshot.latest_attempt else "UNAVAILABLE",
            "attempt_count": snapshot.attempt_count,
            "readiness_status": snapshot.verification_status,
            "ledger_verification_status": snapshot.verification_status,
        },
        request_context=request_context,
    )
    return _as_governance_ledger_verify_status_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/ledger/verify/runs",
    response_model=GovernanceLedgerVerifyRunsResponse,
)
def list_project_document_governance_run_ledger_verify_runs(
    project_id: str,
    document_id: str,
    run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceLedgerVerifyRunsResponse:
    try:
        snapshot = document_service.list_governance_run_ledger_verification_runs(
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
            required_roles=["ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_LEDGER_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "status": snapshot.items[0].status if snapshot.items else "UNAVAILABLE",
            "attempt_count": len(snapshot.items),
            "readiness_status": snapshot.verification_status,
            "ledger_verification_status": snapshot.verification_status,
        },
        request_context=request_context,
    )
    return _as_governance_ledger_verify_runs_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/ledger/verify/{verification_run_id}",
    response_model=GovernanceLedgerVerifyDetailResponse,
)
def get_project_document_governance_run_ledger_verify_run(
    project_id: str,
    document_id: str,
    run_id: str,
    verification_run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceLedgerVerifyDetailResponse:
    try:
        snapshot = document_service.get_governance_run_ledger_verification_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            verification_run_id=verification_run_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["ADMIN", "AUDITOR"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_LEDGER_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "verification_run_id": verification_run_id,
            "status": snapshot.attempt.status,
            "readiness_status": snapshot.verification_status,
            "ledger_verification_status": snapshot.verification_status,
        },
        request_context=request_context,
    )
    return _as_governance_ledger_verify_detail_response(snapshot)


@router.get(
    "/documents/{document_id}/governance/runs/{run_id}/ledger/verify/{verification_run_id}/status",
    response_model=GovernanceLedgerVerifyDetailResponse,
)
def get_project_document_governance_run_ledger_verify_run_status(
    project_id: str,
    document_id: str,
    run_id: str,
    verification_run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceLedgerVerifyDetailResponse:
    return get_project_document_governance_run_ledger_verify_run(
        project_id=project_id,
        document_id=document_id,
        run_id=run_id,
        verification_run_id=verification_run_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        document_service=document_service,
    )


@router.post(
    "/documents/{document_id}/governance/runs/{run_id}/ledger/verify/{verification_run_id}/cancel",
    response_model=GovernanceLedgerVerifyDetailResponse,
)
def post_project_document_governance_run_ledger_verify_run_cancel(
    project_id: str,
    document_id: str,
    run_id: str,
    verification_run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> GovernanceLedgerVerifyDetailResponse:
    try:
        snapshot = document_service.cancel_governance_run_ledger_verification_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            verification_run_id=verification_run_id,
        )
    except Exception as error:  # noqa: BLE001
        _raise_http_from_error(
            error=error,
            current_user=current_user,
            project_id=project_id,
            audit_service=audit_service,
            request_context=request_context,
            required_roles=["ADMIN"],
        )
    audit_service.record_event_best_effort(
        event_type="REDACTION_LEDGER_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_run",
        object_id=run_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "verification_run_id": verification_run_id,
            "status": snapshot.attempt.status,
            "readiness_status": snapshot.verification_status,
            "ledger_verification_status": snapshot.verification_status,
        },
        request_context=request_context,
    )
    return _as_governance_ledger_verify_detail_response(snapshot)


@router.post(
    "/documents/{document_id}/redaction-runs/{run_id}/pages/{page_id}/area-masks",
    response_model=PatchRedactionAreaMaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_document_redaction_area_mask(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    payload: CreateRedactionAreaMaskRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PatchRedactionAreaMaskResponse:
    try:
        area_mask, finding = document_service.create_redaction_area_mask(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            geometry_json=payload.geometry_json,
            mask_reason=payload.mask_reason,
            finding_id=payload.finding_id,
            expected_finding_decision_etag=payload.finding_decision_etag,
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

    if finding is not None:
        audit_service.record_event_best_effort(
            event_type="REDACTION_FINDING_DECISION_CHANGED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="redaction_finding",
            object_id=finding.id,
            metadata={
                "route": request_context.route_template,
                "run_id": run_id,
                "page_id": finding.page_id,
                "finding_id": finding.id,
                "decision_status": finding.decision_status,
                "decision_etag": finding.decision_etag,
            },
            request_context=request_context,
        )
    audit_service.record_event_best_effort(
        event_type="SAFEGUARDED_PREVIEW_REGENERATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=area_mask.page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": area_mask.page_id,
            "reason": "area_mask_created",
        },
        request_context=request_context,
    )
    return PatchRedactionAreaMaskResponse(
        area_mask=_as_redaction_area_mask_response(area_mask),
        finding=(
            _as_redaction_finding_response(
                finding,
                active_area_mask=area_mask,
            )
            if finding is not None
            else None
        ),
    )


@router.patch(
    "/documents/{document_id}/redaction-runs/{run_id}/area-masks/{mask_id}",
    response_model=PatchRedactionAreaMaskResponse,
)
def patch_project_document_redaction_area_mask(
    project_id: str,
    document_id: str,
    run_id: str,
    mask_id: str,
    payload: PatchRedactionAreaMaskRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PatchRedactionAreaMaskResponse:
    try:
        area_mask, finding = document_service.revise_redaction_area_mask_by_id(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            mask_id=mask_id,
            expected_version_etag=payload.version_etag,
            geometry_json=payload.geometry_json,
            mask_reason=payload.mask_reason,
            finding_id=payload.finding_id,
            expected_finding_decision_etag=payload.finding_decision_etag,
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

    if finding is not None:
        audit_service.record_event_best_effort(
            event_type="REDACTION_FINDING_DECISION_CHANGED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="redaction_finding",
            object_id=finding.id,
            metadata={
                "route": request_context.route_template,
                "run_id": run_id,
                "page_id": finding.page_id,
                "finding_id": finding.id,
                "decision_status": finding.decision_status,
                "decision_etag": finding.decision_etag,
            },
            request_context=request_context,
        )
    audit_service.record_event_best_effort(
        event_type="SAFEGUARDED_PREVIEW_REGENERATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=area_mask.page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": area_mask.page_id,
            "reason": "area_mask_revised",
        },
        request_context=request_context,
    )
    return PatchRedactionAreaMaskResponse(
        area_mask=_as_redaction_area_mask_response(area_mask),
        finding=(
            _as_redaction_finding_response(
                finding,
                active_area_mask=area_mask,
            )
            if finding is not None
            else None
        ),
    )


@router.patch(
    "/documents/{document_id}/redaction-runs/{run_id}/pages/{page_id}/area-masks/{mask_id}",
    response_model=PatchRedactionAreaMaskResponse,
)
def patch_project_document_redaction_area_mask_page_scoped(
    project_id: str,
    document_id: str,
    run_id: str,
    page_id: str,
    mask_id: str,
    payload: PatchRedactionAreaMaskRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> PatchRedactionAreaMaskResponse:
    try:
        area_mask, finding = document_service.revise_redaction_area_mask(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
            mask_id=mask_id,
            expected_version_etag=payload.version_etag,
            geometry_json=payload.geometry_json,
            mask_reason=payload.mask_reason,
            finding_id=payload.finding_id,
            expected_finding_decision_etag=payload.finding_decision_etag,
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

    if finding is not None:
        audit_service.record_event_best_effort(
            event_type="REDACTION_FINDING_DECISION_CHANGED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="redaction_finding",
            object_id=finding.id,
            metadata={
                "route": request_context.route_template,
                "run_id": run_id,
                "page_id": finding.page_id,
                "finding_id": finding.id,
                "decision_status": finding.decision_status,
                "decision_etag": finding.decision_etag,
            },
            request_context=request_context,
        )
    audit_service.record_event_best_effort(
        event_type="SAFEGUARDED_PREVIEW_REGENERATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="page",
        object_id=page_id,
        metadata={
            "route": request_context.route_template,
            "run_id": run_id,
            "page_id": page_id,
            "reason": "area_mask_revised",
        },
        request_context=request_context,
    )
    return PatchRedactionAreaMaskResponse(
        area_mask=_as_redaction_area_mask_response(area_mask),
        finding=(
            _as_redaction_finding_response(
                finding,
                active_area_mask=area_mask,
            )
            if finding is not None
            else None
        ),
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
