import { PageHeader } from "../../../../components/page-header";
import { SecurityPreferencesCard } from "../../../../components/security-preferences-card";
import { resolveAdminRoleMode } from "../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../lib/auth/session";
import {
  adminAuditPath,
  adminSecurityFindingsPath,
  adminSecurityRiskAcceptancesPath,
  adminOperationsExportStatusPath,
  adminOperationsPath,
  adminOperationsTimelinesPath,
  adminPath
} from "../../../../lib/routes";
import { getSecurityStatus, listAdminSecurityFindings } from "../../../../lib/security";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

export const dynamic = "force-dynamic";

export default async function AdminSecurityPage() {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const [statusResult, findingsResult] = await Promise.all([
    getSecurityStatus(),
    listAdminSecurityFindings()
  ]);
  const secondaryActions = roleMode.isAdmin
    ? [
        { href: adminPath, label: "Back to admin" },
        { href: adminSecurityFindingsPath, label: "Security findings" },
        { href: adminSecurityRiskAcceptancesPath, label: "Risk acceptances" },
        { href: adminOperationsPath, label: "Operations overview" },
        { href: adminAuditPath, label: "Audit viewer" }
      ]
    : [
        { href: adminPath, label: "Back to admin" },
        { href: adminSecurityFindingsPath, label: "Security findings" },
        { href: adminSecurityRiskAcceptancesPath, label: "Risk acceptances" },
        { href: adminOperationsExportStatusPath, label: "Export status" },
        { href: adminOperationsTimelinesPath, label: "Timelines" },
        { href: adminAuditPath, label: "Audit viewer" }
      ];
  const findings = findingsResult.ok && findingsResult.data ? findingsResult.data : null;

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform security"
        meta={
          <StatusChip tone={roleMode.isAdmin ? "danger" : "warning"}>
            {roleMode.isAdmin ? "ADMIN" : "AUDITOR read-only"}
          </StatusChip>
        }
        secondaryActions={secondaryActions}
        summary="Controlled-environment posture, deny-by-default egress checks, and export gateway state."
        title="Security status"
      />

      {!statusResult.ok || !statusResult.data ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Security status unavailable"
            description={statusResult.detail ?? "Unknown failure"}
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <div className="auditIntegrityRow">
            <span className="ukde-badge">{statusResult.data.environment}</span>
            <span className="ukde-badge">{statusResult.data.cspMode}</span>
            <span className="ukde-badge">
              {statusResult.data.exportGatewayState}
            </span>
          </div>
          <ul className="projectMetaList">
            <li>
              <span>Deny-by-default egress</span>
              <strong>
                {statusResult.data.denyByDefaultEgress
                  ? "enforced"
                  : "not enforced"}
              </strong>
            </li>
            <li>
              <span>Last successful egress deny test</span>
              <strong>
                {statusResult.data.lastSuccessfulEgressDenyTestAt ??
                  "Not recorded"}
              </strong>
            </li>
            <li>
              <span>Last backup timestamp</span>
              <strong>
                {statusResult.data.lastBackupAt ?? "Not configured"}
              </strong>
            </li>
            <li>
              <span>Role mode</span>
              <strong>
                {roleMode.isAdmin ? "ADMIN (full access)" : "AUDITOR (read-only)"}
              </strong>
            </li>
          </ul>
          <p className="ukde-muted">{statusResult.data.egressTestDetail}</p>
          <p className="ukde-muted">
            Outbound allowlist: {statusResult.data.outboundAllowlist.join(", ")}
          </p>
        </section>
      )}

      {!findingsResult.ok || !findings ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Findings posture unavailable"
            description={findingsResult.detail ?? "Unable to load security findings posture."}
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2>Findings posture</h2>
          <ul className="projectMetaList">
            <li>
              <span>Critical/high gate</span>
              <strong>
                {findings.criticalHighGatePassed ? "passing" : "blocked"}
              </strong>
            </li>
            <li>
              <span>Pen-test checklist</span>
              <strong>
                {findings.penTestChecklistComplete ? "complete" : "incomplete"}
              </strong>
            </li>
            <li>
              <span>Total findings</span>
              <strong>{findings.items.length}</strong>
            </li>
          </ul>
          {findings.criticalHighUnresolvedFindingIds.length > 0 ? (
            <p className="ukde-muted">
              Unresolved critical/high:{" "}
              {findings.criticalHighUnresolvedFindingIds.join(", ")}
            </p>
          ) : null}
        </section>
      )}

      <SecurityPreferencesCard />
    </main>
  );
}
