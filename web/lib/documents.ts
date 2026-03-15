import type {
  ActivateDocumentLayoutRunResponse,
  ActivateDocumentPreprocessRunResponse,
  ActivateDocumentRedactionRunResponse,
  ActivateDocumentTranscriptionRunResponse,
  CompleteDocumentRedactionRunReviewRequest,
  CreateDocumentLayoutRunRequest,
  CreateDocumentPreprocessRunRequest,
  CreateDocumentRedactionRunRequest,
  CreateDocumentTranscriptionFallbackRunRequest,
  CreateDocumentTranscriptionRunRequest,
  DocumentLayoutActiveRunResponse,
  DocumentLayoutPageRecallStatusResponse,
  DocumentLayoutRescueCandidateListResponse,
  DocumentLayoutOverviewResponse,
  DocumentLayoutRun,
  DocumentLayoutRunListResponse,
  DocumentLayoutRunPageListResponse,
  DocumentLayoutPageOverlay,
  UpdateDocumentLayoutElementsRequest,
  UpdateDocumentLayoutElementsResponse,
  UpdateDocumentLayoutReadingOrderRequest,
  UpdateDocumentLayoutReadingOrderResponse,
  DocumentLayoutRunStatusResponse,
  DocumentPreprocessActiveRunResponse,
  DocumentPreprocessCompareResponse,
  DocumentPreprocessOverviewResponse,
  DocumentPreprocessPageResult,
  DocumentPreprocessQualityResponse,
  DocumentPreprocessRun,
  DocumentPreprocessRunListResponse,
  DocumentPreprocessRunPageListResponse,
  DocumentPreprocessRunStatusResponse,
  DocumentRedactionActiveRunResponse,
  DocumentRedactionCompareResponse,
  DocumentRedactionFinding,
  DocumentRedactionFindingListResponse,
  DocumentGovernanceLedgerResponse,
  DocumentGovernanceLedgerEntriesResponse,
  DocumentGovernanceLedgerSummaryResponse,
  DocumentGovernanceLedgerVerifyDetailResponse,
  DocumentGovernanceLedgerVerifyRunsResponse,
  DocumentGovernanceLedgerVerifyStatusResponse,
  DocumentGovernanceLedgerStatusResponse,
  DocumentGovernanceManifestEntriesResponse,
  DocumentGovernanceManifestHashResponse,
  DocumentGovernanceManifestResponse,
  DocumentGovernanceManifestStatusResponse,
  DocumentGovernanceOverviewResponse,
  DocumentGovernanceRunEventsResponse,
  DocumentGovernanceRunOverviewResponse,
  DocumentGovernanceRunsResponse,
  DocumentRedactionOverviewResponse,
  DocumentRedactionPageReview,
  DocumentRedactionPreviewStatusResponse,
  DocumentRedactionRun,
  DocumentRedactionRunEventsResponse,
  DocumentRedactionRunListResponse,
  DocumentRedactionRunOutput,
  DocumentRedactionRunPageListResponse,
  DocumentRedactionRunReview,
  DocumentRedactionRunStatusResponse,
  DocumentTranscriptionActiveRunResponse,
  DocumentTranscriptionCompareResponse,
  DocumentTranscriptionLineVersionHistoryResponse,
  CorrectDocumentTranscriptionLineRequest,
  CorrectDocumentTranscriptionLineResponse,
  FinalizeDocumentTranscriptionCompareRequest,
  FinalizeDocumentTranscriptionCompareResponse,
  DocumentTranscriptionLineResultListResponse,
  DocumentTranscriptionMetricsResponse,
  DocumentTranscriptionOverviewResponse,
  DocumentTranscriptionRun,
  DocumentTranscriptionRunListResponse,
  DocumentTranscriptionRunPageListResponse,
  DocumentTranscriptionRunRescueStatusResponse,
  DocumentTranscriptionRunStatusResponse,
  DocumentTranscriptionTokenResultListResponse,
  DocumentTranscriptionTriageResponse,
  DocumentTranscriptionPageRescueSourcesResponse,
  UpdateDocumentTranscriptionTriageAssignmentRequest,
  UpdateDocumentTranscriptionTriageAssignmentResponse,
  UpdateDocumentTranscriptionRescueResolutionRequest,
  RecordTranscriptVariantSuggestionDecisionRequest,
  RecordTranscriptVariantSuggestionDecisionResponse,
  PageLayoutResultStatus,
  PageRecallStatus,
  PreprocessPageResultStatus,
  TranscriptVariantKind,
  TranscriptVariantLayerListResponse,
  TranscriptionTokenSourceKind,
  TranscriptionRunStatus,
  CreateDocumentUploadSessionRequest,
  DocumentProcessingRunDetailResponse,
  DocumentListSort,
  DocumentProcessingRunStatusResponse,
  RerunDocumentPreprocessRunRequest,
  ProjectDocumentUploadSessionStatus,
  DocumentTimelineResponse,
  DocumentStatus,
  DocumentPageVariantsResponse,
  ProjectDocument,
  ProjectDocumentImportStatus,
  ProjectDocumentPage,
  ProjectDocumentPageDetail,
  ProjectDocumentPageListResponse,
  ProjectDocumentListResponse,
  RecordDocumentTranscriptionCompareDecisionsRequest,
  RecordDocumentTranscriptionCompareDecisionsResponse,
  CreateDocumentRedactionAreaMaskRequest,
  PatchDocumentRedactionAreaMaskRequest,
  PatchDocumentRedactionAreaMaskResponse,
  PatchDocumentRedactionFindingRequest,
  PatchDocumentRedactionPageReviewRequest,
  TranscriptVersionLineage,
  SortDirection
} from "@ukde/contracts";

import {
  projectDocumentPageImagePath,
  type DocumentPageImageVariant
} from "./document-page-image";
import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryCacheClass } from "./data/cache-policy";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type DocumentApiResult<T> = ApiResult<T>;
export type { DocumentPageImageVariant };

export interface ProjectDocumentListFilters {
  cursor?: number;
  direction?: SortDirection;
  from?: string;
  pageSize?: number;
  q?: string;
  search?: string;
  sort?: DocumentListSort;
  status?: DocumentStatus;
  to?: string;
  uploader?: string;
}

export interface ProjectDocumentPreprocessRunListFilters {
  cursor?: number;
  pageSize?: number;
}

export interface ProjectDocumentPreprocessQualityFilters {
  cursor?: number;
  pageSize?: number;
  runId?: string;
  status?: PreprocessPageResultStatus;
  warning?: string;
}

export interface ProjectDocumentPreprocessRunPagesFilters {
  cursor?: number;
  pageSize?: number;
  status?: PreprocessPageResultStatus;
  warning?: string;
}

export interface ProjectDocumentLayoutRunListFilters {
  cursor?: number;
  pageSize?: number;
}

export interface ProjectDocumentLayoutRunPagesFilters {
  cursor?: number;
  pageRecallStatus?: PageRecallStatus;
  pageSize?: number;
  status?: PageLayoutResultStatus;
}

export interface ProjectDocumentTranscriptionRunListFilters {
  cursor?: number;
  pageSize?: number;
}

export interface ProjectDocumentTranscriptionTriageFilters {
  confidenceBelow?: number;
  cursor?: number;
  page?: number;
  pageSize?: number;
  runId?: string;
  status?: TranscriptionRunStatus;
}

export interface ProjectDocumentTranscriptionMetricsFilters {
  confidenceBelow?: number;
  runId?: string;
}

export interface ProjectDocumentTranscriptionRunPagesFilters {
  cursor?: number;
  pageSize?: number;
  status?: TranscriptionRunStatus;
}

export interface ProjectDocumentTranscriptionRunPageLinesFilters {
  lineId?: string;
  sourceKind?: TranscriptionTokenSourceKind;
  sourceRefId?: string;
  tokenId?: string;
  workspaceView?: boolean;
}

