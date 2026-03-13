import Link from "next/link";

import type { OperationsTimelineScope } from "@ukde/contracts";

import { requirePlatformRole } from "../../../../../lib/auth/session";
import { listOperationsTimelines } from "../../../../../lib/operations";

const TIMELINE_SCOPE_OPTIONS: Array<OperationsTimelineScope | "all"> = [
  "all",
  "api",
  "auth",
  "audit",
  "readiness",
  "operations",
  "worker",
  "telemetry"
];

export const dynamic = "force-dynamic";

export default async function AdminOperationsTimelinesPage({
  searchParams
}: Readonly<{
  searchParams: Promise<{
    scope?: OperationsTimelineScope | "all";
    cursor?: string;
  }>;
}>) {
  await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const filters = await searchParams;
  const cursor = Number(filters.cursor ?? "0");
  const scope = filters.scope ?? "all";
  const timelineResult = await listOperationsTimelines({
    scope,
    cursor: Number.isFinite(cursor) ? cursor : 0,
    pageSize: 60
  });

  const items =
    timelineResult.ok && timelineResult.data ? timelineResult.data.items : [];
  const nextCursor =
    timelineResult.ok && timelineResult.data
      ? timelineResult.data.nextCursor
      : null;

  return (
    <main className="homeLayout">
      <section
        className="sectionCard ukde-panel"
        aria-labelledby="operations-timelines-title"
      >
        <p className="ukde-eyebrow">Platform operations</p>
        <h1 id="operations-timelines-title">Operational timelines</h1>
        <p className="ukde-muted">
          Read-only event stream for operator diagnostics and governance review.
        </p>
        <div className="buttonRow">
          <Link className="secondaryButton" href="/admin/operations">
            Overview
          </Link>
          <Link className="secondaryButton" href="/admin/operations/slos">
            SLOs
          </Link>
          <Link className="secondaryButton" href="/admin/operations/alerts">
            Alerts
          </Link>
        </div>
      </section>

      <section
        className="sectionCard ukde-panel"
        aria-labelledby="operations-timeline-filters"
      >
        <h2 id="operations-timeline-filters">Filters</h2>
        <form className="auditFilterForm" method="get">
          <label htmlFor="scope">Scope</label>
          <select defaultValue={scope} id="scope" name="scope">
            {TIMELINE_SCOPE_OPTIONS.map((option) => (
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
        {!timelineResult.ok ? (
          <p className="ukde-muted">
            Timeline unavailable: {timelineResult.detail ?? "unknown"}
          </p>
        ) : items.length === 0 ? (
          <p className="ukde-muted">
            No timeline events for the current filter.
          </p>
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Scope</th>
                  <th>Severity</th>
                  <th>Message</th>
                  <th>Request ID</th>
                  <th>Trace ID</th>
                </tr>
              </thead>
              <tbody>
                {items.map((event) => (
                  <tr key={event.id}>
                    <td>{new Date(event.occurredAt).toISOString()}</td>
                    <td>{event.scope}</td>
                    <td>{event.severity}</td>
                    <td>{event.message}</td>
                    <td>{event.requestId ?? "-"}</td>
                    <td>{event.traceId ?? "-"}</td>
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
              href={`/admin/operations/timelines?${new URLSearchParams({
                scope,
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
