import { NextRequest, NextResponse } from "next/server";

import { resolveApiOrigins } from "../../../lib/bootstrap-content";
import {
  getCsrfCookieName,
  getSessionCookieName
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
  const sessionToken =
    request.cookies.get(getSessionCookieName())?.value ?? null;
  const csrfCookie = request.cookies.get(getCsrfCookieName())?.value ?? null;
  let csrfToken: string | null = null;
  try {
    const formData = await request.formData();
    const csrfFormValue = formData.get("csrf_token");
    csrfToken = typeof csrfFormValue === "string" ? csrfFormValue : null;
  } catch {
    // Requests without form payload should fail CSRF validation.
  }

  if (!sessionToken) {
    return redirectTo("/login");
  }
  if (!csrfCookie || !csrfToken || csrfCookie !== csrfToken) {
    return NextResponse.json(
      { detail: "CSRF token validation failed." },
      { status: 403 }
    );
  }

  const { internalOrigin } = resolveApiOrigins();
  const traceHeaders = await buildApiTraceHeaders();
  const redirectResponse = redirectTo("/login");
  redirectResponse.cookies.delete(getSessionCookieName());
  redirectResponse.cookies.delete(getCsrfCookieName());
  try {
    await fetch(`${internalOrigin}/auth/logout`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${sessionToken}`,
        "X-CSRF-Token": csrfToken,
        ...traceHeaders
      },
      cache: "no-store"
    });
  } catch (error) {
    logServerDiagnostic("logout_api_failed", {
      path: "/auth/logout",
      errorClass: error instanceof Error ? error.name : "unknown"
    });
    return redirectResponse;
  }

  return redirectResponse;
}
