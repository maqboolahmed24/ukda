import type {
  AuditEvent,
  AuditEventListResponse,
  AuditEventType,
  AuditIntegrityResponse
} from "@ukde/contracts";

import { readSessionToken } from "./auth/session";
import { resolveApiOrigins } from "./bootstrap-content";
import { buildApiTraceHeaders, logServerDiagnostic } from "./telemetry";

export interface AuditApiResult<T> {
  ok: boolean;
  status: number;
  data?: T;
  detail?: string;
}

async function requestAuditApi<T>(
  path: string,
  init?: RequestInit
): Promise<AuditApiResult<T>> {
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
    logServerDiagnostic("audit_api_fetch_failed", {
      path,
      method: init?.method ?? "GET",
      errorClass: error instanceof Error ? error.name : "unknown"
    });
    return {
      ok: false,
      status: 503,
      detail: "Audit API is unavailable."
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
    logServerDiagnostic("audit_api_server_error", {
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
    `/admin/audit-events${toAuditQueryString(filters)}`
  );
}

export async function getAuditEvent(
  eventId: string
): Promise<AuditApiResult<AuditEvent>> {
  return requestAuditApi<AuditEvent>(`/admin/audit-events/${eventId}`);
}

export async function getAuditIntegrity(): Promise<
  AuditApiResult<AuditIntegrityResponse>
> {
  return requestAuditApi<AuditIntegrityResponse>("/admin/audit-integrity");
}

export async function listMyActivity(
  limit: number = 50
): Promise<AuditApiResult<AuditEventListResponse>> {
  return requestAuditApi<AuditEventListResponse>(`/me/activity?limit=${limit}`);
}
