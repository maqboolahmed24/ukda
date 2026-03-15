import { readSessionToken } from "../auth/cookies";
import { resolveApiOrigins } from "../bootstrap-content";
import { buildApiTraceHeaders, logServerDiagnostic } from "../telemetry";
import type { QueryCacheClass } from "./cache-policy";
import { resolveBrowserRegressionApiResult } from "./browser-regression-fixtures";
import { queryCachePolicy } from "./cache-policy";
import {
  type ApiResult,
  normalizeDetail,
  normalizeMethod,
  resolveErrorCode,
  resolveRetryable
} from "./api-types";
import type { QueryKey } from "./query-keys";
import { serializeQueryKey } from "./query-keys";

export type { ApiError, ApiErrorCode, ApiResult } from "./api-types";

export interface ServerApiRequestOptions {
  allowStatuses?: number[];
  body?: BodyInit | null;
  cacheClass?: QueryCacheClass;
  expectNoContent?: boolean;
  headers?: HeadersInit;
  method?: string;
  path: string;
  queryKey?: QueryKey;
  requireAuth?: boolean;
  signal?: AbortSignal;
}

async function parseJsonPayload(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

async function requestUkdeApi<T>(
  url: string,
  options: {
    allowStatuses?: number[];
    authToken?: string | null;
    body?: BodyInit | null;
    cacheClass: QueryCacheClass;
    expectNoContent: boolean;
    headers?: HeadersInit;
    method: string;
    path: string;
    queryKey?: QueryKey;
    requireAuth: boolean;
    signal?: AbortSignal;
  }
): Promise<ApiResult<T>> {
  const policy = queryCachePolicy[options.cacheClass];

  if (options.requireAuth && !options.authToken) {
    return {
      ok: false,
      status: 401,
      detail: "Authentication is required.",
      error: {
        code: "AUTH_REQUIRED",
        detail: "Authentication is required.",
        retryable: false
      }
    };
  }

  const fixtureResult = resolveBrowserRegressionApiResult<T>({
    authToken: options.authToken,
    body: options.body,
    method: options.method,
    path: options.path
  });
  if (fixtureResult) {
    return fixtureResult;
  }

  const traceHeaders = await buildApiTraceHeaders();
  const headers = new Headers(options.headers);
  for (const [key, value] of Object.entries(traceHeaders)) {
    headers.set(key, value);
  }
  if (options.authToken) {
    headers.set("Authorization", `Bearer ${options.authToken}`);
  }
  if (options.queryKey) {
    headers.set("X-UKDE-Query-Key", serializeQueryKey(options.queryKey));
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method,
      body: options.body,
      headers,
      signal: options.signal,
      cache: policy.fetchCache
    });
  } catch (error) {
    logServerDiagnostic("web_api_fetch_failed", {
      cacheClass: policy.cacheClass,
      errorClass: error instanceof Error ? error.name : "unknown",
      method: options.method,
      path: options.path
    }, { level: "warn" });
    return {
      ok: false,
      status: 503,
      detail: "API is unavailable.",
      error: {
        code: "NETWORK",
        detail: "API is unavailable.",
        retryable: resolveRetryable("NETWORK", options.method)
      }
    };
  }

  if (options.expectNoContent || response.status === 204) {
    return {
      ok: response.ok,
      status: response.status,
      ...(response.ok
        ? {}
        : {
            detail: "Request failed.",
            error: {
              code: resolveErrorCode(response.status),
              detail: "Request failed.",
              retryable: resolveRetryable(
                resolveErrorCode(response.status),
                options.method
              )
            }
          })
    };
  }

  const parsed = await parseJsonPayload(response);
  if (
    !response.ok &&
    options.allowStatuses &&
    options.allowStatuses.includes(response.status)
  ) {
    return {
      ok: true,
      status: response.status,
      data: parsed as T
    };
  }

  if (!response.ok) {
    const code = resolveErrorCode(response.status);
    const detail = normalizeDetail(parsed);
    return {
      ok: false,
      status: response.status,
      detail,
      error: {
        code,
        detail,
        retryable: resolveRetryable(code, options.method)
      }
    };
  }

  return {
    ok: true,
    status: response.status,
    data: parsed as T
  };
}

function resolveScopedPath(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return path.startsWith("/") ? path : `/${path}`;
}

function resolveTokenDebugScope(token: string | null): string {
  if (!token) {
    return "anonymous";
  }
  return `${token.slice(0, 4)}…${token.slice(-4)}`;
}

export async function requestServerApi<T>(
  options: ServerApiRequestOptions
): Promise<ApiResult<T>> {
  const method = normalizeMethod(options.method);
  const requireAuth = options.requireAuth ?? true;
  const authToken = requireAuth ? await readSessionToken() : null;
  const { internalOrigin } = resolveApiOrigins();
  const path = resolveScopedPath(options.path);
  const url = path.startsWith("http") ? path : `${internalOrigin}${path}`;

  const result = await requestUkdeApi<T>(url, {
    authToken,
    allowStatuses: options.allowStatuses,
    body: options.body,
    cacheClass: options.cacheClass ?? "mutable-list",
    expectNoContent: options.expectNoContent ?? false,
    headers: options.headers,
    method,
    path,
    queryKey: options.queryKey,
    requireAuth,
    signal: options.signal
  });

  if (!result.ok && result.status >= 500) {
    logServerDiagnostic("web_api_server_error", {
      authScope: resolveTokenDebugScope(authToken),
      method,
      path,
      status: result.status
    }, { level: "warn" });
  }
  return result;
}
