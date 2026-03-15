from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ExportCandidateSourcePhase = Literal["PHASE6", "PHASE7", "PHASE9", "PHASE10"]
ExportCandidateSourceArtifactKind = Literal[
    "REDACTION_RUN_OUTPUT",
    "DEPOSIT_BUNDLE",
    "DERIVATIVE_SNAPSHOT",
]
ExportCandidateKind = Literal[
    "SAFEGUARDED_PREVIEW",
    "POLICY_RERUN",
    "DEPOSIT_BUNDLE",
    "SAFEGUARDED_DERIVATIVE",
]
ExportCandidateEligibilityStatus = Literal["ELIGIBLE", "SUPERSEDED"]

ExportRequestRiskClassification = Literal["STANDARD", "HIGH"]
ExportRequestReviewPath = Literal["SINGLE", "DUAL"]
ExportRequestStatus = Literal[
    "SUBMITTED",
    "RESUBMITTED",
    "IN_REVIEW",
    "APPROVED",
    "EXPORTED",
    "REJECTED",
    "RETURNED",
]
ExportRequestEventType = Literal[
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
ExportRequestReviewStage = Literal["PRIMARY", "SECONDARY"]
ExportRequestReviewStatus = Literal["PENDING", "IN_REVIEW", "APPROVED", "RETURNED", "REJECTED"]
ExportRequestReviewEventType = Literal[
    "REVIEW_CREATED",
    "REVIEW_CLAIMED",
    "REVIEW_STARTED",
    "REVIEW_APPROVED",
    "REVIEW_REJECTED",
    "REVIEW_RETURNED",
    "REVIEW_RELEASED",
]
ExportRequestDecision = Literal["APPROVE", "REJECT", "RETURN"]
ExportReviewAgingBucket = Literal[
    "UNSTARTED",
    "NO_SLA",
    "ON_TRACK",
    "DUE_SOON",
    "OVERDUE",
]


@dataclass(frozen=True)
class ExportCandidateSnapshotRecord:
    id: str
    project_id: str
    source_phase: ExportCandidateSourcePhase
    source_artifact_kind: ExportCandidateSourceArtifactKind
    source_run_id: str | None
    source_artifact_id: str
    governance_run_id: str | None
    governance_manifest_id: str | None
    governance_ledger_id: str | None
    governance_manifest_sha256: str | None
    governance_ledger_sha256: str | None
    policy_snapshot_hash: str | None
    policy_id: str | None
    policy_family_id: str | None
    policy_version: str | None
    candidate_kind: ExportCandidateKind
    artefact_manifest_json: dict[str, object]
    candidate_sha256: str
    eligibility_status: ExportCandidateEligibilityStatus
    supersedes_candidate_snapshot_id: str | None
    superseded_by_candidate_snapshot_id: str | None
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class ExportReleasePackRecord:
    key: str
    sha256: str
    pack_json: dict[str, object]
    created_at: datetime | None


@dataclass(frozen=True)
class ExportRequestRecord:
    id: str
    project_id: str
    candidate_snapshot_id: str
    candidate_origin_phase: ExportCandidateSourcePhase
    candidate_kind: ExportCandidateKind
    bundle_profile: str | None
    risk_classification: ExportRequestRiskClassification
    risk_reason_codes_json: tuple[str, ...]
    review_path: ExportRequestReviewPath
    requires_second_review: bool
    supersedes_export_request_id: str | None
    superseded_by_export_request_id: str | None
    request_revision: int
    purpose_statement: str
    status: ExportRequestStatus
    submitted_by: str
    submitted_at: datetime
    first_review_started_by: str | None
    first_review_started_at: datetime | None
    sla_due_at: datetime | None
    last_queue_activity_at: datetime | None
    retention_until: datetime | None
    final_review_id: str | None
    final_decision_by: str | None
    final_decision_at: datetime | None
    final_decision_reason: str | None
    final_return_comment: str | None
    release_pack_key: str
    release_pack_sha256: str
    release_pack_json: dict[str, object]
    release_pack_created_at: datetime
    receipt_id: str | None
    receipt_key: str | None
    receipt_sha256: str | None
    receipt_created_by: str | None
    receipt_created_at: datetime | None
    exported_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ExportRequestEventRecord:
    id: str
    export_request_id: str
    event_type: ExportRequestEventType
    from_status: ExportRequestStatus | None
    to_status: ExportRequestStatus
    actor_user_id: str | None
    reason: str | None
    created_at: datetime


@dataclass(frozen=True)
class ExportRequestReviewRecord:
    id: str
    export_request_id: str
    review_stage: ExportRequestReviewStage
    is_required: bool
    status: ExportRequestReviewStatus
    assigned_reviewer_user_id: str | None
    assigned_at: datetime | None
    acted_by_user_id: str | None
    acted_at: datetime | None
    decision_reason: str | None
    return_comment: str | None
    review_etag: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ExportRequestReviewEventRecord:
    id: str
    review_id: str
    export_request_id: str
    review_stage: ExportRequestReviewStage
    event_type: ExportRequestReviewEventType
    actor_user_id: str | None
    assigned_reviewer_user_id: str | None
    decision_reason: str | None
    return_comment: str | None
    created_at: datetime


@dataclass(frozen=True)
class ExportReceiptRecord:
    id: str
    export_request_id: str
    attempt_number: int
    supersedes_receipt_id: str | None
    superseded_by_receipt_id: str | None
    receipt_key: str
    receipt_sha256: str
    created_by: str
    created_at: datetime
    exported_at: datetime


@dataclass(frozen=True)
class ExportReviewQueueItemRecord:
    request: ExportRequestRecord
    reviews: tuple[ExportRequestReviewRecord, ...]
    active_review_id: str | None
    active_review_stage: ExportRequestReviewStage | None
    active_review_status: ExportRequestReviewStatus | None
    active_review_assigned_reviewer_user_id: str | None
    aging_bucket: ExportReviewAgingBucket
    sla_seconds_remaining: int | None
    is_sla_breached: bool


@dataclass(frozen=True)
class ExportOperationsStatusRecord:
    generated_at: datetime
    open_request_count: int
    aging_unstarted_count: int
    aging_no_sla_count: int
    aging_on_track_count: int
    aging_due_soon_count: int
    aging_overdue_count: int
    stale_open_count: int
    reminder_due_count: int
    reminders_sent_last_24h: int
    reminders_sent_total: int
    escalation_due_count: int
    escalated_open_count: int
    escalations_total: int
    retention_pending_count: int
    retention_pending_window_days: int
    terminal_approved_count: int
    terminal_exported_count: int
    terminal_rejected_count: int
    terminal_returned_count: int
    policy_sla_hours: int
    policy_reminder_after_hours: int
    policy_reminder_cooldown_hours: int
    policy_escalation_after_sla_hours: int
    policy_escalation_cooldown_hours: int
    policy_stale_open_after_days: int
    policy_retention_stale_open_days: int
    policy_retention_terminal_approved_days: int
    policy_retention_terminal_other_days: int


@dataclass(frozen=True)
class ExportOperationsMaintenanceResult:
    run_at: datetime
    reminders_appended: int
    escalations_appended: int
    retention_updates_applied: int
    retention_audit_safe: bool


@dataclass(frozen=True)
class ExportRequestListPage:
    items: tuple[ExportRequestRecord, ...]
    next_cursor: int | None


@dataclass(frozen=True)
class ProvenanceProofRecord:
    id: str
    project_id: str
    export_request_id: str
    candidate_snapshot_id: str
    attempt_number: int
    supersedes_proof_id: str | None
    superseded_by_proof_id: str | None
    root_sha256: str
    signature_key_ref: str
    signature_bytes_key: str
    proof_artifact_key: str
    proof_artifact_sha256: str
    created_by: str
    created_at: datetime


DepositBundleKind = Literal["CONTROLLED_EVIDENCE", "SAFEGUARDED_DEPOSIT"]
DepositBundleStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
BundleVerificationProjectionStatus = Literal["PENDING", "VERIFIED", "FAILED"]
BundleVerificationRunStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
BundleValidationProjectionStatus = Literal["PENDING", "READY", "FAILED"]
BundleValidationRunStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
ReplayFailureClass = Literal[
    "MISSING_ARTEFACT",
    "TAMPERED_PROOF",
    "INVALID_BUNDLE_CONTENTS",
    "PROFILE_MISMATCH",
    "ENVIRONMENTAL_RUNTIME",
]
BundleEventType = Literal[
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


@dataclass(frozen=True)
class DepositBundleRecord:
    id: str
    project_id: str
    export_request_id: str
    candidate_snapshot_id: str
    provenance_proof_id: str
    provenance_proof_artifact_sha256: str
    bundle_kind: DepositBundleKind
    status: DepositBundleStatus
    attempt_number: int
    supersedes_bundle_id: str | None
    superseded_by_bundle_id: str | None
    bundle_key: str | None
    bundle_sha256: str | None
    failure_reason: str | None
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    canceled_by: str | None
    canceled_at: datetime | None


@dataclass(frozen=True)
class BundleVerificationProjectionRecord:
    bundle_id: str
    status: BundleVerificationProjectionStatus
    last_verification_run_id: str | None
    verified_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True)
class BundleVerificationRunRecord:
    id: str
    project_id: str
    bundle_id: str
    attempt_number: int
    supersedes_verification_run_id: str | None
    superseded_by_verification_run_id: str | None
    status: BundleVerificationRunStatus
    result_json: dict[str, object]
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    canceled_by: str | None
    canceled_at: datetime | None
    failure_reason: str | None


@dataclass(frozen=True)
class BundleValidationProjectionRecord:
    bundle_id: str
    profile_id: str
    status: BundleValidationProjectionStatus
    last_validation_run_id: str | None
    ready_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True)
class BundleValidationRunRecord:
    id: str
    project_id: str
    bundle_id: str
    profile_id: str
    profile_snapshot_key: str
    profile_snapshot_sha256: str
    status: BundleValidationRunStatus
    attempt_number: int
    supersedes_validation_run_id: str | None
    superseded_by_validation_run_id: str | None
    result_json: dict[str, object]
    failure_reason: str | None
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    canceled_by: str | None
    canceled_at: datetime | None


@dataclass(frozen=True)
class BundleProfileRecord:
    id: str
    label: str
    description: str
    allowed_bundle_kinds: tuple[DepositBundleKind, ...]
    required_archive_entries: tuple[str, ...]
    required_metadata_paths: tuple[str, ...]
    forbidden_metadata_paths: tuple[str, ...]


@dataclass(frozen=True)
class BundleEventRecord:
    id: str
    bundle_id: str
    event_type: BundleEventType
    verification_run_id: str | None
    validation_run_id: str | None
    actor_user_id: str | None
    reason: str | None
    created_at: datetime
