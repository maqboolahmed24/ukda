import type {
  OperationsAlertListResponse,
  OperationsAlertState,
  OperationsOverviewResponse,
  OperationsSloListResponse,
  OperationsTimelineListResponse,
  OperationsTimelineScope
} from "@ukde/contracts";

import { readSessionToken } from "./auth/session";
import { resolveApiOrigins } from "./bootstrap-content";
import { buildApiTraceHeaders, logServerDiagnostic } from "./telemetry";

export interface OperationsApiResult<T> {
  ok: boolean;
  status: number;
  data?: T;
  detail?: string;
}

interface OperationsAlertsFilters {
  state?: OperationsAlertState | "ALL";
  cursor?: number;
  pageSize?: number;
}

interface OperationsTimelineFilters {
  scope?: OperationsTimelineScope | "all";
  cursor?: number;
  pageSize?: number;
}

async function requestOperationsApi<T>(
  path: string,
  init?: RequestInit
): Promise<OperationsApiResult<T>> {
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
    logServerDiagnostic("operations_api_fetch_failed", {
      path,
      method: init?.method ?? "GET",
      errorClass: error instanceof Error ? error.name : "unknown"
    });
    return {
      ok: false,
      status: 503,
      detail: "Operations API is unavailable."
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

function toQueryString(
  params: Record<string, string | number | undefined>
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) {
      continue;
    }
    query.set(key, String(value));
  }
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
}

export async function getOperationsOverview(): Promise<
  OperationsApiResult<OperationsOverviewResponse>
> {
  return requestOperationsApi<OperationsOverviewResponse>(
    "/admin/operations/overview"
  );
}

export async function getOperationsSlos(): Promise<
  OperationsApiResult<OperationsSloListResponse>
> {
  return requestOperationsApi<OperationsSloListResponse>(
    "/admin/operations/slos"
  );
}

export async function listOperationsAlerts(
  filters: OperationsAlertsFilters
): Promise<OperationsApiResult<OperationsAlertListResponse>> {
  return requestOperationsApi<OperationsAlertListResponse>(
    `/admin/operations/alerts${toQueryString({
      state: filters.state,
      cursor: filters.cursor,
      pageSize: filters.pageSize
    })}`
  );
}

export async function listOperationsTimelines(
  filters: OperationsTimelineFilters
): Promise<OperationsApiResult<OperationsTimelineListResponse>> {
  return requestOperationsApi<OperationsTimelineListResponse>(
    `/admin/operations/timelines${toQueryString({
      scope: filters.scope,
      cursor: filters.cursor,
      pageSize: filters.pageSize
    })}`
  );
}
