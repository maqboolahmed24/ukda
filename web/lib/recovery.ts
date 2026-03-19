import type {
  RecoveryDrillCancelResponse,
  RecoveryDrillCreateRequest,
  RecoveryDrillCreateResponse,
  RecoveryDrillDetailResponse,
  RecoveryDrillEvidenceResponse,
  RecoveryDrillListResponse,
  RecoveryDrillStatusResponse,
  RecoveryStatusResponse
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type RecoveryApiResult<T> = ApiResult<T>;

interface RecoveryDrillsFilters {
  cursor?: number;
  pageSize?: number;
}

async function requestRecoveryApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<RecoveryApiResult<T>> {
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

export async function getAdminRecoveryStatus(): Promise<
  RecoveryApiResult<RecoveryStatusResponse>
> {
  return requestRecoveryApi<RecoveryStatusResponse>("/admin/recovery/status", {
    queryKey: queryKeys.admin.recoveryStatus()
  });
}

export async function listAdminRecoveryDrills(
  filters: RecoveryDrillsFilters
): Promise<RecoveryApiResult<RecoveryDrillListResponse>> {
  const cursor =
    typeof filters.cursor === "number" ? Math.max(0, Math.round(filters.cursor)) : 0;
  const pageSize =
    typeof filters.pageSize === "number"
      ? Math.max(1, Math.min(200, Math.round(filters.pageSize)))
      : 50;
  return requestRecoveryApi<RecoveryDrillListResponse>(
    `/admin/recovery/drills${toQueryString({ cursor, pageSize })}`,
    {
      queryKey: queryKeys.admin.recoveryDrills({ cursor, pageSize })
    }
  );
}

export async function createAdminRecoveryDrill(
  payload: RecoveryDrillCreateRequest
): Promise<RecoveryApiResult<RecoveryDrillCreateResponse>> {
  return requestRecoveryApi<RecoveryDrillCreateResponse>("/admin/recovery/drills", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function getAdminRecoveryDrill(
  drillId: string
): Promise<RecoveryApiResult<RecoveryDrillDetailResponse>> {
  const encoded = encodeURIComponent(drillId);
  return requestRecoveryApi<RecoveryDrillDetailResponse>(`/admin/recovery/drills/${encoded}`, {
    queryKey: queryKeys.admin.recoveryDrillDetail(drillId)
  });
}

export async function getAdminRecoveryDrillStatus(
  drillId: string
): Promise<RecoveryApiResult<RecoveryDrillStatusResponse>> {
  const encoded = encodeURIComponent(drillId);
  return requestRecoveryApi<RecoveryDrillStatusResponse>(
    `/admin/recovery/drills/${encoded}/status`,
    {
      queryKey: queryKeys.admin.recoveryDrillStatus(drillId)
    }
  );
}

export async function getAdminRecoveryDrillEvidence(
  drillId: string
): Promise<RecoveryApiResult<RecoveryDrillEvidenceResponse>> {
  const encoded = encodeURIComponent(drillId);
  return requestRecoveryApi<RecoveryDrillEvidenceResponse>(
    `/admin/recovery/drills/${encoded}/evidence`,
    {
      queryKey: queryKeys.admin.recoveryDrillEvidence(drillId)
    }
  );
}

export async function cancelAdminRecoveryDrill(
  drillId: string
): Promise<RecoveryApiResult<RecoveryDrillCancelResponse>> {
  const encoded = encodeURIComponent(drillId);
  return requestRecoveryApi<RecoveryDrillCancelResponse>(
    `/admin/recovery/drills/${encoded}/cancel`,
    {
      method: "POST"
    }
  );
}
