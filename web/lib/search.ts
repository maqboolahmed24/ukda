import type {
  ProjectSearchHit,
  ProjectSearchResponse,
  ProjectSearchResultOpenResponse,
  TranscriptionTokenSourceKind
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import { queryKeys } from "./data/query-keys";
import { projectDocumentTranscriptionWorkspacePath } from "./routes";

export type SearchApiResult<T> = ApiResult<T>;

export interface ProjectSearchQuery {
  cursor?: number;
  documentId?: string;
  limit?: number;
  pageNumber?: number;
  q: string;
  runId?: string;
}

function normalizeText(value: string | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : undefined;
}

function toQueryString(query: ProjectSearchQuery): string {
  const params = new URLSearchParams();
  params.set("q", query.q.trim());
  if (typeof query.cursor === "number" && Number.isFinite(query.cursor)) {
    params.set("cursor", String(Math.max(0, Math.round(query.cursor))));
  }
  if (typeof query.limit === "number" && Number.isFinite(query.limit)) {
    params.set("limit", String(Math.max(1, Math.round(query.limit))));
  }
  if (typeof query.pageNumber === "number" && Number.isFinite(query.pageNumber)) {
    params.set("pageNumber", String(Math.max(1, Math.round(query.pageNumber))));
  }
  const documentId = normalizeText(query.documentId);
  if (documentId) {
    params.set("documentId", documentId);
  }
  const runId = normalizeText(query.runId);
  if (runId) {
    params.set("runId", runId);
  }
  return params.toString();
}

export async function getProjectSearch(
  projectId: string,
  query: ProjectSearchQuery
): Promise<SearchApiResult<ProjectSearchResponse>> {
  const queryString = toQueryString(query);
  return requestServerApi<ProjectSearchResponse>({
    path: `/projects/${projectId}/search?${queryString}`,
    queryKey: queryKeys.projects.search(projectId, {
      cursor: query.cursor,
      documentId: query.documentId,
      limit: query.limit,
      pageNumber: query.pageNumber,
      q: query.q,
      runId: query.runId
    })
  });
}

export async function openProjectSearchResult(
  projectId: string,
  searchDocumentId: string
): Promise<SearchApiResult<ProjectSearchResultOpenResponse>> {
  return requestServerApi<ProjectSearchResultOpenResponse>({
    body: null,
    method: "POST",
    path: `/projects/${projectId}/search/${searchDocumentId}/open`
  });
}

function toSourceKind(
  value: string | null | undefined
): TranscriptionTokenSourceKind | undefined {
  if (value === "LINE" || value === "RESCUE_CANDIDATE" || value === "PAGE_WINDOW") {
    return value;
  }
  return undefined;
}

export function buildWorkspacePathFromSearchHit(
  projectId: string,
  hit: Pick<
    ProjectSearchHit,
    "documentId" | "lineId" | "pageNumber" | "runId" | "sourceKind" | "sourceRefId" | "tokenId"
  >
): string {
  const sourceRefId =
    typeof hit.sourceRefId === "string" && hit.sourceRefId.trim().length > 0
      ? hit.sourceRefId.trim()
      : undefined;
  return projectDocumentTranscriptionWorkspacePath(projectId, hit.documentId, {
    lineId: hit.lineId ?? undefined,
    page: hit.pageNumber,
    runId: hit.runId,
    sourceKind: toSourceKind(hit.sourceKind),
    sourceRefId,
    tokenId: hit.tokenId ?? undefined
  });
}
