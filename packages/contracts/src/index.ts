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
  | "TRANSCRIPTION_RUN_ACTIVATED"
  | "TRANSCRIPTION_WORKSPACE_VIEWED"
  | "TRANSCRIPT_LINE_CORRECTED"
  | "TRANSCRIPT_EDIT_CONFLICT_DETECTED"
  | "TRANSCRIPT_DOWNSTREAM_INVALIDATED"
  | "TRANSCRIPT_VARIANT_LAYER_VIEWED"
  | "TRANSCRIPT_ASSIST_DECISION_RECORDED"
  | "APPROVED_MODEL_LIST_VIEWED"
  | "APPROVED_MODEL_CREATED"
  | "PROJECT_MODEL_ASSIGNMENT_CREATED"
  | "MODEL_ASSIGNMENT_LIST_VIEWED"
  | "MODEL_ASSIGNMENT_DETAIL_VIEWED"
  | "TRAINING_DATASET_VIEWED"
  | "PROJECT_MODEL_ACTIVATED"
  | "PROJECT_MODEL_RETIRED"
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
export type TranscriptionProjectionBasis = "ENGINE_OUTPUT" | "REVIEW_CORRECTED";
export type TranscriptionFallbackReasonCode =
  | "SCHEMA_VALIDATION_FAILED"
  | "ANCHOR_RESOLUTION_FAILED"
  | "CONFIDENCE_BELOW_THRESHOLD";
export type TranscriptionCompareDecision = "KEEP_BASE" | "PROMOTE_CANDIDATE";
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
    label: "Export candidates",
    route: "/projects/:projectId/export-candidates",
    scope: "project"
  },
  {
    label: "Export requests",
    route: "/projects/:projectId/export-requests",
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
