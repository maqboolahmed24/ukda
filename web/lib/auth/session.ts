import type { PlatformRole, SessionResponse } from "@ukde/contracts";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { resolveApiOrigins } from "../bootstrap-content";
import { buildApiTraceHeaders, logServerDiagnostic } from "../telemetry";

const FALLBACK_SESSION_COOKIE = "ukde_session";
const FALLBACK_CSRF_COOKIE = "ukde_csrf";

export function getSessionCookieName(): string {
  return process.env.AUTH_COOKIE_NAME?.trim() || FALLBACK_SESSION_COOKIE;
}

export function getCsrfCookieName(): string {
  return process.env.AUTH_CSRF_COOKIE_NAME?.trim() || FALLBACK_CSRF_COOKIE;
}

export function shouldUseSecureCookies(): boolean {
  const appEnv = (
    process.env.APP_ENV ||
    process.env.NEXT_PUBLIC_APP_ENV ||
    "dev"
  ).toLowerCase();
  return appEnv === "staging" || appEnv === "prod";
}

export async function readSessionToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(getSessionCookieName())?.value ?? null;
}

export async function readCsrfToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(getCsrfCookieName())?.value ?? null;
}

export async function resolveCurrentSession(
  tokenOverride?: string
): Promise<SessionResponse | null> {
  const token = tokenOverride ?? (await readSessionToken());
  if (!token) {
    return null;
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
