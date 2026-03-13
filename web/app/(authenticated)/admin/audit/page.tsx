import Link from "next/link";

import type { AuditEventType } from "@ukde/contracts";

import { PageHeader } from "../../../../components/page-header";
import { getAuditIntegrity, listAuditEvents } from "../../../../lib/audit";

const EVENT_FILTER_OPTIONS: AuditEventType[] = [
  "USER_LOGIN",
  "USER_LOGOUT",
  "AUTH_FAILED",
  "PROJECT_CREATED",
  "PROJECT_MEMBER_ADDED",
  "PROJECT_MEMBER_REMOVED",
  "PROJECT_MEMBER_ROLE_CHANGED",
  "AUDIT_LOG_VIEWED",
  "AUDIT_EVENT_VIEWED",
  "MY_ACTIVITY_VIEWED",
  "ACCESS_DENIED",
  "JOB_LIST_VIEWED",
  "JOB_RUN_CREATED",
  "JOB_RUN_STARTED",
  "JOB_RUN_FINISHED",
  "JOB_RUN_FAILED",
  "JOB_RUN_CANCELED",
  "JOB_RUN_VIEWED",
  "JOB_RUN_STATUS_VIEWED",
  "OPERATIONS_OVERVIEW_VIEWED",
  "OPERATIONS_SLOS_VIEWED",
  "OPERATIONS_ALERTS_VIEWED",
  "OPERATIONS_TIMELINE_VIEWED"
];

export const dynamic = "force-dynamic";

export default async function AdminAuditPage({
  searchParams
}: Readonly<{
  searchParams: Promise<{
    projectId?: string;
    actorUserId?: string;
    eventType?: AuditEventType;
    from?: string;
    to?: string;
    cursor?: string;
  }>;
}>) {
  const filters = await searchParams;
  const cursor = filters.cursor ? Number(filters.cursor) : 0;
  const [eventsResult, integrityResult] = await Promise.all([
    listAuditEvents({
      projectId: filters.projectId,
      actorUserId: filters.actorUserId,
      eventType: filters.eventType,
      from: filters.from,
      to: filters.to,
      cursor: Number.isFinite(cursor) ? cursor : 0,
      pageSize: 50
    }),
    getAuditIntegrity()
  ]);

  const events =
    eventsResult.ok && eventsResult.data ? eventsResult.data.items : [];
  const nextCursor =
    eventsResult.ok && eventsResult.data ? eventsResult.data.nextCursor : null;

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Governance surface"
        meta={
          integrityResult.ok && integrityResult.data ? (
            <span
              className="ukde-badge"
              data-tone={integrityResult.data.isValid ? "success" : "warning"}
            >
              {integrityResult.data.isValid ? "Chain valid" : "Chain mismatch"}
            </span>
          ) : null
        }
        secondaryActions={[{ href: "/activity", label: "My activity" }]}
        summary="Append-only event stream with request correlation and integrity-chain status."
        title="Audit event viewer"
      />

      <section className="sectionCard ukde-panel">
        {integrityResult.ok && integrityResult.data ? (
          <div className="auditIntegrityRow">
            <span className="ukde-muted">
              Checked rows: {integrityResult.data.checkedRows}
            </span>
            <span className="ukde-muted">{integrityResult.data.detail}</span>
          </div>
        ) : (
          <p className="ukde-muted">
            Integrity check unavailable: {integrityResult.detail ?? "unknown"}
          </p>
        )}
      </section>

      <section
        className="sectionCard ukde-panel"
        aria-labelledby="audit-filter-title"
      >
        <h2 id="audit-filter-title">Filters</h2>
        <form className="auditFilterForm" method="get">
          <label htmlFor="projectId">Project ID</label>
          <input
            defaultValue={filters.projectId ?? ""}
            id="projectId"
            name="projectId"
          />

          <label htmlFor="actorUserId">Actor user ID</label>
          <input
            defaultValue={filters.actorUserId ?? ""}
            id="actorUserId"
            name="actorUserId"
          />

          <label htmlFor="eventType">Event type</label>
          <select
            defaultValue={filters.eventType ?? ""}
            id="eventType"
            name="eventType"
          >
            <option value="">All event types</option>
            {EVENT_FILTER_OPTIONS.map((eventType) => (
              <option key={eventType} value={eventType}>
                {eventType}
              </option>
            ))}
          </select>

          <label htmlFor="from">From (ISO timestamp)</label>
          <input defaultValue={filters.from ?? ""} id="from" name="from" />

          <label htmlFor="to">To (ISO timestamp)</label>
          <input defaultValue={filters.to ?? ""} id="to" name="to" />

          <button className="secondaryButton" type="submit">
            Apply filters
          </button>
        </form>
      </section>

      <section
        className="sectionCard ukde-panel"
        aria-labelledby="audit-events-title"
      >
        <h2 id="audit-events-title">Audit events</h2>
        {!eventsResult.ok ? (
          <p className="ukde-muted">
            Audit event read failed: {eventsResult.detail ?? "unknown"}
          </p>
        ) : events.length === 0 ? (
          <p className="ukde-muted">No events matched the current filters.</p>
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Event</th>
                  <th>Actor</th>
                  <th>Project</th>
                  <th>Request ID</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td>{new Date(event.timestamp).toISOString()}</td>
                    <td>{event.eventType}</td>
                    <td>{event.actorUserId ?? "-"}</td>
                    <td>{event.projectId ?? "-"}</td>
                    <td>{event.requestId}</td>
                    <td>
                      <Link
                        className="ukde-link"
                        href={`/admin/audit/${event.id}`}
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="buttonRow">
          {typeof nextCursor === "number" ? (
            <Link
              className="secondaryButton"
              href={`/admin/audit?${new URLSearchParams({
                ...(filters.projectId ? { projectId: filters.projectId } : {}),
                ...(filters.actorUserId
                  ? { actorUserId: filters.actorUserId }
                  : {}),
                ...(filters.eventType ? { eventType: filters.eventType } : {}),
                ...(filters.from ? { from: filters.from } : {}),
                ...(filters.to ? { to: filters.to } : {}),
                cursor: String(nextCursor)
              }).toString()}`}
            >
              Next page
            </Link>
          ) : null}
        </div>
      </section>
    </main>
  );
}
