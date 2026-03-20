import type {
  DocumentGovernanceLedgerStatusResponse,
  DocumentGovernanceManifestStatusResponse,
  DocumentGovernanceOverviewResponse,
  DocumentLayoutOverviewResponse,
  DocumentPreprocessOverviewResponse,
  DocumentRedactionOverviewResponse,
  DocumentStatus,
  DocumentTimelineEvent,
  DocumentTranscriptionOverviewResponse
} from "@ukde/contracts";

export type DocumentPipelinePhaseId =
  | "INGEST"
  | "PREPROCESS"
  | "LAYOUT"
  | "TRANSCRIPTION"
  | "PRIVACY"
  | "GOVERNANCE";

export type DocumentPipelinePhaseStatus =
  | "NOT_STARTED"
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED"
  | "DEGRADED";

export interface DocumentPipelineStatusError {
  phaseId: DocumentPipelinePhaseId;
  detail: string;
}

export interface DocumentPipelinePhase {
  phaseId: DocumentPipelinePhaseId;
  status: DocumentPipelinePhaseStatus;
  percent: number | null;
  completedUnits: number | null;
  totalUnits: number | null;
  label: string;
  detail: string;
}

export interface DocumentPipelineStatusResponse {
  phases: DocumentPipelinePhase[];
  overallPercent: number | null;
  degraded: boolean;
  errors: DocumentPipelineStatusError[];
  recommendedPollMs: number;
}

type CountedRunStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELED";

type CountMap = Partial<Record<CountedRunStatus, number>>;

const COUNTED_STATUSES: CountedRunStatus[] = [
  "QUEUED",
  "RUNNING",
  "SUCCEEDED",
  "FAILED",
  "CANCELED"
];

const INGEST_STAGE_ORDER = ["UPLOAD", "SCAN", "EXTRACTION", "THUMBNAIL_RENDER"] as const;

function clampNonNegativeInteger(value: number | null | undefined): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.floor(value));
}

function toPercent(completed: number, total: number): number | null {
  if (!Number.isFinite(completed) || !Number.isFinite(total) || total <= 0) {
    return null;
  }
  const bounded = Math.min(100, Math.max(0, (completed / total) * 100));
  return Math.round(bounded);
}

function isActiveRunStatus(status: string | null | undefined): status is "QUEUED" | "RUNNING" {
  return status === "QUEUED" || status === "RUNNING";
}

function isTerminalRunStatus(status: string | null | undefined): status is "SUCCEEDED" | "FAILED" | "CANCELED" {
  return status === "SUCCEEDED" || status === "FAILED" || status === "CANCELED";
}

function normalizeCountMap(input: CountMap): Required<CountMap> {
  return {
    QUEUED: clampNonNegativeInteger(input.QUEUED),
    RUNNING: clampNonNegativeInteger(input.RUNNING),
    SUCCEEDED: clampNonNegativeInteger(input.SUCCEEDED),
    FAILED: clampNonNegativeInteger(input.FAILED),
    CANCELED: clampNonNegativeInteger(input.CANCELED)
  };
}

function resolveIngestStageLabel(
  runKind: (typeof INGEST_STAGE_ORDER)[number]
): string {
  switch (runKind) {
    case "UPLOAD":
      return "Upload";
    case "SCAN":
      return "Scan";
    case "EXTRACTION":
      return "Extraction";
    case "THUMBNAIL_RENDER":
      return "Thumbnail rendering";
    default:
      return "Ingest";
  }
}

function resolveIngestFallbackStatus(documentStatus: DocumentStatus): DocumentPipelinePhaseStatus {
  switch (documentStatus) {
    case "QUEUED":
      return "QUEUED";
    case "UPLOADING":
    case "SCANNING":
    case "EXTRACTING":
      return "RUNNING";
    case "READY":
      return "SUCCEEDED";
    case "FAILED":
      return "FAILED";
    case "CANCELED":
      return "CANCELED";
    default:
      return "NOT_STARTED";
  }
}

