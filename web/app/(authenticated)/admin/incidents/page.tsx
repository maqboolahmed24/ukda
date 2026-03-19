import Link from "next/link";

import type { AdminIncident } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../lib/auth/session";
import { listAdminIncidents } from "../../../../lib/launch-operations";
import {
  adminIncidentDetailPath,
  adminIncidentStatusPath,
  adminPath,
  adminRunbooksPath
} from "../../../../lib/routes";

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

function statusTone(
  status: AdminIncident["status"]
): "danger" | "warning" | "success" | "info" {
  if (status === "RESOLVED") {
    return "success";
  }
  if (status === "MITIGATING") {
    return "warning";
  }
  if (status === "OPEN") {
    return "danger";
  }
  return "info";
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toISOString();
}

export default async function AdminIncidentsPage() {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const result = await listAdminIncidents();
  const items = result.ok && result.data ? result.data.items : [];

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
          { href: adminIncidentStatusPath, label: "Incident status" },
          ...(roleMode.isAdmin
            ? [{ href: adminRunbooksPath, label: "Runbooks" }]
            : []),
          { href: adminPath, label: "Back to admin" }
        ]}
        summary="Launch and early-life incident list with command ownership and current severity posture."
        title="Incidents"
      />

      <section className="sectionCard ukde-panel">
        {!result.ok ? (
          <SectionState
            kind="error"
            title="Incidents unavailable"
            description={result.detail ?? "Unable to load incident records."}
          />
        ) : items.length === 0 ? (
          <SectionState
            kind="no-results"
            title="No incidents recorded"
            description="No incidents are currently present in the launch catalog."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Incident</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Commander</th>
                  <th>Started</th>
                  <th>Resolved</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link href={adminIncidentDetailPath(item.id)}>{item.id}</Link>
                      <p className="ukde-muted">{item.summary}</p>
                    </td>
                    <td>
                      <StatusChip tone={severityTone(item.severity)}>
                        {item.severity}
                      </StatusChip>
                    </td>
                    <td>
                      <StatusChip tone={statusTone(item.status)}>{item.status}</StatusChip>
                    </td>
                    <td>{item.incidentCommanderUserId}</td>
                    <td>{formatTimestamp(item.startedAt)}</td>
                    <td>{formatTimestamp(item.resolvedAt)}</td>
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
