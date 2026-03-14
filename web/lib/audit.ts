import type {
  AuditEvent,
  AuditEventListResponse,
  AuditEventType,
  AuditIntegrityResponse
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type AuditApiResult<T> = ApiResult<T>;

async function requestAuditApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<AuditApiResult<T>> {
  return requestServerApi<T>({
    path,
    method: options?.method,
    headers: options?.headers,
    body: options?.body,
    cacheClass: "governance-event",
    queryKey: options?.queryKey
  });
}

interface AuditFilterInput {
  projectId?: string;
  actorUserId?: string;
  eventType?: AuditEventType;
  from?: string;
  to?: string;
  cursor?: number;
  pageSize?: number;
}

function toAuditQueryString(filters: AuditFilterInput): string {
  const params = new URLSearchParams();
  if (filters.projectId) {
    params.set("projectId", filters.projectId);
  }
  if (filters.actorUserId) {
    params.set("actorUserId", filters.actorUserId);
  }
  if (filters.eventType) {
    params.set("eventType", filters.eventType);
  }
  if (filters.from) {
    params.set("from", filters.from);
  }
  if (filters.to) {
    params.set("to", filters.to);
  }
  if (typeof filters.cursor === "number") {
    params.set("cursor", String(filters.cursor));
  }
  if (typeof filters.pageSize === "number") {
    params.set("pageSize", String(filters.pageSize));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function listAuditEvents(
  filters: AuditFilterInput
): Promise<AuditApiResult<AuditEventListResponse>> {
  return requestAuditApi<AuditEventListResponse>(
    `/admin/audit-events${toAuditQueryString(filters)}`,
    {
      queryKey: queryKeys.audit.list(filters)
    }
  );
}

export async function getAuditEvent(
  eventId: string
): Promise<AuditApiResult<AuditEvent>> {
  return requestAuditApi<AuditEvent>(`/admin/audit-events/${eventId}`, {
    queryKey: queryKeys.audit.detail(eventId)
  });
}

export async function getAuditIntegrity(): Promise<
  AuditApiResult<AuditIntegrityResponse>
> {
  return requestAuditApi<AuditIntegrityResponse>("/admin/audit-integrity", {
    queryKey: queryKeys.audit.integrity()
  });
}

export async function listMyActivity(
  limit: number = 50
): Promise<AuditApiResult<AuditEventListResponse>> {
  return requestAuditApi<AuditEventListResponse>(`/me/activity?limit=${limit}`, {
    queryKey: queryKeys.audit.myActivity(limit)
  });
}
