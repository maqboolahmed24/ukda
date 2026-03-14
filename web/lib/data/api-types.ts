export type ApiErrorCode =
  | "AUTH_REQUIRED"
  | "FORBIDDEN"
  | "NOT_FOUND"
  | "VALIDATION"
  | "CONFLICT"
  | "NETWORK"
  | "SERVER"
  | "UNKNOWN";

export interface ApiError {
  code: ApiErrorCode;
  detail: string;
  retryable: boolean;
}

export interface ApiResult<T> {
  ok: boolean;
  status: number;
  data?: T;
  detail?: string;
  error?: ApiError;
}

export function resolveErrorCode(status: number): ApiErrorCode {
  if (status === 401) {
    return "AUTH_REQUIRED";
  }
  if (status === 403) {
    return "FORBIDDEN";
  }
  if (status === 404) {
    return "NOT_FOUND";
  }
  if (status === 409) {
    return "CONFLICT";
  }
  if (status === 422 || status === 400) {
    return "VALIDATION";
  }
  if (status >= 500) {
    return "SERVER";
  }
  return "UNKNOWN";
}

export function resolveRetryable(code: ApiErrorCode, method: string): boolean {
  if (code === "NETWORK" || code === "SERVER") {
    return method.toUpperCase() === "GET";
  }
  return false;
}

export function normalizeDetail(payload: unknown): string {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }
  return "Request failed.";
}

export function normalizeMethod(value?: string): string {
  return value?.toUpperCase() ?? "GET";
}

