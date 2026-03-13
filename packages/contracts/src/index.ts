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

export type JobType = "NOOP";
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

export const shellStateBreakpoints: ShellStateBreakpoint[] = [
  { state: "Expanded", minWidth: 1360 },
  { state: "Balanced", minWidth: 1080 },
  { state: "Compact", minWidth: 820 }
];

export function resolveShellState(
  viewportWidth: number,
  forceFocus: boolean = false
): ShellState {
  if (forceFocus) {
    return "Focus";
  }

  for (const breakpoint of shellStateBreakpoints) {
    if (viewportWidth >= breakpoint.minWidth) {
      return breakpoint.state;
    }
  }
  return "Focus";
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
