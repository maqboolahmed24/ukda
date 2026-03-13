import type { SecurityStatusResponse } from "@ukde/contracts";

import { readSessionToken } from "./auth/session";
import { resolveApiOrigins } from "./bootstrap-content";
import { buildApiTraceHeaders, logServerDiagnostic } from "./telemetry";

export interface SecurityApiResult<T> {
  ok: boolean;
  status: number;
  data?: T;
  detail?: string;
}

async function requestSecurityApi<T>(
  path: string
): Promise<SecurityApiResult<T>> {
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
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${token}`,
        ...traceHeaders
      }
    });
  } catch (error) {
    logServerDiagnostic("security_api_fetch_failed", {
      path,
      method: "GET",
      errorClass: error instanceof Error ? error.name : "unknown"
    });
    return {
      ok: false,
      status: 503,
      detail: "Security API is unavailable."
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

export async function getSecurityStatus(): Promise<
  SecurityApiResult<SecurityStatusResponse>
> {
  return requestSecurityApi<SecurityStatusResponse>("/admin/security/status");
}
