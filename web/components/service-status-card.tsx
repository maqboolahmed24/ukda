import type {
  ServiceHealthPayload,
  ServiceReadinessPayload,
  ServiceUnavailablePayload
} from "@ukde/contracts";

import { resolveApiOrigins } from "../lib/bootstrap-content";
import { buildApiTraceHeaders, logServerDiagnostic } from "../lib/telemetry";

const UNREACHABLE_PAYLOAD: ServiceUnavailablePayload = {
  service: "api",
  status: "UNREACHABLE",
  environment: "dev",
  version: "bootstrap",
  timestamp: new Date(0).toISOString(),
  detail: "API has not been contacted yet."
};

async function fetchHealth(
  baseUrl: string
): Promise<ServiceHealthPayload | ServiceUnavailablePayload> {
  const traceHeaders = await buildApiTraceHeaders();
  try {
    const response = await fetch(`${baseUrl}/healthz`, {
      cache: "no-store",
      headers: traceHeaders
    });
    if (!response.ok) {
      return {
        ...UNREACHABLE_PAYLOAD,
        detail: `Health check returned ${response.status}.`
      };
    }
    return (await response.json()) as ServiceHealthPayload;
  } catch {
    logServerDiagnostic("health_fetch_failed", {
      path: "/healthz",
      baseUrl
    });
    return {
      ...UNREACHABLE_PAYLOAD,
      detail: "Could not connect to /healthz."
    };
  }
}

async function fetchReadiness(
  baseUrl: string
): Promise<ServiceReadinessPayload | ServiceUnavailablePayload> {
  const traceHeaders = await buildApiTraceHeaders();
  try {
    const response = await fetch(`${baseUrl}/readyz`, {
      cache: "no-store",
      headers: traceHeaders
    });
    if (!response.ok && response.status !== 503) {
      return {
        ...UNREACHABLE_PAYLOAD,
        detail: `Readiness check returned ${response.status}.`
      };
    }
    return (await response.json()) as ServiceReadinessPayload;
  } catch {
    logServerDiagnostic("readiness_fetch_failed", {
      path: "/readyz",
      baseUrl
    });
    return {
      ...UNREACHABLE_PAYLOAD,
      detail: "Could not connect to /readyz."
    };
  }
}

function getReadinessTone(
  status:
    | ServiceReadinessPayload["status"]
    | ServiceUnavailablePayload["status"]
): "success" | "warning" {
  return status === "READY" ? "success" : "warning";
}

export async function ServiceStatusCard() {
  const { internalOrigin } = resolveApiOrigins();
  const [health, readiness] = await Promise.all([
    fetchHealth(internalOrigin),
    fetchReadiness(internalOrigin)
  ]);

  return (
    <section aria-live="polite" className="statusCard">
      <div
        className="ukde-badge"
        data-tone={health.status === "OK" ? "success" : "warning"}
      >
        Liveness {health.status}
      </div>
      <h2>
        {readiness.status === "READY"
          ? "Service status: OK"
          : "Service status: NOT READY"}
      </h2>
      <p className="ukde-muted">
        API environment <strong>{health.environment}</strong>, version{" "}
        <strong>{health.version}</strong>.
      </p>
      <div className="ukde-grid" data-columns="2">
        <div className="statusCheck">
          <strong>Health</strong>
          <span>{health.status}</span>
        </div>
        <div className="statusCheck">
          <strong>Readiness</strong>
          <span className={`tone-${getReadinessTone(readiness.status)}`}>
            {readiness.status}
          </span>
        </div>
      </div>
      {"checks" in readiness ? (
        <ul className="statusChecks">
          {readiness.checks.map((check) => (
            <li key={check.name}>
              <span>{check.name}</span>
              <span>{check.status}</span>
            </li>
          ))}
        </ul>
      ) : (
        <code className="statusDetail">{readiness.detail}</code>
      )}
      <code className="statusDetail">{health.timestamp}</code>
    </section>
  );
}
