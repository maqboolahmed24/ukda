import type {
  ActivateDocumentLayoutRunResponse,
  ActivateDocumentPreprocessRunResponse,
  ActivateDocumentTranscriptionRunResponse,
  CreateDocumentLayoutRunRequest,
  CreateDocumentPreprocessRunRequest,
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
  DocumentTranscriptionActiveRunResponse,
  DocumentTranscriptionCompareResponse,
  CorrectDocumentTranscriptionLineRequest,
  CorrectDocumentTranscriptionLineResponse,
  DocumentTranscriptionLineResultListResponse,
  DocumentTranscriptionMetricsResponse,
  DocumentTranscriptionOverviewResponse,
  DocumentTranscriptionRun,
  DocumentTranscriptionRunListResponse,
  DocumentTranscriptionRunPageListResponse,
  DocumentTranscriptionRunStatusResponse,
  DocumentTranscriptionTokenResultListResponse,
  DocumentTranscriptionTriageResponse,
  UpdateDocumentTranscriptionTriageAssignmentRequest,
  UpdateDocumentTranscriptionTriageAssignmentResponse,
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

export interface ProjectDocumentPageVariantsFilters {
  runId?: string;
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
  candidateRunId: string
): Promise<DocumentApiResult<DocumentTranscriptionCompareResponse>> {
  const query = new URLSearchParams({
    baseRunId,
    candidateRunId
  });
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
