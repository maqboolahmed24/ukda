import { randomBytes } from "node:crypto";

import { headers } from "next/headers";

const TRACEPARENT_PATTERN = /^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$/i;
const REQUEST_ID_PATTERN = /^[A-Za-z0-9._:-]{8,128}$/;
const SENSITIVE_KEY_FRAGMENTS = [
  "token",
  "password",
  "secret",
  "cookie",
  "authorization",
  "raw",
  "content",
  "bytes"
];

function randomHex(bytes: number): string {
  return randomBytes(bytes).toString("hex");
}

function isSensitiveKey(key: string): boolean {
  const lowered = key.toLowerCase();
  return SENSITIVE_KEY_FRAGMENTS.some((fragment) => lowered.includes(fragment));
}

function sanitizeLogPayload(
  payload: Record<string, unknown>
): Record<string, unknown> {
  const sanitized: Record<string, unknown> = {};
  for (const [rawKey, rawValue] of Object.entries(payload)) {
    const key = rawKey.trim().slice(0, 64);
    if (!key || isSensitiveKey(key)) {
      continue;
    }
    if (typeof rawValue === "string") {
      sanitized[key] = rawValue.replace(/\s+/g, " ").trim().slice(0, 512);
      continue;
    }
    if (typeof rawValue === "number" || typeof rawValue === "boolean") {
      sanitized[key] = rawValue;
      continue;
    }
    if (rawValue === null || rawValue === undefined) {
      sanitized[key] = null;
      continue;
    }
    sanitized[key] = String(rawValue).replace(/\s+/g, " ").trim().slice(0, 512);
  }
  return sanitized;
}

async function readIncomingHeaders(): Promise<{
  traceparent: string | null;
  requestId: string | null;
}> {
  try {
    const requestHeaders = await headers();
    return {
      traceparent: requestHeaders.get("traceparent"),
      requestId: requestHeaders.get("x-request-id")
    };
  } catch {
    return {
      traceparent: null,
      requestId: null
    };
  }
}

export async function buildApiTraceHeaders(): Promise<Record<string, string>> {
  const incoming = await readIncomingHeaders();
  const traceparentMatch = incoming.traceparent
    ? TRACEPARENT_PATTERN.exec(incoming.traceparent.trim())
    : null;
  const traceId = traceparentMatch?.[1]?.toLowerCase() ?? randomHex(16);
  const traceFlags = traceparentMatch?.[3]?.toLowerCase() ?? "01";
  const spanId = randomHex(8);

  const headersToForward: Record<string, string> = {
    traceparent: `00-${traceId}-${spanId}-${traceFlags}`
  };
  if (
    incoming.requestId &&
    REQUEST_ID_PATTERN.test(incoming.requestId.trim())
  ) {
    headersToForward["X-Request-ID"] = incoming.requestId.trim();
  }
  return headersToForward;
}

export function logServerDiagnostic(
  event: string,
  payload: Record<string, unknown>
): void {
  const message = {
    event,
    payload: sanitizeLogPayload(payload)
  };
  console.error(`[ukde.telemetry] ${JSON.stringify(message)}`);
}