function resolveTimelineLatestByKind(
  timelineItems: DocumentTimelineEvent[]
): Map<(typeof INGEST_STAGE_ORDER)[number], DocumentTimelineEvent> {
  const sorted = [...timelineItems].sort((left, right) => {
    return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime();
  });

  const latest = new Map<(typeof INGEST_STAGE_ORDER)[number], DocumentTimelineEvent>();

  for (const item of sorted) {
    if (!INGEST_STAGE_ORDER.includes(item.runKind)) {
      continue;
    }
    if (item.supersededByProcessingRunId !== null) {
      continue;
    }
    if (!latest.has(item.runKind)) {
      latest.set(item.runKind, item);
    }
  }

  if (latest.size === INGEST_STAGE_ORDER.length) {
    return latest;
  }

  for (const item of sorted) {
    if (!INGEST_STAGE_ORDER.includes(item.runKind)) {
      continue;
    }
    if (!latest.has(item.runKind)) {
      latest.set(item.runKind, item);
    }
  }

  return latest;
}

function resolveCountedRunStatus(
  activeRunStatus: string | null | undefined,
  latestRunStatus: string | null | undefined
): DocumentPipelinePhaseStatus {
  if (activeRunStatus === "RUNNING") {
    return "RUNNING";
  }
  if (activeRunStatus === "QUEUED") {
    return "QUEUED";
  }
  if (latestRunStatus === "SUCCEEDED") {
    return "SUCCEEDED";
  }
  if (latestRunStatus === "FAILED") {
    return "FAILED";
  }
  if (latestRunStatus === "CANCELED") {
    return "CANCELED";
  }
  if (latestRunStatus === "RUNNING") {
    return "RUNNING";
  }
  if (latestRunStatus === "QUEUED") {
    return "QUEUED";
  }
  return "NOT_STARTED";
}

function resolveCountedPhaseDetail(
  status: DocumentPipelinePhaseStatus,
  completedUnits: number,
  totalUnits: number,
  phaseLabel: string
): string {
  if (status === "NOT_STARTED") {
    return `${phaseLabel} has no recorded run yet.`;
  }
  if (status === "DEGRADED") {
    return `${phaseLabel} status polling is degraded.`;
  }
  if (status === "RUNNING" || status === "QUEUED") {
    if (totalUnits > 0) {
      return `${phaseLabel} is active (${completedUnits}/${totalUnits} pages settled).`;
    }
    return `${phaseLabel} is active.`;
  }
  if (status === "SUCCEEDED") {
    if (totalUnits > 0) {
      return `${phaseLabel} completed (${completedUnits}/${totalUnits} pages settled).`;
    }
    return `${phaseLabel} completed.`;
  }
  if (status === "FAILED") {
    if (totalUnits > 0) {
      return `${phaseLabel} failed (${completedUnits}/${totalUnits} pages settled).`;
    }
    return `${phaseLabel} failed.`;
  }
  if (status === "CANCELED") {
    if (totalUnits > 0) {
      return `${phaseLabel} was canceled (${completedUnits}/${totalUnits} pages settled).`;
    }
    return `${phaseLabel} was canceled.`;
  }
  return `${phaseLabel} status is available.`;
}

export function createDegradedPipelinePhase(
  phaseId: DocumentPipelinePhaseId,
  label: string,
  detail: string
): DocumentPipelinePhase {
  return {
    phaseId,
    status: "DEGRADED",
    percent: null,
    completedUnits: null,
    totalUnits: null,
    label,
    detail
  };
}

