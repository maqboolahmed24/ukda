import Link from "next/link";

import type { SecurityFindingSeverity, SecurityFindingStatus } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import { listAdminSecurityFindings } from "../../../../../lib/security";
import {
  adminPath,
  adminSecurityPath,
  adminSecurityFindingDetailPath,
  adminSecurityRiskAcceptancesPath
} from "../../../../../lib/routes";

export const dynamic = "force-dynamic";

function severityTone(
  severity: SecurityFindingSeverity
): "danger" | "warning" | "info" | "neutral" {
  if (severity === "CRITICAL") {
    return "danger";
  }
  if (severity === "HIGH") {
    return "warning";
  }
  if (severity === "MEDIUM") {
    return "info";
  }
  return "neutral";
}

function statusTone(
  status: SecurityFindingStatus
): "danger" | "warning" | "success" | "info" {
  if (status === "RESOLVED") {
    return "success";
  }
  if (status === "IN_PROGRESS") {
    return "info";
  }
  return "danger";
}

function checklistTone(status: string): "success" | "warning" | "danger" {
  if (status === "PASS" || status === "RISK_ACCEPTED") {
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

export default async function AdminSecurityFindingsPage() {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const result = await listAdminSecurityFindings();
  const payload = result.ok && result.data ? result.data : null;

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform security"
        meta={
          <StatusChip tone={roleMode.isAdmin ? "danger" : "warning"}>
            {roleMode.isAdmin ? "ADMIN" : "AUDITOR read-only"}
          </StatusChip>
        }
        secondaryActions={[
          { href: adminSecurityPath, label: "Security status" },
          { href: adminSecurityRiskAcceptancesPath, label: "Risk acceptances" },
          { href: adminPath, label: "Back to admin" }
        ]}
        summary="Security findings intake/read surface with closure tracking, risk acceptance visibility, and pen-test readiness posture."
        title="Security findings"
      />

      {!result.ok || !payload ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Security findings unavailable"
            description={result.detail ?? "Unable to load security findings."}
          />
        </section>
      ) : (
        <>
          <section className="sectionCard ukde-panel">
            <div className="auditIntegrityRow">
              <StatusChip tone={payload.criticalHighGatePassed ? "success" : "danger"}>
                {payload.criticalHighGatePassed
                  ? "Critical/high gate passing"
                  : "Critical/high gate blocked"}
              </StatusChip>
              <StatusChip tone={payload.penTestChecklistComplete ? "success" : "warning"}>
                {payload.penTestChecklistComplete
                  ? "Pen-test checklist complete"
                  : "Pen-test checklist incomplete"}
              </StatusChip>
            </div>
            {payload.criticalHighUnresolvedFindingIds.length > 0 ? (
              <p className="ukde-muted">
                Unresolved critical/high findings:{" "}
                {payload.criticalHighUnresolvedFindingIds.join(", ")}
              </p>
            ) : null}
            {payload.penTestChecklist.length > 0 ? (
              <div className="auditTableWrap">
                <table className="auditTable">
                  <thead>
                    <tr>
                      <th>Checklist item</th>
                      <th>Status</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payload.penTestChecklist.map((item) => (
                      <tr key={item.key}>
                        <td>{item.title}</td>
                        <td>
                          <StatusChip tone={checklistTone(item.status)}>
                            {item.status}
                          </StatusChip>
                        </td>
                        <td>{item.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>

          <section className="sectionCard ukde-panel">
            {payload.items.length === 0 ? (
              <SectionState
                kind="no-results"
                title="No security findings recorded"
                description="No findings are currently present in the findings store."
              />
            ) : (
              <div className="auditTableWrap">
                <table className="auditTable">
                  <thead>
                    <tr>
                      <th>Finding</th>
                      <th>Severity</th>
                      <th>Status</th>
                      <th>Owner</th>
                      <th>Source</th>
                      <th>Opened</th>
                      <th>Resolved</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payload.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <Link href={adminSecurityFindingDetailPath(item.id)}>{item.id}</Link>
                        </td>
                        <td>
                          <StatusChip tone={severityTone(item.severity)}>
                            {item.severity}
                          </StatusChip>
                        </td>
                        <td>
                          <StatusChip tone={statusTone(item.status)}>{item.status}</StatusChip>
                        </td>
                        <td>{item.ownerUserId}</td>
                        <td>{item.source}</td>
                        <td>{formatTimestamp(item.openedAt)}</td>
                        <td>{formatTimestamp(item.resolvedAt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
