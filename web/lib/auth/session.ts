import type { PlatformRole, SessionResponse } from "@ukde/contracts";
import { redirect } from "next/navigation";

import { resolveApiOrigins } from "../bootstrap-content";
import { resolveBrowserRegressionFixtureSession } from "../data/browser-regression-fixtures";
import { buildApiTraceHeaders, logServerDiagnostic } from "../telemetry";
export {
  getCsrfCookieName,
  getSessionCookieName,
  readCsrfToken,
  readSessionToken,
  shouldUseSecureCookies
} from "./cookies";
import { readSessionToken } from "./cookies";

export async function resolveCurrentSession(
  tokenOverride?: string
): Promise<SessionResponse | null> {
  const token = tokenOverride ?? (await readSessionToken());
  if (!token) {
    return null;
  }

  const fixtureSession = resolveBrowserRegressionFixtureSession(token);
  if (fixtureSession) {
    return fixtureSession;
  }

  const { internalOrigin } = resolveApiOrigins();
  const traceHeaders = await buildApiTraceHeaders();
  let response: Response;
  try {
    response = await fetch(`${internalOrigin}/auth/session`, {
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${token}`,
        ...traceHeaders
      }
    });
  } catch (error) {
    logServerDiagnostic("auth_session_fetch_failed", {
      path: "/auth/session",
      errorClass: error instanceof Error ? error.name : "unknown"
    });
    return null;
  }

  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    logServerDiagnostic("auth_session_non_200", {
      path: "/auth/session",
      status: response.status
    });
    return null;
  }
  return (await response.json()) as SessionResponse;
}

export async function requireCurrentSession(): Promise<SessionResponse> {
  const session = await resolveCurrentSession();
  if (!session) {
    redirect("/login");
  }
  return session;
}

export async function requirePlatformRole(
  requiredRoles: PlatformRole[]
): Promise<SessionResponse> {
  const session = await requireCurrentSession();
  const current = new Set(session.user.platformRoles);
  const hasRole = requiredRoles.some((role) => current.has(role));
  if (!hasRole) {
    redirect("/projects");
  }
  return session;
}
