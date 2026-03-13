import type { SessionIssueResponse } from "@ukde/contracts";
import { NextRequest, NextResponse } from "next/server";

import { resolveApiOrigins } from "../../../lib/bootstrap-content";
import {
  getOidcCodeVerifierCookieName,
  getOidcNonceCookieName,
  getOidcStateCookieName
} from "../../../lib/auth/oidc";
import {
  buildApiTraceHeaders,
  logServerDiagnostic
} from "../../../lib/telemetry";
import {
  getCsrfCookieName,
  getSessionCookieName,
  shouldUseSecureCookies
} from "../../../lib/auth/session";

function redirectTo(path: string, status = 307): NextResponse {
  return new NextResponse(null, {
    status,
    headers: {
      Location: path
    }
  });
}

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const expectedState =
    request.cookies.get(getOidcStateCookieName())?.value ?? null;
  const codeVerifier =
    request.cookies.get(getOidcCodeVerifierCookieName())?.value ?? null;
  const nonce = request.cookies.get(getOidcNonceCookieName())?.value ?? null;

  if (!code || !state || !expectedState || !codeVerifier || !nonce) {
    return redirectTo("/login?error=oidc-callback");
  }
  if (state !== expectedState) {
    return redirectTo("/login?error=oidc-state");
  }

  const { internalOrigin } = resolveApiOrigins();
  const traceHeaders = await buildApiTraceHeaders();
  try {
    const response = await fetch(`${internalOrigin}/auth/oidc/exchange`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...traceHeaders
      },
      body: JSON.stringify({
        code,
        code_verifier: codeVerifier,
        nonce
      }),
      cache: "no-store"
    });
    if (!response.ok) {
      logServerDiagnostic("oidc_exchange_failed", {
        path: "/auth/oidc/exchange",
        status: response.status
      });
      return redirectTo("/login?error=oidc-exchange");
    }

    const payload = (await response.json()) as SessionIssueResponse;
    const redirectResponse = redirectTo("/projects");
    const secure = shouldUseSecureCookies();
    redirectResponse.cookies.set(getSessionCookieName(), payload.sessionToken, {
      expires: new Date(payload.session.expiresAt),
      httpOnly: true,
      path: "/",
      sameSite: "lax",
      secure
    });
    redirectResponse.cookies.set(getCsrfCookieName(), payload.csrfToken, {
      expires: new Date(payload.session.expiresAt),
      httpOnly: false,
      path: "/",
      sameSite: "lax",
      secure
    });
    redirectResponse.cookies.delete(getOidcStateCookieName());
    redirectResponse.cookies.delete(getOidcNonceCookieName());
    redirectResponse.cookies.delete(getOidcCodeVerifierCookieName());
    return redirectResponse;
  } catch (error) {
    logServerDiagnostic("oidc_exchange_failed", {
      path: "/auth/oidc/exchange",
      errorClass: error instanceof Error ? error.name : "unknown"
    });
    return redirectTo("/login?error=oidc-exchange");
  }
}
