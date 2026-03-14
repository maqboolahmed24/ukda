import type { SecurityStatusResponse } from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import { queryKeys } from "./data/query-keys";

export type SecurityApiResult<T> = ApiResult<T>;

async function requestSecurityApi<T>(
  path: string
): Promise<SecurityApiResult<T>> {
  return requestServerApi<T>({
    path,
    cacheClass: "governance-event",
    queryKey: queryKeys.security.status()
  });
}

export async function getSecurityStatus(): Promise<
  SecurityApiResult<SecurityStatusResponse>
> {
  return requestSecurityApi<SecurityStatusResponse>("/admin/security/status");
}
