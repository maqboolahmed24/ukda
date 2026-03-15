import type {
  PseudonymRegistryEntry,
  PseudonymRegistryEntryEventListResponse,
  PseudonymRegistryEntryListResponse
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryCacheClass } from "./data/cache-policy";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type PseudonymRegistryApiResult<T> = ApiResult<T>;

async function requestPseudonymRegistryApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    cacheClass?: QueryCacheClass;
    expectNoContent?: boolean;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<PseudonymRegistryApiResult<T>> {
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

export async function listProjectPseudonymRegistryEntries(
  projectId: string
): Promise<PseudonymRegistryApiResult<PseudonymRegistryEntryListResponse>> {
  return requestPseudonymRegistryApi<PseudonymRegistryEntryListResponse>(
    `/projects/${projectId}/pseudonym-registry`,
    {
      queryKey: queryKeys.projects.pseudonymRegistryList(projectId)
    }
  );
}

export async function getProjectPseudonymRegistryEntry(
  projectId: string,
  entryId: string
): Promise<PseudonymRegistryApiResult<PseudonymRegistryEntry>> {
  return requestPseudonymRegistryApi<PseudonymRegistryEntry>(
    `/projects/${projectId}/pseudonym-registry/${entryId}`,
    {
      queryKey: queryKeys.projects.pseudonymRegistryDetail(projectId, entryId)
    }
  );
}

export async function listProjectPseudonymRegistryEntryEvents(
  projectId: string,
  entryId: string
): Promise<PseudonymRegistryApiResult<PseudonymRegistryEntryEventListResponse>> {
  return requestPseudonymRegistryApi<PseudonymRegistryEntryEventListResponse>(
    `/projects/${projectId}/pseudonym-registry/${entryId}/events`,
    {
      queryKey: queryKeys.projects.pseudonymRegistryEvents(projectId, entryId)
    }
  );
}
