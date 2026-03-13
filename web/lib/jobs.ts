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

import { readSessionToken } from "./auth/session";
import { resolveApiOrigins } from "./bootstrap-content";
import { buildApiTraceHeaders, logServerDiagnostic } from "./telemetry";

export interface JobApiResult<T> {
  ok: boolean;
  status: number;
  data?: T;
  detail?: string;
}

async function requestJobApi<T>(
  path: string,
  init?: RequestInit
): Promise<JobApiResult<T>> {
  const token = await readSessionToken();
  if (!token) {
    return {
      ok: false,
      status: 401,
      detail: "Authentication is required."
    };
  }

  const { internalOrigin } = resolveApiOrigins();
  const traceHeaders = await buildApiTraceHeaders();
  let response: Response;
  try {
    response = await fetch(`${internalOrigin}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${token}`,
        ...traceHeaders,
        ...(init?.headers ?? {})
      }
    });
  } catch (error) {
    logServerDiagnostic("jobs_api_fetch_failed", {
      path,
      method: init?.method ?? "GET",
      errorClass: error instanceof Error ? error.name : "unknown"
    });
    return {
      ok: false,
      status: 503,
      detail: "Jobs API is unavailable."
    };
  }

  let parsed: unknown;
  try {
    parsed = await response.json();
  } catch {
    parsed = undefined;
  }

  if (!response.ok) {
    const detail =
      typeof parsed === "object" &&
      parsed !== null &&
      "detail" in parsed &&
      typeof parsed.detail === "string"
        ? parsed.detail
        : "Request failed.";
    return {
      ok: false,
      status: response.status,
      detail
    };
  }

  if (response.status >= 500) {
    logServerDiagnostic("jobs_api_server_error", {
      path,
      method: init?.method ?? "GET",
      status: response.status
    });
  }

  return {
    ok: true,
    status: response.status,
    data: parsed as T
  };
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
    `/projects/${projectId}/jobs${toQueryString(pagination)}`
  );
}

export async function getProjectJob(
  projectId: string,
  jobId: string
): Promise<JobApiResult<ProjectJob>> {
  return requestJobApi<ProjectJob>(`/projects/${projectId}/jobs/${jobId}`);
}

export async function getProjectJobStatus(
  projectId: string,
  jobId: string
): Promise<JobApiResult<ProjectJobStatusResponse>> {
  return requestJobApi<ProjectJobStatusResponse>(
    `/projects/${projectId}/jobs/${jobId}/status`
  );
}

export async function listProjectJobEvents(
  projectId: string,
  jobId: string,
  pagination: PaginationInput = {}
): Promise<JobApiResult<ProjectJobEventListResponse>> {
  return requestJobApi<ProjectJobEventListResponse>(
    `/projects/${projectId}/jobs/${jobId}/events${toQueryString(pagination)}`
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
    `/projects/${projectId}/jobs/summary`
  );
}
