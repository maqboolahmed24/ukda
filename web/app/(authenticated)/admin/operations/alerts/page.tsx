import Link from "next/link";

import type { OperationsAlertState } from "@ukde/contracts";

import { requirePlatformRole } from "../../../../../lib/auth/session";
import { listOperationsAlerts } from "../../../../../lib/operations";

const ALERT_STATE_OPTIONS: Array<OperationsAlertState | "ALL"> = [
  "OPEN",
  "UNAVAILABLE",
  "OK",
  "ALL"
];

export const dynamic = "force-dynamic";

export default async function AdminOperationsAlertsPage({
  searchParams
}: Readonly<{
  searchParams: Promise<{
    state?: OperationsAlertState | "ALL";
    cursor?: string;
  }>;
}>) {
  await requirePlatformRole(["ADMIN"]);
  const filters = await searchParams;
  const cursor = Number(filters.cursor ?? "0");
  const state = filters.state ?? "OPEN";
  const alertsResult = await listOperationsAlerts({
    state,
    cursor: Number.isFinite(cursor) ? cursor : 0,
    pageSize: 50
  });

  const items =
    alertsResult.ok && alertsResult.data ? alertsResult.data.items : [];
  const nextCursor =
    alertsResult.ok && alertsResult.data ? alertsResult.data.nextCursor : null;

  return (
    <main className="homeLayout">
      <section
        className="sectionCard ukde-panel"
        aria-labelledby="operations-alerts-title"
      >
        <p className="ukde-eyebrow">Platform operations</p>
        <h1 id="operations-alerts-title">Alert posture</h1>
        <p className="ukde-muted">
          Threshold-derived alerts only. No synthetic dashboard noise.
        </p>
        <div className="buttonRow">
          <Link className="secondaryButton" href="/admin/operations">
            Overview
          </Link>
          <Link className="secondaryButton" href="/admin/operations/slos">
            SLOs
          </Link>
          <Link className="secondaryButton" href="/admin/operations/timelines">
            Timelines
          </Link>
        </div>
      </section>

      <section
        className="sectionCard ukde-panel"
        aria-labelledby="operations-alert-filters"
      >
        <h2 id="operations-alert-filters">Filters</h2>
        <form className="auditFilterForm" method="get">
          <label htmlFor="state">State</label>
          <select defaultValue={state} id="state" name="state">
            {ALERT_STATE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <button className="secondaryButton" type="submit">
            Apply
          </button>
        </form>
      </section>

      <section className="sectionCard ukde-panel">
        {!alertsResult.ok ? (
          <p className="ukde-muted">
            Alerts unavailable: {alertsResult.detail ?? "unknown"}
          </p>
        ) : items.length === 0 ? (
          <p className="ukde-muted">No alerts matched the selected state.</p>
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>State</th>
                  <th>Severity</th>
                  <th>Threshold</th>
                  <th>Current</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {items.map((alert) => (
                  <tr key={alert.key}>
                    <td>{alert.title}</td>
                    <td>{alert.state}</td>
                    <td>{alert.severity}</td>
                    <td>{alert.threshold}</td>
                    <td>{alert.current}</td>
                    <td>{new Date(alert.updatedAt).toISOString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {typeof nextCursor === "number" ? (
          <div className="buttonRow">
            <Link
              className="secondaryButton"
              href={`/admin/operations/alerts?${new URLSearchParams({
                state,
                cursor: String(nextCursor)
              }).toString()}`}
            >
              Next page
            </Link>
          </div>
        ) : null}
      </section>
    </main>
  );
}
