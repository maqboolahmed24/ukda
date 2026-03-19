import type { AdminIncident } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../../lib/auth/session";
import {
  getAdminIncident,
  getAdminIncidentTimeline
} from "../../../../../../lib/launch-operations";
import {
  adminIncidentDetailPath,
  adminIncidentStatusPath,
  adminIncidentsPath
} from "../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function severityTone(
  severity: AdminIncident["severity"]
): "danger" | "warning" | "info" | "neutral" {
  if (severity === "SEV1") {
    return "danger";
  }
  if (severity === "SEV2") {
    return "warning";
  }
  if (severity === "SEV3") {
    return "info";
  }
  return "neutral";
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toISOString();
}

export default async function AdminIncidentTimelinePage({
  params
}: Readonly<{
  params: Promise<{ incidentId: string }>;
}>) {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const { incidentId } = await params;
  const [detailResult, timelineResult] = await Promise.all([
    getAdminIncident(incidentId),
    getAdminIncidentTimeline(incidentId)
  ]);

  if (!detailResult.ok || !detailResult.data) {
    return (
      <main className="homeLayout">
        <PageHeader
          eyebrow="Platform operations"
          secondaryActions={[
            { href: adminIncidentsPath, label: "Back to incidents" },
            { href: adminIncidentStatusPath, label: "Incident status" }
          ]}
          summary="Incident timeline retrieval failed because the incident detail could not be loaded."
          title="Incident timeline"
        />
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Incident unavailable"
            description={detailResult.detail ?? "Unable to load incident detail."}
          />
        </section>
      </main>
    );
  }

  const incident = detailResult.data;
  const events = timelineResult.ok && timelineResult.data ? timelineResult.data.items : [];

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
          { href: adminIncidentsPath, label: "Back to incidents" },
          { href: adminIncidentDetailPath(incident.id), label: "Incident detail" },
          { href: adminIncidentStatusPath, label: "Incident status" }
        ]}
        summary="Read-only timeline chronology for launch and early-life incident command."
        title={`Timeline · ${incident.id}`}
      />

      <section className="sectionCard ukde-panel">
        <div className="auditIntegrityRow">
          <StatusChip tone={severityTone(incident.severity)}>
            {incident.severity}
          </StatusChip>
          <StatusChip tone={incident.status === "RESOLVED" ? "success" : "warning"}>
            {incident.status}
          </StatusChip>
        </div>
        <p className="ukde-muted">{incident.summary}</p>
        <ul className="projectMetaList">
          <li>
            <span>Commander</span>
            <strong>{incident.incidentCommanderUserId}</strong>
          </li>
          <li>
            <span>Started</span>
            <strong>{formatTimestamp(incident.startedAt)}</strong>
          </li>
          <li>
            <span>Resolved</span>
            <strong>{formatTimestamp(incident.resolvedAt)}</strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        {!timelineResult.ok ? (
          <SectionState
            kind="error"
            title="Timeline unavailable"
            description={timelineResult.detail ?? "Unable to load incident timeline."}
          />
        ) : events.length === 0 ? (
          <SectionState
            kind="no-results"
            title="No timeline events"
            description="No timeline events are currently stored for this incident."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Type</th>
                  <th>Actor</th>
                  <th>Summary</th>
                </tr>
              </thead>
              <tbody>
                {events.map((item) => (
                  <tr key={item.id}>
                    <td>{formatTimestamp(item.createdAt)}</td>
                    <td>{item.eventType}</td>
                    <td>{item.actorUserId}</td>
                    <td>{item.summary}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
