import { NextResponse } from "next/server";
import type { ProjectDocumentPageDetail } from "@ukde/contracts";

import { readSessionToken } from "../../../../../../../../../lib/auth/cookies";
import { resolveApiOrigins } from "../../../../../../../../../lib/bootstrap-content";
import {
  isBrowserRegressionFixtureMode,
  resolveBrowserRegressionApiResult
} from "../../../../../../../../../lib/data/browser-regression-fixtures";
import {
  buildApiTraceHeaders,
  logServerDiagnostic
} from "../../../../../../../../../lib/telemetry";

const IMAGE_VARIANTS = new Set([
  "full",
  "thumb",
  "preprocessed_gray",
  "preprocessed_bin"
]);
const PAGE_IMAGE_DEFAULT_CACHE_CONTROL =
  "private, no-cache, max-age=0, must-revalidate";
const PAGE_IMAGE_DEFAULT_VARY = "Authorization";
const FIXTURE_TRANSPARENT_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAJUb3uoAAAAASUVORK5CYII=",
  "base64"
);
const FIXTURE_TRANSPARENT_JPEG = Buffer.from(
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBAPEA8QDw8PEA8PDw8PDw8PFREWFhURFRUYHSggGBolGxUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OFQ8PFSsdFR0tKy0tKy0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAQMBIgACEQEDEQH/xAAZAAADAQEBAAAAAAAAAAAAAAAABQYDBAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH8xwD/xAAaEAABBQEAAAAAAAAAAAAAAAAAAQIDERQh/9oACAEBAAEFAjNts2mq2f/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQMBAT8BP//EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQIBAT8BP//Z",
  "base64"
);

function resolveVariant(
  raw: string | null
): "full" | "thumb" | "preprocessed_gray" | "preprocessed_bin" {
  if (raw && IMAGE_VARIANTS.has(raw)) {
    return raw as "full" | "thumb" | "preprocessed_gray" | "preprocessed_bin";
  }
  return "full";
}

function formatEtag(seed: string): string {
  return `"${seed.replace(/"/g, "")}"`;
}

function ifNoneMatchMatches(ifNoneMatch: string | null, etag: string): boolean {
  if (!ifNoneMatch) {
    return false;
  }
  const candidate = etag.trim().replace(/^W\//, "").replace(/^"|"$/g, "");
  const tokens = ifNoneMatch.split(",");
  for (const rawToken of tokens) {
    const token = rawToken.trim();
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
}) {
  const headers: Record<string, string> = {
    "Cache-Control": options.cacheControl ?? PAGE_IMAGE_DEFAULT_CACHE_CONTROL,
    "Cross-Origin-Resource-Policy": "same-origin",
    Vary: options.vary ?? PAGE_IMAGE_DEFAULT_VARY,
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
    if (
      typeof payload.detail === "string" &&
      payload.detail.trim().length > 0
    ) {
      return payload.detail;
    }
  } catch {}
  return "Document page image request failed.";
}

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  context: {
    params: Promise<{
      projectId: string;
      documentId: string;
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

  const { projectId, documentId, pageId } = await context.params;
  const requestUrl = new URL(request.url);
  const variant = resolveVariant(requestUrl.searchParams.get("variant"));
  const runId = requestUrl.searchParams.get("runId")?.trim() || null;
  const ifNoneMatch = request.headers.get("if-none-match");

  if (isBrowserRegressionFixtureMode()) {
    const fixturePageResult =
      resolveBrowserRegressionApiResult<ProjectDocumentPageDetail>({
        authToken: sessionToken,
        method: "GET",
        path: `/projects/${projectId}/documents/${documentId}/pages/${pageId}`
      });
    if (
      !fixturePageResult ||
      !fixturePageResult.ok ||
      !fixturePageResult.data
    ) {
      return NextResponse.json(
        {
          detail:
            fixturePageResult?.detail ?? "Document page image request failed."
        },
        { status: fixturePageResult?.status ?? 503 }
      );
    }

    if (variant === "full" && !fixturePageResult.data.derivedImageAvailable) {
      return NextResponse.json(
        { detail: "Page image is not ready." },
        { status: 409 }
      );
    }
    if (variant === "thumb" && !fixturePageResult.data.thumbnailAvailable) {
      return NextResponse.json(
        { detail: "Page thumbnail is not ready." },
        { status: 409 }
      );
    }

    const fixtureEtag = formatEtag(
      `fixture-${documentId}-${pageId}-${variant}`
    );
    const fixtureHeaders = resolveSecureHeaders({
      cacheControl: PAGE_IMAGE_DEFAULT_CACHE_CONTROL,
      contentType: variant === "thumb" ? "image/jpeg" : "image/png",
      etag: fixtureEtag
    });
    if (ifNoneMatchMatches(ifNoneMatch, fixtureEtag)) {
      return new NextResponse(null, {
        status: 304,
        headers: resolveSecureHeaders({
          cacheControl: PAGE_IMAGE_DEFAULT_CACHE_CONTROL,
          etag: fixtureEtag
        })
      });
    }
    return new NextResponse(
      variant === "thumb" ? FIXTURE_TRANSPARENT_JPEG : FIXTURE_TRANSPARENT_PNG,
      {
        status: 200,
        headers: fixtureHeaders
      }
    );
  }

  const { internalOrigin } = resolveApiOrigins();
  const traceHeaders = await buildApiTraceHeaders();
  const runIdQuery = runId ? `&runId=${encodeURIComponent(runId)}` : "";
  const upstreamPath = `/projects/${projectId}/documents/${documentId}/pages/${pageId}/image?variant=${variant}${runIdQuery}`;
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
    logServerDiagnostic("viewer_page_image_proxy_fetch_failed", {
      errorClass: error instanceof Error ? error.name : "unknown",
      path: upstreamPath
    });
    return NextResponse.json(
      { detail: "Document page image API is unavailable." },
      { status: 503 }
    );
  }

  const responseHeaders = resolveSecureHeaders({
    cacheControl: upstreamResponse.headers.get("cache-control"),
    contentType:
      upstreamResponse.headers.get("content-type") ??
      (variant === "thumb" ? "image/jpeg" : "image/png"),
    etag: upstreamResponse.headers.get("etag"),
    vary: upstreamResponse.headers.get("vary")
  });

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

  const content = await upstreamResponse.arrayBuffer();
  return new NextResponse(content, {
    status: upstreamResponse.status,
    headers: responseHeaders
  });
}
