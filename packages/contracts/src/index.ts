export type DeploymentEnvironment = "dev" | "staging" | "prod" | "test";

export type AccessTier = "CONTROLLED" | "SAFEGUARDED" | "OPEN";
export type PlatformRole = "ADMIN" | "AUDITOR";
export type ProjectRole = "PROJECT_LEAD" | "RESEARCHER" | "REVIEWER";
export type ProjectStatus = "ACTIVE" | "ARCHIVED";
export type AuditEventType =
  | "USER_LOGIN"
  | "USER_LOGOUT"
  | "AUTH_FAILED"
  | "PROJECT_CREATED"
  | "PROJECT_MEMBER_ADDED"
  | "PROJECT_MEMBER_REMOVED"
  | "PROJECT_MEMBER_ROLE_CHANGED"
  | "BASELINE_POLICY_SNAPSHOT_SEEDED"
  | "PROJECT_BASELINE_POLICY_ATTACHED"
  | "AUDIT_LOG_VIEWED"
  | "AUDIT_EVENT_VIEWED"
  | "MY_ACTIVITY_VIEWED"
  | "OUTBOUND_CALL_BLOCKED"
  | "EXPORT_STUB_ROUTE_ACCESSED"
  | "EXPORT_CANDIDATES_VIEWED"
  | "EXPORT_CANDIDATE_VIEWED"
  | "EXPORT_RELEASE_PACK_VIEWED"
  | "EXPORT_REQUEST_SUBMITTED"
  | "EXPORT_HISTORY_VIEWED"
  | "EXPORT_REQUEST_VIEWED"
  | "EXPORT_REQUEST_STATUS_VIEWED"
  | "EXPORT_REQUEST_EVENTS_VIEWED"
  | "EXPORT_REQUEST_REVIEWS_VIEWED"
  | "EXPORT_REQUEST_REVIEW_EVENTS_VIEWED"
  | "EXPORT_REQUEST_RECEIPT_VIEWED"
  | "EXPORT_REQUEST_RECEIPTS_VIEWED"
  | "EXPORT_REVIEW_QUEUE_VIEWED"
  | "EXPORT_REQUEST_RESUBMITTED"
  | "EXPORT_REQUEST_REVIEW_CLAIMED"
  | "EXPORT_REQUEST_REVIEW_RELEASED"
  | "EXPORT_REQUEST_REVIEW_STARTED"
  | "EXPORT_REQUEST_RETURNED"
  | "EXPORT_REQUEST_APPROVED"
  | "EXPORT_REQUEST_REJECTED"
  | "EXPORT_REQUEST_EXPORTED"
  | "EXPORT_PROVENANCE_VIEWED"
  | "EXPORT_PROVENANCE_PROOFS_VIEWED"
  | "EXPORT_PROVENANCE_PROOF_VIEWED"
  | "EXPORT_PROVENANCE_PROOF_REGENERATED"
  | "BUNDLE_LIST_VIEWED"
  | "BUNDLE_BUILD_RUN_CREATED"
  | "BUNDLE_BUILD_RUN_STARTED"
  | "BUNDLE_BUILD_RUN_FINISHED"
  | "BUNDLE_BUILD_RUN_FAILED"
  | "BUNDLE_BUILD_RUN_CANCELED"
  | "BUNDLE_DETAIL_VIEWED"
  | "BUNDLE_STATUS_VIEWED"
  | "BUNDLE_EVENTS_VIEWED"
  | "BUNDLE_VERIFICATION_RUN_CREATED"
  | "BUNDLE_VERIFICATION_RUN_STARTED"
  | "BUNDLE_VERIFICATION_RUN_FINISHED"
  | "BUNDLE_VERIFICATION_RUN_FAILED"
  | "BUNDLE_VERIFICATION_RUN_CANCELED"
  | "BUNDLE_VERIFICATION_VIEWED"
  | "BUNDLE_VERIFICATION_STATUS_VIEWED"
  | "BUNDLE_PROFILES_VIEWED"
  | "BUNDLE_VALIDATION_RUN_CREATED"
  | "BUNDLE_VALIDATION_RUN_STARTED"
  | "BUNDLE_VALIDATION_RUN_FINISHED"
  | "BUNDLE_VALIDATION_RUN_FAILED"
  | "BUNDLE_VALIDATION_RUN_CANCELED"
  | "BUNDLE_VALIDATION_VIEWED"
  | "BUNDLE_VALIDATION_STATUS_VIEWED"
  | "ADMIN_SECURITY_STATUS_VIEWED"
  | "ACCESS_DENIED"
  | "JOB_LIST_VIEWED"
  | "JOB_RUN_CREATED"
  | "JOB_RUN_STARTED"
  | "JOB_RUN_FINISHED"
  | "JOB_RUN_FAILED"
  | "JOB_RUN_CANCELED"
  | "JOB_RUN_VIEWED"
  | "JOB_RUN_STATUS_VIEWED"
  | "INDEX_ACTIVE_VIEWED"
  | "SEARCH_INDEX_LIST_VIEWED"
  | "SEARCH_INDEX_DETAIL_VIEWED"
  | "SEARCH_INDEX_STATUS_VIEWED"
  | "SEARCH_INDEX_RUN_CREATED"
  | "SEARCH_INDEX_RUN_STARTED"
  | "SEARCH_INDEX_RUN_FINISHED"
  | "SEARCH_INDEX_RUN_FAILED"
  | "SEARCH_INDEX_RUN_CANCELED"
  | "ENTITY_INDEX_LIST_VIEWED"
  | "ENTITY_INDEX_DETAIL_VIEWED"
  | "ENTITY_INDEX_STATUS_VIEWED"
  | "ENTITY_INDEX_RUN_CREATED"
  | "ENTITY_INDEX_RUN_STARTED"
  | "ENTITY_INDEX_RUN_FINISHED"
  | "ENTITY_INDEX_RUN_FAILED"
  | "ENTITY_INDEX_RUN_CANCELED"
  | "DERIVATIVE_INDEX_LIST_VIEWED"
  | "DERIVATIVE_INDEX_DETAIL_VIEWED"
  | "DERIVATIVE_INDEX_STATUS_VIEWED"
  | "DERIVATIVE_INDEX_RUN_CREATED"
  | "DERIVATIVE_INDEX_RUN_STARTED"
  | "DERIVATIVE_INDEX_RUN_FINISHED"
  | "DERIVATIVE_INDEX_RUN_FAILED"
  | "DERIVATIVE_INDEX_RUN_CANCELED"
  | "SEARCH_RESULT_OPENED"
  | "ENTITY_LIST_VIEWED"
  | "ENTITY_DETAIL_VIEWED"
  | "ENTITY_OCCURRENCES_VIEWED"
  | "DOCUMENT_LIBRARY_VIEWED"
  | "DOCUMENT_DETAIL_VIEWED"
  | "DOCUMENT_TIMELINE_VIEWED"
  | "DOCUMENT_UPLOAD_STARTED"
  | "DOCUMENT_STORED"
  | "DOCUMENT_SCAN_STARTED"
  | "DOCUMENT_UPLOAD_CANCELED"
  | "DOCUMENT_SCAN_PASSED"
  | "DOCUMENT_SCAN_REJECTED"
  | "DOCUMENT_IMPORT_FAILED"
  | "DOCUMENT_PAGE_EXTRACTION_STARTED"
  | "DOCUMENT_PAGE_EXTRACTION_COMPLETED"
  | "DOCUMENT_PAGE_EXTRACTION_FAILED"
  | "DOCUMENT_PAGE_EXTRACTION_RETRY_REQUESTED"
  | "DOCUMENT_PROCESSING_RUN_VIEWED"
  | "DOCUMENT_PROCESSING_RUN_STATUS_VIEWED"
  | "PREPROCESS_OVERVIEW_VIEWED"
  | "PREPROCESS_QUALITY_VIEWED"
  | "PREPROCESS_RUNS_VIEWED"
  | "PREPROCESS_ACTIVE_RUN_VIEWED"
  | "PREPROCESS_RUN_VIEWED"
  | "PREPROCESS_RUN_STATUS_VIEWED"
  | "PREPROCESS_RUN_CREATED"
  | "PREPROCESS_RUN_STARTED"
  | "PREPROCESS_RUN_FINISHED"
  | "PREPROCESS_RUN_FAILED"
  | "PREPROCESS_RUN_CANCELED"
  | "PREPROCESS_RUN_ACTIVATED"
  | "PREPROCESS_COMPARE_VIEWED"
  | "PREPROCESS_VARIANT_ACCESSED"
  | "TRANSCRIPTION_OVERVIEW_VIEWED"
  | "TRANSCRIPTION_TRIAGE_VIEWED"
  | "TRANSCRIPTION_TRIAGE_ASSIGNMENT_UPDATED"
  | "TRANSCRIPTION_RUN_CREATED"
  | "TRANSCRIPTION_RUN_STARTED"
  | "TRANSCRIPTION_RUN_FINISHED"
  | "TRANSCRIPTION_RUN_FAILED"
  | "TRANSCRIPTION_RUN_CANCELED"
  | "TRANSCRIPTION_RUN_VIEWED"
  | "TRANSCRIPTION_RUN_STATUS_VIEWED"
  | "TRANSCRIPTION_ACTIVE_RUN_VIEWED"
  | "TRANSCRIPTION_RESCUE_STATUS_VIEWED"
  | "TRANSCRIPTION_RESCUE_RESOLUTION_UPDATED"
  | "TRANSCRIPTION_RUN_ACTIVATION_BLOCKED"
  | "TRANSCRIPTION_RUN_ACTIVATED"
  | "TRANSCRIPTION_WORKSPACE_VIEWED"
  | "TRANSCRIPTION_RUN_COMPARE_VIEWED"
  | "TRANSCRIPTION_COMPARE_DECISION_RECORDED"
  | "TRANSCRIPTION_COMPARE_FINALIZED"
  | "TRANSCRIPT_LINE_CORRECTED"
  | "TRANSCRIPT_LINE_VERSION_HISTORY_VIEWED"
  | "TRANSCRIPT_LINE_VERSION_VIEWED"
  | "TRANSCRIPT_EDIT_CONFLICT_DETECTED"
  | "TRANSCRIPT_DOWNSTREAM_INVALIDATED"
  | "TRANSCRIPT_VARIANT_LAYER_VIEWED"
  | "TRANSCRIPT_ASSIST_DECISION_RECORDED"
  | "PRIVACY_OVERVIEW_VIEWED"
  | "PRIVACY_TRIAGE_VIEWED"
  | "PRIVACY_WORKSPACE_VIEWED"
  | "PRIVACY_RUN_VIEWED"
  | "REDACTION_RUN_CREATED"
  | "REDACTION_RUN_STARTED"
  | "REDACTION_RUN_FINISHED"
  | "REDACTION_RUN_FAILED"
  | "REDACTION_RUN_CANCELED"
  | "REDACTION_ACTIVE_RUN_VIEWED"
  | "REDACTION_RUN_ACTIVATED"
  | "REDACTION_RUN_STATUS_VIEWED"
  | "REDACTION_RUN_REVIEW_VIEWED"
  | "REDACTION_RUN_REVIEW_OPENED"
  | "REDACTION_RUN_REVIEW_CHANGES_REQUESTED"
  | "REDACTION_RUN_REVIEW_COMPLETED"
  | "REDACTION_RUN_EVENTS_VIEWED"
  | "REDACTION_PAGE_REVIEW_UPDATED"
  | "REDACTION_PAGE_REVIEW_VIEWED"
  | "REDACTION_PAGE_EVENTS_VIEWED"
  | "REDACTION_FINDING_DECISION_CHANGED"
  | "REDACTION_COMPARE_VIEWED"
  | "POLICY_RUN_COMPARE_VIEWED"
  | "POLICY_RERUN_REQUESTED"
  | "REDACTION_RUN_OUTPUT_VIEWED"
  | "REDACTION_RUN_OUTPUT_STATUS_VIEWED"
  | "GOVERNANCE_OVERVIEW_VIEWED"
  | "GOVERNANCE_RUNS_VIEWED"
  | "GOVERNANCE_RUN_VIEWED"
  | "GOVERNANCE_EVENTS_VIEWED"
  | "REDACTION_MANIFEST_VIEWED"
  | "REDACTION_LEDGER_VIEWED"
  | "SAFEGUARDED_PREVIEW_REGENERATED"
  | "SAFEGUARDED_PREVIEW_STATUS_VIEWED"
  | "SAFEGUARDED_PREVIEW_ACCESSED"
  | "SAFEGUARDED_PREVIEW_VIEWED"
  | "APPROVED_MODEL_LIST_VIEWED"
  | "APPROVED_MODEL_CREATED"
  | "PROJECT_MODEL_ASSIGNMENT_CREATED"
  | "MODEL_ASSIGNMENT_LIST_VIEWED"
  | "MODEL_ASSIGNMENT_DETAIL_VIEWED"
  | "TRAINING_DATASET_VIEWED"
  | "PROJECT_MODEL_ACTIVATED"
  | "PROJECT_MODEL_RETIRED"
  | "POLICY_CREATED"
  | "POLICY_LIST_VIEWED"
  | "POLICY_ACTIVE_VIEWED"
  | "POLICY_DETAIL_VIEWED"
  | "POLICY_EVENTS_VIEWED"
  | "POLICY_LINEAGE_VIEWED"
  | "POLICY_USAGE_VIEWED"
  | "POLICY_EXPLAINABILITY_VIEWED"
  | "POLICY_SNAPSHOT_VIEWED"
  | "POLICY_UPDATED"
  | "POLICY_VALIDATION_REQUESTED"
  | "POLICY_ACTIVATED"
  | "POLICY_RETIRED"
  | "POLICY_COMPARE_VIEWED"
  | "PSEUDONYM_REGISTRY_VIEWED"
  | "PSEUDONYM_REGISTRY_ENTRY_VIEWED"
  | "PSEUDONYM_REGISTRY_EVENTS_VIEWED"
  | "LAYOUT_OVERVIEW_VIEWED"
  | "LAYOUT_TRIAGE_VIEWED"
  | "LAYOUT_RUNS_VIEWED"
  | "LAYOUT_ACTIVE_RUN_VIEWED"
  | "LAYOUT_RUN_CREATED"
  | "LAYOUT_RUN_ACTIVATED"
  | "LAYOUT_RUN_STARTED"
  | "LAYOUT_RUN_FINISHED"
  | "LAYOUT_RUN_FAILED"
  | "LAYOUT_RUN_CANCELED"
  | "LAYOUT_READING_ORDER_UPDATED"
  | "LAYOUT_EDIT_APPLIED"
  | "LAYOUT_DOWNSTREAM_INVALIDATED"
  | "LAYOUT_OVERLAY_ACCESSED"
  | "LAYOUT_PAGEXML_ACCESSED"
  | "PAGE_METADATA_VIEWED"
  | "PAGE_IMAGE_VIEWED"
  | "PAGE_THUMBNAIL_VIEWED"
  | "OPERATIONS_OVERVIEW_VIEWED"
  | "OPERATIONS_EXPORT_STATUS_VIEWED"
  | "OPERATIONS_SLOS_VIEWED"
  | "OPERATIONS_ALERTS_VIEWED"
  | "OPERATIONS_TIMELINE_VIEWED";

export type ThemePreference = "system" | "dark" | "light";

export type ThemeMode = "dark" | "light";

export type ShellState = "Expanded" | "Balanced" | "Compact" | "Focus";

export interface ServiceHealthPayload {
  service: "api";
  status: "OK";
  environment: DeploymentEnvironment;
  version: string;
  timestamp: string;
}

export interface ServiceReadinessCheck {
  name: string;
  status: "OK" | "FAIL";
  detail: string;
}

export interface ServiceReadinessPayload {
  service: "api";
  status: "READY" | "NOT_READY";
  environment: DeploymentEnvironment;
  version: string;
  timestamp: string;
  checks: ServiceReadinessCheck[];
  detail?: string;
}

export interface ServiceUnavailablePayload {
  service: "api";
  status: "UNREACHABLE";
  environment: DeploymentEnvironment;
  version: string;
  timestamp: string;
  detail?: string;
}

export type ServiceStatusPayload =
  | ServiceHealthPayload
  | ServiceReadinessPayload
  | ServiceUnavailablePayload;

export interface SessionUser {
  id: string;
  sub: string;
  email: string;
  displayName: string;
  platformRoles: PlatformRole[];
}

export interface SessionBoundary {
  id: string;
  expiresAt: string;
}

export interface SessionResponse {
  user: SessionUser;
  session: SessionBoundary;
}

export interface SessionIssueResponse extends SessionResponse {
  sessionToken: string;
  csrfToken: string;
}

