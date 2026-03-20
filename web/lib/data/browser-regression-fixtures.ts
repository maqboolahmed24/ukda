import type {
  AuditEventListResponse,
  AuditIntegrityResponse,
  AuthProviderResponse,
  CreateDocumentUploadSessionRequest,
  DocumentGovernanceLedgerEntriesResponse,
  DocumentGovernanceLedgerResponse,
  DocumentGovernanceLedgerStatusResponse,
  DocumentGovernanceLedgerSummaryResponse,
  DocumentGovernanceLedgerVerifyDetailResponse,
  DocumentGovernanceLedgerVerifyRunsResponse,
  DocumentGovernanceLedgerVerifyStatusResponse,
  DocumentGovernanceManifestEntriesResponse,
  DocumentGovernanceManifestHashResponse,
  DocumentGovernanceManifestResponse,
  DocumentGovernanceManifestStatusResponse,
  DocumentGovernanceOverviewResponse,
  DocumentGovernanceRunEventsResponse,
  DocumentGovernanceRunOverviewResponse,
  DocumentGovernanceRunsResponse,
  DocumentLayoutActiveRunResponse,
  DocumentLayoutOverviewResponse,
  DocumentLayoutPageOverlay,
  DocumentLayoutPageResult,
  DocumentLayoutProjection,
  DocumentLayoutRun,
  DocumentLayoutRunListResponse,
  DocumentLayoutRunStatusResponse,
  DocumentRedactionFinding,
  DocumentRedactionCompareResponse,
  DocumentRedactionActiveRunResponse,
  DocumentRedactionFindingListResponse,
  DocumentRedactionOverviewResponse,
  DocumentRedactionPageReview,
  DocumentRedactionPreviewStatusResponse,
  DocumentRedactionProjection,
  DocumentRedactionRun,
  DocumentRedactionRunOutput,
  DocumentRedactionRunEventsResponse,
  DocumentRedactionRunListResponse,
  DocumentRedactionRunPage,
  DocumentRedactionRunPageListResponse,
  DocumentRedactionRunReview,
  DocumentRedactionRunStatusResponse,
  DocumentRedactionTimelineEvent,
  DocumentPageVariantsResponse,
  DocumentImportStatus,
  DocumentPreprocessActiveRunResponse,
  DocumentPreprocessCompareResponse,
  DocumentPreprocessOverviewResponse,
  DocumentPreprocessPageResult,
  DocumentPreprocessQualityResponse,
  DocumentPreprocessProjection,
  DocumentPreprocessRun,
  DocumentPreprocessRunListResponse,
  DocumentPreprocessRunPageListResponse,
  DocumentPreprocessRunStatusResponse,
  DocumentProcessingRunStatusResponse,
  DocumentTranscriptionLineResult,
  DocumentTranscriptionLineResultListResponse,
  DocumentTranscriptionOverviewResponse,
  DocumentTimelineResponse,
  DocumentUploadSessionStatus,
  ControlledEntity,
  EntityOccurrence,
  OperationsExportStatusResponse,
  OperationsOverviewResponse,
  ProjectDocument,
  ProjectDocumentUploadSessionStatus,
  ProjectDocumentPage,
  ProjectDocumentPageDetail,
  ProjectDocumentListResponse,
  ProjectJobListResponse,
  ProjectJobSummaryResponse,
  ProjectListResponse,
  ProjectRole,
  ProjectSearchHit,
  ProjectSearchResponse,
  ProjectSearchResultOpenResponse,
  ProjectDerivativeCandidateSnapshotCreateResponse,
  ProjectDerivativeDetailResponse,
  ProjectDerivativeListResponse,
  ProjectDerivativePreviewResponse,
  ProjectDerivativeSnapshot,
  ProjectDerivativeStatusResponse,
  ProjectEntityDetailResponse,
  ProjectEntityListResponse,
  ProjectEntityOccurrencesResponse,
  ProjectSummary,
  GovernanceLedgerEntry,
  GovernanceArtifactStatus,
  GovernanceLedgerVerificationRun,
  GovernanceManifestEntry,
  GovernanceReadinessProjection,
  GovernanceRunEvent,
  GovernanceRunSummary,
  SecurityStatusResponse,
  ServiceHealthPayload,
  ServiceReadinessPayload,
  SessionResponse
} from "@ukde/contracts";

import type { ApiResult } from "./api-types";
import { queryCachePolicy } from "./cache-policy";
import {
  computeGovernancePipelinePhase,
  computeIngestPipelinePhase,
  computeLayoutPipelinePhase,
  computeOverallPipelinePercent,
  computePreprocessPipelinePhase,
  computePrivacyPipelinePhase,
  computeTranscriptionPipelinePhase,
  createDegradedPipelinePhase,
  normalizePipelinePhaseOrder,
  resolvePipelineErrors,
  type DocumentPipelinePhaseId,
  type DocumentPipelineStatusResponse
} from "../pipeline-status";

const BROWSER_TEST_MODE_FLAG = "UKDE_BROWSER_TEST_MODE";
export type BrowserFixtureSessionProfile =
  | "admin"
  | "auditor"
  | "project-lead"
  | "reviewer"
  | "researcher";

const FIXTURE_SESSION_TOKENS: Record<BrowserFixtureSessionProfile, string> = {
  admin: "fixture-session-token",
  auditor: "fixture-session-token-auditor",
  "project-lead": "fixture-session-token-project-lead",
  reviewer: "fixture-session-token-reviewer",
  researcher: "fixture-session-token-researcher"
};
const FIXTURE_NOW = "2026-03-13T10:00:00.000Z";

const FIXTURE_SESSION: SessionResponse = {
  user: {
    id: "user-fixture-admin",
    sub: "fixture-admin-sub",
    email: "fixture.admin@ukde.test",
    displayName: "Fixture Admin",
    platformRoles: ["ADMIN"]
  },
  session: {
    id: "session-fixture-001",
    expiresAt: "2026-03-14T10:00:00.000Z"
  }
};

const FIXTURE_AUDITOR_SESSION: SessionResponse = {
  user: {
    id: "user-fixture-auditor",
    sub: "fixture-auditor-sub",
    email: "fixture.auditor@ukde.test",
    displayName: "Fixture Auditor",
    platformRoles: ["AUDITOR"]
  },
  session: {
    id: "session-fixture-002",
    expiresAt: "2026-03-14T10:00:00.000Z"
  }
};

const FIXTURE_PROJECT_LEAD_SESSION: SessionResponse = {
  user: {
    id: "user-fixture-project-lead",
    sub: "fixture-project-lead-sub",
    email: "fixture.projectlead@ukde.test",
    displayName: "Fixture Project Lead",
    platformRoles: []
  },
  session: {
    id: "session-fixture-003",
    expiresAt: "2026-03-14T10:00:00.000Z"
  }
};

const FIXTURE_REVIEWER_SESSION: SessionResponse = {
  user: {
    id: "user-fixture-reviewer",
    sub: "fixture-reviewer-sub",
    email: "fixture.reviewer@ukde.test",
    displayName: "Fixture Reviewer",
    platformRoles: []
  },
  session: {
    id: "session-fixture-004",
    expiresAt: "2026-03-14T10:00:00.000Z"
  }
};

const FIXTURE_RESEARCHER_SESSION: SessionResponse = {
  user: {
    id: "user-fixture-researcher",
    sub: "fixture-researcher-sub",
    email: "fixture.researcher@ukde.test",
    displayName: "Fixture Researcher",
    platformRoles: []
  },
  session: {
    id: "session-fixture-005",
    expiresAt: "2026-03-14T10:00:00.000Z"
  }
};

const FIXTURE_SESSION_BY_PROFILE: Record<BrowserFixtureSessionProfile, SessionResponse> = {
  admin: FIXTURE_SESSION,
  auditor: FIXTURE_AUDITOR_SESSION,
  "project-lead": FIXTURE_PROJECT_LEAD_SESSION,
  reviewer: FIXTURE_REVIEWER_SESSION,
  researcher: FIXTURE_RESEARCHER_SESSION
};

const FIXTURE_PROJECTS: ProjectSummary[] = [
  {
    id: "project-fixture-alpha",
    name: "Victorian Parish Registers",
    purpose: "Create governed transcript and audit baseline for parish scans.",
    status: "ACTIVE",
    createdBy: "user-fixture-admin",
    createdAt: "2026-03-10T08:30:00.000Z",
    intendedAccessTier: "CONTROLLED",
    baselinePolicySnapshotId: "policy-baseline-v1",
    currentUserRole: "PROJECT_LEAD",
    isMember: true,
    canAccessSettings: true,
    canManageMembers: true
  },
  {
    id: "project-fixture-beta",
    name: "Estate Correspondence",
    purpose: "Review document quality and queue controlled ingestion runs.",
    status: "ACTIVE",
    createdBy: "user-fixture-admin",
    createdAt: "2026-03-09T13:15:00.000Z",
    intendedAccessTier: "SAFEGUARDED",
    baselinePolicySnapshotId: "policy-baseline-v1",
    currentUserRole: "RESEARCHER",
    isMember: true,
    canAccessSettings: false,
    canManageMembers: false
  }
];

const FIXTURE_AUTH_PROVIDERS: AuthProviderResponse = {
  oidcEnabled: true,
  devEnabled: true,
  devSeeds: [
    {
      key: "fixture-admin",
      displayName: "Fixture Admin",
      email: "fixture.admin@ukde.test",
      platformRoles: ["ADMIN"]
    },
    {
      key: "fixture-auditor",
      displayName: "Fixture Auditor",
      email: "fixture.auditor@ukde.test",
      platformRoles: ["AUDITOR"]
    }
  ]
};

const FIXTURE_HEALTH: ServiceHealthPayload = {
  service: "api",
  status: "OK",
  environment: "test",
  version: "fixture",
  timestamp: FIXTURE_NOW
};

const FIXTURE_READINESS: ServiceReadinessPayload = {
  service: "api",
  status: "READY",
  environment: "test",
  version: "fixture",
  timestamp: FIXTURE_NOW,
  checks: [
    {
      name: "db",
      status: "OK",
      detail: "Fixture database check passed."
    }
  ]
};

const FIXTURE_AUDIT_INTEGRITY: AuditIntegrityResponse = {
  checkedRows: 128,
  chainHead: "fixture-chain-head",
  isValid: true,
  firstInvalidChainIndex: null,
  firstInvalidEventId: null,
  detail: "Fixture integrity chain is valid."
};

const FIXTURE_SECURITY_STATUS: SecurityStatusResponse = {
  generatedAt: FIXTURE_NOW,
  environment: "test",
  denyByDefaultEgress: true,
  outboundAllowlist: [],
  lastSuccessfulEgressDenyTestAt: "2026-03-12T18:00:00.000Z",
  egressTestDetail: "Fixture deny test confirms no direct egress route.",
  cspMode: "enforce",
  lastBackupAt: "2026-03-12T01:00:00.000Z",
  reducedMotionPreferenceState: "supported",
  reducedTransparencyPreferenceState: "supported",
  exportGatewayState: "ENFORCED_GATEWAY_ONLY"
};

const FIXTURE_OPERATIONS_OVERVIEW: OperationsOverviewResponse = {
  generatedAt: FIXTURE_NOW,
  uptimeSeconds: 86_400,
  requestCount: 9_120,
  requestErrorCount: 27,
  errorRatePercent: 0.296,
  p95LatencyMs: 188.22,
  jobsPerMinute: 14.25,
  jobsCompletedCount: 20_512,
  queueLatencyAvgMs: 1_250.4,
  queueLatencyP95Ms: 4_884.75,
  gpuUtilizationAvgPercent: 42.3,
  gpuUtilizationMaxPercent: 78.1,
  gpuUtilizationSampleCount: 144,
  gpuUtilizationSource: "fixture-worker-gpu",
  gpuUtilizationDetail: "Fixture GPU sampler attached to worker runtime.",
  modelRequestCount: 3_482,
  modelErrorCount: 41,
  modelErrorRatePercent: 1.177,
  modelFallbackInvocationCount: 134,
  modelFallbackInvocationRatePercent: 3.848,
  modelRequestP95LatencyMs: 842.31,
  exportReviewLatencyAvgMs: 128_300.23,
  exportReviewLatencyP95Ms: 356_889.5,
  exportReviewLatencySampleCount: 83,
  storageRequestCount: 18_462,
  storageErrorCount: 21,
  storageErrorRatePercent: 0.114,
  readinessDbChecks: 48,
  readinessDbFailures: 0,
  readinessDbLastLatencyMs: 7.8,
  readinessDbAvgLatencyMs: 6.4,
  authSuccessCount: 215,
  authFailureCount: 4,
  auditWriteSuccessCount: 640,
  auditWriteFailureCount: 0,
  traceContextEnabled: true,
  queueDepth: 3,
  queueDepthSource: "fixture",
  queueDepthDetail: "Fixture queue depth is stable for browser regression.",
  exporter: {
    mode: "otlp-http",
    endpoint: "http://collector.internal:4318",
    state: "healthy",
    detail: "Fixture telemetry exporter is active."
  },
  storage: [
    {
      operation: "READ",
      requestCount: 11_050,
      errorCount: 9,
      averageLatencyMs: 38.61,
      p95LatencyMs: 72.1
    },
    {
      operation: "WRITE",
      requestCount: 7_412,
      errorCount: 12,
      averageLatencyMs: 54.2,
      p95LatencyMs: 109.32
    }
  ],
  modelDeployments: [
    {
      deploymentUnit: "transcription-primary-a10g",
      requestCount: 2_710,
      errorCount: 19,
      errorRatePercent: 0.701,
      fallbackInvocationCount: 74,
      fallbackInvocationRatePercent: 2.73,
      averageLatencyMs: 412.9,
      p95LatencyMs: 840.2,
      coldStartP95Ms: 1_540.25,
      warmStartP95Ms: 799.61
    },
    {
      deploymentUnit: "governed-fallback",
      requestCount: 772,
      errorCount: 22,
      errorRatePercent: 2.85,
      fallbackInvocationCount: 60,
      fallbackInvocationRatePercent: 7.772,
      averageLatencyMs: 523.2,
      p95LatencyMs: 1_102.4,
      coldStartP95Ms: 1_860.41,
      warmStartP95Ms: 1_035.09
    }
  ],
  models: [
    {
      modelKey: "vlm-primary-2026.03",
      deploymentUnit: "transcription-primary-a10g",
      requestCount: 2_710,
      errorCount: 19,
      errorRatePercent: 0.701,
      fallbackInvocationCount: 74,
      fallbackInvocationRatePercent: 2.73,
      averageLatencyMs: 412.9,
      p95LatencyMs: 840.2
    },
    {
      modelKey: "KRAKEN_LINE",
      deploymentUnit: "governed-fallback",
      requestCount: 772,
      errorCount: 22,
      errorRatePercent: 2.85,
      fallbackInvocationCount: 60,
      fallbackInvocationRatePercent: 7.772,
      averageLatencyMs: 523.2,
      p95LatencyMs: 1_102.4
    }
  ],
  topRoutes: [
    {
      routeTemplate: "/projects/{projectId}/overview",
      method: "GET",
      requestCount: 320,
      errorCount: 0,
      averageLatencyMs: 45.12,
      p95LatencyMs: 108.44
    },
    {
      routeTemplate: "/admin/design-system",
      method: "GET",
      requestCount: 88,
      errorCount: 0,
      averageLatencyMs: 51.33,
      p95LatencyMs: 120.76
    }
  ]
};

const FIXTURE_OPERATIONS_EXPORT_STATUS: OperationsExportStatusResponse = {
  generatedAt: FIXTURE_NOW,
  openRequestCount: 7,
  aging: {
    unstarted: 2,
    noSla: 0,
    onTrack: 3,
    dueSoon: 1,
    overdue: 1,
    staleOpen: 1
  },
  reminders: {
    due: 2,
    sentLast24h: 4,
    total: 18
  },
  escalations: {
    due: 1,
    openEscalated: 2,
    total: 9
  },
  retention: {
    pendingCount: 5,
    pendingWindowDays: 14
  },
  terminal: {
    approved: 11,
    exported: 26,
    rejected: 4,
    returned: 6
  },
  policy: {
    slaHours: 72,
    reminderAfterHours: 24,
    reminderCooldownHours: 12,
    escalationAfterSlaHours: 24,
    escalationCooldownHours: 24,
    staleOpenAfterDays: 30,
    retentionStaleOpenDays: 60,
    retentionTerminalApprovedDays: 180,
    retentionTerminalOtherDays: 90
  }
};

const FIXTURE_ACTIVITY: AuditEventListResponse = {
  items: [
    {
      id: "audit-fixture-001",
      chainIndex: 1,
      timestamp: "2026-03-13T09:55:00.000Z",
      actorUserId: "user-fixture-admin",
      projectId: "project-fixture-alpha",
      eventType: "MY_ACTIVITY_VIEWED",
      objectType: "route",
      objectId: "/activity",
      ip: "127.0.0.1",
      userAgent: "playwright",
      requestId: "req-fixture-001",
      metadataJson: {},
      prevHash: "0",
      rowHash: "hash-fixture-001"
    }
  ],
  nextCursor: null
};

const FIXTURE_PROJECT_JOBS: ProjectJobListResponse = {
  items: [
    {
      id: "job-fixture-001",
      projectId: "project-fixture-alpha",
      attemptNumber: 1,
      supersedesJobId: null,
      supersededByJobId: null,
      type: "NOOP",
      dedupeKey: "noop-fixture-001",
      status: "RUNNING",
      attempts: 1,
      maxAttempts: 1,
      payloadJson: {
        logical_key: "noop-fixture-001",
        mode: "SUCCESS"
      },
      createdBy: "user-fixture-admin",
      createdAt: "2026-03-13T09:58:00.000Z",
      startedAt: "2026-03-13T09:58:03.000Z",
      finishedAt: null,
      canceledBy: null,
      canceledAt: null,
      errorCode: null,
      errorMessage: null,
      cancelRequested: false,
      cancelRequestedBy: null,
      cancelRequestedAt: null
    }
  ],
  nextCursor: null
};

const FIXTURE_PROJECT_JOBS_SUMMARY: ProjectJobSummaryResponse = {
  runningJobs: 1,
  lastJobStatus: "RUNNING"
};

const FIXTURE_DOCUMENTS_BY_PROJECT: Record<string, ProjectDocument[]> = {
  "project-fixture-alpha": [
    {
      id: "doc-fixture-001",
      projectId: "project-fixture-alpha",
      originalFilename: "diary-1871-scan.pdf",
      storedFilename: null,
      contentTypeDetected: "application/pdf",
      bytes: null,
      sha256: null,
      pageCount: null,
      status: "SCANNING",
      createdBy: "user-fixture-admin",
      createdAt: "2026-03-13T09:40:00.000Z",
      updatedAt: "2026-03-13T09:42:00.000Z"
    },
    {
      id: "doc-fixture-002",
      projectId: "project-fixture-alpha",
      originalFilename: "register-volume-04.pdf",
      storedFilename: "c4/register-volume-04.pdf",
      contentTypeDetected: "application/pdf",
      bytes: 1_240_000,
      sha256:
        "0f4a2ea4a4f70eb7e59717dd41db1b23a34175d63f767f95f1171bf11ec53087",
      pageCount: 2,
      status: "READY",
      createdBy: "user-fixture-admin",
      createdAt: "2026-03-11T12:15:00.000Z",
      updatedAt: "2026-03-12T08:05:00.000Z"
    },
    {
      id: "doc-fixture-003",
      projectId: "project-fixture-alpha",
      originalFilename: "water-damaged-parish-notes.pdf",
      storedFilename: "c4/water-damaged-parish-notes.pdf",
      contentTypeDetected: "application/pdf",
      bytes: 882_144,
      sha256:
        "4e3e7d2843d4ee4becd66f7214fa994aacd403d1700514b6a2f2a0513868c4ab",
      pageCount: 1,
      status: "FAILED",
      createdBy: "user-fixture-admin",
      createdAt: "2026-03-10T11:08:00.000Z",
      updatedAt: "2026-03-10T11:12:00.000Z"
    }
  ],
  "project-fixture-beta": []
};

const FIXTURE_DOCUMENT_TIMELINES: Record<
  string,
  DocumentTimelineResponse["items"]
> = {
  "doc-fixture-001": [
    {
      id: "run-fixture-001",
      attemptNumber: 1,
      runKind: "SCAN",
      supersedesProcessingRunId: null,
      supersededByProcessingRunId: null,
      status: "RUNNING",
      failureReason: null,
      createdBy: "user-fixture-admin",
      startedAt: "2026-03-13T09:42:00.000Z",
      finishedAt: null,
      canceledBy: null,
      canceledAt: null,
      createdAt: "2026-03-13T09:40:00.000Z"
    },
    {
      id: "run-fixture-000",
      attemptNumber: 1,
      runKind: "UPLOAD",
      supersedesProcessingRunId: null,
      supersededByProcessingRunId: null,
      status: "SUCCEEDED",
      failureReason: null,
      createdBy: "user-fixture-admin",
      startedAt: "2026-03-13T09:40:00.000Z",
      finishedAt: "2026-03-13T09:40:15.000Z",
      canceledBy: null,
      canceledAt: null,
      createdAt: "2026-03-13T09:40:00.000Z"
    }
  ],
  "doc-fixture-002": [
    {
      id: "run-fixture-005",
      attemptNumber: 1,
      runKind: "THUMBNAIL_RENDER",
      supersedesProcessingRunId: null,
      supersededByProcessingRunId: null,
      status: "SUCCEEDED",
      failureReason: null,
      createdBy: "user-fixture-admin",
      startedAt: "2026-03-11T12:26:00.000Z",
      finishedAt: "2026-03-11T12:27:00.000Z",
      canceledBy: null,
      canceledAt: null,
      createdAt: "2026-03-11T12:26:00.000Z"
    },
    {
      id: "run-fixture-004",
      attemptNumber: 1,
      runKind: "EXTRACTION",
      supersedesProcessingRunId: null,
      supersededByProcessingRunId: null,
      status: "SUCCEEDED",
      failureReason: null,
      createdBy: "user-fixture-admin",
      startedAt: "2026-03-11T12:23:00.000Z",
      finishedAt: "2026-03-11T12:25:00.000Z",
      canceledBy: null,
      canceledAt: null,
      createdAt: "2026-03-11T12:23:00.000Z"
    },
    {
      id: "run-fixture-003",
      attemptNumber: 1,
      runKind: "SCAN",
      supersedesProcessingRunId: null,
      supersededByProcessingRunId: null,
      status: "SUCCEEDED",
      failureReason: null,
      createdBy: "user-fixture-admin",
      startedAt: "2026-03-11T12:20:00.000Z",
      finishedAt: "2026-03-11T12:22:00.000Z",
      canceledBy: null,
      canceledAt: null,
      createdAt: "2026-03-11T12:20:00.000Z"
    },
    {
      id: "run-fixture-002",
      attemptNumber: 1,
      runKind: "UPLOAD",
      supersedesProcessingRunId: null,
      supersededByProcessingRunId: null,
      status: "SUCCEEDED",
      failureReason: null,
      createdBy: "user-fixture-admin",
      startedAt: "2026-03-11T12:15:00.000Z",
      finishedAt: "2026-03-11T12:16:00.000Z",
      canceledBy: null,
      canceledAt: null,
      createdAt: "2026-03-11T12:15:00.000Z"
    }
  ],
  "doc-fixture-003": [
    {
      id: "run-fixture-103",
      attemptNumber: 1,
      runKind: "EXTRACTION",
      supersedesProcessingRunId: null,
      supersededByProcessingRunId: null,
      status: "FAILED",
      failureReason: "Fixture extraction failed for retry flow.",
      createdBy: "user-fixture-admin",
      startedAt: "2026-03-10T11:09:00.000Z",
      finishedAt: "2026-03-10T11:10:00.000Z",
      canceledBy: null,
      canceledAt: null,
      createdAt: "2026-03-10T11:09:00.000Z"
    },
    {
      id: "run-fixture-102",
      attemptNumber: 1,
      runKind: "SCAN",
      supersedesProcessingRunId: null,
      supersededByProcessingRunId: null,
      status: "SUCCEEDED",
      failureReason: null,
      createdBy: "user-fixture-admin",
      startedAt: "2026-03-10T11:08:10.000Z",
      finishedAt: "2026-03-10T11:08:50.000Z",
      canceledBy: null,
      canceledAt: null,
      createdAt: "2026-03-10T11:08:10.000Z"
    },
    {
      id: "run-fixture-101",
      attemptNumber: 1,
      runKind: "UPLOAD",
      supersedesProcessingRunId: null,
      supersededByProcessingRunId: null,
      status: "SUCCEEDED",
      failureReason: null,
      createdBy: "user-fixture-admin",
      startedAt: "2026-03-10T11:08:00.000Z",
      finishedAt: "2026-03-10T11:08:08.000Z",
      canceledBy: null,
      canceledAt: null,
      createdAt: "2026-03-10T11:08:00.000Z"
    }
  ]
};

interface FixtureUploadSessionState {
  sessionId: string;
  importId: string;
  documentId: string;
  projectId: string;
  originalFilename: string;
  uploadStatus: DocumentUploadSessionStatus;
  importStatus: DocumentImportStatus;
  documentStatus: ProjectDocument["status"];
  bytesReceived: number;
  expectedTotalBytes: number | null;
  expectedSha256: string | null;
  lastChunkIndex: number;
  chunkSizeLimitBytes: number;
  uploadLimitBytes: number;
  cancelAllowed: boolean;
  failureReason: string | null;
  createdAt: string;
  updatedAt: string;
  chunks: Map<number, number>;
  interruptChunkIndex: number | null;
}

const FIXTURE_UPLOAD_SESSIONS = new Map<string, FixtureUploadSessionState>();
let fixtureUploadSessionSequence = 0;

const FIXTURE_DOCUMENT_PAGES: Record<string, ProjectDocumentPageDetail[]> = {
  "doc-fixture-001": [],
  "doc-fixture-002": [
    {
      id: "page-fixture-001",
      documentId: "doc-fixture-002",
      pageIndex: 0,
      width: 1200,
      height: 1800,
      dpi: 300,
      sourceWidth: 1200,
      sourceHeight: 1800,
      sourceDpi: 300,
      sourceColorMode: "GRAY",
      status: "READY",
      failureReason: null,
      viewerRotation: 0,
      createdAt: "2026-03-11T12:23:00.000Z",
      updatedAt: "2026-03-11T12:27:00.000Z",
      derivedImageAvailable: true,
      thumbnailAvailable: true
    },
    {
      id: "page-fixture-002",
      documentId: "doc-fixture-002",
      pageIndex: 1,
      width: 1200,
      height: 1800,
      dpi: 300,
      sourceWidth: 1200,
      sourceHeight: 1800,
      sourceDpi: 300,
      sourceColorMode: "GRAY",
      status: "READY",
      failureReason: null,
      viewerRotation: 0,
      createdAt: "2026-03-11T12:23:00.000Z",
      updatedAt: "2026-03-11T12:27:00.000Z",
      derivedImageAvailable: true,
      thumbnailAvailable: true
    }
  ]
};

const FIXTURE_PREPROCESS_RUNS_BY_DOCUMENT: Record<string, DocumentPreprocessRun[]> = {
  "doc-fixture-002": [
    {
      id: "pre-run-fixture-002",
      projectId: "project-fixture-alpha",
      documentId: "doc-fixture-002",
      parentRunId: "pre-run-fixture-001",
      attemptNumber: 2,
      runScope: "FULL_DOCUMENT",
      targetPageIdsJson: null,
      composedFromRunIdsJson: null,
      supersededByRunId: null,
      profileId: "BALANCED",
      profileVersion: "1.0.0",
      profileRevision: 2,
      profileLabel: "Balanced",
      profileDescription: "Fixture balanced profile for preprocessing review.",
      profileParamsHash: "fixture-profile-hash-002",
      profileIsAdvanced: false,
      profileIsGated: false,
      paramsJson: {
        deskew: true,
        denoise: "mild"
      },
      paramsHash: "fixture-params-hash-002",
      pipelineVersion: "preprocess-v1",
      containerDigest: "ukde/preprocess:v1",
      manifestObjectKey: "controlled/derived/project-fixture-alpha/doc-fixture-002/preprocess/pre-run-fixture-002/manifest.json",
      manifestSha256: "fixture-manifest-002",
      manifestSchemaVersion: 1,
      status: "SUCCEEDED",
      createdBy: "user-fixture-admin",
      createdAt: "2026-03-12T08:00:00.000Z",
      startedAt: "2026-03-12T08:00:10.000Z",
      finishedAt: "2026-03-12T08:01:10.000Z",
      failureReason: null,
      isActiveProjection: true,
      isSuperseded: false,
      isCurrentAttempt: true,
      isHistoricalAttempt: false,
      downstreamImpact: {
        resolvedAgainstRunId: "pre-run-fixture-002",
        layoutBasisState: "CURRENT",
        layoutBasisRunId: "pre-run-fixture-002",
        transcriptionBasisState: "NOT_STARTED",
        transcriptionBasisRunId: null
      }
    },
    {
      id: "pre-run-fixture-001",
      projectId: "project-fixture-alpha",
      documentId: "doc-fixture-002",
      parentRunId: null,
      attemptNumber: 1,
      runScope: "FULL_DOCUMENT",
      targetPageIdsJson: null,
      composedFromRunIdsJson: null,
      supersededByRunId: "pre-run-fixture-002",
      profileId: "BALANCED",
      profileVersion: "1.0.0",
      profileRevision: 1,
      profileLabel: "Balanced",
      profileDescription: "Fixture baseline run for compare diagnostics.",
      profileParamsHash: "fixture-profile-hash-001",
      profileIsAdvanced: false,
      profileIsGated: false,
      paramsJson: {
        deskew: false,
        denoise: "off"
      },
      paramsHash: "fixture-params-hash-001",
      pipelineVersion: "preprocess-v1",
      containerDigest: "ukde/preprocess:v1",
      manifestObjectKey: "controlled/derived/project-fixture-alpha/doc-fixture-002/preprocess/pre-run-fixture-001/manifest.json",
      manifestSha256: "fixture-manifest-001",
      manifestSchemaVersion: 1,
      status: "SUCCEEDED",
      createdBy: "user-fixture-admin",
      createdAt: "2026-03-12T07:30:00.000Z",
      startedAt: "2026-03-12T07:30:10.000Z",
      finishedAt: "2026-03-12T07:31:00.000Z",
      failureReason: null,
      isActiveProjection: false,
      isSuperseded: true,
      isCurrentAttempt: false,
      isHistoricalAttempt: true,
      downstreamImpact: {
        resolvedAgainstRunId: "pre-run-fixture-001",
        layoutBasisState: "STALE",
        layoutBasisRunId: "pre-run-fixture-002",
        transcriptionBasisState: "NOT_STARTED",
        transcriptionBasisRunId: null
      }
    }
  ]
};

const FIXTURE_PREPROCESS_PAGE_RESULTS_BY_RUN: Record<
  string,
  DocumentPreprocessPageResult[]
