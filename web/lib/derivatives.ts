import type {
  ProjectDerivativeCandidateSnapshotCreateResponse,
  ProjectDerivativeDetailResponse,
  ProjectDerivativeListResponse,
  ProjectDerivativePreviewResponse,
  ProjectDerivativeStatusResponse
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryCacheClass } from "./data/cache-policy";
import { queryKeys } from "./data/query-keys";
import type { QueryKey } from "./data/query-keys";

export type DerivativesApiResult<T> = ApiResult<T>;

function normalizeScope(
  scope: string | null | undefined
): "active" | "historical" | undefined {
  const value = typeof scope === "string" ? scope.trim().toLowerCase() : "";
  if (value === "active" || value === "historical") {
    return value;
  }
  return undefined;
}

async function requestDerivativesApi<T>(
  path: string,
  options?: {
    cacheClass?: QueryCacheClass;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<DerivativesApiResult<T>> {
  return requestServerApi<T>({
    path,
    cacheClass: options?.cacheClass ?? "mutable-list",
    method: options?.method,
    queryKey: options?.queryKey
  });
}

export async function getProjectDerivatives(
  projectId: string,
  options?: { scope?: string | null }
): Promise<DerivativesApiResult<ProjectDerivativeListResponse>> {
  const scope = normalizeScope(options?.scope);
  const querySuffix = scope && scope !== "active" ? `?scope=${scope}` : "";
  return requestDerivativesApi<ProjectDerivativeListResponse>(
    `/projects/${projectId}/derivatives${querySuffix}`,
    {
      queryKey: queryKeys.projects.derivatives(projectId, {
        scope: scope ?? "active"
      })
    }
  );
}

export async function getProjectDerivativeDetail(
  projectId: string,
  derivativeId: string
): Promise<DerivativesApiResult<ProjectDerivativeDetailResponse>> {
  return requestDerivativesApi<ProjectDerivativeDetailResponse>(
    `/projects/${projectId}/derivatives/${derivativeId}`,
    {
      queryKey: queryKeys.projects.derivativeDetail(projectId, derivativeId)
    }
  );
}

export async function getProjectDerivativeStatus(
  projectId: string,
  derivativeId: string
): Promise<DerivativesApiResult<ProjectDerivativeStatusResponse>> {
  return requestDerivativesApi<ProjectDerivativeStatusResponse>(
    `/projects/${projectId}/derivatives/${derivativeId}/status`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.projects.derivativeStatus(projectId, derivativeId)
    }
  );
}

export async function getProjectDerivativePreview(
  projectId: string,
  derivativeId: string
): Promise<DerivativesApiResult<ProjectDerivativePreviewResponse>> {
  return requestDerivativesApi<ProjectDerivativePreviewResponse>(
    `/projects/${projectId}/derivatives/${derivativeId}/preview`,
    {
      queryKey: queryKeys.projects.derivativePreview(projectId, derivativeId)
    }
  );
}

export async function createProjectDerivativeCandidateSnapshot(
  projectId: string,
  derivativeId: string
): Promise<DerivativesApiResult<ProjectDerivativeCandidateSnapshotCreateResponse>> {
  return requestDerivativesApi<ProjectDerivativeCandidateSnapshotCreateResponse>(
    `/projects/${projectId}/derivatives/${derivativeId}/candidate-snapshots`,
    {
      method: "POST"
    }
  );
}
