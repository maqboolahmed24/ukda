import type { ExportStubDisabledResponse } from "@ukde/contracts";

import { readSessionToken } from "./auth/session";
import { resolveApiOrigins } from "./bootstrap-content";
import { buildApiTraceHeaders, logServerDiagnostic } from "./telemetry";

export interface ExportApiResult<T> {
  ok: boolean;
  status: number;
  data?: T;
  detail?: string;
}

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
  init?: RequestInit
): Promise<ExportApiResult<T>> {
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
    logServerDiagnostic("export_api_fetch_failed", {
      path,
      method: init?.method ?? "GET",
      errorClass: error instanceof Error ? error.name : "unknown"
    });
    return {
      ok: false,
      status: 503,
      detail: "Export API is unavailable."
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

  return {
    ok: true,
    status: response.status,
    data: parsed as T
  };
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
  return requestExportApi<ExportStubDisabledResponse>(
    `/projects/${projectId}/export-candidates`
  );
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
    })}`
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
    })}`
  );
}
