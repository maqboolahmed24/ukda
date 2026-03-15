import type {
  EntityOccurrence,
  ProjectEntityDetailResponse,
  ProjectEntityListResponse,
  ProjectEntityOccurrencesResponse,
  TranscriptionTokenSourceKind
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import { queryKeys } from "./data/query-keys";
import { projectDocumentTranscriptionWorkspacePath } from "./routes";

export type EntitiesApiResult<T> = ApiResult<T>;

export interface ProjectEntitiesQuery {
  cursor?: number;
  entityType?: string;
  limit?: number;
  q?: string;
}

function normalizeText(value: string | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : undefined;
}

function toQueryString(query: ProjectEntitiesQuery): string {
  const params = new URLSearchParams();
  const q = normalizeText(query.q);
  if (q) {
    params.set("q", q);
  }
  const entityType = normalizeText(query.entityType);
  if (entityType) {
    params.set("entityType", entityType);
  }
  if (typeof query.cursor === "number" && Number.isFinite(query.cursor)) {
    params.set("cursor", String(Math.max(0, Math.round(query.cursor))));
  }
  if (typeof query.limit === "number" && Number.isFinite(query.limit)) {
    params.set("limit", String(Math.max(1, Math.round(query.limit))));
  }
  return params.toString();
}

function toSourceKind(
  value: string | null | undefined
): TranscriptionTokenSourceKind | undefined {
  if (value === "LINE" || value === "RESCUE_CANDIDATE" || value === "PAGE_WINDOW") {
    return value;
  }
  return undefined;
}

export async function getProjectEntities(
  projectId: string,
  query: ProjectEntitiesQuery
): Promise<EntitiesApiResult<ProjectEntityListResponse>> {
  const queryString = toQueryString(query);
  const suffix = queryString ? `?${queryString}` : "";
  return requestServerApi<ProjectEntityListResponse>({
    path: `/projects/${projectId}/entities${suffix}`,
    queryKey: queryKeys.projects.entities(projectId, {
      cursor: query.cursor,
      entityType: query.entityType,
      limit: query.limit,
      q: query.q
    })
  });
}

export async function getProjectEntityDetail(
  projectId: string,
  entityId: string
): Promise<EntitiesApiResult<ProjectEntityDetailResponse>> {
  return requestServerApi<ProjectEntityDetailResponse>({
    path: `/projects/${projectId}/entities/${entityId}`,
    queryKey: queryKeys.projects.entityDetail(projectId, entityId)
  });
}

export async function getProjectEntityOccurrences(
  projectId: string,
  entityId: string,
  query: Pick<ProjectEntitiesQuery, "cursor" | "limit">
): Promise<EntitiesApiResult<ProjectEntityOccurrencesResponse>> {
  const params = new URLSearchParams();
  if (typeof query.cursor === "number" && Number.isFinite(query.cursor)) {
    params.set("cursor", String(Math.max(0, Math.round(query.cursor))));
  }
  if (typeof query.limit === "number" && Number.isFinite(query.limit)) {
    params.set("limit", String(Math.max(1, Math.round(query.limit))));
  }
  const queryString = params.toString();
  const suffix = queryString ? `?${queryString}` : "";
  return requestServerApi<ProjectEntityOccurrencesResponse>({
    path: `/projects/${projectId}/entities/${entityId}/occurrences${suffix}`,
    queryKey: queryKeys.projects.entityOccurrences(projectId, entityId, {
      cursor: query.cursor,
      limit: query.limit
    })
  });
}

export function buildWorkspacePathFromEntityOccurrence(
  projectId: string,
  occurrence: Pick<
    EntityOccurrence,
    | "documentId"
    | "lineId"
    | "pageNumber"
    | "runId"
    | "sourceKind"
    | "sourceRefId"
    | "tokenId"
  >
): string {
  const sourceRefId =
    typeof occurrence.sourceRefId === "string" && occurrence.sourceRefId.trim().length > 0
      ? occurrence.sourceRefId.trim()
      : undefined;
  return projectDocumentTranscriptionWorkspacePath(
    projectId,
    occurrence.documentId,
    {
      lineId: occurrence.lineId ?? undefined,
      page: occurrence.pageNumber,
      runId: occurrence.runId,
      sourceKind: toSourceKind(occurrence.sourceKind),
      sourceRefId,
      tokenId: occurrence.tokenId ?? undefined
    }
  );
}
