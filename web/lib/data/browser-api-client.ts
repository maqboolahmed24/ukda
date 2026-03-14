import type { QueryCacheClass } from "./cache-policy";
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

export interface BrowserApiRequestOptions {
  allowStatuses?: number[];
  body?: BodyInit | null;
  cacheClass?: QueryCacheClass;
  credentials?: RequestCredentials;
  expectNoContent?: boolean;
  headers?: HeadersInit;
  method?: string;
  origin?: string;
  path: string;
  queryKey?: QueryKey;
  signal?: AbortSignal;
}

export type { ApiError, ApiErrorCode, ApiResult } from "./api-types";

async function parseJsonPayload(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

function resolveScopedPath(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return path.startsWith("/") ? path : `/${path}`;
}

export async function requestBrowserApi<T>(
  options: BrowserApiRequestOptions
): Promise<ApiResult<T>> {
  const method = normalizeMethod(options.method);
  const policy = queryCachePolicy[options.cacheClass ?? "operations-live"];
  const path = resolveScopedPath(options.path);
  const baseOrigin = options.origin?.replace(/\/+$/, "") ?? "";
  const url = path.startsWith("http") ? path : `${baseOrigin}${path}`;

  const headers = new Headers(options.headers);
  if (options.queryKey) {
    headers.set("X-UKDE-Query-Key", serializeQueryKey(options.queryKey));
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      body: options.body,
      headers,
      credentials: options.credentials ?? "same-origin",
      signal: options.signal,
      cache: policy.fetchCache
    });
  } catch {
    return {
      ok: false,
      status: 503,
      detail: "API is unavailable.",
      error: {
        code: "NETWORK",
        detail: "API is unavailable.",
        retryable: resolveRetryable("NETWORK", method)
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
              retryable: resolveRetryable(resolveErrorCode(response.status), method)
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
        retryable: resolveRetryable(code, method)
      }
    };
  }

  return {
    ok: true,
    status: response.status,
    data: parsed as T
  };
}

