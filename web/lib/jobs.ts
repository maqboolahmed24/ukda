import type {
  CreateNoopJobRequest,
  ProjectJob,
  ProjectJobCancelResponse,
  ProjectJobEventListResponse,
  ProjectJobListResponse,
  ProjectJobMutationResponse,
  ProjectJobStatusResponse,
  ProjectJobSummaryResponse
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryCacheClass } from "./data/cache-policy";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type JobApiResult<T> = ApiResult<T>;

async function requestJobApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    cacheClass?: QueryCacheClass;
    expectNoContent?: boolean;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<JobApiResult<T>> {
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

interface PaginationInput {
  cursor?: number;
  pageSize?: number;
}

function toQueryString(pagination: PaginationInput): string {
  const params = new URLSearchParams();
  if (typeof pagination.cursor === "number") {
    params.set("cursor", String(pagination.cursor));
  }
  if (typeof pagination.pageSize === "number") {
    params.set("pageSize", String(pagination.pageSize));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function listProjectJobs(
  projectId: string,
  pagination: PaginationInput = {}
): Promise<JobApiResult<ProjectJobListResponse>> {
  return requestJobApi<ProjectJobListResponse>(
    `/projects/${projectId}/jobs${toQueryString(pagination)}`,
    {
      queryKey: queryKeys.jobs.list(projectId, pagination)
    }
  );
}

export async function getProjectJob(
  projectId: string,
  jobId: string
): Promise<JobApiResult<ProjectJob>> {
  return requestJobApi<ProjectJob>(`/projects/${projectId}/jobs/${jobId}`, {
    queryKey: queryKeys.jobs.detail(projectId, jobId)
  });
}

export async function getProjectJobStatus(
  projectId: string,
  jobId: string
): Promise<JobApiResult<ProjectJobStatusResponse>> {
  return requestJobApi<ProjectJobStatusResponse>(
    `/projects/${projectId}/jobs/${jobId}/status`,
    {
      cacheClass: "operations-live",
      queryKey: queryKeys.jobs.status(projectId, jobId)
    }
  );
}

export async function listProjectJobEvents(
  projectId: string,
  jobId: string,
  pagination: PaginationInput = {}
): Promise<JobApiResult<ProjectJobEventListResponse>> {
  return requestJobApi<ProjectJobEventListResponse>(
    `/projects/${projectId}/jobs/${jobId}/events${toQueryString(pagination)}`,
    {
      queryKey: queryKeys.jobs.events(projectId, jobId, pagination)
    }
  );
}

export async function enqueueNoopProjectJob(
  projectId: string,
  payload: CreateNoopJobRequest
): Promise<JobApiResult<ProjectJobMutationResponse>> {
  return requestJobApi<ProjectJobMutationResponse>(
    `/projects/${projectId}/jobs`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        logical_key: payload.logicalKey,
        mode: payload.mode,
        max_attempts: payload.maxAttempts ?? 1,
        delay_ms: payload.delayMs ?? 0
      })
    }
  );
}

export async function retryProjectJob(
  projectId: string,
  jobId: string
): Promise<JobApiResult<ProjectJobMutationResponse>> {
  return requestJobApi<ProjectJobMutationResponse>(
    `/projects/${projectId}/jobs/${jobId}/retry`,
    { method: "POST" }
  );
}

export async function cancelProjectJob(
  projectId: string,
  jobId: string
): Promise<JobApiResult<ProjectJobCancelResponse>> {
  return requestJobApi<ProjectJobCancelResponse>(
    `/projects/${projectId}/jobs/${jobId}/cancel`,
    { method: "POST" }
  );
}

export async function getProjectJobsSummary(
  projectId: string
): Promise<JobApiResult<ProjectJobSummaryResponse>> {
  return requestJobApi<ProjectJobSummaryResponse>(
    `/projects/${projectId}/jobs/summary`,
    {
      queryKey: queryKeys.jobs.summary(projectId)
    }
  );
}
