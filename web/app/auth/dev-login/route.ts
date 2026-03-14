import type { SessionIssueResponse } from "@ukde/contracts";
import { NextRequest, NextResponse } from "next/server";

import { resolveApiOrigins } from "../../../lib/bootstrap-content";
import { revalidateAfterMutation } from "../../../lib/data/invalidation";
import {
  getCsrfCookieName,
  getSessionCookieName,
  shouldUseSecureCookies
} from "../../../lib/auth/session";
import {
  buildApiTraceHeaders,
  logServerDiagnostic
} from "../../../lib/telemetry";

function redirectTo(path: string, status = 307): NextResponse {
  return new NextResponse(null, {
    status,
    headers: {
      Location: path
    }
  });
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const seedKey = formData.get("seed_key");
  if (!seedKey || typeof seedKey !== "string") {
    return redirectTo("/login?error=dev-seed");
  }

  const { internalOrigin } = resolveApiOrigins();
  const traceHeaders = await buildApiTraceHeaders();
  try {
    const response = await fetch(`${internalOrigin}/auth/dev/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...traceHeaders
      },
      body: JSON.stringify({
        seed_key: seedKey
      }),
      cache: "no-store"
    });

    if (!response.ok) {
      logServerDiagnostic("dev_login_failed", {
        path: "/auth/dev/login",
        status: response.status
      });
      return redirectTo("/login?error=dev-login");
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
    revalidateAfterMutation("auth.login");
    return redirectResponse;
  } catch (error) {
    logServerDiagnostic("dev_login_failed", {
      path: "/auth/dev/login",
      errorClass: error instanceof Error ? error.name : "unknown"
    });
    return redirectTo("/login?error=dev-login");
  }
}
