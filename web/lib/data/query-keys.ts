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
  cursor?: number;
  limit?: number;
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

interface RedactionRunListFilter extends CursorPageFilter {}

interface RedactionRunPagesFilter extends CursorPageFilter {
  category?: string;
  directIdentifiersOnly?: boolean;
  unresolvedOnly?: boolean;
}

interface RedactionRunPageFindingsFilter {
  category?: string;
  directIdentifiersOnly?: boolean;
  findingId?: string;
  lineId?: string;
  tokenId?: string;
  unresolvedOnly?: boolean;
  workspaceView?: boolean;
}

interface RedactionCompareFilter {
  findingId?: string;
  lineId?: string;
  page?: number;
  tokenId?: string;
}

interface GovernanceManifestEntriesFilter {
  category?: string;
  cursor?: number;
  from?: string;
  limit?: number;
  page?: number;
  reviewState?: string;
  to?: string;
}

interface GovernanceLedgerEntriesFilter {
  cursor?: number;
  limit?: number;
  view?: "list" | "timeline";
}

interface PageVariantsFilter {
  runId?: string;
}

interface PolicyCompareFilter {
  against?: string;
  againstBaselineSnapshotId?: string;
}

interface ProjectSearchFilter {
  cursor?: number;
  documentId?: string;
  limit?: number;
  pageNumber?: number;
  q?: string;
  runId?: string;
}

