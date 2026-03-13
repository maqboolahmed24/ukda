import Link from "next/link";

import { requirePlatformRole } from "../../../../lib/auth/session";
import { getOperationsOverview } from "../../../../lib/operations";

export const dynamic = "force-dynamic";

export default async function AdminOperationsOverviewPage() {
  await requirePlatformRole(["ADMIN"]);
  const overviewResult = await getOperationsOverview();

  return (
    <main className="homeLayout">
      <section
        className="sectionCard ukde-panel"
        aria-labelledby="operations-title"
      >
        <p className="ukde-eyebrow">Platform operations</p>
        <h1 id="operations-title">Operations overview</h1>
        <p className="ukde-muted">
          Privacy-safe metrics, alert posture, and telemetry export boundaries.
        </p>
        <div className="buttonRow">
          <Link className="secondaryButton" href="/admin/operations/slos">
            SLO targets
          </Link>
          <Link className="secondaryButton" href="/admin/operations/alerts">
            Alerts
          </Link>
          <Link className="secondaryButton" href="/admin/operations/timelines">
            Timelines
          </Link>
          <Link className="secondaryButton" href="/admin">
            Back to admin
          </Link>
        </div>
      </section>

      {!overviewResult.ok || !overviewResult.data ? (
        <section className="sectionCard ukde-panel">
          <p className="ukde-muted">
            Operations overview unavailable:{" "}
            {overviewResult.detail ?? "unknown"}
          </p>
        </section>
      ) : (
        <>
          <section className="sectionCard ukde-panel">
            <div className="ukde-grid" data-columns="2">
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Requests</p>
                <h3>{overviewResult.data.requestCount}</h3>
                <p className="ukde-muted">
                  Error rate {overviewResult.data.errorRatePercent.toFixed(3)}%
                </p>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Latency p95</p>
                <h3>
                  {overviewResult.data.p95LatencyMs === null
                    ? "n/a"
                    : `${overviewResult.data.p95LatencyMs.toFixed(2)} ms`}
                </h3>
                <p className="ukde-muted">
                  Uptime {overviewResult.data.uptimeSeconds}s
                </p>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Auth outcomes</p>
                <h3>
                  {overviewResult.data.authSuccessCount}/
                  {overviewResult.data.authFailureCount}
                </h3>
                <p className="ukde-muted">success / failure</p>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Audit writes</p>
                <h3>
                  {overviewResult.data.auditWriteSuccessCount}/
                  {overviewResult.data.auditWriteFailureCount}
                </h3>
                <p className="ukde-muted">success / failure</p>
              </article>
            </div>
          </section>

          <section className="sectionCard ukde-panel">
            <p className="ukde-eyebrow">Readiness telemetry</p>
            <p className="ukde-muted">
              DB checks: {overviewResult.data.readinessDbChecks}, failures:{" "}
              {overviewResult.data.readinessDbFailures}, latest latency:{" "}
              {overviewResult.data.readinessDbLastLatencyMs === null
                ? "n/a"
                : `${overviewResult.data.readinessDbLastLatencyMs.toFixed(2)} ms`}
              .
            </p>
            <p className="ukde-muted">
              Queue depth source: {overviewResult.data.queueDepthSource}.{" "}
              {overviewResult.data.queueDepthDetail}
            </p>
          </section>

          <section className="sectionCard ukde-panel">
            <p className="ukde-eyebrow">Telemetry exporter</p>
            <div className="auditIntegrityRow">
              <span className="ukde-badge">
                {overviewResult.data.exporter.mode}
              </span>
              <span className="ukde-badge">
                {overviewResult.data.exporter.state}
              </span>
              {overviewResult.data.exporter.endpoint ? (
                <span className="ukde-muted">
                  {overviewResult.data.exporter.endpoint}
                </span>
              ) : null}
            </div>
            <p className="ukde-muted">{overviewResult.data.exporter.detail}</p>
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Top routes</h2>
            {overviewResult.data.topRoutes.length === 0 ? (
              <p className="ukde-muted">
                No route telemetry has been collected yet.
              </p>
            ) : (
              <div className="auditTableWrap">
                <table className="auditTable">
                  <thead>
                    <tr>
                      <th>Route</th>
                      <th>Method</th>
                      <th>Requests</th>
                      <th>Errors</th>
                      <th>Avg latency</th>
                      <th>p95 latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overviewResult.data.topRoutes.map((route) => (
                      <tr key={`${route.routeTemplate}-${route.method}`}>
                        <td>{route.routeTemplate}</td>
                        <td>{route.method}</td>
                        <td>{route.requestCount}</td>
                        <td>{route.errorCount}</td>
                        <td>
                          {route.averageLatencyMs === null
                            ? "n/a"
                            : `${route.averageLatencyMs.toFixed(2)} ms`}
                        </td>
                        <td>
                          {route.p95LatencyMs === null
                            ? "n/a"
                            : `${route.p95LatencyMs.toFixed(2)} ms`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
