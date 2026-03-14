import {
  VIEWER_ZOOM_DEFAULT,
  VIEWER_ZOOM_MAX,
  VIEWER_ZOOM_MIN
} from "./url-state";

export interface QueryInput {
  [key: string]: string | number | boolean | null | undefined;
}

export type ViewerMode = "original" | "preprocessed" | "compare";
export type ViewerComparePair =
  | "original_gray"
  | "original_binary"
  | "gray_binary";
export type LayoutTab = "overview" | "triage" | "runs";
export type TranscriptionTab = "overview" | "triage" | "runs" | "artefacts";
export type TranscriptionSourceKind =
  | "LINE"
  | "RESCUE_CANDIDATE"
  | "PAGE_WINDOW";
export type TranscriptionWorkspaceMode = "reading-order" | "as-on-page";

function encodePathSegment(value: string): string {
  return encodeURIComponent(value);
}

export function toQueryString(input: QueryInput): string {
  const entries = Object.entries(input)
    .filter(
      ([, value]) => value !== undefined && value !== null && value !== ""
    )
    .map(([key, value]) => [key, String(value)] as const)
    .sort(([a], [b]) => a.localeCompare(b));

  if (entries.length === 0) {
    return "";
  }

  const params = new URLSearchParams();
  for (const [key, value] of entries) {
    params.set(key, value);
  }

  return `?${params.toString()}`;
}

export function withQuery(path: string, input: QueryInput): string {
  return `${path}${toQueryString(input)}`;
}

export const rootPath = "/";
export const loginPath = "/login";
export const logoutPath = "/logout";
export const healthPath = "/health";
export const errorPath = "/error";
export const projectsPath = "/projects";
export const approvedModelsPath = "/approved-models";
export const activityPath = "/activity";
export const adminPath = "/admin";
export const adminAuditPath = "/admin/audit";
export const adminSecurityPath = "/admin/security";
export const adminOperationsPath = "/admin/operations";
export const adminOperationsExportStatusPath = "/admin/operations/export-status";
export const adminOperationsSlosPath = "/admin/operations/slos";
export const adminOperationsAlertsPath = "/admin/operations/alerts";
export const adminOperationsTimelinesPath = "/admin/operations/timelines";
export const adminDesignSystemPath = "/admin/design-system";

export function projectAnchorPath(projectId: string): string {
  return `/projects/${encodePathSegment(projectId)}`;
}

export function projectOverviewPath(projectId: string): string {
  return `${projectAnchorPath(projectId)}/overview`;
}

export function projectDocumentsPath(projectId: string): string {
  return `${projectAnchorPath(projectId)}/documents`;
}

export function projectDocumentImportPath(projectId: string): string {
  return `${projectDocumentsPath(projectId)}/import`;
}

export function projectDocumentPath(
  projectId: string,
  documentId: string
): string {
  return `${projectDocumentsPath(projectId)}/${encodePathSegment(documentId)}`;
}

export type PreprocessingTab = "pages" | "quality" | "runs" | "metadata";

export function projectDocumentPreprocessingPath(
  projectId: string,
  documentId: string,
  options?: { tab?: Exclude<PreprocessingTab, "quality"> | null }
): string {
  const tab = options?.tab;
  return withQuery(`${projectDocumentPath(projectId, documentId)}/preprocessing`, {
    tab: tab && tab !== "pages" ? tab : undefined
  });
}

export function projectDocumentPreprocessingQualityPath(
  projectId: string,
  documentId: string,
  options?: {
    blurMax?: number | null;
    compareBaseRunId?: string | null;
    cursor?: number | null;
    failedOnly?: boolean | null;
    pageSize?: number | null;
    runId?: string | null;
    skewMax?: number | null;
    skewMin?: number | null;
    status?: string | null;
    warning?: string | null;
  }
): string {
  return withQuery(`${projectDocumentPath(projectId, documentId)}/preprocessing/quality`, {
    blurMax: options?.blurMax ?? undefined,
    compareBaseRunId: options?.compareBaseRunId ?? undefined,
    cursor: options?.cursor ?? undefined,
    failedOnly: options?.failedOnly ? 1 : undefined,
    pageSize: options?.pageSize ?? undefined,
    runId: options?.runId ?? undefined,
    skewMax: options?.skewMax ?? undefined,
    skewMin: options?.skewMin ?? undefined,
    status: options?.status ?? undefined,
    warning: options?.warning ?? undefined
  });
}

