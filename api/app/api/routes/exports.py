from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import (
    require_authenticated_user,
    require_internal_export_gateway_service_account,
)
from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.exports.models import (
    BundleEventRecord,
    BundleProfileRecord,
    BundleValidationProjectionRecord,
    BundleValidationRunRecord,
    BundleVerificationProjectionRecord,
    BundleVerificationRunRecord,
    DepositBundleRecord,
    ExportCandidateSnapshotRecord,
    ExportReceiptRecord,
    ProvenanceProofRecord,
    ExportRequestEventRecord,
    ExportRequestRecord,
    ExportRequestReviewEventRecord,
    ExportRequestReviewRecord,
    ExportReviewQueueItemRecord,
)
from app.exports.service import (
    ExportAccessDeniedError,
    ExportConflictError,
    ExportNotFoundError,
    ExportService,
    ExportValidationError,
    get_export_service,
)
from app.exports.store import ExportStoreUnavailableError
from app.projects.service import ProjectAccessDeniedError
from app.projects.store import ProjectNotFoundError

router = APIRouter(
    prefix="/projects/{project_id}",
    dependencies=[Depends(require_authenticated_user)],
)
internal_router = APIRouter(prefix="/internal")

ExportCandidateSourcePhaseLiteral = Literal["PHASE6", "PHASE7", "PHASE9", "PHASE10"]
ExportCandidateSourceArtifactKindLiteral = Literal[
    "REDACTION_RUN_OUTPUT",
    "DEPOSIT_BUNDLE",
    "DERIVATIVE_SNAPSHOT",
]
ExportCandidateKindLiteral = Literal[
    "SAFEGUARDED_PREVIEW",
    "POLICY_RERUN",
    "DEPOSIT_BUNDLE",
    "SAFEGUARDED_DERIVATIVE",
]
ExportCandidateEligibilityStatusLiteral = Literal["ELIGIBLE", "SUPERSEDED"]
ExportRequestRiskClassificationLiteral = Literal["STANDARD", "HIGH"]
ExportRequestReviewPathLiteral = Literal["SINGLE", "DUAL"]
ExportRequestStatusLiteral = Literal[
    "SUBMITTED",
    "RESUBMITTED",
    "IN_REVIEW",
    "APPROVED",
    "EXPORTED",
    "REJECTED",
    "RETURNED",
]
ExportRequestEventTypeLiteral = Literal[
    "REQUEST_SUBMITTED",
    "REQUEST_REVIEW_STARTED",
    "REQUEST_RESUBMITTED",
    "REQUEST_APPROVED",
    "REQUEST_EXPORTED",
    "REQUEST_REJECTED",
    "REQUEST_RETURNED",
    "REQUEST_RECEIPT_ATTACHED",
    "REQUEST_REMINDER_SENT",
    "REQUEST_ESCALATED",
]
ExportRequestReviewStageLiteral = Literal["PRIMARY", "SECONDARY"]
ExportRequestReviewStatusLiteral = Literal[
    "PENDING",
    "IN_REVIEW",
    "APPROVED",
    "RETURNED",
    "REJECTED",
]
ExportRequestReviewEventTypeLiteral = Literal[
    "REVIEW_CREATED",
    "REVIEW_CLAIMED",
    "REVIEW_STARTED",
    "REVIEW_APPROVED",
    "REVIEW_REJECTED",
    "REVIEW_RETURNED",
    "REVIEW_RELEASED",
]
ExportRequestDecisionLiteral = Literal["APPROVE", "REJECT", "RETURN"]
ExportReviewAgingBucketLiteral = Literal[
    "UNSTARTED",
    "NO_SLA",
    "ON_TRACK",
    "DUE_SOON",
    "OVERDUE",
]
DepositBundleKindLiteral = Literal["CONTROLLED_EVIDENCE", "SAFEGUARDED_DEPOSIT"]
DepositBundleStatusLiteral = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
BundleEventTypeLiteral = Literal[
    "BUNDLE_BUILD_QUEUED",
    "BUNDLE_REBUILD_REQUESTED",
    "BUNDLE_BUILD_STARTED",
    "BUNDLE_BUILD_SUCCEEDED",
    "BUNDLE_BUILD_FAILED",
    "BUNDLE_BUILD_CANCELED",
    "BUNDLE_VERIFICATION_STARTED",
    "BUNDLE_VERIFICATION_SUCCEEDED",
    "BUNDLE_VERIFICATION_FAILED",
    "BUNDLE_VERIFICATION_CANCELED",
    "BUNDLE_VALIDATION_STARTED",
    "BUNDLE_VALIDATION_SUCCEEDED",
    "BUNDLE_VALIDATION_FAILED",
    "BUNDLE_VALIDATION_CANCELED",
]
BundleVerificationProjectionStatusLiteral = Literal["PENDING", "VERIFIED", "FAILED"]
BundleVerificationRunStatusLiteral = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
]
BundleValidationProjectionStatusLiteral = Literal["PENDING", "READY", "FAILED"]
BundleValidationRunStatusLiteral = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
]


class ExportCandidateResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    source_phase: ExportCandidateSourcePhaseLiteral = Field(serialization_alias="sourcePhase")
    source_artifact_kind: ExportCandidateSourceArtifactKindLiteral = Field(
        serialization_alias="sourceArtifactKind"
    )
    source_run_id: str | None = Field(default=None, serialization_alias="sourceRunId")
    source_artifact_id: str = Field(serialization_alias="sourceArtifactId")
    governance_run_id: str | None = Field(default=None, serialization_alias="governanceRunId")
    governance_manifest_id: str | None = Field(
        default=None,
        serialization_alias="governanceManifestId",
    )
    governance_ledger_id: str | None = Field(default=None, serialization_alias="governanceLedgerId")
    governance_manifest_sha256: str | None = Field(
        default=None,
        serialization_alias="governanceManifestSha256",
    )
    governance_ledger_sha256: str | None = Field(
        default=None,
        serialization_alias="governanceLedgerSha256",
    )
    policy_snapshot_hash: str | None = Field(default=None, serialization_alias="policySnapshotHash")
    policy_id: str | None = Field(default=None, serialization_alias="policyId")
    policy_family_id: str | None = Field(default=None, serialization_alias="policyFamilyId")
    policy_version: str | None = Field(default=None, serialization_alias="policyVersion")
    candidate_kind: ExportCandidateKindLiteral = Field(serialization_alias="candidateKind")
    artefact_manifest_json: dict[str, object] = Field(serialization_alias="artefactManifestJson")
    candidate_sha256: str = Field(serialization_alias="candidateSha256")
    eligibility_status: ExportCandidateEligibilityStatusLiteral = Field(
        serialization_alias="eligibilityStatus"
    )
    supersedes_candidate_snapshot_id: str | None = Field(
        default=None,
        serialization_alias="supersedesCandidateSnapshotId",
    )
    superseded_by_candidate_snapshot_id: str | None = Field(
        default=None,
        serialization_alias="supersededByCandidateSnapshotId",
    )
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")


class ExportCandidateListResponse(BaseModel):
    items: list[ExportCandidateResponse]


class ExportReleasePackPreviewResponse(BaseModel):
    candidate: ExportCandidateResponse
    release_pack: dict[str, object] = Field(serialization_alias="releasePack")
    release_pack_sha256: str = Field(serialization_alias="releasePackSha256")
    release_pack_key: str = Field(serialization_alias="releasePackKey")
    risk_classification: ExportRequestRiskClassificationLiteral = Field(
        serialization_alias="riskClassification"
    )
    risk_reason_codes: list[str] = Field(serialization_alias="riskReasonCodes")
    review_path: ExportRequestReviewPathLiteral = Field(serialization_alias="reviewPath")
    requires_second_review: bool = Field(serialization_alias="requiresSecondReview")


class CreateExportRequestRequest(BaseModel):
    candidate_snapshot_id: str = Field(
        alias="candidateSnapshotId",
        serialization_alias="candidateSnapshotId",
    )
    purpose_statement: str = Field(alias="purposeStatement", serialization_alias="purposeStatement")
    bundle_profile: str | None = Field(
        default=None,
        alias="bundleProfile",
        serialization_alias="bundleProfile",
    )


class ResubmitExportRequestRequest(BaseModel):
    candidate_snapshot_id: str | None = Field(
        default=None,
        alias="candidateSnapshotId",
        serialization_alias="candidateSnapshotId",
    )
    purpose_statement: str | None = Field(
        default=None,
        alias="purposeStatement",
        serialization_alias="purposeStatement",
    )
    bundle_profile: str | None = Field(
        default=None,
        alias="bundleProfile",
        serialization_alias="bundleProfile",
    )


class ExportRequestResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    candidate_snapshot_id: str = Field(serialization_alias="candidateSnapshotId")
    candidate_origin_phase: ExportCandidateSourcePhaseLiteral = Field(
        serialization_alias="candidateOriginPhase"
    )
    candidate_kind: ExportCandidateKindLiteral = Field(serialization_alias="candidateKind")
    bundle_profile: str | None = Field(default=None, serialization_alias="bundleProfile")
    risk_classification: ExportRequestRiskClassificationLiteral = Field(
        serialization_alias="riskClassification"
    )
    risk_reason_codes_json: list[str] = Field(serialization_alias="riskReasonCodesJson")
    review_path: ExportRequestReviewPathLiteral = Field(serialization_alias="reviewPath")
    requires_second_review: bool = Field(serialization_alias="requiresSecondReview")
    supersedes_export_request_id: str | None = Field(
        default=None,
        serialization_alias="supersedesExportRequestId",
    )
    superseded_by_export_request_id: str | None = Field(
        default=None,
        serialization_alias="supersededByExportRequestId",
    )
    request_revision: int = Field(serialization_alias="requestRevision")
    purpose_statement: str = Field(serialization_alias="purposeStatement")
    status: ExportRequestStatusLiteral
    submitted_by: str = Field(serialization_alias="submittedBy")
    submitted_at: datetime = Field(serialization_alias="submittedAt")
    first_review_started_by: str | None = Field(
        default=None,
        serialization_alias="firstReviewStartedBy",
    )
    first_review_started_at: datetime | None = Field(
        default=None,
        serialization_alias="firstReviewStartedAt",
    )
    sla_due_at: datetime | None = Field(default=None, serialization_alias="slaDueAt")
    last_queue_activity_at: datetime | None = Field(
        default=None,
        serialization_alias="lastQueueActivityAt",
    )
    retention_until: datetime | None = Field(default=None, serialization_alias="retentionUntil")
    final_review_id: str | None = Field(default=None, serialization_alias="finalReviewId")
    final_decision_by: str | None = Field(default=None, serialization_alias="finalDecisionBy")
    final_decision_at: datetime | None = Field(default=None, serialization_alias="finalDecisionAt")
    final_decision_reason: str | None = Field(
        default=None,
        serialization_alias="finalDecisionReason",
    )
    final_return_comment: str | None = Field(
        default=None,
        serialization_alias="finalReturnComment",
    )
    release_pack_key: str = Field(serialization_alias="releasePackKey")
    release_pack_sha256: str = Field(serialization_alias="releasePackSha256")
    release_pack_json: dict[str, object] = Field(serialization_alias="releasePackJson")
    release_pack_created_at: datetime = Field(serialization_alias="releasePackCreatedAt")
    receipt_id: str | None = Field(default=None, serialization_alias="receiptId")
    receipt_key: str | None = Field(default=None, serialization_alias="receiptKey")
    receipt_sha256: str | None = Field(default=None, serialization_alias="receiptSha256")
    receipt_created_by: str | None = Field(default=None, serialization_alias="receiptCreatedBy")
    receipt_created_at: datetime | None = Field(
        default=None,
        serialization_alias="receiptCreatedAt",
    )
    exported_at: datetime | None = Field(default=None, serialization_alias="exportedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class ExportRequestListResponse(BaseModel):
    items: list[ExportRequestResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class ExportRequestStatusResponse(BaseModel):
    id: str
    status: ExportRequestStatusLiteral
    risk_classification: ExportRequestRiskClassificationLiteral = Field(
        serialization_alias="riskClassification"
    )
    review_path: ExportRequestReviewPathLiteral = Field(serialization_alias="reviewPath")
    requires_second_review: bool = Field(serialization_alias="requiresSecondReview")
    request_revision: int = Field(serialization_alias="requestRevision")
    submitted_at: datetime = Field(serialization_alias="submittedAt")
    last_queue_activity_at: datetime | None = Field(
        default=None,
        serialization_alias="lastQueueActivityAt",
    )
    sla_due_at: datetime | None = Field(default=None, serialization_alias="slaDueAt")
    retention_until: datetime | None = Field(default=None, serialization_alias="retentionUntil")
    final_decision_at: datetime | None = Field(default=None, serialization_alias="finalDecisionAt")
    final_decision_by: str | None = Field(default=None, serialization_alias="finalDecisionBy")
    final_decision_reason: str | None = Field(
        default=None,
        serialization_alias="finalDecisionReason",
    )
    final_return_comment: str | None = Field(
        default=None,
        serialization_alias="finalReturnComment",
    )
    exported_at: datetime | None = Field(default=None, serialization_alias="exportedAt")


class ExportRequestReleasePackResponse(BaseModel):
    request_id: str = Field(serialization_alias="requestId")
    request_revision: int = Field(serialization_alias="requestRevision")
    release_pack: dict[str, object] = Field(serialization_alias="releasePack")
    release_pack_sha256: str = Field(serialization_alias="releasePackSha256")
    release_pack_key: str = Field(serialization_alias="releasePackKey")
    release_pack_created_at: datetime = Field(serialization_alias="releasePackCreatedAt")


class ExportValidationIssueResponse(BaseModel):
    code: str
    detail: str
    field: str | None = None
    expected: str | None = None
    actual: str | None = None
    blocking: bool


class ExportValidationCheckResponse(BaseModel):
    check_id: str = Field(serialization_alias="checkId")
    passed: bool
    issue_count: int = Field(serialization_alias="issueCount")
    issues: list[ExportValidationIssueResponse]
    facts: dict[str, object]


class ExportRequestValidationSummaryResponse(BaseModel):
    request_id: str = Field(serialization_alias="requestId")
    project_id: str = Field(serialization_alias="projectId")
    request_status: ExportRequestStatusLiteral = Field(serialization_alias="requestStatus")
    request_revision: int = Field(serialization_alias="requestRevision")
    generated_at: datetime = Field(serialization_alias="generatedAt")
    is_valid: bool = Field(serialization_alias="isValid")
    release_pack: ExportValidationCheckResponse = Field(serialization_alias="releasePack")
    audit_completeness: ExportValidationCheckResponse = Field(
        serialization_alias="auditCompleteness"
    )


class ExportRequestEventResponse(BaseModel):
    id: str
    export_request_id: str = Field(serialization_alias="exportRequestId")
    event_type: ExportRequestEventTypeLiteral = Field(serialization_alias="eventType")
    from_status: ExportRequestStatusLiteral | None = Field(
        default=None,
        serialization_alias="fromStatus",
    )
    to_status: ExportRequestStatusLiteral = Field(serialization_alias="toStatus")
    actor_user_id: str | None = Field(default=None, serialization_alias="actorUserId")
    reason: str | None = None
    created_at: datetime = Field(serialization_alias="createdAt")


class ExportRequestEventsResponse(BaseModel):
    items: list[ExportRequestEventResponse]


class ExportRequestReviewResponse(BaseModel):
    id: str
    export_request_id: str = Field(serialization_alias="exportRequestId")
    review_stage: ExportRequestReviewStageLiteral = Field(serialization_alias="reviewStage")
    is_required: bool = Field(serialization_alias="isRequired")
    status: ExportRequestReviewStatusLiteral
    assigned_reviewer_user_id: str | None = Field(
        default=None,
        serialization_alias="assignedReviewerUserId",
    )
    assigned_at: datetime | None = Field(default=None, serialization_alias="assignedAt")
    acted_by_user_id: str | None = Field(default=None, serialization_alias="actedByUserId")
    acted_at: datetime | None = Field(default=None, serialization_alias="actedAt")
    decision_reason: str | None = Field(default=None, serialization_alias="decisionReason")
    return_comment: str | None = Field(default=None, serialization_alias="returnComment")
    review_etag: str = Field(serialization_alias="reviewEtag")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class ExportRequestReviewsResponse(BaseModel):
    items: list[ExportRequestReviewResponse]


class ExportRequestReviewEventResponse(BaseModel):
    id: str
    review_id: str = Field(serialization_alias="reviewId")
    export_request_id: str = Field(serialization_alias="exportRequestId")
    review_stage: ExportRequestReviewStageLiteral = Field(serialization_alias="reviewStage")
    event_type: ExportRequestReviewEventTypeLiteral = Field(serialization_alias="eventType")
    actor_user_id: str | None = Field(default=None, serialization_alias="actorUserId")
    assigned_reviewer_user_id: str | None = Field(
        default=None,
        serialization_alias="assignedReviewerUserId",
    )
    decision_reason: str | None = Field(default=None, serialization_alias="decisionReason")
    return_comment: str | None = Field(default=None, serialization_alias="returnComment")
    created_at: datetime = Field(serialization_alias="createdAt")


class ExportRequestReviewEventsResponse(BaseModel):
    items: list[ExportRequestReviewEventResponse]


class ExportReviewQueueItemResponse(BaseModel):
    request: ExportRequestResponse
    reviews: list[ExportRequestReviewResponse]
    active_review_id: str | None = Field(default=None, serialization_alias="activeReviewId")
    active_review_stage: ExportRequestReviewStageLiteral | None = Field(
        default=None,
        serialization_alias="activeReviewStage",
    )
    active_review_status: ExportRequestReviewStatusLiteral | None = Field(
        default=None,
        serialization_alias="activeReviewStatus",
    )
    active_review_assigned_reviewer_user_id: str | None = Field(
        default=None,
        serialization_alias="activeReviewAssignedReviewerUserId",
    )
    aging_bucket: ExportReviewAgingBucketLiteral = Field(serialization_alias="agingBucket")
    sla_seconds_remaining: int | None = Field(
        default=None,
        serialization_alias="slaSecondsRemaining",
    )
    is_sla_breached: bool = Field(serialization_alias="isSlaBreached")


class ExportReviewQueueResponse(BaseModel):
    items: list[ExportReviewQueueItemResponse]
    read_only: bool = Field(serialization_alias="readOnly")


class ExportReviewEtagRequest(BaseModel):
    review_etag: str = Field(alias="reviewEtag", serialization_alias="reviewEtag")


class ExportStartReviewRequest(BaseModel):
    review_id: str = Field(alias="reviewId", serialization_alias="reviewId")
    review_etag: str = Field(alias="reviewEtag", serialization_alias="reviewEtag")


class ExportDecisionRequest(BaseModel):
    review_id: str = Field(alias="reviewId", serialization_alias="reviewId")
    review_etag: str = Field(alias="reviewEtag", serialization_alias="reviewEtag")
    decision: ExportRequestDecisionLiteral
    decision_reason: str | None = Field(
        default=None,
        alias="decisionReason",
        serialization_alias="decisionReason",
    )
    return_comment: str | None = Field(
        default=None,
        alias="returnComment",
        serialization_alias="returnComment",
    )


class ExportReceiptResponse(BaseModel):
    id: str
    export_request_id: str = Field(serialization_alias="exportRequestId")
    attempt_number: int = Field(serialization_alias="attemptNumber")
    supersedes_receipt_id: str | None = Field(
        default=None,
        serialization_alias="supersedesReceiptId",
    )
    superseded_by_receipt_id: str | None = Field(
        default=None,
        serialization_alias="supersededByReceiptId",
    )
    receipt_key: str = Field(serialization_alias="receiptKey")
    receipt_sha256: str = Field(serialization_alias="receiptSha256")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    exported_at: datetime = Field(serialization_alias="exportedAt")


class ExportReceiptListResponse(BaseModel):
    items: list[ExportReceiptResponse]


class AttachExportReceiptRequest(BaseModel):
    receipt_key: str = Field(alias="receiptKey", serialization_alias="receiptKey")
    receipt_sha256: str = Field(alias="receiptSha256", serialization_alias="receiptSha256")
    exported_at: datetime = Field(alias="exportedAt", serialization_alias="exportedAt")


class AttachExportReceiptResponse(BaseModel):
    request: ExportRequestResponse
    receipt: ExportReceiptResponse


class ExportReviewActionResponse(BaseModel):
    request: ExportRequestResponse
    review: ExportRequestReviewResponse


class ExportDeferredResponse(BaseModel):
    status: Literal["DEFERRED"] = "DEFERRED"
    code: str = "EXPORT_WORKFLOW_DEFERRED_TO_LATER_PROMPTS"
    detail: str
    route: str
    method: str


class ProvenanceLineageNodeResponse(BaseModel):
    artifact_kind: str = Field(serialization_alias="artifactKind")
    stable_identifier: str = Field(serialization_alias="stableIdentifier")
    immutable_reference: str = Field(serialization_alias="immutableReference")
    parent_references: list[str] = Field(serialization_alias="parentReferences")


class ExportRequestProvenanceSummaryResponse(BaseModel):
    project_id: str = Field(serialization_alias="projectId")
    request_id: str = Field(serialization_alias="requestId")
    request_status: ExportRequestStatusLiteral = Field(serialization_alias="requestStatus")
    candidate_snapshot_id: str = Field(serialization_alias="candidateSnapshotId")
    proof_attempt_count: int = Field(serialization_alias="proofAttemptCount")
    current_proof_id: str | None = Field(default=None, serialization_alias="currentProofId")
    current_attempt_number: int | None = Field(
        default=None,
        serialization_alias="currentAttemptNumber",
    )
    current_proof_generated_at: str | None = Field(
        default=None,
        serialization_alias="currentProofGeneratedAt",
    )
    root_sha256: str | None = Field(default=None, serialization_alias="rootSha256")
    signature_key_ref: str | None = Field(default=None, serialization_alias="signatureKeyRef")
    signature_status: Literal["SIGNED", "MISSING"] = Field(serialization_alias="signatureStatus")
    lineage_nodes: list[ProvenanceLineageNodeResponse] = Field(
        serialization_alias="lineageNodes"
    )
    references: dict[str, object]


class ProvenanceProofResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    export_request_id: str = Field(serialization_alias="exportRequestId")
    candidate_snapshot_id: str = Field(serialization_alias="candidateSnapshotId")
    attempt_number: int = Field(serialization_alias="attemptNumber")
    supersedes_proof_id: str | None = Field(
        default=None,
        serialization_alias="supersedesProofId",
    )
    superseded_by_proof_id: str | None = Field(
        default=None,
        serialization_alias="supersededByProofId",
    )
    root_sha256: str = Field(serialization_alias="rootSha256")
    signature_key_ref: str = Field(serialization_alias="signatureKeyRef")
    signature_bytes_key: str = Field(serialization_alias="signatureBytesKey")
    proof_artifact_key: str = Field(serialization_alias="proofArtifactKey")
    proof_artifact_sha256: str = Field(serialization_alias="proofArtifactSha256")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")


class ProvenanceProofListResponse(BaseModel):
    items: list[ProvenanceProofResponse]


class ProvenanceProofDetailResponse(BaseModel):
    proof: ProvenanceProofResponse
    artifact: dict[str, object]


class RegenerateProvenanceProofResponse(BaseModel):
    proof: ProvenanceProofResponse


class DepositBundleResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    export_request_id: str = Field(serialization_alias="exportRequestId")
    candidate_snapshot_id: str = Field(serialization_alias="candidateSnapshotId")
    provenance_proof_id: str = Field(serialization_alias="provenanceProofId")
    provenance_proof_artifact_sha256: str = Field(
        serialization_alias="provenanceProofArtifactSha256"
    )
    bundle_kind: DepositBundleKindLiteral = Field(serialization_alias="bundleKind")
    status: DepositBundleStatusLiteral
    attempt_number: int = Field(serialization_alias="attemptNumber")
    supersedes_bundle_id: str | None = Field(
        default=None,
        serialization_alias="supersedesBundleId",
    )
    superseded_by_bundle_id: str | None = Field(
        default=None,
        serialization_alias="supersededByBundleId",
    )
    bundle_key: str | None = Field(default=None, serialization_alias="bundleKey")
    bundle_sha256: str | None = Field(default=None, serialization_alias="bundleSha256")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")


class DepositBundleListResponse(BaseModel):
    items: list[DepositBundleResponse]


class BundleVerificationProjectionResponse(BaseModel):
    bundle_id: str = Field(serialization_alias="bundleId")
    status: BundleVerificationProjectionStatusLiteral
    last_verification_run_id: str | None = Field(
        default=None,
        serialization_alias="lastVerificationRunId",
    )
    verified_at: datetime | None = Field(default=None, serialization_alias="verifiedAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class BundleProfileResponse(BaseModel):
    id: str
    label: str
    description: str
    allowed_bundle_kinds: list[DepositBundleKindLiteral] = Field(
        serialization_alias="allowedBundleKinds"
    )
    required_archive_entries: list[str] = Field(serialization_alias="requiredArchiveEntries")
    required_metadata_paths: list[str] = Field(serialization_alias="requiredMetadataPaths")
    forbidden_metadata_paths: list[str] = Field(serialization_alias="forbiddenMetadataPaths")


class BundleProfilesResponse(BaseModel):
    items: list[BundleProfileResponse]


class BundleValidationProjectionResponse(BaseModel):
    bundle_id: str = Field(serialization_alias="bundleId")
    profile_id: str = Field(serialization_alias="profileId")
    status: BundleValidationProjectionStatusLiteral
    last_validation_run_id: str | None = Field(
        default=None,
        serialization_alias="lastValidationRunId",
    )
    ready_at: datetime | None = Field(default=None, serialization_alias="readyAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class DepositBundleDetailResponse(BaseModel):
    bundle: DepositBundleResponse
    lineage_attempts: list[DepositBundleResponse] = Field(
        serialization_alias="lineageAttempts"
    )
    verification_projection: BundleVerificationProjectionResponse | None = Field(
        default=None,
        serialization_alias="verificationProjection",
    )
    artifact: dict[str, object]


class DepositBundleStatusResponse(BaseModel):
    bundle: DepositBundleResponse
    verification_projection: BundleVerificationProjectionResponse | None = Field(
        default=None,
        serialization_alias="verificationProjection",
    )


class BundleEventResponse(BaseModel):
    id: str
    bundle_id: str = Field(serialization_alias="bundleId")
    event_type: BundleEventTypeLiteral = Field(serialization_alias="eventType")
    verification_run_id: str | None = Field(
        default=None,
        serialization_alias="verificationRunId",
    )
    validation_run_id: str | None = Field(default=None, serialization_alias="validationRunId")
    actor_user_id: str | None = Field(default=None, serialization_alias="actorUserId")
    reason: str | None = None
    created_at: datetime = Field(serialization_alias="createdAt")


class BundleEventsResponse(BaseModel):
    items: list[BundleEventResponse]


class BundleVerificationRunResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    bundle_id: str = Field(serialization_alias="bundleId")
    attempt_number: int = Field(serialization_alias="attemptNumber")
    supersedes_verification_run_id: str | None = Field(
        default=None,
        serialization_alias="supersedesVerificationRunId",
    )
    superseded_by_verification_run_id: str | None = Field(
        default=None,
        serialization_alias="supersededByVerificationRunId",
    )
    status: BundleVerificationRunStatusLiteral
    result_json: dict[str, object] = Field(serialization_alias="resultJson")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")


class BundleVerificationResponse(BaseModel):
    bundle: DepositBundleResponse
    verification_projection: BundleVerificationProjectionResponse | None = Field(
        default=None,
        serialization_alias="verificationProjection",
    )
    latest_attempt: BundleVerificationRunResponse | None = Field(
        default=None,
        serialization_alias="latestAttempt",
    )
    latest_completed_attempt: BundleVerificationRunResponse | None = Field(
        default=None,
        serialization_alias="latestCompletedAttempt",
    )


class BundleVerificationStatusResponse(BaseModel):
    bundle_id: str = Field(serialization_alias="bundleId")
    bundle_status: DepositBundleStatusLiteral = Field(serialization_alias="bundleStatus")
    verification_projection: BundleVerificationProjectionResponse | None = Field(
        default=None,
        serialization_alias="verificationProjection",
    )
    latest_attempt: BundleVerificationRunResponse | None = Field(
        default=None,
        serialization_alias="latestAttempt",
    )


class BundleVerificationRunsResponse(BaseModel):
    items: list[BundleVerificationRunResponse]


class BundleVerificationRunDetailResponse(BaseModel):
    verification_run: BundleVerificationRunResponse = Field(serialization_alias="verificationRun")


class BundleVerificationRunStatusResponse(BaseModel):
    verification_run: BundleVerificationRunResponse = Field(serialization_alias="verificationRun")


class BundleVerificationRunMutationResponse(BaseModel):
    verification_run: BundleVerificationRunResponse = Field(serialization_alias="verificationRun")


class BundleValidationRunResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    bundle_id: str = Field(serialization_alias="bundleId")
    profile_id: str = Field(serialization_alias="profileId")
    profile_snapshot_key: str = Field(serialization_alias="profileSnapshotKey")
    profile_snapshot_sha256: str = Field(serialization_alias="profileSnapshotSha256")
    status: BundleValidationRunStatusLiteral
    attempt_number: int = Field(serialization_alias="attemptNumber")
    supersedes_validation_run_id: str | None = Field(
        default=None,
        serialization_alias="supersedesValidationRunId",
    )
    superseded_by_validation_run_id: str | None = Field(
        default=None,
        serialization_alias="supersededByValidationRunId",
    )
    result_json: dict[str, object] = Field(serialization_alias="resultJson")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")


class BundleValidationStatusResponse(BaseModel):
    bundle_id: str = Field(serialization_alias="bundleId")
    bundle_status: DepositBundleStatusLiteral = Field(serialization_alias="bundleStatus")
    profile_id: str = Field(serialization_alias="profileId")
    verification_projection: BundleVerificationProjectionResponse | None = Field(
        default=None,
        serialization_alias="verificationProjection",
    )
    validation_projection: BundleValidationProjectionResponse | None = Field(
        default=None,
        serialization_alias="validationProjection",
    )
    latest_attempt: BundleValidationRunResponse | None = Field(
        default=None,
        serialization_alias="latestAttempt",
    )
    in_flight_attempt: BundleValidationRunResponse | None = Field(
        default=None,
        serialization_alias="inFlightAttempt",
    )
    last_successful_attempt: BundleValidationRunResponse | None = Field(
        default=None,
        serialization_alias="lastSuccessfulAttempt",
    )


class BundleValidationRunsResponse(BaseModel):
    items: list[BundleValidationRunResponse]


class BundleValidationRunDetailResponse(BaseModel):
    validation_run: BundleValidationRunResponse = Field(serialization_alias="validationRun")


class BundleValidationRunStatusResponse(BaseModel):
    validation_run: BundleValidationRunResponse = Field(serialization_alias="validationRun")


class BundleValidationRunMutationResponse(BaseModel):
    validation_run: BundleValidationRunResponse = Field(serialization_alias="validationRun")


class DepositBundleMutationResponse(BaseModel):
    bundle: DepositBundleResponse


def _as_candidate_response(record: ExportCandidateSnapshotRecord) -> ExportCandidateResponse:
    return ExportCandidateResponse(
        id=record.id,
        project_id=record.project_id,
        source_phase=record.source_phase,
        source_artifact_kind=record.source_artifact_kind,
        source_run_id=record.source_run_id,
        source_artifact_id=record.source_artifact_id,
        governance_run_id=record.governance_run_id,
        governance_manifest_id=record.governance_manifest_id,
        governance_ledger_id=record.governance_ledger_id,
        governance_manifest_sha256=record.governance_manifest_sha256,
        governance_ledger_sha256=record.governance_ledger_sha256,
        policy_snapshot_hash=record.policy_snapshot_hash,
        policy_id=record.policy_id,
        policy_family_id=record.policy_family_id,
        policy_version=record.policy_version,
        candidate_kind=record.candidate_kind,
        artefact_manifest_json=dict(record.artefact_manifest_json),
        candidate_sha256=record.candidate_sha256,
        eligibility_status=record.eligibility_status,
        supersedes_candidate_snapshot_id=record.supersedes_candidate_snapshot_id,
        superseded_by_candidate_snapshot_id=record.superseded_by_candidate_snapshot_id,
        created_by=record.created_by,
        created_at=record.created_at,
    )


def _as_request_response(record: ExportRequestRecord) -> ExportRequestResponse:
    return ExportRequestResponse(
        id=record.id,
        project_id=record.project_id,
        candidate_snapshot_id=record.candidate_snapshot_id,
        candidate_origin_phase=record.candidate_origin_phase,
        candidate_kind=record.candidate_kind,
        bundle_profile=record.bundle_profile,
        risk_classification=record.risk_classification,
        risk_reason_codes_json=list(record.risk_reason_codes_json),
        review_path=record.review_path,
        requires_second_review=record.requires_second_review,
        supersedes_export_request_id=record.supersedes_export_request_id,
        superseded_by_export_request_id=record.superseded_by_export_request_id,
        request_revision=record.request_revision,
        purpose_statement=record.purpose_statement,
        status=record.status,
        submitted_by=record.submitted_by,
        submitted_at=record.submitted_at,
        first_review_started_by=record.first_review_started_by,
        first_review_started_at=record.first_review_started_at,
        sla_due_at=record.sla_due_at,
        last_queue_activity_at=record.last_queue_activity_at,
        retention_until=record.retention_until,
        final_review_id=record.final_review_id,
        final_decision_by=record.final_decision_by,
        final_decision_at=record.final_decision_at,
        final_decision_reason=record.final_decision_reason,
        final_return_comment=record.final_return_comment,
        release_pack_key=record.release_pack_key,
        release_pack_sha256=record.release_pack_sha256,
        release_pack_json=dict(record.release_pack_json),
        release_pack_created_at=record.release_pack_created_at,
        receipt_id=record.receipt_id,
        receipt_key=_safe_storage_reference(record.receipt_key),
        receipt_sha256=record.receipt_sha256,
        receipt_created_by=record.receipt_created_by,
        receipt_created_at=record.receipt_created_at,
        exported_at=record.exported_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_event_response(record: ExportRequestEventRecord) -> ExportRequestEventResponse:
    return ExportRequestEventResponse(
        id=record.id,
        export_request_id=record.export_request_id,
        event_type=record.event_type,
        from_status=record.from_status,
        to_status=record.to_status,
        actor_user_id=record.actor_user_id,
        reason=record.reason,
        created_at=record.created_at,
    )


def _as_review_response(record: ExportRequestReviewRecord) -> ExportRequestReviewResponse:
    return ExportRequestReviewResponse(
        id=record.id,
        export_request_id=record.export_request_id,
        review_stage=record.review_stage,
        is_required=record.is_required,
        status=record.status,
        assigned_reviewer_user_id=record.assigned_reviewer_user_id,
        assigned_at=record.assigned_at,
        acted_by_user_id=record.acted_by_user_id,
        acted_at=record.acted_at,
        decision_reason=record.decision_reason,
        return_comment=record.return_comment,
        review_etag=record.review_etag,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_review_event_response(
    record: ExportRequestReviewEventRecord,
) -> ExportRequestReviewEventResponse:
    return ExportRequestReviewEventResponse(
        id=record.id,
        review_id=record.review_id,
        export_request_id=record.export_request_id,
        review_stage=record.review_stage,
        event_type=record.event_type,
        actor_user_id=record.actor_user_id,
        assigned_reviewer_user_id=record.assigned_reviewer_user_id,
        decision_reason=record.decision_reason,
        return_comment=record.return_comment,
        created_at=record.created_at,
    )


def _safe_storage_reference(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if "/" in normalized:
        return normalized.split("/")[-1] or None
    return normalized


def _as_receipt_response(record: ExportReceiptRecord) -> ExportReceiptResponse:
    return ExportReceiptResponse(
        id=record.id,
        export_request_id=record.export_request_id,
        attempt_number=record.attempt_number,
        supersedes_receipt_id=record.supersedes_receipt_id,
        superseded_by_receipt_id=record.superseded_by_receipt_id,
        receipt_key=_safe_storage_reference(record.receipt_key) or record.receipt_key,
        receipt_sha256=record.receipt_sha256,
        created_by=record.created_by,
        created_at=record.created_at,
        exported_at=record.exported_at,
    )


def _as_review_queue_item_response(
    item: ExportReviewQueueItemRecord,
) -> ExportReviewQueueItemResponse:
    return ExportReviewQueueItemResponse(
        request=_as_request_response(item.request),
        reviews=[_as_review_response(review) for review in item.reviews],
        active_review_id=item.active_review_id,
        active_review_stage=item.active_review_stage,
        active_review_status=item.active_review_status,
        active_review_assigned_reviewer_user_id=item.active_review_assigned_reviewer_user_id,
        aging_bucket=item.aging_bucket,
        sla_seconds_remaining=item.sla_seconds_remaining,
        is_sla_breached=item.is_sla_breached,
    )


def _as_provenance_proof_response(record: ProvenanceProofRecord) -> ProvenanceProofResponse:
    return ProvenanceProofResponse(
        id=record.id,
        project_id=record.project_id,
        export_request_id=record.export_request_id,
        candidate_snapshot_id=record.candidate_snapshot_id,
        attempt_number=record.attempt_number,
        supersedes_proof_id=record.supersedes_proof_id,
        superseded_by_proof_id=record.superseded_by_proof_id,
        root_sha256=record.root_sha256,
        signature_key_ref=record.signature_key_ref,
        signature_bytes_key=record.signature_bytes_key,
        proof_artifact_key=record.proof_artifact_key,
        proof_artifact_sha256=record.proof_artifact_sha256,
        created_by=record.created_by,
        created_at=record.created_at,
    )


def _as_bundle_response(record: DepositBundleRecord) -> DepositBundleResponse:
    return DepositBundleResponse(
        id=record.id,
        project_id=record.project_id,
        export_request_id=record.export_request_id,
        candidate_snapshot_id=record.candidate_snapshot_id,
        provenance_proof_id=record.provenance_proof_id,
        provenance_proof_artifact_sha256=record.provenance_proof_artifact_sha256,
        bundle_kind=record.bundle_kind,
        status=record.status,
        attempt_number=record.attempt_number,
        supersedes_bundle_id=record.supersedes_bundle_id,
        superseded_by_bundle_id=record.superseded_by_bundle_id,
        bundle_key=_safe_storage_reference(record.bundle_key),
        bundle_sha256=record.bundle_sha256,
        failure_reason=record.failure_reason,
        created_by=record.created_by,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        canceled_by=record.canceled_by,
        canceled_at=record.canceled_at,
    )


def _as_bundle_verification_projection_response(
    record: BundleVerificationProjectionRecord,
) -> BundleVerificationProjectionResponse:
    return BundleVerificationProjectionResponse(
        bundle_id=record.bundle_id,
        status=record.status,
        last_verification_run_id=record.last_verification_run_id,
        verified_at=record.verified_at,
        updated_at=record.updated_at,
    )


def _as_bundle_event_response(record: BundleEventRecord) -> BundleEventResponse:
    return BundleEventResponse(
        id=record.id,
        bundle_id=record.bundle_id,
        event_type=record.event_type,
        verification_run_id=record.verification_run_id,
        validation_run_id=record.validation_run_id,
        actor_user_id=record.actor_user_id,
        reason=record.reason,
        created_at=record.created_at,
    )


def _as_bundle_verification_run_response(
    record: BundleVerificationRunRecord,
) -> BundleVerificationRunResponse:
    return BundleVerificationRunResponse(
        id=record.id,
        project_id=record.project_id,
        bundle_id=record.bundle_id,
        attempt_number=record.attempt_number,
        supersedes_verification_run_id=record.supersedes_verification_run_id,
        superseded_by_verification_run_id=record.superseded_by_verification_run_id,
        status=record.status,
        result_json=dict(record.result_json),
        created_by=record.created_by,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        canceled_by=record.canceled_by,
        canceled_at=record.canceled_at,
        failure_reason=record.failure_reason,
    )


def _as_bundle_profile_response(record: BundleProfileRecord) -> BundleProfileResponse:
    return BundleProfileResponse(
        id=record.id,
        label=record.label,
        description=record.description,
        allowed_bundle_kinds=list(record.allowed_bundle_kinds),
        required_archive_entries=list(record.required_archive_entries),
        required_metadata_paths=list(record.required_metadata_paths),
        forbidden_metadata_paths=list(record.forbidden_metadata_paths),
    )


def _as_bundle_validation_projection_response(
    record: BundleValidationProjectionRecord,
) -> BundleValidationProjectionResponse:
    return BundleValidationProjectionResponse(
        bundle_id=record.bundle_id,
        profile_id=record.profile_id,
        status=record.status,
        last_validation_run_id=record.last_validation_run_id,
        ready_at=record.ready_at,
        updated_at=record.updated_at,
    )


def _as_bundle_validation_run_response(
    record: BundleValidationRunRecord,
) -> BundleValidationRunResponse:
    return BundleValidationRunResponse(
        id=record.id,
        project_id=record.project_id,
        bundle_id=record.bundle_id,
        profile_id=record.profile_id,
        profile_snapshot_key=_safe_storage_reference(record.profile_snapshot_key)
        or record.profile_snapshot_key,
        profile_snapshot_sha256=record.profile_snapshot_sha256,
        status=record.status,
        attempt_number=record.attempt_number,
        supersedes_validation_run_id=record.supersedes_validation_run_id,
        superseded_by_validation_run_id=record.superseded_by_validation_run_id,
        result_json=dict(record.result_json),
        failure_reason=record.failure_reason,
        created_by=record.created_by,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        canceled_by=record.canceled_by,
        canceled_at=record.canceled_at,
    )


def _raise_export_http_error(error: Exception) -> None:
    if isinstance(error, ExportAccessDeniedError | ProjectAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, ExportNotFoundError | ProjectNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, ExportValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    if isinstance(error, ExportConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if isinstance(error, ExportStoreUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Export persistence is unavailable.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(error),
    ) from error


@router.get(
    "/export-candidates",
    response_model=ExportCandidateListResponse,
)
def list_export_candidates(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportCandidateListResponse:
    try:
        items = export_service.list_export_candidates(
            current_user=current_user,
            project_id=project_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_CANDIDATES_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return ExportCandidateListResponse(items=[_as_candidate_response(item) for item in items])


@router.get(
    "/export-candidates/{candidate_id}",
    response_model=ExportCandidateResponse,
)
def get_export_candidate(
    project_id: str,
    candidate_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportCandidateResponse:
    try:
        candidate = export_service.get_export_candidate(
            current_user=current_user,
            project_id=project_id,
            candidate_id=candidate_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_CANDIDATE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_candidate_snapshot",
        object_id=candidate_id,
        metadata={
            "route": request_context.route_template,
            "candidate_kind": candidate.candidate_kind,
            "source_phase": candidate.source_phase,
        },
        request_context=request_context,
    )
    return _as_candidate_response(candidate)


@router.get(
    "/export-candidates/{candidate_id}/release-pack",
    response_model=ExportReleasePackPreviewResponse,
)
def get_export_candidate_release_pack_preview(
    project_id: str,
    candidate_id: str,
    purpose_statement: str | None = Query(default=None, alias="purposeStatement"),
    bundle_profile: str | None = Query(default=None, alias="bundleProfile"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportReleasePackPreviewResponse:
    try:
        preview = export_service.get_candidate_release_pack_preview(
            current_user=current_user,
            project_id=project_id,
            candidate_id=candidate_id,
            purpose_statement=purpose_statement,
            bundle_profile=bundle_profile,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)

    candidate_record = preview["candidate"]
    if not isinstance(candidate_record, ExportCandidateSnapshotRecord):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid candidate release-pack preview payload.",
        )
    risk_reason_codes = [str(item) for item in preview.get("riskReasonCodes", ())]
    audit_service.record_event_best_effort(
        event_type="EXPORT_RELEASE_PACK_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_candidate_snapshot",
        object_id=candidate_id,
        metadata={
            "route": request_context.route_template,
            "risk_classification": preview.get("riskClassification"),
            "review_path": preview.get("reviewPath"),
            "reason_codes": risk_reason_codes,
        },
        request_context=request_context,
    )
    return ExportReleasePackPreviewResponse(
        candidate=_as_candidate_response(candidate_record),
        release_pack=dict(preview["releasePack"]),
        release_pack_sha256=str(preview["releasePackSha256"]),
        release_pack_key=str(preview["releasePackKey"]),
        risk_classification=preview["riskClassification"],  # type: ignore[arg-type]
        risk_reason_codes=risk_reason_codes,
        review_path=preview["reviewPath"],  # type: ignore[arg-type]
        requires_second_review=bool(preview["requiresSecondReview"]),
    )


@router.post(
    "/export-requests",
    response_model=ExportRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_export_request(
    project_id: str,
    payload: CreateExportRequestRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportRequestResponse:
    try:
        request_record = export_service.create_export_request(
            current_user=current_user,
            project_id=project_id,
            candidate_snapshot_id=payload.candidate_snapshot_id,
            purpose_statement=payload.purpose_statement,
            bundle_profile=payload.bundle_profile,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_SUBMITTED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=request_record.id,
        metadata={
            "route": request_context.route_template,
            "candidate_snapshot_id": request_record.candidate_snapshot_id,
            "request_revision": request_record.request_revision,
            "risk_classification": request_record.risk_classification,
            "review_path": request_record.review_path,
            "requires_second_review": request_record.requires_second_review,
            "release_pack_sha256": request_record.release_pack_sha256,
        },
        request_context=request_context,
    )
    return _as_request_response(request_record)


@router.get(
    "/export-requests",
    response_model=ExportRequestListResponse,
)
def list_export_requests(
    project_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    requester_id: str | None = Query(default=None, alias="requesterId"),
    candidate_kind: str | None = Query(default=None, alias="candidateKind"),
    cursor: int = Query(default=0, ge=0, alias="cursor"),
    limit: int = Query(default=50, ge=1, le=100, alias="limit"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportRequestListResponse:
    try:
        page = export_service.list_export_requests(
            current_user=current_user,
            project_id=project_id,
            status=status_filter,
            requester_id=requester_id,
            candidate_kind=candidate_kind,
            cursor=cursor,
            limit=limit,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_HISTORY_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "status_filter": status_filter,
            "requester_id_filter": requester_id,
            "candidate_kind_filter": candidate_kind,
            "cursor": cursor,
            "returned_count": len(page.items),
        },
        request_context=request_context,
    )
    return ExportRequestListResponse(
        items=[_as_request_response(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/export-requests/{export_request_id}",
    response_model=ExportRequestResponse,
)
def get_export_request(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportRequestResponse:
    try:
        request_record = export_service.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "status": request_record.status,
            "request_revision": request_record.request_revision,
        },
        request_context=request_context,
    )
    return _as_request_response(request_record)


@router.get(
    "/export-requests/{export_request_id}/status",
    response_model=ExportRequestStatusResponse,
)
def get_export_request_status(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportRequestStatusResponse:
    try:
        payload = export_service.get_export_request_status(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "status": payload["status"],
            "request_revision": payload["requestRevision"],
        },
        request_context=request_context,
    )
    return ExportRequestStatusResponse(
        id=str(payload["id"]),
        status=payload["status"],  # type: ignore[arg-type]
        risk_classification=payload["riskClassification"],  # type: ignore[arg-type]
        review_path=payload["reviewPath"],  # type: ignore[arg-type]
        requires_second_review=bool(payload["requiresSecondReview"]),
        request_revision=int(payload["requestRevision"]),
        submitted_at=payload["submittedAt"],  # type: ignore[arg-type]
        last_queue_activity_at=payload.get("lastQueueActivityAt"),  # type: ignore[arg-type]
        sla_due_at=payload.get("slaDueAt"),  # type: ignore[arg-type]
        retention_until=payload.get("retentionUntil"),  # type: ignore[arg-type]
        final_decision_at=payload.get("finalDecisionAt"),  # type: ignore[arg-type]
        final_decision_by=(
            str(payload["finalDecisionBy"])
            if isinstance(payload.get("finalDecisionBy"), str)
            else None
        ),
        final_decision_reason=(
            str(payload["finalDecisionReason"])
            if isinstance(payload.get("finalDecisionReason"), str)
            else None
        ),
        final_return_comment=(
            str(payload["finalReturnComment"])
            if isinstance(payload.get("finalReturnComment"), str)
            else None
        ),
        exported_at=payload.get("exportedAt"),  # type: ignore[arg-type]
    )


@router.get(
    "/export-requests/{export_request_id}/release-pack",
    response_model=ExportRequestReleasePackResponse,
)
def get_export_request_release_pack(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportRequestReleasePackResponse:
    try:
        payload = export_service.get_export_request_release_pack(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_RELEASE_PACK_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "request_revision": payload["requestRevision"],
            "release_pack_sha256": payload["releasePackSha256"],
        },
        request_context=request_context,
    )
    return ExportRequestReleasePackResponse(
        request_id=str(payload["requestId"]),
        request_revision=int(payload["requestRevision"]),
        release_pack=dict(payload["releasePack"]),  # type: ignore[arg-type]
        release_pack_sha256=str(payload["releasePackSha256"]),
        release_pack_key=str(payload["releasePackKey"]),
        release_pack_created_at=payload["releasePackCreatedAt"],  # type: ignore[arg-type]
    )


@router.get(
    "/export-requests/{export_request_id}/validation-summary",
    response_model=ExportRequestValidationSummaryResponse,
)
def get_export_request_validation_summary(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportRequestValidationSummaryResponse:
    try:
        payload = export_service.get_export_request_validation_summary(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "status": payload["requestStatus"],
            "request_revision": payload["requestRevision"],
        },
        request_context=request_context,
    )

    release_pack_payload = payload["releasePack"]
    audit_payload = payload["auditCompleteness"]

    def _parse_check(check: object) -> ExportValidationCheckResponse:
        check_map = check if isinstance(check, dict) else {}
        issue_rows = check_map.get("issues")
        issue_items: list[ExportValidationIssueResponse] = []
        if isinstance(issue_rows, list):
            for issue in issue_rows:
                if not isinstance(issue, dict):
                    continue
                issue_items.append(
                    ExportValidationIssueResponse(
                        code=str(issue.get("code") or "UNKNOWN"),
                        detail=str(issue.get("detail") or "Validation issue."),
                        field=(
                            str(issue["field"])
                            if isinstance(issue.get("field"), str)
                            else None
                        ),
                        expected=(
                            str(issue["expected"])
                            if isinstance(issue.get("expected"), str)
                            else None
                        ),
                        actual=(
                            str(issue["actual"])
                            if isinstance(issue.get("actual"), str)
                            else None
                        ),
                        blocking=bool(issue.get("blocking", True)),
                    )
                )
        facts = check_map.get("facts")
        return ExportValidationCheckResponse(
            check_id=str(check_map.get("checkId") or "unknown"),
            passed=bool(check_map.get("passed", False)),
            issue_count=int(check_map.get("issueCount") or len(issue_items)),
            issues=issue_items,
            facts=dict(facts) if isinstance(facts, dict) else {},
        )

    return ExportRequestValidationSummaryResponse(
        request_id=str(payload["requestId"]),
        project_id=str(payload["projectId"]),
        request_status=payload["requestStatus"],  # type: ignore[arg-type]
        request_revision=int(payload["requestRevision"]),
        generated_at=payload["generatedAt"],  # type: ignore[arg-type]
        is_valid=bool(payload["isValid"]),
        release_pack=_parse_check(release_pack_payload),
        audit_completeness=_parse_check(audit_payload),
    )


@router.get(
    "/export-requests/{export_request_id}/provenance",
    response_model=ExportRequestProvenanceSummaryResponse,
)
def get_export_request_provenance_summary(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportRequestProvenanceSummaryResponse:
    try:
        payload = export_service.get_export_request_provenance_summary(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)

    raw_nodes = payload.get("lineageNodes")
    nodes: list[ProvenanceLineageNodeResponse] = []
    if isinstance(raw_nodes, list):
        for row in raw_nodes:
            if not isinstance(row, dict):
                continue
            nodes.append(
                ProvenanceLineageNodeResponse(
                    artifact_kind=str(row.get("artifactKind") or ""),
                    stable_identifier=str(row.get("stableIdentifier") or ""),
                    immutable_reference=str(row.get("immutableReference") or ""),
                    parent_references=[
                        str(item)
                        for item in row.get("parentReferences", [])
                        if isinstance(item, str)
                    ],
                )
            )

    references = payload.get("references")
    references_json = dict(references) if isinstance(references, dict) else {}
    audit_service.record_event_best_effort(
        event_type="EXPORT_PROVENANCE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "current_proof_id": payload.get("currentProofId"),
            "proof_attempt_count": payload.get("proofAttemptCount"),
        },
        request_context=request_context,
    )
    return ExportRequestProvenanceSummaryResponse(
        project_id=str(payload.get("projectId") or project_id),
        request_id=str(payload.get("requestId") or export_request_id),
        request_status=payload.get("requestStatus"),  # type: ignore[arg-type]
        candidate_snapshot_id=str(payload.get("candidateSnapshotId") or ""),
        proof_attempt_count=int(payload.get("proofAttemptCount") or 0),
        current_proof_id=(
            str(payload["currentProofId"])
            if isinstance(payload.get("currentProofId"), str)
            else None
        ),
        current_attempt_number=(
            int(payload["currentAttemptNumber"])
            if isinstance(payload.get("currentAttemptNumber"), int)
            else None
        ),
        current_proof_generated_at=(
            str(payload["currentProofGeneratedAt"])
            if isinstance(payload.get("currentProofGeneratedAt"), str)
            else None
        ),
        root_sha256=(
            str(payload["rootSha256"]) if isinstance(payload.get("rootSha256"), str) else None
        ),
        signature_key_ref=(
            str(payload["signatureKeyRef"])
            if isinstance(payload.get("signatureKeyRef"), str)
            else None
        ),
        signature_status=(
            "SIGNED"
            if str(payload.get("signatureStatus") or "").upper() == "SIGNED"
            else "MISSING"
        ),
        lineage_nodes=nodes,
        references=references_json,
    )


@router.get(
    "/export-requests/{export_request_id}/provenance/proofs",
    response_model=ProvenanceProofListResponse,
)
def list_export_request_provenance_proofs(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ProvenanceProofListResponse:
    try:
        proofs = export_service.list_export_request_provenance_proofs(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_PROVENANCE_PROOFS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(proofs),
        },
        request_context=request_context,
    )
    return ProvenanceProofListResponse(
        items=[_as_provenance_proof_response(item) for item in proofs]
    )


@router.get(
    "/export-requests/{export_request_id}/provenance/proof",
    response_model=ProvenanceProofDetailResponse,
)
def get_export_request_current_provenance_proof(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ProvenanceProofDetailResponse:
    try:
        payload = export_service.get_export_request_current_provenance_proof(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    proof = payload.get("proof")
    artifact = payload.get("artifact")
    proof_record = proof if isinstance(proof, ProvenanceProofRecord) else None
    artifact_payload = dict(artifact) if isinstance(artifact, dict) else {}
    if proof_record is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Current provenance proof payload is unavailable.",
        )
    audit_service.record_event_best_effort(
        event_type="EXPORT_PROVENANCE_PROOF_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "proof_id": proof_record.id,
            "attempt_number": proof_record.attempt_number,
            "current": True,
        },
        request_context=request_context,
    )
    return ProvenanceProofDetailResponse(
        proof=_as_provenance_proof_response(proof_record),
        artifact=artifact_payload,
    )


@router.get(
    "/export-requests/{export_request_id}/provenance/proofs/{proof_id}",
    response_model=ProvenanceProofDetailResponse,
)
def get_export_request_provenance_proof(
    project_id: str,
    export_request_id: str,
    proof_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ProvenanceProofDetailResponse:
    try:
        payload = export_service.get_export_request_provenance_proof(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            proof_id=proof_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    proof = payload.get("proof")
    artifact = payload.get("artifact")
    proof_record = proof if isinstance(proof, ProvenanceProofRecord) else None
    artifact_payload = dict(artifact) if isinstance(artifact, dict) else {}
    if proof_record is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Provenance proof payload is unavailable.",
        )
    audit_service.record_event_best_effort(
        event_type="EXPORT_PROVENANCE_PROOF_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "proof_id": proof_record.id,
            "attempt_number": proof_record.attempt_number,
            "current": proof_record.superseded_by_proof_id is None,
        },
        request_context=request_context,
    )
    return ProvenanceProofDetailResponse(
        proof=_as_provenance_proof_response(proof_record),
        artifact=artifact_payload,
    )


@router.post(
    "/export-requests/{export_request_id}/provenance/proofs/regenerate",
    response_model=RegenerateProvenanceProofResponse,
)
def regenerate_export_request_provenance_proof(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> RegenerateProvenanceProofResponse:
    try:
        proof = export_service.regenerate_export_request_provenance_proof(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_PROVENANCE_PROOF_REGENERATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "proof_id": proof.id,
            "attempt_number": proof.attempt_number,
            "supersedes_proof_id": proof.supersedes_proof_id,
        },
        request_context=request_context,
    )
    return RegenerateProvenanceProofResponse(proof=_as_provenance_proof_response(proof))


@router.get(
    "/export-requests/{export_request_id}/bundles",
    response_model=DepositBundleListResponse,
)
def list_export_request_bundles(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> DepositBundleListResponse:
    try:
        bundles = export_service.list_export_request_bundles(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_LIST_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(bundles),
        },
        request_context=request_context,
    )
    return DepositBundleListResponse(items=[_as_bundle_response(item) for item in bundles])


@router.post(
    "/export-requests/{export_request_id}/bundles",
    response_model=DepositBundleMutationResponse,
)
def create_export_request_bundle(
    project_id: str,
    export_request_id: str,
    kind: DepositBundleKindLiteral = Query(alias="kind"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> DepositBundleMutationResponse:
    try:
        bundle = export_service.create_export_request_bundle(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_kind=kind,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_BUILD_RUN_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle.id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle.id,
            "bundle_kind": bundle.bundle_kind,
            "status": bundle.status,
            "attempt_number": bundle.attempt_number,
            "export_request_id": export_request_id,
        },
        request_context=request_context,
    )
    return DepositBundleMutationResponse(bundle=_as_bundle_response(bundle))


@router.get(
    "/export-requests/{export_request_id}/bundles/{bundle_id}",
    response_model=DepositBundleDetailResponse,
)
def get_export_request_bundle(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> DepositBundleDetailResponse:
    try:
        payload = export_service.get_export_request_bundle(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    bundle = payload.get("bundle")
    if not isinstance(bundle, DepositBundleRecord):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deposit bundle detail payload is unavailable.",
        )
    lineage_attempts = payload.get("lineageAttempts")
    lineage = (
        [item for item in lineage_attempts if isinstance(item, DepositBundleRecord)]
        if isinstance(lineage_attempts, tuple)
        else []
    )
    projection = payload.get("verificationProjection")
    projection_record = (
        projection if isinstance(projection, BundleVerificationProjectionRecord) else None
    )
    artifact = payload.get("artifact")
    artifact_payload = dict(artifact) if isinstance(artifact, dict) else {}
    audit_service.record_event_best_effort(
        event_type="BUNDLE_DETAIL_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle.id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle.id,
            "bundle_kind": bundle.bundle_kind,
            "status": bundle.status,
            "attempt_number": bundle.attempt_number,
        },
        request_context=request_context,
    )
    return DepositBundleDetailResponse(
        bundle=_as_bundle_response(bundle),
        lineage_attempts=[_as_bundle_response(item) for item in lineage],
        verification_projection=(
            _as_bundle_verification_projection_response(projection_record)
            if projection_record is not None
            else None
        ),
        artifact=artifact_payload,
    )


@router.get(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/status",
    response_model=DepositBundleStatusResponse,
)
def get_export_request_bundle_status(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> DepositBundleStatusResponse:
    try:
        payload = export_service.get_export_request_bundle_status(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    bundle = payload.get("bundle")
    if not isinstance(bundle, DepositBundleRecord):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deposit bundle status payload is unavailable.",
        )
    projection = payload.get("verificationProjection")
    projection_record = (
        projection if isinstance(projection, BundleVerificationProjectionRecord) else None
    )
    audit_service.record_event_best_effort(
        event_type="BUNDLE_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle.id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle.id,
            "bundle_kind": bundle.bundle_kind,
            "status": bundle.status,
        },
        request_context=request_context,
    )
    return DepositBundleStatusResponse(
        bundle=_as_bundle_response(bundle),
        verification_projection=(
            _as_bundle_verification_projection_response(projection_record)
            if projection_record is not None
            else None
        ),
    )


@router.get(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/events",
    response_model=BundleEventsResponse,
)
def list_export_request_bundle_events(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleEventsResponse:
    try:
        events = export_service.list_export_request_bundle_events(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_EVENTS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "returned_count": len(events),
        },
        request_context=request_context,
    )
    return BundleEventsResponse(items=[_as_bundle_event_response(item) for item in events])


@router.post(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/cancel",
    response_model=DepositBundleMutationResponse,
)
def cancel_export_request_bundle(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> DepositBundleMutationResponse:
    try:
        bundle = export_service.cancel_export_request_bundle(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_BUILD_RUN_CANCELED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle.id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle.id,
            "bundle_kind": bundle.bundle_kind,
            "status": bundle.status,
            "attempt_number": bundle.attempt_number,
        },
        request_context=request_context,
    )
    return DepositBundleMutationResponse(bundle=_as_bundle_response(bundle))


@router.post(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/rebuild",
    response_model=DepositBundleMutationResponse,
)
def rebuild_export_request_bundle(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> DepositBundleMutationResponse:
    try:
        bundle = export_service.rebuild_export_request_bundle(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_BUILD_RUN_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle.id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle.id,
            "bundle_kind": bundle.bundle_kind,
            "status": bundle.status,
            "attempt_number": bundle.attempt_number,
            "supersedes_bundle_id": bundle.supersedes_bundle_id,
            "requested_from_bundle_id": bundle_id,
        },
        request_context=request_context,
    )
    return DepositBundleMutationResponse(bundle=_as_bundle_response(bundle))


@router.post(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/verify",
    response_model=BundleVerificationRunMutationResponse,
)
def start_export_request_bundle_verification(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleVerificationRunMutationResponse:
    try:
        run = export_service.start_export_request_bundle_verification(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VERIFICATION_RUN_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "verification_run_id": run.id,
        },
        request_context=request_context,
    )
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VERIFICATION_RUN_STARTED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "verification_run_id": run.id,
        },
        request_context=request_context,
    )
    if run.status == "SUCCEEDED":
        audit_service.record_event_best_effort(
            event_type="BUNDLE_VERIFICATION_RUN_FINISHED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="deposit_bundle",
            object_id=bundle_id,
            metadata={
                "route": request_context.route_template,
                "bundle_id": bundle_id,
                "verification_run_id": run.id,
            },
            request_context=request_context,
        )
    elif run.status == "FAILED":
        audit_service.record_event_best_effort(
            event_type="BUNDLE_VERIFICATION_RUN_FAILED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="deposit_bundle",
            object_id=bundle_id,
            metadata={
                "route": request_context.route_template,
                "bundle_id": bundle_id,
                "verification_run_id": run.id,
                "reason": run.failure_reason,
            },
            request_context=request_context,
        )
    return BundleVerificationRunMutationResponse(
        verification_run=_as_bundle_verification_run_response(run)
    )


@router.get(
    "/export-requests/{export_request_id}/bundle-profiles",
    response_model=BundleProfilesResponse,
)
def list_export_request_bundle_profiles(
    project_id: str,
    export_request_id: str,
    bundle_id: str | None = Query(default=None, alias="bundleId"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleProfilesResponse:
    try:
        profiles = export_service.list_export_request_bundle_profiles(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_PROFILES_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id or "*",
            "returned_count": len(profiles),
        },
        request_context=request_context,
    )
    return BundleProfilesResponse(items=[_as_bundle_profile_response(item) for item in profiles])


@router.post(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/validate-profile",
    response_model=BundleValidationRunMutationResponse,
)
def start_export_request_bundle_validation(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    profile_id: str = Query(alias="profile"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleValidationRunMutationResponse:
    try:
        run = export_service.start_export_request_bundle_validation(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            profile_id=profile_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VALIDATION_RUN_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "validation_run_id": run.id,
            "profile_id": run.profile_id,
        },
        request_context=request_context,
    )
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VALIDATION_RUN_STARTED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "validation_run_id": run.id,
            "profile_id": run.profile_id,
        },
        request_context=request_context,
    )
    if run.status == "SUCCEEDED":
        audit_service.record_event_best_effort(
            event_type="BUNDLE_VALIDATION_RUN_FINISHED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="deposit_bundle",
            object_id=bundle_id,
            metadata={
                "route": request_context.route_template,
                "bundle_id": bundle_id,
                "validation_run_id": run.id,
                "profile_id": run.profile_id,
            },
            request_context=request_context,
        )
    elif run.status == "FAILED":
        audit_service.record_event_best_effort(
            event_type="BUNDLE_VALIDATION_RUN_FAILED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="deposit_bundle",
            object_id=bundle_id,
            metadata={
                "route": request_context.route_template,
                "bundle_id": bundle_id,
                "validation_run_id": run.id,
                "profile_id": run.profile_id,
                "reason": run.failure_reason,
            },
            request_context=request_context,
        )
    return BundleValidationRunMutationResponse(
        validation_run=_as_bundle_validation_run_response(run)
    )


@router.get(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/validation-status",
    response_model=BundleValidationStatusResponse,
)
def get_export_request_bundle_validation_status(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    profile_id: str = Query(alias="profile"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleValidationStatusResponse:
    try:
        payload = export_service.get_export_request_bundle_validation_status(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            profile_id=profile_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    bundle_id_value = payload.get("bundleId")
    if not isinstance(bundle_id_value, str):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bundle validation status payload is unavailable.",
        )
    bundle_status = payload.get("bundleStatus")
    if not isinstance(bundle_status, str):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bundle validation status payload is unavailable.",
        )
    profile_id_value = payload.get("profileId")
    if not isinstance(profile_id_value, str):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bundle validation status payload is unavailable.",
        )
    verification_projection = payload.get("verificationProjection")
    verification_projection_record = (
        verification_projection
        if isinstance(verification_projection, BundleVerificationProjectionRecord)
        else None
    )
    validation_projection = payload.get("projection")
    validation_projection_record = (
        validation_projection
        if isinstance(validation_projection, BundleValidationProjectionRecord)
        else None
    )
    latest_attempt = payload.get("latestAttempt")
    latest_attempt_record = (
        latest_attempt if isinstance(latest_attempt, BundleValidationRunRecord) else None
    )
    in_flight_attempt = payload.get("inFlightAttempt")
    in_flight_attempt_record = (
        in_flight_attempt if isinstance(in_flight_attempt, BundleValidationRunRecord) else None
    )
    last_successful_attempt = payload.get("lastSuccessfulAttempt")
    last_successful_attempt_record = (
        last_successful_attempt
        if isinstance(last_successful_attempt, BundleValidationRunRecord)
        else None
    )
    resolved_status = (
        latest_attempt_record.status
        if latest_attempt_record is not None
        else (
            validation_projection_record.status
            if validation_projection_record is not None
            else "PENDING"
        )
    )
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VALIDATION_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id_value,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id_value,
            "profile_id": profile_id_value,
            "status": resolved_status,
        },
        request_context=request_context,
    )
    return BundleValidationStatusResponse(
        bundle_id=bundle_id_value,
        bundle_status=bundle_status,  # type: ignore[arg-type]
        profile_id=profile_id_value,
        verification_projection=(
            _as_bundle_verification_projection_response(verification_projection_record)
            if verification_projection_record is not None
            else None
        ),
        validation_projection=(
            _as_bundle_validation_projection_response(validation_projection_record)
            if validation_projection_record is not None
            else None
        ),
        latest_attempt=(
            _as_bundle_validation_run_response(latest_attempt_record)
            if latest_attempt_record is not None
            else None
        ),
        in_flight_attempt=(
            _as_bundle_validation_run_response(in_flight_attempt_record)
            if in_flight_attempt_record is not None
            else None
        ),
        last_successful_attempt=(
            _as_bundle_validation_run_response(last_successful_attempt_record)
            if last_successful_attempt_record is not None
            else None
        ),
    )


@router.get(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/validation-runs",
    response_model=BundleValidationRunsResponse,
)
def list_export_request_bundle_validation_runs(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    profile_id: str = Query(alias="profile"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleValidationRunsResponse:
    try:
        runs = export_service.list_export_request_bundle_validation_runs(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            profile_id=profile_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    resolved_profile_id = runs[0].profile_id if runs else profile_id.strip().upper()
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VALIDATION_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "profile_id": resolved_profile_id,
            "returned_count": len(runs),
        },
        request_context=request_context,
    )
    return BundleValidationRunsResponse(
        items=[_as_bundle_validation_run_response(item) for item in runs]
    )


@router.get(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/validation-runs/{validation_run_id}",
    response_model=BundleValidationRunDetailResponse,
)
def get_export_request_bundle_validation_run(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    validation_run_id: str,
    profile_id: str | None = Query(default=None, alias="profile"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleValidationRunDetailResponse:
    try:
        run = export_service.get_export_request_bundle_validation_run(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            profile_id=profile_id,
            validation_run_id=validation_run_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VALIDATION_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "profile_id": run.profile_id,
            "returned_count": 1,
        },
        request_context=request_context,
    )
    return BundleValidationRunDetailResponse(
        validation_run=_as_bundle_validation_run_response(run)
    )


@router.get(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/validation-runs/{validation_run_id}/status",
    response_model=BundleValidationRunStatusResponse,
)
def get_export_request_bundle_validation_run_status(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    validation_run_id: str,
    profile_id: str | None = Query(default=None, alias="profile"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleValidationRunStatusResponse:
    try:
        payload = export_service.get_export_request_bundle_validation_run_status(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            profile_id=profile_id,
            validation_run_id=validation_run_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    validation_run = payload.get("validationRun")
    run = validation_run if isinstance(validation_run, BundleValidationRunRecord) else None
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bundle validation run status payload is unavailable.",
        )
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VALIDATION_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "profile_id": run.profile_id,
            "status": run.status,
        },
        request_context=request_context,
    )
    return BundleValidationRunStatusResponse(
        validation_run=_as_bundle_validation_run_response(run)
    )


@router.post(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/validation-runs/{validation_run_id}/cancel",
    response_model=BundleValidationRunMutationResponse,
)
def cancel_export_request_bundle_validation_run(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    validation_run_id: str,
    profile_id: str | None = Query(default=None, alias="profile"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleValidationRunMutationResponse:
    try:
        run = export_service.cancel_export_request_bundle_validation_run(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            profile_id=profile_id,
            validation_run_id=validation_run_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VALIDATION_RUN_CANCELED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "validation_run_id": run.id,
            "profile_id": run.profile_id,
        },
        request_context=request_context,
    )
    return BundleValidationRunMutationResponse(
        validation_run=_as_bundle_validation_run_response(run)
    )


@router.get(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/verification",
    response_model=BundleVerificationResponse,
)
def get_export_request_bundle_verification(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleVerificationResponse:
    try:
        payload = export_service.get_export_request_bundle_verification(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    bundle = payload.get("bundle")
    if not isinstance(bundle, DepositBundleRecord):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bundle verification payload is unavailable.",
        )
    projection = payload.get("projection")
    projection_record = (
        projection if isinstance(projection, BundleVerificationProjectionRecord) else None
    )
    latest_attempt = payload.get("latestAttempt")
    latest_attempt_record = (
        latest_attempt if isinstance(latest_attempt, BundleVerificationRunRecord) else None
    )
    latest_completed_attempt = payload.get("latestCompletedAttempt")
    latest_completed_attempt_record = (
        latest_completed_attempt
        if isinstance(latest_completed_attempt, BundleVerificationRunRecord)
        else None
    )
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VERIFICATION_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle.id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle.id,
            "returned_count": 1,
        },
        request_context=request_context,
    )
    return BundleVerificationResponse(
        bundle=_as_bundle_response(bundle),
        verification_projection=(
            _as_bundle_verification_projection_response(projection_record)
            if projection_record is not None
            else None
        ),
        latest_attempt=(
            _as_bundle_verification_run_response(latest_attempt_record)
            if latest_attempt_record is not None
            else None
        ),
        latest_completed_attempt=(
            _as_bundle_verification_run_response(latest_completed_attempt_record)
            if latest_completed_attempt_record is not None
            else None
        ),
    )


@router.get(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/verification/status",
    response_model=BundleVerificationStatusResponse,
)
def get_export_request_bundle_verification_status(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleVerificationStatusResponse:
    try:
        payload = export_service.get_export_request_bundle_verification_status(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    bundle = payload.get("bundle")
    if not isinstance(bundle, DepositBundleRecord):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bundle verification status payload is unavailable.",
        )
    projection = payload.get("projection")
    projection_record = (
        projection if isinstance(projection, BundleVerificationProjectionRecord) else None
    )
    latest_attempt = payload.get("latestAttempt")
    latest_attempt_record = (
        latest_attempt if isinstance(latest_attempt, BundleVerificationRunRecord) else None
    )
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VERIFICATION_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle.id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle.id,
            "status": (
                latest_attempt_record.status
                if latest_attempt_record is not None
                else (projection_record.status if projection_record is not None else "PENDING")
            ),
        },
        request_context=request_context,
    )
    return BundleVerificationStatusResponse(
        bundle_id=bundle.id,
        bundle_status=bundle.status,
        verification_projection=(
            _as_bundle_verification_projection_response(projection_record)
            if projection_record is not None
            else None
        ),
        latest_attempt=(
            _as_bundle_verification_run_response(latest_attempt_record)
            if latest_attempt_record is not None
            else None
        ),
    )


@router.get(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/verification-runs",
    response_model=BundleVerificationRunsResponse,
)
def list_export_request_bundle_verification_runs(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleVerificationRunsResponse:
    try:
        runs = export_service.list_export_request_bundle_verification_runs(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VERIFICATION_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "returned_count": len(runs),
        },
        request_context=request_context,
    )
    return BundleVerificationRunsResponse(
        items=[_as_bundle_verification_run_response(item) for item in runs]
    )


@router.get(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/verification/{verification_run_id}",
    response_model=BundleVerificationRunDetailResponse,
)
def get_export_request_bundle_verification_run(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    verification_run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleVerificationRunDetailResponse:
    try:
        run = export_service.get_export_request_bundle_verification_run(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            verification_run_id=verification_run_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VERIFICATION_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "returned_count": 1,
        },
        request_context=request_context,
    )
    return BundleVerificationRunDetailResponse(
        verification_run=_as_bundle_verification_run_response(run)
    )


@router.get(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/verification/{verification_run_id}/status",
    response_model=BundleVerificationRunStatusResponse,
)
def get_export_request_bundle_verification_run_status(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    verification_run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleVerificationRunStatusResponse:
    try:
        payload = export_service.get_export_request_bundle_verification_run_status(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            verification_run_id=verification_run_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    verification_run = payload.get("verificationRun")
    run = verification_run if isinstance(verification_run, BundleVerificationRunRecord) else None
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bundle verification run status payload is unavailable.",
        )
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VERIFICATION_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "status": run.status,
        },
        request_context=request_context,
    )
    return BundleVerificationRunStatusResponse(
        verification_run=_as_bundle_verification_run_response(run)
    )


@router.post(
    "/export-requests/{export_request_id}/bundles/{bundle_id}/verification/{verification_run_id}/cancel",
    response_model=BundleVerificationRunMutationResponse,
)
def cancel_export_request_bundle_verification_run(
    project_id: str,
    export_request_id: str,
    bundle_id: str,
    verification_run_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> BundleVerificationRunMutationResponse:
    try:
        run = export_service.cancel_export_request_bundle_verification_run(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            verification_run_id=verification_run_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="BUNDLE_VERIFICATION_RUN_CANCELED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="deposit_bundle",
        object_id=bundle_id,
        metadata={
            "route": request_context.route_template,
            "bundle_id": bundle_id,
            "verification_run_id": run.id,
        },
        request_context=request_context,
    )
    return BundleVerificationRunMutationResponse(
        verification_run=_as_bundle_verification_run_response(run)
    )


@router.get(
    "/export-requests/{export_request_id}/events",
    response_model=ExportRequestEventsResponse,
)
def get_export_request_events(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportRequestEventsResponse:
    try:
        items = export_service.get_export_request_events(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_EVENTS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return ExportRequestEventsResponse(items=[_as_event_response(item) for item in items])


@router.get(
    "/export-requests/{export_request_id}/reviews",
    response_model=ExportRequestReviewsResponse,
)
def get_export_request_reviews(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportRequestReviewsResponse:
    try:
        items = export_service.get_export_request_reviews(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_REVIEWS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return ExportRequestReviewsResponse(items=[_as_review_response(item) for item in items])


@router.get(
    "/export-requests/{export_request_id}/reviews/events",
    response_model=ExportRequestReviewEventsResponse,
)
def get_export_request_review_events(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportRequestReviewEventsResponse:
    try:
        items = export_service.get_export_request_review_events(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_REVIEW_EVENTS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=export_request_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(items),
        },
        request_context=request_context,
    )
    return ExportRequestReviewEventsResponse(
        items=[_as_review_event_response(item) for item in items]
    )


@router.post(
    "/export-requests/{export_request_id}/reviews/{review_id}/claim",
    response_model=ExportReviewActionResponse,
)
def claim_export_request_review(
    project_id: str,
    export_request_id: str,
    review_id: str,
    payload: ExportReviewEtagRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportReviewActionResponse:
    try:
        request_record, review_record = export_service.claim_export_request_review(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            review_id=review_id,
            review_etag=payload.review_etag,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_REVIEW_CLAIMED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request_review",
        object_id=review_record.id,
        metadata={
            "route": request_context.route_template,
            "review_id": review_record.id,
            "review_stage": review_record.review_stage,
            "review_etag": review_record.review_etag,
        },
        request_context=request_context,
    )
    return ExportReviewActionResponse(
        request=_as_request_response(request_record),
        review=_as_review_response(review_record),
    )


@router.post(
    "/export-requests/{export_request_id}/reviews/{review_id}/release",
    response_model=ExportReviewActionResponse,
)
def release_export_request_review(
    project_id: str,
    export_request_id: str,
    review_id: str,
    payload: ExportReviewEtagRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportReviewActionResponse:
    try:
        request_record, review_record = export_service.release_export_request_review(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            review_id=review_id,
            review_etag=payload.review_etag,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_REVIEW_RELEASED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request_review",
        object_id=review_record.id,
        metadata={
            "route": request_context.route_template,
            "released_review_id": review_record.id,
            "review_stage": review_record.review_stage,
        },
        request_context=request_context,
    )
    return ExportReviewActionResponse(
        request=_as_request_response(request_record),
        review=_as_review_response(review_record),
    )


@router.post(
    "/export-requests/{export_request_id}/resubmit",
    response_model=ExportRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def resubmit_export_request(
    project_id: str,
    export_request_id: str,
    payload: ResubmitExportRequestRequest = Body(default_factory=ResubmitExportRequestRequest),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportRequestResponse:
    try:
        request_record = export_service.resubmit_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            candidate_snapshot_id=payload.candidate_snapshot_id,
            purpose_statement=payload.purpose_statement,
            bundle_profile=payload.bundle_profile,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_RESUBMITTED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request",
        object_id=request_record.id,
        metadata={
            "route": request_context.route_template,
            "supersedes_export_request_id": export_request_id,
            "candidate_snapshot_id": request_record.candidate_snapshot_id,
            "request_revision": request_record.request_revision,
            "risk_classification": request_record.risk_classification,
            "review_path": request_record.review_path,
            "requires_second_review": request_record.requires_second_review,
            "release_pack_sha256": request_record.release_pack_sha256,
        },
        request_context=request_context,
    )
    return _as_request_response(request_record)


@router.post(
    "/export-requests/{export_request_id}/start-review",
    response_model=ExportReviewActionResponse,
)
def start_export_request_review(
    project_id: str,
    export_request_id: str,
    payload: ExportStartReviewRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportReviewActionResponse:
    try:
        request_record, review_record = export_service.start_export_request_review(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            review_id=payload.review_id,
            review_etag=payload.review_etag,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_REVIEW_STARTED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request_review",
        object_id=review_record.id,
        metadata={
            "route": request_context.route_template,
            "review_id": review_record.id,
            "review_stage": review_record.review_stage,
            "review_etag": review_record.review_etag,
        },
        request_context=request_context,
    )
    return ExportReviewActionResponse(
        request=_as_request_response(request_record),
        review=_as_review_response(review_record),
    )


@router.get(
    "/export-requests/{export_request_id}/receipt",
    response_model=ExportReceiptResponse,
)
def get_export_request_receipt(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportReceiptResponse:
    try:
        receipt = export_service.get_export_request_receipt(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_RECEIPT_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request_receipt",
        object_id=receipt.id,
        metadata={
            "route": request_context.route_template,
            "attempt_number": receipt.attempt_number,
        },
        request_context=request_context,
    )
    return _as_receipt_response(receipt)


@router.get(
    "/export-requests/{export_request_id}/receipts",
    response_model=ExportReceiptListResponse,
)
def list_export_request_receipts(
    project_id: str,
    export_request_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportReceiptListResponse:
    try:
        receipts = export_service.list_export_request_receipts(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_RECEIPTS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(receipts),
        },
        request_context=request_context,
    )
    return ExportReceiptListResponse(items=[_as_receipt_response(item) for item in receipts])


@router.post(
    "/export-requests/{export_request_id}/decision",
    response_model=ExportReviewActionResponse,
)
def decide_export_request(
    project_id: str,
    export_request_id: str,
    payload: ExportDecisionRequest = Body(),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportReviewActionResponse:
    try:
        request_record, review_record = export_service.decide_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            review_id=payload.review_id,
            review_etag=payload.review_etag,
            decision=payload.decision,
            decision_reason=payload.decision_reason,
            return_comment=payload.return_comment,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    decision_event_type: Literal[
        "EXPORT_REQUEST_APPROVED",
        "EXPORT_REQUEST_REJECTED",
        "EXPORT_REQUEST_RETURNED",
    ]
    if payload.decision == "APPROVE":
        decision_event_type = "EXPORT_REQUEST_APPROVED"
    elif payload.decision == "REJECT":
        decision_event_type = "EXPORT_REQUEST_REJECTED"
    else:
        decision_event_type = "EXPORT_REQUEST_RETURNED"
    audit_service.record_event_best_effort(
        event_type=decision_event_type,
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="export_request_review",
        object_id=review_record.id,
        metadata={
            "route": request_context.route_template,
            "review_id": review_record.id,
            "decision_reason": payload.decision_reason,
        },
        request_context=request_context,
    )
    return ExportReviewActionResponse(
        request=_as_request_response(request_record),
        review=_as_review_response(review_record),
    )


@router.get(
    "/export-review",
    response_model=ExportReviewQueueResponse,
)
def list_export_review_queue(
    project_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    aging_bucket_filter: str | None = Query(default=None, alias="agingBucket"),
    reviewer_user_id: str | None = Query(default=None, alias="reviewerUserId"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportReviewQueueResponse:
    try:
        items = export_service.list_export_review_queue(
            current_user=current_user,
            project_id=project_id,
            status=status_filter,
            aging_bucket=aging_bucket_filter,
            reviewer_user_id=reviewer_user_id,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)

    platform_roles = set(current_user.platform_roles)
    read_only = "AUDITOR" in platform_roles and "ADMIN" not in platform_roles
    audit_service.record_event_best_effort(
        event_type="EXPORT_REVIEW_QUEUE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "status_filter": status_filter,
            "aging_bucket_filter": aging_bucket_filter,
            "reviewer_user_id_filter": reviewer_user_id,
            "returned_count": len(items),
            "read_only": read_only,
        },
        request_context=request_context,
    )
    return ExportReviewQueueResponse(
        items=[_as_review_queue_item_response(item) for item in items],
        read_only=read_only,
    )


@internal_router.post(
    "/export-requests/{export_request_id}/receipt",
    response_model=AttachExportReceiptResponse,
)
def attach_export_request_receipt_from_gateway(
    export_request_id: str,
    payload: AttachExportReceiptRequest = Body(),
    gateway_user_id: str = Depends(require_internal_export_gateway_service_account),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    export_service: ExportService = Depends(get_export_service),
    settings: Settings = Depends(get_settings),
) -> AttachExportReceiptResponse:
    try:
        request_record, receipt_record = export_service.attach_gateway_export_request_receipt(
            export_request_id=export_request_id,
            gateway_user_id=gateway_user_id,
            gateway_oidc_sub=settings.internal_export_gateway_oidc_sub,
            gateway_email=settings.internal_export_gateway_email,
            gateway_display_name=settings.internal_export_gateway_display_name,
            receipt_key=payload.receipt_key,
            receipt_sha256=payload.receipt_sha256,
            exported_at=payload.exported_at,
        )
    except Exception as error:  # pragma: no cover - mapped to typed HTTP failure
        _raise_export_http_error(error)
    audit_service.record_event_best_effort(
        event_type="EXPORT_REQUEST_EXPORTED",
        actor_user_id=gateway_user_id,
        project_id=request_record.project_id,
        object_type="export_request",
        object_id=request_record.id,
        metadata={
            "route": request_context.route_template,
            "attempt_number": receipt_record.attempt_number,
            "receipt_sha256": receipt_record.receipt_sha256,
        },
        request_context=request_context,
    )
    return AttachExportReceiptResponse(
        request=_as_request_response(request_record),
        receipt=_as_receipt_response(receipt_record),
    )
