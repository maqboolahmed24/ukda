import type {
  CreateRiskAcceptanceRequest,
  RenewRiskAcceptanceRequest,
  RevokeRiskAcceptanceRequest,
  ReviewScheduleRequest,
  RiskAcceptance,
  RiskAcceptanceEventsResponse,
  RiskAcceptanceListResponse,
  SecurityFinding,
  SecurityFindingsListResponse,
  SecurityStatusResponse
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type SecurityApiResult<T> = ApiResult<T>;

interface RiskAcceptanceFilters {
  findingId?: string;
  status?: "ACTIVE" | "EXPIRED" | "REVOKED";
}

async function requestSecurityApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<SecurityApiResult<T>> {
  return requestServerApi<T>({
    path,
    method: options?.method,
    headers: options?.headers,
    body: options?.body,
    cacheClass: "governance-event",
    queryKey: options?.queryKey
  });
}

export async function getSecurityStatus(): Promise<
  SecurityApiResult<SecurityStatusResponse>
> {
  return requestSecurityApi<SecurityStatusResponse>("/admin/security/status", {
    queryKey: queryKeys.security.status()
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

export async function listAdminSecurityFindings(): Promise<
  SecurityApiResult<SecurityFindingsListResponse>
> {
  return requestSecurityApi<SecurityFindingsListResponse>("/admin/security/findings", {
    queryKey: queryKeys.admin.securityFindings()
  });
}

export async function getAdminSecurityFinding(
  findingId: string
): Promise<SecurityApiResult<SecurityFinding>> {
  const encoded = encodeURIComponent(findingId);
  return requestSecurityApi<SecurityFinding>(`/admin/security/findings/${encoded}`, {
    queryKey: queryKeys.admin.securityFindingDetail(findingId)
  });
}

export async function createAdminRiskAcceptance(
  findingId: string,
  payload: CreateRiskAcceptanceRequest
): Promise<SecurityApiResult<RiskAcceptance>> {
  const encoded = encodeURIComponent(findingId);
  return requestSecurityApi<RiskAcceptance>(
    `/admin/security/findings/${encoded}/risk-acceptance`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function listAdminRiskAcceptances(
  filters: RiskAcceptanceFilters
): Promise<SecurityApiResult<RiskAcceptanceListResponse>> {
  const path = `/admin/security/risk-acceptances${toQueryString({
    findingId: filters.findingId,
    status: filters.status
  })}`;
  return requestSecurityApi<RiskAcceptanceListResponse>(path, {
    queryKey: queryKeys.admin.securityRiskAcceptances({
      findingId: filters.findingId,
      status: filters.status
    })
  });
}

export async function getAdminRiskAcceptance(
  riskAcceptanceId: string
): Promise<SecurityApiResult<RiskAcceptance>> {
  const encoded = encodeURIComponent(riskAcceptanceId);
  return requestSecurityApi<RiskAcceptance>(
    `/admin/security/risk-acceptances/${encoded}`,
    {
      queryKey: queryKeys.admin.securityRiskAcceptanceDetail(riskAcceptanceId)
    }
  );
}

export async function listAdminRiskAcceptanceEvents(
  riskAcceptanceId: string
): Promise<SecurityApiResult<RiskAcceptanceEventsResponse>> {
  const encoded = encodeURIComponent(riskAcceptanceId);
  return requestSecurityApi<RiskAcceptanceEventsResponse>(
    `/admin/security/risk-acceptances/${encoded}/events`,
    {
      queryKey: queryKeys.admin.securityRiskAcceptanceEvents(riskAcceptanceId)
    }
  );
}

export async function renewAdminRiskAcceptance(
  riskAcceptanceId: string,
  payload: RenewRiskAcceptanceRequest
): Promise<SecurityApiResult<RiskAcceptance>> {
  const encoded = encodeURIComponent(riskAcceptanceId);
  return requestSecurityApi<RiskAcceptance>(
    `/admin/security/risk-acceptances/${encoded}/renew`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function scheduleAdminRiskAcceptanceReview(
  riskAcceptanceId: string,
  payload: ReviewScheduleRequest
): Promise<SecurityApiResult<RiskAcceptance>> {
  const encoded = encodeURIComponent(riskAcceptanceId);
  return requestSecurityApi<RiskAcceptance>(
    `/admin/security/risk-acceptances/${encoded}/review-schedule`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function revokeAdminRiskAcceptance(
  riskAcceptanceId: string,
  payload: RevokeRiskAcceptanceRequest
): Promise<SecurityApiResult<RiskAcceptance>> {
  const encoded = encodeURIComponent(riskAcceptanceId);
  return requestSecurityApi<RiskAcceptance>(
    `/admin/security/risk-acceptances/${encoded}/revoke`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}