export function projectDocumentPreprocessingRunPath(
  projectId: string,
  documentId: string,
  runId: string
): string {
  return `${projectDocumentPath(projectId, documentId)}/preprocessing/runs/${encodePathSegment(runId)}`;
}

export function projectDocumentPreprocessingComparePath(
  projectId: string,
  documentId: string,
  baseRunId?: string | null,
  candidateRunId?: string | null,
  options?: {
    page?: number | null;
    viewerComparePair?: ViewerComparePair | null;
    viewerMode?: ViewerMode | null;
    viewerRunId?: string | null;
  }
): string {
  return withQuery(`${projectDocumentPath(projectId, documentId)}/preprocessing/compare`, {
    baseRunId: baseRunId ?? undefined,
    candidateRunId: candidateRunId ?? undefined,
    page:
      typeof options?.page === "number" && Number.isFinite(options.page)
        ? Math.max(1, Math.round(options.page))
        : undefined,
    viewerMode:
      options?.viewerMode && options.viewerMode !== "original"
        ? options.viewerMode
        : undefined,
    viewerComparePair:
      options?.viewerMode === "compare" &&
      options.viewerComparePair &&
      options.viewerComparePair !== "original_gray"
        ? options.viewerComparePair
        : undefined,
    viewerRunId:
      options?.viewerRunId && options.viewerRunId.trim().length > 0
        ? options.viewerRunId.trim()
        : undefined
  });
}

export function projectDocumentLayoutPath(
  projectId: string,
  documentId: string,
  options?: { runId?: string | null; tab?: LayoutTab | null }
): string {
  const tab = options?.tab;
  return withQuery(`${projectDocumentPath(projectId, documentId)}/layout`, {
    runId:
      options?.runId && options.runId.trim().length > 0
        ? options.runId.trim()
        : undefined,
    tab: tab && tab !== "overview" ? tab : undefined
  });
}

export function projectDocumentLayoutRunPath(
  projectId: string,
  documentId: string,
  runId: string
): string {
  return `${projectDocumentPath(projectId, documentId)}/layout/runs/${encodePathSegment(runId)}`;
}

export function projectDocumentLayoutWorkspacePath(
  projectId: string,
  documentId: string,
  options?: {
    page?: number | null;
    runId?: string | null;
  }
): string {
  const page =
    typeof options?.page === "number" && Number.isFinite(options.page)
      ? Math.max(1, Math.round(options.page))
      : undefined;
  return withQuery(`${projectDocumentPath(projectId, documentId)}/layout/workspace`, {
    page,
    runId:
      options?.runId && options.runId.trim().length > 0
        ? options.runId.trim()
        : undefined
  });
}

export function projectDocumentTranscriptionPath(
  projectId: string,
  documentId: string,
  options?: { runId?: string | null; tab?: TranscriptionTab | null }
): string {
  const tab = options?.tab;
  return withQuery(`${projectDocumentPath(projectId, documentId)}/transcription`, {
    runId:
      options?.runId && options.runId.trim().length > 0
        ? options.runId.trim()
        : undefined,
    tab: tab && tab !== "overview" ? tab : undefined
  });
}

export function projectDocumentTranscriptionRunPath(
  projectId: string,
  documentId: string,
  runId: string
): string {
  return `${projectDocumentPath(projectId, documentId)}/transcription/runs/${encodePathSegment(runId)}`;
}

export function projectDocumentTranscriptionWorkspacePath(
  projectId: string,
  documentId: string,
  options?: {
    lineId?: string | null;
    mode?: TranscriptionWorkspaceMode | null;
    page?: number | null;
    runId?: string | null;
    sourceKind?: TranscriptionSourceKind | null;
    sourceRefId?: string | null;
    tokenId?: string | null;
  }
): string {
  const page =
    typeof options?.page === "number" && Number.isFinite(options.page)
      ? Math.max(1, Math.round(options.page))
      : undefined;
  return withQuery(`${projectDocumentPath(projectId, documentId)}/transcription/workspace`, {
    page,
    runId:
      options?.runId && options.runId.trim().length > 0
        ? options.runId.trim()
        : undefined,
    mode:
      options?.mode === "as-on-page" || options?.mode === "reading-order"
        ? options.mode
        : undefined,
    lineId:
      options?.lineId && options.lineId.trim().length > 0
        ? options.lineId.trim()
        : undefined,
    tokenId:
      options?.tokenId && options.tokenId.trim().length > 0
        ? options.tokenId.trim()
        : undefined,
    sourceKind: options?.sourceKind ?? undefined,
    sourceRefId:
      options?.sourceRefId && options.sourceRefId.trim().length > 0
        ? options.sourceRefId.trim()
        : undefined
  });
}

