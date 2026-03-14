import type { AuditEventType, OperationsAlertState, OperationsTimelineScope } from "@ukde/contracts";

type Primitive = string | number | boolean | null;
type QueryKeyPart = Primitive | ReadonlyArray<QueryKeyPart> | { readonly [key: string]: QueryKeyPart };

export type QueryKey = ReadonlyArray<QueryKeyPart>;

interface CursorPageFilter {
  cursor?: number;
  pageSize?: number;
}

interface AuditListFilter extends CursorPageFilter {
  actorUserId?: string;
  eventType?: AuditEventType;
  from?: string;
  projectId?: string;
  to?: string;
}

interface ApprovedModelListFilter {
  modelRole?: string;
  status?: string;
}

interface ExportRequestsFilter {
  candidateKind?: string;
  cursor?: string;
  requesterId?: string;
  status?: string;
}

interface ExportReviewFilter {
  agingBucket?: string;
  reviewerUserId?: string;
  status?: string;
}

interface DocumentListFilter extends CursorPageFilter {
  direction?: "asc" | "desc";
  from?: string;
  q?: string;
  search?: string;
  sort?: "created" | "name" | "updated";
  status?: string;
  to?: string;
  uploader?: string;
}

interface PreprocessRunListFilter extends CursorPageFilter {}

interface PreprocessQualityFilter extends CursorPageFilter {
  runId?: string;
  status?: string;
  warning?: string;
}

interface PreprocessRunPagesFilter extends CursorPageFilter {
  status?: string;
  warning?: string;
}

interface LayoutRunListFilter extends CursorPageFilter {}

interface LayoutRunPagesFilter extends CursorPageFilter {
  pageRecallStatus?: string;
  status?: string;
}

interface TranscriptionRunListFilter extends CursorPageFilter {}

interface TranscriptionTriageFilter extends CursorPageFilter {
  confidenceBelow?: number;
  page?: number;
  runId?: string;
  status?: string;
}

interface TranscriptionMetricsFilter {
  confidenceBelow?: number;
  runId?: string;
}

interface TranscriptionRunPagesFilter extends CursorPageFilter {
  status?: string;
}

interface TranscriptionVariantLayersFilter {
  variantKind?: string;
}

interface PageVariantsFilter {
  runId?: string;
}

