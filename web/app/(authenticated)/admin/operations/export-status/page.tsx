import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import { getOperationsExportStatus } from "../../../../../lib/operations";
import {
  adminOperationsPath,
  adminOperationsTimelinesPath,
  adminPath,
  adminSecurityPath
} from "../../../../../lib/routes";
import { getSecurityStatus } from "../../../../../lib/security";

export const dynamic = "force-dynamic";

export default async function AdminOperationsExportStatusPage() {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const [securityStatus, exportStatus] = await Promise.all([
    getSecurityStatus(),
    getOperationsExportStatus()
  ]);
  const secondaryActions = roleMode.isAdmin
    ? [
        { href: adminPath, label: "Back to admin" },
        { href: adminOperationsPath, label: "Operations overview" },
        { href: adminOperationsTimelinesPath, label: "Timelines" }
      ]
    : [
        { href: adminPath, label: "Back to admin" },
        { href: adminOperationsTimelinesPath, label: "Timelines" },
        { href: adminSecurityPath, label: "Security status" }
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
        summary="Read-only export queue posture and gateway readiness context for governance monitoring."
        title="Export status"
      />

      {!securityStatus.ok || !securityStatus.data ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Export status unavailable"
            description={securityStatus.detail ?? "Unknown failure"}
          />
        </section>
      ) : (
        <>
          <section className="sectionCard ukde-panel">
            <ul className="projectMetaList">
              <li>
                <span>Export gateway</span>
                <strong>{securityStatus.data.exportGatewayState}</strong>
              </li>
              <li>
                <span>Deny-by-default egress</span>
                <strong>
                  {securityStatus.data.denyByDefaultEgress
                    ? "enforced"
                    : "not enforced"}
                </strong>
              </li>
              <li>
                <span>Last egress deny test</span>
                <strong>
                  {securityStatus.data.lastSuccessfulEgressDenyTestAt ??
                    "Not recorded"}
                </strong>
              </li>
            </ul>
            <p className="ukde-muted">{securityStatus.data.egressTestDetail}</p>
          </section>
        </>
      )}

      {!exportStatus.ok || !exportStatus.data ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Export queue telemetry unavailable"
            description={exportStatus.detail ?? "Unknown failure"}
          />
        </section>
      ) : (
        <>
          <section className="sectionCard ukde-panel">
            <p className="ukde-eyebrow">Open queue posture</p>
            <div className="ukde-grid" data-columns="3">
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Open requests</p>
                <h3>{exportStatus.data.openRequestCount}</h3>
                <p className="ukde-muted">
                  stale {exportStatus.data.aging.staleOpen}
                </p>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">SLA overdue</p>
                <h3>{exportStatus.data.aging.overdue}</h3>
                <p className="ukde-muted">
                  due soon {exportStatus.data.aging.dueSoon}
                </p>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Retention pending</p>
                <h3>{exportStatus.data.retention.pendingCount}</h3>
                <p className="ukde-muted">
                  next {exportStatus.data.retention.pendingWindowDays} days
                </p>
              </article>
            </div>
          </section>

          <section className="sectionCard ukde-panel">
            <div className="ukde-grid" data-columns="2">
              <article className="ukde-panel">
                <p className="ukde-eyebrow">Aging buckets</p>
                <ul className="projectMetaList">
                  <li>
                    <span>Unstarted</span>
                    <strong>{exportStatus.data.aging.unstarted}</strong>
                  </li>
                  <li>
                    <span>No SLA</span>
                    <strong>{exportStatus.data.aging.noSla}</strong>
                  </li>
                  <li>
                    <span>On track</span>
                    <strong>{exportStatus.data.aging.onTrack}</strong>
                  </li>
                  <li>
                    <span>Due soon</span>
                    <strong>{exportStatus.data.aging.dueSoon}</strong>
                  </li>
                  <li>
                    <span>Overdue</span>
                    <strong>{exportStatus.data.aging.overdue}</strong>
                  </li>
                </ul>
              </article>
              <article className="ukde-panel">
                <p className="ukde-eyebrow">Ops actions</p>
                <ul className="projectMetaList">
                  <li>
                    <span>Reminders due</span>
                    <strong>{exportStatus.data.reminders.due}</strong>
                  </li>
                  <li>
                    <span>Reminders (24h)</span>
                    <strong>{exportStatus.data.reminders.sentLast24h}</strong>
                  </li>
                  <li>
                    <span>Escalations due</span>
                    <strong>{exportStatus.data.escalations.due}</strong>
                  </li>
                  <li>
                    <span>Open escalated</span>
                    <strong>{exportStatus.data.escalations.openEscalated}</strong>
                  </li>
                </ul>
              </article>
            </div>
          </section>

          <section className="sectionCard ukde-panel">
            <p className="ukde-eyebrow">Terminal outcomes</p>
            <div className="auditIntegrityRow">
              <span className="ukde-badge">
                approved {exportStatus.data.terminal.approved}
              </span>
              <span className="ukde-badge">
                exported {exportStatus.data.terminal.exported}
              </span>
              <span className="ukde-badge">
                rejected {exportStatus.data.terminal.rejected}
              </span>
              <span className="ukde-badge">
                returned {exportStatus.data.terminal.returned}
              </span>
            </div>
            <p className="ukde-muted">
              Policy: SLA {exportStatus.data.policy.slaHours}h, reminder after{" "}
              {exportStatus.data.policy.reminderAfterHours}h, escalation after SLA +{" "}
              {exportStatus.data.policy.escalationAfterSlaHours}h.
            </p>
          </section>
        </>
      )}
    </main>
  );
}