export function computeIngestPipelinePhase(
  documentStatus: DocumentStatus,
  timelineItems: DocumentTimelineEvent[]
): DocumentPipelinePhase {
  const latestByKind = resolveTimelineLatestByKind(timelineItems);
  const completedStages = INGEST_STAGE_ORDER.filter((runKind) => {
    const latest = latestByKind.get(runKind);
    return latest?.status === "SUCCEEDED";
  }).length;

  const failedStage = INGEST_STAGE_ORDER.find((runKind) => {
    const latest = latestByKind.get(runKind);
    return latest?.status === "FAILED" || latest?.status === "CANCELED";
  });

  const activeStage = INGEST_STAGE_ORDER.find((runKind) => {
    const latest = latestByKind.get(runKind);
    return isActiveRunStatus(latest?.status ?? null);
  });

  let status: DocumentPipelinePhaseStatus;
  let detail: string;

  if (failedStage) {
    const failedRecord = latestByKind.get(failedStage);
    status = failedRecord?.status === "CANCELED" ? "CANCELED" : "FAILED";
    detail =
      failedRecord?.failureReason?.trim() ||
      `${resolveIngestStageLabel(failedStage)} did not complete.`;
  } else if (activeStage) {
    const activeRecord = latestByKind.get(activeStage);
    status = activeRecord?.status === "QUEUED" ? "QUEUED" : "RUNNING";
    detail = `${resolveIngestStageLabel(activeStage)} is ${
      status === "QUEUED" ? "queued" : "running"
    }.`;
  } else if (completedStages >= INGEST_STAGE_ORDER.length || documentStatus === "READY") {
    status = "SUCCEEDED";
    detail = "Upload, scan, extraction, and thumbnail stages are complete.";
  } else {
    status = resolveIngestFallbackStatus(documentStatus);
    if (status === "NOT_STARTED") {
      detail = "Ingest has not started for this document yet.";
    } else if (status === "QUEUED") {
      detail = "Ingest is queued.";
    } else if (status === "RUNNING") {
      detail = "Ingest is running.";
    } else if (status === "FAILED") {
      detail = "Ingest failed.";
    } else if (status === "CANCELED") {
      detail = "Ingest was canceled.";
    } else {
      detail = "Ingest is complete.";
    }
  }

  return {
    phaseId: "INGEST",
    status,
    percent: toPercent(completedStages, INGEST_STAGE_ORDER.length),
    completedUnits: completedStages,
    totalUnits: INGEST_STAGE_ORDER.length,
    label: "Ingest",
    detail
  };
}

export function computeCountBasedPipelinePhase(input: {
  phaseId: Extract<DocumentPipelinePhaseId, "PREPROCESS" | "LAYOUT" | "TRANSCRIPTION">;
  label: string;
  pageCount: number;
  statusCounts: CountMap;
  activeRunStatus: string | null | undefined;
  latestRunStatus: string | null | undefined;
}): DocumentPipelinePhase {
  const normalizedCounts = normalizeCountMap(input.statusCounts);
  const completedUnits =
    normalizedCounts.SUCCEEDED + normalizedCounts.FAILED + normalizedCounts.CANCELED;
  const totalUnits = clampNonNegativeInteger(input.pageCount);
  const status = resolveCountedRunStatus(input.activeRunStatus, input.latestRunStatus);

  return {
    phaseId: input.phaseId,
    status,
    percent: toPercent(completedUnits, totalUnits),
    completedUnits,
    totalUnits,
    label: input.label,
    detail: resolveCountedPhaseDetail(status, completedUnits, totalUnits, input.label)
  };
}

export function computePrivacyPipelinePhase(
  overview: DocumentRedactionOverviewResponse
): DocumentPipelinePhase {
  const completedUnits =
    clampNonNegativeInteger(overview.previewReadyPages) +
    clampNonNegativeInteger(overview.previewFailedPages);
  const totalUnits = clampNonNegativeInteger(overview.previewTotalPages);

  const activeRunStatus = overview.activeRun?.status ?? null;
  const latestRunStatus = overview.latestRun?.status ?? null;
  const status = resolveCountedRunStatus(activeRunStatus, latestRunStatus);

  return {
    phaseId: "PRIVACY",
    status,
    percent: toPercent(completedUnits, totalUnits),
    completedUnits,
    totalUnits,
    label: "Privacy",
    detail:
      totalUnits > 0
        ? `Safeguarded preview generation settled ${completedUnits}/${totalUnits} pages.`
        : resolveCountedPhaseDetail(status, completedUnits, totalUnits, "Privacy")
  };
}