function normalizeText(value?: string): string | null {
  if (!value) {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length === 0 ? null : trimmed;
}

function normalizeNumber(value?: number): number | null {
  return typeof value === "number" ? value : null;
}

export const queryKeys = {
  auth: {
    providers: () => ["auth", "providers"] as const,
    session: () => ["auth", "session"] as const
  },
  audit: {
    detail: (eventId: string) => ["audit", "detail", eventId] as const,
    integrity: () => ["audit", "integrity"] as const,
    list: (filters: AuditListFilter) =>
      [
        "audit",
        "list",
        {
          actorUserId: normalizeText(filters.actorUserId),
          cursor: normalizeNumber(filters.cursor),
          eventType: normalizeText(filters.eventType),
          from: normalizeText(filters.from),
          pageSize: normalizeNumber(filters.pageSize),
          projectId: normalizeText(filters.projectId),
          to: normalizeText(filters.to)
        }
      ] as const,
    myActivity: (limit: number) =>
      ["audit", "my-activity", { limit }] as const
  },
  models: {
    approvedList: (filters: ApprovedModelListFilter) =>
      [
        "models",
        "approved-list",
        {
          modelRole: normalizeText(filters.modelRole),
          status: normalizeText(filters.status)
        }
      ] as const
  },
  documents: {
    detail: (projectId: string, documentId: string) =>
      ["projects", projectId, "documents", "detail", documentId] as const,
    importStatus: (projectId: string, importId: string) =>
      ["projects", projectId, "documents", "import-status", importId] as const,
    list: (projectId: string, filters: DocumentListFilter) =>
      [
        "projects",
        projectId,
        "documents",
        "list",
        {
          cursor: normalizeNumber(filters.cursor),
          direction: normalizeText(filters.direction),
          from: normalizeText(filters.from),
          pageSize: normalizeNumber(filters.pageSize),
          search: normalizeText(filters.search ?? filters.q),
          sort: normalizeText(filters.sort),
          status: normalizeText(filters.status),
          to: normalizeText(filters.to),
          uploader: normalizeText(filters.uploader)
        }
      ] as const,
    pageDetail: (projectId: string, documentId: string, pageId: string) =>
      [
        "projects",
        projectId,
        "documents",
        "page-detail",
        documentId,
        pageId
      ] as const,
    pageVariants: (
      projectId: string,
      documentId: string,
      pageId: string,
      filters: PageVariantsFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "page-variants",
        documentId,
        pageId,
        {
          runId: normalizeText(filters.runId)
        }
      ] as const,
    pages: (projectId: string, documentId: string) =>
      ["projects", projectId, "documents", "pages", documentId] as const,
    preprocessActiveRun: (projectId: string, documentId: string) =>
      [
        "projects",
        projectId,
        "documents",
        "preprocess-active-run",
        documentId
      ] as const,
    preprocessCompare: (
      projectId: string,
      documentId: string,
      baseRunId: string,
      candidateRunId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "preprocess-compare",
        documentId,
        baseRunId,
        candidateRunId
      ] as const,
    preprocessOverview: (projectId: string, documentId: string) =>
      [
        "projects",
        projectId,
        "documents",
        "preprocess-overview",
        documentId
      ] as const,
    preprocessQuality: (
      projectId: string,
      documentId: string,
      filters: PreprocessQualityFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "preprocess-quality",
        documentId,
        {
          cursor: normalizeNumber(filters.cursor),
          pageSize: normalizeNumber(filters.pageSize),
          runId: normalizeText(filters.runId),
          status: normalizeText(filters.status),
          warning: normalizeText(filters.warning)
        }
      ] as const,
    preprocessRunDetail: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "preprocess-run-detail",
        documentId,
        runId
      ] as const,
    preprocessRunPage: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "preprocess-run-page",
        documentId,
        runId,
        pageId
      ] as const,
    preprocessRunPages: (
      projectId: string,
      documentId: string,
      runId: string,
      filters: PreprocessRunPagesFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "preprocess-run-pages",
        documentId,
        runId,
        {
          cursor: normalizeNumber(filters.cursor),
          pageSize: normalizeNumber(filters.pageSize),
          status: normalizeText(filters.status),
          warning: normalizeText(filters.warning)
        }
      ] as const,
    preprocessRuns: (
      projectId: string,
      documentId: string,
      filters: PreprocessRunListFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "preprocess-runs",
        documentId,
        {
          cursor: normalizeNumber(filters.cursor),
          pageSize: normalizeNumber(filters.pageSize)
        }
      ] as const,
    preprocessRunStatus: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "preprocess-run-status",
        documentId,
        runId
      ] as const,
    layoutActiveRun: (projectId: string, documentId: string) =>
      [
        "projects",
        projectId,
        "documents",
        "layout-active-run",
        documentId
      ] as const,
    layoutOverview: (projectId: string, documentId: string) =>
      [
        "projects",
        projectId,
        "documents",
        "layout-overview",
        documentId
      ] as const,
    layoutRuns: (
      projectId: string,
      documentId: string,
      filters: LayoutRunListFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "layout-runs",
        documentId,
        {
          cursor: normalizeNumber(filters.cursor),
          pageSize: normalizeNumber(filters.pageSize)
        }
      ] as const,
    layoutRunDetail: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "layout-run-detail",
        documentId,
        runId
      ] as const,
    layoutRunStatus: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "layout-run-status",
        documentId,
        runId
      ] as const,
    layoutRunPages: (
      projectId: string,
      documentId: string,
      runId: string,
      filters: LayoutRunPagesFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "layout-run-pages",
        documentId,
        runId,
        {
          cursor: normalizeNumber(filters.cursor),
          pageSize: normalizeNumber(filters.pageSize),
          pageRecallStatus: normalizeText(filters.pageRecallStatus),
          status: normalizeText(filters.status)
        }
      ] as const,
    layoutPageOverlay: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "layout-page-overlay",
        documentId,
        runId,
        pageId
      ] as const,
    layoutPageRecallStatus: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "layout-page-recall-status",
        documentId,
        runId,
        pageId
      ] as const,
    layoutPageRescueCandidates: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "layout-page-rescue-candidates",
        documentId,
        runId,
        pageId
      ] as const,
    transcriptionOverview: (projectId: string, documentId: string) =>
      [
        "projects",
        projectId,
        "documents",
        "transcription-overview",
        documentId
      ] as const,
    transcriptionTriage: (
      projectId: string,
      documentId: string,
      filters: TranscriptionTriageFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "transcription-triage",
        documentId,
        {
          confidenceBelow:
            typeof filters.confidenceBelow === "number"
              ? filters.confidenceBelow
              : null,
          cursor: normalizeNumber(filters.cursor),
          page: normalizeNumber(filters.page),
          pageSize: normalizeNumber(filters.pageSize),
          runId: normalizeText(filters.runId),
          status: normalizeText(filters.status)
        }
      ] as const,
    transcriptionMetrics: (
      projectId: string,
      documentId: string,
      filters: TranscriptionMetricsFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "transcription-metrics",
        documentId,
        {
          confidenceBelow:
            typeof filters.confidenceBelow === "number"
              ? filters.confidenceBelow
              : null,
          runId: normalizeText(filters.runId)
        }
      ] as const,
    transcriptionRuns: (
      projectId: string,
      documentId: string,
      filters: TranscriptionRunListFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "transcription-runs",
        documentId,
        {
          cursor: normalizeNumber(filters.cursor),
          pageSize: normalizeNumber(filters.pageSize)
        }
      ] as const,
    transcriptionActiveRun: (projectId: string, documentId: string) =>
      [
        "projects",
        projectId,
        "documents",
        "transcription-active-run",
        documentId
      ] as const,
    transcriptionRunDetail: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "transcription-run-detail",
        documentId,
        runId
      ] as const,
    transcriptionRunStatus: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "transcription-run-status",
        documentId,
        runId
      ] as const,
    transcriptionRunPages: (
      projectId: string,
      documentId: string,
      runId: string,
      filters: TranscriptionRunPagesFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "transcription-run-pages",
        documentId,
        runId,
        {
          cursor: normalizeNumber(filters.cursor),
          pageSize: normalizeNumber(filters.pageSize),
          status: normalizeText(filters.status)
        }
      ] as const,
    transcriptionRunPageLines: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "transcription-run-page-lines",
        documentId,
        runId,
        pageId
      ] as const,
    transcriptionRunPageTokens: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "transcription-run-page-tokens",
        documentId,
        runId,
        pageId
      ] as const,
    transcriptionRunPageVariantLayers: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string,
      filters: TranscriptionVariantLayersFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "transcription-run-page-variant-layers",
        documentId,
        runId,
        pageId,
        {
          variantKind: normalizeText(filters.variantKind)
        }
      ] as const,
    transcriptionRunPageVariantSuggestionDecision: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string,
      suggestionId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "transcription-run-page-variant-suggestion-decision",
        documentId,
        runId,
        pageId,
        suggestionId
      ] as const,
    processingRunStatus: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "processing-run-status",
        documentId,
        runId
      ] as const,
    processingRunDetail: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "processing-run-detail",
        documentId,
        runId
      ] as const,
    timeline: (projectId: string, documentId: string) =>
      ["projects", projectId, "documents", "timeline", documentId] as const
  },
  exports: {
    candidates: (projectId: string) =>
      ["projects", projectId, "exports", "candidates"] as const,
    requests: (projectId: string, filters: ExportRequestsFilter) =>
      [
        "projects",
        projectId,
        "exports",
        "requests",
        {
          candidateKind: normalizeText(filters.candidateKind),
          cursor: normalizeText(filters.cursor),
          requesterId: normalizeText(filters.requesterId),
          status: normalizeText(filters.status)
        }
      ] as const,
    review: (projectId: string, filters: ExportReviewFilter) =>
      [
        "projects",
        projectId,
        "exports",
        "review",
        {
          agingBucket: normalizeText(filters.agingBucket),
          reviewerUserId: normalizeText(filters.reviewerUserId),
          status: normalizeText(filters.status)
        }
      ] as const
  },
  jobs: {
    detail: (projectId: string, jobId: string) =>
      ["projects", projectId, "jobs", "detail", jobId] as const,
    events: (projectId: string, jobId: string, filters: CursorPageFilter) =>
      [
        "projects",
        projectId,
        "jobs",
        "events",
        jobId,
        {
          cursor: normalizeNumber(filters.cursor),
          pageSize: normalizeNumber(filters.pageSize)
        }
      ] as const,
    list: (projectId: string, filters: CursorPageFilter) =>
      [
        "projects",
        projectId,
        "jobs",
        "list",
        {
          cursor: normalizeNumber(filters.cursor),
          pageSize: normalizeNumber(filters.pageSize)
        }
      ] as const,
    status: (projectId: string, jobId: string) =>
      ["projects", projectId, "jobs", "status", jobId] as const,
    summary: (projectId: string) =>
      ["projects", projectId, "jobs", "summary"] as const
  },
  operations: {
    alerts: (
      filters: Readonly<{
        cursor?: number;
        pageSize?: number;
        state?: OperationsAlertState | "ALL";
      }>
    ) =>
      [
        "operations",
        "alerts",
        {
          cursor: normalizeNumber(filters.cursor),
          pageSize: normalizeNumber(filters.pageSize),
          state: normalizeText(filters.state)
        }
      ] as const,
    exportStatus: () => ["operations", "export-status"] as const,
    overview: () => ["operations", "overview"] as const,
    slos: () => ["operations", "slos"] as const,
    timelines: (
      filters: Readonly<{
        cursor?: number;
        pageSize?: number;
        scope?: OperationsTimelineScope | "all";
      }>
    ) =>
      [
        "operations",
        "timelines",
        {
          cursor: normalizeNumber(filters.cursor),
          pageSize: normalizeNumber(filters.pageSize),
          scope: normalizeText(filters.scope)
        }
      ] as const
  },
  projects: {
    detail: (projectId: string) => ["projects", projectId, "detail"] as const,
    list: () => ["projects", "list"] as const,
    members: (projectId: string) =>
      ["projects", projectId, "members"] as const,
    modelAssignmentDatasets: (projectId: string, assignmentId: string) =>
      [
        "projects",
        projectId,
        "model-assignments",
        "datasets",
        assignmentId
      ] as const,
    modelAssignmentDetail: (projectId: string, assignmentId: string) =>
      [
        "projects",
        projectId,
        "model-assignments",
        "detail",
        assignmentId
      ] as const,
    modelAssignments: (projectId: string) =>
      ["projects", projectId, "model-assignments", "list"] as const,
    projectActivity: (projectId: string) =>
      ["projects", projectId, "activity"] as const,
    workspace: (projectId: string) =>
      ["projects", projectId, "workspace"] as const
  },
  security: {
    status: () => ["security", "status"] as const
  },
  system: {
    health: () => ["system", "health"] as const,
    readiness: () => ["system", "readiness"] as const
  }
} as const;

function stableSortObject(
  value: { readonly [key: string]: QueryKeyPart }
): { readonly [key: string]: QueryKeyPart } {
  const entries = Object.entries(value).sort(([a], [b]) => a.localeCompare(b));
  const sorted: Record<string, QueryKeyPart> = {};
  for (const [key, entryValue] of entries) {
    sorted[key] = normalizeQueryKeyPart(entryValue);
  }
  return sorted;
}

export function normalizeQueryKeyPart(value: QueryKeyPart): QueryKeyPart {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeQueryKeyPart(item));
  }
  if (value && typeof value === "object") {
    return stableSortObject(value as { readonly [key: string]: QueryKeyPart });
  }
  return value;
}

export function serializeQueryKey(queryKey: QueryKey): string {
  return JSON.stringify(normalizeQueryKeyPart(queryKey));
}
