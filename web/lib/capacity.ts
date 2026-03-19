import type {
  CapacityTestCreateRequest,
  CapacityTestCreateResponse,
  CapacityTestRunDetailResponse,
  CapacityTestRunListResponse,
  CapacityTestRunResultsResponse
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type CapacityApiResult<T> = ApiResult<T>;

interface CapacityTestsFilters {
  cursor?: number;
  pageSize?: number;
}

async function requestCapacityApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<CapacityApiResult<T>> {
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

export async function listAdminCapacityTests(
  filters: CapacityTestsFilters
): Promise<CapacityApiResult<CapacityTestRunListResponse>> {
  const cursor =
    typeof filters.cursor === "number" ? Math.max(0, Math.round(filters.cursor)) : 0;
  const pageSize =
    typeof filters.pageSize === "number"
      ? Math.max(1, Math.min(200, Math.round(filters.pageSize)))
      : 50;
  return requestCapacityApi<CapacityTestRunListResponse>(
    `/admin/capacity/tests${toQueryString({ cursor, pageSize })}`,
    {
      queryKey: queryKeys.admin.capacityTests({ cursor, pageSize })
    }
  );
}

export async function createAdminCapacityTest(
  payload: CapacityTestCreateRequest
): Promise<CapacityApiResult<CapacityTestCreateResponse>> {
  return requestCapacityApi<CapacityTestCreateResponse>("/admin/capacity/tests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function getAdminCapacityTest(
  testRunId: string
): Promise<CapacityApiResult<CapacityTestRunDetailResponse>> {
  const encoded = encodeURIComponent(testRunId);
  return requestCapacityApi<CapacityTestRunDetailResponse>(
    `/admin/capacity/tests/${encoded}`,
    {
      queryKey: queryKeys.admin.capacityTestDetail(testRunId)
    }
  );
}

export async function getAdminCapacityTestResults(
  testRunId: string
): Promise<CapacityApiResult<CapacityTestRunResultsResponse>> {
  const encoded = encodeURIComponent(testRunId);
  return requestCapacityApi<CapacityTestRunResultsResponse>(
    `/admin/capacity/tests/${encoded}/results`,
    {
      queryKey: queryKeys.admin.capacityTestResults(testRunId)
    }
  );
}