export interface AuthProviderSeed {
  key: string;
  displayName: string;
  email: string;
  platformRoles: PlatformRole[];
}

export interface AuthProviderResponse {
  oidcEnabled: boolean;
  devEnabled: boolean;
  devSeeds: AuthProviderSeed[];
}

export interface ProjectSummary {
  id: string;
  name: string;
  purpose: string;
  status: ProjectStatus;
  createdBy: string;
  createdAt: string;
  intendedAccessTier: AccessTier;
  baselinePolicySnapshotId: string;
  currentUserRole: ProjectRole | null;
  isMember: boolean;
  canAccessSettings: boolean;
  canManageMembers: boolean;
}

export interface ProjectListResponse {
  items: ProjectSummary[];
}

export interface ProjectMember {
  projectId: string;
  userId: string;
  email: string;
  displayName: string;
  role: ProjectRole;
  createdAt: string;
  updatedAt: string;
}

export interface ProjectMembersResponse {
  project: ProjectSummary;
  items: ProjectMember[];
}

export interface CreateProjectRequest {
  name: string;
  purpose: string;
  intendedAccessTier: AccessTier;
}

export interface AddProjectMemberRequest {
  memberEmail: string;
  role: ProjectRole;
}

export interface ChangeProjectMemberRoleRequest {
  role: ProjectRole;
}

export type DocumentStatus =
  | "UPLOADING"
  | "QUEUED"
  | "SCANNING"
  | "EXTRACTING"
  | "READY"
  | "FAILED"
  | "CANCELED";
export type DocumentImportStatus =
  | "UPLOADING"
  | "QUEUED"
  | "SCANNING"
  | "ACCEPTED"
  | "REJECTED"
  | "FAILED"
  | "CANCELED";
export type DocumentProcessingRunKind =
  | "UPLOAD"
  | "SCAN"
  | "EXTRACTION"
  | "THUMBNAIL_RENDER";
export type DocumentProcessingRunStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";
export type DocumentUploadSessionStatus =
  | "ACTIVE"
  | "ASSEMBLING"
  | "FAILED"
  | "CANCELED"
  | "COMPLETED";
export type DocumentPageStatus = "PENDING" | "READY" | "FAILED" | "CANCELED";
export type DocumentPageImageVariant =
  | "full"
  | "thumb"
  | "preprocessed_gray"
  | "preprocessed_bin";
export type PreprocessRunStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";
export type PreprocessRunScope =
  | "FULL_DOCUMENT"
  | "PAGE_SUBSET"
  | "COMPOSED_FULL_DOCUMENT";
export type PreprocessProfileId =
  | "BALANCED"
  | "CONSERVATIVE"
  | "AGGRESSIVE"
  | "BLEED_THROUGH";
export type PreprocessPageResultStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";
export type PreprocessQualityGateStatus = "PASS" | "REVIEW_REQUIRED" | "BLOCKED";
export type LayoutRunKind = "AUTO";
export type LayoutRunStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";
export type PageLayoutResultStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";
export type PageRecallStatus =
  | "COMPLETE"
  | "NEEDS_RESCUE"
  | "NEEDS_MANUAL_REVIEW";
export type LayoutRescueCandidateKind = "LINE_EXPANSION" | "PAGE_WINDOW";
export type LayoutRescueCandidateStatus =
  | "PENDING"
  | "ACCEPTED"
  | "REJECTED"
  | "RESOLVED";
export type TranscriptionRunEngine =
  | "VLM_LINE_CONTEXT"
  | "REVIEW_COMPOSED"
  | "KRAKEN_LINE"
  | "TROCR_LINE"
  | "DAN_PAGE";
export type TranscriptionRunStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";
export type RedactionRunKind = "BASELINE" | "POLICY_RERUN";
export type RedactionRunStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";
export type RedactionDecisionStatus =
  | "AUTO_APPLIED"
  | "NEEDS_REVIEW"
  | "APPROVED"
  | "OVERRIDDEN"
  | "FALSE_POSITIVE";
export type RedactionDecisionActionType = "MASK" | "PSEUDONYMIZE" | "GENERALIZE";
export type RedactionCompareActionState =
  | "AVAILABLE"
  | "NOT_YET_RERUN"
  | "NOT_YET_AVAILABLE";
export type RedactionComparePageActionState = "AVAILABLE" | "NOT_YET_AVAILABLE";
export type RedactionPageReviewStatus =
  | "NOT_STARTED"
  | "IN_REVIEW"
  | "APPROVED"
  | "CHANGES_REQUESTED";
export type RedactionSecondReviewStatus =
  | "NOT_REQUIRED"
  | "PENDING"
  | "APPROVED"
  | "CHANGES_REQUESTED";
export type RedactionRunReviewStatus =
  | "NOT_READY"
  | "IN_REVIEW"
  | "APPROVED"
  | "CHANGES_REQUESTED";
export type RedactionOutputStatus = "PENDING" | "READY" | "FAILED" | "CANCELED";
export type RedactionRunOutputReadinessState =
  | "APPROVAL_REQUIRED"
  | "APPROVED_OUTPUT_PENDING"
  | "OUTPUT_GENERATING"
  | "OUTPUT_FAILED"
  | "OUTPUT_CANCELED"
  | "OUTPUT_READY";
export type TranscriptionConfidenceBasis =
  | "MODEL_NATIVE"
  | "READ_AGREEMENT"
  | "FALLBACK_DISAGREEMENT";
export type TranscriptionConfidenceBand = "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
export type TranscriptionLineSchemaValidationStatus =
  | "VALID"
  | "FALLBACK_USED"
  | "INVALID";
export type TokenAnchorStatus = "CURRENT" | "STALE" | "REFRESH_REQUIRED";
export type TranscriptionTokenSourceKind =
  | "LINE"
  | "RESCUE_CANDIDATE"
  | "PAGE_WINDOW";
export type TranscriptionRescueResolutionStatus =
  | "RESCUE_VERIFIED"
  | "MANUAL_REVIEW_RESOLVED";
export type TranscriptionRescueReadinessState =
  | "READY"
  | "BLOCKED_RESCUE"
  | "BLOCKED_MANUAL_REVIEW"
  | "BLOCKED_PAGE_STATUS";
export type TranscriptionRescueBlockerReasonCode =
  | "PAGE_TRANSCRIPTION_NOT_SUCCEEDED"
  | "RESCUE_SOURCE_MISSING"
  | "RESCUE_SOURCE_UNTRANSCRIBED"
  | "MANUAL_REVIEW_RESOLUTION_REQUIRED";
export type TranscriptionActivationBlockerCode =
  | "RUN_NOT_SUCCEEDED"
  | "RUN_LAYOUT_BASIS_STALE"
  | "RUN_LAYOUT_SNAPSHOT_STALE"
  | "RUN_LAYOUT_PROJECTION_MISSING"
  | "TOKEN_ANCHOR_MISSING"
  | "TOKEN_ANCHOR_INVALID"
  | "TOKEN_ANCHOR_STALE"
  | "PAGE_TRANSCRIPTION_NOT_SUCCEEDED"
  | "RESCUE_SOURCE_MISSING"
  | "RESCUE_SOURCE_UNTRANSCRIBED"
  | "MANUAL_REVIEW_RESOLUTION_REQUIRED";
export type TranscriptionProjectionBasis = "ENGINE_OUTPUT" | "REVIEW_CORRECTED";
export type TranscriptionFallbackReasonCode =
  | "SCHEMA_VALIDATION_FAILED"
  | "ANCHOR_RESOLUTION_FAILED"
  | "CONFIDENCE_BELOW_THRESHOLD";
export type TranscriptionCompareDecision = "KEEP_BASE" | "PROMOTE_CANDIDATE";
export type TranscriptVersionSourceType =
  | "ENGINE_OUTPUT"
  | "REVIEWER_CORRECTION"
  | "COMPARE_COMPOSED";
export type TranscriptVariantKind = "NORMALISED";
export type TranscriptVariantSuggestionStatus =
  | "PENDING"
  | "ACCEPTED"
  | "REJECTED";
export type TranscriptVariantSuggestionDecision = "ACCEPT" | "REJECT";
export type DownstreamBasisState = "NOT_STARTED" | "CURRENT" | "STALE";
export type ApprovedModelType = "VLM" | "LLM" | "HTR";
export type ApprovedModelRole =
  | "TRANSCRIPTION_PRIMARY"
  | "TRANSCRIPTION_FALLBACK"
  | "ASSIST";
export type ApprovedModelServingInterface =
  | "OPENAI_CHAT"
  | "OPENAI_EMBEDDING"
  | "ENGINE_NATIVE"
  | "RULES_NATIVE";
export type ApprovedModelStatus = "APPROVED" | "DEPRECATED" | "ROLLED_BACK";
export type ProjectModelAssignmentStatus = "DRAFT" | "ACTIVE" | "RETIRED";
export type TrainingDatasetKind = "TRANSCRIPTION_TRAINING";
export type RedactionPolicyStatus = "DRAFT" | "ACTIVE" | "RETIRED";
export type RedactionPolicyValidationStatus =
  | "NOT_VALIDATED"
  | "VALID"
  | "INVALID";
export type PolicyEventType =
  | "POLICY_CREATED"
  | "POLICY_EDITED"
  | "POLICY_VALIDATED_VALID"
  | "POLICY_VALIDATED_INVALID"
  | "POLICY_ACTIVATED"
  | "POLICY_RETIRED";
export type PolicyCompareTargetKind = "POLICY" | "BASELINE_SNAPSHOT";
export type PseudonymRegistryEntryStatus = "ACTIVE" | "RETIRED";
export type PseudonymRegistryEntryEventType =
  | "ENTRY_CREATED"
  | "ENTRY_REUSED"
  | "ENTRY_RETIRED";
export type LayoutActivationBlockerCode =
  | "LAYOUT_RUN_NOT_SUCCEEDED"
  | "LAYOUT_RECALL_PAGE_RESULTS_MISSING"
  | "LAYOUT_RECALL_STATUS_MISSING"
  | "LAYOUT_RECALL_STATUS_UNRESOLVED"
  | "LAYOUT_RECALL_CHECK_MISSING"
  | "LAYOUT_RESCUE_PENDING"
  | "LAYOUT_RESCUE_ACCEPTANCE_MISSING";
export type SourceColorMode = "RGB" | "RGBA" | "GRAY" | "CMYK" | "UNKNOWN";
export type DocumentListSort = "updated" | "created" | "name";
export type SortDirection = "asc" | "desc";

