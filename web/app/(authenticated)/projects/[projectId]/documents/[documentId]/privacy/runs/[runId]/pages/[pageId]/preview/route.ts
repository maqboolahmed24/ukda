import { NextResponse } from "next/server";

import { readSessionToken } from "../../../../../../../../../../../../lib/auth/cookies";
import { resolveApiOrigins } from "../../../../../../../../../../../../lib/bootstrap-content";
import {
  isBrowserRegressionFixtureMode,
  resolveBrowserRegressionApiResult
} from "../../../../../../../../../../../../lib/data/browser-regression-fixtures";
import { buildApiTraceHeaders, logServerDiagnostic } from "../../../../../../../../../../../../lib/telemetry";

const PREVIEW_DEFAULT_CACHE_CONTROL = "private, no-cache, max-age=0, must-revalidate";
const PREVIEW_DEFAULT_VARY = "Authorization";
const FIXTURE_PREVIEW_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAJUb3uoAAAAASUVORK5CYII=",
  "base64"
);

function formatEtag(seed: string): string {
  return `"${seed.replace(/"/g, "")}"`;
}

function ifNoneMatchMatches(ifNoneMatch: string | null, etag: string): boolean {
  if (!ifNoneMatch) {
    return false;
  }
  const candidate = etag.trim().replace(/^W\//, "").replace(/^"|"$/g, "");
  for (const raw of ifNoneMatch.split(",")) {
    const token = raw.trim();
    if (token === "*") {
      return true;
    }
    const normalized = token.replace(/^W\//, "").replace(/^"|"$/g, "");
    if (normalized === candidate) {
      return true;
    }
  }
  return false;
}

function resolveSecureHeaders(options: {
  cacheControl?: string | null;
  contentType?: string | null;
  etag?: string | null;
  vary?: string | null;
}): Record<string, string> {
  const headers: Record<string, string> = {
    "Cache-Control": options.cacheControl ?? PREVIEW_DEFAULT_CACHE_CONTROL,
    "Cross-Origin-Resource-Policy": "same-origin",
    Vary: options.vary ?? PREVIEW_DEFAULT_VARY,
    "X-Content-Type-Options": "nosniff"
  };
  if (options.contentType) {
    headers["Content-Type"] = options.contentType;
  }
  if (options.etag) {
    headers.ETag = options.etag;
  }
  return headers;
}

async function resolveErrorDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
      return payload.detail;
    }
  } catch {}
  return "Safeguarded preview request failed.";
}

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  context: {
    params: Promise<{
      projectId: string;
      documentId: string;
      runId: string;
      pageId: string;
    }>;
  }
) {
  const sessionToken = await readSessionToken();
  if (!sessionToken) {
    return NextResponse.json(
      { detail: "Authentication is required." },
      { status: 401 }
    );
  }

  const { projectId, documentId, runId, pageId } = await context.params;
  const ifNoneMatch = request.headers.get("if-none-match");

  if (isBrowserRegressionFixtureMode()) {
    const fixturePageResult = resolveBrowserRegressionApiResult({
      authToken: sessionToken,
      method: "GET",
      path: `/projects/${projectId}/documents/${documentId}/pages/${pageId}`
    });
    if (!fixturePageResult || !fixturePageResult.ok || !fixturePageResult.data) {
      return NextResponse.json(
        {
          detail:
            fixturePageResult?.detail ??
            "Safeguarded preview request failed."
        },
        { status: fixturePageResult?.status ?? 503 }
      );
    }

    const fixtureEtag = formatEtag(
      `fixture-redaction-preview-${documentId}-${runId}-${pageId}`
    );
    if (ifNoneMatchMatches(ifNoneMatch, fixtureEtag)) {
      return new NextResponse(null, {
        status: 304,
        headers: resolveSecureHeaders({
          cacheControl: PREVIEW_DEFAULT_CACHE_CONTROL,
          etag: fixtureEtag
        })
      });
    }

    return new NextResponse(FIXTURE_PREVIEW_PNG, {
      status: 200,
      headers: resolveSecureHeaders({
        cacheControl: PREVIEW_DEFAULT_CACHE_CONTROL,
        contentType: "image/png",
        etag: fixtureEtag
      })
    });
  }

  const { internalOrigin } = resolveApiOrigins();
  const traceHeaders = await buildApiTraceHeaders();
  const upstreamPath =
    `/projects/${projectId}/documents/${documentId}/redaction-runs/${runId}/pages/${pageId}/preview`;
  const upstreamHeaders: Record<string, string> = {
    Authorization: `Bearer ${sessionToken}`,
    ...traceHeaders
  };
  if (ifNoneMatch) {
    upstreamHeaders["If-None-Match"] = ifNoneMatch;
  }

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(`${internalOrigin}${upstreamPath}`, {
      method: "GET",
      cache: "no-store",
      headers: upstreamHeaders
    });
  } catch (error) {
    logServerDiagnostic("privacy_preview_proxy_fetch_failed", {
      errorClass: error instanceof Error ? error.name : "unknown",
      path: upstreamPath
    });
    return NextResponse.json(
      { detail: "Privacy preview API is unavailable." },
      { status: 503 }
    );
  }

  if (upstreamResponse.status === 304) {
    return new NextResponse(null, {
      status: 304,
      headers: resolveSecureHeaders({
        cacheControl: upstreamResponse.headers.get("cache-control"),
        etag: upstreamResponse.headers.get("etag"),
        vary: upstreamResponse.headers.get("vary")
      })
    });
  }

  if (!upstreamResponse.ok) {
    return NextResponse.json(
      { detail: await resolveErrorDetail(upstreamResponse) },
      { status: upstreamResponse.status }
    );
  }

  const payload = await upstreamResponse.arrayBuffer();
  return new NextResponse(payload, {
    status: upstreamResponse.status,
    headers: resolveSecureHeaders({
      cacheControl: upstreamResponse.headers.get("cache-control"),
      contentType: upstreamResponse.headers.get("content-type") ?? "image/png",
      etag: upstreamResponse.headers.get("etag"),
      vary: upstreamResponse.headers.get("vary")
    })
  });
}
