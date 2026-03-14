import type { ExportStubDisabledResponse } from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type ExportApiResult<T> = ApiResult<T>;

interface ExportRequestsFilters {
  status?: string;
  requesterId?: string;
  candidateKind?: string;
  cursor?: string;
}

interface ExportReviewFilters {
  status?: string;
  agingBucket?: string;
  reviewerUserId?: string;
}

async function requestExportApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<ExportApiResult<T>> {
  return requestServerApi<T>({
    path,
    method: options?.method,
    headers: options?.headers,
    body: options?.body,
    cacheClass: "governance-event",
    queryKey: options?.queryKey
  });
}

function toQueryString(params: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (!value) {
      continue;
    }
    query.set(key, value);
  }
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
}

export async function listExportCandidates(
  projectId: string
): Promise<ExportApiResult<ExportStubDisabledResponse>> {
  return requestExportApi<ExportStubDisabledResponse>(`/projects/${projectId}/export-candidates`, {
    queryKey: queryKeys.exports.candidates(projectId)
  });
}

export async function listExportRequests(
  projectId: string,
  filters: ExportRequestsFilters
): Promise<ExportApiResult<ExportStubDisabledResponse>> {
  return requestExportApi<ExportStubDisabledResponse>(
    `/projects/${projectId}/export-requests${toQueryString({
      status: filters.status,
      requesterId: filters.requesterId,
      candidateKind: filters.candidateKind,
      cursor: filters.cursor
    })}`,
    {
      queryKey: queryKeys.exports.requests(projectId, filters)
    }
  );
}

export async function listExportReviewQueue(
  projectId: string,
  filters: ExportReviewFilters
): Promise<ExportApiResult<ExportStubDisabledResponse>> {
  return requestExportApi<ExportStubDisabledResponse>(
    `/projects/${projectId}/export-review${toQueryString({
      status: filters.status,
      agingBucket: filters.agingBucket,
      reviewerUserId: filters.reviewerUserId
    })}`,
    {
      queryKey: queryKeys.exports.review(projectId, filters)
    }
  );
}
