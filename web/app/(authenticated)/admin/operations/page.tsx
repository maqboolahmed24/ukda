import { PageHeader } from "../../../../components/page-header";
import { requirePlatformRole } from "../../../../lib/auth/session";
import { getOperationsOverview } from "../../../../lib/operations";
import {
  adminCapacityTestsPath,
  adminOperationsAlertsPath,
  adminOperationsExportStatusPath,
  adminOperationsReadinessPath,
  adminOperationsSlosPath,
  adminOperationsTimelinesPath,
  adminRecoveryDrillsPath,
  adminRecoveryStatusPath,
  adminPath
} from "../../../../lib/routes";
import { SectionState } from "@ukde/ui/primitives";

export const dynamic = "force-dynamic";

function formatMs(value: number | null): string {
  return value === null ? "n/a" : `${value.toFixed(2)} ms`;
}

function formatPercent(value: number | null): string {
  return value === null ? "n/a" : `${value.toFixed(3)}%`;
}

export default async function AdminOperationsOverviewPage() {
  await requirePlatformRole(["ADMIN"]);
  const overviewResult = await getOperationsOverview();

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform operations"
        secondaryActions={[
          { href: adminOperationsReadinessPath, label: "Readiness" },
          { href: adminCapacityTestsPath, label: "Capacity tests" },
          { href: adminRecoveryStatusPath, label: "Recovery status" },
          { href: adminRecoveryDrillsPath, label: "Recovery drills" },
          { href: adminOperationsSlosPath, label: "SLO targets" },
          { href: adminOperationsAlertsPath, label: "Alerts" },
          { href: adminOperationsTimelinesPath, label: "Timelines" },
          { href: adminOperationsExportStatusPath, label: "Export status" },
          { href: adminPath, label: "Back to admin" }
        ]}
        summary="Measured platform health across API, workers, model services, and controlled storage."
        title="Operations overview"
      />

      {!overviewResult.ok || !overviewResult.data ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Operations overview unavailable"
            description={overviewResult.detail ?? "Unknown failure"}
          />
        </section>
      ) : (
        <>
          <section className="sectionCard ukde-panel">
            <div className="ukde-grid" data-columns="3">
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Requests</p>
                <h3>{overviewResult.data.requestCount}</h3>
                <p className="ukde-muted">
                  error rate {overviewResult.data.errorRatePercent.toFixed(3)}%
                </p>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Queue depth</p>
                <h3>{overviewResult.data.queueDepth ?? "n/a"}</h3>
                <p className="ukde-muted">
                  latency p95 {formatMs(overviewResult.data.queueLatencyP95Ms)}
                </p>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Jobs per minute</p>
                <h3>
                  {overviewResult.data.jobsPerMinute === null
                    ? "n/a"
                    : overviewResult.data.jobsPerMinute.toFixed(3)}
                </h3>
                <p className="ukde-muted">
                  completed {overviewResult.data.jobsCompletedCount}
                </p>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">GPU utilization</p>
                <h3>{formatPercent(overviewResult.data.gpuUtilizationAvgPercent)}</h3>
                <p className="ukde-muted">
                  max {formatPercent(overviewResult.data.gpuUtilizationMaxPercent)}
                </p>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Model requests</p>
                <h3>{overviewResult.data.modelRequestCount}</h3>
                <p className="ukde-muted">
                  error {formatPercent(overviewResult.data.modelErrorRatePercent)}, fallback{" "}
                  {formatPercent(
                    overviewResult.data.modelFallbackInvocationRatePercent
                  )}
                </p>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Export review latency</p>
                <h3>{formatMs(overviewResult.data.exportReviewLatencyP95Ms)}</h3>
                <p className="ukde-muted">
                  avg {formatMs(overviewResult.data.exportReviewLatencyAvgMs)}
                </p>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Storage requests</p>
                <h3>{overviewResult.data.storageRequestCount}</h3>
                <p className="ukde-muted">
                  error {formatPercent(overviewResult.data.storageErrorRatePercent)}
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
              request p95 {formatMs(overviewResult.data.p95LatencyMs)}. DB checks{" "}
              {overviewResult.data.readinessDbChecks}, failures{" "}
              {overviewResult.data.readinessDbFailures}, latest{" "}
              {formatMs(overviewResult.data.readinessDbLastLatencyMs)}.
            </p>
            <p className="ukde-muted">
              queue source {overviewResult.data.queueDepthSource}, GPU source{" "}
              {overviewResult.data.gpuUtilizationSource}.
            </p>
            <p className="ukde-muted">{overviewResult.data.queueDepthDetail}</p>
            <p className="ukde-muted">{overviewResult.data.gpuUtilizationDetail}</p>
          </section>

          <section className="sectionCard ukde-panel">
            <p className="ukde-eyebrow">Telemetry exporter</p>
            <div className="auditIntegrityRow">
              <span className="ukde-badge">{overviewResult.data.exporter.mode}</span>
              <span className="ukde-badge">{overviewResult.data.exporter.state}</span>
              {overviewResult.data.exporter.endpoint ? (
                <span className="ukde-muted">
                  {overviewResult.data.exporter.endpoint}
                </span>
              ) : null}
            </div>
            <p className="ukde-muted">{overviewResult.data.exporter.detail}</p>
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Model deployment telemetry</h2>
            {overviewResult.data.modelDeployments.length === 0 ? (
              <SectionState
                kind="no-results"
                title="No model requests recorded"
                description="Model deployment metrics appear after transcription engines process jobs."
              />
            ) : (
              <div className="auditTableWrap">
                <table className="auditTable">
                  <thead>
                    <tr>
                      <th>Deployment</th>
                      <th>Requests</th>
                      <th>Error rate</th>
                      <th>Fallback rate</th>
                      <th>p95 latency</th>
                      <th>Cold p95</th>
                      <th>Warm p95</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overviewResult.data.modelDeployments.map((item) => (
                      <tr key={item.deploymentUnit}>
                        <td>{item.deploymentUnit}</td>
                        <td>{item.requestCount}</td>
                        <td>{item.errorRatePercent.toFixed(3)}%</td>
                        <td>{item.fallbackInvocationRatePercent.toFixed(3)}%</td>
                        <td>{formatMs(item.p95LatencyMs)}</td>
                        <td>{formatMs(item.coldStartP95Ms)}</td>
                        <td>{formatMs(item.warmStartP95Ms)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Model breakdown</h2>
            {overviewResult.data.models.length === 0 ? (
              <SectionState
                kind="no-results"
                title="No model aggregates yet"
                description="Per-model error and fallback rates appear once model requests are observed."
              />
            ) : (
              <div className="auditTableWrap">
                <table className="auditTable">
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Deployment</th>
                      <th>Requests</th>
                      <th>Error rate</th>
                      <th>Fallback rate</th>
                      <th>p95 latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overviewResult.data.models.map((item) => (
                      <tr key={`${item.deploymentUnit}-${item.modelKey}`}>
                        <td>{item.modelKey}</td>
                        <td>{item.deploymentUnit}</td>
                        <td>{item.requestCount}</td>
                        <td>{item.errorRatePercent.toFixed(3)}%</td>
                        <td>{item.fallbackInvocationRatePercent.toFixed(3)}%</td>
                        <td>{formatMs(item.p95LatencyMs)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Storage operations</h2>
            <div className="auditTableWrap">
              <table className="auditTable">
                <thead>
                  <tr>
                    <th>Operation</th>
                    <th>Requests</th>
                    <th>Errors</th>
                    <th>Avg latency</th>
                    <th>p95 latency</th>
                  </tr>
                </thead>
                <tbody>
                  {overviewResult.data.storage.map((item) => (
                    <tr key={item.operation}>
                      <td>{item.operation}</td>
                      <td>{item.requestCount}</td>
                      <td>{item.errorCount}</td>
                      <td>{formatMs(item.averageLatencyMs)}</td>
                      <td>{formatMs(item.p95LatencyMs)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Top routes</h2>
            {overviewResult.data.topRoutes.length === 0 ? (
              <SectionState
                kind="no-results"
                title="No route telemetry yet"
                description="Route-level telemetry has not been collected in this environment."
              />
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
                        <td>{formatMs(route.averageLatencyMs)}</td>
                        <td>{formatMs(route.p95LatencyMs)}</td>
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
