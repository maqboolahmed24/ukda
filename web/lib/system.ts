import type {
  AuthProviderResponse,
  ServiceHealthPayload,
  ServiceReadinessPayload,
  ServiceUnavailablePayload
} from "@ukde/contracts";

import { normalizeAuthProviderResponse } from "./auth/providers";
import { type ApiResult, requestServerApi } from "./data/api-client";
import { queryKeys } from "./data/query-keys";

export type SystemApiResult<T> = ApiResult<T>;

const UNREACHABLE_PAYLOAD: ServiceUnavailablePayload = {
  service: "api",
  status: "UNREACHABLE",
  environment: "dev",
  version: "bootstrap",
  timestamp: new Date(0).toISOString(),
  detail: "API has not been contacted yet."
};

export async function getAuthProviders(): Promise<AuthProviderResponse> {
  const result = await requestServerApi<AuthProviderResponse>({
    cacheClass: "public-status",
    path: "/auth/providers",
    queryKey: queryKeys.auth.providers(),
    requireAuth: false
  });
  if (!result.ok || !result.data) {
    return {
      oidcEnabled: false,
      devEnabled: false,
      devSeeds: []
    };
  }
  return normalizeAuthProviderResponse(result.data);
}

export async function getServiceHealth(): Promise<
  ServiceHealthPayload | ServiceUnavailablePayload
> {
  const result = await requestServerApi<ServiceHealthPayload>({
    cacheClass: "public-status",
    path: "/healthz",
    queryKey: queryKeys.system.health(),
    requireAuth: false
  });
  if (!result.ok || !result.data) {
    return {
      ...UNREACHABLE_PAYLOAD,
      detail: result.detail ?? "Could not connect to /healthz."
    };
  }
  return result.data;
}

export async function getServiceReadiness(): Promise<
  ServiceReadinessPayload | ServiceUnavailablePayload
> {
  const result = await requestServerApi<ServiceReadinessPayload>({
    allowStatuses: [503],
    cacheClass: "public-status",
    path: "/readyz",
    queryKey: queryKeys.system.readiness(),
    requireAuth: false
  });
  if (!result.ok || !result.data) {
    return {
      ...UNREACHABLE_PAYLOAD,
      detail: result.detail ?? "Could not connect to /readyz."
    };
  }
  return result.data;
}