export interface ProjectDocumentTranscriptionVariantLayersFilters {
  variantKind?: TranscriptVariantKind;
}

export interface ProjectDocumentTranscriptionCompareFilters {
  lineId?: string;
  page?: number;
  tokenId?: string;
}

export interface ProjectDocumentRedactionRunListFilters {
  cursor?: number;
  pageSize?: number;
}

export interface ProjectDocumentRedactionRunPagesFilters {
  category?: string;
  cursor?: number;
  directIdentifiersOnly?: boolean;
  pageSize?: number;
  unresolvedOnly?: boolean;
}

export interface ProjectDocumentRedactionRunPageFindingsFilters {
  category?: string;
  directIdentifiersOnly?: boolean;
  findingId?: string;
  lineId?: string;
  tokenId?: string;
  unresolvedOnly?: boolean;
  workspaceView?: boolean;
}

export interface ProjectDocumentRedactionCompareFilters {
  findingId?: string;
  lineId?: string;
  page?: number;
  tokenId?: string;
}

export interface ProjectDocumentPageVariantsFilters {
  runId?: string;
}

export interface ProjectDocumentGovernanceManifestEntriesFilters {
  category?: string;
  cursor?: number;
  from?: string;
  limit?: number;
  page?: number;
  reviewState?: string;
  to?: string;
}

export interface ProjectDocumentGovernanceLedgerEntriesFilters {
  cursor?: number;
  limit?: number;
  view?: "list" | "timeline";
}

async function requestDocumentApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    cacheClass?: QueryCacheClass;
    expectNoContent?: boolean;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<DocumentApiResult<T>> {
  return requestServerApi<T>({
    path,
    method: options?.method,
    headers: options?.headers,
    body: options?.body,
    expectNoContent: options?.expectNoContent,
    cacheClass: options?.cacheClass ?? "mutable-list",
    queryKey: options?.queryKey
  });
}

function toQueryString(filters: ProjectDocumentListFilters): string {
  const params = new URLSearchParams();
  const searchText =
    typeof filters.search === "string" && filters.search.trim().length > 0
      ? filters.search.trim()
      : typeof filters.q === "string" && filters.q.trim().length > 0
        ? filters.q.trim()
        : undefined;

  if (searchText) {
    params.set("search", searchText);
  }
  if (typeof filters.status === "string") {
    params.set("status", filters.status);
  }
  if (typeof filters.uploader === "string" && filters.uploader.trim().length > 0) {
    params.set("uploader", filters.uploader.trim());
  }
  if (typeof filters.from === "string" && filters.from.trim().length > 0) {
    params.set("from", filters.from.trim());
  }
  if (typeof filters.to === "string" && filters.to.trim().length > 0) {
    params.set("to", filters.to.trim());
  }
  if (typeof filters.sort === "string") {
    params.set("sort", filters.sort);
  }
  if (typeof filters.direction === "string") {
    params.set("direction", filters.direction);
  }
  if (typeof filters.cursor === "number") {
    params.set("cursor", String(filters.cursor));
  }
  if (typeof filters.pageSize === "number") {
    params.set("pageSize", String(filters.pageSize));
  }

  const query = params.toString();
  return query ? `?${query}` : "";
}

