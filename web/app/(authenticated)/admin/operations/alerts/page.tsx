import Link from "next/link";

import type { OperationsAlertState } from "@ukde/contracts";
import { SectionState } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import { listOperationsAlerts } from "../../../../../lib/operations";
import {
  adminOperationsAlertsPath,
  adminOperationsExportStatusPath,
  adminOperationsPath,
  adminOperationsSlosPath,
  adminOperationsTimelinesPath,
  withQuery
} from "../../../../../lib/routes";
import {
  normalizeCursorParam,
  normalizeOptionalEnumParam
} from "../../../../../lib/url-state";

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
  const rawFilters = await searchParams;
  const cursor = normalizeCursorParam(rawFilters.cursor);
  const state =
    normalizeOptionalEnumParam(rawFilters.state, ALERT_STATE_OPTIONS) ?? "OPEN";
  const alertsResult = await listOperationsAlerts({
    state,
    cursor,
    pageSize: 50
  });

  const items =
    alertsResult.ok && alertsResult.data ? alertsResult.data.items : [];
  const nextCursor =
    alertsResult.ok && alertsResult.data ? alertsResult.data.nextCursor : null;

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform operations"
        secondaryActions={[
          { href: adminOperationsPath, label: "Overview" },
          { href: adminOperationsSlosPath, label: "SLOs" },
          { href: adminOperationsTimelinesPath, label: "Timelines" },
          { href: adminOperationsExportStatusPath, label: "Export status" }
        ]}
        summary="Threshold-derived alerts only, without synthetic dashboard noise."
        title="Alert posture"
      />

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
          <SectionState
            kind="error"
            title="Alerts unavailable"
            description={alertsResult.detail ?? "Unknown failure"}
          />
        ) : items.length === 0 ? (
          <SectionState
            kind="no-results"
            title="No alerts matched the filter"
            description="Try a different state filter to expand the result set."
          />
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
              href={withQuery(adminOperationsAlertsPath, {
                state,
                cursor: nextCursor
              })}
            >
              Next page
            </Link>
          </div>
        ) : null}
      </section>
    </main>
  );
}
