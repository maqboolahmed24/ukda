import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import { getAdminIncidentStatus } from "../../../../../lib/launch-operations";
import {
  adminIncidentsPath,
  adminPath,
  adminRunbooksPath
} from "../../../../../lib/routes";

export const dynamic = "force-dynamic";

function rehearsalTone(
  status: "COMPLETED" | "PENDING" | "BLOCKED"
): "success" | "warning" | "danger" {
  if (status === "COMPLETED") {
    return "success";
  }
  if (status === "BLOCKED") {
    return "danger";
  }
  return "warning";
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toISOString();
}

export default async function AdminIncidentStatusPage() {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const result = await getAdminIncidentStatus();

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform operations"
        meta={
          <StatusChip tone={roleMode.isAdmin ? "danger" : "warning"}>
            {roleMode.isAdmin ? "ADMIN" : "AUDITOR read-only"}
          </StatusChip>
        }
        secondaryActions={[
          { href: adminIncidentsPath, label: "Incidents" },
          ...(roleMode.isAdmin
            ? [{ href: adminRunbooksPath, label: "Runbooks" }]
            : []),
          { href: adminPath, label: "Back to admin" }
        ]}
        summary="No-go trigger summary and rehearsal status panel for final ship/no-ship review."
        title="Incident status"
      />

      {!result.ok || !result.data ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Incident status unavailable"
            description={result.detail ?? "Unable to load incident status snapshot."}
          />
        </section>
      ) : (
        <>
          <section className="sectionCard ukde-panel">
            <div className="auditIntegrityRow">
              <StatusChip tone={result.data.noGoTriggered ? "danger" : "success"}>
                {result.data.noGoTriggered ? "No-go triggered" : "No-go clear"}
              </StatusChip>
              <StatusChip tone="info">
                Open incidents {result.data.openIncidentCount}
              </StatusChip>
              <StatusChip tone="warning">
                Unresolved high severity {result.data.unresolvedHighSeverityCount}
              </StatusChip>
            </div>
            <ul className="projectMetaList">
              <li>
                <span>Generated</span>
                <strong>{formatTimestamp(result.data.generatedAt)}</strong>
              </li>
              <li>
                <span>Latest incident started</span>
                <strong>{formatTimestamp(result.data.latestStartedAt)}</strong>
              </li>
            </ul>
            {result.data.noGoReasons.length === 0 ? (
              <SectionState
                kind="success"
                title="No no-go reasons active"
                description="No active no-go triggers are reported in this snapshot."
              />
            ) : (
              <ul className="ukde-list">
                {result.data.noGoReasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Rehearsal status</h2>
            <div className="auditIntegrityRow">
              <StatusChip tone={rehearsalTone(result.data.goLiveRehearsalStatus)}>
                Go-live rehearsal: {result.data.goLiveRehearsalStatus}
              </StatusChip>
              <StatusChip tone={rehearsalTone(result.data.incidentResponseTabletopStatus)}>
                Incident tabletop: {result.data.incidentResponseTabletopStatus}
              </StatusChip>
              <StatusChip tone={rehearsalTone(result.data.modelRollbackRehearsalStatus)}>
                Model rollback: {result.data.modelRollbackRehearsalStatus}
              </StatusChip>
            </div>
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Status buckets</h2>
            <div className="ukde-grid" data-columns="2">
              <article className="statCard ukde-panel ukde-surface-raised">
                <h3>By incident status</h3>
                <div className="auditTableWrap">
                  <table className="auditTable">
                    <thead>
                      <tr>
                        <th>Status</th>
                        <th>Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.data.byStatus.map((item) => (
                        <tr key={`status-${item.key}`}>
                          <td>{item.key}</td>
                          <td>{item.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>

              <article className="statCard ukde-panel ukde-surface-raised">
                <h3>By severity</h3>
                <div className="auditTableWrap">
                  <table className="auditTable">
                    <thead>
                      <tr>
                        <th>Severity</th>
                        <th>Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.data.bySeverity.map((item) => (
                        <tr key={`severity-${item.key}`}>
                          <td>{item.key}</td>
                          <td>{item.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