> = {
  "pre-run-fixture-001": [
    {
      runId: "pre-run-fixture-001",
      pageId: "page-fixture-001",
      pageIndex: 0,
      status: "SUCCEEDED",
      qualityGateStatus: "PASS",
      inputObjectKey: "controlled/derived/project-fixture-alpha/doc-fixture-002/pages/0.png",
      inputSha256: "fixture-page-sha-001",
      sourceResultRunId: null,
      outputObjectKeyGray: "controlled/derived/project-fixture-alpha/doc-fixture-002/preprocess/pre-run-fixture-001/gray/0.png",
      outputObjectKeyBin: null,
      metricsObjectKey: "controlled/derived/project-fixture-alpha/doc-fixture-002/preprocess/pre-run-fixture-001/metrics/0.json",
      metricsSha256: "fixture-metrics-sha-001",
      metricsJson: {
        blurScore: 0.18,
        skewDeg: 0.3,
        dpiEstimate: 300
      },
      sha256Gray: "fixture-gray-sha-001",
      sha256Bin: null,
      warningsJson: [],
      failureReason: null,
      createdAt: "2026-03-12T07:31:05.000Z",
      updatedAt: "2026-03-12T07:31:05.000Z"
    },
    {
      runId: "pre-run-fixture-001",
      pageId: "page-fixture-002",
      pageIndex: 1,
      status: "SUCCEEDED",
      qualityGateStatus: "REVIEW_REQUIRED",
      inputObjectKey: "controlled/derived/project-fixture-alpha/doc-fixture-002/pages/1.png",
      inputSha256: "fixture-page-sha-002",
      sourceResultRunId: null,
      outputObjectKeyGray: "controlled/derived/project-fixture-alpha/doc-fixture-002/preprocess/pre-run-fixture-001/gray/1.png",
      outputObjectKeyBin: null,
      metricsObjectKey: "controlled/derived/project-fixture-alpha/doc-fixture-002/preprocess/pre-run-fixture-001/metrics/1.json",
      metricsSha256: "fixture-metrics-sha-002",
      metricsJson: {
        blurScore: 0.34,
        skewDeg: 1.2,
        dpiEstimate: 185
      },
      sha256Gray: "fixture-gray-sha-002",
      sha256Bin: null,
      warningsJson: ["LOW_DPI", "BLUR_HIGH"],
      failureReason: null,
      createdAt: "2026-03-12T07:31:08.000Z",
      updatedAt: "2026-03-12T07:31:08.000Z"
    }
  ],
  "pre-run-fixture-002": [
    {
      runId: "pre-run-fixture-002",
      pageId: "page-fixture-001",
      pageIndex: 0,
      status: "SUCCEEDED",
      qualityGateStatus: "PASS",
      inputObjectKey: "controlled/derived/project-fixture-alpha/doc-fixture-002/pages/0.png",
      inputSha256: "fixture-page-sha-001",
      sourceResultRunId: null,
      outputObjectKeyGray: "controlled/derived/project-fixture-alpha/doc-fixture-002/preprocess/pre-run-fixture-002/gray/0.png",
      outputObjectKeyBin: "controlled/derived/project-fixture-alpha/doc-fixture-002/preprocess/pre-run-fixture-002/bin/0.png",
      metricsObjectKey: "controlled/derived/project-fixture-alpha/doc-fixture-002/preprocess/pre-run-fixture-002/metrics/0.json",
      metricsSha256: "fixture-metrics-sha-003",
      metricsJson: {
        blurScore: 0.11,
        skewDeg: 0.1,
        dpiEstimate: 300
      },
      sha256Gray: "fixture-gray-sha-003",
      sha256Bin: "fixture-bin-sha-003",
      warningsJson: [],
      failureReason: null,
      createdAt: "2026-03-12T08:01:15.000Z",
      updatedAt: "2026-03-12T08:01:15.000Z"
    },
    {
      runId: "pre-run-fixture-002",
      pageId: "page-fixture-002",
      pageIndex: 1,
      status: "SUCCEEDED",
      qualityGateStatus: "PASS",
      inputObjectKey: "controlled/derived/project-fixture-alpha/doc-fixture-002/pages/1.png",
      inputSha256: "fixture-page-sha-002",
      sourceResultRunId: null,
      outputObjectKeyGray: "controlled/derived/project-fixture-alpha/doc-fixture-002/preprocess/pre-run-fixture-002/gray/1.png",
      outputObjectKeyBin: null,
      metricsObjectKey: "controlled/derived/project-fixture-alpha/doc-fixture-002/preprocess/pre-run-fixture-002/metrics/1.json",
      metricsSha256: "fixture-metrics-sha-004",
      metricsJson: {
        blurScore: 0.22,
        skewDeg: 0.4,
        dpiEstimate: 240
      },
      sha256Gray: "fixture-gray-sha-004",
      sha256Bin: null,
      warningsJson: ["LOW_DPI"],
      failureReason: null,
      createdAt: "2026-03-12T08:01:18.000Z",
      updatedAt: "2026-03-12T08:01:18.000Z"
    }
  ]
};

const FIXTURE_PREPROCESS_PROJECTION_BY_DOCUMENT: Record<
  string,
  DocumentPreprocessProjection
> = {
  "doc-fixture-002": {
    documentId: "doc-fixture-002",
    projectId: "project-fixture-alpha",
    activePreprocessRunId: "pre-run-fixture-002",
    activeProfileId: "BALANCED",
    activeProfileVersion: "1.0.0",
    activeProfileRevision: 2,
    activeParamsHash: "fixture-params-hash-002",
    activePipelineVersion: "preprocess-v1",
    activeContainerDigest: "ukde/preprocess:v1",
    selectionMode: "EXPLICIT_ACTIVATION",
    downstreamDefaultConsumer: "LAYOUT_ANALYSIS_PHASE_3",
    downstreamDefaultRunId: "pre-run-fixture-002",
    downstreamImpact: {
      resolvedAgainstRunId: "pre-run-fixture-002",
      layoutBasisState: "CURRENT",
      layoutBasisRunId: "pre-run-fixture-002",
      transcriptionBasisState: "NOT_STARTED",
      transcriptionBasisRunId: null
    },
    updatedAt: "2026-03-12T08:02:00.000Z"
  }
};

const FIXTURE_LAYOUT_RUNS_BY_DOCUMENT: Record<string, DocumentLayoutRun[]> = {
  "doc-fixture-002": [
    {
      id: "layout-run-fixture-002",
      projectId: "project-fixture-alpha",
      documentId: "doc-fixture-002",
      inputPreprocessRunId: "pre-run-fixture-002",
      runKind: "AUTO",
      parentRunId: "layout-run-fixture-001",
      attemptNumber: 2,
      supersededByRunId: null,
      modelId: "layout-rule-v1",
      profileId: "DEFAULT",
      paramsJson: {
        threshold_offset: 0
      },
      paramsHash: "layout-params-hash-002",
      pipelineVersion: "layout-v1",
      containerDigest: "ukde/layout:v1",
      status: "SUCCEEDED",
      createdBy: "user-fixture-admin",
      createdAt: "2026-03-12T08:20:00.000Z",
      startedAt: "2026-03-12T08:20:10.000Z",
      finishedAt: "2026-03-12T08:21:05.000Z",
      failureReason: null,
      isActiveProjection: true,
      isSuperseded: false,
      isCurrentAttempt: true,
      isHistoricalAttempt: false
    },
    {
      id: "layout-run-fixture-001",
      projectId: "project-fixture-alpha",
      documentId: "doc-fixture-002",
      inputPreprocessRunId: "pre-run-fixture-001",
      runKind: "AUTO",
      parentRunId: null,
      attemptNumber: 1,
      supersededByRunId: "layout-run-fixture-002",
      modelId: "layout-rule-v1",
      profileId: "DEFAULT",
      paramsJson: {
        threshold_offset: -4
      },
      paramsHash: "layout-params-hash-001",
      pipelineVersion: "layout-v1",
      containerDigest: "ukde/layout:v1",
      status: "SUCCEEDED",
      createdBy: "user-fixture-admin",
      createdAt: "2026-03-12T08:10:00.000Z",
      startedAt: "2026-03-12T08:10:08.000Z",
      finishedAt: "2026-03-12T08:11:00.000Z",
      failureReason: null,
      isActiveProjection: false,
      isSuperseded: true,
      isCurrentAttempt: false,
      isHistoricalAttempt: true
    }
  ]
};

const FIXTURE_LAYOUT_PAGE_RESULTS_BY_RUN: Record<string, DocumentLayoutPageResult[]> = {
  "layout-run-fixture-001": [
    {
      runId: "layout-run-fixture-001",
      pageId: "page-fixture-001",
      pageIndex: 0,
      status: "SUCCEEDED",
      pageRecallStatus: "NEEDS_MANUAL_REVIEW",
      activeLayoutVersionId: null,
      pageXmlKey:
        "controlled/derived/project-fixture-alpha/doc-fixture-002/layout/layout-run-fixture-001/page/0.xml",
      overlayJsonKey:
        "controlled/derived/project-fixture-alpha/doc-fixture-002/layout/layout-run-fixture-001/page/0.json",
      pageXmlSha256: "layout-pagexml-sha-001",
      overlayJsonSha256: "layout-overlay-sha-001",
      metricsJson: {
        num_regions: 2,
        num_lines: 5,
        region_coverage_percent: 24.82,
        line_coverage_percent: 12.44,
        column_count: 2
      },
      warningsJson: ["COMPLEX_LAYOUT"],
      failureReason: null,
      createdAt: "2026-03-12T08:10:40.000Z",
      updatedAt: "2026-03-12T08:10:42.000Z"
    },
    {
      runId: "layout-run-fixture-001",
      pageId: "page-fixture-002",
      pageIndex: 1,
      status: "SUCCEEDED",
      pageRecallStatus: "NEEDS_RESCUE",
      activeLayoutVersionId: null,
      pageXmlKey:
        "controlled/derived/project-fixture-alpha/doc-fixture-002/layout/layout-run-fixture-001/page/1.xml",
      overlayJsonKey:
        "controlled/derived/project-fixture-alpha/doc-fixture-002/layout/layout-run-fixture-001/page/1.json",
      pageXmlSha256: "layout-pagexml-sha-002",
      overlayJsonSha256: "layout-overlay-sha-002",
      metricsJson: {
        num_regions: 1,
        num_lines: 2,
        region_coverage_percent: 14.14,
        line_coverage_percent: 4.1,
        column_count: 1
      },
      warningsJson: ["LOW_LINES"],
      failureReason: null,
      createdAt: "2026-03-12T08:10:45.000Z",
      updatedAt: "2026-03-12T08:10:46.000Z"
    }
  ],
  "layout-run-fixture-002": [
    {
      runId: "layout-run-fixture-002",
      pageId: "page-fixture-001",
      pageIndex: 0,
      status: "SUCCEEDED",
      pageRecallStatus: "COMPLETE",
      activeLayoutVersionId: null,
      pageXmlKey:
        "controlled/derived/project-fixture-alpha/doc-fixture-002/layout/layout-run-fixture-002/page/0.xml",
      overlayJsonKey:
        "controlled/derived/project-fixture-alpha/doc-fixture-002/layout/layout-run-fixture-002/page/0.json",
      pageXmlSha256: "layout-pagexml-sha-003",
      overlayJsonSha256: "layout-overlay-sha-003",
      metricsJson: {
        num_regions: 2,
        num_lines: 6,
        region_coverage_percent: 27.45,
        line_coverage_percent: 13.4,
        column_count: 2
      },
      warningsJson: [],
      failureReason: null,
      createdAt: "2026-03-12T08:20:44.000Z",
      updatedAt: "2026-03-12T08:20:46.000Z"
    },
    {
      runId: "layout-run-fixture-002",
      pageId: "page-fixture-002",
      pageIndex: 1,
      status: "SUCCEEDED",
      pageRecallStatus: "NEEDS_MANUAL_REVIEW",
      activeLayoutVersionId: null,
      pageXmlKey:
        "controlled/derived/project-fixture-alpha/doc-fixture-002/layout/layout-run-fixture-002/page/1.xml",
      overlayJsonKey:
        "controlled/derived/project-fixture-alpha/doc-fixture-002/layout/layout-run-fixture-002/page/1.json",
      pageXmlSha256: "layout-pagexml-sha-004",
      overlayJsonSha256: "layout-overlay-sha-004",
      metricsJson: {
        num_regions: 1,
        num_lines: 3,
        region_coverage_percent: 18.76,
        line_coverage_percent: 8.22,
        column_count: 1
      },
      warningsJson: ["COMPLEX_LAYOUT", "LOW_LINES"],
      failureReason: null,
      createdAt: "2026-03-12T08:20:48.000Z",
      updatedAt: "2026-03-12T08:20:50.000Z"
    }
  ]
};

const FIXTURE_LAYOUT_OVERLAYS_BY_RUN_PAGE: Record<string, DocumentLayoutPageOverlay> = {
  "layout-run-fixture-001:page-fixture-001": {
    schemaVersion: 1,
    runId: "layout-run-fixture-001",
    pageId: "page-fixture-001",
    pageIndex: 0,
    page: { width: 1200, height: 1800 },
    elements: [
      {
        id: "r-0001-0001",
        type: "REGION",
        parentId: null,
        childIds: ["l-0001-0001", "l-0001-0002", "l-0001-0003"],
        regionType: "TEXT",
        polygon: [
          { x: 88, y: 150 },
          { x: 560, y: 150 },
          { x: 560, y: 760 },
          { x: 88, y: 760 }
        ]
      },
      {
        id: "r-0001-0002",
        type: "REGION",
        parentId: null,
        childIds: ["l-0001-0004", "l-0001-0005"],
        regionType: "TEXT",
        polygon: [
          { x: 640, y: 170 },
          { x: 1120, y: 170 },
          { x: 1120, y: 660 },
          { x: 640, y: 660 }
        ]
      },
      {
        id: "l-0001-0001",
        type: "LINE",
        parentId: "r-0001-0001",
        polygon: [
          { x: 120, y: 190 },
          { x: 532, y: 190 },
          { x: 532, y: 226 },
          { x: 120, y: 226 }
        ],
        baseline: [
          { x: 122, y: 220 },
          { x: 530, y: 220 }
        ]
      },
      {
        id: "l-0001-0002",
        type: "LINE",
        parentId: "r-0001-0001",
        polygon: [
          { x: 120, y: 266 },
          { x: 540, y: 266 },
          { x: 540, y: 300 },
          { x: 120, y: 300 }
        ],
        baseline: [
          { x: 122, y: 294 },
          { x: 538, y: 294 }
        ]
      },
      {
        id: "l-0001-0003",
        type: "LINE",
        parentId: "r-0001-0001",
        polygon: [
          { x: 120, y: 338 },
          { x: 536, y: 338 },
          { x: 536, y: 374 },
          { x: 120, y: 374 }
        ]
      },
      {
        id: "l-0001-0004",
        type: "LINE",
        parentId: "r-0001-0002",
        polygon: [
          { x: 668, y: 208 },
          { x: 1088, y: 208 },
          { x: 1088, y: 244 },
          { x: 668, y: 244 }
        ],
        baseline: [
          { x: 670, y: 238 },
          { x: 1086, y: 238 }
        ]
      },
      {
        id: "l-0001-0005",
        type: "LINE",
        parentId: "r-0001-0002",
        polygon: [
          { x: 668, y: 284 },
          { x: 1094, y: 284 },
          { x: 1094, y: 320 },
          { x: 668, y: 320 }
        ],
        baseline: [
          { x: 670, y: 314 },
          { x: 1092, y: 314 }
        ]
      }
    ],
    readingOrder: [
      { fromId: "r-0001-0001", toId: "l-0001-0001" },
      { fromId: "l-0001-0001", toId: "l-0001-0002" },
      { fromId: "l-0001-0002", toId: "l-0001-0003" },
      { fromId: "r-0001-0001", toId: "r-0001-0002" },
      { fromId: "r-0001-0002", toId: "l-0001-0004" },
      { fromId: "l-0001-0004", toId: "l-0001-0005" }
    ],
    readingOrderGroups: [
      { id: "g-0001", ordered: true, regionIds: ["r-0001-0001", "r-0001-0002"] }
    ],
    readingOrderMeta: {
      schemaVersion: 1,
      mode: "ORDERED",
      source: "AUTO_INFERRED",
      ambiguityScore: 0.14,
      columnCertainty: 0.91,
      overlapConflictScore: 0.03,
      orphanLineCount: 0,
      nonTextComplexityScore: 0.02,
      orderWithheld: false,
      versionEtag: "fixture-layout-etag-001",
      layoutVersionId: "fixture-layout-version-001"
    }
  },
  "layout-run-fixture-001:page-fixture-002": {
    schemaVersion: 1,
    runId: "layout-run-fixture-001",
    pageId: "page-fixture-002",
    pageIndex: 1,
    page: { width: 1200, height: 1800 },
    elements: [
      {
        id: "r-0002-0001",
        type: "REGION",
        parentId: null,
        childIds: ["l-0002-0001", "l-0002-0002"],
        regionType: "TEXT",
        polygon: [
          { x: 120, y: 350 },
          { x: 1080, y: 350 },
          { x: 1080, y: 760 },
          { x: 120, y: 760 }
        ]
      },
      {
        id: "l-0002-0001",
        type: "LINE",
        parentId: "r-0002-0001",
        polygon: [
          { x: 160, y: 400 },
          { x: 1040, y: 400 },
          { x: 1040, y: 436 },
          { x: 160, y: 436 }
        ],
        baseline: [
          { x: 162, y: 430 },
          { x: 1038, y: 430 }
        ]
      },
      {
        id: "l-0002-0002",
        type: "LINE",
        parentId: "r-0002-0001",
        polygon: [
          { x: 160, y: 482 },
          { x: 1020, y: 482 },
          { x: 1020, y: 520 },
          { x: 160, y: 520 }
        ]
      }
    ],
    readingOrder: [
      { fromId: "r-0002-0001", toId: "l-0002-0001" },
      { fromId: "l-0002-0001", toId: "l-0002-0002" }
    ],
    readingOrderGroups: [
      { id: "g-0001", ordered: true, regionIds: ["r-0002-0001"] }
    ],
    readingOrderMeta: {
      schemaVersion: 1,
      mode: "ORDERED",
      source: "AUTO_INFERRED",
      ambiguityScore: 0.08,
      columnCertainty: 0.95,
      overlapConflictScore: 0.01,
      orphanLineCount: 0,
      nonTextComplexityScore: 0,
      orderWithheld: false,
      versionEtag: "fixture-layout-etag-002",
      layoutVersionId: "fixture-layout-version-002"
    }
  },
  "layout-run-fixture-002:page-fixture-001": {
    schemaVersion: 1,
    runId: "layout-run-fixture-002",
    pageId: "page-fixture-001",
    pageIndex: 0,
    page: { width: 1200, height: 1800 },
    elements: [
      {
        id: "r-0001-0001",
        type: "REGION",
        parentId: null,
        childIds: ["l-0001-0001", "l-0001-0002", "l-0001-0003"],
        regionType: "TEXT",
        polygon: [
          { x: 96, y: 132 },
          { x: 568, y: 132 },
          { x: 568, y: 804 },
          { x: 96, y: 804 }
        ]
      },
      {
        id: "r-0001-0002",
        type: "REGION",
        parentId: null,
        childIds: ["l-0001-0004", "l-0001-0005", "l-0001-0006"],
        regionType: "TEXT",
        polygon: [
          { x: 636, y: 154 },
          { x: 1114, y: 154 },
          { x: 1114, y: 804 },
          { x: 636, y: 804 }
        ]
      },
      {
        id: "l-0001-0001",
        type: "LINE",
        parentId: "r-0001-0001",
        polygon: [
          { x: 128, y: 188 },
          { x: 534, y: 188 },
          { x: 534, y: 224 },
          { x: 128, y: 224 }
        ],
        baseline: [
          { x: 130, y: 218 },
          { x: 532, y: 218 }
        ]
      },
      {
        id: "l-0001-0002",
        type: "LINE",
        parentId: "r-0001-0001",
        polygon: [
          { x: 128, y: 262 },
          { x: 544, y: 262 },
          { x: 544, y: 298 },
          { x: 128, y: 298 }
        ],
        baseline: [
          { x: 130, y: 292 },
          { x: 542, y: 292 }
        ]
      },
      {
        id: "l-0001-0003",
        type: "LINE",
        parentId: "r-0001-0001",
        polygon: [
          { x: 128, y: 336 },
          { x: 536, y: 336 },
          { x: 536, y: 372 },
          { x: 128, y: 372 }
        ],
        baseline: [
          { x: 130, y: 366 },
          { x: 534, y: 366 }
        ]
      },
      {
        id: "l-0001-0004",
        type: "LINE",
        parentId: "r-0001-0002",
        polygon: [
          { x: 664, y: 194 },
          { x: 1092, y: 194 },
          { x: 1092, y: 230 },
          { x: 664, y: 230 }
        ],
        baseline: [
          { x: 666, y: 224 },
          { x: 1090, y: 224 }
        ]
      },
      {
        id: "l-0001-0005",
        type: "LINE",
        parentId: "r-0001-0002",
        polygon: [
          { x: 664, y: 268 },
          { x: 1098, y: 268 },
          { x: 1098, y: 304 },
          { x: 664, y: 304 }
        ],
        baseline: [
          { x: 666, y: 298 },
          { x: 1096, y: 298 }
        ]
      },
      {
        id: "l-0001-0006",
        type: "LINE",
        parentId: "r-0001-0002",
        polygon: [
          { x: 664, y: 342 },
          { x: 1088, y: 342 },
          { x: 1088, y: 378 },
          { x: 664, y: 378 }
        ],
        baseline: [
          { x: 666, y: 372 },
          { x: 1086, y: 372 }
        ]
      }
    ],
    readingOrder: [
      { fromId: "r-0001-0001", toId: "l-0001-0001" },
      { fromId: "l-0001-0001", toId: "l-0001-0002" },
      { fromId: "l-0001-0002", toId: "l-0001-0003" },
      { fromId: "r-0001-0001", toId: "r-0001-0002" },
      { fromId: "r-0001-0002", toId: "l-0001-0004" },
      { fromId: "l-0001-0004", toId: "l-0001-0005" },
      { fromId: "l-0001-0005", toId: "l-0001-0006" }
    ],
    readingOrderGroups: [
      { id: "g-0001", ordered: true, regionIds: ["r-0001-0001", "r-0001-0002"] }
    ],
    readingOrderMeta: {
      schemaVersion: 1,
      mode: "ORDERED",
      source: "AUTO_INFERRED",
      ambiguityScore: 0.16,
      columnCertainty: 0.89,
      overlapConflictScore: 0.04,
      orphanLineCount: 0,
      nonTextComplexityScore: 0.01,
      orderWithheld: false,
      versionEtag: "fixture-layout-etag-003",
      layoutVersionId: "fixture-layout-version-003"
    }
  },
  "layout-run-fixture-002:page-fixture-002": {
    schemaVersion: 1,
    runId: "layout-run-fixture-002",
    pageId: "page-fixture-002",
    pageIndex: 1,
    page: { width: 1200, height: 1800 },
    elements: [
      {
        id: "r-0002-0001",
        type: "REGION",
        parentId: null,
        childIds: ["l-0002-0001", "l-0002-0002", "l-0002-0003"],
        regionType: "TEXT",
        polygon: [
          { x: 112, y: 322 },
          { x: 1090, y: 322 },
          { x: 1090, y: 902 },
          { x: 112, y: 902 }
        ]
      },
      {
        id: "l-0002-0001",
        type: "LINE",
        parentId: "r-0002-0001",
        polygon: [
          { x: 156, y: 380 },
          { x: 1050, y: 380 },
          { x: 1050, y: 418 },
          { x: 156, y: 418 }
        ],
        baseline: [
          { x: 158, y: 412 },
          { x: 1048, y: 412 }
        ]
      },
      {
        id: "l-0002-0002",
        type: "LINE",
        parentId: "r-0002-0001",
        polygon: [
          { x: 156, y: 456 },
          { x: 1032, y: 456 },
          { x: 1032, y: 494 },
          { x: 156, y: 494 }
        ],
        baseline: [
          { x: 158, y: 488 },
          { x: 1030, y: 488 }
        ]
      },
      {
        id: "l-0002-0003",
        type: "LINE",
        parentId: "r-0002-0001",
        polygon: [
          { x: 156, y: 534 },
          { x: 1014, y: 534 },
          { x: 1014, y: 572 },
          { x: 156, y: 572 }
        ]
      }
    ],
    readingOrder: [
      { fromId: "r-0002-0001", toId: "l-0002-0001" },
      { fromId: "l-0002-0001", toId: "l-0002-0002" },
      { fromId: "l-0002-0002", toId: "l-0002-0003" }
    ],
    readingOrderGroups: [
      { id: "g-0001", ordered: true, regionIds: ["r-0002-0001"] }
    ],
    readingOrderMeta: {
      schemaVersion: 1,
      mode: "ORDERED",
      source: "AUTO_INFERRED",
      ambiguityScore: 0.09,
      columnCertainty: 0.96,
      overlapConflictScore: 0.01,
      orphanLineCount: 0,
      nonTextComplexityScore: 0,
      orderWithheld: false,
      versionEtag: "fixture-layout-etag-004",
      layoutVersionId: "fixture-layout-version-004"
    }
  }
};

const FIXTURE_LAYOUT_PROJECTION_BY_DOCUMENT: Record<string, DocumentLayoutProjection> = {
  "doc-fixture-002": {
    documentId: "doc-fixture-002",
    projectId: "project-fixture-alpha",
    activeLayoutRunId: "layout-run-fixture-002",
    activeInputPreprocessRunId: "pre-run-fixture-002",
    activeLayoutSnapshotHash: "fixture-layout-snapshot-002",
    downstreamTranscriptionState: "NOT_STARTED",
    downstreamTranscriptionInvalidatedAt: null,
    downstreamTranscriptionInvalidatedReason: null,
    updatedAt: "2026-03-12T08:21:10.000Z"
  }
};

const FIXTURE_REDACTION_RUNS_BY_DOCUMENT: Record<string, DocumentRedactionRun[]> = {
  "doc-fixture-002": [
    {
      id: "redaction-run-fixture-002",
      projectId: "project-fixture-alpha",
      documentId: "doc-fixture-002",
      inputTranscriptionRunId: "transcription-run-fixture-002",
      inputLayoutRunId: "layout-run-fixture-002",
      runKind: "BASELINE",
      supersedesRedactionRunId: "redaction-run-fixture-001",
      supersededByRedactionRunId: null,
      policySnapshotId: "policy-baseline-v1",
      policySnapshotJson: {
        directIdentifiers: {
          dualReviewRequiredCategories: ["EMAIL", "NI_NUMBER"]
        }
      },
      policySnapshotHash: "policy-fixture-hash-002",
      policyId: null,
      policyFamilyId: null,
      policyVersion: null,
      detectorsVersion: "redaction-detectors-v1",
      status: "SUCCEEDED",
      createdBy: "user-fixture-admin",
      createdAt: "2026-03-12T09:14:00.000Z",
      startedAt: "2026-03-12T09:14:10.000Z",
      finishedAt: "2026-03-12T09:15:05.000Z",
      failureReason: null,
      isActiveProjection: true,
      isSuperseded: false,
      isCurrentAttempt: true,
      isHistoricalAttempt: false
    },
    {
      id: "redaction-run-fixture-001",
      projectId: "project-fixture-alpha",
      documentId: "doc-fixture-002",
      inputTranscriptionRunId: "transcription-run-fixture-002",
      inputLayoutRunId: "layout-run-fixture-002",
      runKind: "BASELINE",
      supersedesRedactionRunId: null,
      supersededByRedactionRunId: "redaction-run-fixture-002",
      policySnapshotId: "policy-baseline-v1",
      policySnapshotJson: {
        directIdentifiers: {
          dualReviewRequiredCategories: ["EMAIL", "NI_NUMBER"]
        }
      },
      policySnapshotHash: "policy-fixture-hash-002",
      policyId: null,
      policyFamilyId: null,
      policyVersion: null,
      detectorsVersion: "redaction-detectors-v1",
      status: "SUCCEEDED",
      createdBy: "user-fixture-admin",
      createdAt: "2026-03-11T16:04:00.000Z",
      startedAt: "2026-03-11T16:04:12.000Z",
      finishedAt: "2026-03-11T16:05:09.000Z",
      failureReason: null,
      isActiveProjection: false,
      isSuperseded: true,
      isCurrentAttempt: false,
      isHistoricalAttempt: true
    }
  ]
};

const FIXTURE_REDACTION_PROJECTION_BY_DOCUMENT: Record<
  string,
  DocumentRedactionProjection
> = {
  "doc-fixture-002": {
    documentId: "doc-fixture-002",
    projectId: "project-fixture-alpha",
    activeRedactionRunId: "redaction-run-fixture-002",
    activeTranscriptionRunId: "transcription-run-fixture-002",
    activeLayoutRunId: "layout-run-fixture-002",
    activePolicySnapshotId: "policy-baseline-v1",
    updatedAt: "2026-03-12T09:15:10.000Z"
  }
};