export function projectDocumentTranscriptionComparePath(
  projectId: string,
  documentId: string,
  baseRunId?: string | null,
  candidateRunId?: string | null,
  options?: {
    lineId?: string | null;
    page?: number | null;
    tokenId?: string | null;
  }
): string {
  const page =
    typeof options?.page === "number" && Number.isFinite(options.page)
      ? Math.max(1, Math.round(options.page))
      : undefined;
  return withQuery(`${projectDocumentPath(projectId, documentId)}/transcription/compare`, {
    baseRunId: baseRunId && baseRunId.trim().length > 0 ? baseRunId.trim() : undefined,
    candidateRunId:
      candidateRunId && candidateRunId.trim().length > 0
        ? candidateRunId.trim()
        : undefined,
    page,
    lineId:
      options?.lineId && options.lineId.trim().length > 0
        ? options.lineId.trim()
        : undefined,
    tokenId:
      options?.tokenId && options.tokenId.trim().length > 0
        ? options.tokenId.trim()
        : undefined
  });
}

function normalizeViewerZoom(value: number | null | undefined): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return undefined;
  }
  return Math.max(VIEWER_ZOOM_MIN, Math.min(VIEWER_ZOOM_MAX, Math.round(value)));
}

export function projectDocumentViewerPath(
  projectId: string,
  documentId: string,
  page: number,
  options?: {
    zoom?: number | null;
    mode?: ViewerMode | null;
    comparePair?: ViewerComparePair | null;
    runId?: string | null;
  }
): string {
  const zoom = normalizeViewerZoom(options?.zoom);
  return withQuery(`${projectDocumentPath(projectId, documentId)}/viewer`, {
    page,
    mode:
      options?.mode && options.mode !== "original" ? options.mode : undefined,
    runId:
      options?.mode &&
      options.mode !== "original" &&
      options?.runId &&
      options.runId.trim().length > 0
        ? options.runId.trim()
        : undefined,
    comparePair:
      options?.mode === "compare" &&
      options?.comparePair &&
      options.comparePair !== "original_gray"
        ? options.comparePair
        : undefined,
    zoom: typeof zoom === "number" && zoom !== VIEWER_ZOOM_DEFAULT ? zoom : undefined
  });
}

export function projectDocumentIngestStatusPath(
  projectId: string,
  documentId: string,
  options?: { page?: number | null; zoom?: number | null }
): string {
  const normalizedPage =
    typeof options?.page === "number" && Number.isFinite(options.page)
      ? Math.max(1, Math.round(options.page))
      : undefined;
  const zoom = normalizeViewerZoom(options?.zoom);
  return withQuery(
    `${projectDocumentPath(projectId, documentId)}/ingest-status`,
    {
      page: normalizedPage,
      zoom:
        typeof zoom === "number" && zoom !== VIEWER_ZOOM_DEFAULT
          ? zoom
          : undefined
    }
  );
}

export function projectJobsPath(projectId: string): string {
  return `${projectAnchorPath(projectId)}/jobs`;
}

export function projectJobPath(projectId: string, jobId: string): string {
  return `${projectJobsPath(projectId)}/${encodePathSegment(jobId)}`;
}

export function projectActivityPath(projectId: string): string {
  return `${projectAnchorPath(projectId)}/activity`;
}

export function projectSettingsPath(projectId: string): string {
  return `${projectAnchorPath(projectId)}/settings`;
}

export function projectModelAssignmentsPath(projectId: string): string {
  return `${projectAnchorPath(projectId)}/model-assignments`;
}

export function projectModelAssignmentPath(
  projectId: string,
  assignmentId: string
): string {
  return `${projectModelAssignmentsPath(projectId)}/${encodePathSegment(assignmentId)}`;
}

export function projectModelAssignmentDatasetsPath(
  projectId: string,
  assignmentId: string
): string {
  return `${projectModelAssignmentPath(projectId, assignmentId)}/datasets`;
}
