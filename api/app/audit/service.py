import re
from dataclasses import asdict
from datetime import datetime
from functools import lru_cache
from typing import Any
from uuid import uuid4

from app.audit.context import current_request_id
from app.audit.models import (
    AuditEventRecord,
    AuditEventType,
    AuditIntegrityStatus,
    AuditRequestContext,
)
from app.audit.store import AuditEventNotFoundError, AuditStore, AuditStoreUnavailableError
from app.core.config import Settings, get_settings
from app.telemetry.service import get_telemetry_service

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "password",
    "secret",
    "raw",
    "content",
    "bytes",
)

_METADATA_ALLOWLIST: dict[AuditEventType, set[str]] = {
    "USER_LOGIN": {"auth_method", "auth_source", "session_id"},
    "USER_LOGOUT": {"auth_source", "session_id"},
    "AUTH_FAILED": {"reason", "auth_source", "route", "status_code"},
    "PROJECT_CREATED": {
        "project_name",
        "intended_access_tier",
        "baseline_policy_snapshot_id",
    },
    "PROJECT_MEMBER_ADDED": {"member_user_id", "member_role"},
    "PROJECT_MEMBER_REMOVED": {"member_user_id", "member_role"},
    "PROJECT_MEMBER_ROLE_CHANGED": {
        "member_user_id",
        "previous_role",
        "new_role",
    },
    "BASELINE_POLICY_SNAPSHOT_SEEDED": {
        "snapshot_id",
        "seeded_by",
    },
    "PROJECT_BASELINE_POLICY_ATTACHED": {
        "project_id",
        "baseline_policy_snapshot_id",
    },
    "AUDIT_LOG_VIEWED": {
        "project_filter",
        "actor_filter",
        "event_type_filter",
        "from",
        "to",
        "cursor",
        "returned_count",
    },
    "AUDIT_EVENT_VIEWED": {"viewed_event_id", "viewed_event_type"},
    "MY_ACTIVITY_VIEWED": {"returned_count"},
    "OUTBOUND_CALL_BLOCKED": {"method", "url", "host", "purpose", "reason"},
    "EXPORT_STUB_ROUTE_ACCESSED": {
        "route",
        "method",
        "status_code",
        "stub_event_id",
    },
    "EXPORT_CANDIDATES_VIEWED": {"route", "returned_count"},
    "EXPORT_CANDIDATE_VIEWED": {"route", "candidate_kind", "source_phase"},
    "EXPORT_RELEASE_PACK_VIEWED": {
        "route",
        "risk_classification",
        "review_path",
        "reason_codes",
        "request_revision",
        "release_pack_sha256",
    },
    "EXPORT_REQUEST_SUBMITTED": {
        "route",
        "candidate_snapshot_id",
        "request_revision",
        "risk_classification",
        "review_path",
        "requires_second_review",
        "release_pack_sha256",
    },
    "EXPORT_HISTORY_VIEWED": {
        "route",
        "status_filter",
        "requester_id_filter",
        "candidate_kind_filter",
        "cursor",
        "returned_count",
    },
    "EXPORT_REQUEST_VIEWED": {"route", "status", "request_revision"},
    "EXPORT_REQUEST_STATUS_VIEWED": {"route", "status", "request_revision"},
    "EXPORT_REQUEST_EVENTS_VIEWED": {"route", "returned_count"},
    "EXPORT_REQUEST_REVIEWS_VIEWED": {"route", "returned_count"},
    "EXPORT_REQUEST_REVIEW_EVENTS_VIEWED": {"route", "returned_count"},
    "EXPORT_REQUEST_RECEIPT_VIEWED": {"route", "attempt_number"},
    "EXPORT_REQUEST_RECEIPTS_VIEWED": {"route", "returned_count"},
    "EXPORT_REVIEW_QUEUE_VIEWED": {
        "route",
        "status_filter",
        "aging_bucket_filter",
        "reviewer_user_id_filter",
        "returned_count",
        "read_only",
    },
    "EXPORT_REQUEST_RESUBMITTED": {
        "route",
        "supersedes_export_request_id",
        "candidate_snapshot_id",
        "request_revision",
        "risk_classification",
        "review_path",
        "requires_second_review",
        "release_pack_sha256",
    },
    "EXPORT_REQUEST_REVIEW_CLAIMED": {
        "route",
        "review_id",
        "review_stage",
        "review_etag",
    },
    "EXPORT_REQUEST_REVIEW_RELEASED": {
        "route",
        "released_review_id",
        "review_stage",
    },
    "EXPORT_REQUEST_REVIEW_STARTED": {
        "route",
        "review_id",
        "review_stage",
        "review_etag",
    },
    "EXPORT_REQUEST_RETURNED": {"route", "review_id", "decision_reason"},
    "EXPORT_REQUEST_APPROVED": {"route", "review_id", "decision_reason"},
    "EXPORT_REQUEST_REJECTED": {"route", "review_id", "decision_reason"},
    "EXPORT_REQUEST_EXPORTED": {"route", "attempt_number", "receipt_sha256"},
    "EXPORT_PROVENANCE_VIEWED": {"route", "current_proof_id", "proof_attempt_count"},
    "EXPORT_PROVENANCE_PROOFS_VIEWED": {"route", "returned_count"},
    "EXPORT_PROVENANCE_PROOF_VIEWED": {"route", "proof_id", "attempt_number", "current"},
    "EXPORT_PROVENANCE_PROOF_REGENERATED": {
        "route",
        "proof_id",
        "attempt_number",
        "supersedes_proof_id",
    },
    "BUNDLE_LIST_VIEWED": {"route", "returned_count"},
    "BUNDLE_BUILD_RUN_CREATED": {
        "route",
        "bundle_id",
        "bundle_kind",
        "status",
        "attempt_number",
        "export_request_id",
        "supersedes_bundle_id",
        "requested_from_bundle_id",
    },
    "BUNDLE_BUILD_RUN_STARTED": {"route", "bundle_id", "status"},
    "BUNDLE_BUILD_RUN_FINISHED": {"route", "bundle_id", "status"},
    "BUNDLE_BUILD_RUN_FAILED": {"route", "bundle_id", "status", "reason"},
    "BUNDLE_BUILD_RUN_CANCELED": {"route", "bundle_id", "bundle_kind", "status", "attempt_number"},
    "BUNDLE_DETAIL_VIEWED": {"route", "bundle_id", "bundle_kind", "status", "attempt_number"},
    "BUNDLE_STATUS_VIEWED": {"route", "bundle_id", "bundle_kind", "status"},
    "BUNDLE_EVENTS_VIEWED": {"route", "bundle_id", "returned_count"},
    "BUNDLE_VERIFICATION_RUN_CREATED": {"route", "bundle_id", "verification_run_id"},
    "BUNDLE_VERIFICATION_RUN_STARTED": {"route", "bundle_id", "verification_run_id"},
    "BUNDLE_VERIFICATION_RUN_FINISHED": {"route", "bundle_id", "verification_run_id"},
    "BUNDLE_VERIFICATION_RUN_FAILED": {"route", "bundle_id", "verification_run_id", "reason"},
    "BUNDLE_VERIFICATION_RUN_CANCELED": {"route", "bundle_id", "verification_run_id"},
    "BUNDLE_VERIFICATION_VIEWED": {"route", "bundle_id", "returned_count"},
    "BUNDLE_VERIFICATION_STATUS_VIEWED": {"route", "bundle_id", "status"},
    "BUNDLE_PROFILES_VIEWED": {"route", "bundle_id", "returned_count"},
    "BUNDLE_VALIDATION_RUN_CREATED": {"route", "bundle_id", "validation_run_id", "profile_id"},
    "BUNDLE_VALIDATION_RUN_STARTED": {"route", "bundle_id", "validation_run_id", "profile_id"},
    "BUNDLE_VALIDATION_RUN_FINISHED": {"route", "bundle_id", "validation_run_id", "profile_id"},
    "BUNDLE_VALIDATION_RUN_FAILED": {
        "route",
        "bundle_id",
        "validation_run_id",
        "profile_id",
        "reason",
    },
    "BUNDLE_VALIDATION_RUN_CANCELED": {"route", "bundle_id", "validation_run_id", "profile_id"},
    "BUNDLE_VALIDATION_VIEWED": {"route", "bundle_id", "returned_count", "profile_id"},
    "BUNDLE_VALIDATION_STATUS_VIEWED": {"route", "bundle_id", "status", "profile_id"},
    "ADMIN_SECURITY_STATUS_VIEWED": {"csp_mode", "egress_deny_test"},
    "ACCESS_DENIED": {"route", "required_roles", "status_code"},
    "JOB_LIST_VIEWED": {"cursor", "returned_count"},
    "JOB_RUN_CREATED": {"job_type", "status", "attempt_number", "retry_of_job_id"},
    "JOB_RUN_STARTED": {"job_type", "status", "attempt_number", "worker_id"},
    "JOB_RUN_FINISHED": {"job_type", "status", "worker_id"},
    "JOB_RUN_FAILED": {"job_type", "status", "worker_id", "attempts", "max_attempts"},
    "JOB_RUN_CANCELED": {"job_type", "status", "worker_id", "mode"},
    "JOB_RUN_VIEWED": {"status", "cursor", "returned_count"},
    "JOB_RUN_STATUS_VIEWED": {"status"},
    "INDEX_ACTIVE_VIEWED": {
        "route",
        "active_search_index_id",
        "active_entity_index_id",
        "active_derivative_index_id",
    },
    "SEARCH_INDEX_LIST_VIEWED": {"route", "returned_count"},
    "SEARCH_INDEX_DETAIL_VIEWED": {"route", "index_id", "status", "version"},
    "SEARCH_INDEX_STATUS_VIEWED": {"route", "index_id", "status"},
    "SEARCH_INDEX_RUN_CREATED": {"route", "index_id", "status", "version", "reason"},
    "SEARCH_INDEX_RUN_STARTED": {"route", "index_id", "index_kind", "status", "version"},
    "SEARCH_INDEX_RUN_FINISHED": {"route", "index_id", "index_kind", "status", "version"},
    "SEARCH_INDEX_RUN_FAILED": {
        "route",
        "index_id",
        "index_kind",
        "status",
        "version",
        "reason",
    },
    "SEARCH_INDEX_RUN_CANCELED": {"route", "index_id", "status", "version", "mode"},
    "ENTITY_INDEX_LIST_VIEWED": {"route", "returned_count"},
    "ENTITY_INDEX_DETAIL_VIEWED": {"route", "index_id", "status", "version"},
    "ENTITY_INDEX_STATUS_VIEWED": {"route", "index_id", "status"},
    "ENTITY_INDEX_RUN_CREATED": {"route", "index_id", "status", "version", "reason"},
    "ENTITY_INDEX_RUN_STARTED": {"route", "index_id", "index_kind", "status", "version"},
    "ENTITY_INDEX_RUN_FINISHED": {"route", "index_id", "index_kind", "status", "version"},
    "ENTITY_INDEX_RUN_FAILED": {
        "route",
        "index_id",
        "index_kind",
        "status",
        "version",
        "reason",
    },
    "ENTITY_INDEX_RUN_CANCELED": {"route", "index_id", "status", "version", "mode"},
    "DERIVATIVE_INDEX_LIST_VIEWED": {"route", "returned_count"},
    "DERIVATIVE_INDEX_DETAIL_VIEWED": {"route", "index_id", "status", "version"},
    "DERIVATIVE_INDEX_STATUS_VIEWED": {"route", "index_id", "status"},
    "DERIVATIVE_INDEX_RUN_CREATED": {"route", "index_id", "status", "version", "reason"},
    "DERIVATIVE_INDEX_RUN_STARTED": {
        "route",
        "index_id",
        "index_kind",
        "status",
        "version",
    },
    "DERIVATIVE_INDEX_RUN_FINISHED": {
        "route",
        "index_id",
        "index_kind",
        "status",
        "version",
    },
    "DERIVATIVE_INDEX_RUN_FAILED": {
        "route",
        "index_id",
        "index_kind",
        "status",
        "version",
        "reason",
    },
    "DERIVATIVE_INDEX_RUN_CANCELED": {"route", "index_id", "status", "version", "mode"},
    "SEARCH_RESULT_OPENED": {
        "route",
        "search_index_id",
        "document_id",
        "run_id",
        "page_number",
        "line_id",
        "token_id",
        "source_kind",
        "source_ref_id",
    },
    "ENTITY_LIST_VIEWED": {
        "route",
        "entity_index_id",
        "returned_count",
        "cursor",
        "query",
        "entity_type_filter",
    },
    "ENTITY_DETAIL_VIEWED": {
        "route",
        "entity_index_id",
        "entity_id",
    },
    "ENTITY_OCCURRENCES_VIEWED": {
        "route",
        "entity_index_id",
        "entity_id",
        "returned_count",
        "cursor",
    },
    "DOCUMENT_LIBRARY_VIEWED": {
        "cursor",
        "returned_count",
        "status_filter",
        "sort",
        "direction",
        "query",
    },
    "DOCUMENT_DETAIL_VIEWED": {"route"},
    "DOCUMENT_TIMELINE_VIEWED": {"returned_count", "limit"},
    "DOCUMENT_UPLOAD_STARTED": {
        "route",
        "import_id",
        "document_id",
        "original_filename",
    },
    "DOCUMENT_STORED": {
        "import_id",
        "document_id",
        "stored_filename",
        "source_meta_key",
        "detected_type",
        "byte_count",
        "sha256_prefix",
    },
    "DOCUMENT_SCAN_STARTED": {"import_id", "document_id"},
    "DOCUMENT_UPLOAD_CANCELED": {
        "route",
        "import_id",
        "document_id",
    },
    "DOCUMENT_SCAN_PASSED": {"import_id", "document_id"},
    "DOCUMENT_SCAN_REJECTED": {"import_id", "document_id", "reason"},
    "DOCUMENT_IMPORT_FAILED": {
        "import_id",
        "document_id",
        "stage",
        "reason",
    },
    "DOCUMENT_PAGE_EXTRACTION_STARTED": {"document_id", "run_kind", "run_id"},
    "DOCUMENT_PAGE_EXTRACTION_COMPLETED": {
        "document_id",
        "run_kind",
        "run_id",
        "page_count",
    },
    "DOCUMENT_PAGE_EXTRACTION_FAILED": {
        "document_id",
        "run_kind",
        "run_id",
        "reason",
    },
    "DOCUMENT_PAGE_EXTRACTION_RETRY_REQUESTED": {
        "route",
        "document_id",
        "run_id",
        "supersedes_processing_run_id",
        "attempt_number",
    },
    "DOCUMENT_PROCESSING_RUN_VIEWED": {"route"},
    "DOCUMENT_PROCESSING_RUN_STATUS_VIEWED": {"route"},
    "PREPROCESS_OVERVIEW_VIEWED": {"route", "active_run_id", "returned_count"},
    "PREPROCESS_QUALITY_VIEWED": {
        "route",
        "run_id",
        "warning_filter",
        "status_filter",
        "cursor",
        "returned_count",
    },
    "PREPROCESS_RUNS_VIEWED": {
        "route",
        "cursor",
        "returned_count",
        "base_run_id",
        "candidate_run_id",
    },
    "PREPROCESS_COMPARE_VIEWED": {
        "route",
        "base_run_id",
        "candidate_run_id",
        "returned_count",
    },
    "PREPROCESS_ACTIVE_RUN_VIEWED": {"route", "run_id"},
    "PREPROCESS_RUN_VIEWED": {"route", "cursor", "returned_count"},
    "PREPROCESS_RUN_STATUS_VIEWED": {"route"},
    "PREPROCESS_RUN_CREATED": {
        "route",
        "run_id",
        "document_id",
        "params_hash",
        "pipeline_version",
    },
    "PREPROCESS_RUN_STARTED": {"run_id", "document_id", "pipeline_version"},
    "PREPROCESS_RUN_FINISHED": {"run_id", "document_id", "status"},
    "PREPROCESS_RUN_FAILED": {"run_id", "document_id", "reason"},
    "PREPROCESS_RUN_CANCELED": {"route", "run_id"},
    "PREPROCESS_RUN_ACTIVATED": {"route", "run_id", "document_id"},
    "PREPROCESS_VARIANT_ACCESSED": {"document_id", "page_id", "variant", "run_id"},
    "TRANSCRIPTION_OVERVIEW_VIEWED": {"route", "active_run_id", "returned_count"},
    "TRANSCRIPTION_TRIAGE_VIEWED": {
        "route",
        "run_id",
        "cursor",
        "status_filter",
        "confidence_below",
        "page",
        "returned_count",
    },
    "TRANSCRIPTION_TRIAGE_ASSIGNMENT_UPDATED": {
        "route",
        "run_id",
        "page_id",
        "reviewer_user_id",
    },
    "TRANSCRIPTION_RUN_CREATED": {
        "route",
        "run_id",
        "document_id",
        "engine",
        "model_id",
        "pipeline_version",
    },
    "TRANSCRIPTION_RUN_STARTED": {"run_id", "document_id", "pipeline_version"},
    "TRANSCRIPTION_RUN_FINISHED": {"run_id", "document_id", "status"},
    "TRANSCRIPTION_RUN_FAILED": {"run_id", "document_id", "reason"},
    "TRANSCRIPTION_RUN_CANCELED": {"route", "run_id"},
    "TRANSCRIPTION_RUN_VIEWED": {
        "route",
        "cursor",
        "returned_count",
        "run_id",
        "document_id",
    },
    "TRANSCRIPTION_RUN_STATUS_VIEWED": {"route"},
    "TRANSCRIPTION_ACTIVE_RUN_VIEWED": {"route", "run_id"},
    "TRANSCRIPTION_RESCUE_STATUS_VIEWED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "page_count",
        "rescue_source_count",
        "readiness_state",
        "blocker_count",
        "ready_for_activation",
    },
    "TRANSCRIPTION_RESCUE_RESOLUTION_UPDATED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "resolution_status",
        "readiness_state",
    },
    "TRANSCRIPTION_RUN_ACTIVATION_BLOCKED": {
        "route",
        "run_id",
        "document_id",
        "reason",
        "blocker_codes",
        "blocker_count",
    },
    "TRANSCRIPTION_RUN_ACTIVATED": {"route", "run_id", "document_id"},
    "TRANSCRIPTION_WORKSPACE_VIEWED": {
        "route",
        "run_id",
        "document_id",
        "page_id",
        "line_id",
        "token_id",
        "source_kind",
        "source_ref_id",
    },
    "TRANSCRIPTION_RUN_COMPARE_VIEWED": {
        "route",
        "base_run_id",
        "candidate_run_id",
        "page_count",
        "page",
        "line_id",
        "token_id",
        "compare_decision_snapshot_hash",
        "compare_decision_count",
        "compare_decision_event_count",
    },
    "TRANSCRIPTION_COMPARE_DECISION_RECORDED": {
        "route",
        "document_id",
        "base_run_id",
        "candidate_run_id",
        "page_id",
        "line_id",
        "token_id",
        "decision",
        "decision_etag",
    },
    "TRANSCRIPTION_COMPARE_FINALIZED": {
        "route",
        "document_id",
        "base_run_id",
        "candidate_run_id",
        "composed_run_id",
        "compare_decision_snapshot_hash",
        "page_scope_count",
    },
    "TRANSCRIPT_LINE_CORRECTED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "line_id",
        "transcript_version_id",
        "version_etag",
        "token_anchor_status",
    },
    "TRANSCRIPT_LINE_VERSION_HISTORY_VIEWED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "line_id",
        "version_count",
    },
    "TRANSCRIPT_LINE_VERSION_VIEWED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "line_id",
        "version_id",
        "source_type",
    },
    "TRANSCRIPT_EDIT_CONFLICT_DETECTED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "line_id",
        "version_etag",
    },
    "TRANSCRIPT_DOWNSTREAM_INVALIDATED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "line_id",
        "downstream_state",
        "reason",
    },
    "TRANSCRIPT_VARIANT_LAYER_VIEWED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "variant_kind",
        "returned_count",
    },
    "TRANSCRIPT_ASSIST_DECISION_RECORDED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "suggestion_id",
        "variant_layer_id",
        "decision",
        "from_status",
        "to_status",
    },
    "PRIVACY_OVERVIEW_VIEWED": {"route", "active_run_id", "returned_count"},
    "PRIVACY_TRIAGE_VIEWED": {
        "route",
        "run_id",
        "cursor",
        "returned_count",
        "category",
        "unresolved_only",
        "direct_identifiers_only",
    },
    "PRIVACY_WORKSPACE_VIEWED": {
        "route",
        "run_id",
        "document_id",
        "page_id",
        "finding_id",
        "line_id",
        "token_id",
    },
    "PRIVACY_RUN_VIEWED": {"route", "run_id", "document_id"},
    "REDACTION_RUN_CREATED": {
        "route",
        "run_id",
        "document_id",
        "run_kind",
        "detectors_version",
    },
    "REDACTION_RUN_STARTED": {"run_id", "document_id", "pipeline_version"},
    "REDACTION_RUN_FINISHED": {"run_id", "document_id", "status"},
    "REDACTION_RUN_FAILED": {"run_id", "document_id", "reason"},
    "REDACTION_RUN_CANCELED": {"route", "run_id", "document_id"},
    "REDACTION_ACTIVE_RUN_VIEWED": {"route", "run_id"},
    "REDACTION_RUN_ACTIVATED": {"route", "run_id", "document_id"},
    "REDACTION_RUN_STATUS_VIEWED": {
        "route",
        "run_id",
        "document_id",
        "status",
    },
    "REDACTION_RUN_REVIEW_VIEWED": {"route", "run_id", "review_status"},
    "REDACTION_RUN_REVIEW_OPENED": {"route", "run_id", "review_status"},
    "REDACTION_RUN_REVIEW_CHANGES_REQUESTED": {"route", "run_id", "review_status"},
    "REDACTION_RUN_REVIEW_COMPLETED": {"route", "run_id", "review_status"},
    "REDACTION_RUN_EVENTS_VIEWED": {"route", "run_id", "returned_count"},
    "REDACTION_PAGE_REVIEW_UPDATED": {
        "route",
        "run_id",
        "page_id",
        "review_status",
        "review_etag",
    },
    "REDACTION_PAGE_REVIEW_VIEWED": {
        "route",
        "run_id",
        "page_id",
        "review_status",
    },
    "REDACTION_PAGE_EVENTS_VIEWED": {
        "route",
        "run_id",
        "page_id",
        "returned_count",
    },
    "REDACTION_FINDING_DECISION_CHANGED": {
        "route",
        "run_id",
        "page_id",
        "finding_id",
        "decision_status",
        "decision_etag",
    },
    "REDACTION_COMPARE_VIEWED": {
        "route",
        "base_run_id",
        "candidate_run_id",
        "changed_page_count",
        "changed_decision_count",
    },
    "POLICY_RUN_COMPARE_VIEWED": {
        "route",
        "base_run_id",
        "candidate_run_id",
        "changed_page_count",
        "changed_decision_count",
        "comparison_only_candidate",
        "warning_count",
    },
    "POLICY_RERUN_REQUESTED": {
        "route",
        "source_run_id",
        "candidate_run_id",
        "document_id",
        "policy_id",
        "policy_family_id",
        "policy_version",
    },
    "REDACTION_RUN_OUTPUT_VIEWED": {
        "route",
        "run_id",
        "status",
        "review_status",
        "readiness_state",
        "downstream_ready",
    },
    "REDACTION_RUN_OUTPUT_STATUS_VIEWED": {
        "route",
        "run_id",
        "status",
        "review_status",
        "readiness_state",
        "downstream_ready",
    },
    "GOVERNANCE_OVERVIEW_VIEWED": {
        "route",
        "active_run_id",
        "total_runs",
        "ready_runs",
    },
    "GOVERNANCE_RUNS_VIEWED": {"route", "active_run_id", "returned_count"},
    "GOVERNANCE_RUN_VIEWED": {
        "route",
        "run_id",
        "manifest_attempt_count",
        "ledger_attempt_count",
        "readiness_status",
    },
    "GOVERNANCE_EVENTS_VIEWED": {"route", "run_id", "returned_count"},
    "REDACTION_MANIFEST_VIEWED": {
        "route",
        "run_id",
        "status",
        "latest_attempt_id",
        "attempt_count",
        "readiness_status",
    },
    "REDACTION_LEDGER_VIEWED": {
        "route",
        "run_id",
        "status",
        "latest_attempt_id",
        "attempt_count",
        "readiness_status",
        "ledger_verification_status",
    },
    "SAFEGUARDED_PREVIEW_REGENERATED": {"route", "run_id", "page_id", "reason"},
    "SAFEGUARDED_PREVIEW_STATUS_VIEWED": {"route", "run_id", "page_id", "status"},
    "SAFEGUARDED_PREVIEW_ACCESSED": {
        "route",
        "run_id",
        "page_id",
        "not_modified",
    },
    "SAFEGUARDED_PREVIEW_VIEWED": {"route", "run_id", "page_id", "media_type"},
    "APPROVED_MODEL_LIST_VIEWED": {"route", "model_role", "status", "returned_count"},
    "APPROVED_MODEL_CREATED": {
        "route",
        "approved_model_id",
        "model_type",
        "model_role",
        "model_family",
        "model_version",
    },
    "PROJECT_MODEL_ASSIGNMENT_CREATED": {
        "route",
        "assignment_id",
        "model_role",
        "approved_model_id",
        "status",
    },
    "MODEL_ASSIGNMENT_LIST_VIEWED": {"route", "returned_count"},
    "MODEL_ASSIGNMENT_DETAIL_VIEWED": {"route", "assignment_id"},
    "TRAINING_DATASET_VIEWED": {"route", "assignment_id", "returned_count"},
    "PROJECT_MODEL_ACTIVATED": {
        "route",
        "assignment_id",
        "model_role",
        "approved_model_id",
        "status",
    },
    "PROJECT_MODEL_RETIRED": {
        "route",
        "assignment_id",
        "model_role",
        "approved_model_id",
        "status",
    },
    "POLICY_CREATED": {
        "route",
        "policy_id",
        "policy_family_id",
        "policy_version",
        "status",
        "rollback_anchor_policy_id",
        "rollback_from_policy_id",
    },
    "POLICY_LIST_VIEWED": {"route", "returned_count"},
    "POLICY_ACTIVE_VIEWED": {"route", "active_policy_id"},
    "POLICY_DETAIL_VIEWED": {"route", "policy_id"},
    "POLICY_EVENTS_VIEWED": {"route", "policy_id", "returned_count"},
    "POLICY_LINEAGE_VIEWED": {
        "route",
        "policy_id",
        "lineage_count",
        "event_count",
        "active_policy_differs",
    },
    "POLICY_USAGE_VIEWED": {
        "route",
        "policy_id",
        "run_count",
        "manifest_count",
        "ledger_count",
        "pseudonym_entry_count",
    },
    "POLICY_EXPLAINABILITY_VIEWED": {
        "route",
        "policy_id",
        "category_rule_count",
        "trace_count",
        "reviewer_explanation_mode",
    },
    "POLICY_SNAPSHOT_VIEWED": {
        "route",
        "policy_id",
        "rules_sha256",
        "rules_snapshot_key",
        "source_event_type",
    },
    "POLICY_UPDATED": {
        "route",
        "policy_id",
        "policy_version",
        "version_etag",
    },
    "POLICY_VALIDATION_REQUESTED": {
        "route",
        "policy_id",
        "validation_status",
        "issue_count",
    },
    "POLICY_ACTIVATED": {
        "route",
        "policy_id",
        "policy_family_id",
        "policy_version",
        "status",
    },
    "POLICY_RETIRED": {
        "route",
        "policy_id",
        "policy_family_id",
        "policy_version",
        "status",
    },
    "POLICY_COMPARE_VIEWED": {
        "route",
        "policy_id",
        "against_policy_id",
        "against_baseline_snapshot_id",
        "difference_count",
    },
    "PSEUDONYM_REGISTRY_VIEWED": {"route", "returned_count"},
    "PSEUDONYM_REGISTRY_ENTRY_VIEWED": {"route", "entry_id"},
    "PSEUDONYM_REGISTRY_EVENTS_VIEWED": {"route", "entry_id", "returned_count"},
    "LAYOUT_OVERVIEW_VIEWED": {"route", "active_run_id", "returned_count"},
    "LAYOUT_TRIAGE_VIEWED": {
        "route",
        "run_id",
        "cursor",
        "status_filter",
        "page_recall_status_filter",
        "returned_count",
    },
    "LAYOUT_RUNS_VIEWED": {"route", "cursor", "returned_count"},
    "LAYOUT_ACTIVE_RUN_VIEWED": {"route", "run_id"},
    "LAYOUT_RUN_CREATED": {
        "route",
        "run_id",
        "document_id",
        "input_preprocess_run_id",
        "params_hash",
        "pipeline_version",
    },
    "LAYOUT_RUN_ACTIVATED": {"route", "run_id", "document_id"},
    "LAYOUT_ACTIVATION_BLOCKED": {"route", "run_id", "document_id", "reason"},
    "LAYOUT_RUN_STARTED": {"run_id", "document_id", "pipeline_version"},
    "LAYOUT_RUN_FINISHED": {"run_id", "document_id", "status"},
    "LAYOUT_RUN_FAILED": {"run_id", "document_id", "reason"},
    "LAYOUT_RUN_CANCELED": {"route", "run_id"},
    "LAYOUT_RECALL_STATUS_VIEWED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "page_recall_status",
        "unresolved_count",
    },
    "LAYOUT_RESCUE_CANDIDATES_VIEWED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "returned_count",
    },
    "LAYOUT_OVERLAY_ACCESSED": {"document_id", "page_id", "run_id"},
    "LAYOUT_PAGEXML_ACCESSED": {"document_id", "page_id", "run_id"},
    "LAYOUT_LINE_ARTIFACTS_VIEWED": {"document_id", "run_id", "page_id", "line_id"},
    "LAYOUT_LINE_CROP_ACCESSED": {
        "document_id",
        "run_id",
        "page_id",
        "line_id",
        "variant",
    },
    "LAYOUT_CONTEXT_WINDOW_ACCESSED": {"document_id", "run_id", "page_id", "line_id"},
    "LAYOUT_THUMBNAIL_ACCESSED": {"document_id", "run_id", "page_id"},
    "LAYOUT_READING_ORDER_UPDATED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "layout_version_id",
        "version_etag",
        "mode",
        "group_count",
        "order_withheld",
        "ambiguity_score",
        "source",
    },
    "LAYOUT_EDIT_APPLIED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "layout_version_id",
        "version_etag",
        "operations_applied",
        "operation_kinds",
    },
    "LAYOUT_DOWNSTREAM_INVALIDATED": {
        "route",
        "document_id",
        "run_id",
        "page_id",
        "layout_version_id",
        "downstream_state",
        "reason",
    },
    "PAGE_METADATA_VIEWED": {"document_id", "page_id"},
    "PAGE_IMAGE_VIEWED": {"document_id", "page_id", "variant"},
    "PAGE_THUMBNAIL_VIEWED": {"document_id", "page_id", "variant"},
    "OPERATIONS_OVERVIEW_VIEWED": {"returned_count"},
    "OPERATIONS_EXPORT_STATUS_VIEWED": {
        "open_request_count",
        "overdue_count",
        "escalation_due_count",
        "retention_pending_count",
    },
    "OPERATIONS_SLOS_VIEWED": {"returned_count"},
    "OPERATIONS_ALERTS_VIEWED": {"state_filter", "cursor", "returned_count"},
    "OPERATIONS_TIMELINE_VIEWED": {"scope_filter", "cursor", "returned_count"},
}