export interface ProjectDocument {
  id: string;
  projectId: string;
  originalFilename: string;
  storedFilename: string | null;
  contentTypeDetected: string | null;
  bytes: number | null;
  sha256: string | null;
  pageCount: number | null;
  status: DocumentStatus;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface ProjectDocumentListResponse {
  items: ProjectDocument[];
  nextCursor: number | null;
}

export interface DocumentTimelineEvent {
  id: string;
  attemptNumber: number;
  runKind: DocumentProcessingRunKind;
  supersedesProcessingRunId: string | null;
  supersededByProcessingRunId: string | null;
  status: DocumentProcessingRunStatus;
  failureReason: string | null;
  createdBy: string;
  startedAt: string | null;
  finishedAt: string | null;
  canceledBy: string | null;
  canceledAt: string | null;
  createdAt: string;
}

export interface DocumentTimelineResponse {
  items: DocumentTimelineEvent[];
}

export interface DocumentProcessingRunStatusResponse {
  runId: string;
  documentId: string;
  attemptNumber: number;
  runKind: DocumentProcessingRunKind;
  supersedesProcessingRunId: string | null;
  supersededByProcessingRunId: string | null;
  status: DocumentProcessingRunStatus;
  failureReason: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  canceledAt: string | null;
  createdAt: string;
  active: boolean;
}

export interface DocumentProcessingRunDetailResponse extends DocumentTimelineEvent {
  documentId: string;
  active: boolean;
}

export interface CreateDocumentUploadSessionRequest {
  originalFilename: string;
  expectedSha256?: string;
  expectedTotalBytes?: number;
}

export interface ProjectDocumentUploadSessionStatus {
  sessionId: string;
  importId: string;
  documentId: string;
  originalFilename: string;
  uploadStatus: DocumentUploadSessionStatus;
  importStatus: DocumentImportStatus;
  documentStatus: DocumentStatus;
  bytesReceived: number;
  expectedTotalBytes: number | null;
  expectedSha256: string | null;
  lastChunkIndex: number;
  nextChunkIndex: number;
  chunkSizeLimitBytes: number;
  uploadLimitBytes: number;
  cancelAllowed: boolean;
  failureReason: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ProjectDocumentImportStatus {
  importId: string;
  documentId: string;
  importStatus: DocumentImportStatus;
  documentStatus: DocumentStatus;
  failureReason: string | null;
  cancelAllowed: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ProjectDocumentPage {
  id: string;
  documentId: string;
  pageIndex: number;
  width: number;
  height: number;
  dpi: number | null;
  sourceWidth: number;
  sourceHeight: number;
  sourceDpi: number | null;
  sourceColorMode: SourceColorMode;
  status: DocumentPageStatus;
  failureReason: string | null;
  viewerRotation: number;
  createdAt: string;
  updatedAt: string;
}

export interface ProjectDocumentPageDetail extends ProjectDocumentPage {
  derivedImageAvailable: boolean;
  thumbnailAvailable: boolean;
}

export interface ProjectDocumentPageListResponse {
  items: ProjectDocumentPage[];
}

export interface DocumentPageVariantAvailability {
  variant: "ORIGINAL" | "PREPROCESSED_GRAY" | "PREPROCESSED_BIN";
  imageVariant: DocumentPageImageVariant;
  available: boolean;
  mediaType: "image/png" | "image/jpeg";
  runId: string | null;
  resultStatus: PreprocessPageResultStatus | null;
  qualityGateStatus: PreprocessQualityGateStatus | null;
  warningsJson: string[];
  metricsJson: Record<string, unknown>;
}

export interface DocumentPageVariantsResponse {
  documentId: string;
  pageId: string;
  requestedRunId: string | null;
  resolvedRunId: string | null;
  run: DocumentPreprocessRun | null;
  variants: DocumentPageVariantAvailability[];
}

export interface DocumentPreprocessDownstreamImpact {
  resolvedAgainstRunId: string | null;
  layoutBasisState: DownstreamBasisState;
  layoutBasisRunId: string | null;
  transcriptionBasisState: DownstreamBasisState;
  transcriptionBasisRunId: string | null;
}

export interface DocumentPreprocessRun {
  id: string;
  projectId: string;
  documentId: string;
  parentRunId: string | null;
  attemptNumber: number;
  runScope: PreprocessRunScope;
  targetPageIdsJson: string[] | null;
  composedFromRunIdsJson: string[] | null;
  supersededByRunId: string | null;
  profileId: PreprocessProfileId;
  profileVersion?: string;
  profileRevision?: number;
  profileLabel?: string;
  profileDescription?: string;
  profileParamsHash?: string;
  profileIsAdvanced?: boolean;
  profileIsGated?: boolean;
  paramsJson: Record<string, unknown>;
  paramsHash: string;
  pipelineVersion: string;
  containerDigest: string;
  manifestObjectKey?: string | null;
  manifestSha256?: string | null;
  manifestSchemaVersion?: number;
  status: PreprocessRunStatus;
  createdBy: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  failureReason: string | null;
  isActiveProjection: boolean;
  isSuperseded: boolean;
  isCurrentAttempt: boolean;
  isHistoricalAttempt: boolean;
  downstreamImpact: DocumentPreprocessDownstreamImpact;
}

export interface DocumentPreprocessRunListResponse {
  items: DocumentPreprocessRun[];
  nextCursor: number | null;
}

export interface DocumentPreprocessRunStatusResponse {
  runId: string;
  documentId: string;
  status: PreprocessRunStatus;
  failureReason: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  createdAt: string;
  active: boolean;
}

export interface DocumentPreprocessProjection {
  documentId: string;
  projectId: string;
  activePreprocessRunId: string | null;
  activeProfileId: string | null;
  activeProfileVersion?: string | null;
  activeProfileRevision?: number | null;
  activeParamsHash?: string | null;
  activePipelineVersion?: string | null;
  activeContainerDigest?: string | null;
  selectionMode?: string;
  downstreamDefaultConsumer?: string;
  downstreamDefaultRunId?: string | null;
  downstreamImpact: DocumentPreprocessDownstreamImpact;
  updatedAt: string;
}

export interface DocumentPreprocessActiveRunResponse {
  projection: DocumentPreprocessProjection | null;
  run: DocumentPreprocessRun | null;
}

export interface DocumentPreprocessPageResult {
  runId: string;
  pageId: string;
  pageIndex: number;
  status: PreprocessPageResultStatus;
  qualityGateStatus: PreprocessQualityGateStatus;
  inputObjectKey: string | null;
  inputSha256?: string | null;
  sourceResultRunId?: string | null;
  outputObjectKeyGray: string | null;
  outputObjectKeyBin: string | null;
  metricsObjectKey?: string | null;
  metricsSha256?: string | null;
  metricsJson: Record<string, unknown>;
  sha256Gray: string | null;
  sha256Bin: string | null;
  warningsJson: string[];
  failureReason: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentPreprocessRunPageListResponse {
  runId: string;
  items: DocumentPreprocessPageResult[];
  nextCursor: number | null;
}

export interface DocumentPreprocessQualityResponse {
  projection: DocumentPreprocessProjection | null;
  run: DocumentPreprocessRun | null;
  items: DocumentPreprocessPageResult[];
  nextCursor: number | null;
}

export interface DocumentPreprocessOverviewResponse {
  documentId: string;
  projectId: string;
  projection: DocumentPreprocessProjection | null;
  activeRun: DocumentPreprocessRun | null;
  latestRun: DocumentPreprocessRun | null;
  totalRuns: number;
  pageCount: number;
  activeStatusCounts: Record<PreprocessPageResultStatus, number>;
  activeQualityGateCounts: Record<PreprocessQualityGateStatus, number>;
  activeWarningCount: number;
}

export interface DocumentPreprocessComparePageResult {
  pageId: string;
  pageIndex: number;
  warningDelta: number;
  addedWarnings: string[];
  removedWarnings: string[];
  metricDeltas: Record<string, number | null>;
  outputAvailability: Record<string, boolean>;
  base: DocumentPreprocessPageResult | null;
  candidate: DocumentPreprocessPageResult | null;
}

export interface DocumentPreprocessCompareResponse {
  documentId: string;
  projectId: string;
  baseRun: DocumentPreprocessRun;
  candidateRun: DocumentPreprocessRun;
  baseWarningCount: number;
  candidateWarningCount: number;
  baseBlockedCount: number;
  candidateBlockedCount: number;
  items: DocumentPreprocessComparePageResult[];
}

export interface CreateDocumentPreprocessRunRequest {
  profileId?: PreprocessProfileId;
  paramsJson?: Record<string, unknown>;
  pipelineVersion?: string;
  containerDigest?: string;
  parentRunId?: string;
  supersedesRunId?: string;
  advancedRiskConfirmed?: boolean;
  advancedRiskAcknowledgement?: string;
}

export interface RerunDocumentPreprocessRunRequest {
  profileId?: PreprocessProfileId;
  paramsJson?: Record<string, unknown>;
  pipelineVersion?: string;
  containerDigest?: string;
  targetPageIds?: string[];
  advancedRiskConfirmed?: boolean;
  advancedRiskAcknowledgement?: string;
}

export interface ActivateDocumentPreprocessRunResponse {
  projection: DocumentPreprocessProjection;
  run: DocumentPreprocessRun;
}

export interface DocumentLayoutRun {
  id: string;
  projectId: string;
  documentId: string;
  inputPreprocessRunId: string;
  runKind: LayoutRunKind;
  parentRunId: string | null;
  attemptNumber: number;
  supersededByRunId: string | null;
  modelId: string | null;
  profileId: string | null;
  paramsJson: Record<string, unknown>;
  paramsHash: string;
  pipelineVersion: string;
  containerDigest: string;
  status: LayoutRunStatus;
  createdBy: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  failureReason: string | null;
  isActiveProjection: boolean;
  isSuperseded: boolean;
  isCurrentAttempt: boolean;
  isHistoricalAttempt: boolean;
  activationGate?: DocumentLayoutActivationGate | null;
}

export interface DocumentLayoutRunListResponse {
  items: DocumentLayoutRun[];
  nextCursor: number | null;
}

export interface DocumentLayoutRunStatusResponse {
  runId: string;
  documentId: string;
  status: LayoutRunStatus;
  failureReason: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  createdAt: string;
  active: boolean;
}

export interface DocumentLayoutProjection {
  documentId: string;
  projectId: string;
  activeLayoutRunId: string | null;
  activeInputPreprocessRunId: string | null;
  activeLayoutSnapshotHash: string | null;
  downstreamTranscriptionState: DownstreamBasisState;
  downstreamTranscriptionInvalidatedAt: string | null;
  downstreamTranscriptionInvalidatedReason: string | null;
  updatedAt: string;
}

export interface DocumentLayoutActivationBlocker {
  code: LayoutActivationBlockerCode;
  message: string;
  count: number;
  pageIds: string[];
  pageNumbers: number[];
}

export interface DocumentLayoutActivationDownstreamImpact {
  transcriptionStateAfterActivation: DownstreamBasisState;
  invalidatesExistingTranscriptionBasis: boolean;
  reason: string | null;
  hasActiveTranscriptionProjection: boolean;
  activeTranscriptionRunId: string | null;
}

export interface DocumentLayoutActivationGate {
  eligible: boolean;
  blockerCount: number;
  blockers: DocumentLayoutActivationBlocker[];
  evaluatedAt: string;
  downstreamImpact: DocumentLayoutActivationDownstreamImpact;
}

export interface DocumentLayoutActiveRunResponse {
  projection: DocumentLayoutProjection | null;
  run: DocumentLayoutRun | null;
}

export interface DocumentLayoutPageResult {
  runId: string;
  pageId: string;
  pageIndex: number;
  status: PageLayoutResultStatus;
  pageRecallStatus: PageRecallStatus;
  activeLayoutVersionId: string | null;
  pageXmlKey: string | null;
  overlayJsonKey: string | null;
  pageXmlSha256: string | null;
  overlayJsonSha256: string | null;
  metricsJson: Record<string, unknown>;
  warningsJson: string[];
  failureReason: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentLayoutRunPageListResponse {
  runId: string;
  items: DocumentLayoutPageResult[];
  nextCursor: number | null;
}

export interface DocumentLayoutLineArtifactsResponse {
  runId: string;
  pageId: string;
  pageIndex: number;
  lineId: string;
  regionId: string | null;
  artifactsSha256: string;
  lineCropPath: string;
  regionCropPath: string | null;
  pageThumbnailPath: string;
  contextWindowPath: string;
  contextWindow: Record<string, unknown>;
}

export interface DocumentLayoutPageRecallStatusResponse {
  runId: string;
  pageId: string;
  pageIndex: number;
  pageRecallStatus: PageRecallStatus;
  recallCheckVersion: string | null;
  missedTextRiskScore: number | null;
  signalsJson: Record<string, unknown>;
  rescueCandidateCounts: Record<LayoutRescueCandidateStatus, number>;
  blockerReasonCodes: string[];
  unresolvedCount: number;
}

export interface DocumentLayoutRescueCandidate {
  id: string;
  runId: string;
  pageId: string;
  candidateKind: LayoutRescueCandidateKind;
  geometryJson: Record<string, unknown>;
  confidence: number | null;
  sourceSignal: string | null;
  status: LayoutRescueCandidateStatus;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentLayoutRescueCandidateListResponse {
  runId: string;
  pageId: string;
  pageIndex: number;
  items: DocumentLayoutRescueCandidate[];
}

export type LayoutOverlayElementType = "REGION" | "LINE";

export interface LayoutOverlayPoint {
  x: number;
  y: number;
}

export interface LayoutOverlayElementBase {
  id: string;
  type: LayoutOverlayElementType;
  parentId: string | null;
  polygon: LayoutOverlayPoint[];
}

export interface LayoutOverlayRegionElement extends LayoutOverlayElementBase {
  type: "REGION";
  childIds: string[];
  regionType?: string;
  includeInReadingOrder?: boolean;
}

export interface LayoutOverlayLineElement extends LayoutOverlayElementBase {
  type: "LINE";
  baseline?: LayoutOverlayPoint[];
}

export type LayoutOverlayElement =
  | LayoutOverlayRegionElement
  | LayoutOverlayLineElement;

export type LayoutReadingOrderMode = "ORDERED" | "UNORDERED" | "WITHHELD";

export interface DocumentLayoutReadingOrderGroup {
  id: string;
  ordered: boolean;
  regionIds: string[];
}

export interface DocumentLayoutReadingOrderMeta {
  schemaVersion: 1;
  mode: LayoutReadingOrderMode;
  source: string;
  ambiguityScore: number;
  columnCertainty: number;
  overlapConflictScore: number;
  orphanLineCount: number;
  nonTextComplexityScore: number;
  orderWithheld: boolean;
  versionEtag?: string;
  layoutVersionId?: string;
}

export interface DocumentLayoutPageOverlay {
  schemaVersion: 1;
  runId: string;
  pageId: string;
  pageIndex: number;
  page: {
    width: number;
    height: number;
  };
  elements: LayoutOverlayElement[];
  readingOrder: Array<{ fromId: string; toId: string }>;
  readingOrderGroups: DocumentLayoutReadingOrderGroup[];
  readingOrderMeta: DocumentLayoutReadingOrderMeta;
}

export interface UpdateDocumentLayoutReadingOrderRequest {
  versionEtag: string;
  mode?: LayoutReadingOrderMode;
  groups: DocumentLayoutReadingOrderGroup[];
}

export interface UpdateDocumentLayoutReadingOrderResponse {
  runId: string;
  pageId: string;
  pageIndex: number;
  layoutVersionId: string;
  versionEtag: string;
  mode: LayoutReadingOrderMode;
  groups: DocumentLayoutReadingOrderGroup[];
  edges: Array<{ fromId: string; toId: string }>;
  signalsJson: Record<string, unknown>;
}

export type LayoutElementsOperationKind =
  | "ADD_REGION"
  | "ADD_LINE"
  | "MOVE_REGION"
  | "MOVE_LINE"
  | "MOVE_BASELINE"
  | "DELETE_REGION"
  | "DELETE_LINE"
  | "RETAG_REGION"
  | "ASSIGN_LINE_REGION"
  | "REORDER_REGION_LINES"
  | "SET_REGION_READING_ORDER_INCLUDED";

export interface LayoutElementsPatchOperation {
  kind: LayoutElementsOperationKind;
  regionId?: string;
  lineId?: string;
  parentRegionId?: string;
  beforeLineId?: string;
  afterLineId?: string;
  polygon?: LayoutOverlayPoint[];
  baseline?: LayoutOverlayPoint[] | null;
  regionType?: string;
  includeInReadingOrder?: boolean;
  lineIds?: string[];
}

export interface UpdateDocumentLayoutElementsRequest {
  versionEtag: string;
  operations: LayoutElementsPatchOperation[];
}

export interface UpdateDocumentLayoutElementsResponse {
  runId: string;
  pageId: string;
  pageIndex: number;
  layoutVersionId: string;
  versionEtag: string;
  operationsApplied: number;
  overlay: DocumentLayoutPageOverlay;
  downstreamTranscriptionInvalidated: boolean;
  downstreamTranscriptionState: DownstreamBasisState | null;
  downstreamTranscriptionInvalidatedReason: string | null;
}

export interface DocumentLayoutSummary {
  regionsDetected: number | null;
  linesDetected: number | null;
  pagesWithIssues: number;
  coveragePercent: number | null;
  structureConfidence: number | null;
}

export interface DocumentLayoutOverviewResponse {
  documentId: string;
  projectId: string;
  projection: DocumentLayoutProjection | null;
  activeRun: DocumentLayoutRun | null;
  latestRun: DocumentLayoutRun | null;
  totalRuns: number;
  pageCount: number;
  activeStatusCounts: Record<PageLayoutResultStatus, number>;
  activeRecallCounts: Record<PageRecallStatus, number>;
  summary: DocumentLayoutSummary;
}

export interface CreateDocumentLayoutRunRequest {
  inputPreprocessRunId?: string;
  modelId?: string;
  profileId?: string;
  paramsJson?: Record<string, unknown>;
  pipelineVersion?: string;
  containerDigest?: string;
  parentRunId?: string;
  supersedesRunId?: string;
}

export interface ActivateDocumentLayoutRunResponse {
  projection: DocumentLayoutProjection;
  run: DocumentLayoutRun;
  activationGate: DocumentLayoutActivationGate;
}

export interface CreateDocumentTranscriptionRunRequest {
  inputPreprocessRunId?: string;
  inputLayoutRunId?: string;
  engine?: TranscriptionRunEngine;
  modelId?: string;
  projectModelAssignmentId?: string;
  promptTemplateId?: string;
  promptTemplateSha256?: string;
  responseSchemaVersion?: number;
  confidenceBasis?: TranscriptionConfidenceBasis;
  confidenceCalibrationVersion?: string;
  paramsJson?: Record<string, unknown>;
  pipelineVersion?: string;
  containerDigest?: string;
  supersedesTranscriptionRunId?: string;
}

export interface CreateDocumentTranscriptionFallbackRunRequest {
  baseRunId?: string;
  engine?: TranscriptionRunEngine;
  modelId?: string;
  projectModelAssignmentId?: string;
  promptTemplateId?: string;
  promptTemplateSha256?: string;
  responseSchemaVersion?: number;
  confidenceCalibrationVersion?: string;
  paramsJson?: Record<string, unknown>;
  pipelineVersion?: string;
  containerDigest?: string;
  fallbackReasonCodes?: TranscriptionFallbackReasonCode[];
  fallbackConfidenceThreshold?: number;
}

export interface DocumentTranscriptionRun {
  id: string;
  projectId: string;
  documentId: string;
  inputPreprocessRunId: string;
  inputLayoutRunId: string;
  inputLayoutSnapshotHash: string;
  engine: TranscriptionRunEngine;
  modelId: string;
  projectModelAssignmentId: string | null;
  promptTemplateId: string | null;
  promptTemplateSha256: string | null;
  responseSchemaVersion: number;
  confidenceBasis: TranscriptionConfidenceBasis;
  confidenceCalibrationVersion: string;
  paramsJson: Record<string, unknown>;
  pipelineVersion: string;
  containerDigest: string;
  attemptNumber: number;
  supersedesTranscriptionRunId: string | null;
  supersededByTranscriptionRunId: string | null;
  status: TranscriptionRunStatus;
  createdBy: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  canceledBy: string | null;
  canceledAt: string | null;
  failureReason: string | null;
  isActiveProjection: boolean;
  isSuperseded: boolean;
  isCurrentAttempt: boolean;
  isHistoricalAttempt: boolean;
}

export interface DocumentTranscriptionRunListResponse {
  items: DocumentTranscriptionRun[];
  nextCursor: number | null;
}

export interface DocumentTranscriptionRunStatusResponse {
  runId: string;
  documentId: string;
  status: TranscriptionRunStatus;
  failureReason: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  createdAt: string;
  active: boolean;
}

export interface DocumentTranscriptionProjection {
  documentId: string;
  projectId: string;
  activeTranscriptionRunId: string | null;
  activeLayoutRunId: string | null;
  activeLayoutSnapshotHash: string | null;
  activePreprocessRunId: string | null;
  downstreamRedactionState: DownstreamBasisState;
  downstreamRedactionInvalidatedAt: string | null;
  downstreamRedactionInvalidatedReason: string | null;
  updatedAt: string;
}

export interface DocumentTranscriptionActiveRunResponse {
  projection: DocumentTranscriptionProjection | null;
  run: DocumentTranscriptionRun | null;
}

export interface ApprovedModel {
  id: string;
  modelType: ApprovedModelType;
  modelRole: ApprovedModelRole;
  modelFamily: string;
  modelVersion: string;
  servingInterface: ApprovedModelServingInterface;
  engineFamily: string;
  deploymentUnit: string;
  artifactSubpath: string;
  checksumSha256: string;
  runtimeProfile: string;
  responseContractVersion: string;
  metadataJson: Record<string, unknown>;
  status: ApprovedModelStatus;
  approvedBy: string | null;
  approvedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ApprovedModelListResponse {
  items: ApprovedModel[];
}

export interface CreateApprovedModelRequest {
  modelType: ApprovedModelType;
  modelRole: ApprovedModelRole;
  modelFamily: string;
  modelVersion: string;
  servingInterface: ApprovedModelServingInterface;
  engineFamily: string;
  deploymentUnit: string;
  artifactSubpath: string;
  checksumSha256: string;
  runtimeProfile: string;
  responseContractVersion: string;
  metadataJson?: Record<string, unknown>;
}

export interface ProjectModelAssignment {
  id: string;
  projectId: string;
  modelRole: ApprovedModelRole;
  approvedModelId: string;
  status: ProjectModelAssignmentStatus;
  assignmentReason: string;
  createdBy: string;
  createdAt: string;
  activatedBy: string | null;
  activatedAt: string | null;
  retiredBy: string | null;
  retiredAt: string | null;
}

export interface ProjectModelAssignmentListResponse {
  items: ProjectModelAssignment[];
}

export interface CreateProjectModelAssignmentRequest {
  modelRole: ApprovedModelRole;
  approvedModelId: string;
  assignmentReason: string;
}

export interface TrainingDataset {
  id: string;
  projectId: string;
  sourceApprovedModelId: string | null;
  projectModelAssignmentId: string | null;
  datasetKind: TrainingDatasetKind;
  pageCount: number;
  storageKey: string;
  datasetSha256: string;
  createdBy: string;
  createdAt: string;
}

export interface TrainingDatasetListResponse {
  items: TrainingDataset[];
}

export interface RedactionPolicy {
  id: string;
  projectId: string;
  policyFamilyId: string;
  name: string;
  version: number;
  seededFromBaselineSnapshotId: string | null;
  supersedesPolicyId: string | null;
  supersededByPolicyId: string | null;
  rulesJson: Record<string, unknown>;
  versionEtag: string;
  status: RedactionPolicyStatus;
  createdBy: string;
  createdAt: string;
  activatedBy: string | null;
  activatedAt: string | null;
  retiredBy: string | null;
  retiredAt: string | null;
  validationStatus: RedactionPolicyValidationStatus;
  validatedRulesSha256: string | null;
  lastValidatedBy: string | null;
  lastValidatedAt: string | null;
}

export interface RedactionPolicyListResponse {
  items: RedactionPolicy[];
}

export interface CreateRedactionPolicyRequest {
  name: string;
  rulesJson: Record<string, unknown>;
  seededFromBaselineSnapshotId?: string | null;
  supersedesPolicyId?: string | null;
  reason?: string | null;
}

export interface UpdateRedactionPolicyRequest {
  versionEtag: string;
  name?: string | null;
  rulesJson?: Record<string, unknown> | null;
  reason?: string | null;
}

export interface CreatePolicyRollbackDraftRequest {
  fromPolicyId: string;
  reason?: string | null;
}

export interface ProjectPolicyProjection {
  projectId: string;
  activePolicyId: string | null;
  activePolicyFamilyId: string | null;
  updatedAt: string;
}

export interface ActiveProjectPolicyResponse {
  projection: ProjectPolicyProjection | null;
  policy: RedactionPolicy | null;
}

export interface PolicyEvent {
  id: string;
  policyId: string;
  eventType: PolicyEventType;
  actorUserId: string | null;
  reason: string | null;
  rulesSha256: string;
  rulesSnapshotKey: string;
  createdAt: string;
}

export interface PolicyEventListResponse {
  items: PolicyEvent[];
}

export interface PolicyValidationResponse {
  policy: RedactionPolicy;
  issues: string[];
}

export interface PolicyCompareDifference {
  path: string;
  before: unknown;
  after: unknown;
}

export interface PolicyCompareResponse {
  sourcePolicy: RedactionPolicy;
  targetKind: PolicyCompareTargetKind;
  targetPolicy: RedactionPolicy | null;
  targetBaselineSnapshotId: string | null;
  sourceRulesSha256: string;
  targetRulesSha256: string;
  differenceCount: number;
  differences: PolicyCompareDifference[];
}

export interface PolicyLineageResponse {
  policy: RedactionPolicy;
  projection: ProjectPolicyProjection | null;
  activePolicyDiffers: boolean;
  seededBaselineSnapshotId: string | null;
  lineage: RedactionPolicy[];
  events: PolicyEvent[];
  validationEvents: PolicyEvent[];
  activationEvents: PolicyEvent[];
  retirementEvents: PolicyEvent[];
}

export interface PolicyUsageRun {
  runId: string;
  projectId: string;
  documentId: string;
  runKind: string;
  runStatus: string;
  supersedesRedactionRunId: string | null;
  policyFamilyId: string | null;
  policyVersion: string | null;
  runCreatedAt: string;
  runFinishedAt: string | null;
  governanceReadinessStatus: string | null;
  governanceGenerationStatus: string | null;
  governanceManifestId: string | null;
  governanceLedgerId: string | null;
  governanceManifestSha256: string | null;
  governanceLedgerSha256: string | null;
  governanceLedgerVerificationStatus: string | null;
}

export interface PolicyUsageManifest {
  id: string;
  runId: string;
  projectId: string;
  documentId: string;
  status: string;
  attemptNumber: number;
  manifestSha256: string | null;
  sourceReviewSnapshotSha256: string;
  createdAt: string;
}

export interface PolicyUsageLedger {
  id: string;
  runId: string;
  projectId: string;
  documentId: string;
  status: string;
  attemptNumber: number;
  ledgerSha256: string | null;
  sourceReviewSnapshotSha256: string;
  createdAt: string;
}

export interface PolicyUsagePseudonymSummary {
  totalEntries: number;
  activeEntries: number;
  retiredEntries: number;
  aliasStrategyVersions: string[];
  saltVersionRefs: string[];
}

export interface PolicyUsageResponse {
  policy: RedactionPolicy;
  runs: PolicyUsageRun[];
  manifests: PolicyUsageManifest[];
  ledgers: PolicyUsageLedger[];
  pseudonymSummary: PolicyUsagePseudonymSummary;
}

export interface PolicyExplainabilityCategoryRule {
  id: string;
  action: string;
  reviewRequiredBelow: number | null;
  autoApplyAbove: number | null;
  confidenceThreshold: number | null;
  requiresReviewer: boolean;
  escalationFlags: string[];
}

export interface PolicyExplainabilityTrace {
  categoryId: string;
  sampleConfidence: number;
  selectedAction: string;
  outcome: "AUTO_APPLY" | "REVIEW_REQUIRED" | "BLOCKED" | "UNSPECIFIED";
  rationale: string;
}

export interface PolicyExplainabilityResponse {
  policy: RedactionPolicy;
  rulesSha256: string;
  categoryRules: PolicyExplainabilityCategoryRule[];
  defaults: Record<string, unknown>;
  reviewerRequirements: boolean | Record<string, unknown> | null;
  escalationFlags: boolean | Record<string, unknown> | null;
  pseudonymisation: Record<string, unknown> | null;
  generalisation: Record<string, unknown> | unknown[] | null;
  reviewerExplanationMode: string | null;
  deterministicTraces: PolicyExplainabilityTrace[];
}

export interface PolicySnapshotResponse {
  policy: RedactionPolicy;
  event: PolicyEvent;
  rulesSha256: string;
  rulesSnapshotKey: string;
  rulesJson: Record<string, unknown>;
  snapshotCreatedAt: string;
}

export interface PseudonymRegistryEntry {
  id: string;
  projectId: string;
  sourceRunId: string;
  sourceFingerprintHmacSha256: string;
  aliasValue: string;
  policyId: string;
  saltVersionRef: string;
  aliasStrategyVersion: string;
  createdBy: string;
  createdAt: string;
  lastUsedRunId: string | null;
  updatedAt: string;
  status: PseudonymRegistryEntryStatus;
  retiredAt: string | null;
  retiredBy: string | null;
  supersedesEntryId: string | null;
  supersededByEntryId: string | null;
}

export interface PseudonymRegistryEntryListResponse {
  items: PseudonymRegistryEntry[];
}

export interface PseudonymRegistryEntryEvent {
  id: string;
  entryId: string;
  eventType: PseudonymRegistryEntryEventType;
  runId: string;
  actorUserId: string | null;
  createdAt: string;
}

export interface PseudonymRegistryEntryEventListResponse {
  items: PseudonymRegistryEntryEvent[];
}

export interface DocumentTranscriptionPageResult {
  runId: string;
  pageId: string;
  pageIndex: number;
  status: TranscriptionRunStatus;
  pagexmlOutKey: string | null;
  pagexmlOutSha256: string | null;
  rawModelResponseKey: string | null;
  rawModelResponseSha256: string | null;
  hocrOutKey: string | null;
  hocrOutSha256: string | null;
  metricsJson: Record<string, unknown>;
  warningsJson: string[];
  failureReason: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentTranscriptionRunPageListResponse {
  runId: string;
  items: DocumentTranscriptionPageResult[];
  nextCursor: number | null;
}

export interface DocumentTranscriptionLineResult {
  runId: string;
  pageId: string;
  lineId: string;
  textDiplomatic: string;
  confLine: number | null;
  confidenceBand: TranscriptionConfidenceBand;
  confidenceBasis: TranscriptionConfidenceBasis;
  confidenceCalibrationVersion: string;
  alignmentJsonKey: string | null;
  charBoxesKey: string | null;
  schemaValidationStatus: TranscriptionLineSchemaValidationStatus;
  flagsJson: Record<string, unknown>;
  machineOutputSha256: string | null;
  activeTranscriptVersionId: string | null;
  versionEtag: string;
  tokenAnchorStatus: TokenAnchorStatus;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentTranscriptionLineResultListResponse {
  runId: string;
  pageId: string;
  items: DocumentTranscriptionLineResult[];
}

export interface DocumentTranscriptionTokenResult {
  runId: string;
  pageId: string;
  lineId: string | null;
  tokenId: string;
  tokenIndex: number;
  tokenText: string;
  tokenConfidence: number | null;
  bboxJson: Record<string, unknown> | null;
  polygonJson: Record<string, unknown> | null;
  sourceKind: TranscriptionTokenSourceKind;
  sourceRefId: string;
  projectionBasis: TranscriptionProjectionBasis;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentTranscriptionTokenResultListResponse {
  runId: string;
  pageId: string;
  items: DocumentTranscriptionTokenResult[];
}

export interface DocumentTranscriptionRescueSource {
  sourceRefId: string;
  sourceKind: TranscriptionTokenSourceKind;
  candidateKind: LayoutRescueCandidateKind;
  candidateStatus: LayoutRescueCandidateStatus;
  tokenCount: number;
  hasTranscriptionOutput: boolean;
  confidence: number | null;
  sourceSignal: string | null;
  geometryJson: Record<string, unknown>;
}

export interface DocumentTranscriptionRescuePageStatus {
  runId: string;
  pageId: string;
  pageIndex: number;
  pageRecallStatus: PageRecallStatus;
  rescueSourceCount: number;
  rescueTranscribedSourceCount: number;
  rescueUnresolvedSourceCount: number;
  readinessState: TranscriptionRescueReadinessState;
  blockerReasonCodes: TranscriptionRescueBlockerReasonCode[];
  resolutionStatus: TranscriptionRescueResolutionStatus | null;
  resolutionReason: string | null;
  resolutionUpdatedBy: string | null;
  resolutionUpdatedAt: string | null;
}

export interface DocumentTranscriptionRunRescueStatusResponse {
  documentId: string;
  projectId: string;
  runId: string;
  readyForActivation: boolean;
  blockerCount: number;
  runBlockerReasonCodes: TranscriptionActivationBlockerCode[];
  pages: DocumentTranscriptionRescuePageStatus[];
}

export interface DocumentTranscriptionPageRescueSourcesResponse {
  documentId: string;
  projectId: string;
  runId: string;
  pageId: string;
  pageIndex: number;
  pageRecallStatus: PageRecallStatus;
  readinessState: TranscriptionRescueReadinessState;
  blockerReasonCodes: TranscriptionRescueBlockerReasonCode[];
  rescueSources: DocumentTranscriptionRescueSource[];
  resolutionStatus: TranscriptionRescueResolutionStatus | null;
  resolutionReason: string | null;
  resolutionUpdatedBy: string | null;
  resolutionUpdatedAt: string | null;
}

export interface UpdateDocumentTranscriptionRescueResolutionRequest {
  resolutionStatus: TranscriptionRescueResolutionStatus;
  resolutionReason?: string;
}

export interface TranscriptVersion {
  id: string;
  runId: string;
  pageId: string;
  lineId: string;
  baseVersionId: string | null;
  supersededByVersionId: string | null;
  versionEtag: string;
  textDiplomatic: string;
  editorUserId: string;
  editReason: string | null;
  createdAt: string;
}

export interface TranscriptVersionLineage {
  version: TranscriptVersion;
  isActive: boolean;
  sourceType: TranscriptVersionSourceType;
}

export interface DocumentTranscriptionLineVersionHistoryResponse {
  documentId: string;
  projectId: string;
  runId: string;
  pageId: string;
  lineId: string;
  line: DocumentTranscriptionLineResult;
  versions: TranscriptVersionLineage[];
}

export interface DocumentTranscriptionOutputProjection {
  runId: string;
  documentId: string;
  pageId: string;
  correctedPagexmlKey: string;
  correctedPagexmlSha256: string;
  correctedTextSha256: string;
  sourcePagexmlSha256: string;
  updatedAt: string;
}

export interface CorrectDocumentTranscriptionLineRequest {
  textDiplomatic: string;
  versionEtag: string;
  editReason?: string;
}

export interface CorrectDocumentTranscriptionLineResponse {
  runId: string;
  pageId: string;
  lineId: string;
  textChanged: boolean;
  line: DocumentTranscriptionLineResult;
  activeVersion: TranscriptVersion;
  outputProjection: DocumentTranscriptionOutputProjection;
  downstreamRedactionInvalidated: boolean;
  downstreamRedactionState: DownstreamBasisState | null;
  downstreamRedactionInvalidatedAt: string | null;
  downstreamRedactionInvalidatedReason: string | null;
}

export interface TranscriptVariantSuggestion {
  id: string;
  variantLayerId: string;
  lineId: string | null;
  suggestionText: string;
  confidence: number | null;
  status: TranscriptVariantSuggestionStatus;
  decidedBy: string | null;
  decidedAt: string | null;
  decisionReason: string | null;
  metadataJson: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface TranscriptVariantSuggestionEvent {
  id: string;
  suggestionId: string;
  variantLayerId: string;
  actorUserId: string;
  decision: TranscriptVariantSuggestionDecision;
  fromStatus: TranscriptVariantSuggestionStatus;
  toStatus: TranscriptVariantSuggestionStatus;
  reason: string | null;
  createdAt: string;
}

export interface TranscriptVariantLayer {
  id: string;
  runId: string;
  pageId: string;
  variantKind: TranscriptVariantKind;
  baseTranscriptVersionId: string | null;
  baseVersionSetSha256: string | null;
  baseProjectionSha256: string;
  variantTextKey: string;
  variantTextSha256: string;
  createdBy: string;
  createdAt: string;
  suggestions: TranscriptVariantSuggestion[];
}

export interface TranscriptVariantLayerListResponse {
  runId: string;
  pageId: string;
  variantKind: TranscriptVariantKind;
  items: TranscriptVariantLayer[];
}

export interface RecordTranscriptVariantSuggestionDecisionRequest {
  decision: TranscriptVariantSuggestionDecision;
  reason?: string;
}

export interface RecordTranscriptVariantSuggestionDecisionResponse {
  runId: string;
  pageId: string;
  variantKind: TranscriptVariantKind;
  suggestion: TranscriptVariantSuggestion;
  event: TranscriptVariantSuggestionEvent;
}

export interface DocumentTranscriptionCompareDecision {
  id: string;
  documentId: string;
  baseRunId: string;
  candidateRunId: string;
  pageId: string;
  lineId: string | null;
  tokenId: string | null;
  decision: TranscriptionCompareDecision;
  decisionEtag: string;
  decidedBy: string;
  decidedAt: string;
  decisionReason: string | null;
}

export interface DocumentTranscriptionCompareLineDiff {
  lineId: string;
  changed: boolean;
  confidenceDelta: number | null;
  base: DocumentTranscriptionLineResult | null;
  candidate: DocumentTranscriptionLineResult | null;
  decision: DocumentTranscriptionCompareDecision | null;
}

export interface DocumentTranscriptionCompareTokenDiff {
  tokenId: string;
  tokenIndex: number | null;
  lineId: string | null;
  changed: boolean;
  confidenceDelta: number | null;
  base: DocumentTranscriptionTokenResult | null;
  candidate: DocumentTranscriptionTokenResult | null;
  decision: DocumentTranscriptionCompareDecision | null;
}

export interface DocumentTranscriptionComparePage {
  pageId: string;
  pageIndex: number;
  changedLineCount: number;
  changedTokenCount: number;
  changedConfidenceCount: number;
  outputAvailability: Record<string, boolean>;
  base: DocumentTranscriptionPageResult | null;
  candidate: DocumentTranscriptionPageResult | null;
  lineDiffs: DocumentTranscriptionCompareLineDiff[];
  tokenDiffs: DocumentTranscriptionCompareTokenDiff[];
}

export interface DocumentTranscriptionCompareResponse {
  documentId: string;
  projectId: string;
  baseRun: DocumentTranscriptionRun;
  candidateRun: DocumentTranscriptionRun;
  changedLineCount: number;
  changedTokenCount: number;
  changedConfidenceCount: number;
  baseEngineMetadata: Record<string, unknown>;
  candidateEngineMetadata: Record<string, unknown>;
  compareDecisionSnapshotHash: string;
  compareDecisionCount: number;
  compareDecisionEventCount: number;
  items: DocumentTranscriptionComparePage[];
}

export interface RecordDocumentTranscriptionCompareDecisionRequestItem {
  pageId: string;
  lineId?: string;
  tokenId?: string;
  decision: TranscriptionCompareDecision;
  decisionReason?: string;
  decisionEtag?: string;
}

export interface RecordDocumentTranscriptionCompareDecisionsRequest {
  baseRunId: string;
  candidateRunId: string;
  items: RecordDocumentTranscriptionCompareDecisionRequestItem[];
}

export interface RecordDocumentTranscriptionCompareDecisionsResponse {
  documentId: string;
  projectId: string;
  baseRunId: string;
  candidateRunId: string;
  items: DocumentTranscriptionCompareDecision[];
}

export interface FinalizeDocumentTranscriptionCompareRequest {
  baseRunId: string;
  candidateRunId: string;
  pageIds?: string[];
  expectedCompareDecisionSnapshotHash?: string;
}

export interface FinalizeDocumentTranscriptionCompareResponse {
  documentId: string;
  projectId: string;
  baseRunId: string;
  candidateRunId: string;
  composedRun: DocumentTranscriptionRun;
  compareDecisionSnapshotHash: string;
  pageScope: string[];
}

export interface DocumentTranscriptionTriagePage {
  runId: string;
  pageId: string;
  pageIndex: number;
  status: TranscriptionRunStatus;
  lineCount: number;
  tokenCount: number;
  anchorRefreshRequired: number;
  lowConfidenceLines: number;
  minConfidence: number | null;
  avgConfidence: number | null;
  warningsJson: string[];
  confidenceBands: Record<TranscriptionConfidenceBand, number>;
  issues: string[];
  rankingScore: number;
  rankingRationale: string;
  reviewerAssignmentUserId: string | null;
  reviewerAssignmentUpdatedBy: string | null;
  reviewerAssignmentUpdatedAt: string | null;
}

export interface DocumentTranscriptionTriageResponse {
  projection: DocumentTranscriptionProjection | null;
  run: DocumentTranscriptionRun | null;
  items: DocumentTranscriptionTriagePage[];
  nextCursor: number | null;
}

export interface DocumentTranscriptionMetricsLowConfidencePage {
  pageId: string;
  pageIndex: number;
  lowConfidenceLines: number;
}

export interface DocumentTranscriptionMetricsResponse {
  projection: DocumentTranscriptionProjection | null;
  run: DocumentTranscriptionRun | null;
  reviewConfidenceThreshold: number;
  fallbackConfidenceThreshold: number;
  pageCount: number;
  lineCount: number;
  tokenCount: number;
  lowConfidenceLineCount: number;
  percentLinesBelowThreshold: number;
  lowConfidencePageCount: number;
  lowConfidencePageDistribution: DocumentTranscriptionMetricsLowConfidencePage[];
  segmentationMismatchWarningCount: number;
  structuredValidationFailureCount: number;
  fallbackInvocationCount: number;
  confidenceBands: Record<TranscriptionConfidenceBand, number>;
}

export interface UpdateDocumentTranscriptionTriageAssignmentRequest {
  runId?: string;
  reviewerUserId?: string;
}

export interface UpdateDocumentTranscriptionTriageAssignmentResponse {
  projection: DocumentTranscriptionProjection | null;
  run: DocumentTranscriptionRun;
  item: DocumentTranscriptionTriagePage;
}

export interface DocumentTranscriptionOverviewResponse {
  documentId: string;
  projectId: string;
  projection: DocumentTranscriptionProjection | null;
  activeRun: DocumentTranscriptionRun | null;
  latestRun: DocumentTranscriptionRun | null;
  totalRuns: number;
  pageCount: number;
  activeStatusCounts: Record<TranscriptionRunStatus, number>;
  activeLineCount: number;
  activeTokenCount: number;
  activeAnchorRefreshRequired: number;
  activeLowConfidenceLines: number;
}

export interface ActivateDocumentTranscriptionRunResponse {
  projection: DocumentTranscriptionProjection;
  run: DocumentTranscriptionRun;
}

export interface CreateDocumentRedactionRunRequest {
  inputTranscriptionRunId?: string;
  inputLayoutRunId?: string;
  runKind?: RedactionRunKind;
  supersedesRedactionRunId?: string;
  detectorsVersion?: string;
}

export interface DocumentRedactionRun {
  id: string;
  projectId: string;
  documentId: string;
  inputTranscriptionRunId: string;
  inputLayoutRunId: string | null;
  runKind: RedactionRunKind;
  supersedesRedactionRunId: string | null;
  supersededByRedactionRunId: string | null;
  policySnapshotId: string;
  policySnapshotJson: Record<string, unknown>;
  policySnapshotHash: string;
  policyId: string | null;
  policyFamilyId: string | null;
  policyVersion: string | null;
  detectorsVersion: string;
  status: RedactionRunStatus;
  createdBy: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  failureReason: string | null;
  isActiveProjection: boolean;
  isSuperseded: boolean;
  isCurrentAttempt: boolean;
  isHistoricalAttempt: boolean;
}

export interface DocumentRedactionRunListResponse {
  items: DocumentRedactionRun[];
  nextCursor: number | null;
}

export interface DocumentRedactionRunStatusResponse {
  runId: string;
  documentId: string;
  status: RedactionRunStatus;
  failureReason: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  createdAt: string;
  active: boolean;
}

export interface DocumentRedactionProjection {
  documentId: string;
  projectId: string;
  activeRedactionRunId: string | null;
  activeTranscriptionRunId: string | null;
  activeLayoutRunId: string | null;
  activePolicySnapshotId: string | null;
  updatedAt: string;
}

export interface DocumentRedactionActiveRunResponse {
  projection: DocumentRedactionProjection | null;
  run: DocumentRedactionRun | null;
}

export interface DocumentRedactionRunReview {
  runId: string;
  reviewStatus: RedactionRunReviewStatus;
  reviewStartedBy: string | null;
  reviewStartedAt: string | null;
  approvedBy: string | null;
  approvedAt: string | null;
  approvedSnapshotKey: string | null;
  approvedSnapshotSha256: string | null;
  lockedAt: string | null;
  updatedAt: string;
}

export interface CompleteDocumentRedactionRunReviewRequest {
  reviewStatus: RedactionRunReviewStatus;
  reason?: string;
}

export type RedactionFindingAnchorKind =
  | "TOKEN_LINKED"
  | "AREA_MASK_BACKED"
  | "BBOX_ONLY"
  | "NONE";
export type RedactionFindingGeometrySource = "TOKEN_REF" | "BBOX_REF" | "AREA_MASK";

export interface DocumentRedactionFindingGeometryPoint {
  x: number;
  y: number;
}

export interface DocumentRedactionFindingGeometryBox {
  x: number;
  y: number;
  width: number;
  height: number;
  source: RedactionFindingGeometrySource;
}

export interface DocumentRedactionFindingGeometryPolygon {
  points: DocumentRedactionFindingGeometryPoint[];
  source: RedactionFindingGeometrySource;
}

export interface DocumentRedactionFindingGeometry {
  anchorKind: RedactionFindingAnchorKind;
  lineId: string | null;
  tokenIds: string[];
  boxes: DocumentRedactionFindingGeometryBox[];
  polygons: DocumentRedactionFindingGeometryPolygon[];
}

export interface DocumentRedactionFinding {
  id: string;
  runId: string;
  pageId: string;
  lineId: string | null;
  category: string;
  spanStart: number | null;
  spanEnd: number | null;
  spanBasisKind: string;
  spanBasisRef: string | null;
  confidence: number | null;
  basisPrimary: string;
  basisSecondaryJson: Record<string, unknown> | null;
  assistExplanationKey: string | null;
  assistExplanationSha256: string | null;
  bboxRefs: Record<string, unknown>;
  tokenRefsJson: Array<Record<string, unknown>> | null;
  areaMaskId: string | null;
  decisionStatus: RedactionDecisionStatus;
  actionType: RedactionDecisionActionType;
  overrideRiskClassification: string | null;
  overrideRiskReasonCodesJson: string[] | null;
  decisionBy: string | null;
  decisionAt: string | null;
  decisionReason: string | null;
  decisionEtag: string;
  updatedAt: string;
  createdAt: string;
  geometry: DocumentRedactionFindingGeometry;
  activeAreaMask: DocumentRedactionAreaMask | null;
}

export interface DocumentRedactionFindingListResponse {
  runId: string;
  pageId: string;
  items: DocumentRedactionFinding[];
}

export interface PatchDocumentRedactionFindingRequest {
  decisionStatus: RedactionDecisionStatus;
  decisionEtag: string;
  reason?: string;
  actionType?: RedactionDecisionActionType;
}

export interface DocumentRedactionPageReview {
  runId: string;
  pageId: string;
  reviewStatus: RedactionPageReviewStatus;
  reviewEtag: string;
  firstReviewedBy: string | null;
  firstReviewedAt: string | null;
  requiresSecondReview: boolean;
  secondReviewStatus: RedactionSecondReviewStatus;
  secondReviewedBy: string | null;
  secondReviewedAt: string | null;
  updatedAt: string;
}

export interface PatchDocumentRedactionPageReviewRequest {
  reviewStatus: RedactionPageReviewStatus;
  reviewEtag: string;
  reason?: string;
}

export interface DocumentRedactionRunPage {
  runId: string;
  pageId: string;
  pageIndex: number;
  findingCount: number;
  unresolvedCount: number;
  reviewStatus: RedactionPageReviewStatus;
  reviewEtag: string;
  requiresSecondReview: boolean;
  secondReviewStatus: RedactionSecondReviewStatus;
  secondReviewedBy: string | null;
  secondReviewedAt: string | null;
  lastReviewedBy: string | null;
  lastReviewedAt: string | null;
  previewStatus: RedactionOutputStatus | null;
  topFindings: DocumentRedactionFinding[];
}

export interface DocumentRedactionRunPageListResponse {
  runId: string;
  items: DocumentRedactionRunPage[];
  nextCursor: number | null;
}

export interface DocumentRedactionAreaMask {
  id: string;
  runId: string;
  pageId: string;
  geometryJson: Record<string, unknown>;
  maskReason: string;
  versionEtag: string;
  supersedesAreaMaskId: string | null;
  supersededByAreaMaskId: string | null;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface PatchDocumentRedactionAreaMaskRequest {
  versionEtag: string;
  geometryJson: Record<string, unknown>;
  maskReason: string;
  findingId?: string;
  findingDecisionEtag?: string;
}

export interface CreateDocumentRedactionAreaMaskRequest {
  geometryJson: Record<string, unknown>;
  maskReason: string;
  findingId?: string;
  findingDecisionEtag?: string;
}

export interface PatchDocumentRedactionAreaMaskResponse {
  areaMask: DocumentRedactionAreaMask;
  finding: DocumentRedactionFinding | null;
}

export interface DocumentRedactionTimelineEvent {
  sourceTable: string;
  sourceTablePrecedence: number;
  eventId: string;
  runId: string;
  pageId: string | null;
  findingId: string | null;
  eventType: string;
  actorUserId: string;
  reason: string | null;
  createdAt: string;
  detailsJson: Record<string, unknown>;
}

export interface DocumentRedactionRunEventsResponse {
  runId: string;
  items: DocumentRedactionTimelineEvent[];
}

export interface DocumentRedactionPreviewStatusResponse {
  runId: string;
  pageId: string;
  status: RedactionOutputStatus;
  previewSha256: string | null;
  generatedAt: string | null;
  failureReason: string | null;
  runOutputStatus: RedactionOutputStatus | null;
  runOutputManifestSha256: string | null;
  runOutputReadinessState: RedactionRunOutputReadinessState | null;
  downstreamReady: boolean;
}

export interface DocumentRedactionRunOutput {
  runId: string;
  status: RedactionOutputStatus;
  reviewStatus: RedactionRunReviewStatus;
  readinessState: RedactionRunOutputReadinessState;
  downstreamReady: boolean;
  outputManifestSha256: string | null;
  pageCount: number;
  startedAt: string | null;
  generatedAt: string | null;
  canceledBy: string | null;
  canceledAt: string | null;
  failureReason: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentRedactionOverviewResponse {
  documentId: string;
  projectId: string;
  projection: DocumentRedactionProjection | null;
  activeRun: DocumentRedactionRun | null;
  latestRun: DocumentRedactionRun | null;
  totalRuns: number;
  pageCount: number;
  findingsByCategory: Record<string, number>;
  unresolvedFindings: number;
  autoAppliedFindings: number;
  needsReviewFindings: number;
  overriddenFindings: number;
  pagesBlockedForReview: number;
  previewReadyPages: number;
  previewTotalPages: number;
  previewFailedPages: number;
}

export interface DocumentRedactionComparePage {
  pageId: string;
  pageIndex: number;
  baseFindingCount: number;
  candidateFindingCount: number;
  changedDecisionCount: number;
  changedActionCount: number;
  baseDecisionCounts: Record<RedactionDecisionStatus, number>;
  candidateDecisionCounts: Record<RedactionDecisionStatus, number>;
  decisionStatusDeltas: Record<RedactionDecisionStatus, number>;
  baseActionCounts: Record<RedactionDecisionActionType, number>;
  candidateActionCounts: Record<RedactionDecisionActionType, number>;
  actionTypeDeltas: Record<RedactionDecisionActionType, number>;
  actionCompareState: RedactionComparePageActionState;
  changedReviewStatus: boolean;
  changedSecondReviewStatus: boolean;
  baseReview: DocumentRedactionPageReview | null;
  candidateReview: DocumentRedactionPageReview | null;
  basePreviewStatus: RedactionOutputStatus | null;
  candidatePreviewStatus: RedactionOutputStatus | null;
  previewReadyDelta: number;
}

export type RedactionPolicyWarningCode =
  | "BROAD_ALLOW_RULE"
  | "INCONSISTENT_THRESHOLD";
export type RedactionPolicyWarningSeverity = "WARNING";

export interface DocumentRedactionPolicyWarning {
  code: RedactionPolicyWarningCode;
  severity: RedactionPolicyWarningSeverity;
  message: string;
  affectedCategories: string[];
}

export interface DocumentRedactionCompareResponse {
  documentId: string;
  projectId: string;
  baseRun: DocumentRedactionRun;
  candidateRun: DocumentRedactionRun;
  changedPageCount: number;
  changedDecisionCount: number;
  changedActionCount: number;
  compareActionState: RedactionCompareActionState;
  candidatePolicyStatus: RedactionPolicyStatus | null;
  comparisonOnlyCandidate: boolean;
  preActivationWarnings: DocumentRedactionPolicyWarning[];
  items: DocumentRedactionComparePage[];
}

export interface ActivateDocumentRedactionRunResponse {
  projection: DocumentRedactionProjection;
  run: DocumentRedactionRun;
}

export type GovernanceArtifactStatus =
  | "UNAVAILABLE"
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";
export type GovernanceReadinessStatus = "PENDING" | "READY" | "FAILED";
export type GovernanceGenerationStatus =
  | "IDLE"
  | "RUNNING"
  | "FAILED"
  | "CANCELED";
export type GovernanceLedgerVerificationStatus = "PENDING" | "VALID" | "INVALID";
export type GovernanceLedgerVerificationResult = "VALID" | "INVALID";
export type GovernanceLedgerEntriesView = "list" | "timeline";
export type GovernanceRunEventType =
  | "RUN_CREATED"
  | "MANIFEST_STARTED"
  | "MANIFEST_SUCCEEDED"
  | "MANIFEST_FAILED"
  | "MANIFEST_CANCELED"
  | "LEDGER_STARTED"
  | "LEDGER_SUCCEEDED"
  | "LEDGER_FAILED"
  | "LEDGER_CANCELED"
  | "LEDGER_VERIFY_STARTED"
  | "LEDGER_VERIFIED_VALID"
  | "LEDGER_VERIFIED_INVALID"
  | "LEDGER_VERIFY_CANCELED"
  | "REGENERATE_REQUESTED"
  | "RUN_CANCELED"
  | "READY_SET"
  | "READY_FAILED";

export interface GovernanceRunSummary {
  runId: string;
  projectId: string;
  documentId: string;
  runStatus: RedactionRunStatus;
  reviewStatus: RedactionRunReviewStatus | null;
  approvedSnapshotKey: string | null;
  approvedSnapshotSha256: string | null;
  runOutputStatus: RedactionOutputStatus | null;
  runOutputManifestSha256: string | null;
  runCreatedAt: string;
  runFinishedAt: string | null;
  readinessStatus: GovernanceReadinessStatus;
  generationStatus: GovernanceGenerationStatus;
  readyManifestId: string | null;
  readyLedgerId: string | null;
  latestManifestSha256: string | null;
  latestLedgerSha256: string | null;
  ledgerVerificationStatus: GovernanceLedgerVerificationStatus;
  readyAt: string | null;
  lastErrorCode: string | null;
  updatedAt: string;
}

export interface GovernanceReadinessProjection {
  runId: string;
  projectId: string;
  documentId: string;
  status: GovernanceReadinessStatus;
  generationStatus: GovernanceGenerationStatus;
  manifestId: string | null;
  ledgerId: string | null;
  lastLedgerVerificationRunId: string | null;
  lastManifestSha256: string | null;
  lastLedgerSha256: string | null;
  ledgerVerificationStatus: GovernanceLedgerVerificationStatus;
  ledgerVerifiedAt: string | null;
  readyAt: string | null;
  lastErrorCode: string | null;
  updatedAt: string;
}

export interface GovernanceManifestAttempt {
  id: string;
  runId: string;
  projectId: string;
  documentId: string;
  sourceReviewSnapshotKey: string;
  sourceReviewSnapshotSha256: string;
  attemptNumber: number;
  supersedesManifestId: string | null;
  supersededByManifestId: string | null;
  status: GovernanceArtifactStatus;
  manifestKey: string | null;
  manifestSha256: string | null;
  formatVersion: number;
  startedAt: string | null;
  finishedAt: string | null;
  canceledBy: string | null;
  canceledAt: string | null;
  failureReason: string | null;
  createdBy: string;
  createdAt: string;
}

export interface GovernanceLedgerAttempt {
  id: string;
  runId: string;
  projectId: string;
  documentId: string;
  sourceReviewSnapshotKey: string;
  sourceReviewSnapshotSha256: string;
  attemptNumber: number;
  supersedesLedgerId: string | null;
  supersededByLedgerId: string | null;
  status: GovernanceArtifactStatus;
  ledgerKey: string | null;
  ledgerSha256: string | null;
  hashChainVersion: string;
  startedAt: string | null;
  finishedAt: string | null;
  canceledBy: string | null;
  canceledAt: string | null;
  failureReason: string | null;
  createdBy: string;
  createdAt: string;
}

export interface DocumentGovernanceRunOverviewResponse {
  documentId: string;
  projectId: string;
  activeRunId: string | null;
  run: GovernanceRunSummary;
  readiness: GovernanceReadinessProjection;
  manifestAttempts: GovernanceManifestAttempt[];
  ledgerAttempts: GovernanceLedgerAttempt[];
}

export interface DocumentGovernanceOverviewResponse {
  documentId: string;
  projectId: string;
  activeRunId: string | null;
  totalRuns: number;
  approvedRuns: number;
  readyRuns: number;
  pendingRuns: number;
  failedRuns: number;
  latestRunId: string | null;
  latestReadyRunId: string | null;
  latestRun: GovernanceRunSummary | null;
  latestReadyRun: GovernanceRunSummary | null;
}

export interface DocumentGovernanceRunsResponse {
  documentId: string;
  projectId: string;
  activeRunId: string | null;
  items: GovernanceRunSummary[];
}

export interface GovernanceRunEvent {
  id: string;
  runId: string;
  eventType: GovernanceRunEventType;
  actorUserId: string | null;
  fromStatus: string | null;
  toStatus: string | null;
  reason: string | null;
  createdAt: string;
  screeningSafe: boolean;
}

export interface DocumentGovernanceRunEventsResponse {
  runId: string;
  items: GovernanceRunEvent[];
}

export interface DocumentGovernanceManifestResponse {
  overview: DocumentGovernanceRunOverviewResponse;
  latestAttempt: GovernanceManifestAttempt | null;
  manifestJson: Record<string, unknown> | null;
  streamSha256: string | null;
  hashMatches: boolean;
  internalOnly: boolean;
  exportApproved: boolean;
  notExportApproved: boolean;
}

export interface DocumentGovernanceManifestStatusResponse {
  runId: string;
  status: GovernanceArtifactStatus;
  latestAttempt: GovernanceManifestAttempt | null;
  attemptCount: number;
  readyManifestId: string | null;
  latestManifestSha256: string | null;
  generationStatus: GovernanceGenerationStatus;
  readinessStatus: GovernanceReadinessStatus;
  updatedAt: string;
}

export interface GovernanceManifestEntry {
  entryId: string;
  appliedAction: string;
  category: string;
  pageId: string;
  pageIndex: number | null;
  lineId: string | null;
  locationRef: Record<string, unknown>;
  basisPrimary: string;
  confidence: number | null;
  secondaryBasisSummary: Record<string, unknown> | null;
  finalDecisionState: string;
  reviewState: string;
  policySnapshotHash: string | null;
  policyId: string | null;
  policyFamilyId: string | null;
  policyVersion: string | null;
  decisionTimestamp: string | null;
  decisionBy: string | null;
  decisionEtag: string | null;
}

export interface DocumentGovernanceManifestEntriesResponse {
  runId: string;
  status: GovernanceArtifactStatus;
  manifestId: string | null;
  manifestSha256: string | null;
  sourceReviewSnapshotSha256: string | null;
  totalCount: number;
  nextCursor: number | null;
  internalOnly: boolean;
  exportApproved: boolean;
  notExportApproved: boolean;
  items: GovernanceManifestEntry[];
}

export interface DocumentGovernanceManifestHashResponse {
  runId: string;
  status: GovernanceArtifactStatus;
  manifestId: string | null;
  manifestSha256: string | null;
  streamSha256: string | null;
  hashMatches: boolean;
  internalOnly: boolean;
  exportApproved: boolean;
  notExportApproved: boolean;
}

export interface DocumentGovernanceLedgerResponse {
  overview: DocumentGovernanceRunOverviewResponse;
  latestAttempt: GovernanceLedgerAttempt | null;
  ledgerJson: Record<string, unknown> | null;
  streamSha256: string | null;
  hashMatches: boolean;
  internalOnly: boolean;
}

export interface DocumentGovernanceLedgerStatusResponse {
  runId: string;
  status: GovernanceArtifactStatus;
  latestAttempt: GovernanceLedgerAttempt | null;
  attemptCount: number;
  readyLedgerId: string | null;
  latestLedgerSha256: string | null;
  generationStatus: GovernanceGenerationStatus;
  readinessStatus: GovernanceReadinessStatus;
  ledgerVerificationStatus: GovernanceLedgerVerificationStatus;
  updatedAt: string;
}

export interface GovernanceLedgerEntry {
  rowId: string;
  rowIndex: number;
  findingId: string;
  pageId: string;
  pageIndex: number | null;
  lineId: string | null;
  category: string;
  actionType: string;
  beforeTextRef: Record<string, unknown>;
  afterTextRef: Record<string, unknown>;
  detectorEvidence: Record<string, unknown>;
  assistExplanationKey: string | null;
  assistExplanationSha256: string | null;
  actorUserId: string | null;
  decisionTimestamp: string | null;
  overrideReason: string | null;
  finalDecisionState: string | null;
  policySnapshotHash: string | null;
  policyId: string | null;
  policyFamilyId: string | null;
  policyVersion: string | null;
  prevHash: string;
  rowHash: string;
}

export interface DocumentGovernanceLedgerEntriesResponse {
  runId: string;
  status: GovernanceArtifactStatus;
  view: GovernanceLedgerEntriesView;
  ledgerId: string | null;
  ledgerSha256: string | null;
  hashChainVersion: string | null;
  totalCount: number;
  nextCursor: number | null;
  verificationStatus: GovernanceLedgerVerificationStatus;
  items: GovernanceLedgerEntry[];
}

export interface DocumentGovernanceLedgerSummaryResponse {
  runId: string;
  status: GovernanceArtifactStatus;
  ledgerId: string | null;
  ledgerSha256: string | null;
  hashChainVersion: string | null;
  rowCount: number;
  hashChainHead: string | null;
  hashChainValid: boolean;
  verificationStatus: GovernanceLedgerVerificationStatus;
  categoryCounts: Record<string, number>;
  actionCounts: Record<string, number>;
  overrideCount: number;
  assistReferenceCount: number;
  internalOnly: boolean;
}

export interface GovernanceLedgerVerificationRun {
  id: string;
  runId: string;
  attemptNumber: number;
  supersedesVerificationRunId: string | null;
  supersededByVerificationRunId: string | null;
  status: GovernanceArtifactStatus;
  verificationResult: GovernanceLedgerVerificationResult | null;
  resultJson: Record<string, unknown> | null;
  startedAt: string | null;
  finishedAt: string | null;
  canceledBy: string | null;
  canceledAt: string | null;
  failureReason: string | null;
  createdBy: string;
  createdAt: string;
}

export interface DocumentGovernanceLedgerVerifyStatusResponse {
  runId: string;
  verificationStatus: GovernanceLedgerVerificationStatus;
  attemptCount: number;
  latestAttempt: GovernanceLedgerVerificationRun | null;
  latestCompletedAttempt: GovernanceLedgerVerificationRun | null;
  readyLedgerId: string | null;
  latestLedgerSha256: string | null;
  lastVerifiedAt: string | null;
}

export interface DocumentGovernanceLedgerVerifyRunsResponse {
  runId: string;
  verificationStatus: GovernanceLedgerVerificationStatus;
  items: GovernanceLedgerVerificationRun[];
}

export interface DocumentGovernanceLedgerVerifyDetailResponse {
  runId: string;
  verificationStatus: GovernanceLedgerVerificationStatus;
  attempt: GovernanceLedgerVerificationRun;
}

export type ExportCandidateSourcePhase = "PHASE6" | "PHASE7" | "PHASE9" | "PHASE10";
export type ExportCandidateSourceArtifactKind =
  | "REDACTION_RUN_OUTPUT"
  | "DEPOSIT_BUNDLE"
  | "DERIVATIVE_SNAPSHOT";
export type ExportCandidateKind =
  | "SAFEGUARDED_PREVIEW"
  | "POLICY_RERUN"
  | "DEPOSIT_BUNDLE"
  | "SAFEGUARDED_DERIVATIVE";
export type ExportCandidateEligibilityStatus = "ELIGIBLE" | "SUPERSEDED";

export interface ExportCandidateSnapshotContract {
  id: string;
  projectId: string;
  sourcePhase: ExportCandidateSourcePhase;
  sourceArtifactKind: ExportCandidateSourceArtifactKind;
  sourceRunId: string | null;
  sourceArtifactId: string;
  governanceRunId: string | null;
  governanceManifestId: string | null;
  governanceLedgerId: string | null;
  governanceManifestSha256: string | null;
  governanceLedgerSha256: string | null;
  policySnapshotHash: string | null;
  policyId: string | null;
  policyFamilyId: string | null;
  policyVersion: string | null;
  candidateKind: ExportCandidateKind;
  artefactManifestJson: Record<string, unknown>;
  candidateSha256: string;
  eligibilityStatus: ExportCandidateEligibilityStatus;
  supersedesCandidateSnapshotId: string | null;
  supersededByCandidateSnapshotId: string | null;
  createdBy: string;
  createdAt: string;
}

export interface ExportCandidateSnapshotContractsResponse {
  projectId: string;
  items: ExportCandidateSnapshotContract[];
}

export type ExportRequestRiskClassification = "STANDARD" | "HIGH";
export type ExportRequestReviewPath = "SINGLE" | "DUAL";
export type ExportRequestStatus =
  | "SUBMITTED"
  | "RESUBMITTED"
  | "IN_REVIEW"
  | "APPROVED"
  | "EXPORTED"
  | "REJECTED"
  | "RETURNED";
export type ExportRequestEventType =
  | "REQUEST_SUBMITTED"
  | "REQUEST_REVIEW_STARTED"
  | "REQUEST_RESUBMITTED"
  | "REQUEST_APPROVED"
  | "REQUEST_EXPORTED"
  | "REQUEST_REJECTED"
  | "REQUEST_RETURNED"
  | "REQUEST_RECEIPT_ATTACHED"
  | "REQUEST_REMINDER_SENT"
  | "REQUEST_ESCALATED";
export type ExportRequestReviewStage = "PRIMARY" | "SECONDARY";
export type ExportRequestReviewStatus =
  | "PENDING"
  | "IN_REVIEW"
  | "APPROVED"
  | "RETURNED"
  | "REJECTED";
export type ExportRequestReviewEventType =
  | "REVIEW_CREATED"
  | "REVIEW_CLAIMED"
  | "REVIEW_STARTED"
  | "REVIEW_APPROVED"
  | "REVIEW_REJECTED"
  | "REVIEW_RETURNED"
  | "REVIEW_RELEASED";
export type ExportRequestDecision = "APPROVE" | "REJECT" | "RETURN";
export type ExportReviewAgingBucket =
  | "UNSTARTED"
  | "NO_SLA"
  | "ON_TRACK"
  | "DUE_SOON"
  | "OVERDUE";

export type ExportCandidateResponse = ExportCandidateSnapshotContract;

export interface ExportCandidateListResponse {
  items: ExportCandidateResponse[];
}

export interface ExportReleasePackPreviewResponse {
  candidate: ExportCandidateResponse;
  releasePack: Record<string, unknown>;
  releasePackSha256: string;
  releasePackKey: string;
  riskClassification: ExportRequestRiskClassification;
  riskReasonCodes: string[];
  reviewPath: ExportRequestReviewPath;
  requiresSecondReview: boolean;
}

export interface CreateExportRequestRequest {
  candidateSnapshotId: string;
  purposeStatement: string;
  bundleProfile?: string | null;
}

export interface ResubmitExportRequestRequest {
  candidateSnapshotId?: string | null;
  purposeStatement?: string | null;
  bundleProfile?: string | null;
}

export interface ExportRequest {
  id: string;
  projectId: string;
  candidateSnapshotId: string;
  candidateOriginPhase: ExportCandidateSourcePhase;
  candidateKind: ExportCandidateKind;
  bundleProfile: string | null;
  riskClassification: ExportRequestRiskClassification;
  riskReasonCodesJson: string[];
  reviewPath: ExportRequestReviewPath;
  requiresSecondReview: boolean;
  supersedesExportRequestId: string | null;
  supersededByExportRequestId: string | null;
  requestRevision: number;
  purposeStatement: string;
  status: ExportRequestStatus;
  submittedBy: string;
  submittedAt: string;
  firstReviewStartedBy: string | null;
  firstReviewStartedAt: string | null;
  slaDueAt: string | null;
  lastQueueActivityAt: string | null;
  retentionUntil: string | null;
  finalReviewId: string | null;
  finalDecisionBy: string | null;
  finalDecisionAt: string | null;
  finalDecisionReason: string | null;
  finalReturnComment: string | null;
  releasePackKey: string;
  releasePackSha256: string;
  releasePackJson: Record<string, unknown>;
  releasePackCreatedAt: string;
  receiptId: string | null;
  receiptKey: string | null;
  receiptSha256: string | null;
  receiptCreatedBy: string | null;
  receiptCreatedAt: string | null;
  exportedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ExportRequestListResponse {
  items: ExportRequest[];
  nextCursor: number | null;
}

export interface ExportRequestStatusResponse {
  id: string;
  status: ExportRequestStatus;
  riskClassification: ExportRequestRiskClassification;
  reviewPath: ExportRequestReviewPath;
  requiresSecondReview: boolean;
  requestRevision: number;
  submittedAt: string;
  lastQueueActivityAt: string | null;
  slaDueAt: string | null;
  retentionUntil: string | null;
  finalDecisionAt: string | null;
  finalDecisionBy: string | null;
  finalDecisionReason: string | null;
  finalReturnComment: string | null;
  exportedAt: string | null;
}

export interface ExportRequestReleasePackResponse {
  requestId: string;
  requestRevision: number;
  releasePack: Record<string, unknown>;
  releasePackSha256: string;
  releasePackKey: string;
  releasePackCreatedAt: string;
}

export interface ExportValidationIssue {
  code: string;
  detail: string;
  field: string | null;
  expected: string | null;
  actual: string | null;
  blocking: boolean;
}

export interface ExportValidationCheck {
  checkId: string;
  passed: boolean;
  issueCount: number;
  issues: ExportValidationIssue[];
  facts: Record<string, unknown>;
}

export interface ExportRequestValidationSummaryResponse {
  requestId: string;
  projectId: string;
  requestStatus: ExportRequestStatus;
  requestRevision: number;
  generatedAt: string;
  isValid: boolean;
  releasePack: ExportValidationCheck;
  auditCompleteness: ExportValidationCheck;
}

export interface ExportProvenanceLineageNode {
  artifactKind: string;
  stableIdentifier: string;
  immutableReference: string;
  parentReferences: string[];
}

export interface ExportRequestProvenanceSummaryResponse {
  projectId: string;
  requestId: string;
  requestStatus: ExportRequestStatus;
  candidateSnapshotId: string;
  proofAttemptCount: number;
  currentProofId: string | null;
  currentAttemptNumber: number | null;
  currentProofGeneratedAt: string | null;
  rootSha256: string | null;
  signatureKeyRef: string | null;
  signatureStatus: "SIGNED" | "MISSING";
  lineageNodes: ExportProvenanceLineageNode[];
  references: Record<string, unknown>;
}

export interface ExportProvenanceProof {
  id: string;
  projectId: string;
  exportRequestId: string;
  candidateSnapshotId: string;
  attemptNumber: number;
  supersedesProofId: string | null;
  supersededByProofId: string | null;
  rootSha256: string;
  signatureKeyRef: string;
  signatureBytesKey: string;
  proofArtifactKey: string;
  proofArtifactSha256: string;
  createdBy: string;
  createdAt: string;
}

export interface ExportProvenanceProofListResponse {
  items: ExportProvenanceProof[];
}

export interface ExportProvenanceProofDetailResponse {
  proof: ExportProvenanceProof;
  artifact: Record<string, unknown>;
}

export interface RegenerateExportProvenanceProofResponse {
  proof: ExportProvenanceProof;
}

export type ExportDepositBundleKind =
  | "CONTROLLED_EVIDENCE"
  | "SAFEGUARDED_DEPOSIT";
export type ExportDepositBundleStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";
export type ExportBundleVerificationProjectionStatus =
  | "PENDING"
  | "VERIFIED"
  | "FAILED";
export type ExportBundleEventType =
  | "BUNDLE_BUILD_QUEUED"
  | "BUNDLE_REBUILD_REQUESTED"
  | "BUNDLE_BUILD_STARTED"
  | "BUNDLE_BUILD_SUCCEEDED"
  | "BUNDLE_BUILD_FAILED"
  | "BUNDLE_BUILD_CANCELED"
  | "BUNDLE_VERIFICATION_STARTED"
  | "BUNDLE_VERIFICATION_SUCCEEDED"
  | "BUNDLE_VERIFICATION_FAILED"
  | "BUNDLE_VERIFICATION_CANCELED"
  | "BUNDLE_VALIDATION_STARTED"
  | "BUNDLE_VALIDATION_SUCCEEDED"
  | "BUNDLE_VALIDATION_FAILED"
  | "BUNDLE_VALIDATION_CANCELED";

export interface ExportDepositBundle {
  id: string;
  projectId: string;
  exportRequestId: string;
  candidateSnapshotId: string;
  provenanceProofId: string;
  provenanceProofArtifactSha256: string;
  bundleKind: ExportDepositBundleKind;
  status: ExportDepositBundleStatus;
  attemptNumber: number;
  supersedesBundleId: string | null;
  supersededByBundleId: string | null;
  bundleKey: string | null;
  bundleSha256: string | null;
  failureReason: string | null;
  createdBy: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  canceledBy: string | null;
  canceledAt: string | null;
}

export interface ExportDepositBundleListResponse {
  items: ExportDepositBundle[];
}

export interface ExportBundleVerificationProjection {
  bundleId: string;
  status: ExportBundleVerificationProjectionStatus;
  lastVerificationRunId: string | null;
  verifiedAt: string | null;
  updatedAt: string;
}

export interface ExportBundleProfile {
  id: string;
  label: string;
  description: string;
  allowedBundleKinds: ExportDepositBundleKind[];
  requiredArchiveEntries: string[];
  requiredMetadataPaths: string[];
  forbiddenMetadataPaths: string[];
}

export interface ExportBundleProfilesResponse {
  items: ExportBundleProfile[];
}

export type ExportBundleValidationProjectionStatus =
  | "PENDING"
  | "READY"
  | "FAILED";

export interface ExportBundleValidationProjection {
  bundleId: string;
  profileId: string;
  status: ExportBundleValidationProjectionStatus;
  lastValidationRunId: string | null;
  readyAt: string | null;
  updatedAt: string;
}

export interface ExportDepositBundleDetailResponse {
  bundle: ExportDepositBundle;
  lineageAttempts: ExportDepositBundle[];
  verificationProjection: ExportBundleVerificationProjection | null;
  artifact: Record<string, unknown>;
}

export interface ExportDepositBundleStatusResponse {
  bundle: ExportDepositBundle;
  verificationProjection: ExportBundleVerificationProjection | null;
}

export interface ExportBundleEvent {
  id: string;
  bundleId: string;
  eventType: ExportBundleEventType;
  verificationRunId: string | null;
  validationRunId: string | null;
  actorUserId: string | null;
  reason: string | null;
  createdAt: string;
}

export interface ExportBundleEventsResponse {
  items: ExportBundleEvent[];
}

export interface ExportDepositBundleMutationResponse {
  bundle: ExportDepositBundle;
}

export type ExportBundleVerificationRunStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";

export interface ExportBundleVerificationRun {
  id: string;
  projectId: string;
  bundleId: string;
  attemptNumber: number;
  supersedesVerificationRunId: string | null;
  supersededByVerificationRunId: string | null;
  status: ExportBundleVerificationRunStatus;
  resultJson: Record<string, unknown>;
  createdBy: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  canceledBy: string | null;
  canceledAt: string | null;
  failureReason: string | null;
}

export interface ExportBundleVerificationResponse {
  bundle: ExportDepositBundle;
  verificationProjection: ExportBundleVerificationProjection | null;
  latestAttempt: ExportBundleVerificationRun | null;
  latestCompletedAttempt: ExportBundleVerificationRun | null;
}

export interface ExportBundleVerificationStatusResponse {
  bundleId: string;
  bundleStatus: ExportDepositBundleStatus;
  verificationProjection: ExportBundleVerificationProjection | null;
  latestAttempt: ExportBundleVerificationRun | null;
}

export interface ExportBundleVerificationRunsResponse {
  items: ExportBundleVerificationRun[];
}

export interface ExportBundleVerificationRunDetailResponse {
  verificationRun: ExportBundleVerificationRun;
}

export interface ExportBundleVerificationRunStatusResponse {
  verificationRun: ExportBundleVerificationRun;
}

export interface ExportBundleVerificationRunMutationResponse {
  verificationRun: ExportBundleVerificationRun;
}

export type ExportBundleValidationRunStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";

export interface ExportBundleValidationRun {
  id: string;
  projectId: string;
  bundleId: string;
  profileId: string;
  profileSnapshotKey: string;
  profileSnapshotSha256: string;
  status: ExportBundleValidationRunStatus;
  attemptNumber: number;
  supersedesValidationRunId: string | null;
  supersededByValidationRunId: string | null;
  resultJson: Record<string, unknown>;
  failureReason: string | null;
  createdBy: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  canceledBy: string | null;
  canceledAt: string | null;
}

export interface ExportBundleValidationStatusResponse {
  bundleId: string;
  bundleStatus: ExportDepositBundleStatus;
  profileId: string;
  verificationProjection: ExportBundleVerificationProjection | null;
  validationProjection: ExportBundleValidationProjection | null;
  latestAttempt: ExportBundleValidationRun | null;
  inFlightAttempt: ExportBundleValidationRun | null;
  lastSuccessfulAttempt: ExportBundleValidationRun | null;
}

export interface ExportBundleValidationRunsResponse {
  items: ExportBundleValidationRun[];
}

export interface ExportBundleValidationRunDetailResponse {
  validationRun: ExportBundleValidationRun;
}

export interface ExportBundleValidationRunStatusResponse {
  validationRun: ExportBundleValidationRun;
}

export interface ExportBundleValidationRunMutationResponse {
  validationRun: ExportBundleValidationRun;
}

export interface ExportReceipt {
  id: string;
  exportRequestId: string;
  attemptNumber: number;
  supersedesReceiptId: string | null;
  supersededByReceiptId: string | null;
  receiptKey: string;
  receiptSha256: string;
  createdBy: string;
  createdAt: string;
  exportedAt: string;
}

export interface ExportReceiptListResponse {
  items: ExportReceipt[];
}

export interface AttachExportReceiptRequest {
  receiptKey: string;
  receiptSha256: string;
  exportedAt: string;
}

export interface AttachExportReceiptResponse {
  request: ExportRequest;
  receipt: ExportReceipt;
}

export interface ExportRequestEvent {
  id: string;
  exportRequestId: string;
  eventType: ExportRequestEventType;
  fromStatus: ExportRequestStatus | null;
  toStatus: ExportRequestStatus;
  actorUserId: string | null;
  reason: string | null;
  createdAt: string;
}

export interface ExportRequestEventsResponse {
  items: ExportRequestEvent[];
}

export interface ExportRequestReview {
  id: string;
  exportRequestId: string;
  reviewStage: ExportRequestReviewStage;
  isRequired: boolean;
  status: ExportRequestReviewStatus;
  assignedReviewerUserId: string | null;
  assignedAt: string | null;
  actedByUserId: string | null;
  actedAt: string | null;
  decisionReason: string | null;
  returnComment: string | null;
  reviewEtag: string;
  createdAt: string;
  updatedAt: string;
}

export interface ExportRequestReviewsResponse {
  items: ExportRequestReview[];
}

export interface ExportRequestReviewEvent {
  id: string;
  reviewId: string;
  exportRequestId: string;
  reviewStage: ExportRequestReviewStage;
  eventType: ExportRequestReviewEventType;
  actorUserId: string | null;
  assignedReviewerUserId: string | null;
  decisionReason: string | null;
  returnComment: string | null;
  createdAt: string;
}

export interface ExportRequestReviewEventsResponse {
  items: ExportRequestReviewEvent[];
}

export interface ExportReviewQueueItem {
  request: ExportRequest;
  reviews: ExportRequestReview[];
  activeReviewId: string | null;
  activeReviewStage: ExportRequestReviewStage | null;
  activeReviewStatus: ExportRequestReviewStatus | null;
  activeReviewAssignedReviewerUserId: string | null;
  agingBucket: ExportReviewAgingBucket;
  slaSecondsRemaining: number | null;
  isSlaBreached: boolean;
}

export interface ExportReviewQueueResponse {
  items: ExportReviewQueueItem[];
  readOnly: boolean;
}

export interface ExportReviewEtagRequest {
  reviewEtag: string;
}

export interface ExportStartReviewRequest {
  reviewId: string;
  reviewEtag: string;
}

export interface ExportDecisionRequest {
  reviewId: string;
  reviewEtag: string;
  decision: ExportRequestDecision;
  decisionReason?: string | null;
  returnComment?: string | null;
}

export interface ExportReviewActionResponse {
  request: ExportRequest;
  review: ExportRequestReview;
}

export type IndexKind = "SEARCH" | "ENTITY" | "DERIVATIVE";
export type IndexStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";

export interface ProjectIndex {
  id: string;
  projectId: string;
  kind: IndexKind;
  version: number;
  sourceSnapshotJson: Record<string, unknown>;
  sourceSnapshotSha256: string;
  buildParametersJson: Record<string, unknown>;
  rebuildDedupeKey: string;
  status: IndexStatus;
  supersedesIndexId: string | null;
  supersededByIndexId: string | null;
  failureReason: string | null;
  createdBy: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  cancelRequested: boolean;
  cancelRequestedBy: string | null;
  cancelRequestedAt: string | null;
  canceledBy: string | null;
  canceledAt: string | null;
  activatedBy: string | null;
  activatedAt: string | null;
}

export interface ProjectIndexStatusResponse {
  id: string;
  projectId: string;
  kind: IndexKind;
  status: IndexStatus;
  startedAt: string | null;
  finishedAt: string | null;
  cancelRequested: boolean;
  cancelRequestedAt: string | null;
  canceledAt: string | null;
  failureReason: string | null;
}

export interface ProjectIndexListResponse {
  items: ProjectIndex[];
}

export interface ProjectIndexProjection {
  projectId: string;
  activeSearchIndexId: string | null;
  activeEntityIndexId: string | null;
  activeDerivativeIndexId: string | null;
  updatedAt: string;
}

export interface ProjectActiveIndexesResponse {
  projectId: string;
  projection: ProjectIndexProjection | null;
  searchIndex: ProjectIndex | null;
  entityIndex: ProjectIndex | null;
  derivativeIndex: ProjectIndex | null;
}

export interface CreateProjectIndexRebuildRequest {
  sourceSnapshotJson: Record<string, unknown>;
  buildParametersJson?: Record<string, unknown>;
  supersedesIndexId?: string | null;
}

export interface ProjectIndexRebuildResponse {
  index: ProjectIndex;
  created: boolean;
  reason: string;
}

export interface ProjectIndexCancelResponse {
  index: ProjectIndex;
  terminal: boolean;
}

export interface ProjectIndexActivateResponse {
  index: ProjectIndex;
  projection: ProjectIndexProjection;
}

export interface ProjectSearchHit {
  searchDocumentId: string;
  searchIndexId: string;
  documentId: string;
  runId: string;
  pageId: string;
  pageNumber: number;
  lineId: string | null;
  tokenId: string | null;
  sourceKind: TranscriptionTokenSourceKind;
  sourceRefId: string;
  matchSpanJson: Record<string, unknown> | null;
  tokenGeometryJson: Record<string, unknown> | null;
  searchText: string;
  searchMetadataJson: Record<string, unknown>;
}

export interface ProjectSearchResponse {
  searchIndexId: string;
  items: ProjectSearchHit[];
  nextCursor: number | null;
}

export interface ProjectSearchResultOpenResponse {
  searchIndexId: string;
  searchDocumentId: string;
  documentId: string;
  runId: string;
  pageNumber: number;
  lineId: string | null;
  tokenId: string | null;
  sourceKind: TranscriptionTokenSourceKind;
  sourceRefId: string;
  workspacePath: string;
}

export type ControlledEntityType = "PERSON" | "PLACE" | "ORGANISATION" | "DATE";
export type EntityOccurrenceSpanBasisKind = "LINE_TEXT" | "PAGE_WINDOW_TEXT" | "NONE";

export interface ControlledEntity {
  id: string;
  projectId: string;
  entityIndexId: string;
  entityType: ControlledEntityType;
  displayValue: string;
  canonicalValue: string;
  confidenceSummaryJson: Record<string, unknown>;
  occurrenceCount: number;
  createdAt: string;
}

export interface EntityOccurrence {
  id: string;
  entityIndexId: string;
  entityId: string;
  documentId: string;
  runId: string;
  pageId: string;
  pageNumber: number;
  lineId: string | null;
  tokenId: string | null;
  sourceKind: TranscriptionTokenSourceKind;
  sourceRefId: string;
  confidence: number;
  occurrenceSpanJson: Record<string, unknown> | null;
  occurrenceSpanBasisKind: EntityOccurrenceSpanBasisKind;
  occurrenceSpanBasisRef: string | null;
  tokenGeometryJson: Record<string, unknown> | null;
  workspacePath: string;
}

export interface ProjectEntityListResponse {
  entityIndexId: string;
  items: ControlledEntity[];
  nextCursor: number | null;
}

export interface ProjectEntityDetailResponse {
  entityIndexId: string;
  entity: ControlledEntity;
}

export interface ProjectEntityOccurrencesResponse {
  entityIndexId: string;
  entity: ControlledEntity;
  items: EntityOccurrence[];
  nextCursor: number | null;
}

export type JobType =
  | "NOOP"
  | "EXTRACT_PAGES"
  | "RENDER_THUMBNAILS"
  | "PREPROCESS_DOCUMENT"
  | "PREPROCESS_PAGE"
  | "FINALIZE_PREPROCESS_RUN"
  | "LAYOUT_ANALYZE_DOCUMENT"
  | "LAYOUT_ANALYZE_PAGE"
  | "FINALIZE_LAYOUT_RUN";
export type JobStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";
export type JobEventType =
  | "JOB_CREATED"
  | "JOB_STARTED"
  | "JOB_SUCCEEDED"
  | "JOB_FAILED"
  | "JOB_CANCELED"
  | "JOB_RETRY_APPENDED";
export type NoopMode = "SUCCESS" | "FAIL_ONCE" | "FAIL_ALWAYS";

export interface ProjectJob {
  id: string;
  projectId: string;
  attemptNumber: number;
  supersedesJobId: string | null;
  supersededByJobId: string | null;
  type: JobType;
  dedupeKey: string;
  status: JobStatus;
  attempts: number;
  maxAttempts: number;
  payloadJson: Record<string, unknown>;
  createdBy: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  canceledBy: string | null;
  canceledAt: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  cancelRequested: boolean;
  cancelRequestedBy: string | null;
  cancelRequestedAt: string | null;
}

export interface ProjectJobListResponse {
  items: ProjectJob[];
  nextCursor: number | null;
}

export interface ProjectJobStatusResponse {
  id: string;
  projectId: string;
  status: JobStatus;
  attempts: number;
  maxAttempts: number;
  startedAt: string | null;
  finishedAt: string | null;
  canceledAt: string | null;
  canceledBy: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  supersededByJobId: string | null;
  cancelRequested: boolean;
}

export interface ProjectJobEvent {
  id: number;
  jobId: string;
  projectId: string;
  eventType: JobEventType;
  fromStatus: JobStatus | null;
  toStatus: JobStatus;
  actorUserId: string | null;
  detailsJson: Record<string, unknown>;
  createdAt: string;
}

export interface ProjectJobEventListResponse {
  items: ProjectJobEvent[];
  nextCursor: number | null;
}

export interface CreateNoopJobRequest {
  logicalKey: string;
  mode: NoopMode;
  maxAttempts?: number;
  delayMs?: number;
}

export interface ProjectJobMutationResponse {
  job: ProjectJob;
  created: boolean;
  reason: string;
}

export interface ProjectJobCancelResponse {
  job: ProjectJob;
  terminal: boolean;
}

export interface ProjectJobSummaryResponse {
  runningJobs: number;
  lastJobStatus: JobStatus | null;
}

export interface AuditEvent {
  id: string;
  chainIndex: number;
  timestamp: string;
  actorUserId: string | null;
  projectId: string | null;
  eventType: AuditEventType;
  objectType: string | null;
  objectId: string | null;
  ip: string | null;
  userAgent: string | null;
  requestId: string;
  metadataJson: Record<string, unknown>;
  prevHash: string;
  rowHash: string;
}

export interface AuditEventListResponse {
  items: AuditEvent[];
  nextCursor: number | null;
}

export interface AuditIntegrityResponse {
  checkedRows: number;
  chainHead: string | null;
  isValid: boolean;
  firstInvalidChainIndex: number | null;
  firstInvalidEventId: string | null;
  detail: string;
}

export type OperationsAlertState = "OPEN" | "OK" | "UNAVAILABLE";
export type OperationsSloStatus = "MEETING" | "BREACHING" | "UNAVAILABLE";
export type OperationsTimelineSeverity = "INFO" | "WARNING" | "ERROR";
export type OperationsTimelineScope =
  | "api"
  | "auth"
  | "audit"
  | "readiness"
  | "operations"
  | "worker"
  | "telemetry";

export interface OperationsRouteMetric {
  routeTemplate: string;
  method: string;
  requestCount: number;
  errorCount: number;
  averageLatencyMs: number | null;
  p95LatencyMs: number | null;
}

export interface OperationsExporterStatus {
  mode: string;
  endpoint: string | null;
  state: string;
  detail: string;
}

export interface OperationsOverviewResponse {
  generatedAt: string;
  uptimeSeconds: number;
  requestCount: number;
  requestErrorCount: number;
  errorRatePercent: number;
  p95LatencyMs: number | null;
  readinessDbChecks: number;
  readinessDbFailures: number;
  readinessDbLastLatencyMs: number | null;
  readinessDbAvgLatencyMs: number | null;
  authSuccessCount: number;
  authFailureCount: number;
  auditWriteSuccessCount: number;
  auditWriteFailureCount: number;
  traceContextEnabled: boolean;
  queueDepth: number | null;
  queueDepthSource: string;
  queueDepthDetail: string;
  exporter: OperationsExporterStatus;
  topRoutes: OperationsRouteMetric[];
}

export interface OperationsExportAgingSummary {
  unstarted: number;
  noSla: number;
  onTrack: number;
  dueSoon: number;
  overdue: number;
  staleOpen: number;
}

export interface OperationsExportReminderSummary {
  due: number;
  sentLast24h: number;
  total: number;
}

export interface OperationsExportEscalationSummary {
  due: number;
  openEscalated: number;
  total: number;
}

export interface OperationsExportRetentionSummary {
  pendingCount: number;
  pendingWindowDays: number;
}

export interface OperationsExportTerminalSummary {
  approved: number;
  exported: number;
  rejected: number;
  returned: number;
}

export interface OperationsExportPolicySummary {
  slaHours: number;
  reminderAfterHours: number;
  reminderCooldownHours: number;
  escalationAfterSlaHours: number;
  escalationCooldownHours: number;
  staleOpenAfterDays: number;
  retentionStaleOpenDays: number;
  retentionTerminalApprovedDays: number;
  retentionTerminalOtherDays: number;
}

export interface OperationsExportStatusResponse {
  generatedAt: string;
  openRequestCount: number;
  aging: OperationsExportAgingSummary;
  reminders: OperationsExportReminderSummary;
  escalations: OperationsExportEscalationSummary;
  retention: OperationsExportRetentionSummary;
  terminal: OperationsExportTerminalSummary;
  policy: OperationsExportPolicySummary;
}

export interface OperationsSlo {
  key: string;
  name: string;
  target: string;
  current: string;
  status: OperationsSloStatus;
  detail: string;
}

export interface OperationsSloListResponse {
  items: OperationsSlo[];
}

export interface OperationsAlert {
  key: string;
  title: string;
  severity: "CRITICAL" | "WARNING" | "INFO";
  state: OperationsAlertState;
  detail: string;
  threshold: string;
  current: string;
  updatedAt: string;
}

export interface OperationsAlertListResponse {
  items: OperationsAlert[];
  nextCursor: number | null;
}

export interface OperationsTimelineEvent {
  id: number;
  occurredAt: string;
  scope: OperationsTimelineScope;
  severity: OperationsTimelineSeverity;
  message: string;
  requestId: string | null;
  traceId: string | null;
  routeTemplate: string | null;
  statusCode: number | null;
  detailsJson: Record<string, unknown>;
}

export interface OperationsTimelineListResponse {
  items: OperationsTimelineEvent[];
  nextCursor: number | null;
}

export interface ExportStubDisabledResponse {
  status: "DISABLED";
  code: "EXPORT_GATEWAY_DISABLED_PHASE0";
  detail: string;
  route: string;
  method: string;
  phase: "PHASE_0";
  futureContract: Record<string, unknown> | null;
}

export interface ExportDeferredResponse {
  status: "DEFERRED";
  code: "EXPORT_WORKFLOW_DEFERRED_TO_LATER_PROMPTS";
  detail: string;
  route: string;
  method: string;
}

export interface SecurityStatusResponse {
  generatedAt: string;
  environment: string;
  denyByDefaultEgress: boolean;
  outboundAllowlist: string[];
  lastSuccessfulEgressDenyTestAt: string | null;
  egressTestDetail: string;
  cspMode: "enforce" | "report-only" | string;
  lastBackupAt: string | null;
  reducedMotionPreferenceState: string;
  reducedTransparencyPreferenceState: string;
  exportGatewayState: string;
}

export interface BootstrapSurface {
  label: string;
  route: string;
  scope: "public" | "project" | "admin";
}

export interface ShellStateBreakpoint {
  state: Exclude<ShellState, "Focus">;
  minWidth: number;
}

export type ShellTaskContext = "standard" | "dense";

export interface ResolveAdaptiveShellStateInput {
  viewportWidth: number;
  viewportHeight: number;
  forceFocus?: boolean;
  taskContext?: ShellTaskContext;
}

export const shellStateBreakpoints: ShellStateBreakpoint[] = [
  { state: "Expanded", minWidth: 1360 },
  { state: "Balanced", minWidth: 1080 },
  { state: "Compact", minWidth: 820 }
];

export function resolveAdaptiveShellState(
  input: ResolveAdaptiveShellStateInput
): ShellState {
  const {
    viewportWidth,
    viewportHeight,
    forceFocus = false,
    taskContext = "standard"
  } = input;

  if (forceFocus) {
    return "Focus";
  }

  let state: ShellState = "Focus";
  for (const breakpoint of shellStateBreakpoints) {
    if (viewportWidth >= breakpoint.minWidth) {
      state = breakpoint.state;
      break;
    }
  }

  // Tight viewport heights reduce chrome priority before full focus takeover.
  if (viewportHeight < 860 && state === "Expanded") {
    state = "Balanced";
  }
  if (viewportHeight < 760 && state === "Balanced") {
    state = "Compact";
  }

  // Dense work regions prefer focus sooner on constrained widths.
  if (taskContext === "dense" && viewportWidth < 980 && state === "Compact") {
    state = "Focus";
  }

  return state;
}

export function resolveShellState(
  viewportWidth: number,
  forceFocus: boolean = false
): ShellState {
  return resolveAdaptiveShellState({
    viewportWidth,
    viewportHeight: Number.POSITIVE_INFINITY,
    forceFocus,
    taskContext: "standard"
  });
}

export const bootstrapSurfaces: BootstrapSurface[] = [
  { label: "Entry resolver", route: "/", scope: "public" },
  { label: "Login", route: "/login", scope: "public" },
  { label: "Auth callback", route: "/auth/callback", scope: "public" },
  { label: "Logout", route: "/logout", scope: "public" },
  { label: "Health", route: "/health", scope: "public" },
  { label: "Projects", route: "/projects", scope: "project" },
  {
    label: "Project overview",
    route: "/projects/:projectId/overview",
    scope: "project"
  },
  {
    label: "Project documents",
    route: "/projects/:projectId/documents",
    scope: "project"
  },
  {
    label: "Project documents import",
    route: "/projects/:projectId/documents/import",
    scope: "project"
  },
  {
    label: "Project document detail",
    route: "/projects/:projectId/documents/:documentId",
    scope: "project"
  },
  {
    label: "Project jobs",
    route: "/projects/:projectId/jobs",
    scope: "project"
  },
  {
    label: "Project job detail",
    route: "/projects/:projectId/jobs/:jobId",
    scope: "project"
  },
  {
    label: "Project activity",
    route: "/projects/:projectId/activity",
    scope: "project"
  },
  {
    label: "Project settings",
    route: "/projects/:projectId/settings",
    scope: "project"
  },
  {
    label: "Approved models",
    route: "/approved-models",
    scope: "project"
  },
  {
    label: "Project model assignments",
    route: "/projects/:projectId/model-assignments",
    scope: "project"
  },
  {
    label: "Project search",
    route: "/projects/:projectId/search",
    scope: "project"
  },
  {
    label: "Project entities",
    route: "/projects/:projectId/entities",
    scope: "project"
  },
  {
    label: "Project entity detail",
    route: "/projects/:projectId/entities/:entityId",
    scope: "project"
  },
  {
    label: "Project model assignment detail",
    route: "/projects/:projectId/model-assignments/:assignmentId",
    scope: "project"
  },
  {
    label: "Project model assignment datasets",
    route: "/projects/:projectId/model-assignments/:assignmentId/datasets",
    scope: "project"
  },
  {
    label: "Project policies",
    route: "/projects/:projectId/policies",
    scope: "project"
  },
  {
    label: "Project active policy",
    route: "/projects/:projectId/policies/active",
    scope: "project"
  },
  {
    label: "Project policy detail",
    route: "/projects/:projectId/policies/:policyId",
    scope: "project"
  },
  {
    label: "Project policy compare",
    route: "/projects/:projectId/policies/:policyId/compare",
    scope: "project"
  },
  {
    label: "Project indexes",
    route: "/projects/:projectId/indexes",
    scope: "project"
  },
  {
    label: "Project search index detail",
    route: "/projects/:projectId/indexes/search/:indexId",
    scope: "project"
  },
  {
    label: "Project entity index detail",
    route: "/projects/:projectId/indexes/entity/:indexId",
    scope: "project"
  },
  {
    label: "Project derivative index detail",
    route: "/projects/:projectId/indexes/derivative/:indexId",
    scope: "project"
  },
  {
    label: "Project pseudonym registry",
    route: "/projects/:projectId/pseudonym-registry",
    scope: "project"
  },
  {
    label: "Project pseudonym registry entry",
    route: "/projects/:projectId/pseudonym-registry/:entryId",
    scope: "project"
  },
  {
    label: "Project pseudonym registry events",
    route: "/projects/:projectId/pseudonym-registry/:entryId/events",
    scope: "project"
  },
  {
    label: "Export candidates",
    route: "/projects/:projectId/export-candidates",
    scope: "project"
  },
  {
    label: "Export candidate detail",
    route: "/projects/:projectId/export-candidates/:candidateId",
    scope: "project"
  },
  {
    label: "Export requests",
    route: "/projects/:projectId/export-requests",
    scope: "project"
  },
  {
    label: "New export request",
    route: "/projects/:projectId/export-requests/new",
    scope: "project"
  },
  {
    label: "Export request detail",
    route: "/projects/:projectId/export-requests/:exportRequestId",
    scope: "project"
  },
  {
    label: "Export request events",
    route: "/projects/:projectId/export-requests/:exportRequestId/events",
    scope: "project"
  },
  {
    label: "Export request reviews",
    route: "/projects/:projectId/export-requests/:exportRequestId/reviews",
    scope: "project"
  },
  {
    label: "Export request bundles",
    route: "/projects/:projectId/export-requests/:exportRequestId/bundles",
    scope: "project"
  },
  {
    label: "Export bundle detail",
    route: "/projects/:projectId/export-requests/:exportRequestId/bundles/:bundleId",
    scope: "project"
  },
  {
    label: "Export bundle events",
    route: "/projects/:projectId/export-requests/:exportRequestId/bundles/:bundleId/events",
    scope: "project"
  },
  {
    label: "Export bundle verification",
    route: "/projects/:projectId/export-requests/:exportRequestId/bundles/:bundleId/verification",
    scope: "project"
  },
  {
    label: "Export bundle validation",
    route: "/projects/:projectId/export-requests/:exportRequestId/bundles/:bundleId/validation",
    scope: "project"
  },
  {
    label: "Export review",
    route: "/projects/:projectId/export-review",
    scope: "project"
  },
  {
    label: "Viewer",
    route: "/projects/:projectId/documents/:documentId/viewer",
    scope: "project"
  },
  {
    label: "Preprocessing",
    route: "/projects/:projectId/documents/:documentId/preprocessing",
    scope: "project"
  },
  {
    label: "Preprocessing quality",
    route: "/projects/:projectId/documents/:documentId/preprocessing/quality",
    scope: "project"
  },
  {
    label: "Preprocessing run",
    route: "/projects/:projectId/documents/:documentId/preprocessing/runs/:runId",
    scope: "project"
  },
  {
    label: "Preprocessing compare",
    route: "/projects/:projectId/documents/:documentId/preprocessing/compare",
    scope: "project"
  },
  {
    label: "Layout",
    route: "/projects/:projectId/documents/:documentId/layout",
    scope: "project"
  },
  {
    label: "Layout run",
    route: "/projects/:projectId/documents/:documentId/layout/runs/:runId",
    scope: "project"
  },
  {
    label: "Layout workspace",
    route: "/projects/:projectId/documents/:documentId/layout/workspace",
    scope: "project"
  },
  {
    label: "Transcription",
    route: "/projects/:projectId/documents/:documentId/transcription",
    scope: "project"
  },
  {
    label: "Transcription run",
    route: "/projects/:projectId/documents/:documentId/transcription/runs/:runId",
    scope: "project"
  },
  {
    label: "Transcription workspace",
    route: "/projects/:projectId/documents/:documentId/transcription/workspace",
    scope: "project"
  },
  {
    label: "Transcription compare",
    route: "/projects/:projectId/documents/:documentId/transcription/compare",
    scope: "project"
  },
  {
    label: "Ingest status",
    route: "/projects/:projectId/documents/:documentId/ingest-status",
    scope: "project"
  },
  { label: "My activity", route: "/activity", scope: "project" },
  { label: "Operations", route: "/admin/operations", scope: "admin" },
  { label: "Operations SLOs", route: "/admin/operations/slos", scope: "admin" },
  {
    label: "Operations alerts",
    route: "/admin/operations/alerts",
    scope: "admin"
  },
  {
    label: "Operations timelines",
    route: "/admin/operations/timelines",
    scope: "admin"
  },
  { label: "Admin audit list", route: "/admin/audit", scope: "admin" },
  {
    label: "Admin audit detail",
    route: "/admin/audit/:eventId",
    scope: "admin"
  },
  { label: "Admin security", route: "/admin/security", scope: "admin" },
  { label: "Design system", route: "/admin/design-system", scope: "admin" }
];

export const bootstrapShellStates: ShellState[] = [
  "Expanded",
  "Balanced",
  "Compact",
  "Focus"
];
