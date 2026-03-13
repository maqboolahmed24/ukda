import { ServiceStatusCard } from "../../components/service-status-card";
import { resolveApiOrigins } from "../../lib/bootstrap-content";

export default function HealthPage() {
  const { publicOrigin } = resolveApiOrigins();

  return (
    <main className="healthLayout">
      <section
        className="healthHeader ukde-panel"
        aria-labelledby="health-title"
      >
        <p className="ukde-eyebrow">Operational diagnostics</p>
        <h2 id="health-title">Browser-to-API health surface</h2>
        <p className="ukde-muted">
          This route reports live liveness and readiness signals from the API.
          It is intentionally operational, not a dashboard.
        </p>
        <div className="ukde-toolbar" aria-label="Health endpoints">
          <span className="ukde-badge">API {publicOrigin}</span>
          <span className="ukde-badge">/healthz</span>
          <span className="ukde-badge">/readyz</span>
        </div>
      </section>

      <ServiceStatusCard />
    </main>
  );
}
