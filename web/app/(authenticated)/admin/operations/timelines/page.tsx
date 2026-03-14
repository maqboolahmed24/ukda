import Link from "next/link";

import type { OperationsTimelineScope } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import { listOperationsTimelines } from "../../../../../lib/operations";
import {
  adminAuditPath,
  adminOperationsAlertsPath,
  adminOperationsExportStatusPath,
  adminOperationsPath,
  adminOperationsSlosPath,
  adminOperationsTimelinesPath,
  adminPath,
  adminSecurityPath,
  withQuery
} from "../../../../../lib/routes";
import {
  normalizeCursorParam,
  normalizeOptionalEnumParam
} from "../../../../../lib/url-state";

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
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const rawFilters = await searchParams;
  const cursor = normalizeCursorParam(rawFilters.cursor);
  const scope =
    normalizeOptionalEnumParam(rawFilters.scope, TIMELINE_SCOPE_OPTIONS) ??
    "all";
  const timelineResult = await listOperationsTimelines({
    scope,
    cursor,
    pageSize: 60
  });

  const items =
    timelineResult.ok && timelineResult.data ? timelineResult.data.items : [];
  const nextCursor =
    timelineResult.ok && timelineResult.data
      ? timelineResult.data.nextCursor
      : null;
  const secondaryActions = roleMode.isAdmin
    ? [
        { href: adminOperationsPath, label: "Overview" },
        { href: adminOperationsSlosPath, label: "SLOs" },
        { href: adminOperationsAlertsPath, label: "Alerts" },
        { href: adminOperationsExportStatusPath, label: "Export status" }
      ]
    : [
        { href: adminPath, label: "Back to admin" },
        { href: adminOperationsExportStatusPath, label: "Export status" },
        { href: adminSecurityPath, label: "Security status" },
        { href: adminAuditPath, label: "Audit viewer" }
      ];

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform operations"
        meta={
          <StatusChip tone={roleMode.isAdmin ? "danger" : "warning"}>
            {roleMode.isAdmin ? "ADMIN" : "AUDITOR read-only"}
          </StatusChip>
        }
        secondaryActions={secondaryActions}
        summary="Read-only event stream for operator diagnostics and governance review."
        title="Operational timelines"
      />

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
          <SectionState
            kind="error"
            title="Timeline unavailable"
            description={timelineResult.detail ?? "Unknown failure"}
          />
        ) : items.length === 0 ? (
          <SectionState
            kind="no-results"
            title="No timeline events"
            description="No timeline events matched the current scope filter."
          />
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
              href={withQuery(adminOperationsTimelinesPath, {
                scope,
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