def _sanitize_text(value: str, *, max_length: int = 512) -> str:
    collapsed = _CONTROL_CHARS_RE.sub(" ", value)
    collapsed = collapsed.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    collapsed = " ".join(collapsed.split())
    return collapsed[:max_length]


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _sanitize_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_value(entry) for entry in value[:20]]
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for raw_key, raw_value in list(value.items())[:20]:
            key = _sanitize_text(str(raw_key), max_length=64)
            if _is_sensitive_key(key):
                continue
            sanitized[key] = _sanitize_value(raw_value)
        return sanitized
    return _sanitize_text(str(value))


def _sanitize_metadata(
    *,
    event_type: AuditEventType,
    metadata: dict[str, object] | None,
) -> dict[str, object]:
    if metadata is None:
        return {}
    allowed = _METADATA_ALLOWLIST[event_type]
    sanitized: dict[str, object] = {}
    for raw_key, raw_value in metadata.items():
        key = _sanitize_text(raw_key, max_length=64)
        if key not in allowed:
            continue
        if _is_sensitive_key(key):
            continue
        sanitized[key] = _sanitize_value(raw_value)
    return sanitized


class AuditService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: AuditStore | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or AuditStore(settings)

    def record_event(
        self,
        *,
        event_type: AuditEventType,
        actor_user_id: str | None,
        project_id: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        metadata: dict[str, object] | None = None,
        request_context: AuditRequestContext | None = None,
        request_id: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEventRecord:
        context = request_context
        resolved_request_id = (
            request_id
            or (context.request_id if context else None)
            or current_request_id()
            or str(uuid4())
        )
        resolved_ip = ip if ip is not None else (context.ip if context else None)
        resolved_user_agent = (
            user_agent if user_agent is not None else (context.user_agent if context else None)
        )

        sanitized_metadata = _sanitize_metadata(event_type=event_type, metadata=metadata)
        sanitized_object_type = _sanitize_text(object_type, max_length=100) if object_type else None
        sanitized_object_id = _sanitize_text(object_id, max_length=128) if object_id else None
        sanitized_project_id = _sanitize_text(project_id, max_length=128) if project_id else None
        sanitized_ip = _sanitize_text(resolved_ip, max_length=64) if resolved_ip else None
        sanitized_user_agent = (
            _sanitize_text(resolved_user_agent, max_length=320) if resolved_user_agent else None
        )

        telemetry_service = get_telemetry_service()

        try:
            record = self._store.append_event(
                actor_user_id=actor_user_id,
                project_id=sanitized_project_id,
                event_type=event_type,
                object_type=sanitized_object_type,
                object_id=sanitized_object_id,
                ip=sanitized_ip,
                user_agent=sanitized_user_agent,
                request_id=resolved_request_id,
                metadata_json=sanitized_metadata,
            )
        except AuditStoreUnavailableError:
            telemetry_service.record_audit_write(success=False, event_type=event_type)
            raise

        telemetry_service.record_audit_write(success=True, event_type=event_type)
        return record

    def record_event_best_effort(
        self,
        *,
        event_type: AuditEventType,
        actor_user_id: str | None,
        project_id: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        metadata: dict[str, object] | None = None,
        request_context: AuditRequestContext | None = None,
        request_id: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEventRecord | None:
        try:
            return self.record_event(
                event_type=event_type,
                actor_user_id=actor_user_id,
                project_id=project_id,
                object_type=object_type,
                object_id=object_id,
                metadata=metadata,
                request_context=request_context,
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
            )
        except AuditStoreUnavailableError:
            return None

    def list_events(
        self,
        *,
        project_id: str | None,
        actor_user_id: str | None,
        event_type: AuditEventType | None,
        from_timestamp: datetime | None,
        to_timestamp: datetime | None,
        cursor: int,
        page_size: int,
    ) -> tuple[list[AuditEventRecord], int | None]:
        return self._store.list_events(
            project_id=project_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            cursor=cursor,
            page_size=page_size,
        )

    def get_event(self, *, event_id: str) -> AuditEventRecord:
        return self._store.get_event(event_id=event_id)

    def list_my_activity(
        self,
        *,
        actor_user_id: str,
        limit: int,
    ) -> list[AuditEventRecord]:
        return self._store.list_user_activity(actor_user_id=actor_user_id, limit=limit)

    def verify_integrity(self) -> AuditIntegrityStatus:
        return self._store.verify_integrity()

    @staticmethod
    def as_record_payload(record: AuditEventRecord) -> dict[str, Any]:
        return asdict(record)

    @staticmethod
    def is_event_not_found(error: Exception) -> bool:
        return isinstance(error, AuditEventNotFoundError)


@lru_cache
def get_audit_service() -> AuditService:
    settings = get_settings()
    return AuditService(settings=settings)