const FIXTURE_REDACTION_FINDINGS_BY_RUN_PAGE: Record<string, DocumentRedactionFinding[]> = {
  "redaction-run-fixture-001:page-fixture-001": [
    {
      id: "red-find-base-1",
      runId: "redaction-run-fixture-001",
      pageId: "page-fixture-001",
      lineId: "line-privacy-001",
      category: "PERSON_NAME",
      spanStart: 0,
      spanEnd: 11,
      spanBasisKind: "LINE_TEXT",
      spanBasisRef: "line-privacy-001",
      confidence: 0.97,
      basisPrimary: "RULE",
      basisSecondaryJson: null,
      assistExplanationKey: null,
      assistExplanationSha256: null,
      bboxRefs: {
        boxes: [{ x: 188, y: 224, width: 286, height: 54 }]
      },
      tokenRefsJson: [{ tokenId: "token-privacy-001" }],
      areaMaskId: null,
      decisionStatus: "APPROVED",
      actionType: "MASK",
      overrideRiskClassification: null,
      overrideRiskReasonCodesJson: null,
      decisionBy: "user-fixture-admin",
      decisionAt: "2026-03-11T16:15:22.000Z",
      decisionReason: null,
      decisionEtag: "red-find-base-1-etag-v3",
      updatedAt: "2026-03-11T16:15:22.000Z",
      createdAt: "2026-03-11T16:15:18.000Z",
      geometry: {
        anchorKind: "TOKEN_LINKED",
        lineId: "line-privacy-001",
        tokenIds: ["token-privacy-001"],
        boxes: [
          {
            x: 188,
            y: 224,
            width: 286,
            height: 54,
            source: "TOKEN_REF"
          }
        ],
        polygons: []
      },
      activeAreaMask: null
    }
  ],
  "redaction-run-fixture-001:page-fixture-002": [
    {
      id: "red-find-base-2",
      runId: "redaction-run-fixture-001",
      pageId: "page-fixture-002",
      lineId: "line-privacy-010",
      category: "EMAIL",
      spanStart: null,
      spanEnd: null,
      spanBasisKind: "NONE",
      spanBasisRef: null,
      confidence: 0.82,
      basisPrimary: "NER",
      basisSecondaryJson: {
        detectorDisagreement: true
      },
      assistExplanationKey: null,
      assistExplanationSha256: null,
      bboxRefs: {
        boxes: [{ x: 366, y: 516, width: 332, height: 68 }]
      },
      tokenRefsJson: null,
      areaMaskId: "mask-fixture-001",
      decisionStatus: "OVERRIDDEN",
      actionType: "MASK",
      overrideRiskClassification: "HIGH",
      overrideRiskReasonCodesJson: ["AREA_MASK_BACKED"],
      decisionBy: "user-fixture-admin",
      decisionAt: "2026-03-11T16:15:38.000Z",
      decisionReason: "Unreadable fold region masked conservatively.",
      decisionEtag: "red-find-base-2-etag-v2",
      updatedAt: "2026-03-11T16:15:38.000Z",
      createdAt: "2026-03-11T16:15:31.000Z",
      geometry: {
        anchorKind: "AREA_MASK_BACKED",
        lineId: "line-privacy-010",
        tokenIds: [],
        boxes: [
          {
            x: 366,
            y: 516,
            width: 332,
            height: 68,
            source: "AREA_MASK"
          }
        ],
        polygons: []
      },
      activeAreaMask: {
        id: "mask-fixture-001",
        runId: "redaction-run-fixture-001",
        pageId: "page-fixture-002",
        geometryJson: {
          boxes: [{ x: 366, y: 516, width: 332, height: 68 }]
        },
        maskReason: "Unreadable direct identifier segment near fold",
        versionEtag: "mask-fixture-001-v1",
        supersedesAreaMaskId: null,
        supersededByAreaMaskId: null,
        createdBy: "user-fixture-admin",
        createdAt: "2026-03-11T16:15:31.000Z",
        updatedAt: "2026-03-11T16:15:31.000Z"
      }
    }
  ],
  "redaction-run-fixture-002:page-fixture-001": [
    {
      id: "red-find-1",
      runId: "redaction-run-fixture-002",
      pageId: "page-fixture-001",
      lineId: "line-privacy-001",
      category: "PERSON_NAME",
      spanStart: 0,
      spanEnd: 11,
      spanBasisKind: "LINE_TEXT",
      spanBasisRef: "line-privacy-001",
      confidence: 0.97,
      basisPrimary: "RULE",
      basisSecondaryJson: {
        fusion: {
          detectorAgreement: "HIGH"
        }
      },
      assistExplanationKey: null,
      assistExplanationSha256: null,
      bboxRefs: {
        boxes: [{ x: 188, y: 224, width: 286, height: 54 }]
      },
      tokenRefsJson: [{ tokenId: "token-privacy-001" }],
      areaMaskId: null,
      decisionStatus: "NEEDS_REVIEW",
      actionType: "PSEUDONYMIZE",
      overrideRiskClassification: null,
      overrideRiskReasonCodesJson: null,
      decisionBy: null,
      decisionAt: null,
      decisionReason: null,
      decisionEtag: "red-find-1-etag-v1",
      updatedAt: "2026-03-12T09:15:20.000Z",
      createdAt: "2026-03-12T09:15:18.000Z",
      geometry: {
        anchorKind: "TOKEN_LINKED",
        lineId: "line-privacy-001",
        tokenIds: ["token-privacy-001"],
        boxes: [
          {
            x: 188,
            y: 224,
            width: 286,
            height: 54,
            source: "TOKEN_REF"
          }
        ],
        polygons: []
      },
      activeAreaMask: null
    }
  ],
  "redaction-run-fixture-002:page-fixture-002": [
    {
      id: "red-find-2",
      runId: "redaction-run-fixture-002",
      pageId: "page-fixture-002",
      lineId: "line-privacy-010",
      category: "EMAIL",
      spanStart: null,
      spanEnd: null,
      spanBasisKind: "NONE",
      spanBasisRef: null,
      confidence: 0.82,
      basisPrimary: "NER",
      basisSecondaryJson: {
        detectorDisagreement: true,
        ambiguousOverlap: true,
        assistSummary: {
          explanation: "Possible contact detail appears in a damaged margin segment."
        }
      },
      assistExplanationKey: null,
      assistExplanationSha256: null,
      bboxRefs: {
        boxes: [{ x: 366, y: 516, width: 332, height: 68 }]
      },
      tokenRefsJson: null,
      areaMaskId: "mask-fixture-002",
      decisionStatus: "NEEDS_REVIEW",
      actionType: "GENERALIZE",
      overrideRiskClassification: "HIGH",
      overrideRiskReasonCodesJson: [
        "AREA_MASK_BACKED",
        "DETECTOR_DISAGREEMENT",
        "AMBIGUOUS_OVERLAP"
      ],
      decisionBy: null,
      decisionAt: null,
      decisionReason: null,
      decisionEtag: "red-find-2-etag-v1",
      updatedAt: "2026-03-12T09:15:32.000Z",
      createdAt: "2026-03-12T09:15:31.000Z",
      geometry: {
        anchorKind: "AREA_MASK_BACKED",
        lineId: "line-privacy-010",
        tokenIds: [],
        boxes: [
          {
            x: 366,
            y: 516,
            width: 332,
            height: 68,
            source: "AREA_MASK"
          }
        ],
        polygons: []
      },
      activeAreaMask: {
        id: "mask-fixture-002",
        runId: "redaction-run-fixture-002",
        pageId: "page-fixture-002",
        geometryJson: {
          boxes: [{ x: 366, y: 516, width: 332, height: 68 }]
        },
        maskReason: "Unreadable direct identifier segment near fold",
        versionEtag: "mask-fixture-002-v1",
        supersedesAreaMaskId: null,
        supersededByAreaMaskId: null,
        createdBy: "user-fixture-admin",
        createdAt: "2026-03-12T09:15:31.000Z",
        updatedAt: "2026-03-12T09:15:31.000Z"
      }
    }
  ]
};

const FIXTURE_REDACTION_PAGE_REVIEWS_BY_RUN_PAGE: Record<
  string,
  DocumentRedactionPageReview
> = {
  "redaction-run-fixture-001:page-fixture-001": {
    runId: "redaction-run-fixture-001",
    pageId: "page-fixture-001",
    reviewStatus: "APPROVED",
    reviewEtag: "red-review-base-page-001-v3",
    firstReviewedBy: "user-fixture-admin",
    firstReviewedAt: "2026-03-11T16:18:45.000Z",
    requiresSecondReview: false,
    secondReviewStatus: "NOT_REQUIRED",
    secondReviewedBy: null,
    secondReviewedAt: null,
    updatedAt: "2026-03-11T16:18:45.000Z"
  },
  "redaction-run-fixture-001:page-fixture-002": {
    runId: "redaction-run-fixture-001",
    pageId: "page-fixture-002",
    reviewStatus: "APPROVED",
    reviewEtag: "red-review-base-page-002-v4",
    firstReviewedBy: "user-fixture-admin",
    firstReviewedAt: "2026-03-11T16:20:06.000Z",
    requiresSecondReview: true,
    secondReviewStatus: "APPROVED",
    secondReviewedBy: "user-fixture-reviewer-2",
    secondReviewedAt: "2026-03-11T16:22:06.000Z",
    updatedAt: "2026-03-11T16:22:06.000Z"
  },
  "redaction-run-fixture-002:page-fixture-001": {
    runId: "redaction-run-fixture-002",
    pageId: "page-fixture-001",
    reviewStatus: "IN_REVIEW",
    reviewEtag: "red-review-page-001-v1",
    firstReviewedBy: "user-fixture-admin",
    firstReviewedAt: "2026-03-12T09:15:45.000Z",
    requiresSecondReview: false,
    secondReviewStatus: "NOT_REQUIRED",
    secondReviewedBy: null,
    secondReviewedAt: null,
    updatedAt: "2026-03-12T09:15:45.000Z"
  },
  "redaction-run-fixture-002:page-fixture-002": {
    runId: "redaction-run-fixture-002",
    pageId: "page-fixture-002",
    reviewStatus: "NOT_STARTED",
    reviewEtag: "red-review-page-002-v1",
    firstReviewedBy: null,
    firstReviewedAt: null,
    requiresSecondReview: false,
    secondReviewStatus: "NOT_REQUIRED",
    secondReviewedBy: null,
    secondReviewedAt: null,
    updatedAt: "2026-03-12T09:15:46.000Z"
  }
};

const FIXTURE_REDACTION_PREVIEW_STATUS_BY_RUN_PAGE: Record<
  string,
  DocumentRedactionPreviewStatusResponse
> = {
  "redaction-run-fixture-001:page-fixture-001": {
    runId: "redaction-run-fixture-001",
    pageId: "page-fixture-001",
    status: "READY",
    previewSha256: "fixture-redaction-preview-sha-base-001",
    generatedAt: "2026-03-11T16:23:02.000Z",
    failureReason: null,
    runOutputStatus: "READY",
    runOutputManifestSha256: "fixture-redaction-manifest-sha-base-001",
    runOutputReadinessState: "OUTPUT_READY",
    downstreamReady: true
  },
  "redaction-run-fixture-001:page-fixture-002": {
    runId: "redaction-run-fixture-001",
    pageId: "page-fixture-002",
    status: "READY",
    previewSha256: "fixture-redaction-preview-sha-base-002",
    generatedAt: "2026-03-11T16:23:04.000Z",
    failureReason: null,
    runOutputStatus: "READY",
    runOutputManifestSha256: "fixture-redaction-manifest-sha-base-001",
    runOutputReadinessState: "OUTPUT_READY",
    downstreamReady: true
  },
  "redaction-run-fixture-002:page-fixture-001": {
    runId: "redaction-run-fixture-002",
    pageId: "page-fixture-001",
    status: "READY",
    previewSha256: "fixture-redaction-preview-sha-001",
    generatedAt: "2026-03-12T09:16:02.000Z",
    failureReason: null,
    runOutputStatus: "PENDING",
    runOutputManifestSha256: null,
    runOutputReadinessState: "OUTPUT_GENERATING",
    downstreamReady: false
  },
  "redaction-run-fixture-002:page-fixture-002": {
    runId: "redaction-run-fixture-002",
    pageId: "page-fixture-002",
    status: "PENDING",
    previewSha256: null,
    generatedAt: null,
    failureReason: null,
    runOutputStatus: "PENDING",
    runOutputManifestSha256: null,
    runOutputReadinessState: "OUTPUT_GENERATING",
    downstreamReady: false
  }
};

const FIXTURE_REDACTION_EVENTS_BY_RUN_PAGE: Record<
  string,
  DocumentRedactionTimelineEvent[]
> = {
  "redaction-run-fixture-001:page-fixture-001": [
    {
      sourceTable: "redaction_page_review_events",
      sourceTablePrecedence: 1,
      eventId: "red-event-base-page-001-approved",
      runId: "redaction-run-fixture-001",
      pageId: "page-fixture-001",
      findingId: null,
      eventType: "PAGE_APPROVED",
      actorUserId: "user-fixture-admin",
      reason: "Baseline review complete.",
      createdAt: "2026-03-11T16:18:45.000Z",
      detailsJson: {}
    }
  ],
  "redaction-run-fixture-001:page-fixture-002": [
    {
      sourceTable: "redaction_page_review_events",
      sourceTablePrecedence: 1,
      eventId: "red-event-base-page-002-second-review",
      runId: "redaction-run-fixture-001",
      pageId: "page-fixture-002",
      findingId: null,
      eventType: "SECOND_REVIEW_APPROVED",
      actorUserId: "user-fixture-reviewer-2",
      reason: "Distinct reviewer approved high-risk override.",
      createdAt: "2026-03-11T16:22:06.000Z",
      detailsJson: {}
    }
  ],
  "redaction-run-fixture-002:page-fixture-001": [
    {
      sourceTable: "redaction_page_review_events",
      sourceTablePrecedence: 1,
      eventId: "red-event-page-001-started",
      runId: "redaction-run-fixture-002",
      pageId: "page-fixture-001",
      findingId: null,
      eventType: "PAGE_REVIEW_STARTED",
      actorUserId: "user-fixture-admin",
      reason: "Workspace opened from triage queue.",
      createdAt: "2026-03-12T09:15:45.000Z",
      detailsJson: {}
    }
  ],
  "redaction-run-fixture-002:page-fixture-002": []
};

const FIXTURE_REDACTION_RUN_REVIEWS_BY_RUN: Record<string, DocumentRedactionRunReview> = {
  "redaction-run-fixture-001": {
    runId: "redaction-run-fixture-001",
    reviewStatus: "APPROVED",
    reviewStartedBy: "user-fixture-admin",
    reviewStartedAt: "2026-03-11T16:17:10.000Z",
    approvedBy: "user-fixture-reviewer-2",
    approvedAt: "2026-03-11T16:24:12.000Z",
    approvedSnapshotKey:
      "controlled/derived/project-fixture-alpha/doc-fixture-002/redaction-run-fixture-001/approved-review.json",
    approvedSnapshotSha256: "approved-fixture-sha-base-001",
    lockedAt: "2026-03-11T16:24:12.000Z",
    updatedAt: "2026-03-11T16:24:12.000Z"
  },
  "redaction-run-fixture-002": {
    runId: "redaction-run-fixture-002",
    reviewStatus: "IN_REVIEW",
    reviewStartedBy: "user-fixture-admin",
    reviewStartedAt: "2026-03-12T09:18:10.000Z",
    approvedBy: null,
    approvedAt: null,
    approvedSnapshotKey: null,
    approvedSnapshotSha256: null,
    lockedAt: null,
    updatedAt: "2026-03-12T09:18:10.000Z"
  }
};

const FIXTURE_REDACTION_RUN_OUTPUTS_BY_RUN: Record<string, DocumentRedactionRunOutput> = {
  "redaction-run-fixture-001": {
    runId: "redaction-run-fixture-001",
    status: "READY",
    reviewStatus: "APPROVED",
    readinessState: "OUTPUT_READY",
    downstreamReady: true,
    outputManifestSha256: "fixture-redaction-manifest-sha-base-001",
    pageCount: 2,
    startedAt: "2026-03-11T16:23:00.000Z",
    generatedAt: "2026-03-11T16:23:08.000Z",
    canceledBy: null,
    canceledAt: null,
    failureReason: null,
    createdAt: "2026-03-11T16:16:00.000Z",
    updatedAt: "2026-03-11T16:23:08.000Z"
  },
  "redaction-run-fixture-002": {
    runId: "redaction-run-fixture-002",
    status: "PENDING",
    reviewStatus: "IN_REVIEW",
    readinessState: "OUTPUT_GENERATING",
    downstreamReady: false,
    outputManifestSha256: null,
    pageCount: 2,
    startedAt: "2026-03-12T09:20:00.000Z",
    generatedAt: null,
    canceledBy: null,
    canceledAt: null,
    failureReason: null,
    createdAt: "2026-03-12T09:14:00.000Z",
    updatedAt: "2026-03-12T09:20:00.000Z"
  }
};

const FIXTURE_REDACTION_RUN_EVENTS_BY_RUN: Record<string, DocumentRedactionTimelineEvent[]> = {
  "redaction-run-fixture-001": [
    {
      sourceTable: "redaction_run_review_events",
      sourceTablePrecedence: 2,
      eventId: "red-event-base-run-approved",
      runId: "redaction-run-fixture-001",
      pageId: null,
      findingId: null,
      eventType: "RUN_APPROVED",
      actorUserId: "user-fixture-reviewer-2",
      reason: "Baseline run approved and locked.",
      createdAt: "2026-03-11T16:24:12.000Z",
      detailsJson: {}
    },
    {
      sourceTable: "redaction_run_output_events",
      sourceTablePrecedence: 3,
      eventId: "red-event-base-run-output-ready",
      runId: "redaction-run-fixture-001",
      pageId: null,
      findingId: null,
      eventType: "RUN_OUTPUT_GENERATION_SUCCEEDED",
      actorUserId: "system-fixture",
      reason: "Reviewed output manifest generated.",
      createdAt: "2026-03-11T16:23:08.000Z",
      detailsJson: {
        fromStatus: "PENDING",
        toStatus: "READY"
      }
    }
  ],
  "redaction-run-fixture-002": [
    {
      sourceTable: "redaction_run_review_events",
      sourceTablePrecedence: 2,
      eventId: "red-event-candidate-run-review-opened",
      runId: "redaction-run-fixture-002",
      pageId: null,
      findingId: null,
      eventType: "RUN_REVIEW_OPENED",
      actorUserId: "user-fixture-admin",
      reason: "Candidate run review started.",
      createdAt: "2026-03-12T09:18:10.000Z",
      detailsJson: {}
    }
  ]
};

const FIXTURE_GOVERNANCE_RUN_SUMMARY: GovernanceRunSummary = {
  runId: "redaction-run-fixture-001",
  projectId: "project-fixture-alpha",
  documentId: "doc-fixture-002",
  runStatus: "SUCCEEDED",
  reviewStatus: "APPROVED",
  approvedSnapshotKey:
    "controlled/derived/project-fixture-alpha/doc-fixture-002/redaction-run-fixture-001/approved-review.json",
  approvedSnapshotSha256: "approved-fixture-sha-base-001",
  runOutputStatus: "READY",
  runOutputManifestSha256: "fixture-redaction-manifest-sha-base-001",
  runCreatedAt: "2026-03-11T16:16:00.000Z",
  runFinishedAt: "2026-03-11T16:24:12.000Z",
  readinessStatus: "READY",
  generationStatus: "IDLE",
  readyManifestId: "gov-manifest-attempt-001",
  readyLedgerId: "gov-ledger-attempt-001",
  latestManifestSha256: "fixture-governance-manifest-sha-001",
  latestLedgerSha256: "fixture-governance-ledger-sha-001",
  ledgerVerificationStatus: "VALID",
  readyAt: "2026-03-11T16:25:15.000Z",
  lastErrorCode: null,
  updatedAt: "2026-03-13T10:02:00.000Z"
};

const FIXTURE_GOVERNANCE_READINESS: GovernanceReadinessProjection = {
  runId: "redaction-run-fixture-001",
  projectId: "project-fixture-alpha",
  documentId: "doc-fixture-002",
  status: "READY",
  generationStatus: "IDLE",
  manifestId: "gov-manifest-attempt-001",
  ledgerId: "gov-ledger-attempt-001",
  lastLedgerVerificationRunId: "gov-ledger-verify-003",
  lastManifestSha256: "fixture-governance-manifest-sha-001",
  lastLedgerSha256: "fixture-governance-ledger-sha-001",
  ledgerVerificationStatus: "VALID",
  ledgerVerifiedAt: "2026-03-13T09:59:30.000Z",
  readyAt: "2026-03-11T16:25:15.000Z",
  lastErrorCode: null,
  updatedAt: "2026-03-13T10:02:00.000Z"
};

const FIXTURE_GOVERNANCE_MANIFEST_ENTRY_SET: GovernanceManifestEntry[] = [
  {
    entryId: "manifest-entry-001",
    appliedAction: "MASK",
    category: "PERSON_NAME",
    pageId: "page-fixture-001",
    pageIndex: 0,
    lineId: "line-privacy-001",
    locationRef: {
      bboxToken: "bbox-fixture-001",
      spanRef: "line-privacy-001:token-1-token-2"
    },
    basisPrimary: "DIRECT_IDENTIFIER_RULE",
    confidence: 0.98,
    secondaryBasisSummary: {
      detectorCount: 2,
      categories: ["PERSON_NAME", "DIRECT_IDENTIFIER"],
      hasPolicyHints: true
    },
    finalDecisionState: "APPLIED",
    reviewState: "APPROVED",
    policySnapshotHash: "policy-snapshot-fixture-v1",
    policyId: "policy-fixture-v1",
    policyFamilyId: "policy-family-fixture",
    policyVersion: "1.0.0",
    decisionTimestamp: "2026-03-11T16:18:45.000Z",
    decisionBy: "user-fixture-admin",
    decisionEtag: "red-find-1-etag-v2"
  },
  {
    entryId: "manifest-entry-002",
    appliedAction: "MASK",
    category: "POSTCODE",
    pageId: "page-fixture-001",
    pageIndex: 0,
    lineId: "line-privacy-002",
    locationRef: {
      bboxToken: "bbox-fixture-002",
      spanRef: "line-privacy-002:token-3-token-5"
    },
    basisPrimary: "RULE_AND_NER",
    confidence: 0.93,
    secondaryBasisSummary: {
      detectorCount: 1,
      categories: ["POSTCODE"],
      hasPolicyHints: true
    },
    finalDecisionState: "APPLIED",
    reviewState: "APPROVED",
    policySnapshotHash: "policy-snapshot-fixture-v1",
    policyId: "policy-fixture-v1",
    policyFamilyId: "policy-family-fixture",
    policyVersion: "1.0.0",
    decisionTimestamp: "2026-03-11T16:20:06.000Z",
    decisionBy: "user-fixture-reviewer-2",
    decisionEtag: "red-find-2-etag-v1"
  },
  {
    entryId: "manifest-entry-003",
    appliedAction: "MASK",
    category: "PHONE",
    pageId: "page-fixture-002",
    pageIndex: 1,
    lineId: "line-privacy-010",
    locationRef: {
      bboxToken: "bbox-fixture-003",
      spanRef: "line-privacy-010:token-2-token-4"
    },
    basisPrimary: "AREA_MASK_BACKED",
    confidence: 0.84,
    secondaryBasisSummary: {
      detectorCount: 3,
      categories: ["PHONE", "DIRECT_IDENTIFIER"],
      hasPolicyHints: true
    },
    finalDecisionState: "APPLIED",
    reviewState: "APPROVED",
    policySnapshotHash: "policy-snapshot-fixture-v1",
    policyId: "policy-fixture-v1",
    policyFamilyId: "policy-family-fixture",
    policyVersion: "1.0.0",
    decisionTimestamp: "2026-03-11T16:22:06.000Z",
    decisionBy: "user-fixture-reviewer-2",
    decisionEtag: "red-find-3-etag-v1"
  }
];

const FIXTURE_GOVERNANCE_LEDGER_ENTRY_SET: GovernanceLedgerEntry[] = [
  {
    rowId: "ledger-row-001",
    rowIndex: 0,
    findingId: "red-find-base-1",
    pageId: "page-fixture-001",
    pageIndex: 0,
    lineId: "line-privacy-001",
    category: "PERSON_NAME",
    actionType: "MASK",
    beforeTextRef: { key: "before-ref-001", span: "token-1:token-2" },
    afterTextRef: { key: "after-ref-001", span: "token-1:token-2" },
    detectorEvidence: {
      basisPrimary: "DIRECT_IDENTIFIER_RULE",
      basisSecondaryJson: { detectorIds: ["rules", "ner"] }
    },
    assistExplanationKey: "assist-exp-fixture-001",
    assistExplanationSha256: "assist-exp-sha-fixture-001",
    actorUserId: "user-fixture-admin",
    decisionTimestamp: "2026-03-11T16:18:45.000Z",
    overrideReason: null,
    finalDecisionState: "APPLIED",
    policySnapshotHash: "policy-snapshot-fixture-v1",
    policyId: "policy-fixture-v1",
    policyFamilyId: "policy-family-fixture",
    policyVersion: "1.0.0",
    prevHash: "0",
    rowHash: "ledger-row-hash-001"
  },
  {
    rowId: "ledger-row-002",
    rowIndex: 1,
    findingId: "red-find-base-2",
    pageId: "page-fixture-001",
    pageIndex: 0,
    lineId: "line-privacy-002",
    category: "POSTCODE",
    actionType: "MASK",
    beforeTextRef: { key: "before-ref-002", span: "token-3:token-5" },
    afterTextRef: { key: "after-ref-002", span: "token-3:token-5" },
    detectorEvidence: {
      basisPrimary: "RULE_AND_NER",
      basisSecondaryJson: { detectorIds: ["ner"] }
    },
    assistExplanationKey: null,
    assistExplanationSha256: null,
    actorUserId: "user-fixture-reviewer-2",
    decisionTimestamp: "2026-03-11T16:20:06.000Z",
    overrideReason: null,
    finalDecisionState: "APPLIED",
    policySnapshotHash: "policy-snapshot-fixture-v1",
    policyId: "policy-fixture-v1",
    policyFamilyId: "policy-family-fixture",
    policyVersion: "1.0.0",
    prevHash: "ledger-row-hash-001",
    rowHash: "ledger-row-hash-002"
  },
  {
    rowId: "ledger-row-003",
    rowIndex: 2,
    findingId: "red-find-base-3",
    pageId: "page-fixture-002",
    pageIndex: 1,
    lineId: "line-privacy-010",
    category: "PHONE",
    actionType: "MASK",
    beforeTextRef: { key: "before-ref-003", span: "token-2:token-4" },
    afterTextRef: { key: "after-ref-003", span: "token-2:token-4" },
    detectorEvidence: {
      basisPrimary: "AREA_MASK_BACKED",
      basisSecondaryJson: { detectorIds: ["area-mask", "rules"] }
    },
    assistExplanationKey: "assist-exp-fixture-003",
    assistExplanationSha256: "assist-exp-sha-fixture-003",
    actorUserId: "user-fixture-reviewer-2",
    decisionTimestamp: "2026-03-11T16:22:06.000Z",
    overrideReason: "Unreadable area required area-mask fallback.",
    finalDecisionState: "APPLIED",
    policySnapshotHash: "policy-snapshot-fixture-v1",
    policyId: "policy-fixture-v1",
    policyFamilyId: "policy-family-fixture",
    policyVersion: "1.0.0",
    prevHash: "ledger-row-hash-002",
    rowHash: "ledger-row-hash-003"
  }
];

const FIXTURE_GOVERNANCE_MANIFEST_ATTEMPTS: DocumentGovernanceRunOverviewResponse["manifestAttempts"] =
  [
    {
      id: "gov-manifest-attempt-001",
      runId: "redaction-run-fixture-001",
      projectId: "project-fixture-alpha",
      documentId: "doc-fixture-002",
      sourceReviewSnapshotKey:
        "controlled/derived/project-fixture-alpha/doc-fixture-002/redaction-run-fixture-001/approved-review.json",
      sourceReviewSnapshotSha256: "approved-fixture-sha-base-001",
      attemptNumber: 1,
      supersedesManifestId: null,
      supersededByManifestId: null,
      status: "SUCCEEDED",
      manifestKey:
        "controlled/derived/project-fixture-alpha/doc-fixture-002/redaction-run-fixture-001/governance/manifest/1/fixture-governance-manifest-sha-001.json",
      manifestSha256: "fixture-governance-manifest-sha-001",
      formatVersion: 1,
      startedAt: "2026-03-11T16:24:20.000Z",
      finishedAt: "2026-03-11T16:24:34.000Z",
      canceledBy: null,
      canceledAt: null,
      failureReason: null,
      createdBy: "system-fixture",
      createdAt: "2026-03-11T16:24:20.000Z"
    }
  ];

const FIXTURE_GOVERNANCE_LEDGER_ATTEMPTS: DocumentGovernanceRunOverviewResponse["ledgerAttempts"] =
  [
    {
      id: "gov-ledger-attempt-001",
      runId: "redaction-run-fixture-001",
      projectId: "project-fixture-alpha",
      documentId: "doc-fixture-002",
      sourceReviewSnapshotKey:
        "controlled/derived/project-fixture-alpha/doc-fixture-002/redaction-run-fixture-001/approved-review.json",
      sourceReviewSnapshotSha256: "approved-fixture-sha-base-001",
      attemptNumber: 1,
      supersedesLedgerId: null,
      supersededByLedgerId: null,
      status: "SUCCEEDED",
      ledgerKey:
        "controlled/derived/project-fixture-alpha/doc-fixture-002/redaction-run-fixture-001/governance/ledger/1/fixture-governance-ledger-sha-001.json",
      ledgerSha256: "fixture-governance-ledger-sha-001",
      hashChainVersion: "v1",
      startedAt: "2026-03-11T16:24:35.000Z",
      finishedAt: "2026-03-11T16:24:50.000Z",
      canceledBy: null,
      canceledAt: null,
      failureReason: null,
      createdBy: "system-fixture",
      createdAt: "2026-03-11T16:24:35.000Z"
    }
  ];

const FIXTURE_GOVERNANCE_RUN_OVERVIEW: DocumentGovernanceRunOverviewResponse = {
  documentId: "doc-fixture-002",
  projectId: "project-fixture-alpha",
  activeRunId: "redaction-run-fixture-001",
  run: FIXTURE_GOVERNANCE_RUN_SUMMARY,
  readiness: FIXTURE_GOVERNANCE_READINESS,
  manifestAttempts: FIXTURE_GOVERNANCE_MANIFEST_ATTEMPTS,
  ledgerAttempts: FIXTURE_GOVERNANCE_LEDGER_ATTEMPTS
};

const FIXTURE_GOVERNANCE_OVERVIEW: DocumentGovernanceOverviewResponse = {
  documentId: "doc-fixture-002",
  projectId: "project-fixture-alpha",
  activeRunId: "redaction-run-fixture-001",
  totalRuns: 1,
  approvedRuns: 1,
  readyRuns: 1,
  pendingRuns: 0,
  failedRuns: 0,
  latestRunId: "redaction-run-fixture-001",
  latestReadyRunId: "redaction-run-fixture-001",
  latestRun: FIXTURE_GOVERNANCE_RUN_SUMMARY,
  latestReadyRun: FIXTURE_GOVERNANCE_RUN_SUMMARY
};

const FIXTURE_GOVERNANCE_RUNS: DocumentGovernanceRunsResponse = {
  documentId: "doc-fixture-002",
  projectId: "project-fixture-alpha",
  activeRunId: "redaction-run-fixture-001",
  items: [FIXTURE_GOVERNANCE_RUN_SUMMARY]
};

const FIXTURE_GOVERNANCE_EVENTS: GovernanceRunEvent[] = [
  {
    id: "gov-event-001",
    runId: "redaction-run-fixture-001",
    eventType: "RUN_CREATED",
    actorUserId: "system-fixture",
    fromStatus: null,
    toStatus: "PENDING",
    reason: "Governance run created from approved privacy review.",
    createdAt: "2026-03-11T16:24:15.000Z",
    screeningSafe: true
  },
  {
    id: "gov-event-002",
    runId: "redaction-run-fixture-001",
    eventType: "MANIFEST_SUCCEEDED",
    actorUserId: "system-fixture",
    fromStatus: "RUNNING",
    toStatus: "SUCCEEDED",
    reason: "Screening-safe manifest finalized.",
    createdAt: "2026-03-11T16:24:34.000Z",
    screeningSafe: true
  },
  {
    id: "gov-event-003",
    runId: "redaction-run-fixture-001",
    eventType: "LEDGER_SUCCEEDED",
    actorUserId: "system-fixture",
    fromStatus: "RUNNING",
    toStatus: "SUCCEEDED",
    reason: "Controlled evidence ledger finalized.",
    createdAt: "2026-03-11T16:24:50.000Z",
    screeningSafe: false
  },
  {
    id: "gov-event-004",
    runId: "redaction-run-fixture-001",
    eventType: "LEDGER_VERIFIED_VALID",
    actorUserId: "system-fixture",
    fromStatus: "RUNNING",
    toStatus: "SUCCEEDED",
    reason: "Hash-chain verification completed as VALID.",
    createdAt: "2026-03-11T16:25:00.000Z",
    screeningSafe: false
  }
];

const FIXTURE_GOVERNANCE_MANIFEST_PAYLOAD = {
  manifestSchemaVersion: 1,
  manifestKind: "SCREENING_SAFE_REDACTION_MANIFEST",
  runId: "redaction-run-fixture-001",
  approvedSnapshotSha256: "approved-fixture-sha-base-001",
  internalOnly: true,
  exportApproved: false,
  notExportApproved: true,
  entryCount: FIXTURE_GOVERNANCE_MANIFEST_ENTRY_SET.length,
  entries: FIXTURE_GOVERNANCE_MANIFEST_ENTRY_SET
};

const FIXTURE_GOVERNANCE_LEDGER_PAYLOAD = {
  schemaVersion: 1,
  ledgerKind: "CONTROLLED_EVIDENCE_LEDGER",
  runId: "redaction-run-fixture-001",
  sourceSnapshotSha256: "approved-fixture-sha-base-001",
  hashChainVersion: "v1",
  rowCount: FIXTURE_GOVERNANCE_LEDGER_ENTRY_SET.length,
  headHash: "ledger-row-hash-003",
  rows: FIXTURE_GOVERNANCE_LEDGER_ENTRY_SET
};

const FIXTURE_GOVERNANCE_MANIFEST_RESPONSE: DocumentGovernanceManifestResponse = {
  overview: FIXTURE_GOVERNANCE_RUN_OVERVIEW,
  latestAttempt: FIXTURE_GOVERNANCE_MANIFEST_ATTEMPTS[0],
  manifestJson: FIXTURE_GOVERNANCE_MANIFEST_PAYLOAD,
  streamSha256: "fixture-governance-manifest-sha-001",
  hashMatches: true,
  internalOnly: true,
  exportApproved: false,
  notExportApproved: true
};

