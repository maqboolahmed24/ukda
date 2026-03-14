import type {
  AuditEventListResponse,
  AuditIntegrityResponse,
  AuthProviderResponse,
  CreateDocumentUploadSessionRequest,
  DocumentLayoutActiveRunResponse,
  DocumentLayoutOverviewResponse,
  DocumentLayoutPageOverlay,
  DocumentLayoutPageResult,
  DocumentLayoutProjection,
  DocumentLayoutRun,
  DocumentLayoutRunListResponse,
  DocumentLayoutRunStatusResponse,
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
  DocumentTimelineResponse,
  DocumentUploadSessionStatus,
  OperationsOverviewResponse,
  ProjectDocument,
  ProjectDocumentUploadSessionStatus,
  ProjectDocumentPage,
  ProjectDocumentPageDetail,
  ProjectDocumentListResponse,
  ProjectJobListResponse,
  ProjectJobSummaryResponse,
  ProjectListResponse,
  ProjectSummary,
  SecurityStatusResponse,
  ServiceHealthPayload,
  ServiceReadinessPayload,
  SessionResponse
} from "@ukde/contracts";

import type { ApiResult } from "./api-types";

const BROWSER_TEST_MODE_FLAG = "UKDE_BROWSER_TEST_MODE";
const FIXTURE_SESSION_TOKEN = "fixture-session-token";
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
  exportGatewayState: "DISABLED_PHASE0"
};

const FIXTURE_OPERATIONS_OVERVIEW: OperationsOverviewResponse = {
  generatedAt: FIXTURE_NOW,
  uptimeSeconds: 86_400,
  requestCount: 9_120,
  requestErrorCount: 27,
  errorRatePercent: 0.296,
  p95LatencyMs: 188.22,
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

function hasFixtureAuthToken(token: string | null | undefined): boolean {
  return Boolean(token && token.trim().length > 0);
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

export function getBrowserFixtureSessionToken(): string {
  return FIXTURE_SESSION_TOKEN;
}

export function resolveBrowserRegressionFixtureSession(
  token: string | null
): SessionResponse | null {
  if (!isBrowserRegressionFixtureMode() || !hasFixtureAuthToken(token)) {
    return null;
  }
  return {
    user: { ...FIXTURE_SESSION.user },
    session: { ...FIXTURE_SESSION.session }
  };
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
    return ok<T>({
      user: { ...FIXTURE_SESSION.user },
      session: { ...FIXTURE_SESSION.session }
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
    const projection = resolveLayoutProjectionFixture(document.id);
    const runs = resolveLayoutRunsFixture(document.id);
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
          ? coverageValues.reduce((sum, value) => sum + value, 0) /
            coverageValues.length
          : null,
      structureConfidence:
        confidenceValues.length > 0
          ? confidenceValues.reduce((sum, value) => sum + value, 0) /
            confidenceValues.length
          : null
    };

    const payload: DocumentLayoutOverviewResponse = {
      documentId: document.id,
      projectId: project.id,
      projection,
      activeRun,
      latestRun,
      totalRuns: runs.length,
      pageCount: resolveDocumentPagesFixture(document.id).length,
      activeStatusCounts,
      activeRecallCounts,
      summary
    };
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
    const projection = resolvePreprocessProjectionFixture(document.id);
    const runs = resolvePreprocessRunsFixture(document.id);
    const activeRun = resolveActivePreprocessRun({ projection, runs });
    const latestRun = runs.length > 0 ? runs[0] : null;
    const activeResults = activeRun
      ? resolvePreprocessPageResultsFixture(activeRun.id)
      : [];
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
    const payload: DocumentPreprocessOverviewResponse = {
      documentId: document.id,
      projectId: project.id,
      projection,
      activeRun,
      latestRun,
      totalRuns: runs.length,
      pageCount: resolveDocumentPagesFixture(document.id).length,
      activeStatusCounts,
      activeQualityGateCounts,
      activeWarningCount: activeResults.reduce(
        (count, item) => count + item.warningsJson.length,
        0
      )
    };
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
