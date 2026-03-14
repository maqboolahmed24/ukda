import type {
  OperationsAlertListResponse,
  OperationsAlertState,
  OperationsOverviewResponse,
  OperationsSloListResponse,
  OperationsTimelineListResponse,
  OperationsTimelineScope
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type OperationsApiResult<T> = ApiResult<T>;

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
  options?: {
    body?: BodyInit | null;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<OperationsApiResult<T>> {
  return requestServerApi<T>({
    path,
    method: options?.method,
    headers: options?.headers,
    body: options?.body,
    cacheClass: "operations-live",
    queryKey: options?.queryKey
  });
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
    "/admin/operations/overview",
    {
      queryKey: queryKeys.operations.overview()
    }
  );
}

export async function getOperationsSlos(): Promise<
  OperationsApiResult<OperationsSloListResponse>
> {
  return requestOperationsApi<OperationsSloListResponse>("/admin/operations/slos", {
    queryKey: queryKeys.operations.slos()
  });
}

export async function listOperationsAlerts(
  filters: OperationsAlertsFilters
): Promise<OperationsApiResult<OperationsAlertListResponse>> {
  return requestOperationsApi<OperationsAlertListResponse>(
    `/admin/operations/alerts${toQueryString({
      state: filters.state,
      cursor: filters.cursor,
      pageSize: filters.pageSize
    })}`,
    {
      queryKey: queryKeys.operations.alerts(filters)
    }
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
    })}`,
    {
      queryKey: queryKeys.operations.timelines(filters)
    }
  );
}