function toPreprocessQueryString(
  filters:
    | ProjectDocumentPreprocessRunListFilters
    | ProjectDocumentPreprocessQualityFilters
    | ProjectDocumentPreprocessRunPagesFilters
    | ProjectDocumentPageVariantsFilters
): string {
  const params = new URLSearchParams();
  if ("runId" in filters && typeof filters.runId === "string" && filters.runId.trim()) {
    params.set("runId", filters.runId.trim());
  }
  if ("status" in filters && typeof filters.status === "string" && filters.status.trim()) {
    params.set("status", filters.status.trim());
  }
  if ("warning" in filters && typeof filters.warning === "string" && filters.warning.trim()) {
    params.set("warning", filters.warning.trim());
  }
  if ("cursor" in filters && typeof filters.cursor === "number") {
    params.set("cursor", String(filters.cursor));
  }
  if ("pageSize" in filters && typeof filters.pageSize === "number") {
    params.set("pageSize", String(filters.pageSize));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

function toLayoutQueryString(
  filters:
    | ProjectDocumentLayoutRunListFilters
    | ProjectDocumentLayoutRunPagesFilters
): string {
  const params = new URLSearchParams();
  if ("status" in filters && typeof filters.status === "string" && filters.status.trim()) {
    params.set("status", filters.status.trim());
  }
  if (
    "pageRecallStatus" in filters &&
    typeof filters.pageRecallStatus === "string" &&
    filters.pageRecallStatus.trim()
  ) {
    params.set("pageRecallStatus", filters.pageRecallStatus.trim());
  }
  if ("cursor" in filters && typeof filters.cursor === "number") {
    params.set("cursor", String(filters.cursor));
  }
  if ("pageSize" in filters && typeof filters.pageSize === "number") {
    params.set("pageSize", String(filters.pageSize));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

function toTranscriptionQueryString(
  filters:
    | ProjectDocumentTranscriptionRunListFilters
    | ProjectDocumentTranscriptionTriageFilters
    | ProjectDocumentTranscriptionMetricsFilters
    | ProjectDocumentTranscriptionRunPagesFilters
): string {
  const params = new URLSearchParams();
  if ("runId" in filters && typeof filters.runId === "string" && filters.runId.trim()) {
    params.set("runId", filters.runId.trim());
  }
  if ("status" in filters && typeof filters.status === "string" && filters.status.trim()) {
    params.set("status", filters.status.trim());
  }
  if (
    "confidenceBelow" in filters &&
    typeof filters.confidenceBelow === "number" &&
    Number.isFinite(filters.confidenceBelow)
  ) {
    params.set("confidenceBelow", String(filters.confidenceBelow));
  }
  if ("page" in filters && typeof filters.page === "number" && Number.isFinite(filters.page)) {
    params.set("page", String(Math.max(1, Math.round(filters.page))));
  }
  if ("cursor" in filters && typeof filters.cursor === "number") {
    params.set("cursor", String(filters.cursor));
  }
  if ("pageSize" in filters && typeof filters.pageSize === "number") {
    params.set("pageSize", String(filters.pageSize));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

function toTranscriptionVariantLayersQueryString(
  filters: ProjectDocumentTranscriptionVariantLayersFilters
): string {
  const params = new URLSearchParams();
  if (
    typeof filters.variantKind === "string" &&
    filters.variantKind.trim().length > 0
  ) {
    params.set("variantKind", filters.variantKind.trim());
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

function toGovernanceManifestEntriesQueryString(
  filters: ProjectDocumentGovernanceManifestEntriesFilters
): string {
  const params = new URLSearchParams();
  if (typeof filters.category === "string" && filters.category.trim().length > 0) {
    params.set("category", filters.category.trim());
  }
  if (
    typeof filters.reviewState === "string" &&
    filters.reviewState.trim().length > 0
  ) {
    params.set("reviewState", filters.reviewState.trim());
  }
  if (typeof filters.page === "number" && Number.isFinite(filters.page)) {
    params.set("page", String(Math.max(1, Math.round(filters.page))));
  }
  if (typeof filters.from === "string" && filters.from.trim().length > 0) {
    params.set("from", filters.from.trim());
  }
  if (typeof filters.to === "string" && filters.to.trim().length > 0) {
    params.set("to", filters.to.trim());
  }
  if (typeof filters.cursor === "number" && Number.isFinite(filters.cursor)) {
    params.set("cursor", String(Math.max(0, Math.floor(filters.cursor))));
  }
  if (typeof filters.limit === "number" && Number.isFinite(filters.limit)) {
    params.set("limit", String(Math.max(1, Math.floor(filters.limit))));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

function toGovernanceLedgerEntriesQueryString(
  filters: ProjectDocumentGovernanceLedgerEntriesFilters
): string {
  const params = new URLSearchParams();
  if (filters.view === "timeline") {
    params.set("view", "timeline");
  } else if (filters.view === "list") {
    params.set("view", "list");
  }
  if (typeof filters.cursor === "number" && Number.isFinite(filters.cursor)) {
    params.set("cursor", String(Math.max(0, Math.floor(filters.cursor))));
  }
  if (typeof filters.limit === "number" && Number.isFinite(filters.limit)) {
    params.set("limit", String(Math.max(1, Math.floor(filters.limit))));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

function toTranscriptionLineQueryString(
  filters: ProjectDocumentTranscriptionRunPageLinesFilters
): string {
  const params = new URLSearchParams();
  if (
    typeof filters.lineId === "string" &&
    filters.lineId.trim().length > 0
  ) {
    params.set("lineId", filters.lineId.trim());
  }
  if (
    typeof filters.tokenId === "string" &&
    filters.tokenId.trim().length > 0
  ) {
    params.set("tokenId", filters.tokenId.trim());
  }
  if (
    typeof filters.sourceKind === "string" &&
    filters.sourceKind.trim().length > 0
  ) {
    params.set("sourceKind", filters.sourceKind.trim());
  }
  if (
    typeof filters.sourceRefId === "string" &&
    filters.sourceRefId.trim().length > 0
  ) {
    params.set("sourceRefId", filters.sourceRefId.trim());
  }
  if (filters.workspaceView) {
    params.set("workspaceView", "true");
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

function toRedactionRunQueryString(
  filters: ProjectDocumentRedactionRunListFilters
): string {
  const params = new URLSearchParams();
  if (typeof filters.cursor === "number") {
    params.set("cursor", String(filters.cursor));
  }
  if (typeof filters.pageSize === "number") {
    params.set("pageSize", String(filters.pageSize));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

function toRedactionRunPagesQueryString(
  filters: ProjectDocumentRedactionRunPagesFilters
): string {
  const params = new URLSearchParams();
  if (typeof filters.category === "string" && filters.category.trim().length > 0) {
    params.set("category", filters.category.trim());
  }
  if (typeof filters.unresolvedOnly === "boolean") {
    params.set("unresolvedOnly", filters.unresolvedOnly ? "true" : "false");
  }
  if (typeof filters.directIdentifiersOnly === "boolean") {
    params.set(
      "directIdentifiersOnly",
      filters.directIdentifiersOnly ? "true" : "false"
    );
  }
  if (typeof filters.cursor === "number") {
    params.set("cursor", String(filters.cursor));
  }
  if (typeof filters.pageSize === "number") {
    params.set("pageSize", String(filters.pageSize));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

function toRedactionFindingsQueryString(
  filters: ProjectDocumentRedactionRunPageFindingsFilters
): string {
  const params = new URLSearchParams();
  if (typeof filters.category === "string" && filters.category.trim().length > 0) {
    params.set("category", filters.category.trim());
  }
  if (typeof filters.unresolvedOnly === "boolean") {
    params.set("unresolvedOnly", filters.unresolvedOnly ? "true" : "false");
  }
  if (typeof filters.directIdentifiersOnly === "boolean") {
    params.set(
      "directIdentifiersOnly",
      filters.directIdentifiersOnly ? "true" : "false"
    );
  }
  if (typeof filters.workspaceView === "boolean" && filters.workspaceView) {
    params.set("workspaceView", "true");
  }
  if (typeof filters.findingId === "string" && filters.findingId.trim().length > 0) {
    params.set("findingId", filters.findingId.trim());
  }
  if (typeof filters.lineId === "string" && filters.lineId.trim().length > 0) {
    params.set("lineId", filters.lineId.trim());
  }
  if (typeof filters.tokenId === "string" && filters.tokenId.trim().length > 0) {
    params.set("tokenId", filters.tokenId.trim());
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

function toRedactionCompareQueryString(
  baseRunId: string,
  candidateRunId: string,
  filters: ProjectDocumentRedactionCompareFilters
): string {
  const params = new URLSearchParams({
    baseRunId,
    candidateRunId
  });
  if (typeof filters.page === "number" && Number.isFinite(filters.page)) {
    params.set("page", String(Math.max(1, Math.round(filters.page))));
  }
  if (typeof filters.findingId === "string" && filters.findingId.trim().length > 0) {
    params.set("findingId", filters.findingId.trim());
  }
  if (typeof filters.lineId === "string" && filters.lineId.trim().length > 0) {
    params.set("lineId", filters.lineId.trim());
  }
  if (typeof filters.tokenId === "string" && filters.tokenId.trim().length > 0) {
    params.set("tokenId", filters.tokenId.trim());
  }
  return `?${params.toString()}`;
}

export async function listProjectDocuments(
  projectId: string,
  filters: ProjectDocumentListFilters = {}
): Promise<DocumentApiResult<ProjectDocumentListResponse>> {
  return requestDocumentApi<ProjectDocumentListResponse>(
    `/projects/${projectId}/documents${toQueryString(filters)}`,
    {
      queryKey: queryKeys.documents.list(projectId, filters)
    }
  );
}

export async function getProjectDocument(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<ProjectDocument>> {
  return requestDocumentApi<ProjectDocument>(
    `/projects/${projectId}/documents/${documentId}`,
    {
      queryKey: queryKeys.documents.detail(projectId, documentId)
    }
  );
}

export async function getProjectDocumentTimeline(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentTimelineResponse>> {
  return requestDocumentApi<DocumentTimelineResponse>(
    `/projects/${projectId}/documents/${documentId}/timeline`,
    {
      queryKey: queryKeys.documents.timeline(projectId, documentId)
    }
  );
}

export async function listProjectDocumentProcessingRuns(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentTimelineResponse>> {
  return requestDocumentApi<DocumentTimelineResponse>(
    `/projects/${projectId}/documents/${documentId}/processing-runs`,
    {
      queryKey: queryKeys.documents.timeline(projectId, documentId)
    }
  );
}

export async function getProjectDocumentProcessingRunStatus(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentProcessingRunStatusResponse>> {
  return requestDocumentApi<DocumentProcessingRunStatusResponse>(
    `/projects/${projectId}/documents/${documentId}/processing-runs/${runId}/status`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.processingRunStatus(
        projectId,
        documentId,
        runId
      )
    }
  );
}

export async function getProjectDocumentProcessingRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentProcessingRunDetailResponse>> {
  return requestDocumentApi<DocumentProcessingRunDetailResponse>(
    `/projects/${projectId}/documents/${documentId}/processing-runs/${runId}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.processingRunDetail(
        projectId,
        documentId,
        runId
      )
    }
  );
}

export async function getProjectDocumentPreprocessOverview(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentPreprocessOverviewResponse>> {
  return requestDocumentApi<DocumentPreprocessOverviewResponse>(
    `/projects/${projectId}/documents/${documentId}/preprocessing/overview`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.preprocessOverview(projectId, documentId)
    }
  );
}

export async function getProjectDocumentPreprocessQuality(
  projectId: string,
  documentId: string,
  filters: ProjectDocumentPreprocessQualityFilters = {}
): Promise<DocumentApiResult<DocumentPreprocessQualityResponse>> {
  return requestDocumentApi<DocumentPreprocessQualityResponse>(
    `/projects/${projectId}/documents/${documentId}/preprocessing/quality${toPreprocessQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.preprocessQuality(projectId, documentId, filters)
    }
  );
}

export async function createProjectDocumentPreprocessRun(
  projectId: string,
  documentId: string,
  payload: CreateDocumentPreprocessRunRequest = {}
): Promise<DocumentApiResult<DocumentPreprocessRun>> {
  return requestDocumentApi<DocumentPreprocessRun>(
    `/projects/${projectId}/documents/${documentId}/preprocess-runs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function getProjectDocumentActivePreprocessRun(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentPreprocessActiveRunResponse>> {
  return requestDocumentApi<DocumentPreprocessActiveRunResponse>(
    `/projects/${projectId}/documents/${documentId}/preprocess-runs/active`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.preprocessActiveRun(projectId, documentId)
    }
  );
}

export async function listProjectDocumentPreprocessRuns(
  projectId: string,
  documentId: string,
  filters: ProjectDocumentPreprocessRunListFilters = {}
): Promise<DocumentApiResult<DocumentPreprocessRunListResponse>> {
  return requestDocumentApi<DocumentPreprocessRunListResponse>(
    `/projects/${projectId}/documents/${documentId}/preprocess-runs${toPreprocessQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.preprocessRuns(projectId, documentId, filters)
    }
  );
}

export async function getProjectDocumentPreprocessRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentPreprocessRun>> {
  return requestDocumentApi<DocumentPreprocessRun>(
    `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.preprocessRunDetail(projectId, documentId, runId)
    }
  );
}

export async function getProjectDocumentPreprocessRunStatus(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentPreprocessRunStatusResponse>> {
  return requestDocumentApi<DocumentPreprocessRunStatusResponse>(
    `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/status`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.preprocessRunStatus(projectId, documentId, runId)
    }
  );
}

export async function listProjectDocumentPreprocessRunPages(
  projectId: string,
  documentId: string,
  runId: string,
  filters: ProjectDocumentPreprocessRunPagesFilters = {}
): Promise<DocumentApiResult<DocumentPreprocessRunPageListResponse>> {
  return requestDocumentApi<DocumentPreprocessRunPageListResponse>(
    `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/pages${toPreprocessQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.preprocessRunPages(
        projectId,
        documentId,
        runId,
        filters
      )
    }
  );
}

export async function getProjectDocumentPreprocessRunPage(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string
): Promise<DocumentApiResult<DocumentPreprocessPageResult>> {
  return requestDocumentApi<DocumentPreprocessPageResult>(
    `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/pages/${pageId}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.preprocessRunPage(
        projectId,
        documentId,
        runId,
        pageId
      )
    }
  );
}

export async function rerunProjectDocumentPreprocessRun(
  projectId: string,
  documentId: string,
  runId: string,
  payload: RerunDocumentPreprocessRunRequest = {}
): Promise<DocumentApiResult<DocumentPreprocessRun>> {
  return requestDocumentApi<DocumentPreprocessRun>(
    `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/rerun`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function cancelProjectDocumentPreprocessRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentPreprocessRun>> {
  return requestDocumentApi<DocumentPreprocessRun>(
    `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/cancel`,
    {
      method: "POST"
    }
  );
}

export async function activateProjectDocumentPreprocessRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<ActivateDocumentPreprocessRunResponse>> {
  return requestDocumentApi<ActivateDocumentPreprocessRunResponse>(
    `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/activate`,
    {
      method: "POST"
    }
  );
}

export async function compareProjectDocumentPreprocessRuns(
  projectId: string,
  documentId: string,
  baseRunId: string,
  candidateRunId: string
): Promise<DocumentApiResult<DocumentPreprocessCompareResponse>> {
  return requestDocumentApi<DocumentPreprocessCompareResponse>(
    `/projects/${projectId}/documents/${documentId}/preprocess-runs/compare?baseRunId=${encodeURIComponent(baseRunId)}&candidateRunId=${encodeURIComponent(candidateRunId)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.preprocessCompare(
        projectId,
        documentId,
        baseRunId,
        candidateRunId
      )
    }
  );
}

export async function getProjectDocumentLayoutOverview(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentLayoutOverviewResponse>> {
  return requestDocumentApi<DocumentLayoutOverviewResponse>(
    `/projects/${projectId}/documents/${documentId}/layout/overview`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.layoutOverview(projectId, documentId)
    }
  );
}

export async function createProjectDocumentLayoutRun(
  projectId: string,
  documentId: string,
  payload: CreateDocumentLayoutRunRequest = {}
): Promise<DocumentApiResult<DocumentLayoutRun>> {
  return requestDocumentApi<DocumentLayoutRun>(
    `/projects/${projectId}/documents/${documentId}/layout-runs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function getProjectDocumentActiveLayoutRun(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentLayoutActiveRunResponse>> {
  return requestDocumentApi<DocumentLayoutActiveRunResponse>(
    `/projects/${projectId}/documents/${documentId}/layout-runs/active`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.layoutActiveRun(projectId, documentId)
    }
  );
}

export async function listProjectDocumentLayoutRuns(
  projectId: string,
  documentId: string,
  filters: ProjectDocumentLayoutRunListFilters = {}
): Promise<DocumentApiResult<DocumentLayoutRunListResponse>> {
  return requestDocumentApi<DocumentLayoutRunListResponse>(
    `/projects/${projectId}/documents/${documentId}/layout-runs${toLayoutQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.layoutRuns(projectId, documentId, filters)
    }
  );
}

export async function getProjectDocumentLayoutRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentLayoutRun>> {
  return requestDocumentApi<DocumentLayoutRun>(
    `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.layoutRunDetail(projectId, documentId, runId)
    }
  );
}

export async function getProjectDocumentLayoutRunStatus(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentLayoutRunStatusResponse>> {
  return requestDocumentApi<DocumentLayoutRunStatusResponse>(
    `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}/status`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.layoutRunStatus(projectId, documentId, runId)
    }
  );
}

export async function listProjectDocumentLayoutRunPages(
  projectId: string,
  documentId: string,
  runId: string,
  filters: ProjectDocumentLayoutRunPagesFilters = {}
): Promise<DocumentApiResult<DocumentLayoutRunPageListResponse>> {
  return requestDocumentApi<DocumentLayoutRunPageListResponse>(
    `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}/pages${toLayoutQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.layoutRunPages(
        projectId,
        documentId,
        runId,
        filters
      )
    }
  );
}

export async function getProjectDocumentLayoutPageOverlay(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string
): Promise<DocumentApiResult<DocumentLayoutPageOverlay>> {
  return requestDocumentApi<DocumentLayoutPageOverlay>(
    `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}/pages/${pageId}/overlay`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.layoutPageOverlay(
        projectId,
        documentId,
        runId,
        pageId
      )
    }
  );
}

export async function updateProjectDocumentLayoutPageReadingOrder(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  payload: UpdateDocumentLayoutReadingOrderRequest
): Promise<DocumentApiResult<UpdateDocumentLayoutReadingOrderResponse>> {
  return requestDocumentApi<UpdateDocumentLayoutReadingOrderResponse>(
    `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}/pages/${pageId}/reading-order`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function updateProjectDocumentLayoutPageElements(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  payload: UpdateDocumentLayoutElementsRequest
): Promise<DocumentApiResult<UpdateDocumentLayoutElementsResponse>> {
  return requestDocumentApi<UpdateDocumentLayoutElementsResponse>(
    `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}/pages/${pageId}/elements`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function getProjectDocumentLayoutPageRecallStatus(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string
): Promise<DocumentApiResult<DocumentLayoutPageRecallStatusResponse>> {
  return requestDocumentApi<DocumentLayoutPageRecallStatusResponse>(
    `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}/pages/${pageId}/recall-status`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.layoutPageRecallStatus(
        projectId,
        documentId,
        runId,
        pageId
      )
    }
  );
}

export async function listProjectDocumentLayoutPageRescueCandidates(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string
): Promise<DocumentApiResult<DocumentLayoutRescueCandidateListResponse>> {
  return requestDocumentApi<DocumentLayoutRescueCandidateListResponse>(
    `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}/pages/${pageId}/rescue-candidates`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.layoutPageRescueCandidates(
        projectId,
        documentId,
        runId,
        pageId
      )
    }
  );
}

export async function cancelProjectDocumentLayoutRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentLayoutRun>> {
  return requestDocumentApi<DocumentLayoutRun>(
    `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}/cancel`,
    {
      method: "POST"
    }
  );
}

export async function activateProjectDocumentLayoutRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<ActivateDocumentLayoutRunResponse>> {
  return requestDocumentApi<ActivateDocumentLayoutRunResponse>(
    `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}/activate`,
    {
      method: "POST"
    }
  );
}

export async function getProjectDocumentTranscriptionOverview(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentTranscriptionOverviewResponse>> {
  return requestDocumentApi<DocumentTranscriptionOverviewResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription/overview`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.transcriptionOverview(projectId, documentId)
    }
  );
}

export async function getProjectDocumentTranscriptionTriage(
  projectId: string,
  documentId: string,
  filters: ProjectDocumentTranscriptionTriageFilters = {}
): Promise<DocumentApiResult<DocumentTranscriptionTriageResponse>> {
  return requestDocumentApi<DocumentTranscriptionTriageResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription/triage${toTranscriptionQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.transcriptionTriage(
        projectId,
        documentId,
        filters
      )
    }
  );
}

export async function getProjectDocumentTranscriptionMetrics(
  projectId: string,
  documentId: string,
  filters: ProjectDocumentTranscriptionMetricsFilters = {}
): Promise<DocumentApiResult<DocumentTranscriptionMetricsResponse>> {
  return requestDocumentApi<DocumentTranscriptionMetricsResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription/metrics${toTranscriptionQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.transcriptionMetrics(
        projectId,
        documentId,
        filters
      )
    }
  );
}

export async function updateProjectDocumentTranscriptionTriageAssignment(
  projectId: string,
  documentId: string,
  pageId: string,
  payload: UpdateDocumentTranscriptionTriageAssignmentRequest
): Promise<DocumentApiResult<UpdateDocumentTranscriptionTriageAssignmentResponse>> {
  return requestDocumentApi<UpdateDocumentTranscriptionTriageAssignmentResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription/triage/pages/${pageId}/assignment`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function createProjectDocumentTranscriptionRun(
  projectId: string,
  documentId: string,
  payload: CreateDocumentTranscriptionRunRequest = {}
): Promise<DocumentApiResult<DocumentTranscriptionRun>> {
  return requestDocumentApi<DocumentTranscriptionRun>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function createProjectDocumentFallbackTranscriptionRun(
  projectId: string,
  documentId: string,
  payload: CreateDocumentTranscriptionFallbackRunRequest = {}
): Promise<DocumentApiResult<DocumentTranscriptionRun>> {
  return requestDocumentApi<DocumentTranscriptionRun>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/fallback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function getProjectDocumentActiveTranscriptionRun(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentTranscriptionActiveRunResponse>> {
  return requestDocumentApi<DocumentTranscriptionActiveRunResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/active`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.transcriptionActiveRun(projectId, documentId)
    }
  );
}

export async function listProjectDocumentTranscriptionRuns(
  projectId: string,
  documentId: string,
  filters: ProjectDocumentTranscriptionRunListFilters = {}
): Promise<DocumentApiResult<DocumentTranscriptionRunListResponse>> {
  return requestDocumentApi<DocumentTranscriptionRunListResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs${toTranscriptionQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.transcriptionRuns(projectId, documentId, filters)
    }
  );
}

export async function compareProjectDocumentTranscriptionRuns(
  projectId: string,
  documentId: string,
  baseRunId: string,
  candidateRunId: string,
  filters: ProjectDocumentTranscriptionCompareFilters = {}
): Promise<DocumentApiResult<DocumentTranscriptionCompareResponse>> {
  const query = new URLSearchParams({
    baseRunId,
    candidateRunId
  });
  if (typeof filters.page === "number" && Number.isFinite(filters.page)) {
    query.set("page", String(Math.max(1, Math.round(filters.page))));
  }
  if (typeof filters.lineId === "string" && filters.lineId.trim().length > 0) {
    query.set("lineId", filters.lineId.trim());
  }
  if (typeof filters.tokenId === "string" && filters.tokenId.trim().length > 0) {
    query.set("tokenId", filters.tokenId.trim());
  }
  return requestDocumentApi<DocumentTranscriptionCompareResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/compare?${query.toString()}`,
    {
      cacheClass: "operations-live"
    }
  );
}

export async function getProjectDocumentTranscriptionRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentTranscriptionRun>> {
  return requestDocumentApi<DocumentTranscriptionRun>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.transcriptionRunDetail(
        projectId,
        documentId,
        runId
      )
    }
  );
}

export async function getProjectDocumentTranscriptionRunStatus(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentTranscriptionRunStatusResponse>> {
  return requestDocumentApi<DocumentTranscriptionRunStatusResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/status`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.transcriptionRunStatus(
        projectId,
        documentId,
        runId
      )
    }
  );
}

export async function getProjectDocumentTranscriptionRunRescueStatus(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentTranscriptionRunRescueStatusResponse>> {
  return requestDocumentApi<DocumentTranscriptionRunRescueStatusResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/rescue-status`,
    {
      cacheClass: "operations-live"
    }
  );
}

export async function getProjectDocumentTranscriptionRunPageRescueSources(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string
): Promise<DocumentApiResult<DocumentTranscriptionPageRescueSourcesResponse>> {
  return requestDocumentApi<DocumentTranscriptionPageRescueSourcesResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/rescue-sources`,
    {
      cacheClass: "operations-live"
    }
  );
}

export async function listProjectDocumentTranscriptionRunPages(
  projectId: string,
  documentId: string,
  runId: string,
  filters: ProjectDocumentTranscriptionRunPagesFilters = {}
): Promise<DocumentApiResult<DocumentTranscriptionRunPageListResponse>> {
  return requestDocumentApi<DocumentTranscriptionRunPageListResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages${toTranscriptionQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.transcriptionRunPages(
        projectId,
        documentId,
        runId,
        filters
      )
    }
  );
}

export async function listProjectDocumentTranscriptionRunPageLines(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  filters: ProjectDocumentTranscriptionRunPageLinesFilters = {}
): Promise<DocumentApiResult<DocumentTranscriptionLineResultListResponse>> {
  return requestDocumentApi<DocumentTranscriptionLineResultListResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/lines${toTranscriptionLineQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.transcriptionRunPageLines(
        projectId,
        documentId,
        runId,
        pageId
      )
    }
  );
}

export async function listProjectDocumentTranscriptionRunPageTokens(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string
): Promise<DocumentApiResult<DocumentTranscriptionTokenResultListResponse>> {
  return requestDocumentApi<DocumentTranscriptionTokenResultListResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/tokens`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.transcriptionRunPageTokens(
        projectId,
        documentId,
        runId,
        pageId
      )
    }
  );
}

export async function correctProjectDocumentTranscriptionLine(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  lineId: string,
  payload: CorrectDocumentTranscriptionLineRequest
): Promise<DocumentApiResult<CorrectDocumentTranscriptionLineResponse>> {
  return requestDocumentApi<CorrectDocumentTranscriptionLineResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/lines/${lineId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function listProjectDocumentTranscriptionLineVersions(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  lineId: string
): Promise<DocumentApiResult<DocumentTranscriptionLineVersionHistoryResponse>> {
  return requestDocumentApi<DocumentTranscriptionLineVersionHistoryResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/lines/${lineId}/versions`,
    {
      cacheClass: "operations-live"
    }
  );
}

export async function getProjectDocumentTranscriptionLineVersion(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  lineId: string,
  versionId: string
): Promise<DocumentApiResult<TranscriptVersionLineage>> {
  return requestDocumentApi<TranscriptVersionLineage>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/lines/${lineId}/versions/${versionId}`,
    {
      cacheClass: "operations-live"
    }
  );
}

export async function listProjectDocumentTranscriptionRunPageVariantLayers(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  filters: ProjectDocumentTranscriptionVariantLayersFilters = {
    variantKind: "NORMALISED"
  }
): Promise<DocumentApiResult<TranscriptVariantLayerListResponse>> {
  return requestDocumentApi<TranscriptVariantLayerListResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/variant-layers${toTranscriptionVariantLayersQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.transcriptionRunPageVariantLayers(
        projectId,
        documentId,
        runId,
        pageId,
        filters
      )
    }
  );
}

export async function recordProjectDocumentTranscriptionVariantSuggestionDecision(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  suggestionId: string,
  payload: RecordTranscriptVariantSuggestionDecisionRequest
): Promise<DocumentApiResult<RecordTranscriptVariantSuggestionDecisionResponse>> {
  return requestDocumentApi<RecordTranscriptVariantSuggestionDecisionResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/variant-layers/NORMALISED/suggestions/${suggestionId}/decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      queryKey: queryKeys.documents.transcriptionRunPageVariantSuggestionDecision(
        projectId,
        documentId,
        runId,
        pageId,
        suggestionId
      )
    }
  );
}

export async function recordProjectDocumentTranscriptionCompareDecisions(
  projectId: string,
  documentId: string,
  payload: RecordDocumentTranscriptionCompareDecisionsRequest
): Promise<DocumentApiResult<RecordDocumentTranscriptionCompareDecisionsResponse>> {
  return requestDocumentApi<RecordDocumentTranscriptionCompareDecisionsResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/compare/decisions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function finalizeProjectDocumentTranscriptionCompare(
  projectId: string,
  documentId: string,
  payload: FinalizeDocumentTranscriptionCompareRequest
): Promise<DocumentApiResult<FinalizeDocumentTranscriptionCompareResponse>> {
  return requestDocumentApi<FinalizeDocumentTranscriptionCompareResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/compare/finalize`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function cancelProjectDocumentTranscriptionRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentTranscriptionRun>> {
  return requestDocumentApi<DocumentTranscriptionRun>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/cancel`,
    {
      method: "POST"
    }
  );
}

export async function activateProjectDocumentTranscriptionRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<ActivateDocumentTranscriptionRunResponse>> {
  return requestDocumentApi<ActivateDocumentTranscriptionRunResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/activate`,
    {
      method: "POST"
    }
  );
}

export async function updateProjectDocumentTranscriptionRunPageRescueResolution(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  payload: UpdateDocumentTranscriptionRescueResolutionRequest
): Promise<DocumentApiResult<DocumentTranscriptionPageRescueSourcesResponse>> {
  return requestDocumentApi<DocumentTranscriptionPageRescueSourcesResponse>(
    `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/rescue-resolution`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function getProjectDocumentRedactionOverview(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentRedactionOverviewResponse>> {
  return requestDocumentApi<DocumentRedactionOverviewResponse>(
    `/projects/${projectId}/documents/${documentId}/privacy/overview`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionOverview(projectId, documentId)
    }
  );
}

export async function listProjectDocumentRedactionRuns(
  projectId: string,
  documentId: string,
  filters: ProjectDocumentRedactionRunListFilters = {}
): Promise<DocumentApiResult<DocumentRedactionRunListResponse>> {
  return requestDocumentApi<DocumentRedactionRunListResponse>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs${toRedactionRunQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRuns(projectId, documentId, filters)
    }
  );
}

export async function createProjectDocumentRedactionRun(
  projectId: string,
  documentId: string,
  payload: CreateDocumentRedactionRunRequest = {}
): Promise<DocumentApiResult<DocumentRedactionRun>> {
  return requestDocumentApi<DocumentRedactionRun>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function rerunProjectDocumentRedactionRunWithPolicy(
  projectId: string,
  documentId: string,
  runId: string,
  policyId: string
): Promise<DocumentApiResult<DocumentRedactionRun>> {
  const normalizedPolicyId = policyId.trim();
  return requestDocumentApi<DocumentRedactionRun>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/rerun?policyId=${encodeURIComponent(normalizedPolicyId)}`,
    {
      method: "POST"
    }
  );
}

export async function getProjectDocumentActiveRedactionRun(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentRedactionActiveRunResponse>> {
  return requestDocumentApi<DocumentRedactionActiveRunResponse>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/active`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionActiveRun(projectId, documentId)
    }
  );
}

export async function compareProjectDocumentRedactionRuns(
  projectId: string,
  documentId: string,
  baseRunId: string,
  candidateRunId: string,
  filters: ProjectDocumentRedactionCompareFilters = {}
): Promise<DocumentApiResult<DocumentRedactionCompareResponse>> {
  return requestDocumentApi<DocumentRedactionCompareResponse>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/compare${toRedactionCompareQueryString(baseRunId, candidateRunId, filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionCompare(
        projectId,
        documentId,
        baseRunId,
        candidateRunId,
        filters
      )
    }
  );
}

export async function getProjectDocumentRedactionRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentRedactionRun>> {
  return requestDocumentApi<DocumentRedactionRun>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRunDetail(projectId, documentId, runId)
    }
  );
}

export async function getProjectDocumentRedactionRunStatus(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentRedactionRunStatusResponse>> {
  return requestDocumentApi<DocumentRedactionRunStatusResponse>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/status`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRunStatus(projectId, documentId, runId)
    }
  );
}

export async function cancelProjectDocumentRedactionRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentRedactionRun>> {
  return requestDocumentApi<DocumentRedactionRun>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/cancel`,
    {
      method: "POST"
    }
  );
}

export async function activateProjectDocumentRedactionRun(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<ActivateDocumentRedactionRunResponse>> {
  return requestDocumentApi<ActivateDocumentRedactionRunResponse>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/activate`,
    {
      method: "POST"
    }
  );
}

export async function getProjectDocumentRedactionRunReview(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentRedactionRunReview>> {
  return requestDocumentApi<DocumentRedactionRunReview>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/review`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRunReview(projectId, documentId, runId)
    }
  );
}

export async function startProjectDocumentRedactionRunReview(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentRedactionRunReview>> {
  return requestDocumentApi<DocumentRedactionRunReview>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/start-review`,
    {
      method: "POST"
    }
  );
}

export async function completeProjectDocumentRedactionRunReview(
  projectId: string,
  documentId: string,
  runId: string,
  payload: CompleteDocumentRedactionRunReviewRequest
): Promise<DocumentApiResult<DocumentRedactionRunReview>> {
  return requestDocumentApi<DocumentRedactionRunReview>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/complete-review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function listProjectDocumentRedactionRunEvents(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentRedactionRunEventsResponse>> {
  return requestDocumentApi<DocumentRedactionRunEventsResponse>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/events`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRunEvents(projectId, documentId, runId)
    }
  );
}

export async function listProjectDocumentRedactionRunPages(
  projectId: string,
  documentId: string,
  runId: string,
  filters: ProjectDocumentRedactionRunPagesFilters = {}
): Promise<DocumentApiResult<DocumentRedactionRunPageListResponse>> {
  return requestDocumentApi<DocumentRedactionRunPageListResponse>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/pages${toRedactionRunPagesQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRunPages(
        projectId,
        documentId,
        runId,
        filters
      )
    }
  );
}

export async function listProjectDocumentRedactionRunPageFindings(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  filters: ProjectDocumentRedactionRunPageFindingsFilters = {}
): Promise<DocumentApiResult<DocumentRedactionFindingListResponse>> {
  return requestDocumentApi<DocumentRedactionFindingListResponse>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/pages/${pageId}/findings${toRedactionFindingsQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRunPageFindings(
        projectId,
        documentId,
        runId,
        pageId,
        filters
      )
    }
  );
}

export async function getProjectDocumentRedactionRunPageFinding(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  findingId: string
): Promise<DocumentApiResult<DocumentRedactionFinding>> {
  return requestDocumentApi<DocumentRedactionFinding>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/pages/${pageId}/findings/${findingId}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRunPageFinding(
        projectId,
        documentId,
        runId,
        pageId,
        findingId
      )
    }
  );
}

export async function patchProjectDocumentRedactionFinding(
  projectId: string,
  documentId: string,
  runId: string,
  findingId: string,
  payload: PatchDocumentRedactionFindingRequest
): Promise<DocumentApiResult<DocumentRedactionFinding>> {
  return requestDocumentApi<DocumentRedactionFinding>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/findings/${findingId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function getProjectDocumentRedactionRunPageReview(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string
): Promise<DocumentApiResult<DocumentRedactionPageReview>> {
  return requestDocumentApi<DocumentRedactionPageReview>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/pages/${pageId}/review`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRunPageReview(
        projectId,
        documentId,
        runId,
        pageId
      )
    }
  );
}

export async function patchProjectDocumentRedactionPageReview(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  payload: PatchDocumentRedactionPageReviewRequest
): Promise<DocumentApiResult<DocumentRedactionPageReview>> {
  return requestDocumentApi<DocumentRedactionPageReview>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/pages/${pageId}/review`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function listProjectDocumentRedactionRunPageEvents(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string
): Promise<DocumentApiResult<DocumentRedactionRunEventsResponse>> {
  return requestDocumentApi<DocumentRedactionRunEventsResponse>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/pages/${pageId}/events`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRunPageEvents(
        projectId,
        documentId,
        runId,
        pageId
      )
    }
  );
}

export async function getProjectDocumentRedactionRunPagePreviewStatus(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string
): Promise<DocumentApiResult<DocumentRedactionPreviewStatusResponse>> {
  return requestDocumentApi<DocumentRedactionPreviewStatusResponse>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/pages/${pageId}/preview-status`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRunPagePreviewStatus(
        projectId,
        documentId,
        runId,
        pageId
      )
    }
  );
}

export async function getProjectDocumentRedactionRunOutput(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentRedactionRunOutput>> {
  return requestDocumentApi<DocumentRedactionRunOutput>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/output`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRunOutput(projectId, documentId, runId)
    }
  );
}

export async function getProjectDocumentRedactionRunOutputStatus(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentRedactionRunOutput>> {
  return requestDocumentApi<DocumentRedactionRunOutput>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/output/status`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.redactionRunOutputStatus(
        projectId,
        documentId,
        runId
      )
    }
  );
}

export async function getProjectDocumentGovernanceOverview(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentGovernanceOverviewResponse>> {
  return requestDocumentApi<DocumentGovernanceOverviewResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/overview`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceOverview(projectId, documentId)
    }
  );
}

export async function listProjectDocumentGovernanceRuns(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentGovernanceRunsResponse>> {
  return requestDocumentApi<DocumentGovernanceRunsResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRuns(projectId, documentId)
    }
  );
}

export async function getProjectDocumentGovernanceRunOverview(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentGovernanceRunOverviewResponse>> {
  return requestDocumentApi<DocumentGovernanceRunOverviewResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/overview`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunOverview(projectId, documentId, runId)
    }
  );
}

export async function listProjectDocumentGovernanceRunEvents(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentGovernanceRunEventsResponse>> {
  return requestDocumentApi<DocumentGovernanceRunEventsResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/events`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunEvents(projectId, documentId, runId)
    }
  );
}

export async function getProjectDocumentGovernanceRunManifest(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentGovernanceManifestResponse>> {
  return requestDocumentApi<DocumentGovernanceManifestResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/manifest`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunManifest(projectId, documentId, runId)
    }
  );
}

export async function getProjectDocumentGovernanceRunManifestStatus(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentGovernanceManifestStatusResponse>> {
  return requestDocumentApi<DocumentGovernanceManifestStatusResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/manifest/status`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunManifestStatus(projectId, documentId, runId)
    }
  );
}

export async function listProjectDocumentGovernanceRunManifestEntries(
  projectId: string,
  documentId: string,
  runId: string,
  filters: ProjectDocumentGovernanceManifestEntriesFilters = {}
): Promise<DocumentApiResult<DocumentGovernanceManifestEntriesResponse>> {
  const query = toGovernanceManifestEntriesQueryString(filters);
  return requestDocumentApi<DocumentGovernanceManifestEntriesResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/manifest/entries${query}`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunManifestEntries(
        projectId,
        documentId,
        runId,
        {
          category: filters.category,
          cursor: filters.cursor,
          from: filters.from,
          limit: filters.limit,
          page: filters.page,
          reviewState: filters.reviewState,
          to: filters.to
        }
      )
    }
  );
}

export async function getProjectDocumentGovernanceRunManifestHash(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentGovernanceManifestHashResponse>> {
  return requestDocumentApi<DocumentGovernanceManifestHashResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/manifest/hash`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunManifestHash(projectId, documentId, runId)
    }
  );
}

export async function getProjectDocumentGovernanceRunLedger(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentGovernanceLedgerResponse>> {
  return requestDocumentApi<DocumentGovernanceLedgerResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/ledger`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunLedger(projectId, documentId, runId)
    }
  );
}

export async function getProjectDocumentGovernanceRunLedgerStatus(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentGovernanceLedgerStatusResponse>> {
  return requestDocumentApi<DocumentGovernanceLedgerStatusResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/ledger/status`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunLedgerStatus(projectId, documentId, runId)
    }
  );
}

export async function listProjectDocumentGovernanceRunLedgerEntries(
  projectId: string,
  documentId: string,
  runId: string,
  filters: ProjectDocumentGovernanceLedgerEntriesFilters = {}
): Promise<DocumentApiResult<DocumentGovernanceLedgerEntriesResponse>> {
  const query = toGovernanceLedgerEntriesQueryString(filters);
  return requestDocumentApi<DocumentGovernanceLedgerEntriesResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/ledger/entries${query}`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunLedgerEntries(
        projectId,
        documentId,
        runId,
        {
          cursor: filters.cursor,
          limit: filters.limit,
          view: filters.view
        }
      )
    }
  );
}

export async function getProjectDocumentGovernanceRunLedgerSummary(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentGovernanceLedgerSummaryResponse>> {
  return requestDocumentApi<DocumentGovernanceLedgerSummaryResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/ledger/summary`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunLedgerSummary(projectId, documentId, runId)
    }
  );
}

export async function postProjectDocumentGovernanceRunLedgerVerify(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentGovernanceLedgerVerifyDetailResponse>> {
  return requestDocumentApi<DocumentGovernanceLedgerVerifyDetailResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/ledger/verify`,
    {
      method: "POST",
      cacheClass: "governance-event"
    }
  );
}

export async function getProjectDocumentGovernanceRunLedgerVerifyStatus(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentGovernanceLedgerVerifyStatusResponse>> {
  return requestDocumentApi<DocumentGovernanceLedgerVerifyStatusResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/ledger/verify/status`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunLedgerVerifyStatus(
        projectId,
        documentId,
        runId
      )
    }
  );
}

export async function listProjectDocumentGovernanceRunLedgerVerifyRuns(
  projectId: string,
  documentId: string,
  runId: string
): Promise<DocumentApiResult<DocumentGovernanceLedgerVerifyRunsResponse>> {
  return requestDocumentApi<DocumentGovernanceLedgerVerifyRunsResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/ledger/verify/runs`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunLedgerVerifyRuns(
        projectId,
        documentId,
        runId
      )
    }
  );
}

export async function getProjectDocumentGovernanceRunLedgerVerifyRun(
  projectId: string,
  documentId: string,
  runId: string,
  verificationRunId: string
): Promise<DocumentApiResult<DocumentGovernanceLedgerVerifyDetailResponse>> {
  return requestDocumentApi<DocumentGovernanceLedgerVerifyDetailResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/ledger/verify/${verificationRunId}`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunLedgerVerifyRun(
        projectId,
        documentId,
        runId,
        verificationRunId
      )
    }
  );
}

export async function getProjectDocumentGovernanceRunLedgerVerifyRunStatus(
  projectId: string,
  documentId: string,
  runId: string,
  verificationRunId: string
): Promise<DocumentApiResult<DocumentGovernanceLedgerVerifyDetailResponse>> {
  return requestDocumentApi<DocumentGovernanceLedgerVerifyDetailResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/ledger/verify/${verificationRunId}/status`,
    {
      cacheClass: "governance-event",
      queryKey: queryKeys.documents.governanceRunLedgerVerifyRunStatus(
        projectId,
        documentId,
        runId,
        verificationRunId
      )
    }
  );
}

export async function postProjectDocumentGovernanceRunLedgerVerifyRunCancel(
  projectId: string,
  documentId: string,
  runId: string,
  verificationRunId: string
): Promise<DocumentApiResult<DocumentGovernanceLedgerVerifyDetailResponse>> {
  return requestDocumentApi<DocumentGovernanceLedgerVerifyDetailResponse>(
    `/projects/${projectId}/documents/${documentId}/governance/runs/${runId}/ledger/verify/${verificationRunId}/cancel`,
    {
      method: "POST",
      cacheClass: "governance-event"
    }
  );
}

export async function patchProjectDocumentRedactionAreaMask(
  projectId: string,
  documentId: string,
  runId: string,
  maskId: string,
  payload: PatchDocumentRedactionAreaMaskRequest
): Promise<DocumentApiResult<PatchDocumentRedactionAreaMaskResponse>> {
  return requestDocumentApi<PatchDocumentRedactionAreaMaskResponse>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/area-masks/${maskId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function createProjectDocumentRedactionAreaMask(
  projectId: string,
  documentId: string,
  runId: string,
  pageId: string,
  payload: CreateDocumentRedactionAreaMaskRequest
): Promise<DocumentApiResult<PatchDocumentRedactionAreaMaskResponse>> {
  return requestDocumentApi<PatchDocumentRedactionAreaMaskResponse>(
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/pages/${pageId}/area-masks`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function listProjectDocumentPages(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<ProjectDocumentPageListResponse>> {
  return requestDocumentApi<ProjectDocumentPageListResponse>(
    `/projects/${projectId}/documents/${documentId}/pages`,
    {
      queryKey: queryKeys.documents.pages(projectId, documentId)
    }
  );
}

export async function getProjectDocumentPage(
  projectId: string,
  documentId: string,
  pageId: string
): Promise<DocumentApiResult<ProjectDocumentPageDetail>> {
  return requestDocumentApi<ProjectDocumentPageDetail>(
    `/projects/${projectId}/documents/${documentId}/pages/${pageId}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.pageDetail(projectId, documentId, pageId)
    }
  );
}

export async function getProjectDocumentPageVariants(
  projectId: string,
  documentId: string,
  pageId: string,
  filters: ProjectDocumentPageVariantsFilters = {}
): Promise<DocumentApiResult<DocumentPageVariantsResponse>> {
  return requestDocumentApi<DocumentPageVariantsResponse>(
    `/projects/${projectId}/documents/${documentId}/pages/${pageId}/variants${toPreprocessQueryString(filters)}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.pageVariants(
        projectId,
        documentId,
        pageId,
        filters
      )
    }
  );
}

export async function updateProjectDocumentPage(
  projectId: string,
  documentId: string,
  pageId: string,
  payload: Pick<ProjectDocumentPage, "viewerRotation">
): Promise<DocumentApiResult<ProjectDocumentPageDetail>> {
  return requestDocumentApi<ProjectDocumentPageDetail>(
    `/projects/${projectId}/documents/${documentId}/pages/${pageId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ viewerRotation: payload.viewerRotation })
    }
  );
}

export { projectDocumentPageImagePath };

export async function uploadProjectDocument(
  projectId: string,
  formData: FormData
): Promise<DocumentApiResult<ProjectDocumentImportStatus>> {
  return requestDocumentApi<ProjectDocumentImportStatus>(
    `/projects/${projectId}/documents/import`,
    {
      method: "POST",
      body: formData
    }
  );
}

export async function createProjectDocumentUploadSession(
  projectId: string,
  payload: CreateDocumentUploadSessionRequest
): Promise<DocumentApiResult<ProjectDocumentUploadSessionStatus>> {
  return requestDocumentApi<ProjectDocumentUploadSessionStatus>(
    `/projects/${projectId}/documents/import-sessions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function getProjectDocumentUploadSession(
  projectId: string,
  sessionId: string
): Promise<DocumentApiResult<ProjectDocumentUploadSessionStatus>> {
  return requestDocumentApi<ProjectDocumentUploadSessionStatus>(
    `/projects/${projectId}/documents/import-sessions/${sessionId}`,
    {
      cacheClass: "operations-live"
    }
  );
}

export async function uploadProjectDocumentChunk(
  projectId: string,
  sessionId: string,
  chunkIndex: number,
  formData: FormData
): Promise<DocumentApiResult<ProjectDocumentUploadSessionStatus>> {
  return requestDocumentApi<ProjectDocumentUploadSessionStatus>(
    `/projects/${projectId}/documents/import-sessions/${sessionId}/chunks?chunkIndex=${chunkIndex}`,
    {
      method: "POST",
      body: formData
    }
  );
}

export async function completeProjectDocumentUploadSession(
  projectId: string,
  sessionId: string
): Promise<DocumentApiResult<ProjectDocumentUploadSessionStatus>> {
  return requestDocumentApi<ProjectDocumentUploadSessionStatus>(
    `/projects/${projectId}/documents/import-sessions/${sessionId}/complete`,
    {
      method: "POST"
    }
  );
}

export async function cancelProjectDocumentUploadSession(
  projectId: string,
  sessionId: string
): Promise<DocumentApiResult<ProjectDocumentUploadSessionStatus>> {
  return requestDocumentApi<ProjectDocumentUploadSessionStatus>(
    `/projects/${projectId}/documents/import-sessions/${sessionId}/cancel`,
    {
      method: "POST"
    }
  );
}

export async function retryProjectDocumentExtraction(
  projectId: string,
  documentId: string
): Promise<DocumentApiResult<DocumentProcessingRunDetailResponse>> {
  return requestDocumentApi<DocumentProcessingRunDetailResponse>(
    `/projects/${projectId}/documents/${documentId}/retry-extraction`,
    {
      method: "POST"
    }
  );
}

export async function getProjectDocumentImportStatus(
  projectId: string,
  importId: string
): Promise<DocumentApiResult<ProjectDocumentImportStatus>> {
  return requestDocumentApi<ProjectDocumentImportStatus>(
    `/projects/${projectId}/document-imports/${importId}`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.documents.importStatus(projectId, importId)
    }
  );
}

export async function cancelProjectDocumentImport(
  projectId: string,
  importId: string
): Promise<DocumentApiResult<ProjectDocumentImportStatus>> {
  return requestDocumentApi<ProjectDocumentImportStatus>(
    `/projects/${projectId}/document-imports/${importId}/cancel`,
    {
      method: "POST"
    }
  );
}
