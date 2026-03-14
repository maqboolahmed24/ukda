import Link from "next/link";

import type { AuditEventType } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { AdminAuditEventsTable } from "../../../../components/admin-audit-events-table";
import { PageHeader } from "../../../../components/page-header";
import { requirePlatformRole } from "../../../../lib/auth/session";
import { getAuditIntegrity, listAuditEvents } from "../../../../lib/audit";
import {
  activityPath,
  adminAuditPath,
  adminPath,
  withQuery
} from "../../../../lib/routes";
import {
  normalizeCursorParam,
  normalizeOptionalEnumParam,
  normalizeOptionalTextParam
} from "../../../../lib/url-state";

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
  "DOCUMENT_LIBRARY_VIEWED",
  "DOCUMENT_DETAIL_VIEWED",
  "DOCUMENT_TIMELINE_VIEWED",
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
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const isAdmin = session.user.platformRoles.includes("ADMIN");
  const rawFilters = await searchParams;
  const filters = {
    projectId: normalizeOptionalTextParam(rawFilters.projectId),
    actorUserId: normalizeOptionalTextParam(rawFilters.actorUserId),
    eventType: normalizeOptionalEnumParam(
      rawFilters.eventType,
      EVENT_FILTER_OPTIONS
    ),
    from: normalizeOptionalTextParam(rawFilters.from),
    to: normalizeOptionalTextParam(rawFilters.to),
    cursor: normalizeCursorParam(rawFilters.cursor)
  };
  const [eventsResult, integrityResult] = await Promise.all([
    listAuditEvents({
      projectId: filters.projectId,
      actorUserId: filters.actorUserId,
      eventType: filters.eventType,
      from: filters.from,
      to: filters.to,
      cursor: filters.cursor,
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
          <div className="auditIntegrityRow">
            {integrityResult.ok && integrityResult.data ? (
              <StatusChip
                tone={integrityResult.data.isValid ? "success" : "warning"}
              >
                {integrityResult.data.isValid
                  ? "Chain valid"
                  : "Chain mismatch"}
              </StatusChip>
            ) : null}
            <StatusChip tone={isAdmin ? "danger" : "warning"}>
              {isAdmin ? "ADMIN" : "AUDITOR read-only"}
            </StatusChip>
          </div>
        }
        secondaryActions={[
          { href: adminPath, label: "Back to admin" },
          { href: activityPath, label: "My activity" }
        ]}
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
          <SectionState
            kind="degraded"
            title="Integrity check unavailable"
            description={integrityResult.detail ?? "Unknown failure"}
          />
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
          <SectionState
            kind="error"
            title="Audit event read failed"
            description={eventsResult.detail ?? "Unknown failure"}
          />
        ) : (
          <AdminAuditEventsTable events={events} />
        )}
        <div className="buttonRow">
          {typeof nextCursor === "number" ? (
            <Link
              className="secondaryButton"
              href={withQuery(adminAuditPath, {
                projectId: filters.projectId,
                actorUserId: filters.actorUserId,
                eventType: filters.eventType,
                from: filters.from,
                to: filters.to,
                cursor: nextCursor
              })}
            >
              Next page
            </Link>
          ) : null}
        </div>
      </section>
    </main>
  );
}
