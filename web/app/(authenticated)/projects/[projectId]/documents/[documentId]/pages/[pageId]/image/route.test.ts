import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ProjectDocumentPageDetail } from "@ukde/contracts";

const mocks = vi.hoisted(() => ({
  readSessionToken: vi.fn(),
  resolveApiOrigins: vi.fn(),
  isBrowserRegressionFixtureMode: vi.fn(),
  resolveBrowserRegressionApiResult: vi.fn(),
  buildApiTraceHeaders: vi.fn(),
  logServerDiagnostic: vi.fn()
}));

vi.mock("../../../../../../../../../lib/auth/cookies", () => ({
  readSessionToken: mocks.readSessionToken
}));

vi.mock("../../../../../../../../../lib/bootstrap-content", () => ({
  resolveApiOrigins: mocks.resolveApiOrigins
}));

vi.mock(
  "../../../../../../../../../lib/data/browser-regression-fixtures",
  () => ({
    isBrowserRegressionFixtureMode: mocks.isBrowserRegressionFixtureMode,
    resolveBrowserRegressionApiResult: mocks.resolveBrowserRegressionApiResult
  })
);

vi.mock("../../../../../../../../../lib/telemetry", () => ({
  buildApiTraceHeaders: mocks.buildApiTraceHeaders,
  logServerDiagnostic: mocks.logServerDiagnostic
}));

import { GET } from "./route";

const FIXTURE_PAGE_DETAIL: ProjectDocumentPageDetail = {
  id: "page-1",
  documentId: "doc-1",
  pageIndex: 0,
  width: 1000,
  height: 1400,
  dpi: 300,
  sourceWidth: 1000,
  sourceHeight: 1400,
  sourceDpi: 300,
  sourceColorMode: "GRAY",
  status: "READY",
  failureReason: null,
  viewerRotation: 0,
  createdAt: "2026-03-13T09:00:00.000Z",
  updatedAt: "2026-03-13T09:00:00.000Z",
  derivedImageAvailable: true,
  thumbnailAvailable: true
};

function buildImageRequest(options?: {
  ifNoneMatch?: string;
  variant?: "full" | "thumb";
}): Request {
  const url = new URL(
    "https://ukde.test/projects/project-1/documents/doc-1/pages/page-1/image"
  );
  if (options?.variant) {
    url.searchParams.set("variant", options.variant);
  }
  const headers = new Headers();
  if (options?.ifNoneMatch) {
    headers.set("if-none-match", options.ifNoneMatch);
  }
  return new Request(url, { method: "GET", headers });
}

const routeContext = {
  params: Promise.resolve({
    projectId: "project-1",
    documentId: "doc-1",
    pageId: "page-1"
  })
};

describe("document page image proxy route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSessionToken.mockResolvedValue("session-token");
    mocks.resolveApiOrigins.mockReturnValue({ internalOrigin: "http://127.0.0.1:8000" });
    mocks.isBrowserRegressionFixtureMode.mockReturnValue(true);
    mocks.resolveBrowserRegressionApiResult.mockReturnValue({
      ok: true,
      status: 200,
      data: FIXTURE_PAGE_DETAIL
    });
    mocks.buildApiTraceHeaders.mockResolvedValue({});
    mocks.logServerDiagnostic.mockReturnValue(undefined);
  });

  it("returns 401 when session is missing", async () => {
    mocks.readSessionToken.mockResolvedValue(null);

    const response = await GET(buildImageRequest(), routeContext);

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      detail: "Authentication is required."
    });
  });

  it("serves fixture image bytes with secure headers", async () => {
    const response = await GET(buildImageRequest({ variant: "full" }), routeContext);

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe(
      "private, no-cache, max-age=0, must-revalidate"
    );
    expect(response.headers.get("content-type")).toBe("image/png");
    expect(response.headers.get("x-content-type-options")).toBe("nosniff");
    expect(response.headers.get("cross-origin-resource-policy")).toBe(
      "same-origin"
    );
    expect(response.headers.get("vary")).toBe("Authorization");
    expect(response.headers.get("content-disposition")).toBeNull();
    expect(response.headers.get("etag")).toBe('"fixture-doc-1-page-1-full"');

    const body = await response.arrayBuffer();
    expect(body.byteLength).toBeGreaterThan(0);
  });

  it("returns 304 when If-None-Match matches the fixture etag", async () => {
    const response = await GET(
      buildImageRequest({ variant: "thumb", ifNoneMatch: '"fixture-doc-1-page-1-thumb"' }),
      routeContext
    );

    expect(response.status).toBe(304);
    expect(response.headers.get("etag")).toBe('"fixture-doc-1-page-1-thumb"');
    expect(response.headers.get("cache-control")).toBe(
      "private, no-cache, max-age=0, must-revalidate"
    );
    expect(response.headers.get("vary")).toBe("Authorization");
    const body = await response.arrayBuffer();
    expect(body.byteLength).toBe(0);
  });

  it("fails closed when page metadata says full image is not ready", async () => {
    mocks.resolveBrowserRegressionApiResult.mockReturnValue({
      ok: true,
      status: 200,
      data: {
        ...FIXTURE_PAGE_DETAIL,
        derivedImageAvailable: false
      }
    });

    const response = await GET(buildImageRequest({ variant: "full" }), routeContext);

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toEqual({
      detail: "Page image is not ready."
    });
  });
});