const FIXTURE_GOVERNANCE_MANIFEST_STATUS_RESPONSE: DocumentGovernanceManifestStatusResponse = {
  runId: "redaction-run-fixture-001",
  status: "SUCCEEDED",
  latestAttempt: FIXTURE_GOVERNANCE_MANIFEST_ATTEMPTS[0],
  attemptCount: FIXTURE_GOVERNANCE_MANIFEST_ATTEMPTS.length,
  readyManifestId: "gov-manifest-attempt-001",
  latestManifestSha256: "fixture-governance-manifest-sha-001",
  generationStatus: "IDLE",
  readinessStatus: "READY",
  updatedAt: "2026-03-13T10:02:00.000Z"
};

const FIXTURE_GOVERNANCE_MANIFEST_HASH_RESPONSE: DocumentGovernanceManifestHashResponse = {
  runId: "redaction-run-fixture-001",
  status: "SUCCEEDED",
  manifestId: "gov-manifest-attempt-001",
  manifestSha256: "fixture-governance-manifest-sha-001",
  streamSha256: "fixture-governance-manifest-sha-001",
  hashMatches: true,
  internalOnly: true,
  exportApproved: false,
  notExportApproved: true
};

const FIXTURE_GOVERNANCE_LEDGER_RESPONSE: DocumentGovernanceLedgerResponse = {
  overview: FIXTURE_GOVERNANCE_RUN_OVERVIEW,
  latestAttempt: FIXTURE_GOVERNANCE_LEDGER_ATTEMPTS[0],
  ledgerJson: FIXTURE_GOVERNANCE_LEDGER_PAYLOAD,
  streamSha256: "fixture-governance-ledger-sha-001",
  hashMatches: true,
  internalOnly: true
};

const FIXTURE_GOVERNANCE_LEDGER_STATUS_RESPONSE: DocumentGovernanceLedgerStatusResponse = {
  runId: "redaction-run-fixture-001",
  status: "SUCCEEDED",
  latestAttempt: FIXTURE_GOVERNANCE_LEDGER_ATTEMPTS[0],
  attemptCount: FIXTURE_GOVERNANCE_LEDGER_ATTEMPTS.length,
  readyLedgerId: "gov-ledger-attempt-001",
  latestLedgerSha256: "fixture-governance-ledger-sha-001",
  generationStatus: "IDLE",
  readinessStatus: "READY",
  ledgerVerificationStatus: "VALID",
  updatedAt: "2026-03-13T10:02:00.000Z"
};

const FIXTURE_GOVERNANCE_VERIFY_RUNS: GovernanceLedgerVerificationRun[] = [
  {
    id: "gov-ledger-verify-003",
    runId: "redaction-run-fixture-001",
    attemptNumber: 3,
    supersedesVerificationRunId: "gov-ledger-verify-002",
    supersededByVerificationRunId: null,
    status: "RUNNING",
    verificationResult: null,
    resultJson: null,
    startedAt: "2026-03-13T10:01:45.000Z",
    finishedAt: null,
    canceledBy: null,
    canceledAt: null,
    failureReason: null,
    createdBy: "user-fixture-admin",
    createdAt: "2026-03-13T10:01:45.000Z"
  },
  {
    id: "gov-ledger-verify-002",
    runId: "redaction-run-fixture-001",
    attemptNumber: 2,
    supersedesVerificationRunId: "gov-ledger-verify-001",
    supersededByVerificationRunId: "gov-ledger-verify-003",
    status: "SUCCEEDED",
    verificationResult: "VALID",
    resultJson: {
      valid: true,
      headHash: "ledger-row-hash-003",
      rowCount: 3
    },
    startedAt: "2026-03-13T09:59:15.000Z",
    finishedAt: "2026-03-13T09:59:30.000Z",
    canceledBy: null,
    canceledAt: null,
    failureReason: null,
    createdBy: "user-fixture-admin",
    createdAt: "2026-03-13T09:59:15.000Z"
  },
  {
    id: "gov-ledger-verify-001",
    runId: "redaction-run-fixture-001",
    attemptNumber: 1,
    supersedesVerificationRunId: null,
    supersededByVerificationRunId: "gov-ledger-verify-002",
    status: "SUCCEEDED",
    verificationResult: "INVALID",
    resultJson: {
      valid: false,
      firstInvalidRowId: "ledger-row-002"
    },
    startedAt: "2026-03-13T09:57:12.000Z",
    finishedAt: "2026-03-13T09:57:22.000Z",
    canceledBy: null,
    canceledAt: null,
    failureReason: null,
    createdBy: "user-fixture-admin",
    createdAt: "2026-03-13T09:57:12.000Z"
  }
];

const FIXTURE_GOVERNANCE_LEDGER_SUMMARY_RESPONSE: DocumentGovernanceLedgerSummaryResponse = {
  runId: "redaction-run-fixture-001",
  status: "SUCCEEDED",
  ledgerId: "gov-ledger-attempt-001",
  ledgerSha256: "fixture-governance-ledger-sha-001",
  hashChainVersion: "v1",
  rowCount: FIXTURE_GOVERNANCE_LEDGER_ENTRY_SET.length,
  hashChainHead: "ledger-row-hash-003",
  hashChainValid: true,
  verificationStatus: "VALID",
  categoryCounts: {
    PERSON_NAME: 1,
    POSTCODE: 1,
    PHONE: 1
  },
  actionCounts: {
    MASK: 3
  },
  overrideCount: 1,
  assistReferenceCount: 2,
  internalOnly: true
};

let fixtureRedactionEventSequence = 4;

const FIXTURE_TRANSCRIPTION_LINES_BY_RUN_PAGE: Record<
  string,
  DocumentTranscriptionLineResult[]
> = {
  "transcription-run-fixture-002:page-fixture-001": [
    {
      runId: "transcription-run-fixture-002",
      pageId: "page-fixture-001",
      lineId: "line-privacy-001",
      textDiplomatic: "John Adams presented testimony in York.",
      confLine: 0.97,
      confidenceBand: "HIGH",
      confidenceBasis: "MODEL_NATIVE",
      confidenceCalibrationVersion: "v1",
      alignmentJsonKey: null,
      charBoxesKey: null,
      schemaValidationStatus: "VALID",
      flagsJson: {},
      machineOutputSha256: "fixture-line-privacy-001",
      activeTranscriptVersionId: "line-privacy-001-v1",
      versionEtag: "line-privacy-001-v1",
      tokenAnchorStatus: "CURRENT",
      createdAt: "2026-03-12T09:10:00.000Z",
      updatedAt: "2026-03-12T09:10:00.000Z"
    },
    {
      runId: "transcription-run-fixture-002",
      pageId: "page-fixture-001",
      lineId: "line-privacy-002",
      textDiplomatic: "No sensitive fields were identified in this line.",
      confLine: 0.94,
      confidenceBand: "HIGH",
      confidenceBasis: "MODEL_NATIVE",
      confidenceCalibrationVersion: "v1",
      alignmentJsonKey: null,
      charBoxesKey: null,
      schemaValidationStatus: "VALID",
      flagsJson: {},
      machineOutputSha256: "fixture-line-privacy-002",
      activeTranscriptVersionId: "line-privacy-002-v1",
      versionEtag: "line-privacy-002-v1",
      tokenAnchorStatus: "CURRENT",
      createdAt: "2026-03-12T09:10:03.000Z",
      updatedAt: "2026-03-12T09:10:03.000Z"
    }
  ],
  "transcription-run-fixture-002:page-fixture-002": [
    {
      runId: "transcription-run-fixture-002",
      pageId: "page-fixture-002",
      lineId: "line-privacy-010",
      textDiplomatic: "Contact reaches remain partially legible near the crease.",
      confLine: 0.79,
      confidenceBand: "MEDIUM",
      confidenceBasis: "MODEL_NATIVE",
      confidenceCalibrationVersion: "v1",
      alignmentJsonKey: null,
      charBoxesKey: null,
      schemaValidationStatus: "VALID",
      flagsJson: {},
      machineOutputSha256: "fixture-line-privacy-010",
      activeTranscriptVersionId: "line-privacy-010-v1",
      versionEtag: "line-privacy-010-v1",
      tokenAnchorStatus: "CURRENT",
      createdAt: "2026-03-12T09:10:10.000Z",
      updatedAt: "2026-03-12T09:10:10.000Z"
    }
  ]
};

const FIXTURE_PROJECT_SEARCH_INDEX_ID: Record<string, string | null> = {
  "project-fixture-alpha": "search-index-fixture-002",
  "project-fixture-beta": "search-index-fixture-001"
};

const FIXTURE_PROJECT_SEARCH_HITS: Record<string, ProjectSearchHit[]> = {
  "project-fixture-alpha": [
    {
      searchDocumentId: "search-hit-token-001",
      searchIndexId: "search-index-fixture-002",
      documentId: "doc-fixture-002",
      runId: "transcription-run-fixture-002",
      pageId: "page-fixture-001",
      pageNumber: 1,
      lineId: "line-privacy-001",
      tokenId: "token-privacy-001",
      sourceKind: "LINE",
      sourceRefId: "line-privacy-001",
      matchSpanJson: null,
      tokenGeometryJson: {
        x: 112,
        y: 208,
        w: 64,
        h: 16
      },
      searchText: "John Adams presented testimony in York.",
      searchMetadataJson: {
        confidence: 0.97
      }
    },
    {
      searchDocumentId: "search-hit-rescue-001",
      searchIndexId: "search-index-fixture-002",
      documentId: "doc-fixture-002",
      runId: "transcription-run-fixture-002",
      pageId: "page-fixture-002",
      pageNumber: 2,
      lineId: null,
      tokenId: null,
      sourceKind: "RESCUE_CANDIDATE",
      sourceRefId: "resc-2-1",
      matchSpanJson: {
        start: 8,
        end: 24
      },
      tokenGeometryJson: null,
      searchText: "Rescue candidate confirms partial name near crease.",
      searchMetadataJson: {
        confidence: 0.74
      }
    },
    {
      searchDocumentId: "search-hit-window-001",
      searchIndexId: "search-index-fixture-002",
      documentId: "doc-fixture-002",
      runId: "transcription-run-fixture-002",
      pageId: "page-fixture-002",
      pageNumber: 2,
      lineId: null,
      tokenId: null,
      sourceKind: "PAGE_WINDOW",
      sourceRefId: "window-2-3",
      matchSpanJson: {
        start: 0,
        end: 14
      },
      tokenGeometryJson: null,
      searchText: "Contact reaches remain partially legible near the crease.",
      searchMetadataJson: {}
    }
  ]
};

const FIXTURE_PROJECT_ENTITY_INDEX_ID: Record<string, string | null> = {
  "project-fixture-alpha": "entity-index-fixture-002",
  "project-fixture-beta": null
};

const FIXTURE_PROJECT_ENTITIES: Record<string, ControlledEntity[]> = {
  "project-fixture-alpha": [
    {
      id: "entity-person-john-adams",
      projectId: "project-fixture-alpha",
      entityIndexId: "entity-index-fixture-002",
      entityType: "PERSON",
      displayValue: "John Adams",
      canonicalValue: "john adams",
      confidenceSummaryJson: {
        band: "HIGH",
        average: 0.962,
        min: 0.931,
        max: 0.989,
        occurrenceCount: 2
      },
      occurrenceCount: 2,
      createdAt: "2026-03-12T09:12:00.000Z"
    },
    {
      id: "entity-place-york",
      projectId: "project-fixture-alpha",
      entityIndexId: "entity-index-fixture-002",
      entityType: "PLACE",
      displayValue: "York",
      canonicalValue: "york",
      confidenceSummaryJson: {
        band: "MEDIUM",
        average: 0.742,
        min: 0.742,
        max: 0.742,
        occurrenceCount: 1
      },
      occurrenceCount: 1,
      createdAt: "2026-03-12T09:12:05.000Z"
    }
  ]
};

const FIXTURE_PROJECT_ENTITY_OCCURRENCES: Record<string, EntityOccurrence[]> = {
  "project-fixture-alpha": [
    {
      id: "entocc-john-adams-line",
      entityIndexId: "entity-index-fixture-002",
      entityId: "entity-person-john-adams",
      documentId: "doc-fixture-002",
      runId: "transcription-run-fixture-002",
      pageId: "page-fixture-001",
      pageNumber: 1,
      lineId: "line-privacy-001",
      tokenId: "token-privacy-001",
      sourceKind: "LINE",
      sourceRefId: "line-privacy-001",
      confidence: 0.989,
      occurrenceSpanJson: {
        start: 0,
        end: 10
      },
      occurrenceSpanBasisKind: "LINE_TEXT",
      occurrenceSpanBasisRef: "line-privacy-001",
      tokenGeometryJson: {
        x: 112,
        y: 208,
        w: 64,
        h: 16
      },
      workspacePath:
        "/projects/project-fixture-alpha/documents/doc-fixture-002/transcription/workspace?lineId=line-privacy-001&page=1&runId=transcription-run-fixture-002&sourceKind=LINE&sourceRefId=line-privacy-001&tokenId=token-privacy-001"
    },
    {
      id: "entocc-john-adams-window",
      entityIndexId: "entity-index-fixture-002",
      entityId: "entity-person-john-adams",
      documentId: "doc-fixture-002",
      runId: "transcription-run-fixture-002",
      pageId: "page-fixture-002",
      pageNumber: 2,
      lineId: null,
      tokenId: null,
      sourceKind: "PAGE_WINDOW",
      sourceRefId: "window-2-3",
      confidence: 0.931,
      occurrenceSpanJson: {
        start: 8,
        end: 19
      },
      occurrenceSpanBasisKind: "PAGE_WINDOW_TEXT",
      occurrenceSpanBasisRef: "window-2-3",
      tokenGeometryJson: null,
      workspacePath:
        "/projects/project-fixture-alpha/documents/doc-fixture-002/transcription/workspace?page=2&runId=transcription-run-fixture-002&sourceKind=PAGE_WINDOW&sourceRefId=window-2-3"
    },
    {
      id: "entocc-york-line",
      entityIndexId: "entity-index-fixture-002",
      entityId: "entity-place-york",
      documentId: "doc-fixture-002",
      runId: "transcription-run-fixture-002",
      pageId: "page-fixture-001",
      pageNumber: 1,
      lineId: "line-privacy-001",
      tokenId: null,
      sourceKind: "LINE",
      sourceRefId: "line-privacy-001",
      confidence: 0.742,
      occurrenceSpanJson: {
        start: 31,
        end: 35
      },
      occurrenceSpanBasisKind: "LINE_TEXT",
      occurrenceSpanBasisRef: "line-privacy-001",
      tokenGeometryJson: null,
      workspacePath:
        "/projects/project-fixture-alpha/documents/doc-fixture-002/transcription/workspace?lineId=line-privacy-001&page=1&runId=transcription-run-fixture-002&sourceKind=LINE&sourceRefId=line-privacy-001"
    }
  ]
};

const FIXTURE_PROJECT_DERIVATIVE_INDEX_ID: Record<string, string | null> = {
  "project-fixture-alpha": "derivative-index-fixture-002",
  "project-fixture-beta": null
};

const FIXTURE_PROJECT_DERIVATIVES: Record<string, ProjectDerivativeSnapshot[]> = {
  "project-fixture-alpha": [
    {
      id: "dersnap-fixture-002",
      projectId: "project-fixture-alpha",
      derivativeIndexId: "derivative-index-fixture-002",
      derivativeKind: "SAFE_ENTITY_COUNTS",
      sourceSnapshotJson: {
        sourceRunId: "redaction-run-fixture-002",
        policyVersionRef: "policy-fixture-v3",
        antiJoinQuasiIdentifierFields: ["category", "period", "region"],
        antiJoinMinimumGroupSize: 2
      },
      policyVersionRef: "policy-fixture-v3",
      status: "SUCCEEDED",
      supersedesDerivativeSnapshotId: "dersnap-fixture-001",
      supersededByDerivativeSnapshotId: null,
      storageKey:
        "indexes/derivatives/project-fixture-alpha/derivative-index-fixture-002/dersnap-fixture-002.json",
      snapshotSha256: "fixture-derivative-sha-002",
      candidateSnapshotId: null,
      createdBy: "user-fixture-admin",
      createdAt: "2026-03-12T10:32:00.000Z",
      startedAt: "2026-03-12T10:31:40.000Z",
      finishedAt: "2026-03-12T10:32:00.000Z",
      failureReason: null,
      isActiveGeneration: true
    },
    {
      id: "dersnap-fixture-001",
      projectId: "project-fixture-alpha",
      derivativeIndexId: "derivative-index-fixture-001",
      derivativeKind: "SAFE_ENTITY_COUNTS",
      sourceSnapshotJson: {
        sourceRunId: "redaction-run-fixture-001",
        policyVersionRef: "policy-fixture-v2",
        antiJoinQuasiIdentifierFields: ["category", "period", "region"],
        antiJoinMinimumGroupSize: 2
      },
      policyVersionRef: "policy-fixture-v2",
      status: "SUCCEEDED",
      supersedesDerivativeSnapshotId: null,
      supersededByDerivativeSnapshotId: "dersnap-fixture-002",
      storageKey:
        "indexes/derivatives/project-fixture-alpha/derivative-index-fixture-001/dersnap-fixture-001.json",
      snapshotSha256: "fixture-derivative-sha-001",
      candidateSnapshotId: "candidate-derivative-fixture-001",
      createdBy: "user-fixture-admin",
      createdAt: "2026-03-11T17:04:00.000Z",
      startedAt: "2026-03-11T17:03:40.000Z",
      finishedAt: "2026-03-11T17:04:00.000Z",
      failureReason: null,
      isActiveGeneration: false
    }
  ]
};

const FIXTURE_PROJECT_DERIVATIVE_PREVIEW_ROWS: Record<string, Array<{
  id: string;
  derivativeIndexId: string;
  derivativeSnapshotId: string;
  derivativeKind: string;
  sourceSnapshotJson: Record<string, unknown>;
  displayPayloadJson: Record<string, unknown>;
  suppressedFieldsJson: Record<string, unknown>;
  createdAt: string;
}>> = {
  "dersnap-fixture-002": [
    {
      id: "derrow-fixture-002-1",
      derivativeIndexId: "derivative-index-fixture-002",
      derivativeSnapshotId: "dersnap-fixture-002",
      derivativeKind: "SAFE_ENTITY_COUNTS",
      sourceSnapshotJson: {
        basis: "entity-index-fixture-002",
        category: "occupation",
        period: "1841",
        region: "yorkshire"
      },
      displayPayloadJson: {
        category: "occupation",
        period: "1841",
        region: "yorkshire",
        value: "farm labourer",
        count: 3
      },
      suppressedFieldsJson: {
        fields: {
          "source.person_name": "IDENTIFIER_SUPPRESSED",
          "source.address": "IDENTIFIER_SUPPRESSED"
        },
        suppressedCount: 2
      },
      createdAt: "2026-03-12T10:31:59.000Z"
    },
    {
      id: "derrow-fixture-002-2",
      derivativeIndexId: "derivative-index-fixture-002",
      derivativeSnapshotId: "dersnap-fixture-002",
      derivativeKind: "SAFE_ENTITY_COUNTS",
      sourceSnapshotJson: {
        basis: "entity-index-fixture-002",
        category: "occupation",
        period: "1841",
        region: "yorkshire"
      },
      displayPayloadJson: {
        category: "occupation",
        period: "1841",
        region: "yorkshire",
        value: "maid servant",
        count: 2
      },
      suppressedFieldsJson: {
        fields: {
          "source.person_name": "IDENTIFIER_SUPPRESSED"
        },
        suppressedCount: 1
      },
      createdAt: "2026-03-12T10:31:59.500Z"
    }
  ],
  "dersnap-fixture-001": [
    {
      id: "derrow-fixture-001-1",
      derivativeIndexId: "derivative-index-fixture-001",
      derivativeSnapshotId: "dersnap-fixture-001",
      derivativeKind: "SAFE_ENTITY_COUNTS",
      sourceSnapshotJson: {
        basis: "entity-index-fixture-001",
        category: "occupation",
        period: "1841",
        region: "yorkshire"
      },
      displayPayloadJson: {
        category: "occupation",
        period: "1841",
        region: "yorkshire",
        value: "farm labourer",
        count: 2
      },
      suppressedFieldsJson: {
        fields: {
          "source.person_name": "IDENTIFIER_SUPPRESSED"
        },
        suppressedCount: 1
      },
      createdAt: "2026-03-11T17:03:59.000Z"
    }
  ]
};

const FIXTURE_DERIVATIVE_FREEZE_TIMESTAMP = "2026-03-13T10:04:00.000Z";

function normalizeFixturePath(path: string): URL {
  try {
    if (path.startsWith("http://") || path.startsWith("https://")) {
      return new URL(path);
    }
    return new URL(path, "http://ukde-fixture.local");
  } catch {
    return new URL("http://ukde-fixture.local/");
  }
}

function parseFixtureJsonBody(body: BodyInit | null | undefined): unknown {
  if (typeof body !== "string" || body.trim().length === 0) {
    return null;
  }
  try {
    return JSON.parse(body);
  } catch {
    return null;
  }
}

function cloneProject(project: ProjectSummary): ProjectSummary {
  return {
    ...project
  };
}

function cloneSearchHit(hit: ProjectSearchHit): ProjectSearchHit {
  return {
    ...hit,
    matchSpanJson: hit.matchSpanJson ? { ...hit.matchSpanJson } : null,
    tokenGeometryJson: hit.tokenGeometryJson ? { ...hit.tokenGeometryJson } : null,
    searchMetadataJson: { ...hit.searchMetadataJson }
  };
}

function cloneControlledEntity(entity: ControlledEntity): ControlledEntity {
  return {
    ...entity,
    confidenceSummaryJson: { ...entity.confidenceSummaryJson }
  };
}

function cloneEntityOccurrence(occurrence: EntityOccurrence): EntityOccurrence {
  return {
    ...occurrence,
    occurrenceSpanJson: occurrence.occurrenceSpanJson
      ? { ...occurrence.occurrenceSpanJson }
      : null,
    tokenGeometryJson: occurrence.tokenGeometryJson
      ? { ...occurrence.tokenGeometryJson }
      : null
  };
}

function cloneDerivativeSnapshot(
  snapshot: ProjectDerivativeSnapshot
): ProjectDerivativeSnapshot {
  return {
    ...snapshot,
    sourceSnapshotJson: cloneJson(snapshot.sourceSnapshotJson)
  };
}

function cloneDerivativePreviewRow(
  row: (typeof FIXTURE_PROJECT_DERIVATIVE_PREVIEW_ROWS)[string][number]
): (typeof FIXTURE_PROJECT_DERIVATIVE_PREVIEW_ROWS)[string][number] {
  return {
    ...row,
    sourceSnapshotJson: cloneJson(row.sourceSnapshotJson),
    displayPayloadJson: cloneJson(row.displayPayloadJson),
    suppressedFieldsJson: cloneJson(row.suppressedFieldsJson)
  };
}

function parsePositiveIntParam(raw: string | null, fallback: number): number {
  const parsed = Number.parseInt(raw ?? "", 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}

function parseNonNegativeIntParam(raw: string | null, fallback: number): number {
  const parsed = Number.parseInt(raw ?? "", 10);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return fallback;
  }
  return parsed;
}

function encodeFixturePathSegment(value: string): string {
  return encodeURIComponent(value);
}

function buildFixtureSearchWorkspacePath(
  projectId: string,
  hit: ProjectSearchHit
): string {
  const params: Array<[string, string]> = [
    ["page", String(hit.pageNumber)],
    ["runId", hit.runId]
  ];
  if (hit.lineId) {
    params.push(["lineId", hit.lineId]);
  }
  if (hit.tokenId) {
    params.push(["tokenId", hit.tokenId]);
  }
  if (hit.sourceKind) {
    params.push(["sourceKind", hit.sourceKind]);
  }
  if (hit.sourceRefId) {
    params.push(["sourceRefId", hit.sourceRefId]);
  }
  params.sort(([left], [right]) => left.localeCompare(right));
  const search = new URLSearchParams(params);
  return `/projects/${encodeFixturePathSegment(projectId)}/documents/${encodeFixturePathSegment(hit.documentId)}/transcription/workspace?${search.toString()}`;
}

function cloneDocument(document: ProjectDocument): ProjectDocument {
  return {
    ...document
  };
}

function cloneDocumentPageDetail(
  page: ProjectDocumentPageDetail
): ProjectDocumentPageDetail {
  return {
    ...page
  };
}

function clonePreprocessRun(run: DocumentPreprocessRun): DocumentPreprocessRun {
  return {
    ...run,
    paramsJson: { ...run.paramsJson }
  };
}

function clonePreprocessProjection(
  projection: DocumentPreprocessProjection
): DocumentPreprocessProjection {
  return {
    ...projection
  };
}

function clonePreprocessPageResult(
  pageResult: DocumentPreprocessPageResult
): DocumentPreprocessPageResult {
  return {
    ...pageResult,
    metricsJson: { ...pageResult.metricsJson },
    warningsJson: [...pageResult.warningsJson]
  };
}

function cloneLayoutRun(run: DocumentLayoutRun): DocumentLayoutRun {
  return {
    ...run,
    paramsJson: { ...run.paramsJson }
  };
}

function cloneLayoutProjection(
  projection: DocumentLayoutProjection
): DocumentLayoutProjection {
  return {
    ...projection
  };
}

function cloneLayoutPageResult(
  pageResult: DocumentLayoutPageResult
): DocumentLayoutPageResult {
  return {
    ...pageResult,
    metricsJson: { ...pageResult.metricsJson },
    warningsJson: [...pageResult.warningsJson]
  };
}

function cloneLayoutOverlay(
  overlay: DocumentLayoutPageOverlay
): DocumentLayoutPageOverlay {
  return {
    ...overlay,
    page: { ...overlay.page },
    elements: overlay.elements.map((element) => ({
      ...element,
      polygon: element.polygon.map((point) => ({ ...point })),
      ...(element.type === "REGION"
        ? {
            childIds: [...element.childIds]
          }
        : {}),
      ...(element.type === "LINE" && Array.isArray(element.baseline)
        ? {
            baseline: element.baseline.map((point) => ({ ...point }))
          }
        : {})
    })),
    readingOrder: overlay.readingOrder.map((edge) => ({ ...edge })),
    readingOrderGroups: overlay.readingOrderGroups.map((group) => ({
      ...group,
      regionIds: [...group.regionIds]
    })),
    readingOrderMeta: { ...overlay.readingOrderMeta }
  };
}

function asListPage(page: ProjectDocumentPageDetail): ProjectDocumentPage {
  return {
    id: page.id,
    documentId: page.documentId,
    pageIndex: page.pageIndex,
    width: page.width,
    height: page.height,
    dpi: page.dpi,
    sourceWidth: page.sourceWidth,
    sourceHeight: page.sourceHeight,
    sourceDpi: page.sourceDpi,
    sourceColorMode: page.sourceColorMode,
    status: page.status,
    failureReason: page.failureReason,
    viewerRotation: page.viewerRotation,
    createdAt: page.createdAt,
    updatedAt: page.updatedAt
  };
}

function resolvePreprocessRunsFixture(documentId: string): DocumentPreprocessRun[] {
  const runs = FIXTURE_PREPROCESS_RUNS_BY_DOCUMENT[documentId] ?? [];
  return runs.map((run) => clonePreprocessRun(run));
}

function resolvePreprocessProjectionFixture(
  documentId: string
): DocumentPreprocessProjection | null {
  const projection = FIXTURE_PREPROCESS_PROJECTION_BY_DOCUMENT[documentId];
  return projection ? clonePreprocessProjection(projection) : null;
}

function resolvePreprocessPageResultsFixture(
  runId: string
): DocumentPreprocessPageResult[] {
  const pageResults = FIXTURE_PREPROCESS_PAGE_RESULTS_BY_RUN[runId] ?? [];
  return pageResults.map((pageResult) => clonePreprocessPageResult(pageResult));
}

function resolveLayoutRunsFixture(documentId: string): DocumentLayoutRun[] {
  const runs = FIXTURE_LAYOUT_RUNS_BY_DOCUMENT[documentId] ?? [];
  return runs.map((run) => cloneLayoutRun(run));
}

function resolveLayoutProjectionFixture(
  documentId: string
): DocumentLayoutProjection | null {
  const projection = FIXTURE_LAYOUT_PROJECTION_BY_DOCUMENT[documentId];
  return projection ? cloneLayoutProjection(projection) : null;
}

function resolveLayoutPageResultsFixture(runId: string): DocumentLayoutPageResult[] {
  const pageResults = FIXTURE_LAYOUT_PAGE_RESULTS_BY_RUN[runId] ?? [];
  return pageResults.map((pageResult) => cloneLayoutPageResult(pageResult));
}

function resolveLayoutOverlayFixture(
  runId: string,
  pageId: string
): DocumentLayoutPageOverlay | null {
  const key = `${runId}:${pageId}`;
  const overlay = FIXTURE_LAYOUT_OVERLAYS_BY_RUN_PAGE[key];
  return overlay ? cloneLayoutOverlay(overlay) : null;
}

function cloneRedactionRun(run: DocumentRedactionRun): DocumentRedactionRun {
  return {
    ...run,
    policySnapshotJson: { ...run.policySnapshotJson }
  };
}

function cloneRedactionProjection(
  projection: DocumentRedactionProjection
): DocumentRedactionProjection {
  return {
    ...projection
  };
}

function cloneRedactionRunReview(
  review: DocumentRedactionRunReview
): DocumentRedactionRunReview {
  return {
    ...review
  };
}

function cloneRedactionRunOutput(
  output: DocumentRedactionRunOutput
): DocumentRedactionRunOutput {
  return {
    ...output
  };
}

function cloneRedactionFinding(
  finding: DocumentRedactionFinding
): DocumentRedactionFinding {
  return {
    ...finding,
    basisSecondaryJson: finding.basisSecondaryJson
      ? { ...finding.basisSecondaryJson }
      : null,
    bboxRefs: { ...finding.bboxRefs },
    tokenRefsJson: finding.tokenRefsJson
      ? finding.tokenRefsJson.map((item) => ({ ...item }))
      : null,
    overrideRiskReasonCodesJson: finding.overrideRiskReasonCodesJson
      ? [...finding.overrideRiskReasonCodesJson]
      : null,
    geometry: {
      ...finding.geometry,
      tokenIds: [...finding.geometry.tokenIds],
      boxes: finding.geometry.boxes.map((box) => ({ ...box })),
      polygons: finding.geometry.polygons.map((polygon) => ({
        ...polygon,
        points: polygon.points.map((point) => ({ ...point }))
      }))
    },
    activeAreaMask: finding.activeAreaMask
      ? {
          ...finding.activeAreaMask,
          geometryJson: { ...finding.activeAreaMask.geometryJson }
        }
      : null
  };
}

function cloneRedactionPageReview(
  review: DocumentRedactionPageReview
): DocumentRedactionPageReview {
  return {
    ...review
  };
}

function cloneRedactionPreviewStatus(
  previewStatus: DocumentRedactionPreviewStatusResponse
): DocumentRedactionPreviewStatusResponse {
  return {
    ...previewStatus
  };
}

function cloneRedactionTimelineEvent(
  event: DocumentRedactionTimelineEvent
): DocumentRedactionTimelineEvent {
  return {
    ...event,
    detailsJson: { ...event.detailsJson }
  };
}

