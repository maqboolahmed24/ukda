import { beforeEach, describe, expect, it, vi } from "vitest";

const readSessionTokenMock = vi.fn<() => Promise<string | null>>();
const resolveApiOriginsMock = vi.fn(() => ({
  internalOrigin: "http://api.internal",
  publicOrigin: "http://api.internal"
}));
const buildApiTraceHeadersMock = vi.fn(() =>
  Promise.resolve({ "X-Request-ID": "req-test" })
);
const logServerDiagnosticMock = vi.fn();

vi.mock("../auth/cookies", () => ({
  readSessionToken: () => readSessionTokenMock()
}));

vi.mock("../bootstrap-content", () => ({
  resolveApiOrigins: () => resolveApiOriginsMock()
}));

vi.mock("../telemetry", () => ({
  buildApiTraceHeaders: () => buildApiTraceHeadersMock(),
  logServerDiagnostic: (...args: unknown[]) => logServerDiagnosticMock(...args)
}));

import { requestServerApi } from "./api-client";
import { requestBrowserApi } from "./browser-api-client";

describe("typed API client", () => {
  beforeEach(() => {
    readSessionTokenMock.mockReset();
    resolveApiOriginsMock.mockClear();
    buildApiTraceHeadersMock.mockClear();
    logServerDiagnosticMock.mockClear();
    vi.restoreAllMocks();
  });

  it("fails closed when auth is required and no session token exists", async () => {
    readSessionTokenMock.mockResolvedValueOnce(null);

    const result = await requestServerApi<{ ok: true }>({
      path: "/projects"
    });

    expect(result.ok).toBe(false);
    expect(result.status).toBe(401);
    expect(result.error?.code).toBe("AUTH_REQUIRED");
  });

  it("normalizes backend errors into typed API error values", async () => {
    readSessionTokenMock.mockResolvedValueOnce("token-1");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Forbidden route." }), {
          status: 403,
          headers: { "Content-Type": "application/json" }
        })
      );

    const result = await requestServerApi<{ ok: true }>({
      path: "/admin/security"
    });

    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe("FORBIDDEN");
    expect(result.detail).toBe("Forbidden route.");
  });

  it("supports accepted non-2xx statuses when a route contract allows them", async () => {
    const readinessPayload = {
      checks: [],
      environment: "dev",
      service: "api",
      status: "NOT_READY",
      timestamp: "2026-03-13T00:00:00.000Z",
      version: "test"
    };
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(readinessPayload), {
          status: 503,
          headers: { "Content-Type": "application/json" }
        })
      );

    const result = await requestServerApi<typeof readinessPayload>({
      allowStatuses: [503],
      cacheClass: "public-status",
      path: "/readyz",
      requireAuth: false
    });

    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(result.ok).toBe(true);
    expect(result.status).toBe(503);
    expect(result.data?.status).toBe("NOT_READY");
  });

  it("returns normalized network errors in browser-safe requests", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("network down"));

    const result = await requestBrowserApi<{ value: string }>({
      path: "/projects/project-1/jobs/job-1/status"
    });

    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe("NETWORK");
    expect(result.error?.retryable).toBe(true);
  });
});
