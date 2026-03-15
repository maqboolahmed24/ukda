import type {
  CreateProjectIndexRebuildRequest,
  IndexKind,
  ProjectActiveIndexesResponse,
  ProjectIndex,
  ProjectIndexActivateResponse,
  ProjectIndexCancelResponse,
  ProjectIndexListResponse,
  ProjectIndexRebuildResponse,
  ProjectIndexStatusResponse
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryCacheClass } from "./data/cache-policy";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type IndexesApiResult<T> = ApiResult<T>;

async function requestIndexesApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    cacheClass?: QueryCacheClass;
    expectNoContent?: boolean;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<IndexesApiResult<T>> {
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

function toKindPathSegment(kind: IndexKind): "search" | "entity" | "derivative" {
  if (kind === "SEARCH") {
    return "search";
  }
  if (kind === "ENTITY") {
    return "entity";
  }
  return "derivative";
}

function toCollectionPath(kind: IndexKind): "search-indexes" | "entity-indexes" | "derivative-indexes" {
  if (kind === "SEARCH") {
    return "search-indexes";
  }
  if (kind === "ENTITY") {
    return "entity-indexes";
  }
  return "derivative-indexes";
}

export async function getProjectActiveIndexes(
  projectId: string
): Promise<IndexesApiResult<ProjectActiveIndexesResponse>> {
  return requestIndexesApi<ProjectActiveIndexesResponse>(
    `/projects/${projectId}/indexes/active`,
    {
      queryKey: queryKeys.projects.indexesActive(projectId)
    }
  );
}

export async function listProjectIndexes(
  projectId: string,
  kind: IndexKind
): Promise<IndexesApiResult<ProjectIndexListResponse>> {
  return requestIndexesApi<ProjectIndexListResponse>(
    `/projects/${projectId}/${toCollectionPath(kind)}`,
    {
      queryKey: queryKeys.projects.indexesList(projectId, kind)
    }
  );
}

export async function rebuildProjectIndex(
  projectId: string,
  kind: IndexKind,
  payload: CreateProjectIndexRebuildRequest,
  options?: { force?: boolean }
): Promise<IndexesApiResult<ProjectIndexRebuildResponse>> {
  const force = options?.force === true ? "?force=true" : "";
  return requestIndexesApi<ProjectIndexRebuildResponse>(
    `/projects/${projectId}/${toCollectionPath(kind)}/rebuild${force}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sourceSnapshotJson: payload.sourceSnapshotJson,
        buildParametersJson: payload.buildParametersJson ?? {},
        supersedesIndexId: payload.supersedesIndexId ?? null
      })
    }
  );
}

export async function getProjectIndex(
  projectId: string,
  kind: IndexKind,
  indexId: string
): Promise<IndexesApiResult<ProjectIndex>> {
  return requestIndexesApi<ProjectIndex>(
    `/projects/${projectId}/${toCollectionPath(kind)}/${indexId}`,
    {
      queryKey: queryKeys.projects.indexesDetail(projectId, kind, indexId)
    }
  );
}

export async function getProjectIndexStatus(
  projectId: string,
  kind: IndexKind,
  indexId: string
): Promise<IndexesApiResult<ProjectIndexStatusResponse>> {
  return requestIndexesApi<ProjectIndexStatusResponse>(
    `/projects/${projectId}/${toCollectionPath(kind)}/${indexId}/status`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.projects.indexesStatus(projectId, kind, indexId)
    }
  );
}

export async function cancelProjectIndex(
  projectId: string,
  kind: IndexKind,
  indexId: string
): Promise<IndexesApiResult<ProjectIndexCancelResponse>> {
  return requestIndexesApi<ProjectIndexCancelResponse>(
    `/projects/${projectId}/${toCollectionPath(kind)}/${indexId}/cancel`,
    { method: "POST" }
  );
}

export async function activateProjectIndex(
  projectId: string,
  kind: IndexKind,
  indexId: string
): Promise<IndexesApiResult<ProjectIndexActivateResponse>> {
  return requestIndexesApi<ProjectIndexActivateResponse>(
    `/projects/${projectId}/${toCollectionPath(kind)}/${indexId}/activate`,
    { method: "POST" }
  );
}

export function projectIndexKindFromPath(
  segment: string
): IndexKind | null {
  if (segment === "search") {
    return "SEARCH";
  }
  if (segment === "entity") {
    return "ENTITY";
  }
  if (segment === "derivative") {
    return "DERIVATIVE";
  }
  return null;
}

export function projectIndexKindLabel(kind: IndexKind): string {
  if (kind === "SEARCH") {
    return "Search";
  }
  if (kind === "ENTITY") {
    return "Entity";
  }
  return "Derivative";
}

export function projectIndexDetailPathSegment(kind: IndexKind): "search" | "entity" | "derivative" {
  return toKindPathSegment(kind);
}