function cloneTranscriptionLine(
  line: DocumentTranscriptionLineResult
): DocumentTranscriptionLineResult {
  return {
    ...line,
    flagsJson: { ...line.flagsJson }
  };
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function resolveRedactionRunsFixture(documentId: string): DocumentRedactionRun[] {
  const runs = FIXTURE_REDACTION_RUNS_BY_DOCUMENT[documentId] ?? [];
  return runs.map((run) => cloneRedactionRun(run));
}

function resolveRedactionProjectionFixture(
  documentId: string
): DocumentRedactionProjection | null {
  const projection = FIXTURE_REDACTION_PROJECTION_BY_DOCUMENT[documentId];
  return projection ? cloneRedactionProjection(projection) : null;
}

function resolveRedactionFindingsFixture(
  runId: string,
  pageId: string
): DocumentRedactionFinding[] {
  const key = `${runId}:${pageId}`;
  const findings = FIXTURE_REDACTION_FINDINGS_BY_RUN_PAGE[key] ?? [];
  return findings.map((finding) => cloneRedactionFinding(finding));
}

function resolveRedactionPageReviewFixture(
  runId: string,
  pageId: string
): DocumentRedactionPageReview | null {
  const key = `${runId}:${pageId}`;
  const review = FIXTURE_REDACTION_PAGE_REVIEWS_BY_RUN_PAGE[key];
  return review ? cloneRedactionPageReview(review) : null;
}

function resolveRedactionPreviewStatusFixture(
  runId: string,
  pageId: string
): DocumentRedactionPreviewStatusResponse | null {
  const key = `${runId}:${pageId}`;
  const previewStatus = FIXTURE_REDACTION_PREVIEW_STATUS_BY_RUN_PAGE[key];
  return previewStatus ? cloneRedactionPreviewStatus(previewStatus) : null;
}

function resolveRedactionRunReviewFixture(
  runId: string
): DocumentRedactionRunReview | null {
  const review = FIXTURE_REDACTION_RUN_REVIEWS_BY_RUN[runId];
  return review ? cloneRedactionRunReview(review) : null;
}

function resolveRedactionRunOutputFixture(
  runId: string
): DocumentRedactionRunOutput | null {
  const output = FIXTURE_REDACTION_RUN_OUTPUTS_BY_RUN[runId];
  return output ? cloneRedactionRunOutput(output) : null;
}

function resolveRedactionEventsFixture(
  runId: string,
  pageId: string
): DocumentRedactionTimelineEvent[] {
  const key = `${runId}:${pageId}`;
  const events = FIXTURE_REDACTION_EVENTS_BY_RUN_PAGE[key] ?? [];
  return events.map((event) => cloneRedactionTimelineEvent(event));
}

function resolveRedactionRunEventsFixture(
  runId: string
): DocumentRedactionTimelineEvent[] {
  const runLevel = FIXTURE_REDACTION_RUN_EVENTS_BY_RUN[runId] ?? [];
  const pageLevel = Object.entries(FIXTURE_REDACTION_EVENTS_BY_RUN_PAGE)
    .filter(([key]) => key.startsWith(`${runId}:`))
    .flatMap(([, events]) => events);
  return [...runLevel, ...pageLevel].map((event) => cloneRedactionTimelineEvent(event));
}

function resolveTranscriptionLinesFixture(
  runId: string,
  pageId: string
): DocumentTranscriptionLineResult[] {
  const key = `${runId}:${pageId}`;
  const lines = FIXTURE_TRANSCRIPTION_LINES_BY_RUN_PAGE[key] ?? [];
  return lines.map((line) => cloneTranscriptionLine(line));
}

function isUnresolvedStatus(status: string): boolean {
  return status === "NEEDS_REVIEW" || status === "OVERRIDDEN" || status === "FALSE_POSITIVE";
}

function isDirectIdentifierCategory(category: string): boolean {
  const normalized = category.trim().toUpperCase();
  if (!normalized) {
    return false;
  }
  if (normalized.startsWith("DIRECT_")) {
    return true;
  }
  return [
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
    "NHS_NUMBER"
  ].includes(normalized);
}

function filterRedactionFindings(options: {
  findings: DocumentRedactionFinding[];
  path: URL;
}): DocumentRedactionFinding[] {
  const { findings, path } = options;
  const category = path.searchParams.get("category")?.trim() ?? "";
  const unresolvedOnly =
    path.searchParams.get("unresolvedOnly")?.trim().toLowerCase() === "true";
  const directIdentifiersOnly =
    path.searchParams.get("directIdentifiersOnly")?.trim().toLowerCase() === "true";
  const findingId = path.searchParams.get("findingId")?.trim() ?? "";
  const lineId = path.searchParams.get("lineId")?.trim() ?? "";
  const tokenId = path.searchParams.get("tokenId")?.trim() ?? "";
  return findings.filter((finding) => {
    if (category && finding.category !== category) {
      return false;
    }
    if (unresolvedOnly && !isUnresolvedStatus(finding.decisionStatus)) {
      return false;
    }
    if (directIdentifiersOnly && !isDirectIdentifierCategory(finding.category)) {
      return false;
    }
    if (findingId && finding.id !== findingId) {
      return false;
    }
    if (lineId) {
      const findingLineId = finding.geometry.lineId ?? finding.lineId ?? "";
      if (findingLineId !== lineId) {
        return false;
      }
    }
    if (tokenId && !finding.geometry.tokenIds.includes(tokenId)) {
      return false;
    }
    return true;
  });
}

function buildRedactionRunPagesFixture(
  runId: string,
  documentId: string
): DocumentRedactionRunPage[] {
  const pages = resolveDocumentPagesFixture(documentId);
  const items: DocumentRedactionRunPage[] = [];
  for (const page of pages) {
    const findings = resolveRedactionFindingsFixture(runId, page.id);
    const review = resolveRedactionPageReviewFixture(runId, page.id);
    const previewStatus = resolveRedactionPreviewStatusFixture(runId, page.id);
    items.push({
      runId,
      pageId: page.id,
      pageIndex: page.pageIndex,
      findingCount: findings.length,
      unresolvedCount: findings.filter((finding) =>
        isUnresolvedStatus(finding.decisionStatus)
      ).length,
      reviewStatus: review?.reviewStatus ?? "NOT_STARTED",
      reviewEtag: review?.reviewEtag ?? "",
      requiresSecondReview: review?.requiresSecondReview ?? false,
      secondReviewStatus: review?.secondReviewStatus ?? "NOT_REQUIRED",
      secondReviewedBy: review?.secondReviewedBy ?? null,
      secondReviewedAt: review?.secondReviewedAt ?? null,
      lastReviewedBy: review?.firstReviewedBy ?? null,
      lastReviewedAt: review?.firstReviewedAt ?? null,
      previewStatus: previewStatus?.status ?? null,
      topFindings: findings.slice(0, 5)
    });
  }
  return items.sort((left, right) => left.pageIndex - right.pageIndex);
}

function resolveRedactionOverviewFixture(
  projectId: string,
  documentId: string
): DocumentRedactionOverviewResponse {
  const projection = resolveRedactionProjectionFixture(documentId);
  const runs = resolveRedactionRunsFixture(documentId);
  const activeRun = projection?.activeRedactionRunId
    ? runs.find((run) => run.id === projection.activeRedactionRunId) ?? null
    : null;
  const latestRun = runs.length > 0 ? runs[0] : null;
  const pages = activeRun ? buildRedactionRunPagesFixture(activeRun.id, documentId) : [];
  const findings = activeRun
    ? pages.flatMap((page) => resolveRedactionFindingsFixture(activeRun.id, page.pageId))
    : [];
  const findingsByCategory: Record<string, number> = {};
  let unresolvedFindings = 0;
  let autoAppliedFindings = 0;
  let needsReviewFindings = 0;
  let overriddenFindings = 0;
  for (const finding of findings) {
    findingsByCategory[finding.category] = (findingsByCategory[finding.category] ?? 0) + 1;
    if (finding.decisionStatus === "AUTO_APPLIED") {
      autoAppliedFindings += 1;
    } else if (finding.decisionStatus === "NEEDS_REVIEW") {
      needsReviewFindings += 1;
    } else if (finding.decisionStatus === "OVERRIDDEN") {
      overriddenFindings += 1;
    }
    if (isUnresolvedStatus(finding.decisionStatus)) {
      unresolvedFindings += 1;
    }
  }
  const previewStatuses = activeRun
    ? pages.map((page) => resolveRedactionPreviewStatusFixture(activeRun.id, page.pageId))
    : [];
  const previewReadyPages = previewStatuses.filter((status) => status?.status === "READY").length;
  const previewFailedPages = previewStatuses.filter((status) => status?.status === "FAILED").length;
  const pagesBlockedForReview = pages.filter((page) => page.reviewStatus !== "APPROVED").length;
  return {
    documentId,
    projectId,
    projection,
    activeRun,
    latestRun,
    totalRuns: runs.length,
    pageCount: resolveDocumentPagesFixture(documentId).length,
    findingsByCategory,
    unresolvedFindings,
    autoAppliedFindings,
    needsReviewFindings,
    overriddenFindings,
    pagesBlockedForReview,
    previewReadyPages,
    previewTotalPages: previewStatuses.length,
    previewFailedPages
  };
}

function resolveListSlice(path: URL): { cursor: number; pageSize: number } {
  const cursorRaw = Number(path.searchParams.get("cursor") ?? "0");
  const pageSizeRaw = Number(path.searchParams.get("pageSize") ?? "50");
  const cursor = Number.isFinite(cursorRaw) && cursorRaw >= 0 ? cursorRaw : 0;
  const pageSize =
    Number.isFinite(pageSizeRaw) && pageSizeRaw > 0
      ? Math.min(500, Math.floor(pageSizeRaw))
      : 50;
  return { cursor: Math.floor(cursor), pageSize };
}

function sliceFixtureItems<T>(
  items: T[],
  path: URL
): { items: T[]; nextCursor: number | null } {
  const { cursor, pageSize } = resolveListSlice(path);
  const end = cursor + pageSize;
  return {
    items: items.slice(cursor, end),
    nextCursor: end < items.length ? end : null
  };
}

function resolveGovernanceCursorLimit(path: URL): { cursor: number; limit: number } {
  const cursorRaw = Number(path.searchParams.get("cursor") ?? "0");
  const limitRaw = Number(path.searchParams.get("limit") ?? "100");
  const cursor = Number.isFinite(cursorRaw) && cursorRaw >= 0 ? Math.floor(cursorRaw) : 0;
  const limit =
    Number.isFinite(limitRaw) && limitRaw > 0
      ? Math.min(200, Math.floor(limitRaw))
      : 100;
  return { cursor, limit };
}

function resolveGovernanceManifestEntriesFixture(
  path: URL
): { items: GovernanceManifestEntry[]; totalCount: number; nextCursor: number | null } {
  const categoryFilter = path.searchParams.get("category")?.trim() ?? "";
  const reviewStateFilter = path.searchParams.get("reviewState")?.trim() ?? "";
  const pageFilter = Number.parseInt(path.searchParams.get("page") ?? "", 10);
  const fromFilter = path.searchParams.get("from")?.trim() ?? "";
  const toFilter = path.searchParams.get("to")?.trim() ?? "";
  const fromTime = fromFilter ? Date.parse(`${fromFilter}T00:00:00.000Z`) : Number.NaN;
  const toTime = toFilter ? Date.parse(`${toFilter}T23:59:59.999Z`) : Number.NaN;

  const filtered = FIXTURE_GOVERNANCE_MANIFEST_ENTRY_SET.filter((entry) => {
    if (categoryFilter && entry.category !== categoryFilter) {
      return false;
    }
    if (reviewStateFilter && entry.reviewState !== reviewStateFilter) {
      return false;
    }
    if (Number.isFinite(pageFilter) && entry.pageIndex !== pageFilter - 1) {
      return false;
    }
    if (Number.isFinite(fromTime) || Number.isFinite(toTime)) {
      const decisionTime = Date.parse(entry.decisionTimestamp ?? "");
      if (!Number.isFinite(decisionTime)) {
        return false;
      }
      if (Number.isFinite(fromTime) && decisionTime < fromTime) {
        return false;
      }
      if (Number.isFinite(toTime) && decisionTime > toTime) {
        return false;
      }
    }
    return true;
  });

  const { cursor, limit } = resolveGovernanceCursorLimit(path);
  const end = cursor + limit;
  return {
    items: filtered.slice(cursor, end).map((entry) => cloneJson(entry)),
    totalCount: filtered.length,
    nextCursor: end < filtered.length ? end : null
  };
}

function resolveGovernanceLedgerEntriesFixture(path: URL): {
  items: GovernanceLedgerEntry[];
  totalCount: number;
  nextCursor: number | null;
  view: "list" | "timeline";
} {
  const view = path.searchParams.get("view")?.trim() === "timeline" ? "timeline" : "list";
  const { cursor, limit } = resolveGovernanceCursorLimit(path);
  const end = cursor + limit;
  return {
    items: FIXTURE_GOVERNANCE_LEDGER_ENTRY_SET.slice(cursor, end).map((entry) =>
      cloneJson(entry)
    ),
    totalCount: FIXTURE_GOVERNANCE_LEDGER_ENTRY_SET.length,
    nextCursor: end < FIXTURE_GOVERNANCE_LEDGER_ENTRY_SET.length ? end : null,
    view
  };
}

function filterPreprocessPageResultsForQuality(options: {
  items: DocumentPreprocessPageResult[];
  path: URL;
}): DocumentPreprocessPageResult[] {
  const { items, path } = options;
  const warningFilter = path.searchParams.get("warning")?.trim() || null;
  const statusFilter = path.searchParams.get("status")?.trim() || null;
  return items.filter((item) => {
    if (warningFilter && !item.warningsJson.includes(warningFilter)) {
      return false;
    }
    if (
      statusFilter &&
      item.status !== statusFilter &&
      item.qualityGateStatus !== statusFilter
    ) {
      return false;
    }
    return true;
  });
}

function filterLayoutPageResults(options: {
  items: DocumentLayoutPageResult[];
  path: URL;
}): DocumentLayoutPageResult[] {
  const { items, path } = options;
  const statusFilter = path.searchParams.get("status")?.trim() || null;
  const recallFilter = path.searchParams.get("pageRecallStatus")?.trim() || null;
  return items.filter((item) => {
    if (statusFilter && item.status !== statusFilter) {
      return false;
    }
    if (recallFilter && item.pageRecallStatus !== recallFilter) {
      return false;
    }
    return true;
  });
}

function resolveMetricNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function resolveActivePreprocessRun(options: {
  projection: DocumentPreprocessProjection | null;
  runs: DocumentPreprocessRun[];
}): DocumentPreprocessRun | null {
  const { projection, runs } = options;
  if (!projection?.activePreprocessRunId) {
    return null;
  }
  return (
    runs.find((run) => run.id === projection.activePreprocessRunId) ?? null
  );
}

function resolveActiveLayoutRun(options: {
  projection: DocumentLayoutProjection | null;
  runs: DocumentLayoutRun[];
}): DocumentLayoutRun | null {
  const { projection, runs } = options;
  if (!projection?.activeLayoutRunId) {
    return null;
  }
  return runs.find((run) => run.id === projection.activeLayoutRunId) ?? null;
}

function buildPreprocessOverviewFixture(
  projectId: string,
  documentId: string
): DocumentPreprocessOverviewResponse {
  const projection = resolvePreprocessProjectionFixture(documentId);
  const runs = resolvePreprocessRunsFixture(documentId);
  const activeRun = resolveActivePreprocessRun({ projection, runs });
  const latestRun = runs.length > 0 ? runs[0] : null;
  const activeResults = activeRun ? resolvePreprocessPageResultsFixture(activeRun.id) : [];
  const activeStatusCounts: DocumentPreprocessOverviewResponse["activeStatusCounts"] = {
    QUEUED: 0,
    RUNNING: 0,
    SUCCEEDED: 0,
    FAILED: 0,
    CANCELED: 0
  };
  const activeQualityGateCounts: DocumentPreprocessOverviewResponse["activeQualityGateCounts"] = {
    PASS: 0,
    REVIEW_REQUIRED: 0,
    BLOCKED: 0
  };
  for (const result of activeResults) {
    activeStatusCounts[result.status] += 1;
    activeQualityGateCounts[result.qualityGateStatus] += 1;
  }
  return {
    documentId,
    projectId,
    projection,
    activeRun,
    latestRun,
    totalRuns: runs.length,
    pageCount: resolveDocumentPagesFixture(documentId).length,
    activeStatusCounts,
    activeQualityGateCounts,
    activeWarningCount: activeResults.reduce(
      (count, item) => count + item.warningsJson.length,
      0
    )
  };
}

function buildLayoutOverviewFixture(
  projectId: string,
  documentId: string
): DocumentLayoutOverviewResponse {
  const projection = resolveLayoutProjectionFixture(documentId);
  const runs = resolveLayoutRunsFixture(documentId);
  const activeRun = resolveActiveLayoutRun({ projection, runs });
  const latestRun = runs.length > 0 ? runs[0] : null;
  const activeResults = activeRun ? resolveLayoutPageResultsFixture(activeRun.id) : [];

  const activeStatusCounts: DocumentLayoutOverviewResponse["activeStatusCounts"] = {
    QUEUED: 0,
    RUNNING: 0,
    SUCCEEDED: 0,
    FAILED: 0,
    CANCELED: 0
  };
  const activeRecallCounts: DocumentLayoutOverviewResponse["activeRecallCounts"] = {
    COMPLETE: 0,
    NEEDS_RESCUE: 0,
    NEEDS_MANUAL_REVIEW: 0
  };
  let regionsTotal = 0;
  let linesTotal = 0;
  let hasRegionsMetric = false;
  let hasLinesMetric = false;
  let pagesWithIssues = 0;
  const coverageValues: number[] = [];
  const confidenceValues: number[] = [];

  for (const result of activeResults) {
    activeStatusCounts[result.status] += 1;
    activeRecallCounts[result.pageRecallStatus] += 1;
    const regionsMetric = resolveMetricNumber(
      result.metricsJson.num_regions ?? result.metricsJson.regions_detected
    );
    const linesMetric = resolveMetricNumber(
      result.metricsJson.num_lines ?? result.metricsJson.lines_detected
    );
    if (regionsMetric !== null) {
      regionsTotal += Math.max(0, Math.round(regionsMetric));
      hasRegionsMetric = true;
    }
    if (linesMetric !== null) {
      linesTotal += Math.max(0, Math.round(linesMetric));
      hasLinesMetric = true;
    }
    const coverageMetric = resolveMetricNumber(
      result.metricsJson.line_coverage_percent ?? result.metricsJson.coverage_percent
    );
    if (coverageMetric !== null) {
      coverageValues.push(coverageMetric);
    }
    const confidenceMetric = resolveMetricNumber(
      result.metricsJson.structure_confidence ?? result.metricsJson.reading_order_confidence
    );
    if (confidenceMetric !== null) {
      confidenceValues.push(confidenceMetric);
    }
    if (result.warningsJson.length > 0 || result.pageRecallStatus !== "COMPLETE") {
      pagesWithIssues += 1;
    }
  }

  const summary: DocumentLayoutOverviewResponse["summary"] = {
    regionsDetected: hasRegionsMetric ? regionsTotal : null,
    linesDetected: hasLinesMetric ? linesTotal : null,
    pagesWithIssues,
    coveragePercent:
      coverageValues.length > 0
        ? coverageValues.reduce((sum, value) => sum + value, 0) / coverageValues.length
        : null,
    structureConfidence:
      confidenceValues.length > 0
        ? confidenceValues.reduce((sum, value) => sum + value, 0) / confidenceValues.length
        : null
  };

  return {
    documentId,
    projectId,
    projection,
    activeRun,
    latestRun,
    totalRuns: runs.length,
    pageCount: resolveDocumentPagesFixture(documentId).length,
    activeStatusCounts,
    activeRecallCounts,
    summary
  };
}

function buildTranscriptionOverviewFixture(
  projectId: string,
  documentId: string
): DocumentTranscriptionOverviewResponse {
  const redactionProjection = resolveRedactionProjectionFixture(documentId);
  const activeRunId = redactionProjection?.activeTranscriptionRunId ?? null;
  const pages = resolveDocumentPagesFixture(documentId);
  const activeStatusCounts: DocumentTranscriptionOverviewResponse["activeStatusCounts"] = {
    QUEUED: 0,
    RUNNING: 0,
    SUCCEEDED: 0,
    FAILED: 0,
    CANCELED: 0
  };

  let activeLineCount = 0;
  let activeTokenCount = 0;
  let activeAnchorRefreshRequired = 0;
  let activeLowConfidenceLines = 0;

  if (activeRunId) {
    for (const page of pages) {
      const lines = resolveTranscriptionLinesFixture(activeRunId, page.id);
      activeLineCount += lines.length;
      for (const line of lines) {
        activeTokenCount += line.textDiplomatic.trim().split(/\s+/).filter(Boolean).length;
        if (line.tokenAnchorStatus === "REFRESH_REQUIRED") {
          activeAnchorRefreshRequired += 1;
        }
        if (typeof line.confLine === "number" && line.confLine < 0.75) {
          activeLowConfidenceLines += 1;
        }
      }
    }
    activeStatusCounts.SUCCEEDED = pages.length;
  }

  const runRef = activeRunId
    ? ({ id: activeRunId, status: "SUCCEEDED" } as DocumentTranscriptionOverviewResponse["activeRun"])
    : null;

  return {
    documentId,
    projectId,
    projection: null,
    activeRun: runRef,
    latestRun: runRef,
    totalRuns: runRef ? 1 : 0,
    pageCount: pages.length,
    activeStatusCounts,
    activeLineCount,
    activeTokenCount,
    activeAnchorRefreshRequired,
    activeLowConfidenceLines
  };
}

function buildDefaultGovernanceOverview(
  projectId: string,
  documentId: string
): DocumentGovernanceOverviewResponse {
  return {
    documentId,
    projectId,
    activeRunId: null,
    totalRuns: 0,
    approvedRuns: 0,
    readyRuns: 0,
    pendingRuns: 0,
    failedRuns: 0,
    latestRunId: null,
    latestReadyRunId: null,
    latestRun: null,
    latestReadyRun: null
  };
}

function buildPipelineStatusFixture(options: {
  document: ProjectDocument;
  fixtureProfile: BrowserFixtureSessionProfile | null;
  projectId: string;
}): DocumentPipelineStatusResponse {
  const { document, fixtureProfile, projectId } = options;
  const failures: Array<{ phaseId: DocumentPipelinePhaseId; detail: string }> = [];
  const phases: DocumentPipelineStatusResponse["phases"] = [];

  const timelineItems = (FIXTURE_DOCUMENT_TIMELINES[document.id] ?? []).map((item) => ({
    ...item
  }));
  phases.push(computeIngestPipelinePhase(document.status, timelineItems));
  phases.push(computePreprocessPipelinePhase(buildPreprocessOverviewFixture(projectId, document.id)));
  phases.push(computeLayoutPipelinePhase(buildLayoutOverviewFixture(projectId, document.id)));
  phases.push(
    computeTranscriptionPipelinePhase(
      buildTranscriptionOverviewFixture(projectId, document.id)
    )
  );
  phases.push(
    computePrivacyPipelinePhase(resolveRedactionOverviewFixture(projectId, document.id))
  );

  if (!canViewGovernanceManifest(fixtureProfile)) {
    const detail =
      "Governance manifest access requires project lead, reviewer, admin, or auditor roles.";
    phases.push(createDegradedPipelinePhase("GOVERNANCE", "Governance", detail));
    failures.push({ phaseId: "GOVERNANCE", detail });
  } else {
    const overview =
      document.id === FIXTURE_GOVERNANCE_OVERVIEW.documentId
        ? cloneJson(FIXTURE_GOVERNANCE_OVERVIEW)
        : buildDefaultGovernanceOverview(projectId, document.id);

    const activeRunId = overview.activeRunId;
    const manifestStatus =
      activeRunId && activeRunId === FIXTURE_GOVERNANCE_MANIFEST_STATUS_RESPONSE.runId
        ? cloneJson(FIXTURE_GOVERNANCE_MANIFEST_STATUS_RESPONSE)
        : null;
    let ledgerStatus =
      activeRunId &&
      activeRunId === FIXTURE_GOVERNANCE_LEDGER_STATUS_RESPONSE.runId &&
      canViewGovernanceLedger(fixtureProfile)
        ? cloneJson(FIXTURE_GOVERNANCE_LEDGER_STATUS_RESPONSE)
        : null;

    if (activeRunId && activeRunId === FIXTURE_GOVERNANCE_LEDGER_STATUS_RESPONSE.runId) {
      if (!canViewGovernanceLedger(fixtureProfile)) {
        failures.push({
          phaseId: "GOVERNANCE",
          detail:
            "Evidence-ledger routes are restricted to administrator or auditor roles."
        });
      } else if (!ledgerStatus) {
        failures.push({
          phaseId: "GOVERNANCE",
          detail: "Governance ledger status unavailable."
        });
      }
    }

    phases.push(
      computeGovernancePipelinePhase({
        overview,
        manifestStatus,
        ledgerStatus
      })
    );
  }

  const orderedPhases = normalizePipelinePhaseOrder(phases);
  const errors = resolvePipelineErrors(failures);
  return {
    phases: orderedPhases,
    overallPercent: computeOverallPipelinePercent(orderedPhases),
    degraded:
      errors.length > 0 || orderedPhases.some((phase) => phase.status === "DEGRADED"),
    errors,
    recommendedPollMs: queryCachePolicy["operations-live"].pollIntervalMs ?? 4_000
  };
}

function ok<T>(data: T): ApiResult<T> {
  return {
    ok: true,
    status: 200,
    data
  };
}

function unauthorized<T>(detail = "Authentication is required."): ApiResult<T> {
  return {
    ok: false,
    status: 401,
    detail,
    error: {
      code: "AUTH_REQUIRED",
      detail,
      retryable: false
    }
  };
}

function notFound<T>(detail = "Fixture route not found."): ApiResult<T> {
  return {
    ok: false,
    status: 404,
    detail,
    error: {
      code: "NOT_FOUND",
      detail,
      retryable: false
    }
  };
}

function validationError<T>(detail: string): ApiResult<T> {
  return {
    ok: false,
    status: 422,
    detail,
    error: {
      code: "VALIDATION",
      detail,
      retryable: false
    }
  };
}

function conflict<T>(detail: string): ApiResult<T> {
  return {
    ok: false,
    status: 409,
    detail,
    error: {
      code: "CONFLICT",
      detail,
      retryable: false
    }
  };
}

function forbidden<T>(detail: string): ApiResult<T> {
  return {
    ok: false,
    status: 403,
    detail,
    error: {
      code: "FORBIDDEN",
      detail,
      retryable: false
    }
  };
}

function hasFixtureAuthToken(token: string | null | undefined): boolean {
  return Boolean(token && token.trim().length > 0);
}

function resolveFixtureSessionProfile(
  token: string | null | undefined
): BrowserFixtureSessionProfile | null {
  if (!token || token.trim().length === 0) {
    return null;
  }
  const normalized = token.trim();
  const directMatch = (Object.entries(FIXTURE_SESSION_TOKENS) as Array<
    [BrowserFixtureSessionProfile, string]
  >).find(([, value]) => value === normalized);
  if (directMatch) {
    return directMatch[0];
  }
  if (normalized === "fixture-session-token-admin") {
    return "admin";
  }
  return null;
}

function resolveFixtureSessionByToken(
  token: string | null | undefined
): SessionResponse | null {
  const profile = resolveFixtureSessionProfile(token);
  if (!profile) {
    return null;
  }
  const session = FIXTURE_SESSION_BY_PROFILE[profile];
  return {
    user: { ...session.user },
    session: { ...session.session }
  };
}

function resolveFixtureProjectRole(
  profile: BrowserFixtureSessionProfile | null
): ProjectRole | null {
  if (profile === "researcher") {
    return "RESEARCHER";
  }
  if (profile === "reviewer") {
    return "REVIEWER";
  }
  if (profile === "project-lead") {
    return "PROJECT_LEAD";
  }
  if (profile === "admin" || profile === "auditor") {
    return "PROJECT_LEAD";
  }
  return null;
}

function canViewGovernanceManifest(profile: BrowserFixtureSessionProfile | null): boolean {
  return (
    profile === "admin" ||
    profile === "auditor" ||
    profile === "project-lead" ||
    profile === "reviewer"
  );
}

function canViewGovernanceLedger(profile: BrowserFixtureSessionProfile | null): boolean {
  return profile === "admin" || profile === "auditor";
}

function canMutateGovernanceLedgerVerification(
  profile: BrowserFixtureSessionProfile | null
): boolean {
  return profile === "admin";
}

function canUseProjectSearch(profile: BrowserFixtureSessionProfile | null): boolean {
  return (
    profile === "admin" ||
    profile === "project-lead" ||
    profile === "researcher" ||
    profile === "reviewer"
  );
}

function canFreezeDerivativeCandidateSnapshot(
  profile: BrowserFixtureSessionProfile | null
): boolean {
  return profile === "admin" || profile === "project-lead" || profile === "reviewer";
}

function canCancelVerificationRun(status: GovernanceArtifactStatus): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

function resolveProjectFixture(projectId: string): ProjectSummary | null {
  const project =
    FIXTURE_PROJECTS.find((candidate) => candidate.id === projectId) ?? null;
  return project ? cloneProject(project) : null;
}

function resolveProjectDocumentsFixture(
  projectId: string
): ProjectDocument[] | null {
  const documents = FIXTURE_DOCUMENTS_BY_PROJECT[projectId];
  if (!documents) {
    return null;
  }
  return documents.map((document) => cloneDocument(document));
}

function resolveProjectDocumentFixture(
  projectId: string,
  documentId: string
): ProjectDocument | null {
  const documents = resolveProjectDocumentsFixture(projectId);
  if (!documents) {
    return null;
  }
  return documents.find((document) => document.id === documentId) ?? null;
}

function resolveProjectDerivativeSnapshotFixture(
  projectId: string,
  derivativeId: string
): ProjectDerivativeSnapshot | null {
  const snapshots = FIXTURE_PROJECT_DERIVATIVES[projectId] ?? [];
  const snapshot =
    snapshots.find((candidate) => candidate.id === derivativeId) ?? null;
  return snapshot ? cloneDerivativeSnapshot(snapshot) : null;
}

function resolveDocumentPagesFixture(
  documentId: string
): ProjectDocumentPageDetail[] {
  const pages = FIXTURE_DOCUMENT_PAGES[documentId] ?? [];
  return pages.map((page) => cloneDocumentPageDetail(page));
}

function asUploadSessionPayload(
  session: FixtureUploadSessionState
): ProjectDocumentUploadSessionStatus {
  return {
    sessionId: session.sessionId,
    importId: session.importId,
    documentId: session.documentId,
    originalFilename: session.originalFilename,
    uploadStatus: session.uploadStatus,
    importStatus: session.importStatus,
    documentStatus: session.documentStatus,
    bytesReceived: session.bytesReceived,
    expectedTotalBytes: session.expectedTotalBytes,
    expectedSha256: session.expectedSha256,
    lastChunkIndex: session.lastChunkIndex,
    nextChunkIndex: session.lastChunkIndex + 1,
    chunkSizeLimitBytes: session.chunkSizeLimitBytes,
    uploadLimitBytes: session.uploadLimitBytes,
    cancelAllowed: session.cancelAllowed,
    failureReason: session.failureReason,
    createdAt: session.createdAt,
    updatedAt: session.updatedAt
  };
}

export function isBrowserRegressionFixtureMode(): boolean {
  return process.env[BROWSER_TEST_MODE_FLAG] === "1";
}

export function getBrowserFixtureSessionToken(
  profile: BrowserFixtureSessionProfile = "admin"
): string {
  return FIXTURE_SESSION_TOKENS[profile];
}

export function resolveBrowserRegressionFixtureSession(
  token: string | null
): SessionResponse | null {
  if (!isBrowserRegressionFixtureMode() || !hasFixtureAuthToken(token)) {
    return null;
  }
  return resolveFixtureSessionByToken(token);
}

export function resolveBrowserRegressionApiResult<T>(options: {
  authToken: string | null | undefined;
  body?: BodyInit | null;
  method: string;
  path: string;
}): ApiResult<T> | null {
  if (!isBrowserRegressionFixtureMode()) {
    return null;
  }

  const method = options.method.toUpperCase();
  const parsedPath = normalizeFixturePath(options.path);
  const pathname = parsedPath.pathname;

  if (method === "GET" && pathname === "/auth/providers") {
    return ok<T>({ ...FIXTURE_AUTH_PROVIDERS } as T);
  }

  if (method === "GET" && pathname === "/auth/session") {
    if (!hasFixtureAuthToken(options.authToken)) {
      return unauthorized<T>();
    }
    const fixtureSession = resolveFixtureSessionByToken(options.authToken);
    if (!fixtureSession) {
      return unauthorized<T>();
    }
    return ok<T>({
      user: { ...fixtureSession.user },
      session: { ...fixtureSession.session }
    } as T);
  }

  if (method === "GET" && pathname === "/healthz") {
    return ok<T>({ ...FIXTURE_HEALTH } as T);
  }

  if (method === "GET" && pathname === "/readyz") {
    return ok<T>({
      ...FIXTURE_READINESS,
      checks: FIXTURE_READINESS.checks.map((check) => ({ ...check }))
    } as T);
  }

  if (!hasFixtureAuthToken(options.authToken)) {
    return unauthorized<T>();
  }
  const fixtureProfile = resolveFixtureSessionProfile(options.authToken);
  if (!fixtureProfile) {
    return unauthorized<T>();
  }

  if (method === "GET" && pathname === "/projects") {
    const payload: ProjectListResponse = {
      items: FIXTURE_PROJECTS.map((project) => cloneProject(project))
    };
    return ok<T>(payload as T);
  }

  const projectWorkspaceMatch = pathname.match(
    /^\/projects\/([^/]+)\/workspace$/
  );
  if (method === "GET" && projectWorkspaceMatch) {
    const project = resolveProjectFixture(projectWorkspaceMatch[1]);
    return project ? ok<T>(project as T) : notFound<T>("Project not found.");
  }

  const projectSummaryMatch = pathname.match(/^\/projects\/([^/]+)$/);
  if (method === "GET" && projectSummaryMatch) {
    const project = resolveProjectFixture(projectSummaryMatch[1]);
    return project ? ok<T>(project as T) : notFound<T>("Project not found.");
  }

  const projectSearchMatch = pathname.match(/^\/projects\/([^/]+)\/search$/);
  if (method === "GET" && projectSearchMatch) {
    const project = resolveProjectFixture(projectSearchMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    if (!canUseProjectSearch(fixtureProfile)) {
      return forbidden<T>("Interactive project search is not available for this role.");
    }

    const activeSearchIndexId = FIXTURE_PROJECT_SEARCH_INDEX_ID[project.id] ?? null;
    if (!activeSearchIndexId) {
      return conflict<T>("No active search index is available for this project.");
    }

    const queryText = parsedPath.searchParams.get("q")?.trim() ?? "";
    if (!queryText) {
      return validationError<T>("q is required.");
    }
    const loweredQuery = queryText.toLocaleLowerCase();
    const documentIdFilter = parsedPath.searchParams.get("documentId")?.trim() ?? "";
    const runIdFilter = parsedPath.searchParams.get("runId")?.trim() ?? "";
    const pageNumberRaw = parsedPath.searchParams.get("pageNumber");
    const pageNumberFilter =
      pageNumberRaw && pageNumberRaw.trim().length > 0
        ? Number.parseInt(pageNumberRaw.trim(), 10)
        : null;
    if (pageNumberRaw && pageNumberRaw.trim().length > 0) {
      if (!Number.isFinite(pageNumberFilter) || (pageNumberFilter ?? 0) < 1) {
        return validationError<T>("pageNumber must be greater than or equal to 1.");
      }
    }
    const cursor = parseNonNegativeIntParam(parsedPath.searchParams.get("cursor"), 0);
    const limit = Math.max(
      1,
      Math.min(100, parsePositiveIntParam(parsedPath.searchParams.get("limit"), 25))
    );

    const baseHits = (FIXTURE_PROJECT_SEARCH_HITS[project.id] ?? []).filter(
      (hit) => hit.searchIndexId === activeSearchIndexId
    );
    const filtered = baseHits
      .filter((hit) => hit.searchText.toLocaleLowerCase().includes(loweredQuery))
      .filter((hit) => (documentIdFilter ? hit.documentId === documentIdFilter : true))
      .filter((hit) => (runIdFilter ? hit.runId === runIdFilter : true))
      .filter((hit) =>
        pageNumberFilter !== null && Number.isFinite(pageNumberFilter)
          ? hit.pageNumber === pageNumberFilter
          : true
      )
      .sort((left, right) => {
        if (left.pageNumber !== right.pageNumber) {
          return left.pageNumber - right.pageNumber;
        }
        if (left.documentId !== right.documentId) {
          return left.documentId.localeCompare(right.documentId);
        }
        if (left.runId !== right.runId) {
          return left.runId.localeCompare(right.runId);
        }
        return left.searchDocumentId.localeCompare(right.searchDocumentId);
      });

    const window = filtered.slice(cursor, cursor + limit + 1);
    const items = window.slice(0, limit).map((hit) => cloneSearchHit(hit));
    const nextCursor = window.length > limit ? cursor + limit : null;
    const payload: ProjectSearchResponse = {
      searchIndexId: activeSearchIndexId,
      items,
      nextCursor
    };
    return ok<T>(payload as T);
  }

  const projectEntitiesMatch = pathname.match(/^\/projects\/([^/]+)\/entities$/);
  if (method === "GET" && projectEntitiesMatch) {
    const project = resolveProjectFixture(projectEntitiesMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    if (!canUseProjectSearch(fixtureProfile)) {
      return forbidden<T>("Interactive entity workspace is not available for this role.");
    }

    const activeEntityIndexId = FIXTURE_PROJECT_ENTITY_INDEX_ID[project.id] ?? null;
    if (!activeEntityIndexId) {
      return conflict<T>("No active entity index is available for this project.");
    }

    const queryText = parsedPath.searchParams.get("q")?.trim().toLocaleLowerCase() ?? "";
    const entityTypeFilter = parsedPath.searchParams.get("entityType")?.trim().toUpperCase() ?? "";
    if (
      entityTypeFilter &&
      !["PERSON", "PLACE", "ORGANISATION", "DATE"].includes(entityTypeFilter)
    ) {
      return validationError<T>(
        "entityType must be one of PERSON, PLACE, ORGANISATION, DATE."
      );
    }

    const cursor = parseNonNegativeIntParam(parsedPath.searchParams.get("cursor"), 0);
    const limit = Math.max(
      1,
      Math.min(100, parsePositiveIntParam(parsedPath.searchParams.get("limit"), 25))
    );

    const base = (FIXTURE_PROJECT_ENTITIES[project.id] ?? []).filter(
      (entity) => entity.entityIndexId === activeEntityIndexId
    );
    const filtered = base
      .filter((entity) =>
        queryText
          ? entity.displayValue.toLocaleLowerCase().includes(queryText) ||
            entity.canonicalValue.toLocaleLowerCase().includes(queryText)
          : true
      )
      .filter((entity) =>
        entityTypeFilter ? entity.entityType === entityTypeFilter : true
      )
      .sort((left, right) => {
        if (left.entityType !== right.entityType) {
          return left.entityType.localeCompare(right.entityType);
        }
        if (left.canonicalValue !== right.canonicalValue) {
          return left.canonicalValue.localeCompare(right.canonicalValue);
        }
        return left.id.localeCompare(right.id);
      });

    const window = filtered.slice(cursor, cursor + limit + 1);
    const items = window.slice(0, limit).map((entity) => cloneControlledEntity(entity));
    const nextCursor = window.length > limit ? cursor + limit : null;
    const payload: ProjectEntityListResponse = {
      entityIndexId: activeEntityIndexId,
      items,
      nextCursor
    };
    return ok<T>(payload as T);
  }

  const projectEntityDetailMatch = pathname.match(/^\/projects\/([^/]+)\/entities\/([^/]+)$/);
  if (method === "GET" && projectEntityDetailMatch) {
    const project = resolveProjectFixture(projectEntityDetailMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    if (!canUseProjectSearch(fixtureProfile)) {
      return forbidden<T>("Interactive entity workspace is not available for this role.");
    }

    const activeEntityIndexId = FIXTURE_PROJECT_ENTITY_INDEX_ID[project.id] ?? null;
    if (!activeEntityIndexId) {
      return conflict<T>("No active entity index is available for this project.");
    }

    const entityId = projectEntityDetailMatch[2];
    const entity =
      (FIXTURE_PROJECT_ENTITIES[project.id] ?? []).find(
        (candidate) =>
          candidate.entityIndexId === activeEntityIndexId && candidate.id === entityId
      ) ?? null;
    if (!entity) {
      return notFound<T>("Entity was not found in the active entity index.");
    }

    const payload: ProjectEntityDetailResponse = {
      entityIndexId: activeEntityIndexId,
      entity: cloneControlledEntity(entity)
    };
    return ok<T>(payload as T);
  }

  const projectEntityOccurrencesMatch = pathname.match(
    /^\/projects\/([^/]+)\/entities\/([^/]+)\/occurrences$/
  );
  if (method === "GET" && projectEntityOccurrencesMatch) {
    const project = resolveProjectFixture(projectEntityOccurrencesMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    if (!canUseProjectSearch(fixtureProfile)) {
      return forbidden<T>("Interactive entity workspace is not available for this role.");
    }

    const activeEntityIndexId = FIXTURE_PROJECT_ENTITY_INDEX_ID[project.id] ?? null;
    if (!activeEntityIndexId) {
      return conflict<T>("No active entity index is available for this project.");
    }

    const entityId = projectEntityOccurrencesMatch[2];
    const entity =
      (FIXTURE_PROJECT_ENTITIES[project.id] ?? []).find(
        (candidate) =>
          candidate.entityIndexId === activeEntityIndexId && candidate.id === entityId
      ) ?? null;
    if (!entity) {
      return notFound<T>("Entity was not found in the active entity index.");
    }

    const cursor = parseNonNegativeIntParam(parsedPath.searchParams.get("cursor"), 0);
    const limit = Math.max(
      1,
      Math.min(100, parsePositiveIntParam(parsedPath.searchParams.get("limit"), 25))
    );
    const filtered = (FIXTURE_PROJECT_ENTITY_OCCURRENCES[project.id] ?? [])
      .filter(
        (occurrence) =>
          occurrence.entityIndexId === activeEntityIndexId &&
          occurrence.entityId === entityId
      )
      .sort((left, right) => {
        if (left.pageNumber !== right.pageNumber) {
          return left.pageNumber - right.pageNumber;
        }
        if (left.documentId !== right.documentId) {
          return left.documentId.localeCompare(right.documentId);
        }
        if (left.runId !== right.runId) {
          return left.runId.localeCompare(right.runId);
        }
        return left.id.localeCompare(right.id);
      });
    const window = filtered.slice(cursor, cursor + limit + 1);
    const items = window.slice(0, limit).map((occurrence) => cloneEntityOccurrence(occurrence));
    const nextCursor = window.length > limit ? cursor + limit : null;

    const payload: ProjectEntityOccurrencesResponse = {
      entityIndexId: activeEntityIndexId,
      entity: cloneControlledEntity(entity),
      items,
      nextCursor
    };
    return ok<T>(payload as T);
  }

  const projectDerivativesMatch = pathname.match(/^\/projects\/([^/]+)\/derivatives$/);
  if (method === "GET" && projectDerivativesMatch) {
    const project = resolveProjectFixture(projectDerivativesMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    if (!canUseProjectSearch(fixtureProfile)) {
      return forbidden<T>("Safeguarded derivative previews are not available for this role.");
    }

    const rawScope = parsedPath.searchParams.get("scope")?.trim().toLowerCase() ?? "active";
    if (rawScope !== "active" && rawScope !== "historical") {
      return validationError<T>("scope must be one of: active, historical.");
    }
    const scope = rawScope as "active" | "historical";
    const activeDerivativeIndexId = FIXTURE_PROJECT_DERIVATIVE_INDEX_ID[project.id] ?? null;
    if (scope === "active" && !activeDerivativeIndexId) {
      return conflict<T>("No active derivative index is available for this project.");
    }

    const snapshots = FIXTURE_PROJECT_DERIVATIVES[project.id] ?? [];
    const filtered =
      scope === "active"
        ? snapshots.filter(
            (snapshot) => snapshot.derivativeIndexId === activeDerivativeIndexId
          )
        : snapshots.filter(
            (snapshot) =>
              snapshot.status === "SUCCEEDED" &&
              snapshot.supersededByDerivativeSnapshotId === null
          );
    const items = filtered
      .map((snapshot) => ({
        ...cloneDerivativeSnapshot(snapshot),
        isActiveGeneration: snapshot.derivativeIndexId === activeDerivativeIndexId
      }))
      .sort((left, right) => right.createdAt.localeCompare(left.createdAt));
    const payload: ProjectDerivativeListResponse = {
      scope,
      activeDerivativeIndexId,
      items
    };
    return ok<T>(payload as T);
  }

  const projectDerivativeStatusMatch = pathname.match(
    /^\/projects\/([^/]+)\/derivatives\/([^/]+)\/status$/
  );
  if (method === "GET" && projectDerivativeStatusMatch) {
    const project = resolveProjectFixture(projectDerivativeStatusMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    if (!canUseProjectSearch(fixtureProfile)) {
      return forbidden<T>("Safeguarded derivative previews are not available for this role.");
    }
    const derivativeId = projectDerivativeStatusMatch[2];
    const snapshot = resolveProjectDerivativeSnapshotFixture(project.id, derivativeId);
    if (!snapshot) {
      return notFound<T>("Derivative snapshot was not found.");
    }
    const payload: ProjectDerivativeStatusResponse = {
      derivativeId: snapshot.id,
      derivativeIndexId: snapshot.derivativeIndexId,
      status: snapshot.status,
      startedAt: snapshot.startedAt,
      finishedAt: snapshot.finishedAt,
      failureReason: snapshot.failureReason,
      candidateSnapshotId: snapshot.candidateSnapshotId
    };
    return ok<T>(payload as T);
  }

  const projectDerivativePreviewMatch = pathname.match(
    /^\/projects\/([^/]+)\/derivatives\/([^/]+)\/preview$/
  );
  if (method === "GET" && projectDerivativePreviewMatch) {
    const project = resolveProjectFixture(projectDerivativePreviewMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    if (!canUseProjectSearch(fixtureProfile)) {
      return forbidden<T>("Safeguarded derivative previews are not available for this role.");
    }
    const derivativeId = projectDerivativePreviewMatch[2];
    const snapshot = resolveProjectDerivativeSnapshotFixture(project.id, derivativeId);
    if (!snapshot) {
      return notFound<T>("Derivative snapshot was not found.");
    }
    const rows = (FIXTURE_PROJECT_DERIVATIVE_PREVIEW_ROWS[snapshot.id] ?? []).map((row) =>
      cloneDerivativePreviewRow(row)
    );
    const payload: ProjectDerivativePreviewResponse = {
      derivativeIndexId: snapshot.derivativeIndexId,
      derivativeSnapshotId: snapshot.id,
      derivativeKind: snapshot.derivativeKind,
      status: snapshot.status,
      rows,
      previewCount: rows.length
    };
    return ok<T>(payload as T);
  }

  const projectDerivativeCandidateFreezeMatch = pathname.match(
    /^\/projects\/([^/]+)\/derivatives\/([^/]+)\/candidate-snapshots$/
  );
  if (method === "POST" && projectDerivativeCandidateFreezeMatch) {
    const project = resolveProjectFixture(projectDerivativeCandidateFreezeMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    if (!canFreezeDerivativeCandidateSnapshot(fixtureProfile)) {
      return forbidden<T>(
        "Candidate freeze is restricted to project leads, reviewers, or administrators."
      );
    }
    const derivativeId = projectDerivativeCandidateFreezeMatch[2];
    const snapshots = FIXTURE_PROJECT_DERIVATIVES[project.id] ?? [];
    const snapshotIndex = snapshots.findIndex((snapshot) => snapshot.id === derivativeId);
    if (snapshotIndex < 0) {
      return notFound<T>("Derivative snapshot was not found.");
    }
    const snapshot = snapshots[snapshotIndex];
    if (snapshot.status !== "SUCCEEDED") {
      return conflict<T>(
        "Candidate freeze is allowed only for SUCCEEDED derivative snapshots."
      );
    }
    if (snapshot.supersededByDerivativeSnapshotId) {
      return conflict<T>("Superseded derivative snapshots cannot be frozen.");
    }
    if (!snapshot.storageKey || !snapshot.snapshotSha256) {
      return conflict<T>(
        "Candidate freeze is blocked until storageKey and snapshotSha256 are available."
      );
    }
    const rows = FIXTURE_PROJECT_DERIVATIVE_PREVIEW_ROWS[snapshot.id] ?? [];
    if (rows.length < 1) {
      return conflict<T>(
        "Candidate freeze is blocked until derivative preview rows are materialized."
      );
    }

    const candidateSnapshotId =
      snapshot.candidateSnapshotId ?? `candidate-derivative-${snapshot.id.replace(/^dersnap-/, "")}`;
    const created = !snapshot.candidateSnapshotId;
    if (created) {
      snapshots[snapshotIndex] = {
        ...snapshot,
        candidateSnapshotId
      };
    }

    const payload: ProjectDerivativeCandidateSnapshotCreateResponse = {
      derivativeId: snapshot.id,
      derivativeIndexId: snapshot.derivativeIndexId,
      candidateSnapshotId,
      created,
      candidate: {
        id: candidateSnapshotId,
        candidateKind: "SAFEGUARDED_DERIVATIVE",
        sourcePhase: "PHASE10",
        sourceArtifactKind: "DERIVATIVE_SNAPSHOT",
        sourceArtifactId: snapshot.id,
        createdAt: FIXTURE_DERIVATIVE_FREEZE_TIMESTAMP
      }
    };
    return {
      ok: true,
      status: 201,
      data: payload as T
    };
  }

  const projectDerivativeDetailMatch = pathname.match(
    /^\/projects\/([^/]+)\/derivatives\/([^/]+)$/
  );
  if (method === "GET" && projectDerivativeDetailMatch) {
    const project = resolveProjectFixture(projectDerivativeDetailMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    if (!canUseProjectSearch(fixtureProfile)) {
      return forbidden<T>("Safeguarded derivative previews are not available for this role.");
    }
    const derivativeId = projectDerivativeDetailMatch[2];
    const snapshot = resolveProjectDerivativeSnapshotFixture(project.id, derivativeId);
    if (!snapshot) {
      return notFound<T>("Derivative snapshot was not found.");
    }
    const payload: ProjectDerivativeDetailResponse = {
      derivative: {
        ...snapshot,
        isActiveGeneration: false
      }
    };
    return ok<T>(payload as T);
  }

  const projectSearchOpenMatch = pathname.match(
    /^\/projects\/([^/]+)\/search\/([^/]+)\/open$/
  );
  if (method === "POST" && projectSearchOpenMatch) {
    const project = resolveProjectFixture(projectSearchOpenMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    if (!canUseProjectSearch(fixtureProfile)) {
      return forbidden<T>("Interactive project search is not available for this role.");
    }

    const activeSearchIndexId = FIXTURE_PROJECT_SEARCH_INDEX_ID[project.id] ?? null;
    if (!activeSearchIndexId) {
      return conflict<T>("No active search index is available for this project.");
    }

    const searchDocumentId = projectSearchOpenMatch[2];
    const hit =
      (FIXTURE_PROJECT_SEARCH_HITS[project.id] ?? []).find(
        (candidate) =>
          candidate.searchIndexId === activeSearchIndexId &&
          candidate.searchDocumentId === searchDocumentId
      ) ?? null;
    if (!hit) {
      return notFound<T>("Search result was not found in the active search index.");
    }

    const payload: ProjectSearchResultOpenResponse = {
      searchIndexId: hit.searchIndexId,
      searchDocumentId: hit.searchDocumentId,
      documentId: hit.documentId,
      runId: hit.runId,
      pageNumber: hit.pageNumber,
      lineId: hit.lineId,
      tokenId: hit.tokenId,
      sourceKind: hit.sourceKind,
      sourceRefId: hit.sourceRefId,
      workspacePath: buildFixtureSearchWorkspacePath(project.id, hit)
    };
    return ok<T>(payload as T);
  }

  const projectJobsSummaryMatch = pathname.match(
    /^\/projects\/([^/]+)\/jobs\/summary$/
  );
  if (method === "GET" && projectJobsSummaryMatch) {
    const project = resolveProjectFixture(projectJobsSummaryMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    return ok<T>({ ...FIXTURE_PROJECT_JOBS_SUMMARY } as T);
  }

  const projectJobsMatch = pathname.match(/^\/projects\/([^/]+)\/jobs$/);
  if (method === "GET" && projectJobsMatch) {
    const project = resolveProjectFixture(projectJobsMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    return ok<T>({
      items: FIXTURE_PROJECT_JOBS.items.map((job) => ({ ...job })),
      nextCursor: FIXTURE_PROJECT_JOBS.nextCursor
    } as T);
  }

  const projectDocumentsMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents$/
  );
  if (method === "GET" && projectDocumentsMatch) {
    const project = resolveProjectFixture(projectDocumentsMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const documents = resolveProjectDocumentsFixture(project.id) ?? [];
    const payload: ProjectDocumentListResponse = {
      items: documents,
      nextCursor: null
    };
    return ok<T>(payload as T);
  }

  const projectDocumentTimelineMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/timeline$/
  );
  if (method === "GET" && projectDocumentTimelineMatch) {
    const project = resolveProjectFixture(projectDocumentTimelineMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentTimelineMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const timelineItems = FIXTURE_DOCUMENT_TIMELINES[document.id] ?? [];
    return ok<T>({
      items: timelineItems.map((item) => ({ ...item }))
    } as T);
  }

  const createUploadSessionMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/import-sessions$/
  );
  if (method === "POST" && createUploadSessionMatch) {
    const projectId = createUploadSessionMatch[1];
    const project = resolveProjectFixture(projectId);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const body = parseFixtureJsonBody(
      options.body
    ) as CreateDocumentUploadSessionRequest | null;
    const originalFilename =
      body && typeof body.originalFilename === "string"
        ? body.originalFilename.trim()
        : "";
    if (!originalFilename) {
      return validationError<T>("originalFilename is required.");
    }

    fixtureUploadSessionSequence += 1;
    const sequence = fixtureUploadSessionSequence;
    const now = "2026-03-13T10:03:00.000Z";
    const sessionId = `session-fixture-${sequence}`;
    const importId = `import-fixture-${sequence}`;
    const documentId = `doc-fixture-upload-${sequence}`;
    const uploadLimitBytes = 16 * 1024 * 1024;
    const chunkSizeLimitBytes = 1024 * 1024;

    const session: FixtureUploadSessionState = {
      sessionId,
      importId,
      documentId,
      projectId,
      originalFilename,
      uploadStatus: "ACTIVE",
      importStatus: "UPLOADING",
      documentStatus: "UPLOADING",
      bytesReceived: 0,
      expectedTotalBytes:
        body && typeof body.expectedTotalBytes === "number"
          ? body.expectedTotalBytes
          : null,
      expectedSha256:
        body && typeof body.expectedSha256 === "string"
          ? body.expectedSha256
          : null,
      lastChunkIndex: -1,
      chunkSizeLimitBytes,
      uploadLimitBytes,
      cancelAllowed: true,
      failureReason: null,
      createdAt: now,
      updatedAt: now,
      chunks: new Map<number, number>(),
      interruptChunkIndex:
        body &&
        typeof body.expectedTotalBytes === "number" &&
        body.expectedTotalBytes > chunkSizeLimitBytes
          ? 1
          : null
    };
    FIXTURE_UPLOAD_SESSIONS.set(sessionId, session);

    const projectDocuments = FIXTURE_DOCUMENTS_BY_PROJECT[projectId];
    if (projectDocuments) {
      projectDocuments.unshift({
        id: documentId,
        projectId,
        originalFilename,
        storedFilename: null,
        contentTypeDetected: null,
        bytes: null,
        sha256: null,
        pageCount: null,
        status: "UPLOADING",
        createdBy: FIXTURE_SESSION.user.id,
        createdAt: now,
        updatedAt: now
      });
      FIXTURE_DOCUMENT_TIMELINES[documentId] = [];
      FIXTURE_DOCUMENT_PAGES[documentId] = [];
    }

    return ok<T>(asUploadSessionPayload(session) as T);
  }

  const uploadSessionMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/import-sessions\/([^/]+)$/
  );
  if (method === "GET" && uploadSessionMatch) {
    const projectId = uploadSessionMatch[1];
    const project = resolveProjectFixture(projectId);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const sessionId = uploadSessionMatch[2];
    const session = FIXTURE_UPLOAD_SESSIONS.get(sessionId);
    if (!session || session.projectId !== projectId) {
      return notFound<T>("Upload session not found.");
    }
    return ok<T>(asUploadSessionPayload(session) as T);
  }

  const uploadSessionChunkMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/import-sessions\/([^/]+)\/chunks$/
  );
  if (method === "POST" && uploadSessionChunkMatch) {
    const projectId = uploadSessionChunkMatch[1];
    const project = resolveProjectFixture(projectId);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const sessionId = uploadSessionChunkMatch[2];
    const session = FIXTURE_UPLOAD_SESSIONS.get(sessionId);
    if (!session || session.projectId !== projectId) {
      return notFound<T>("Upload session not found.");
    }
    if (session.uploadStatus !== "ACTIVE") {
      return conflict<T>(`Upload session is ${session.uploadStatus}.`);
    }
    const chunkIndexRaw = parsedPath.searchParams.get("chunkIndex");
    const chunkIndex = Number(chunkIndexRaw);
    if (!Number.isInteger(chunkIndex) || chunkIndex < 0) {
      return validationError<T>("chunkIndex must be a non-negative integer.");
    }
    if (chunkIndex > session.lastChunkIndex + 1) {
      return conflict<T>(
        `Chunk index gap detected. Resume from chunk ${session.lastChunkIndex + 1}.`
      );
    }
    if (session.interruptChunkIndex === chunkIndex) {
      session.interruptChunkIndex = null;
      session.updatedAt = "2026-03-13T10:03:09.000Z";
      return conflict<T>(
        "Upload was interrupted. Resume from the last acknowledged chunk."
      );
    }

    let chunkSize = 1024;
    if (typeof FormData !== "undefined" && options.body instanceof FormData) {
      const payload = options.body.get("file");
      if (typeof File !== "undefined" && payload instanceof File) {
        chunkSize = payload.size;
      }
    }
    if (chunkSize < 1) {
      return validationError<T>("Chunk payload is empty.");
    }
    if (chunkSize > session.chunkSizeLimitBytes) {
      return validationError<T>("Chunk exceeds configured size limit.");
    }
    if (!session.chunks.has(chunkIndex)) {
      session.chunks.set(chunkIndex, chunkSize);
      session.bytesReceived += chunkSize;
      session.lastChunkIndex = Math.max(session.lastChunkIndex, chunkIndex);
      session.updatedAt = "2026-03-13T10:03:10.000Z";
    }
    return ok<T>(asUploadSessionPayload(session) as T);
  }

  const uploadSessionCompleteMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/import-sessions\/([^/]+)\/complete$/
  );
  if (method === "POST" && uploadSessionCompleteMatch) {
    const projectId = uploadSessionCompleteMatch[1];
    const project = resolveProjectFixture(projectId);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const sessionId = uploadSessionCompleteMatch[2];
    const session = FIXTURE_UPLOAD_SESSIONS.get(sessionId);
    if (!session || session.projectId !== projectId) {
      return notFound<T>("Upload session not found.");
    }
    if (session.uploadStatus !== "ACTIVE") {
      return conflict<T>(`Upload session is ${session.uploadStatus}.`);
    }
    if (session.lastChunkIndex < 0 || session.bytesReceived < 1) {
      return conflict<T>("Upload session has no persisted chunks.");
    }
    if (
      session.expectedTotalBytes !== null &&
      session.expectedTotalBytes !== session.bytesReceived
    ) {
      return conflict<T>(
        "Upload session byte count does not match expectedTotalBytes."
      );
    }
    session.uploadStatus = "COMPLETED";
    session.importStatus = "QUEUED";
    session.documentStatus = "QUEUED";
    session.cancelAllowed = false;
    session.updatedAt = "2026-03-13T10:03:20.000Z";
    const projectDocuments = FIXTURE_DOCUMENTS_BY_PROJECT[projectId];
    if (projectDocuments) {
      const target = projectDocuments.find(
        (document) => document.id === session.documentId
      );
      if (target) {
        target.status = "QUEUED";
        target.bytes = session.bytesReceived;
        target.updatedAt = session.updatedAt;
      }
    }
    return ok<T>(asUploadSessionPayload(session) as T);
  }

  const uploadSessionCancelMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/import-sessions\/([^/]+)\/cancel$/
  );
  if (method === "POST" && uploadSessionCancelMatch) {
    const projectId = uploadSessionCancelMatch[1];
    const project = resolveProjectFixture(projectId);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const sessionId = uploadSessionCancelMatch[2];
    const session = FIXTURE_UPLOAD_SESSIONS.get(sessionId);
    if (!session || session.projectId !== projectId) {
      return notFound<T>("Upload session not found.");
    }
    if (["FAILED", "CANCELED", "COMPLETED"].includes(session.uploadStatus)) {
      return conflict<T>(`Upload session is already ${session.uploadStatus}.`);
    }
    session.uploadStatus = "CANCELED";
    session.importStatus = "CANCELED";
    session.documentStatus = "CANCELED";
    session.cancelAllowed = false;
    session.updatedAt = "2026-03-13T10:03:30.000Z";
    const projectDocuments = FIXTURE_DOCUMENTS_BY_PROJECT[projectId];
    if (projectDocuments) {
      const target = projectDocuments.find(
        (document) => document.id === session.documentId
      );
      if (target) {
        target.status = "CANCELED";
        target.updatedAt = session.updatedAt;
      }
    }
    return ok<T>(asUploadSessionPayload(session) as T);
  }

  const projectDocumentProcessingRunsMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/processing-runs$/
  );
  if (method === "GET" && projectDocumentProcessingRunsMatch) {
    const project = resolveProjectFixture(
      projectDocumentProcessingRunsMatch[1]
    );
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentProcessingRunsMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const timelineItems = FIXTURE_DOCUMENT_TIMELINES[document.id] ?? [];
    return ok<T>({
      items: timelineItems.map((item) => ({ ...item }))
    } as T);
  }

  const projectDocumentProcessingRunDetailMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/processing-runs\/([^/]+)$/
  );
  if (method === "GET" && projectDocumentProcessingRunDetailMatch) {
    const project = resolveProjectFixture(
      projectDocumentProcessingRunDetailMatch[1]
    );
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentProcessingRunDetailMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentProcessingRunDetailMatch[3];
    const run = (FIXTURE_DOCUMENT_TIMELINES[document.id] ?? []).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Processing run not found.");
    }
    return ok<T>({
      ...run,
      documentId: document.id,
      active: run.status === "QUEUED" || run.status === "RUNNING"
    } as T);
  }

  const projectDocumentProcessingRunStatusMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/processing-runs\/([^/]+)\/status$/
  );
  if (method === "GET" && projectDocumentProcessingRunStatusMatch) {
    const project = resolveProjectFixture(
      projectDocumentProcessingRunStatusMatch[1]
    );
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentProcessingRunStatusMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentProcessingRunStatusMatch[3];
    const run = (FIXTURE_DOCUMENT_TIMELINES[document.id] ?? []).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Processing run not found.");
    }
    const payload: DocumentProcessingRunStatusResponse = {
      runId: run.id,
      documentId: document.id,
      attemptNumber: run.attemptNumber,
      runKind: run.runKind,
      supersedesProcessingRunId: run.supersedesProcessingRunId,
      supersededByProcessingRunId: run.supersededByProcessingRunId,
      status: run.status,
      failureReason: run.failureReason,
      startedAt: run.startedAt,
      finishedAt: run.finishedAt,
      canceledAt: run.canceledAt,
      createdAt: run.createdAt,
      active: run.status === "QUEUED" || run.status === "RUNNING"
    };
    return ok<T>(payload as T);
  }

  const projectDocumentPipelineStatusMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/pipeline\/status$/
  );
  if (method === "GET" && projectDocumentPipelineStatusMatch) {
    const project = resolveProjectFixture(projectDocumentPipelineStatusMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPipelineStatusMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }

    const payload = buildPipelineStatusFixture({
      document,
      fixtureProfile,
      projectId: project.id
    });
    return ok<T>(payload as T);
  }

  const projectDocumentGovernanceOverviewMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/overview$/
  );
  if (method === "GET" && projectDocumentGovernanceOverviewMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceOverviewMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceOverviewMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    if (!canViewGovernanceManifest(fixtureProfile)) {
      return forbidden<T>("Governance manifest access requires project lead, reviewer, admin, or auditor roles.");
    }
    return ok<T>(cloneJson(FIXTURE_GOVERNANCE_OVERVIEW) as T);
  }

  const projectDocumentGovernanceRunsMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs$/
  );
  if (method === "GET" && projectDocumentGovernanceRunsMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunsMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(project.id, projectDocumentGovernanceRunsMatch[2]);
    if (!document) {
      return notFound<T>("Document not found.");
    }
    if (!canViewGovernanceManifest(fixtureProfile)) {
      return forbidden<T>("Governance manifest access requires project lead, reviewer, admin, or auditor roles.");
    }
    return ok<T>(cloneJson(FIXTURE_GOVERNANCE_RUNS) as T);
  }

  const projectDocumentGovernanceRunOverviewMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/overview$/
  );
  if (method === "GET" && projectDocumentGovernanceRunOverviewMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunOverviewMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunOverviewMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunOverviewMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceManifest(fixtureProfile)) {
      return forbidden<T>("Governance manifest access requires project lead, reviewer, admin, or auditor roles.");
    }
    return ok<T>(cloneJson(FIXTURE_GOVERNANCE_RUN_OVERVIEW) as T);
  }

  const projectDocumentGovernanceRunEventsMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/events$/
  );
  if (method === "GET" && projectDocumentGovernanceRunEventsMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunEventsMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunEventsMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunEventsMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceManifest(fixtureProfile)) {
      return forbidden<T>("Governance manifest access requires project lead, reviewer, admin, or auditor roles.");
    }
    const payload: DocumentGovernanceRunEventsResponse = {
      runId,
      items: FIXTURE_GOVERNANCE_EVENTS.map((event) => cloneJson(event))
    };
    return ok<T>(payload as T);
  }

  const projectDocumentGovernanceRunManifestStatusMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/manifest\/status$/
  );
  if (method === "GET" && projectDocumentGovernanceRunManifestStatusMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunManifestStatusMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunManifestStatusMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunManifestStatusMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceManifest(fixtureProfile)) {
      return forbidden<T>("Governance manifest access requires project lead, reviewer, admin, or auditor roles.");
    }
    return ok<T>(cloneJson(FIXTURE_GOVERNANCE_MANIFEST_STATUS_RESPONSE) as T);
  }

  const projectDocumentGovernanceRunManifestEntriesMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/manifest\/entries$/
  );
  if (method === "GET" && projectDocumentGovernanceRunManifestEntriesMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunManifestEntriesMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunManifestEntriesMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunManifestEntriesMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceManifest(fixtureProfile)) {
      return forbidden<T>("Governance manifest access requires project lead, reviewer, admin, or auditor roles.");
    }
    const sliced = resolveGovernanceManifestEntriesFixture(parsedPath);
    const payload: DocumentGovernanceManifestEntriesResponse = {
      runId,
      status: "SUCCEEDED",
      manifestId: "gov-manifest-attempt-001",
      manifestSha256: "fixture-governance-manifest-sha-001",
      sourceReviewSnapshotSha256: "approved-fixture-sha-base-001",
      totalCount: sliced.totalCount,
      nextCursor: sliced.nextCursor,
      internalOnly: true,
      exportApproved: false,
      notExportApproved: true,
      items: sliced.items
    };
    return ok<T>(payload as T);
  }

  const projectDocumentGovernanceRunManifestHashMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/manifest\/hash$/
  );
  if (method === "GET" && projectDocumentGovernanceRunManifestHashMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunManifestHashMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunManifestHashMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunManifestHashMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceManifest(fixtureProfile)) {
      return forbidden<T>("Governance manifest access requires project lead, reviewer, admin, or auditor roles.");
    }
    return ok<T>(cloneJson(FIXTURE_GOVERNANCE_MANIFEST_HASH_RESPONSE) as T);
  }

  const projectDocumentGovernanceRunManifestMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/manifest$/
  );
  if (method === "GET" && projectDocumentGovernanceRunManifestMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunManifestMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunManifestMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunManifestMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceManifest(fixtureProfile)) {
      return forbidden<T>("Governance manifest access requires project lead, reviewer, admin, or auditor roles.");
    }
    return ok<T>(cloneJson(FIXTURE_GOVERNANCE_MANIFEST_RESPONSE) as T);
  }

  const projectDocumentGovernanceRunLedgerVerifyStatusMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/ledger\/verify\/status$/
  );
  if (method === "GET" && projectDocumentGovernanceRunLedgerVerifyStatusMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunLedgerVerifyStatusMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunLedgerVerifyStatusMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunLedgerVerifyStatusMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceLedger(fixtureProfile)) {
      return forbidden<T>("Evidence-ledger routes are restricted to administrator or auditor roles.");
    }
    const latestAttempt = FIXTURE_GOVERNANCE_VERIFY_RUNS[0];
    const latestCompletedAttempt =
      FIXTURE_GOVERNANCE_VERIFY_RUNS.find((item) => item.status === "SUCCEEDED") ?? null;
    const payload: DocumentGovernanceLedgerVerifyStatusResponse = {
      runId,
      verificationStatus: "VALID",
      attemptCount: FIXTURE_GOVERNANCE_VERIFY_RUNS.length,
      latestAttempt: latestAttempt ? cloneJson(latestAttempt) : null,
      latestCompletedAttempt: latestCompletedAttempt ? cloneJson(latestCompletedAttempt) : null,
      readyLedgerId: "gov-ledger-attempt-001",
      latestLedgerSha256: "fixture-governance-ledger-sha-001",
      lastVerifiedAt: "2026-03-13T09:59:30.000Z"
    };
    return ok<T>(payload as T);
  }

  const projectDocumentGovernanceRunLedgerVerifyRunsMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/ledger\/verify\/runs$/
  );
  if (method === "GET" && projectDocumentGovernanceRunLedgerVerifyRunsMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunLedgerVerifyRunsMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunLedgerVerifyRunsMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunLedgerVerifyRunsMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceLedger(fixtureProfile)) {
      return forbidden<T>("Evidence-ledger routes are restricted to administrator or auditor roles.");
    }
    const payload: DocumentGovernanceLedgerVerifyRunsResponse = {
      runId,
      verificationStatus: "VALID",
      items: FIXTURE_GOVERNANCE_VERIFY_RUNS.map((item) => cloneJson(item))
    };
    return ok<T>(payload as T);
  }

  const projectDocumentGovernanceRunLedgerVerifyRunStatusMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/ledger\/verify\/([^/]+)\/status$/
  );
  if (method === "GET" && projectDocumentGovernanceRunLedgerVerifyRunStatusMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunLedgerVerifyRunStatusMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunLedgerVerifyRunStatusMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunLedgerVerifyRunStatusMatch[3];
    const verificationRunId = projectDocumentGovernanceRunLedgerVerifyRunStatusMatch[4];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceLedger(fixtureProfile)) {
      return forbidden<T>("Evidence-ledger routes are restricted to administrator or auditor roles.");
    }
    const attempt =
      FIXTURE_GOVERNANCE_VERIFY_RUNS.find((item) => item.id === verificationRunId) ?? null;
    if (!attempt) {
      return notFound<T>("Verification attempt not found.");
    }
    const payload: DocumentGovernanceLedgerVerifyDetailResponse = {
      runId,
      verificationStatus: "VALID",
      attempt: cloneJson(attempt)
    };
    return ok<T>(payload as T);
  }

  const projectDocumentGovernanceRunLedgerVerifyRunMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/ledger\/verify\/([^/]+)$/
  );
  if (method === "GET" && projectDocumentGovernanceRunLedgerVerifyRunMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunLedgerVerifyRunMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunLedgerVerifyRunMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunLedgerVerifyRunMatch[3];
    const verificationRunId = projectDocumentGovernanceRunLedgerVerifyRunMatch[4];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceLedger(fixtureProfile)) {
      return forbidden<T>("Evidence-ledger routes are restricted to administrator or auditor roles.");
    }
    const attempt =
      FIXTURE_GOVERNANCE_VERIFY_RUNS.find((item) => item.id === verificationRunId) ?? null;
    if (!attempt) {
      return notFound<T>("Verification attempt not found.");
    }
    const payload: DocumentGovernanceLedgerVerifyDetailResponse = {
      runId,
      verificationStatus: "VALID",
      attempt: cloneJson(attempt)
    };
    return ok<T>(payload as T);
  }

  const projectDocumentGovernanceRunLedgerVerifyCancelMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/ledger\/verify\/([^/]+)\/cancel$/
  );
  if (method === "POST" && projectDocumentGovernanceRunLedgerVerifyCancelMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunLedgerVerifyCancelMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunLedgerVerifyCancelMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunLedgerVerifyCancelMatch[3];
    const verificationRunId = projectDocumentGovernanceRunLedgerVerifyCancelMatch[4];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canMutateGovernanceLedgerVerification(fixtureProfile)) {
      return forbidden<T>("Only administrators may mutate ledger verification attempts.");
    }
    const attempt =
      FIXTURE_GOVERNANCE_VERIFY_RUNS.find((item) => item.id === verificationRunId) ?? null;
    if (!attempt) {
      return notFound<T>("Verification attempt not found.");
    }
    if (!canCancelVerificationRun(attempt.status)) {
      return conflict<T>("Verification attempt is not cancelable.");
    }
    const payload: DocumentGovernanceLedgerVerifyDetailResponse = {
      runId,
      verificationStatus: "VALID",
      attempt: {
        ...cloneJson(attempt),
        status: "CANCELED",
        canceledBy: FIXTURE_SESSION.user.id,
        canceledAt: "2026-03-13T10:02:25.000Z",
        finishedAt: "2026-03-13T10:02:25.000Z"
      }
    };
    return ok<T>(payload as T);
  }

  const projectDocumentGovernanceRunLedgerVerifyMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/ledger\/verify$/
  );
  if (method === "POST" && projectDocumentGovernanceRunLedgerVerifyMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunLedgerVerifyMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunLedgerVerifyMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunLedgerVerifyMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canMutateGovernanceLedgerVerification(fixtureProfile)) {
      return forbidden<T>("Only administrators may mutate ledger verification attempts.");
    }
    const payload: DocumentGovernanceLedgerVerifyDetailResponse = {
      runId,
      verificationStatus: "VALID",
      attempt: {
        id: "gov-ledger-verify-004",
        runId,
        attemptNumber: 4,
        supersedesVerificationRunId: "gov-ledger-verify-003",
        supersededByVerificationRunId: null,
        status: "RUNNING",
        verificationResult: null,
        resultJson: null,
        startedAt: "2026-03-13T10:02:05.000Z",
        finishedAt: null,
        canceledBy: null,
        canceledAt: null,
        failureReason: null,
        createdBy: FIXTURE_SESSION.user.id,
        createdAt: "2026-03-13T10:02:05.000Z"
      }
    };
    return ok<T>(payload as T);
  }

  const projectDocumentGovernanceRunLedgerEntriesMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/ledger\/entries$/
  );
  if (method === "GET" && projectDocumentGovernanceRunLedgerEntriesMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunLedgerEntriesMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunLedgerEntriesMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunLedgerEntriesMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceLedger(fixtureProfile)) {
      return forbidden<T>("Evidence-ledger routes are restricted to administrator or auditor roles.");
    }
    const sliced = resolveGovernanceLedgerEntriesFixture(parsedPath);
    const payload: DocumentGovernanceLedgerEntriesResponse = {
      runId,
      status: "SUCCEEDED",
      view: sliced.view,
      ledgerId: "gov-ledger-attempt-001",
      ledgerSha256: "fixture-governance-ledger-sha-001",
      hashChainVersion: "v1",
      totalCount: sliced.totalCount,
      nextCursor: sliced.nextCursor,
      verificationStatus: "VALID",
      items: sliced.items
    };
    return ok<T>(payload as T);
  }

  const projectDocumentGovernanceRunLedgerSummaryMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/ledger\/summary$/
  );
  if (method === "GET" && projectDocumentGovernanceRunLedgerSummaryMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunLedgerSummaryMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunLedgerSummaryMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunLedgerSummaryMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceLedger(fixtureProfile)) {
      return forbidden<T>("Evidence-ledger routes are restricted to administrator or auditor roles.");
    }
    return ok<T>(cloneJson(FIXTURE_GOVERNANCE_LEDGER_SUMMARY_RESPONSE) as T);
  }

  const projectDocumentGovernanceRunLedgerStatusMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/ledger\/status$/
  );
  if (method === "GET" && projectDocumentGovernanceRunLedgerStatusMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunLedgerStatusMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunLedgerStatusMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunLedgerStatusMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceLedger(fixtureProfile)) {
      return forbidden<T>("Evidence-ledger routes are restricted to administrator or auditor roles.");
    }
    return ok<T>(cloneJson(FIXTURE_GOVERNANCE_LEDGER_STATUS_RESPONSE) as T);
  }

  const projectDocumentGovernanceRunLedgerMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/governance\/runs\/([^/]+)\/ledger$/
  );
  if (method === "GET" && projectDocumentGovernanceRunLedgerMatch) {
    const project = resolveProjectFixture(projectDocumentGovernanceRunLedgerMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentGovernanceRunLedgerMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentGovernanceRunLedgerMatch[3];
    if (runId !== FIXTURE_GOVERNANCE_RUN_SUMMARY.runId) {
      return notFound<T>("Governance run not found.");
    }
    if (!canViewGovernanceLedger(fixtureProfile)) {
      return forbidden<T>("Evidence-ledger routes are restricted to administrator or auditor roles.");
    }
    return ok<T>(cloneJson(FIXTURE_GOVERNANCE_LEDGER_RESPONSE) as T);
  }

  const projectDocumentLayoutOverviewMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/layout\/overview$/
  );
  if (method === "GET" && projectDocumentLayoutOverviewMatch) {
    const project = resolveProjectFixture(projectDocumentLayoutOverviewMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentLayoutOverviewMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const payload = buildLayoutOverviewFixture(project.id, document.id);
    return ok<T>(payload as T);
  }

  const projectDocumentLayoutRunsActiveMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/layout-runs\/active$/
  );
  if (method === "GET" && projectDocumentLayoutRunsActiveMatch) {
    const project = resolveProjectFixture(projectDocumentLayoutRunsActiveMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentLayoutRunsActiveMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const projection = resolveLayoutProjectionFixture(document.id);
    const runs = resolveLayoutRunsFixture(document.id);
    const run = resolveActiveLayoutRun({ projection, runs });
    const payload: DocumentLayoutActiveRunResponse = {
      projection,
      run
    };
    return ok<T>(payload as T);
  }

  const projectDocumentLayoutRunStatusMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/layout-runs\/([^/]+)\/status$/
  );
  if (method === "GET" && projectDocumentLayoutRunStatusMatch) {
    const project = resolveProjectFixture(projectDocumentLayoutRunStatusMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentLayoutRunStatusMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentLayoutRunStatusMatch[3];
    const run = resolveLayoutRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Layout run not found.");
    }
    const payload: DocumentLayoutRunStatusResponse = {
      runId: run.id,
      documentId: document.id,
      status: run.status,
      failureReason: run.failureReason,
      startedAt: run.startedAt,
      finishedAt: run.finishedAt,
      createdAt: run.createdAt,
      active: run.status === "QUEUED" || run.status === "RUNNING"
    };
    return ok<T>(payload as T);
  }

  const projectDocumentLayoutRunPagesOverlayMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/layout-runs\/([^/]+)\/pages\/([^/]+)\/overlay$/
  );
  if (method === "GET" && projectDocumentLayoutRunPagesOverlayMatch) {
    const project = resolveProjectFixture(projectDocumentLayoutRunPagesOverlayMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentLayoutRunPagesOverlayMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentLayoutRunPagesOverlayMatch[3];
    const pageId = projectDocumentLayoutRunPagesOverlayMatch[4];
    const run = resolveLayoutRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Layout run not found.");
    }
    const pageResult = resolveLayoutPageResultsFixture(run.id).find(
      (candidate) => candidate.pageId === pageId
    );
    if (!pageResult) {
      return notFound<T>("Layout page result not found.");
    }
    if (!pageResult.overlayJsonKey) {
      return conflict<T>("Layout overlay is not ready.");
    }
    const overlay = resolveLayoutOverlayFixture(run.id, pageId);
    if (!overlay) {
      return conflict<T>("Layout overlay is not ready.");
    }
    return ok<T>(overlay as T);
  }

  const projectDocumentLayoutRunPagesMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/layout-runs\/([^/]+)\/pages$/
  );
  if (method === "GET" && projectDocumentLayoutRunPagesMatch) {
    const project = resolveProjectFixture(projectDocumentLayoutRunPagesMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentLayoutRunPagesMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentLayoutRunPagesMatch[3];
    const run = resolveLayoutRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Layout run not found.");
    }
    const filtered = filterLayoutPageResults({
      items: resolveLayoutPageResultsFixture(run.id),
      path: parsedPath
    });
    const sliced = sliceFixtureItems(filtered, parsedPath);
    return ok<T>({
      runId: run.id,
      items: sliced.items,
      nextCursor: sliced.nextCursor
    } as T);
  }

  const projectDocumentLayoutRunDetailMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/layout-runs\/([^/]+)$/
  );
  if (method === "GET" && projectDocumentLayoutRunDetailMatch) {
    const project = resolveProjectFixture(projectDocumentLayoutRunDetailMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentLayoutRunDetailMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentLayoutRunDetailMatch[3];
    const run = resolveLayoutRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Layout run not found.");
    }
    return ok<T>(run as T);
  }

  const projectDocumentLayoutRunsMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/layout-runs$/
  );
  if (method === "GET" && projectDocumentLayoutRunsMatch) {
    const project = resolveProjectFixture(projectDocumentLayoutRunsMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentLayoutRunsMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runs = resolveLayoutRunsFixture(document.id);
    const sliced = sliceFixtureItems(runs, parsedPath);
    const payload: DocumentLayoutRunListResponse = {
      items: sliced.items,
      nextCursor: sliced.nextCursor
    };
    return ok<T>(payload as T);
  }

  const projectDocumentTranscriptionOverviewMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/transcription\/overview$/
  );
  if (method === "GET" && projectDocumentTranscriptionOverviewMatch) {
    const project = resolveProjectFixture(projectDocumentTranscriptionOverviewMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentTranscriptionOverviewMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const payload = buildTranscriptionOverviewFixture(project.id, document.id);
    return ok<T>(payload as T);
  }

  const projectDocumentPreprocessOverviewMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/preprocessing\/overview$/
  );
  if (method === "GET" && projectDocumentPreprocessOverviewMatch) {
    const project = resolveProjectFixture(projectDocumentPreprocessOverviewMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPreprocessOverviewMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const payload = buildPreprocessOverviewFixture(project.id, document.id);
    return ok<T>(payload as T);
  }

  const projectDocumentPreprocessQualityMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/preprocessing\/quality$/
  );
  if (method === "GET" && projectDocumentPreprocessQualityMatch) {
    const project = resolveProjectFixture(projectDocumentPreprocessQualityMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPreprocessQualityMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const projection = resolvePreprocessProjectionFixture(document.id);
    const runs = resolvePreprocessRunsFixture(document.id);
    const requestedRunId = parsedPath.searchParams.get("runId")?.trim() || null;
    const selectedRun = requestedRunId
      ? runs.find((run) => run.id === requestedRunId) ?? null
      : resolveActivePreprocessRun({ projection, runs });
    if (requestedRunId && !selectedRun) {
      return notFound<T>("Preprocess run not found.");
    }
    const filtered = selectedRun
      ? filterPreprocessPageResultsForQuality({
          items: resolvePreprocessPageResultsFixture(selectedRun.id),
          path: parsedPath
        })
      : [];
    const sliced = sliceFixtureItems(filtered, parsedPath);
    const payload: DocumentPreprocessQualityResponse = {
      projection,
      run: selectedRun,
      items: sliced.items,
      nextCursor: sliced.nextCursor
    };
    return ok<T>(payload as T);
  }

  const projectDocumentPreprocessRunsActiveMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/preprocess-runs\/active$/
  );
  if (method === "GET" && projectDocumentPreprocessRunsActiveMatch) {
    const project = resolveProjectFixture(projectDocumentPreprocessRunsActiveMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPreprocessRunsActiveMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const projection = resolvePreprocessProjectionFixture(document.id);
    const runs = resolvePreprocessRunsFixture(document.id);
    const activeRun = resolveActivePreprocessRun({ projection, runs });
    const payload: DocumentPreprocessActiveRunResponse = {
      projection,
      run: activeRun
    };
    return ok<T>(payload as T);
  }

  const projectDocumentPreprocessRunStatusMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/preprocess-runs\/([^/]+)\/status$/
  );
  if (method === "GET" && projectDocumentPreprocessRunStatusMatch) {
    const project = resolveProjectFixture(projectDocumentPreprocessRunStatusMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPreprocessRunStatusMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentPreprocessRunStatusMatch[3];
    const run = resolvePreprocessRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Preprocess run not found.");
    }
    const payload: DocumentPreprocessRunStatusResponse = {
      runId: run.id,
      documentId: document.id,
      status: run.status,
      failureReason: run.failureReason,
      startedAt: run.startedAt,
      finishedAt: run.finishedAt,
      createdAt: run.createdAt,
      active: run.status === "QUEUED" || run.status === "RUNNING"
    };
    return ok<T>(payload as T);
  }

  const projectDocumentPreprocessRunPagesMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/preprocess-runs\/([^/]+)\/pages$/
  );
  if (method === "GET" && projectDocumentPreprocessRunPagesMatch) {
    const project = resolveProjectFixture(projectDocumentPreprocessRunPagesMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPreprocessRunPagesMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentPreprocessRunPagesMatch[3];
    const run = resolvePreprocessRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Preprocess run not found.");
    }
    const filtered = filterPreprocessPageResultsForQuality({
      items: resolvePreprocessPageResultsFixture(run.id),
      path: parsedPath
    });
    const sliced = sliceFixtureItems(filtered, parsedPath);
    const payload: DocumentPreprocessRunPageListResponse = {
      runId: run.id,
      items: sliced.items,
      nextCursor: sliced.nextCursor
    };
    return ok<T>(payload as T);
  }

  const projectDocumentPreprocessRunPageMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/preprocess-runs\/([^/]+)\/pages\/([^/]+)$/
  );
  if (method === "GET" && projectDocumentPreprocessRunPageMatch) {
    const project = resolveProjectFixture(projectDocumentPreprocessRunPageMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPreprocessRunPageMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentPreprocessRunPageMatch[3];
    const pageId = projectDocumentPreprocessRunPageMatch[4];
    const run = resolvePreprocessRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Preprocess run not found.");
    }
    const pageResult = resolvePreprocessPageResultsFixture(run.id).find(
      (candidate) => candidate.pageId === pageId
    );
    if (!pageResult) {
      return notFound<T>("Preprocess page result not found.");
    }
    return ok<T>(pageResult as T);
  }

  const projectDocumentPreprocessRunsCompareMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/preprocess-runs\/compare$/
  );
  if (method === "GET" && projectDocumentPreprocessRunsCompareMatch) {
    const project = resolveProjectFixture(projectDocumentPreprocessRunsCompareMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPreprocessRunsCompareMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }

    const baseRunId = parsedPath.searchParams.get("baseRunId")?.trim() || "";
    const candidateRunId =
      parsedPath.searchParams.get("candidateRunId")?.trim() || "";
    if (!baseRunId || !candidateRunId) {
      return validationError<T>(
        "baseRunId and candidateRunId are required for compare."
      );
    }
    const runs = resolvePreprocessRunsFixture(document.id);
    const baseRun = runs.find((run) => run.id === baseRunId);
    const candidateRun = runs.find((run) => run.id === candidateRunId);
    if (!baseRun || !candidateRun) {
      return notFound<T>("Preprocess run not found.");
    }

    const basePageResults = resolvePreprocessPageResultsFixture(baseRun.id);
    const candidatePageResults = resolvePreprocessPageResultsFixture(candidateRun.id);
    const baseByPage = new Map(basePageResults.map((pageResult) => [pageResult.pageId, pageResult]));
    const candidateByPage = new Map(
      candidatePageResults.map((pageResult) => [pageResult.pageId, pageResult])
    );
    const pageIds = new Set<string>([
      ...baseByPage.keys(),
      ...candidateByPage.keys()
    ]);
    const pageMetaById = new Map(
      resolveDocumentPagesFixture(document.id).map((page) => [page.id, page.pageIndex])
    );
    const items = [...pageIds]
      .sort((left, right) => {
        const leftIndex = pageMetaById.get(left) ?? Number.MAX_SAFE_INTEGER;
        const rightIndex = pageMetaById.get(right) ?? Number.MAX_SAFE_INTEGER;
        return leftIndex - rightIndex;
      })
      .map((pageId) => ({
        pageId,
        pageIndex: pageMetaById.get(pageId) ?? 0,
        warningDelta:
          (candidateByPage.get(pageId)?.warningsJson.length ?? 0) -
          (baseByPage.get(pageId)?.warningsJson.length ?? 0),
        addedWarnings: [],
        removedWarnings: [],
        metricDeltas: {},
        outputAvailability: {
          baseGray: Boolean(baseByPage.get(pageId)?.outputObjectKeyGray),
          baseBin: Boolean(baseByPage.get(pageId)?.outputObjectKeyBin),
          candidateGray: Boolean(candidateByPage.get(pageId)?.outputObjectKeyGray),
          candidateBin: Boolean(candidateByPage.get(pageId)?.outputObjectKeyBin)
        },
        base: baseByPage.get(pageId) ?? null,
        candidate: candidateByPage.get(pageId) ?? null
      }));

    const payload: DocumentPreprocessCompareResponse = {
      documentId: document.id,
      projectId: project.id,
      baseRun,
      candidateRun,
      baseWarningCount: basePageResults.reduce(
        (count, pageResult) => count + pageResult.warningsJson.length,
        0
      ),
      candidateWarningCount: candidatePageResults.reduce(
        (count, pageResult) => count + pageResult.warningsJson.length,
        0
      ),
      baseBlockedCount: basePageResults.filter(
        (pageResult) => pageResult.qualityGateStatus === "BLOCKED"
      ).length,
      candidateBlockedCount: candidatePageResults.filter(
        (pageResult) => pageResult.qualityGateStatus === "BLOCKED"
      ).length,
      items
    };
    return ok<T>(payload as T);
  }

  const projectDocumentPreprocessRunDetailMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/preprocess-runs\/([^/]+)$/
  );
  if (method === "GET" && projectDocumentPreprocessRunDetailMatch) {
    const project = resolveProjectFixture(projectDocumentPreprocessRunDetailMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPreprocessRunDetailMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentPreprocessRunDetailMatch[3];
    const run = resolvePreprocessRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Preprocess run not found.");
    }
    return ok<T>(run as T);
  }

  const projectDocumentPreprocessRunsMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/preprocess-runs$/
  );
  if (method === "GET" && projectDocumentPreprocessRunsMatch) {
    const project = resolveProjectFixture(projectDocumentPreprocessRunsMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPreprocessRunsMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }

    const cursorRaw = Number(parsedPath.searchParams.get("cursor") ?? "0");
    const pageSizeRaw = Number(parsedPath.searchParams.get("pageSize") ?? "50");
    const cursor = Number.isFinite(cursorRaw) && cursorRaw >= 0 ? cursorRaw : 0;
    const pageSize =
      Number.isFinite(pageSizeRaw) && pageSizeRaw > 0
        ? Math.min(200, pageSizeRaw)
        : 50;
    const runs = resolvePreprocessRunsFixture(document.id);
    const start = Math.floor(cursor);
    const end = start + Math.floor(pageSize);
    const payload: DocumentPreprocessRunListResponse = {
      items: runs.slice(start, end),
      nextCursor: end < runs.length ? end : null
    };
    return ok<T>(payload as T);
  }

  const projectDocumentRedactionOverviewMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/(?:redaction|privacy)\/overview$/
  );
  if (method === "GET" && projectDocumentRedactionOverviewMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionOverviewMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionOverviewMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const payload = resolveRedactionOverviewFixture(project.id, document.id);
    return ok<T>(payload as T);
  }

  const projectDocumentRedactionRunsMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs$/
  );
  if (method === "GET" && projectDocumentRedactionRunsMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunsMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunsMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runs = resolveRedactionRunsFixture(document.id);
    const sliced = sliceFixtureItems(runs, parsedPath);
    const payload: DocumentRedactionRunListResponse = {
      items: sliced.items,
      nextCursor: sliced.nextCursor
    };
    return ok<T>(payload as T);
  }

  const projectDocumentRedactionRunsActiveMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/active$/
  );
  if (method === "GET" && projectDocumentRedactionRunsActiveMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunsActiveMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunsActiveMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const projection = resolveRedactionProjectionFixture(document.id);
    const activeRun = projection?.activeRedactionRunId
      ? resolveRedactionRunsFixture(document.id).find(
          (candidate) => candidate.id === projection.activeRedactionRunId
        ) ?? null
      : null;
    const payload: DocumentRedactionActiveRunResponse = {
      projection,
      run: activeRun
    };
    return ok<T>(payload as T);
  }

  const projectDocumentRedactionRunsCompareMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/compare$/
  );
  if (method === "GET" && projectDocumentRedactionRunsCompareMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunsCompareMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunsCompareMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const baseRunId = parsedPath.searchParams.get("baseRunId")?.trim() || "";
    const candidateRunId = parsedPath.searchParams.get("candidateRunId")?.trim() || "";
    if (!baseRunId || !candidateRunId) {
      return validationError<T>("baseRunId and candidateRunId are required for compare.");
    }
    const runs = resolveRedactionRunsFixture(document.id);
    const baseRun = runs.find((run) => run.id === baseRunId);
    const candidateRun = runs.find((run) => run.id === candidateRunId);
    if (!baseRun || !candidateRun) {
      return notFound<T>("Redaction run not found.");
    }
    const statuses = [
      "AUTO_APPLIED",
      "NEEDS_REVIEW",
      "APPROVED",
      "OVERRIDDEN",
      "FALSE_POSITIVE"
    ] as const;
    const actionTypes = ["MASK", "PSEUDONYMIZE", "GENERALIZE"] as const;
    const pages = resolveDocumentPagesFixture(document.id);
    const pageParam = Number.parseInt(parsedPath.searchParams.get("page") ?? "", 10);
    const requestedPage = Number.isFinite(pageParam) && pageParam > 0 ? pageParam : null;
    const findingFilter = parsedPath.searchParams.get("findingId")?.trim() || null;
    const lineFilter = parsedPath.searchParams.get("lineId")?.trim() || null;
    const tokenFilter = parsedPath.searchParams.get("tokenId")?.trim() || null;
    const items = pages
      .filter((page) => requestedPage === null || page.pageIndex + 1 === requestedPage)
      .map((page) => {
        const baseFindings = resolveRedactionFindingsFixture(baseRun.id, page.id);
        const candidateFindings = resolveRedactionFindingsFixture(candidateRun.id, page.id);
        if (findingFilter) {
          const hasFinding =
            baseFindings.some((item) => item.id === findingFilter) ||
            candidateFindings.some((item) => item.id === findingFilter);
          if (!hasFinding) {
            return null;
          }
        }
        if (lineFilter) {
          const hasLine =
            baseFindings.some((item) => item.lineId === lineFilter || item.geometry.lineId === lineFilter) ||
            candidateFindings.some(
              (item) => item.lineId === lineFilter || item.geometry.lineId === lineFilter
            );
          if (!hasLine) {
            return null;
          }
        }
        if (tokenFilter) {
          const hasToken =
            baseFindings.some((item) => item.geometry.tokenIds.includes(tokenFilter)) ||
            candidateFindings.some((item) => item.geometry.tokenIds.includes(tokenFilter));
          if (!hasToken) {
            return null;
          }
        }
        const baseDecisionCounts = Object.fromEntries(
          statuses.map((status) => [status, baseFindings.filter((item) => item.decisionStatus === status).length])
        ) as Record<(typeof statuses)[number], number>;
        const candidateDecisionCounts = Object.fromEntries(
          statuses.map((status) => [status, candidateFindings.filter((item) => item.decisionStatus === status).length])
        ) as Record<(typeof statuses)[number], number>;
        const decisionStatusDeltas = Object.fromEntries(
          statuses.map((status) => [status, candidateDecisionCounts[status] - baseDecisionCounts[status]])
        ) as Record<(typeof statuses)[number], number>;
        const baseActionCounts = Object.fromEntries(
          actionTypes.map((actionType) => [
            actionType,
            baseFindings.filter((item) => item.actionType === actionType).length
          ])
        ) as Record<(typeof actionTypes)[number], number>;
        const candidateActionCounts = Object.fromEntries(
          actionTypes.map((actionType) => [
            actionType,
            candidateFindings.filter((item) => item.actionType === actionType).length
          ])
        ) as Record<(typeof actionTypes)[number], number>;
        const actionTypeDeltas = Object.fromEntries(
          actionTypes.map((actionType) => [
            actionType,
            candidateActionCounts[actionType] - baseActionCounts[actionType]
          ])
        ) as Record<(typeof actionTypes)[number], number>;
        const changedDecisionCount = statuses.reduce(
          (count, status) => count + Math.abs(decisionStatusDeltas[status]),
          0
        );
        const changedActionCount = actionTypes.reduce(
          (count, actionType) => count + Math.abs(actionTypeDeltas[actionType]),
          0
        );
        const baseReview = resolveRedactionPageReviewFixture(baseRun.id, page.id);
        const candidateReview = resolveRedactionPageReviewFixture(candidateRun.id, page.id);
        const basePreview = resolveRedactionPreviewStatusFixture(baseRun.id, page.id);
        const candidatePreview = resolveRedactionPreviewStatusFixture(candidateRun.id, page.id);
        const actionCompareState =
          basePreview?.status === "READY" && candidatePreview?.status === "READY"
            ? ("AVAILABLE" as const)
            : ("NOT_YET_AVAILABLE" as const);
        return {
          pageId: page.id,
          pageIndex: page.pageIndex,
          baseFindingCount: baseFindings.length,
          candidateFindingCount: candidateFindings.length,
          changedDecisionCount,
          changedActionCount,
          baseDecisionCounts,
          candidateDecisionCounts,
          decisionStatusDeltas,
          baseActionCounts,
          candidateActionCounts,
          actionTypeDeltas,
          actionCompareState,
          changedReviewStatus: (baseReview?.reviewStatus ?? null) !== (candidateReview?.reviewStatus ?? null),
          changedSecondReviewStatus:
            (baseReview?.secondReviewStatus ?? null) !== (candidateReview?.secondReviewStatus ?? null),
          baseReview,
          candidateReview,
          basePreviewStatus: basePreview?.status ?? null,
          candidatePreviewStatus: candidatePreview?.status ?? null,
          previewReadyDelta:
            Number(candidatePreview?.status === "READY") - Number(basePreview?.status === "READY")
        };
      })
      .filter((item): item is NonNullable<typeof item> => item !== null);
    const payload: DocumentRedactionCompareResponse = {
      documentId: document.id,
      projectId: project.id,
      baseRun,
      candidateRun,
      compareActionState:
        candidateRun.runKind === "POLICY_RERUN" ||
        baseRun.runKind === "POLICY_RERUN" ||
        candidateRun.supersedesRedactionRunId === baseRun.id ||
        baseRun.supersedesRedactionRunId === candidateRun.id
          ? items.every((item) => item.actionCompareState === "AVAILABLE")
            ? "AVAILABLE"
            : "NOT_YET_AVAILABLE"
          : "NOT_YET_RERUN",
      changedPageCount: items.filter(
        (item) =>
          item.changedDecisionCount > 0 ||
          item.changedActionCount > 0 ||
          item.changedReviewStatus ||
          item.changedSecondReviewStatus ||
          item.basePreviewStatus !== item.candidatePreviewStatus
      ).length,
      changedDecisionCount: items.reduce((count, item) => count + item.changedDecisionCount, 0),
      changedActionCount: items.reduce((count, item) => count + item.changedActionCount, 0),
      candidatePolicyStatus: null,
      comparisonOnlyCandidate: false,
      preActivationWarnings: [],
      items
    };
    return ok<T>(payload as T);
  }

  const projectDocumentRedactionRunDetailMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/([^/]+)$/
  );
  if (method === "GET" && projectDocumentRedactionRunDetailMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunDetailMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunDetailMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentRedactionRunDetailMatch[3];
    const run = resolveRedactionRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Redaction run not found.");
    }
    return ok<T>(run as T);
  }

  const projectDocumentRedactionRunStatusMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/([^/]+)\/status$/
  );
  if (method === "GET" && projectDocumentRedactionRunStatusMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunStatusMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunStatusMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentRedactionRunStatusMatch[3];
    const run = resolveRedactionRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Redaction run not found.");
    }
    const projection = resolveRedactionProjectionFixture(document.id);
    const payload: DocumentRedactionRunStatusResponse = {
      runId: run.id,
      documentId: document.id,
      status: run.status,
      failureReason: run.failureReason,
      startedAt: run.startedAt,
      finishedAt: run.finishedAt,
      createdAt: run.createdAt,
      active: projection?.activeRedactionRunId === run.id
    };
    return ok<T>(payload as T);
  }

  const projectDocumentRedactionRunReviewMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/([^/]+)\/review$/
  );
  if (method === "GET" && projectDocumentRedactionRunReviewMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunReviewMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunReviewMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentRedactionRunReviewMatch[3];
    const run = resolveRedactionRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Redaction run not found.");
    }
    const review = resolveRedactionRunReviewFixture(run.id);
    if (!review) {
      return notFound<T>("Redaction run review not found.");
    }
    return ok<T>(review as T);
  }

  const projectDocumentRedactionRunEventsMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/([^/]+)\/events$/
  );
  if (method === "GET" && projectDocumentRedactionRunEventsMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunEventsMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunEventsMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentRedactionRunEventsMatch[3];
    const run = resolveRedactionRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Redaction run not found.");
    }
    const events = resolveRedactionRunEventsFixture(run.id).sort((left, right) => {
      if (left.createdAt !== right.createdAt) {
        return left.createdAt.localeCompare(right.createdAt);
      }
      if (left.sourceTablePrecedence !== right.sourceTablePrecedence) {
        return left.sourceTablePrecedence - right.sourceTablePrecedence;
      }
      return left.eventId.localeCompare(right.eventId);
    });
    const payload: DocumentRedactionRunEventsResponse = {
      runId: run.id,
      items: events
    };
    return ok<T>(payload as T);
  }

  const projectDocumentRedactionRunOutputMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/([^/]+)\/output(?:\/status)?$/
  );
  if (method === "GET" && projectDocumentRedactionRunOutputMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunOutputMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunOutputMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentRedactionRunOutputMatch[3];
    const run = resolveRedactionRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Redaction run not found.");
    }
    const output = resolveRedactionRunOutputFixture(run.id);
    if (!output) {
      return notFound<T>("Redaction run output not found.");
    }
    return ok<T>(output as T);
  }

  const projectDocumentRedactionRunPagesMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/([^/]+)\/pages$/
  );
  if (method === "GET" && projectDocumentRedactionRunPagesMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunPagesMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunPagesMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentRedactionRunPagesMatch[3];
    const run = resolveRedactionRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Redaction run not found.");
    }
    const category = parsedPath.searchParams.get("category")?.trim() ?? "";
    const unresolvedOnly =
      parsedPath.searchParams.get("unresolvedOnly")?.trim().toLowerCase() === "true";
    const directIdentifiersOnly =
      parsedPath.searchParams.get("directIdentifiersOnly")?.trim().toLowerCase() === "true";
    const pages = resolveDocumentPagesFixture(document.id);
    const rows: DocumentRedactionRunPage[] = [];
    for (const page of pages) {
      let findings = resolveRedactionFindingsFixture(run.id, page.id);
      if (category) {
        findings = findings.filter((finding) => finding.category === category);
      }
      if (directIdentifiersOnly) {
        findings = findings.filter((finding) =>
          isDirectIdentifierCategory(finding.category)
        );
      }
      const unresolvedCount = findings.filter((finding) =>
        isUnresolvedStatus(finding.decisionStatus)
      ).length;
      if (unresolvedOnly && unresolvedCount <= 0) {
        continue;
      }
      const review = resolveRedactionPageReviewFixture(run.id, page.id);
      const previewStatus = resolveRedactionPreviewStatusFixture(run.id, page.id);
      rows.push({
        runId: run.id,
        pageId: page.id,
        pageIndex: page.pageIndex,
        findingCount: findings.length,
        unresolvedCount,
        reviewStatus: review?.reviewStatus ?? "NOT_STARTED",
        reviewEtag: review?.reviewEtag ?? "",
        requiresSecondReview: review?.requiresSecondReview ?? false,
        secondReviewStatus: review?.secondReviewStatus ?? "NOT_REQUIRED",
        secondReviewedBy: review?.secondReviewedBy ?? null,
        secondReviewedAt: review?.secondReviewedAt ?? null,
        lastReviewedBy: review?.firstReviewedBy ?? null,
        lastReviewedAt: review?.firstReviewedAt ?? null,
        previewStatus: previewStatus?.status ?? null,
        topFindings: findings.slice(0, 5)
      });
    }
    const sorted = rows.sort((left, right) => left.pageIndex - right.pageIndex);
    const sliced = sliceFixtureItems(sorted, parsedPath);
    const payload: DocumentRedactionRunPageListResponse = {
      runId: run.id,
      items: sliced.items,
      nextCursor: sliced.nextCursor
    };
    return ok<T>(payload as T);
  }

  const projectDocumentRedactionRunPageFindingsMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/([^/]+)\/pages\/([^/]+)\/findings$/
  );
  if (method === "GET" && projectDocumentRedactionRunPageFindingsMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunPageFindingsMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunPageFindingsMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentRedactionRunPageFindingsMatch[3];
    const pageId = projectDocumentRedactionRunPageFindingsMatch[4];
    const run = resolveRedactionRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Redaction run not found.");
    }
    const page = resolveDocumentPagesFixture(document.id).find(
      (candidate) => candidate.id === pageId
    );
    if (!page) {
      return notFound<T>("Page not found.");
    }
    const findings = filterRedactionFindings({
      findings: resolveRedactionFindingsFixture(run.id, page.id),
      path: parsedPath
    });
    const payload: DocumentRedactionFindingListResponse = {
      runId: run.id,
      pageId: page.id,
      items: findings
    };
    return ok<T>(payload as T);
  }

  const projectDocumentRedactionRunFindingPatchMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/([^/]+)\/findings\/([^/]+)$/
  );
  if (method === "PATCH" && projectDocumentRedactionRunFindingPatchMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunFindingPatchMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunFindingPatchMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentRedactionRunFindingPatchMatch[3];
    const findingId = projectDocumentRedactionRunFindingPatchMatch[4];
    const run = resolveRedactionRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Redaction run not found.");
    }
    const runReview = resolveRedactionRunReviewFixture(run.id);
    if (runReview?.reviewStatus === "APPROVED") {
      return conflict<T>("Approved runs are locked and cannot be mutated.");
    }
    const payload = parseFixtureJsonBody(options.body) as {
      actionType?: unknown;
      decisionEtag?: unknown;
      decisionStatus?: unknown;
      reason?: unknown;
    } | null;
    if (!payload || typeof payload.decisionStatus !== "string") {
      return validationError<T>("decisionStatus is required.");
    }
    if (!payload || typeof payload.decisionEtag !== "string" || !payload.decisionEtag.trim()) {
      return validationError<T>("decisionEtag is required.");
    }
    if (
      payload.decisionStatus !== "APPROVED" &&
      payload.decisionStatus !== "OVERRIDDEN" &&
      payload.decisionStatus !== "FALSE_POSITIVE" &&
      payload.decisionStatus !== "AUTO_APPLIED" &&
      payload.decisionStatus !== "NEEDS_REVIEW"
    ) {
      return validationError<T>("decisionStatus is invalid.");
    }
    const reason =
      typeof payload.reason === "string" && payload.reason.trim().length > 0
        ? payload.reason.trim()
        : null;
    if (
      (payload.decisionStatus === "OVERRIDDEN" ||
        payload.decisionStatus === "FALSE_POSITIVE") &&
      !reason
    ) {
      return validationError<T>(
        "reason is required when decisionStatus is OVERRIDDEN or FALSE_POSITIVE."
      );
    }

    const runPageKeys = Object.keys(FIXTURE_REDACTION_FINDINGS_BY_RUN_PAGE).filter((key) =>
      key.startsWith(`${run.id}:`)
    );
    let updatedFinding: DocumentRedactionFinding | null = null;
    let updatedPageId: string | null = null;
    for (const runPageKey of runPageKeys) {
      const findings = FIXTURE_REDACTION_FINDINGS_BY_RUN_PAGE[runPageKey] ?? [];
      const findingIndex = findings.findIndex((item) => item.id === findingId);
      if (findingIndex < 0) {
        continue;
      }
      const currentFinding = findings[findingIndex];
      if (currentFinding.decisionEtag !== payload.decisionEtag.trim()) {
        return conflict<T>("Redaction finding update conflicts with a newer change.");
      }
      const nextEtag = `${currentFinding.id}-etag-v${Date.now()}`;
      const now = new Date().toISOString();
      const nextDecisionStatus = payload.decisionStatus as DocumentRedactionFinding["decisionStatus"];
      const nextFinding = {
        ...currentFinding,
        decisionStatus: nextDecisionStatus,
        decisionBy: FIXTURE_SESSION.user.id,
        decisionAt: now,
        decisionReason: reason,
        decisionEtag: nextEtag,
        updatedAt: now
      };
      findings[findingIndex] = nextFinding;
      updatedFinding = cloneRedactionFinding(nextFinding);
      updatedPageId = nextFinding.pageId;
      const previewKey = `${run.id}:${nextFinding.pageId}`;
      const currentPreview = FIXTURE_REDACTION_PREVIEW_STATUS_BY_RUN_PAGE[previewKey];
      if (currentPreview) {
        FIXTURE_REDACTION_PREVIEW_STATUS_BY_RUN_PAGE[previewKey] = {
          ...currentPreview,
          status: "PENDING",
          previewSha256: null,
          generatedAt: null
        };
      }
      fixtureRedactionEventSequence += 1;
      const eventsKey = `${run.id}:${nextFinding.pageId}`;
      const eventList = FIXTURE_REDACTION_EVENTS_BY_RUN_PAGE[eventsKey] ?? [];
      eventList.push({
        sourceTable: "redaction_decision_events",
        sourceTablePrecedence: 0,
        eventId: `red-event-decision-${fixtureRedactionEventSequence}`,
        runId: run.id,
        pageId: nextFinding.pageId,
        findingId: nextFinding.id,
        eventType: String(payload.actionType ?? "MASK"),
        actorUserId: FIXTURE_SESSION.user.id,
        reason,
        createdAt: now,
        detailsJson: {
          fromDecisionStatus: currentFinding.decisionStatus,
          toDecisionStatus: nextFinding.decisionStatus,
          actionType: String(payload.actionType ?? "MASK"),
          areaMaskId: nextFinding.areaMaskId
        }
      });
      FIXTURE_REDACTION_EVENTS_BY_RUN_PAGE[eventsKey] = eventList;
      break;
    }
    if (!updatedFinding || !updatedPageId) {
      return notFound<T>("Redaction finding not found.");
    }
    return ok<T>(updatedFinding as T);
  }

  const projectDocumentRedactionRunPageReviewMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/([^/]+)\/pages\/([^/]+)\/review$/
  );
  if (projectDocumentRedactionRunPageReviewMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunPageReviewMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunPageReviewMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentRedactionRunPageReviewMatch[3];
    const pageId = projectDocumentRedactionRunPageReviewMatch[4];
    const run = resolveRedactionRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Redaction run not found.");
    }
    const key = `${run.id}:${pageId}`;
    const currentReview = FIXTURE_REDACTION_PAGE_REVIEWS_BY_RUN_PAGE[key];
    if (!currentReview) {
      return notFound<T>("Redaction page review not found.");
    }
    if (method === "GET") {
      return ok<T>(cloneRedactionPageReview(currentReview) as T);
    }
    if (method === "PATCH") {
      const runReview = resolveRedactionRunReviewFixture(run.id);
      if (runReview?.reviewStatus === "APPROVED") {
        return conflict<T>("Approved runs are locked and cannot be mutated.");
      }
      const payload = parseFixtureJsonBody(options.body) as {
        reviewEtag?: unknown;
        reviewStatus?: unknown;
        reason?: unknown;
      } | null;
      if (!payload || typeof payload.reviewStatus !== "string") {
        return validationError<T>("reviewStatus is required.");
      }
      if (!payload || typeof payload.reviewEtag !== "string" || !payload.reviewEtag.trim()) {
        return validationError<T>("reviewEtag is required.");
      }
      if (
        payload.reviewStatus !== "NOT_STARTED" &&
        payload.reviewStatus !== "IN_REVIEW" &&
        payload.reviewStatus !== "APPROVED" &&
        payload.reviewStatus !== "CHANGES_REQUESTED"
      ) {
        return validationError<T>("reviewStatus is invalid.");
      }
      if (currentReview.reviewEtag !== payload.reviewEtag.trim()) {
        return conflict<T>("Redaction page review update conflicts with a newer change.");
      }
      const now = new Date().toISOString();
      const nextReview: DocumentRedactionPageReview = {
        ...currentReview,
        reviewStatus: payload.reviewStatus,
        reviewEtag: `${currentReview.pageId}-review-v${Date.now()}`,
        firstReviewedBy: currentReview.firstReviewedBy ?? FIXTURE_SESSION.user.id,
        firstReviewedAt: currentReview.firstReviewedAt ?? now,
        updatedAt: now
      };
      FIXTURE_REDACTION_PAGE_REVIEWS_BY_RUN_PAGE[key] = nextReview;
      fixtureRedactionEventSequence += 1;
      const eventType =
        payload.reviewStatus === "APPROVED"
          ? "PAGE_APPROVED"
          : payload.reviewStatus === "CHANGES_REQUESTED"
            ? "CHANGES_REQUESTED"
            : "PAGE_REVIEW_STARTED";
      const eventList = FIXTURE_REDACTION_EVENTS_BY_RUN_PAGE[key] ?? [];
      eventList.push({
        sourceTable: "redaction_page_review_events",
        sourceTablePrecedence: 1,
        eventId: `red-event-review-${fixtureRedactionEventSequence}`,
        runId: run.id,
        pageId,
        findingId: null,
        eventType,
        actorUserId: FIXTURE_SESSION.user.id,
        reason:
          typeof payload.reason === "string" && payload.reason.trim()
            ? payload.reason.trim()
            : null,
        createdAt: now,
        detailsJson: {}
      });
      FIXTURE_REDACTION_EVENTS_BY_RUN_PAGE[key] = eventList;
      return ok<T>(cloneRedactionPageReview(nextReview) as T);
    }
  }

  const projectDocumentRedactionRunPagePreviewStatusMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/([^/]+)\/pages\/([^/]+)\/preview-status$/
  );
  if (method === "GET" && projectDocumentRedactionRunPagePreviewStatusMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunPagePreviewStatusMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunPagePreviewStatusMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentRedactionRunPagePreviewStatusMatch[3];
    const pageId = projectDocumentRedactionRunPagePreviewStatusMatch[4];
    const run = resolveRedactionRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Redaction run not found.");
    }
    const previewStatus = resolveRedactionPreviewStatusFixture(run.id, pageId);
    if (!previewStatus) {
      return notFound<T>("Safeguarded preview status was not found.");
    }
    return ok<T>(previewStatus as T);
  }

  const projectDocumentRedactionRunPageEventsMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/redaction-runs\/([^/]+)\/pages\/([^/]+)\/events$/
  );
  if (method === "GET" && projectDocumentRedactionRunPageEventsMatch) {
    const project = resolveProjectFixture(projectDocumentRedactionRunPageEventsMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentRedactionRunPageEventsMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentRedactionRunPageEventsMatch[3];
    const pageId = projectDocumentRedactionRunPageEventsMatch[4];
    const run = resolveRedactionRunsFixture(document.id).find(
      (candidate) => candidate.id === runId
    );
    if (!run) {
      return notFound<T>("Redaction run not found.");
    }
    const events = resolveRedactionEventsFixture(run.id, pageId).sort((left, right) => {
      if (left.createdAt !== right.createdAt) {
        return left.createdAt.localeCompare(right.createdAt);
      }
      if (left.sourceTablePrecedence !== right.sourceTablePrecedence) {
        return left.sourceTablePrecedence - right.sourceTablePrecedence;
      }
      return left.eventId.localeCompare(right.eventId);
    });
    const payload: DocumentRedactionRunEventsResponse = {
      runId: run.id,
      items: events
    };
    return ok<T>(payload as T);
  }

  const projectDocumentTranscriptionRunPageLinesMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/transcription-runs\/([^/]+)\/pages\/([^/]+)\/lines$/
  );
  if (method === "GET" && projectDocumentTranscriptionRunPageLinesMatch) {
    const project = resolveProjectFixture(projectDocumentTranscriptionRunPageLinesMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentTranscriptionRunPageLinesMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const runId = projectDocumentTranscriptionRunPageLinesMatch[3];
    const pageId = projectDocumentTranscriptionRunPageLinesMatch[4];
    const requestedLineId = parsedPath.searchParams.get("lineId")?.trim() ?? "";
    let lines = resolveTranscriptionLinesFixture(runId, pageId);
    if (requestedLineId) {
      lines = lines.filter((line) => line.lineId === requestedLineId);
    }
    const payload: DocumentTranscriptionLineResultListResponse = {
      runId,
      pageId,
      items: lines
    };
    return ok<T>(payload as T);
  }

  const projectDocumentRetryExtractionMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/retry-extraction$/
  );
  if (method === "POST" && projectDocumentRetryExtractionMatch) {
    const project = resolveProjectFixture(
      projectDocumentRetryExtractionMatch[1]
    );
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const documentId = projectDocumentRetryExtractionMatch[2];
    const document = resolveProjectDocumentFixture(project.id, documentId);
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const timeline = FIXTURE_DOCUMENT_TIMELINES[document.id] ?? [];
    const latestExtraction = timeline.find(
      (candidate) =>
        candidate.runKind === "EXTRACTION" &&
        candidate.supersededByProcessingRunId === null
    );
    if (!latestExtraction) {
      return conflict<T>("No extraction attempt is available for retry.");
    }
    if (!["FAILED", "CANCELED"].includes(latestExtraction.status)) {
      return conflict<T>(
        "Retry is allowed only when the latest extraction attempt is FAILED or CANCELED."
      );
    }

    const newRunId = `run-fixture-retry-${latestExtraction.attemptNumber + 1}`;
    const now = "2026-03-13T10:03:00.000Z";
    const retryRun = {
      id: newRunId,
      attemptNumber: latestExtraction.attemptNumber + 1,
      runKind: "EXTRACTION" as const,
      supersedesProcessingRunId: latestExtraction.id,
      supersededByProcessingRunId: null,
      status: "QUEUED" as const,
      failureReason: null,
      createdBy: "user-fixture-admin",
      startedAt: null,
      finishedAt: null,
      canceledBy: null,
      canceledAt: null,
      createdAt: now
    };
    return ok<T>({
      ...retryRun,
      documentId: document.id,
      active: true
    } as T);
  }

  const projectDocumentPagesMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/pages$/
  );
  if (method === "GET" && projectDocumentPagesMatch) {
    const project = resolveProjectFixture(projectDocumentPagesMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPagesMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const pages = resolveDocumentPagesFixture(document.id);
    return ok<T>({
      items: pages.map((page) => asListPage(page))
    } as T);
  }

  const projectDocumentPageVariantsMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/pages\/([^/]+)\/variants$/
  );
  if (method === "GET" && projectDocumentPageVariantsMatch) {
    const project = resolveProjectFixture(projectDocumentPageVariantsMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPageVariantsMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }

    const page = resolveDocumentPagesFixture(document.id).find(
      (candidate) => candidate.id === projectDocumentPageVariantsMatch[3]
    );
    if (!page) {
      return notFound<T>("Page not found.");
    }

    const runs = resolvePreprocessRunsFixture(document.id);
    const requestedRunId =
      parsedPath.searchParams.get("runId")?.trim() || null;
    const projection = resolvePreprocessProjectionFixture(document.id);

    const resolvedRun = requestedRunId
      ? runs.find((run) => run.id === requestedRunId) ?? null
      : projection?.activePreprocessRunId
        ? runs.find((run) => run.id === projection.activePreprocessRunId) ?? null
        : null;

    if (requestedRunId && !resolvedRun) {
      return notFound<T>("Preprocess run not found.");
    }
    if (!requestedRunId && !projection?.activePreprocessRunId) {
      return conflict<T>("No active preprocess run exists for this document.");
    }
    if (!resolvedRun) {
      return conflict<T>(
        "Active preprocess projection references a missing run."
      );
    }

    const pageResult =
      resolvePreprocessPageResultsFixture(resolvedRun.id).find(
        (candidate) => candidate.pageId === page.id
      ) ?? null;
    const metricsJson = pageResult ? { ...pageResult.metricsJson } : {};
    const warningsJson = pageResult ? [...pageResult.warningsJson] : [];
    const resultStatus = pageResult?.status ?? null;
    const qualityGateStatus = pageResult?.qualityGateStatus ?? null;
    const preprocessedGrayAvailable = Boolean(
      pageResult &&
        pageResult.status === "SUCCEEDED" &&
        pageResult.outputObjectKeyGray
    );
    const preprocessedBinAvailable = Boolean(
      pageResult &&
        pageResult.status === "SUCCEEDED" &&
        pageResult.outputObjectKeyBin
    );

    const payload: DocumentPageVariantsResponse = {
      documentId: document.id,
      pageId: page.id,
      requestedRunId,
      resolvedRunId: resolvedRun.id,
      run: resolvedRun,
      variants: [
        {
          variant: "ORIGINAL",
          imageVariant: "full",
          available: page.derivedImageAvailable,
          mediaType: "image/png",
          runId: null,
          resultStatus: null,
          qualityGateStatus: null,
          warningsJson: [],
          metricsJson: {}
        },
        {
          variant: "PREPROCESSED_GRAY",
          imageVariant: "preprocessed_gray",
          available: preprocessedGrayAvailable,
          mediaType: "image/png",
          runId: resolvedRun.id,
          resultStatus,
          qualityGateStatus,
          warningsJson,
          metricsJson
        },
        {
          variant: "PREPROCESSED_BIN",
          imageVariant: "preprocessed_bin",
          available: preprocessedBinAvailable,
          mediaType: "image/png",
          runId: resolvedRun.id,
          resultStatus,
          qualityGateStatus,
          warningsJson,
          metricsJson
        }
      ]
    };
    return ok<T>(payload as T);
  }

  const projectDocumentPageMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)\/pages\/([^/]+)$/
  );
  if (method === "GET" && projectDocumentPageMatch) {
    const project = resolveProjectFixture(projectDocumentPageMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPageMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const page = resolveDocumentPagesFixture(document.id).find(
      (candidate) => candidate.id === projectDocumentPageMatch[3]
    );
    if (!page) {
      return notFound<T>("Page not found.");
    }
    return ok<T>(cloneDocumentPageDetail(page) as T);
  }
  if (method === "PATCH" && projectDocumentPageMatch) {
    const project = resolveProjectFixture(projectDocumentPageMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentPageMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    const payload = parseFixtureJsonBody(options.body) as {
      viewerRotation?: unknown;
    } | null;
    if (!payload || typeof payload.viewerRotation !== "number") {
      return validationError<T>("viewerRotation must be a number.");
    }
    if (!Number.isFinite(payload.viewerRotation)) {
      return validationError<T>("viewerRotation must be a number.");
    }
    if (payload.viewerRotation < -360 || payload.viewerRotation > 360) {
      return validationError<T>("viewerRotation must be between -360 and 360.");
    }
    const pages = FIXTURE_DOCUMENT_PAGES[document.id] ?? [];
    const page = pages.find(
      (candidate) => candidate.id === projectDocumentPageMatch[3]
    );
    if (!page) {
      return notFound<T>("Page not found.");
    }
    page.viewerRotation = payload.viewerRotation;
    page.updatedAt = FIXTURE_NOW;
    return ok<T>(cloneDocumentPageDetail(page) as T);
  }

  const projectDocumentMatch = pathname.match(
    /^\/projects\/([^/]+)\/documents\/([^/]+)$/
  );
  if (method === "GET" && projectDocumentMatch) {
    const project = resolveProjectFixture(projectDocumentMatch[1]);
    if (!project) {
      return notFound<T>("Project not found.");
    }
    const document = resolveProjectDocumentFixture(
      project.id,
      projectDocumentMatch[2]
    );
    if (!document) {
      return notFound<T>("Document not found.");
    }
    return ok<T>(cloneDocument(document) as T);
  }

  if (method === "GET" && pathname === "/admin/audit-integrity") {
    return ok<T>({ ...FIXTURE_AUDIT_INTEGRITY } as T);
  }

  if (method === "GET" && pathname === "/admin/security/status") {
    return ok<T>({
      ...FIXTURE_SECURITY_STATUS,
      outboundAllowlist: [...FIXTURE_SECURITY_STATUS.outboundAllowlist]
    } as T);
  }

  if (method === "GET" && pathname === "/admin/operations/overview") {
    return ok<T>({
      ...FIXTURE_OPERATIONS_OVERVIEW,
      topRoutes: FIXTURE_OPERATIONS_OVERVIEW.topRoutes.map((route) => ({
        ...route
      })),
      exporter: { ...FIXTURE_OPERATIONS_OVERVIEW.exporter }
    } as T);
  }

  if (method === "GET" && pathname === "/admin/operations/export-status") {
    return ok<T>({
      ...FIXTURE_OPERATIONS_EXPORT_STATUS,
      aging: { ...FIXTURE_OPERATIONS_EXPORT_STATUS.aging },
      reminders: { ...FIXTURE_OPERATIONS_EXPORT_STATUS.reminders },
      escalations: { ...FIXTURE_OPERATIONS_EXPORT_STATUS.escalations },
      retention: { ...FIXTURE_OPERATIONS_EXPORT_STATUS.retention },
      terminal: { ...FIXTURE_OPERATIONS_EXPORT_STATUS.terminal },
      policy: { ...FIXTURE_OPERATIONS_EXPORT_STATUS.policy }
    } as T);
  }

  if (method === "GET" && pathname === "/me/activity") {
    return ok<T>({
      items: FIXTURE_ACTIVITY.items.map((event) => ({
        ...event,
        metadataJson: { ...event.metadataJson }
      })),
      nextCursor: FIXTURE_ACTIVITY.nextCursor
    } as T);
  }

  return notFound<T>();
}
