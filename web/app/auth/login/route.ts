import { NextResponse } from "next/server";

import { resolveApiOrigins } from "../../../lib/bootstrap-content";
import {
  generateCodeChallenge,
  generateStateToken,
  generateVerifier,
  getOidcCodeVerifierCookieName,
  getOidcNonceCookieName,
  getOidcStateCookieName
} from "../../../lib/auth/oidc";
import {
  buildApiTraceHeaders,
  logServerDiagnostic
} from "../../../lib/telemetry";
import { shouldUseSecureCookies } from "../../../lib/auth/session";

interface AuthorizationUrlResponse {
  authorizationUrl: string;
}

function redirectTo(path: string, status = 307): NextResponse {
  return new NextResponse(null, {
    status,
    headers: {
      Location: path
    }
  });
}

export async function GET() {
  const { internalOrigin } = resolveApiOrigins();
  const state = generateStateToken();
  const nonce = generateStateToken();
  const codeVerifier = generateVerifier();
  const codeChallenge = generateCodeChallenge(codeVerifier);
  const traceHeaders = await buildApiTraceHeaders();

  try {
    const response = await fetch(
      `${internalOrigin}/auth/oidc/authorization-url`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...traceHeaders
        },
        body: JSON.stringify({
          state,
          nonce,
          code_challenge: codeChallenge
        }),
        cache: "no-store"
      }
    );

    if (!response.ok) {
      logServerDiagnostic("oidc_authorization_url_failed", {
        path: "/auth/oidc/authorization-url",
        status: response.status
      });
      return redirectTo("/login?error=oidc-start");
    }

    const payload = (await response.json()) as AuthorizationUrlResponse;
    const redirectResponse = NextResponse.redirect(payload.authorizationUrl);
    const secure = shouldUseSecureCookies();
    const sharedCookieOptions = {
      httpOnly: true,
      maxAge: 10 * 60,
      path: "/",
      sameSite: "lax" as const,
      secure
    };
    redirectResponse.cookies.set(
      getOidcStateCookieName(),
      state,
      sharedCookieOptions
    );
    redirectResponse.cookies.set(
      getOidcNonceCookieName(),
      nonce,
      sharedCookieOptions
    );
    redirectResponse.cookies.set(
      getOidcCodeVerifierCookieName(),
      codeVerifier,
      sharedCookieOptions
    );
    return redirectResponse;
  } catch (error) {
    logServerDiagnostic("oidc_authorization_url_failed", {
      path: "/auth/oidc/authorization-url",
      errorClass: error instanceof Error ? error.name : "unknown"
    });
    return redirectTo("/login?error=oidc-start");
  }
}
