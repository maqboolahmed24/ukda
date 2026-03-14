import type {
  ServiceReadinessPayload,
  ServiceUnavailablePayload
} from "@ukde/contracts";

import { getServiceHealth, getServiceReadiness } from "../lib/system";

function getReadinessTone(
  status:
    | ServiceReadinessPayload["status"]
    | ServiceUnavailablePayload["status"]
): "success" | "warning" {
  return status === "READY" ? "success" : "warning";
}

export async function ServiceStatusCard() {
  const [health, readiness] = await Promise.all([
    getServiceHealth(),
    getServiceReadiness()
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