interface ProjectEntityFilter {
  cursor?: number;
  entityType?: string;
  limit?: number;
  q?: string;
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
    redactionOverview: (projectId: string, documentId: string) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-overview",
        documentId
      ] as const,
    redactionRuns: (
      projectId: string,
      documentId: string,
      filters: RedactionRunListFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-runs",
        documentId,
        {
          cursor: normalizeNumber(filters.cursor),
          pageSize: normalizeNumber(filters.pageSize)
        }
      ] as const,
    redactionActiveRun: (projectId: string, documentId: string) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-active-run",
        documentId
      ] as const,
    redactionRunDetail: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-run-detail",
        documentId,
        runId
      ] as const,
    redactionRunStatus: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-run-status",
        documentId,
        runId
      ] as const,
    redactionRunReview: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-run-review",
        documentId,
        runId
      ] as const,
    redactionRunEvents: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-run-events",
        documentId,
        runId
      ] as const,
    redactionRunPages: (
      projectId: string,
      documentId: string,
      runId: string,
      filters: RedactionRunPagesFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-run-pages",
        documentId,
        runId,
        {
          category: normalizeText(filters.category),
          cursor: normalizeNumber(filters.cursor),
          directIdentifiersOnly:
            typeof filters.directIdentifiersOnly === "boolean"
              ? filters.directIdentifiersOnly
              : null,
          pageSize: normalizeNumber(filters.pageSize),
          unresolvedOnly:
            typeof filters.unresolvedOnly === "boolean"
              ? filters.unresolvedOnly
              : null
        }
      ] as const,
    redactionRunPageFindings: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string,
      filters: RedactionRunPageFindingsFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-run-page-findings",
        documentId,
        runId,
        pageId,
        {
          category: normalizeText(filters.category),
          directIdentifiersOnly:
            typeof filters.directIdentifiersOnly === "boolean"
              ? filters.directIdentifiersOnly
              : null,
          findingId: normalizeText(filters.findingId),
          lineId: normalizeText(filters.lineId),
          tokenId: normalizeText(filters.tokenId),
          unresolvedOnly:
            typeof filters.unresolvedOnly === "boolean"
              ? filters.unresolvedOnly
              : null,
          workspaceView:
            typeof filters.workspaceView === "boolean"
              ? filters.workspaceView
              : null
        }
      ] as const,
    redactionRunPageFinding: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string,
      findingId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-run-page-finding",
        documentId,
        runId,
        pageId,
        findingId
      ] as const,
    redactionRunPageReview: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-run-page-review",
        documentId,
        runId,
        pageId
      ] as const,
    redactionRunPageEvents: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-run-page-events",
        documentId,
        runId,
        pageId
      ] as const,
    redactionRunPagePreviewStatus: (
      projectId: string,
      documentId: string,
      runId: string,
      pageId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-run-page-preview-status",
        documentId,
        runId,
        pageId
      ] as const,
    redactionRunOutput: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-run-output",
        documentId,
        runId
      ] as const,
    redactionRunOutputStatus: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-run-output-status",
        documentId,
        runId
      ] as const,
    redactionCompare: (
      projectId: string,
      documentId: string,
      baseRunId: string,
      candidateRunId: string,
      filters: RedactionCompareFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "redaction-compare",
        documentId,
        baseRunId,
        candidateRunId,
        {
          findingId: normalizeText(filters.findingId),
          lineId: normalizeText(filters.lineId),
          page: normalizeNumber(filters.page),
          tokenId: normalizeText(filters.tokenId)
        }
      ] as const,
    governanceOverview: (projectId: string, documentId: string) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-overview",
        documentId
      ] as const,
    governanceRuns: (projectId: string, documentId: string) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-runs",
        documentId
      ] as const,
    governanceRunOverview: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-overview",
        documentId,
        runId
      ] as const,
    governanceRunEvents: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-events",
        documentId,
        runId
      ] as const,
    governanceRunManifest: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-manifest",
        documentId,
        runId
      ] as const,
    governanceRunManifestStatus: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-manifest-status",
        documentId,
        runId
      ] as const,
    governanceRunManifestEntries: (
      projectId: string,
      documentId: string,
      runId: string,
      filters: GovernanceManifestEntriesFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-manifest-entries",
        documentId,
        runId,
        {
          category: normalizeText(filters.category),
          cursor: normalizeNumber(filters.cursor),
          from: normalizeText(filters.from),
          limit: normalizeNumber(filters.limit),
          page: normalizeNumber(filters.page),
          reviewState: normalizeText(filters.reviewState),
          to: normalizeText(filters.to)
        }
      ] as const,
    governanceRunManifestHash: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-manifest-hash",
        documentId,
        runId
      ] as const,
    governanceRunLedger: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-ledger",
        documentId,
        runId
      ] as const,
    governanceRunLedgerStatus: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-ledger-status",
        documentId,
        runId
      ] as const,
    governanceRunLedgerEntries: (
      projectId: string,
      documentId: string,
      runId: string,
      filters: GovernanceLedgerEntriesFilter
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-ledger-entries",
        documentId,
        runId,
        {
          cursor: normalizeNumber(filters.cursor),
          limit: normalizeNumber(filters.limit),
          view: normalizeText(filters.view)
        }
      ] as const,
    governanceRunLedgerSummary: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-ledger-summary",
        documentId,
        runId
      ] as const,
    governanceRunLedgerVerifyStatus: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-ledger-verify-status",
        documentId,
        runId
      ] as const,
    governanceRunLedgerVerifyRuns: (
      projectId: string,
      documentId: string,
      runId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-ledger-verify-runs",
        documentId,
        runId
      ] as const,
    governanceRunLedgerVerifyRun: (
      projectId: string,
      documentId: string,
      runId: string,
      verificationRunId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-ledger-verify-run",
        documentId,
        runId,
        verificationRunId
      ] as const,
    governanceRunLedgerVerifyRunStatus: (
      projectId: string,
      documentId: string,
      runId: string,
      verificationRunId: string
    ) =>
      [
        "projects",
        projectId,
        "documents",
        "governance-run-ledger-verify-run-status",
        documentId,
        runId,
        verificationRunId
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
    candidate: (projectId: string, candidateId: string) =>
      ["projects", projectId, "exports", "candidate", candidateId] as const,
    candidateReleasePack: (
      projectId: string,
      candidateId: string,
      input?: Readonly<{
        bundleProfile?: string;
        purposeStatement?: string;
      }>
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "candidate-release-pack",
        candidateId,
        {
          bundleProfile: normalizeText(input?.bundleProfile),
          purposeStatement: normalizeText(input?.purposeStatement)
        }
      ] as const,
    requests: (projectId: string, filters: ExportRequestsFilter) =>
      [
        "projects",
        projectId,
        "exports",
        "requests",
        {
          candidateKind: normalizeText(filters.candidateKind),
          cursor: normalizeNumber(filters.cursor),
          limit: normalizeNumber(filters.limit),
          requesterId: normalizeText(filters.requesterId),
          status: normalizeText(filters.status)
        }
      ] as const,
    request: (projectId: string, exportRequestId: string) =>
      ["projects", projectId, "exports", "request", exportRequestId] as const,
    requestStatus: (projectId: string, exportRequestId: string) =>
      ["projects", projectId, "exports", "request-status", exportRequestId] as const,
    requestReleasePack: (projectId: string, exportRequestId: string) =>
      ["projects", projectId, "exports", "request-release-pack", exportRequestId] as const,
    requestValidationSummary: (projectId: string, exportRequestId: string) =>
      [
        "projects",
        projectId,
        "exports",
        "request-validation-summary",
        exportRequestId
      ] as const,
    requestProvenanceSummary: (projectId: string, exportRequestId: string) =>
      [
        "projects",
        projectId,
        "exports",
        "request-provenance-summary",
        exportRequestId
      ] as const,
    requestProvenanceProofs: (projectId: string, exportRequestId: string) =>
      [
        "projects",
        projectId,
        "exports",
        "request-provenance-proofs",
        exportRequestId
      ] as const,
    requestProvenanceProofCurrent: (projectId: string, exportRequestId: string) =>
      [
        "projects",
        projectId,
        "exports",
        "request-provenance-proof-current",
        exportRequestId
      ] as const,
    requestProvenanceProof: (
      projectId: string,
      exportRequestId: string,
      proofId: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-provenance-proof",
        exportRequestId,
        proofId
      ] as const,
    requestBundles: (projectId: string, exportRequestId: string) =>
      ["projects", projectId, "exports", "request-bundles", exportRequestId] as const,
    requestBundle: (projectId: string, exportRequestId: string, bundleId: string) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle",
        exportRequestId,
        bundleId
      ] as const,
    requestBundleStatus: (
      projectId: string,
      exportRequestId: string,
      bundleId: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle-status",
        exportRequestId,
        bundleId
      ] as const,
    requestBundleEvents: (
      projectId: string,
      exportRequestId: string,
      bundleId: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle-events",
        exportRequestId,
        bundleId
      ] as const,
    requestBundleVerification: (
      projectId: string,
      exportRequestId: string,
      bundleId: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle-verification",
        exportRequestId,
        bundleId
      ] as const,
    requestBundleVerificationStatus: (
      projectId: string,
      exportRequestId: string,
      bundleId: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle-verification-status",
        exportRequestId,
        bundleId
      ] as const,
    requestBundleVerificationRuns: (
      projectId: string,
      exportRequestId: string,
      bundleId: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle-verification-runs",
        exportRequestId,
        bundleId
      ] as const,
    requestBundleVerificationRun: (
      projectId: string,
      exportRequestId: string,
      bundleId: string,
      verificationRunId: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle-verification-run",
        exportRequestId,
        bundleId,
        verificationRunId
      ] as const,
    requestBundleVerificationRunStatus: (
      projectId: string,
      exportRequestId: string,
      bundleId: string,
      verificationRunId: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle-verification-run-status",
        exportRequestId,
        bundleId,
        verificationRunId
      ] as const,
    requestBundleProfiles: (
      projectId: string,
      exportRequestId: string,
      bundleId?: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle-profiles",
        exportRequestId,
        {
          bundleId: normalizeText(bundleId)
        }
      ] as const,
    requestBundleValidationStatus: (
      projectId: string,
      exportRequestId: string,
      bundleId: string,
      profileId: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle-validation-status",
        exportRequestId,
        bundleId,
        normalizeText(profileId)
      ] as const,
    requestBundleValidationRuns: (
      projectId: string,
      exportRequestId: string,
      bundleId: string,
      profileId: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle-validation-runs",
        exportRequestId,
        bundleId,
        normalizeText(profileId)
      ] as const,
    requestBundleValidationRun: (
      projectId: string,
      exportRequestId: string,
      bundleId: string,
      validationRunId: string,
      profileId?: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle-validation-run",
        exportRequestId,
        bundleId,
        validationRunId,
        {
          profileId: normalizeText(profileId)
        }
      ] as const,
    requestBundleValidationRunStatus: (
      projectId: string,
      exportRequestId: string,
      bundleId: string,
      validationRunId: string,
      profileId?: string
    ) =>
      [
        "projects",
        projectId,
        "exports",
        "request-bundle-validation-run-status",
        exportRequestId,
        bundleId,
        validationRunId,
        {
          profileId: normalizeText(profileId)
        }
      ] as const,
    requestReceipt: (projectId: string, exportRequestId: string) =>
      ["projects", projectId, "exports", "request-receipt", exportRequestId] as const,
    requestReceipts: (projectId: string, exportRequestId: string) =>
      ["projects", projectId, "exports", "request-receipts", exportRequestId] as const,
    requestEvents: (projectId: string, exportRequestId: string) =>
      ["projects", projectId, "exports", "request-events", exportRequestId] as const,
    requestReviews: (projectId: string, exportRequestId: string) =>
      ["projects", projectId, "exports", "request-reviews", exportRequestId] as const,
    requestReviewEvents: (projectId: string, exportRequestId: string) =>
      [
        "projects",
        projectId,
        "exports",
        "request-review-events",
        exportRequestId
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
    search: (projectId: string, filters: ProjectSearchFilter) =>
      [
        "projects",
        projectId,
        "search",
        {
          cursor: normalizeNumber(filters.cursor),
          documentId: normalizeText(filters.documentId),
          limit: normalizeNumber(filters.limit),
          pageNumber: normalizeNumber(filters.pageNumber),
          q: normalizeText(filters.q),
          runId: normalizeText(filters.runId)
        }
      ] as const,
    entities: (projectId: string, filters: ProjectEntityFilter) =>
      [
        "projects",
        projectId,
        "entities",
        "list",
        {
          cursor: normalizeNumber(filters.cursor),
          entityType: normalizeText(filters.entityType),
          limit: normalizeNumber(filters.limit),
          q: normalizeText(filters.q)
        }
      ] as const,
    entityDetail: (projectId: string, entityId: string) =>
      ["projects", projectId, "entities", "detail", entityId] as const,
    entityOccurrences: (
      projectId: string,
      entityId: string,
      filters: Pick<ProjectEntityFilter, "cursor" | "limit">
    ) =>
      [
        "projects",
        projectId,
        "entities",
        "occurrences",
        entityId,
        {
          cursor: normalizeNumber(filters.cursor),
          limit: normalizeNumber(filters.limit)
        }
      ] as const,
    indexesActive: (projectId: string) =>
      ["projects", projectId, "indexes", "active"] as const,
    indexesList: (
      projectId: string,
      kind: "SEARCH" | "ENTITY" | "DERIVATIVE"
    ) =>
      [
        "projects",
        projectId,
        "indexes",
        "list",
        normalizeText(kind)
      ] as const,
    indexesDetail: (
      projectId: string,
      kind: "SEARCH" | "ENTITY" | "DERIVATIVE",
      indexId: string
    ) =>
      [
        "projects",
        projectId,
        "indexes",
        "detail",
        normalizeText(kind),
        indexId
      ] as const,
    indexesStatus: (
      projectId: string,
      kind: "SEARCH" | "ENTITY" | "DERIVATIVE",
      indexId: string
    ) =>
      [
        "projects",
        projectId,
        "indexes",
        "status",
        normalizeText(kind),
        indexId
      ] as const,
    policyActive: (projectId: string) =>
      ["projects", projectId, "policies", "active"] as const,
    policyCompare: (
      projectId: string,
      policyId: string,
      filters: PolicyCompareFilter
    ) =>
      [
        "projects",
        projectId,
        "policies",
        "compare",
        policyId,
        {
          against: normalizeText(filters.against),
          againstBaselineSnapshotId: normalizeText(
            filters.againstBaselineSnapshotId
          )
        }
      ] as const,
    policyDetail: (projectId: string, policyId: string) =>
      ["projects", projectId, "policies", "detail", policyId] as const,
    policyExplainability: (projectId: string, policyId: string) =>
      ["projects", projectId, "policies", "explainability", policyId] as const,
    policyEvents: (projectId: string, policyId: string) =>
      ["projects", projectId, "policies", "events", policyId] as const,
    policyLineage: (projectId: string, policyId: string) =>
      ["projects", projectId, "policies", "lineage", policyId] as const,
    policyList: (projectId: string) =>
      ["projects", projectId, "policies", "list"] as const,
    policySnapshot: (projectId: string, policyId: string, rulesSha256: string) =>
      [
        "projects",
        projectId,
        "policies",
        "snapshot",
        policyId,
        normalizeText(rulesSha256)
      ] as const,
    policyUsage: (projectId: string, policyId: string) =>
      ["projects", projectId, "policies", "usage", policyId] as const,
    pseudonymRegistryDetail: (projectId: string, entryId: string) =>
      ["projects", projectId, "pseudonym-registry", "detail", entryId] as const,
    pseudonymRegistryEvents: (projectId: string, entryId: string) =>
      ["projects", projectId, "pseudonym-registry", "events", entryId] as const,
    pseudonymRegistryList: (projectId: string) =>
      ["projects", projectId, "pseudonym-registry", "list"] as const,
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