function hasGovernanceArtifactCompleted(
  status: DocumentGovernanceManifestStatusResponse["status"] | DocumentGovernanceLedgerStatusResponse["status"] | undefined,
  readyId: string | null | undefined,
  latestSha256: string | null | undefined
): boolean {
  return status === "SUCCEEDED" || Boolean(readyId) || Boolean(latestSha256);
}

export function computeGovernancePipelinePhase(input: {
  overview: DocumentGovernanceOverviewResponse;
  manifestStatus: DocumentGovernanceManifestStatusResponse | null;
  ledgerStatus: DocumentGovernanceLedgerStatusResponse | null;
}): DocumentPipelinePhase {
  const latestRun = input.overview.latestRun;

  if (!latestRun && !input.overview.activeRunId) {
    return {
      phaseId: "GOVERNANCE",
      status: "NOT_STARTED",
      percent: null,
      completedUnits: 0,
      totalUnits: 3,
      label: "Governance",
      detail: "Governance has no run history yet."
    };
  }

  const manifestDone = hasGovernanceArtifactCompleted(
    input.manifestStatus?.status,
    input.manifestStatus?.readyManifestId,
    input.manifestStatus?.latestManifestSha256 ?? latestRun?.latestManifestSha256
  );
  const ledgerDone = hasGovernanceArtifactCompleted(
    input.ledgerStatus?.status,
    input.ledgerStatus?.readyLedgerId,
    input.ledgerStatus?.latestLedgerSha256 ?? latestRun?.latestLedgerSha256
  );
  const verificationDone =
    input.ledgerStatus?.ledgerVerificationStatus === "VALID" ||
    latestRun?.ledgerVerificationStatus === "VALID";

  const completedUnits = Number(manifestDone) + Number(ledgerDone) + Number(verificationDone);
  const totalUnits = 3;

  let status: DocumentPipelinePhaseStatus = "QUEUED";
  if (latestRun?.readinessStatus === "READY") {
    status = "SUCCEEDED";
  } else if (
    latestRun?.readinessStatus === "FAILED" ||
    latestRun?.runStatus === "FAILED"
  ) {
    status = "FAILED";
  } else if (
    latestRun?.runStatus === "CANCELED" ||
    latestRun?.generationStatus === "CANCELED"
  ) {
    status = "CANCELED";
  } else if (latestRun?.runStatus === "RUNNING" || latestRun?.generationStatus === "RUNNING") {
    status = "RUNNING";
  } else if (latestRun?.runStatus === "QUEUED") {
    status = "QUEUED";
  }

  const hasActiveArtifactWork =
    input.manifestStatus?.status === "RUNNING" ||
    input.manifestStatus?.status === "QUEUED" ||
    input.ledgerStatus?.status === "RUNNING" ||
    input.ledgerStatus?.status === "QUEUED";

  const percent =
    status === "RUNNING" || status === "QUEUED" || hasActiveArtifactWork
      ? completedUnits >= totalUnits
        ? 100
        : null
      : toPercent(completedUnits, totalUnits);

  let detail = `Governance milestones completed ${completedUnits}/${totalUnits}.`;
  if (status === "SUCCEEDED") {
    detail = "Manifest, ledger, and verification milestones are complete.";
  } else if (status === "FAILED") {
    detail = "Governance generation failed. Review run-level readiness and artifact status.";
  } else if (status === "CANCELED") {
    detail = "Governance generation was canceled.";
  }

  return {
    phaseId: "GOVERNANCE",
    status,
    percent,
    completedUnits,
    totalUnits,
    label: "Governance",
    detail
  };
}

export function mergeProcessingTimelineStatuses(
  timelineItems: DocumentTimelineEvent[],
  statusEntries: Array<{
    runId: string;
    status: CountedRunStatus;
    failureReason: string | null;
    startedAt: string | null;
    finishedAt: string | null;
    canceledAt: string | null;
  }>
): DocumentTimelineEvent[] {
  if (statusEntries.length === 0) {
    return timelineItems;
  }
  const statusMap = new Map(statusEntries.map((entry) => [entry.runId, entry]));
  return timelineItems.map((item) => {
    const update = statusMap.get(item.id);
    if (!update) {
      return item;
    }
    return {
      ...item,
      status: update.status,
      failureReason: update.failureReason,
      startedAt: update.startedAt,
      finishedAt: update.finishedAt,
      canceledAt: update.canceledAt
    };
  });
}

