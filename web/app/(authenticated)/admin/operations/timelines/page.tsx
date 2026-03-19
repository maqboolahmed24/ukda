import Link from "next/link";

import type { OperationsTimelineScope } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import { listOperationsTimelines } from "../../../../../lib/operations";
import {
  adminAuditPath,
  adminCapacityTestsPath,
  adminOperationsAlertsPath,
  adminOperationsExportStatusPath,
  adminOperationsPath,
  adminOperationsSlosPath,
  adminOperationsTimelinesPath,
  adminPath,
  adminRecoveryDrillDetailPath,
  adminRecoveryDrillEvidencePath,
  adminRecoveryDrillsPath,
  adminRecoveryStatusPath,
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
  "model",
  "readiness",
  "operations",
  "storage",
  "worker",
  "telemetry"
];

export const dynamic = "force-dynamic";

function asTrimmedString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function resolveRecoveryEvent(event: {
  message: string;
  detailsJson: Record<string, unknown>;
}) {
  const details = event.detailsJson;
  const drillId =
    asTrimmedString(details.drill_id) ??
    asTrimmedString(details.drillId) ??
    asTrimmedString(details.recovery_drill_id);
  const status = asTrimmedString(details.status) ?? "UNKNOWN";
  const startedAt = asTrimmedString(details.started_at) ?? asTrimmedString(details.startedAt);
  const finishedAt = asTrimmedString(details.finished_at) ?? asTrimmedString(details.finishedAt);
  const summary =
    asTrimmedString(details.summary) ??
    asTrimmedString(details.summary_text) ??
    asTrimmedString(details.summaryText) ??
    event.message;
  const evidenceStorageKey =
    asTrimmedString(details.evidence_storage_key) ??
    asTrimmedString(details.evidenceStorageKey);
  const evidenceStorageSha256 =
    asTrimmedString(details.evidence_storage_sha256) ??
    asTrimmedString(details.evidenceStorageSha256);
  const evidenceSummaryJson =
    (typeof details.evidence_summary_json === "object" &&
    details.evidence_summary_json !== null
      ? details.evidence_summary_json
      : null) ??
    (typeof details.evidenceSummaryJson === "object" &&
    details.evidenceSummaryJson !== null
      ? details.evidenceSummaryJson
      : null);

  const isRecoveryMessage = event.message.toLowerCase().includes("recovery");
  if (!drillId && !isRecoveryMessage) {
    return null;
  }

  return {
    drillId,
    status,
    startedAt,
    finishedAt,
    summary,
    evidenceStorageKey,
    evidenceStorageSha256,
    evidenceSummaryJson
  };
}

function statusTone(status: string): "success" | "warning" | "danger" | "neutral" | "info" {
  if (status === "SUCCEEDED") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  if (status === "RUNNING") {
    return "info";
  }
  return "warning";
}

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
  const recoveryEvents = items
    .map((event) => ({
      event,
      recovery: resolveRecoveryEvent(event)
    }))
    .filter(
      (entry): entry is { event: (typeof items)[number]; recovery: NonNullable<ReturnType<typeof resolveRecoveryEvent>> } =>
        entry.recovery !== null
    );
  const nextCursor =
    timelineResult.ok && timelineResult.data
      ? timelineResult.data.nextCursor
      : null;
  const secondaryActions = roleMode.isAdmin
      ? [
          { href: adminCapacityTestsPath, label: "Capacity tests" },
          { href: adminRecoveryStatusPath, label: "Recovery status" },
          { href: adminRecoveryDrillsPath, label: "Recovery drills" },
          { href: adminOperationsPath, label: "Overview" },
          { href: adminOperationsSlosPath, label: "SLOs" },
          { href: adminOperationsAlertsPath, label: "Alerts" },
          { href: adminOperationsExportStatusPath, label: "Export status" }
        ]
      : [
          { href: adminCapacityTestsPath, label: "Capacity tests" },
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

      {recoveryEvents.length > 0 ? (
        <section className="sectionCard ukde-panel">
          <h2>Recovery drill timeline evidence</h2>
          <div className="ukde-stack-sm">
            {recoveryEvents.map(({ event, recovery }) => (
              <article className="statCard ukde-panel ukde-surface-raised" key={`recovery-${event.id}`}>
                <div className="auditIntegrityRow">
                  <h3>{recovery.drillId ?? `timeline-${event.id}`}</h3>
                  <StatusChip tone={statusTone(recovery.status)}>{recovery.status}</StatusChip>
                </div>
                <p className="ukde-muted">{recovery.summary}</p>
                <ul className="projectMetaList">
                  <li>
                    <span>Started</span>
                    <strong>{recovery.startedAt ? new Date(recovery.startedAt).toISOString() : "n/a"}</strong>
                  </li>
                  <li>
                    <span>Finished</span>
                    <strong>{recovery.finishedAt ? new Date(recovery.finishedAt).toISOString() : "n/a"}</strong>
                  </li>
                  <li>
                    <span>Timeline event</span>
                    <strong>{event.id}</strong>
                  </li>
                </ul>
                {roleMode.isAdmin && recovery.drillId ? (
                  <div className="buttonRow">
                    <Link
                      className="secondaryButton"
                      href={adminRecoveryDrillDetailPath(recovery.drillId)}
                    >
                      Open drill
                    </Link>
                    <Link
                      className="secondaryButton"
                      href={adminRecoveryDrillEvidencePath(recovery.drillId)}
                    >
                      Open evidence
                    </Link>
                  </div>
                ) : null}
                {roleMode.isAdmin && recovery.evidenceStorageKey ? (
                  <p className="ukde-muted">
                    Evidence key: {recovery.evidenceStorageKey}
                    {recovery.evidenceStorageSha256
                      ? ` (sha256 ${recovery.evidenceStorageSha256})`
                      : ""}
                  </p>
                ) : null}
                {roleMode.isAdmin && recovery.evidenceSummaryJson ? (
                  <pre className="ukde-json-panel">
                    {JSON.stringify(recovery.evidenceSummaryJson, null, 2)}
                  </pre>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}
