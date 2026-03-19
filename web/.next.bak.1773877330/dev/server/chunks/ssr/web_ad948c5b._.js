module.exports = [
"[project]/web/lib/data/cache-policy.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "queryCachePolicy",
    ()=>queryCachePolicy
]);
// Governance and RBAC-sensitive reads remain network-only in Phase 0/1.
const NETWORK_ONLY = "no-store";
const queryCachePolicy = {
    "auth-critical": {
        cacheClass: "auth-critical",
        description: "Session and authorization truth. Never cache between requests.",
        fetchCache: NETWORK_ONLY,
        optimistic: "never",
        pollIntervalMs: null,
        retryMaxAttempts: 0
    },
    "governance-event": {
        cacheClass: "governance-event",
        description: "Audit/security/governance reads. Exact server truth wins over speculative freshness.",
        fetchCache: NETWORK_ONLY,
        optimistic: "never",
        pollIntervalMs: null,
        retryMaxAttempts: 1
    },
    "mutable-list": {
        cacheClass: "mutable-list",
        description: "Project and jobs lists mutate frequently and are invalidated on successful mutations.",
        fetchCache: NETWORK_ONLY,
        optimistic: "never",
        pollIntervalMs: null,
        retryMaxAttempts: 1
    },
    "operations-live": {
        cacheClass: "operations-live",
        description: "Live operational posture. Always fresh with optional short polling in client-only status widgets.",
        fetchCache: NETWORK_ONLY,
        optimistic: "never",
        pollIntervalMs: 4000,
        retryMaxAttempts: 0
    },
    "public-status": {
        cacheClass: "public-status",
        description: "Health/readiness checks for diagnostics. Read as live status rather than cached snapshots.",
        fetchCache: NETWORK_ONLY,
        optimistic: "never",
        pollIntervalMs: 5000,
        retryMaxAttempts: 0
    }
};
}),
"[project]/web/lib/data/api-types.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "normalizeDetail",
    ()=>normalizeDetail,
    "normalizeMethod",
    ()=>normalizeMethod,
    "resolveErrorCode",
    ()=>resolveErrorCode,
    "resolveRetryable",
    ()=>resolveRetryable
]);
function resolveErrorCode(status) {
    if (status === 401) {
        return "AUTH_REQUIRED";
    }
    if (status === 403) {
        return "FORBIDDEN";
    }
    if (status === 404) {
        return "NOT_FOUND";
    }
    if (status === 409) {
        return "CONFLICT";
    }
    if (status === 422 || status === 400) {
        return "VALIDATION";
    }
    if (status >= 500) {
        return "SERVER";
    }
    return "UNKNOWN";
}
function resolveRetryable(code, method) {
    if (code === "NETWORK" || code === "SERVER") {
        return method.toUpperCase() === "GET";
    }
    return false;
}
function normalizeDetail(payload) {
    if (typeof payload === "object" && payload !== null && "detail" in payload && typeof payload.detail === "string") {
        return payload.detail;
    }
    return "Request failed.";
}
function normalizeMethod(value) {
    return value?.toUpperCase() ?? "GET";
}
}),
"[project]/web/lib/data/query-keys.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "normalizeQueryKeyPart",
    ()=>normalizeQueryKeyPart,
    "queryKeys",
    ()=>queryKeys,
    "serializeQueryKey",
    ()=>serializeQueryKey
]);
function normalizeText(value) {
    if (!value) {
        return null;
    }
    const trimmed = value.trim();
    return trimmed.length === 0 ? null : trimmed;
}
function normalizeNumber(value) {
    return typeof value === "number" ? value : null;
}
const queryKeys = {
    admin: {
        capacityTestDetail: (testRunId)=>[
                "admin",
                "capacity",
                "detail",
                {
                    testRunId: normalizeText(testRunId)
                }
            ],
        capacityTestResults: (testRunId)=>[
                "admin",
                "capacity",
                "results",
                {
                    testRunId: normalizeText(testRunId)
                }
            ],
        capacityTests: (filters)=>[
                "admin",
                "capacity",
                "tests",
                {
                    cursor: normalizeNumber(filters.cursor),
                    pageSize: normalizeNumber(filters.pageSize)
                }
            ],
        recoveryDrillDetail: (drillId)=>[
                "admin",
                "recovery",
                "detail",
                {
                    drillId: normalizeText(drillId)
                }
            ],
        recoveryDrillEvidence: (drillId)=>[
                "admin",
                "recovery",
                "evidence",
                {
                    drillId: normalizeText(drillId)
                }
            ],
        recoveryDrillStatus: (drillId)=>[
                "admin",
                "recovery",
                "status",
                {
                    drillId: normalizeText(drillId)
                }
            ],
        recoveryDrills: (filters)=>[
                "admin",
                "recovery",
                "drills",
                {
                    cursor: normalizeNumber(filters.cursor),
                    pageSize: normalizeNumber(filters.pageSize)
                }
            ],
        recoveryStatus: ()=>[
                "admin",
                "recovery",
                "status-summary"
            ],
        securityFindingDetail: (findingId)=>[
                "admin",
                "security",
                "finding-detail",
                {
                    findingId: normalizeText(findingId)
                }
            ],
        securityFindings: ()=>[
                "admin",
                "security",
                "findings"
            ],
        securityRiskAcceptanceDetail: (riskAcceptanceId)=>[
                "admin",
                "security",
                "risk-acceptance-detail",
                {
                    riskAcceptanceId: normalizeText(riskAcceptanceId)
                }
            ],
        securityRiskAcceptanceEvents: (riskAcceptanceId)=>[
                "admin",
                "security",
                "risk-acceptance-events",
                {
                    riskAcceptanceId: normalizeText(riskAcceptanceId)
                }
            ],
        securityRiskAcceptances: (filters)=>[
                "admin",
                "security",
                "risk-acceptances",
                {
                    findingId: normalizeText(filters.findingId),
                    status: normalizeText(filters.status)
                }
            ],
        indexQualityDetail: (indexKind, indexId)=>[
                "admin",
                "index-quality",
                "detail",
                {
                    indexId: normalizeText(indexId),
                    indexKind: normalizeText(indexKind)
                }
            ],
        indexQualityQueryAudits: (filters)=>[
                "admin",
                "index-quality",
                "query-audits",
                {
                    cursor: normalizeNumber(filters.cursor),
                    limit: normalizeNumber(filters.limit),
                    projectId: normalizeText(filters.projectId)
                }
            ],
        indexQualitySummary: (projectId)=>[
                "admin",
                "index-quality",
                "summary",
                {
                    projectId: normalizeText(projectId)
                }
            ]
    },
    auth: {
        providers: ()=>[
                "auth",
                "providers"
            ],
        session: ()=>[
                "auth",
                "session"
            ]
    },
    audit: {
        detail: (eventId)=>[
                "audit",
                "detail",
                eventId
            ],
        integrity: ()=>[
                "audit",
                "integrity"
            ],
        list: (filters)=>[
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
            ],
        myActivity: (limit)=>[
                "audit",
                "my-activity",
                {
                    limit
                }
            ]
    },
    models: {
        approvedList: (filters)=>[
                "models",
                "approved-list",
                {
                    modelRole: normalizeText(filters.modelRole),
                    status: normalizeText(filters.status)
                }
            ]
    },
    documents: {
        detail: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "detail",
                documentId
            ],
        importStatus: (projectId, importId)=>[
                "projects",
                projectId,
                "documents",
                "import-status",
                importId
            ],
        list: (projectId, filters)=>[
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
            ],
        pageDetail: (projectId, documentId, pageId)=>[
                "projects",
                projectId,
                "documents",
                "page-detail",
                documentId,
                pageId
            ],
        pageVariants: (projectId, documentId, pageId, filters)=>[
                "projects",
                projectId,
                "documents",
                "page-variants",
                documentId,
                pageId,
                {
                    runId: normalizeText(filters.runId)
                }
            ],
        pages: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "pages",
                documentId
            ],
        preprocessActiveRun: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "preprocess-active-run",
                documentId
            ],
        preprocessCompare: (projectId, documentId, baseRunId, candidateRunId)=>[
                "projects",
                projectId,
                "documents",
                "preprocess-compare",
                documentId,
                baseRunId,
                candidateRunId
            ],
        preprocessOverview: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "preprocess-overview",
                documentId
            ],
        preprocessQuality: (projectId, documentId, filters)=>[
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
            ],
        preprocessRunDetail: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "preprocess-run-detail",
                documentId,
                runId
            ],
        preprocessRunPage: (projectId, documentId, runId, pageId)=>[
                "projects",
                projectId,
                "documents",
                "preprocess-run-page",
                documentId,
                runId,
                pageId
            ],
        preprocessRunPages: (projectId, documentId, runId, filters)=>[
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
            ],
        preprocessRuns: (projectId, documentId, filters)=>[
                "projects",
                projectId,
                "documents",
                "preprocess-runs",
                documentId,
                {
                    cursor: normalizeNumber(filters.cursor),
                    pageSize: normalizeNumber(filters.pageSize)
                }
            ],
        preprocessRunStatus: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "preprocess-run-status",
                documentId,
                runId
            ],
        layoutActiveRun: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "layout-active-run",
                documentId
            ],
        layoutOverview: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "layout-overview",
                documentId
            ],
        layoutRuns: (projectId, documentId, filters)=>[
                "projects",
                projectId,
                "documents",
                "layout-runs",
                documentId,
                {
                    cursor: normalizeNumber(filters.cursor),
                    pageSize: normalizeNumber(filters.pageSize)
                }
            ],
        layoutRunDetail: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "layout-run-detail",
                documentId,
                runId
            ],
        layoutRunStatus: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "layout-run-status",
                documentId,
                runId
            ],
        layoutRunPages: (projectId, documentId, runId, filters)=>[
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
            ],
        layoutPageOverlay: (projectId, documentId, runId, pageId)=>[
                "projects",
                projectId,
                "documents",
                "layout-page-overlay",
                documentId,
                runId,
                pageId
            ],
        layoutPageRecallStatus: (projectId, documentId, runId, pageId)=>[
                "projects",
                projectId,
                "documents",
                "layout-page-recall-status",
                documentId,
                runId,
                pageId
            ],
        layoutPageRescueCandidates: (projectId, documentId, runId, pageId)=>[
                "projects",
                projectId,
                "documents",
                "layout-page-rescue-candidates",
                documentId,
                runId,
                pageId
            ],
        transcriptionOverview: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "transcription-overview",
                documentId
            ],
        transcriptionTriage: (projectId, documentId, filters)=>[
                "projects",
                projectId,
                "documents",
                "transcription-triage",
                documentId,
                {
                    confidenceBelow: typeof filters.confidenceBelow === "number" ? filters.confidenceBelow : null,
                    cursor: normalizeNumber(filters.cursor),
                    page: normalizeNumber(filters.page),
                    pageSize: normalizeNumber(filters.pageSize),
                    runId: normalizeText(filters.runId),
                    status: normalizeText(filters.status)
                }
            ],
        transcriptionMetrics: (projectId, documentId, filters)=>[
                "projects",
                projectId,
                "documents",
                "transcription-metrics",
                documentId,
                {
                    confidenceBelow: typeof filters.confidenceBelow === "number" ? filters.confidenceBelow : null,
                    runId: normalizeText(filters.runId)
                }
            ],
        transcriptionRuns: (projectId, documentId, filters)=>[
                "projects",
                projectId,
                "documents",
                "transcription-runs",
                documentId,
                {
                    cursor: normalizeNumber(filters.cursor),
                    pageSize: normalizeNumber(filters.pageSize)
                }
            ],
        transcriptionActiveRun: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "transcription-active-run",
                documentId
            ],
        transcriptionRunDetail: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "transcription-run-detail",
                documentId,
                runId
            ],
        transcriptionRunStatus: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "transcription-run-status",
                documentId,
                runId
            ],
        transcriptionRunPages: (projectId, documentId, runId, filters)=>[
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
            ],
        transcriptionRunPageLines: (projectId, documentId, runId, pageId)=>[
                "projects",
                projectId,
                "documents",
                "transcription-run-page-lines",
                documentId,
                runId,
                pageId
            ],
        transcriptionRunPageTokens: (projectId, documentId, runId, pageId)=>[
                "projects",
                projectId,
                "documents",
                "transcription-run-page-tokens",
                documentId,
                runId,
                pageId
            ],
        transcriptionRunPageVariantLayers: (projectId, documentId, runId, pageId, filters)=>[
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
            ],
        transcriptionRunPageVariantSuggestionDecision: (projectId, documentId, runId, pageId, suggestionId)=>[
                "projects",
                projectId,
                "documents",
                "transcription-run-page-variant-suggestion-decision",
                documentId,
                runId,
                pageId,
                suggestionId
            ],
        redactionOverview: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "redaction-overview",
                documentId
            ],
        redactionRuns: (projectId, documentId, filters)=>[
                "projects",
                projectId,
                "documents",
                "redaction-runs",
                documentId,
                {
                    cursor: normalizeNumber(filters.cursor),
                    pageSize: normalizeNumber(filters.pageSize)
                }
            ],
        redactionActiveRun: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "redaction-active-run",
                documentId
            ],
        redactionRunDetail: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "redaction-run-detail",
                documentId,
                runId
            ],
        redactionRunStatus: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "redaction-run-status",
                documentId,
                runId
            ],
        redactionRunReview: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "redaction-run-review",
                documentId,
                runId
            ],
        redactionRunEvents: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "redaction-run-events",
                documentId,
                runId
            ],
        redactionRunPages: (projectId, documentId, runId, filters)=>[
                "projects",
                projectId,
                "documents",
                "redaction-run-pages",
                documentId,
                runId,
                {
                    category: normalizeText(filters.category),
                    cursor: normalizeNumber(filters.cursor),
                    directIdentifiersOnly: typeof filters.directIdentifiersOnly === "boolean" ? filters.directIdentifiersOnly : null,
                    pageSize: normalizeNumber(filters.pageSize),
                    unresolvedOnly: typeof filters.unresolvedOnly === "boolean" ? filters.unresolvedOnly : null
                }
            ],
        redactionRunPageFindings: (projectId, documentId, runId, pageId, filters)=>[
                "projects",
                projectId,
                "documents",
                "redaction-run-page-findings",
                documentId,
                runId,
                pageId,
                {
                    category: normalizeText(filters.category),
                    directIdentifiersOnly: typeof filters.directIdentifiersOnly === "boolean" ? filters.directIdentifiersOnly : null,
                    findingId: normalizeText(filters.findingId),
                    lineId: normalizeText(filters.lineId),
                    tokenId: normalizeText(filters.tokenId),
                    unresolvedOnly: typeof filters.unresolvedOnly === "boolean" ? filters.unresolvedOnly : null,
                    workspaceView: typeof filters.workspaceView === "boolean" ? filters.workspaceView : null
                }
            ],
        redactionRunPageFinding: (projectId, documentId, runId, pageId, findingId)=>[
                "projects",
                projectId,
                "documents",
                "redaction-run-page-finding",
                documentId,
                runId,
                pageId,
                findingId
            ],
        redactionRunPageReview: (projectId, documentId, runId, pageId)=>[
                "projects",
                projectId,
                "documents",
                "redaction-run-page-review",
                documentId,
                runId,
                pageId
            ],
        redactionRunPageEvents: (projectId, documentId, runId, pageId)=>[
                "projects",
                projectId,
                "documents",
                "redaction-run-page-events",
                documentId,
                runId,
                pageId
            ],
        redactionRunPagePreviewStatus: (projectId, documentId, runId, pageId)=>[
                "projects",
                projectId,
                "documents",
                "redaction-run-page-preview-status",
                documentId,
                runId,
                pageId
            ],
        redactionRunOutput: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "redaction-run-output",
                documentId,
                runId
            ],
        redactionRunOutputStatus: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "redaction-run-output-status",
                documentId,
                runId
            ],
        redactionCompare: (projectId, documentId, baseRunId, candidateRunId, filters)=>[
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
            ],
        governanceOverview: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "governance-overview",
                documentId
            ],
        governanceRuns: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "governance-runs",
                documentId
            ],
        governanceRunOverview: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "governance-run-overview",
                documentId,
                runId
            ],
        governanceRunEvents: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "governance-run-events",
                documentId,
                runId
            ],
        governanceRunManifest: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "governance-run-manifest",
                documentId,
                runId
            ],
        governanceRunManifestStatus: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "governance-run-manifest-status",
                documentId,
                runId
            ],
        governanceRunManifestEntries: (projectId, documentId, runId, filters)=>[
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
            ],
        governanceRunManifestHash: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "governance-run-manifest-hash",
                documentId,
                runId
            ],
        governanceRunLedger: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "governance-run-ledger",
                documentId,
                runId
            ],
        governanceRunLedgerStatus: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "governance-run-ledger-status",
                documentId,
                runId
            ],
        governanceRunLedgerEntries: (projectId, documentId, runId, filters)=>[
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
            ],
        governanceRunLedgerSummary: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "governance-run-ledger-summary",
                documentId,
                runId
            ],
        governanceRunLedgerVerifyStatus: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "governance-run-ledger-verify-status",
                documentId,
                runId
            ],
        governanceRunLedgerVerifyRuns: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "governance-run-ledger-verify-runs",
                documentId,
                runId
            ],
        governanceRunLedgerVerifyRun: (projectId, documentId, runId, verificationRunId)=>[
                "projects",
                projectId,
                "documents",
                "governance-run-ledger-verify-run",
                documentId,
                runId,
                verificationRunId
            ],
        governanceRunLedgerVerifyRunStatus: (projectId, documentId, runId, verificationRunId)=>[
                "projects",
                projectId,
                "documents",
                "governance-run-ledger-verify-run-status",
                documentId,
                runId,
                verificationRunId
            ],
        processingRunStatus: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "processing-run-status",
                documentId,
                runId
            ],
        processingRunDetail: (projectId, documentId, runId)=>[
                "projects",
                projectId,
                "documents",
                "processing-run-detail",
                documentId,
                runId
            ],
        timeline: (projectId, documentId)=>[
                "projects",
                projectId,
                "documents",
                "timeline",
                documentId
            ]
    },
    exports: {
        candidates: (projectId)=>[
                "projects",
                projectId,
                "exports",
                "candidates"
            ],
        candidate: (projectId, candidateId)=>[
                "projects",
                projectId,
                "exports",
                "candidate",
                candidateId
            ],
        candidateReleasePack: (projectId, candidateId, input)=>[
                "projects",
                projectId,
                "exports",
                "candidate-release-pack",
                candidateId,
                {
                    bundleProfile: normalizeText(input?.bundleProfile),
                    purposeStatement: normalizeText(input?.purposeStatement)
                }
            ],
        requests: (projectId, filters)=>[
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
            ],
        request: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request",
                exportRequestId
            ],
        requestStatus: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request-status",
                exportRequestId
            ],
        requestReleasePack: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request-release-pack",
                exportRequestId
            ],
        requestValidationSummary: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request-validation-summary",
                exportRequestId
            ],
        requestProvenanceSummary: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request-provenance-summary",
                exportRequestId
            ],
        requestProvenanceProofs: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request-provenance-proofs",
                exportRequestId
            ],
        requestProvenanceProofCurrent: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request-provenance-proof-current",
                exportRequestId
            ],
        requestProvenanceProof: (projectId, exportRequestId, proofId)=>[
                "projects",
                projectId,
                "exports",
                "request-provenance-proof",
                exportRequestId,
                proofId
            ],
        requestBundles: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request-bundles",
                exportRequestId
            ],
        requestBundle: (projectId, exportRequestId, bundleId)=>[
                "projects",
                projectId,
                "exports",
                "request-bundle",
                exportRequestId,
                bundleId
            ],
        requestBundleStatus: (projectId, exportRequestId, bundleId)=>[
                "projects",
                projectId,
                "exports",
                "request-bundle-status",
                exportRequestId,
                bundleId
            ],
        requestBundleEvents: (projectId, exportRequestId, bundleId)=>[
                "projects",
                projectId,
                "exports",
                "request-bundle-events",
                exportRequestId,
                bundleId
            ],
        requestBundleVerification: (projectId, exportRequestId, bundleId)=>[
                "projects",
                projectId,
                "exports",
                "request-bundle-verification",
                exportRequestId,
                bundleId
            ],
        requestBundleVerificationStatus: (projectId, exportRequestId, bundleId)=>[
                "projects",
                projectId,
                "exports",
                "request-bundle-verification-status",
                exportRequestId,
                bundleId
            ],
        requestBundleVerificationRuns: (projectId, exportRequestId, bundleId)=>[
                "projects",
                projectId,
                "exports",
                "request-bundle-verification-runs",
                exportRequestId,
                bundleId
            ],
        requestBundleVerificationRun: (projectId, exportRequestId, bundleId, verificationRunId)=>[
                "projects",
                projectId,
                "exports",
                "request-bundle-verification-run",
                exportRequestId,
                bundleId,
                verificationRunId
            ],
        requestBundleVerificationRunStatus: (projectId, exportRequestId, bundleId, verificationRunId)=>[
                "projects",
                projectId,
                "exports",
                "request-bundle-verification-run-status",
                exportRequestId,
                bundleId,
                verificationRunId
            ],
        requestBundleProfiles: (projectId, exportRequestId, bundleId)=>[
                "projects",
                projectId,
                "exports",
                "request-bundle-profiles",
                exportRequestId,
                {
                    bundleId: normalizeText(bundleId)
                }
            ],
        requestBundleValidationStatus: (projectId, exportRequestId, bundleId, profileId)=>[
                "projects",
                projectId,
                "exports",
                "request-bundle-validation-status",
                exportRequestId,
                bundleId,
                normalizeText(profileId)
            ],
        requestBundleValidationRuns: (projectId, exportRequestId, bundleId, profileId)=>[
                "projects",
                projectId,
                "exports",
                "request-bundle-validation-runs",
                exportRequestId,
                bundleId,
                normalizeText(profileId)
            ],
        requestBundleValidationRun: (projectId, exportRequestId, bundleId, validationRunId, profileId)=>[
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
            ],
        requestBundleValidationRunStatus: (projectId, exportRequestId, bundleId, validationRunId, profileId)=>[
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
            ],
        requestReceipt: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request-receipt",
                exportRequestId
            ],
        requestReceipts: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request-receipts",
                exportRequestId
            ],
        requestEvents: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request-events",
                exportRequestId
            ],
        requestReviews: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request-reviews",
                exportRequestId
            ],
        requestReviewEvents: (projectId, exportRequestId)=>[
                "projects",
                projectId,
                "exports",
                "request-review-events",
                exportRequestId
            ],
        review: (projectId, filters)=>[
                "projects",
                projectId,
                "exports",
                "review",
                {
                    agingBucket: normalizeText(filters.agingBucket),
                    reviewerUserId: normalizeText(filters.reviewerUserId),
                    status: normalizeText(filters.status)
                }
            ]
    },
    jobs: {
        detail: (projectId, jobId)=>[
                "projects",
                projectId,
                "jobs",
                "detail",
                jobId
            ],
        events: (projectId, jobId, filters)=>[
                "projects",
                projectId,
                "jobs",
                "events",
                jobId,
                {
                    cursor: normalizeNumber(filters.cursor),
                    pageSize: normalizeNumber(filters.pageSize)
                }
            ],
        list: (projectId, filters)=>[
                "projects",
                projectId,
                "jobs",
                "list",
                {
                    cursor: normalizeNumber(filters.cursor),
                    pageSize: normalizeNumber(filters.pageSize)
                }
            ],
        status: (projectId, jobId)=>[
                "projects",
                projectId,
                "jobs",
                "status",
                jobId
            ],
        summary: (projectId)=>[
                "projects",
                projectId,
                "jobs",
                "summary"
            ]
    },
    operations: {
        alerts: (filters)=>[
                "operations",
                "alerts",
                {
                    cursor: normalizeNumber(filters.cursor),
                    pageSize: normalizeNumber(filters.pageSize),
                    state: normalizeText(filters.state)
                }
            ],
        exportStatus: ()=>[
                "operations",
                "export-status"
            ],
        readiness: ()=>[
                "operations",
                "readiness"
            ],
        overview: ()=>[
                "operations",
                "overview"
            ],
        slos: ()=>[
                "operations",
                "slos"
            ],
        timelines: (filters)=>[
                "operations",
                "timelines",
                {
                    cursor: normalizeNumber(filters.cursor),
                    pageSize: normalizeNumber(filters.pageSize),
                    scope: normalizeText(filters.scope)
                }
            ]
    },
    projects: {
        detail: (projectId)=>[
                "projects",
                projectId,
                "detail"
            ],
        list: ()=>[
                "projects",
                "list"
            ],
        members: (projectId)=>[
                "projects",
                projectId,
                "members"
            ],
        modelAssignmentDatasets: (projectId, assignmentId)=>[
                "projects",
                projectId,
                "model-assignments",
                "datasets",
                assignmentId
            ],
        modelAssignmentDetail: (projectId, assignmentId)=>[
                "projects",
                projectId,
                "model-assignments",
                "detail",
                assignmentId
            ],
        modelAssignments: (projectId)=>[
                "projects",
                projectId,
                "model-assignments",
                "list"
            ],
        search: (projectId, filters)=>[
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
            ],
        entities: (projectId, filters)=>[
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
            ],
        entityDetail: (projectId, entityId)=>[
                "projects",
                projectId,
                "entities",
                "detail",
                entityId
            ],
        entityOccurrences: (projectId, entityId, filters)=>[
                "projects",
                projectId,
                "entities",
                "occurrences",
                entityId,
                {
                    cursor: normalizeNumber(filters.cursor),
                    limit: normalizeNumber(filters.limit)
                }
            ],
        derivatives: (projectId, filters)=>[
                "projects",
                projectId,
                "derivatives",
                "list",
                {
                    scope: normalizeText(filters.scope)
                }
            ],
        derivativeDetail: (projectId, derivativeId)=>[
                "projects",
                projectId,
                "derivatives",
                "detail",
                derivativeId
            ],
        derivativeStatus: (projectId, derivativeId)=>[
                "projects",
                projectId,
                "derivatives",
                "status",
                derivativeId
            ],
        derivativePreview: (projectId, derivativeId)=>[
                "projects",
                projectId,
                "derivatives",
                "preview",
                derivativeId
            ],
        indexesActive: (projectId)=>[
                "projects",
                projectId,
                "indexes",
                "active"
            ],
        indexesList: (projectId, kind)=>[
                "projects",
                projectId,
                "indexes",
                "list",
                normalizeText(kind)
            ],
        indexesDetail: (projectId, kind, indexId)=>[
                "projects",
                projectId,
                "indexes",
                "detail",
                normalizeText(kind),
                indexId
            ],
        indexesStatus: (projectId, kind, indexId)=>[
                "projects",
                projectId,
                "indexes",
                "status",
                normalizeText(kind),
                indexId
            ],
        policyActive: (projectId)=>[
                "projects",
                projectId,
                "policies",
                "active"
            ],
        policyCompare: (projectId, policyId, filters)=>[
                "projects",
                projectId,
                "policies",
                "compare",
                policyId,
                {
                    against: normalizeText(filters.against),
                    againstBaselineSnapshotId: normalizeText(filters.againstBaselineSnapshotId)
                }
            ],
        policyDetail: (projectId, policyId)=>[
                "projects",
                projectId,
                "policies",
                "detail",
                policyId
            ],
        policyExplainability: (projectId, policyId)=>[
                "projects",
                projectId,
                "policies",
                "explainability",
                policyId
            ],
        policyEvents: (projectId, policyId)=>[
                "projects",
                projectId,
                "policies",
                "events",
                policyId
            ],
        policyLineage: (projectId, policyId)=>[
                "projects",
                projectId,
                "policies",
                "lineage",
                policyId
            ],
        policyList: (projectId)=>[
                "projects",
                projectId,
                "policies",
                "list"
            ],
        policySnapshot: (projectId, policyId, rulesSha256)=>[
                "projects",
                projectId,
                "policies",
                "snapshot",
                policyId,
                normalizeText(rulesSha256)
            ],
        policyUsage: (projectId, policyId)=>[
                "projects",
                projectId,
                "policies",
                "usage",
                policyId
            ],
        pseudonymRegistryDetail: (projectId, entryId)=>[
                "projects",
                projectId,
                "pseudonym-registry",
                "detail",
                entryId
            ],
        pseudonymRegistryEvents: (projectId, entryId)=>[
                "projects",
                projectId,
                "pseudonym-registry",
                "events",
                entryId
            ],
        pseudonymRegistryList: (projectId)=>[
                "projects",
                projectId,
                "pseudonym-registry",
                "list"
            ],
        projectActivity: (projectId)=>[
                "projects",
                projectId,
                "activity"
            ],
        workspace: (projectId)=>[
                "projects",
                projectId,
                "workspace"
            ]
    },
    security: {
        status: ()=>[
                "security",
                "status"
            ]
    },
    system: {
        health: ()=>[
                "system",
                "health"
            ],
        readiness: ()=>[
                "system",
                "readiness"
            ]
    }
};
function stableSortObject(value) {
    const entries = Object.entries(value).sort(([a], [b])=>a.localeCompare(b));
    const sorted = {};
    for (const [key, entryValue] of entries){
        sorted[key] = normalizeQueryKeyPart(entryValue);
    }
    return sorted;
}
function normalizeQueryKeyPart(value) {
    if (Array.isArray(value)) {
        return value.map((item)=>normalizeQueryKeyPart(item));
    }
    if (value && typeof value === "object") {
        return stableSortObject(value);
    }
    return value;
}
function serializeQueryKey(queryKey) {
    return JSON.stringify(normalizeQueryKeyPart(queryKey));
}
}),
"[project]/web/lib/data/browser-api-client.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "requestBrowserApi",
    ()=>requestBrowserApi
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$cache$2d$policy$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/web/lib/data/cache-policy.ts [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$api$2d$types$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/web/lib/data/api-types.ts [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$query$2d$keys$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/web/lib/data/query-keys.ts [app-ssr] (ecmascript)");
;
;
;
async function parseJsonPayload(response) {
    try {
        return await response.json();
    } catch  {
        return undefined;
    }
}
function resolveScopedPath(path) {
    if (path.startsWith("http://") || path.startsWith("https://")) {
        return path;
    }
    return path.startsWith("/") ? path : `/${path}`;
}
async function requestBrowserApi(options) {
    const method = (0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$api$2d$types$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["normalizeMethod"])(options.method);
    const policy = __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$cache$2d$policy$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["queryCachePolicy"][options.cacheClass ?? "operations-live"];
    const path = resolveScopedPath(options.path);
    const baseOrigin = options.origin?.replace(/\/+$/, "") ?? "";
    const url = path.startsWith("http") ? path : `${baseOrigin}${path}`;
    const headers = new Headers(options.headers);
    if (options.queryKey) {
        headers.set("X-UKDE-Query-Key", (0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$query$2d$keys$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["serializeQueryKey"])(options.queryKey));
    }
    let response;
    try {
        response = await fetch(url, {
            method,
            body: options.body,
            headers,
            credentials: options.credentials ?? "same-origin",
            signal: options.signal,
            cache: policy.fetchCache
        });
    } catch  {
        return {
            ok: false,
            status: 503,
            detail: "API is unavailable.",
            error: {
                code: "NETWORK",
                detail: "API is unavailable.",
                retryable: (0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$api$2d$types$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["resolveRetryable"])("NETWORK", method)
            }
        };
    }
    if (options.expectNoContent || response.status === 204) {
        return {
            ok: response.ok,
            status: response.status,
            ...response.ok ? {} : {
                detail: "Request failed.",
                error: {
                    code: (0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$api$2d$types$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["resolveErrorCode"])(response.status),
                    detail: "Request failed.",
                    retryable: (0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$api$2d$types$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["resolveRetryable"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$api$2d$types$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["resolveErrorCode"])(response.status), method)
                }
            }
        };
    }
    const parsed = await parseJsonPayload(response);
    if (!response.ok && options.allowStatuses && options.allowStatuses.includes(response.status)) {
        return {
            ok: true,
            status: response.status,
            data: parsed
        };
    }
    if (!response.ok) {
        const code = (0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$api$2d$types$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["resolveErrorCode"])(response.status);
        const detail = (0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$api$2d$types$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["normalizeDetail"])(parsed);
        return {
            ok: false,
            status: response.status,
            detail,
            error: {
                code,
                detail,
                retryable: (0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$api$2d$types$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["resolveRetryable"])(code, method)
            }
        };
    }
    return {
        ok: true,
        status: response.status,
        data: parsed
    };
}
}),
"[project]/web/components/document-preprocess-run-actions.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "DocumentPreprocessRunActions",
    ()=>DocumentPreprocessRunActions
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/.pnpm/next@16.1.6_@playwright+test@1.58.2_react-dom@19.2.4_react@19.2.4__react@19.2.4/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/.pnpm/next@16.1.6_@playwright+test@1.58.2_react-dom@19.2.4_react@19.2.4__react@19.2.4/node_modules/next/navigation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/.pnpm/next@16.1.6_@playwright+test@1.58.2_react-dom@19.2.4_react@19.2.4__react@19.2.4/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$primitives$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/packages/ui/src/primitives.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$browser$2d$api$2d$client$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/web/lib/data/browser-api-client.ts [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$routes$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/web/lib/routes.ts [app-ssr] (ecmascript)");
"use client";
;
;
;
;
;
;
const ADVANCED_RISK_CONFIRMATION_COPY = "Advanced full-document preprocessing can remove faint handwriting details. Confirm only when stronger cleanup is necessary and compare review will follow.";
const PROFILE_DESCRIPTIONS = {
    BALANCED: "Safe default profile for deterministic grayscale cleanup.",
    CONSERVATIVE: "Lower-intensity cleanup for fragile scans and faint handwriting.",
    AGGRESSIVE: "Stronger cleanup with optional adaptive binarization.",
    BLEED_THROUGH: "Advanced show-through reduction; best results use paired recto/verso pages."
};
function DocumentPreprocessRunActions({ canMutate, documentId, isActiveProjection = false, projectId, runId, runStatus }) {
    const router = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRouter"])();
    const [pendingAction, setPendingAction] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const [error, setError] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const [success, setSuccess] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const [profileId, setProfileId] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])("BALANCED");
    const [advancedRiskConfirmed, setAdvancedRiskConfirmed] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [advancedRiskAcknowledgement, setAdvancedRiskAcknowledgement] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])("");
    const advancedProfileSelected = profileId === "AGGRESSIVE" || profileId === "BLEED_THROUGH";
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        if (!advancedProfileSelected) {
            setAdvancedRiskConfirmed(false);
            setAdvancedRiskAcknowledgement("");
        }
    }, [
        advancedProfileSelected
    ]);
    async function triggerCreate() {
        if (advancedProfileSelected && !advancedRiskConfirmed) {
            setError("Confirm advanced full-document risk posture before queueing.");
            setSuccess(null);
            return;
        }
        setPendingAction("create");
        setError(null);
        setSuccess(null);
        const result = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$browser$2d$api$2d$client$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["requestBrowserApi"])({
            method: "POST",
            path: `/projects/${projectId}/documents/${documentId}/preprocess-runs`,
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                profileId,
                advancedRiskConfirmed: advancedProfileSelected ? advancedRiskConfirmed : undefined,
                advancedRiskAcknowledgement: advancedProfileSelected ? advancedRiskAcknowledgement.trim() || ADVANCED_RISK_CONFIRMATION_COPY : undefined
            })
        });
        setPendingAction(null);
        if (!result.ok || !result.data) {
            setError(result.detail ?? "Preprocessing run creation failed.");
            return;
        }
        setSuccess("Preprocessing run queued.");
        router.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$routes$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["projectDocumentPreprocessingRunPath"])(projectId, documentId, result.data.id));
        router.refresh();
    }
    async function triggerRerun() {
        if (!runId) {
            return;
        }
        if (advancedProfileSelected && !advancedRiskConfirmed) {
            setError("Confirm advanced full-document risk posture before queueing.");
            setSuccess(null);
            return;
        }
        setPendingAction("rerun");
        setError(null);
        setSuccess(null);
        const result = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$browser$2d$api$2d$client$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["requestBrowserApi"])({
            method: "POST",
            path: `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/rerun`,
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                profileId,
                advancedRiskConfirmed: advancedProfileSelected ? advancedRiskConfirmed : undefined,
                advancedRiskAcknowledgement: advancedProfileSelected ? advancedRiskAcknowledgement.trim() || ADVANCED_RISK_CONFIRMATION_COPY : undefined
            })
        });
        setPendingAction(null);
        if (!result.ok || !result.data) {
            setError(result.detail ?? "Preprocessing rerun request failed.");
            return;
        }
        setSuccess("Rerun queued.");
        router.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$routes$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["projectDocumentPreprocessingRunPath"])(projectId, documentId, result.data.id));
        router.refresh();
    }
    async function triggerCancel() {
        if (!runId) {
            return;
        }
        setPendingAction("cancel");
        setError(null);
        setSuccess(null);
        const result = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$browser$2d$api$2d$client$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["requestBrowserApi"])({
            method: "POST",
            path: `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/cancel`
        });
        setPendingAction(null);
        if (!result.ok) {
            setError(result.detail ?? "Preprocessing cancel request failed.");
            return;
        }
        setSuccess("Run cancellation recorded.");
        router.refresh();
    }
    async function triggerActivate() {
        if (!runId) {
            return;
        }
        setPendingAction("activate");
        setError(null);
        setSuccess(null);
        const result = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$web$2f$lib$2f$data$2f$browser$2d$api$2d$client$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["requestBrowserApi"])({
            method: "POST",
            path: `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/activate`
        });
        setPendingAction(null);
        if (!result.ok) {
            setError(result.detail ?? "Preprocess run activation failed.");
            return;
        }
        setSuccess("Run activated for document projection.");
        router.refresh();
    }
    if (!canMutate) {
        return null;
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
        className: "sectionCard ukde-panel",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                children: "Run actions"
            }, void 0, false, {
                fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                lineNumber: 178,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("details", {
                className: "preprocessRunAdvancedControls",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("summary", {
                        children: "Advanced profile controls"
                    }, void 0, false, {
                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                        lineNumber: 180,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                        children: [
                            "Profile",
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("select", {
                                value: profileId,
                                onChange: (event)=>setProfileId(event.target.value),
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("option", {
                                        value: "BALANCED",
                                        children: "Balanced"
                                    }, void 0, false, {
                                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                                        lineNumber: 189,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("option", {
                                        value: "CONSERVATIVE",
                                        children: "Conservative"
                                    }, void 0, false, {
                                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                                        lineNumber: 190,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("option", {
                                        value: "AGGRESSIVE",
                                        children: "Aggressive (Advanced)"
                                    }, void 0, false, {
                                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                                        lineNumber: 191,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("option", {
                                        value: "BLEED_THROUGH",
                                        children: "Bleed-through (Advanced)"
                                    }, void 0, false, {
                                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                                        lineNumber: 192,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                                lineNumber: 183,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                        lineNumber: 181,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        className: "ukde-muted",
                        children: PROFILE_DESCRIPTIONS[profileId]
                    }, void 0, false, {
                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                        lineNumber: 195,
                        columnNumber: 9
                    }, this),
                    advancedProfileSelected ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                className: "ukde-muted",
                                children: ADVANCED_RISK_CONFIRMATION_COPY
                            }, void 0, false, {
                                fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                                lineNumber: 198,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                                className: "qualityWizardChoice",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                        type: "checkbox",
                                        checked: advancedRiskConfirmed,
                                        onChange: (event)=>setAdvancedRiskConfirmed(event.target.checked)
                                    }, void 0, false, {
                                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                                        lineNumber: 200,
                                        columnNumber: 15
                                    }, this),
                                    "I confirm advanced full-document processing for this run."
                                ]
                            }, void 0, true, {
                                fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                                lineNumber: 199,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                                children: [
                                    "Confirmation note (optional)",
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                        type: "text",
                                        maxLength: 400,
                                        value: advancedRiskAcknowledgement,
                                        onChange: (event)=>setAdvancedRiskAcknowledgement(event.target.value),
                                        placeholder: "Reason for stronger cleanup"
                                    }, void 0, false, {
                                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                                        lineNumber: 211,
                                        columnNumber: 15
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                                lineNumber: 209,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true) : null
                ]
            }, void 0, true, {
                fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                lineNumber: 179,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "buttonRow",
                children: [
                    !runId ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "secondaryButton",
                        type: "button",
                        disabled: pendingAction !== null || advancedProfileSelected && !advancedRiskConfirmed,
                        onClick: ()=>{
                            void triggerCreate();
                        },
                        children: pendingAction === "create" ? "Queueing..." : "Run preprocessing"
                    }, void 0, false, {
                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                        lineNumber: 226,
                        columnNumber: 11
                    }, this) : null,
                    runId ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "secondaryButton",
                        type: "button",
                        disabled: pendingAction !== null || advancedProfileSelected && !advancedRiskConfirmed,
                        onClick: ()=>{
                            void triggerRerun();
                        },
                        children: pendingAction === "rerun" ? "Queueing rerun..." : "Rerun"
                    }, void 0, false, {
                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                        lineNumber: 241,
                        columnNumber: 11
                    }, this) : null,
                    runId && (runStatus === "QUEUED" || runStatus === "RUNNING") ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "secondaryButton",
                        type: "button",
                        disabled: pendingAction !== null,
                        onClick: ()=>{
                            void triggerCancel();
                        },
                        children: pendingAction === "cancel" ? "Canceling..." : "Cancel run"
                    }, void 0, false, {
                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                        lineNumber: 256,
                        columnNumber: 11
                    }, this) : null,
                    runId && runStatus === "SUCCEEDED" && !isActiveProjection ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "secondaryButton",
                        type: "button",
                        disabled: pendingAction !== null,
                        onClick: ()=>{
                            void triggerActivate();
                        },
                        children: pendingAction === "activate" ? "Activating..." : "Activate run"
                    }, void 0, false, {
                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                        lineNumber: 268,
                        columnNumber: 11
                    }, this) : null,
                    runId && runStatus === "SUCCEEDED" && isActiveProjection ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                        className: "ukde-muted",
                        children: "Run is already the active projection."
                    }, void 0, false, {
                        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                        lineNumber: 280,
                        columnNumber: 11
                    }, this) : null
                ]
            }, void 0, true, {
                fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                lineNumber: 224,
                columnNumber: 7
            }, this),
            error ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$primitives$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["InlineAlert"], {
                title: "Preprocessing action failed",
                tone: "danger",
                children: error
            }, void 0, false, {
                fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                lineNumber: 284,
                columnNumber: 9
            }, this) : null,
            success ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$primitives$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["InlineAlert"], {
                title: "Preprocessing action completed",
                tone: "success",
                children: success
            }, void 0, false, {
                fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
                lineNumber: 289,
                columnNumber: 9
            }, this) : null
        ]
    }, void 0, true, {
        fileName: "[project]/web/components/document-preprocess-run-actions.tsx",
        lineNumber: 177,
        columnNumber: 5
    }, this);
}
}),
];

//# sourceMappingURL=web_ad948c5b._.js.map