export function computeOverallPipelinePercent(phases: DocumentPipelinePhase[]): number | null {
  const numeric = phases
    .map((phase) => phase.percent)
    .filter((value): value is number => typeof value === "number");

  if (numeric.length === 0) {
    return null;
  }

  const sum = numeric.reduce((total, value) => total + value, 0);
  return Math.round(sum / numeric.length);
}

export function resolvePipelineErrors(
  entries: Array<{ phaseId: DocumentPipelinePhaseId; detail: string | null | undefined }>
): DocumentPipelineStatusError[] {
  return entries
    .map((entry) => ({
      phaseId: entry.phaseId,
      detail: (entry.detail ?? "").trim()
    }))
    .filter((entry) => entry.detail.length > 0);
}

export function toCountMapFromOverview(
  counts: Record<string, number>
): CountMap {
  const normalized: CountMap = {};
  for (const status of COUNTED_STATUSES) {
    const raw = counts[status];
    if (typeof raw === "number" && Number.isFinite(raw)) {
      normalized[status] = Math.max(0, Math.floor(raw));
    }
  }
  return normalized;
}

export function computePreprocessPipelinePhase(
  overview: DocumentPreprocessOverviewResponse
): DocumentPipelinePhase {
  return computeCountBasedPipelinePhase({
    phaseId: "PREPROCESS",
    label: "Preprocess",
    pageCount: overview.pageCount,
    statusCounts: toCountMapFromOverview(overview.activeStatusCounts),
    activeRunStatus: overview.activeRun?.status,
    latestRunStatus: overview.latestRun?.status
  });
}

export function computeLayoutPipelinePhase(
  overview: DocumentLayoutOverviewResponse
): DocumentPipelinePhase {
  return computeCountBasedPipelinePhase({
    phaseId: "LAYOUT",
    label: "Layout",
    pageCount: overview.pageCount,
    statusCounts: toCountMapFromOverview(overview.activeStatusCounts),
    activeRunStatus: overview.activeRun?.status,
    latestRunStatus: overview.latestRun?.status
  });
}

export function computeTranscriptionPipelinePhase(
  overview: DocumentTranscriptionOverviewResponse
): DocumentPipelinePhase {
  return computeCountBasedPipelinePhase({
    phaseId: "TRANSCRIPTION",
    label: "Transcription",
    pageCount: overview.pageCount,
    statusCounts: toCountMapFromOverview(overview.activeStatusCounts),
    activeRunStatus: overview.activeRun?.status,
    latestRunStatus: overview.latestRun?.status
  });
}

export function hasActiveTimelineRuns(items: DocumentTimelineEvent[]): boolean {
  return items.some((item) => isActiveRunStatus(item.status));
}

export function normalizePipelinePhaseOrder(
  phases: DocumentPipelinePhase[]
): DocumentPipelinePhase[] {
  const order: DocumentPipelinePhaseId[] = [
    "INGEST",
    "PREPROCESS",
    "LAYOUT",
    "TRANSCRIPTION",
    "PRIVACY",
    "GOVERNANCE"
  ];

  const index = new Map(order.map((phaseId, idx) => [phaseId, idx]));
  return [...phases].sort((left, right) => {
    return (index.get(left.phaseId) ?? 999) - (index.get(right.phaseId) ?? 999);
  });
}

export function isTerminalPipelineStatus(status: DocumentPipelinePhaseStatus): boolean {
  return status === "SUCCEEDED" || status === "FAILED" || status === "CANCELED";
}

export function isActivePipelineStatus(status: DocumentPipelinePhaseStatus): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

export function toPipelineStatusTone(
  status: DocumentPipelinePhaseStatus
): "danger" | "info" | "neutral" | "success" | "warning" {
  if (status === "SUCCEEDED") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED" || status === "NOT_STARTED") {
    return "neutral";
  }
  if (status === "RUNNING") {
    return "info";
  }
  return "warning";
}
