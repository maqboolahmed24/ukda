import Link from "next/link";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../components/page-header";
import { requirePlatformRole } from "../../../lib/auth/session";
import {
  resolveAdminRoleMode,
  resolveAdminSurfaces
} from "../../../lib/admin-console";
import { getAuditIntegrity } from "../../../lib/audit";
import { getOperationsOverview } from "../../../lib/operations";
import { getSecurityStatus } from "../../../lib/security";

export const dynamic = "force-dynamic";

export default async function AdminHomePage() {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const surfaces = resolveAdminSurfaces(session);
  const [auditIntegrity, securityStatus, operationsOverview] = await Promise.all(
    [
      getAuditIntegrity(),
      getSecurityStatus(),
      roleMode.isAdmin ? getOperationsOverview() : Promise.resolve(null)
    ]
  );

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform route"
        meta={
          <StatusChip tone={roleMode.isAdmin ? "danger" : "info"}>
            {roleMode.isAdmin ? "ADMIN" : "AUDITOR (read-only)"}
          </StatusChip>
        }
        secondaryActions={[{ href: "/projects", label: "Back to projects" }]}
        summary="Platform-role access is enforced server-side for governance and operator surfaces."
        title="Admin console"
      />

      <section className="sectionCard ukde-panel">
        <h2>Accessible modules</h2>
        {surfaces.length === 0 ? (
          <SectionState
            kind="empty"
            title="No admin surfaces available"
            description="This session does not currently expose platform governance modules."
          />
        ) : (
          <div className="ukde-grid" data-columns="2">
            {surfaces.map((surface) => (
              <article
                className="statCard ukde-panel ukde-surface-raised"
                key={surface.id}
              >
                <div className="auditIntegrityRow">
                  <h3>{surface.label}</h3>
                  {surface.readOnlyForAuditor && !roleMode.isAdmin ? (
                    <StatusChip tone="warning">Read-only</StatusChip>
                  ) : null}
                </div>
                <p className="ukde-muted">{surface.description}</p>
                <Link className="secondaryButton" href={surface.href}>
                  Open module
                </Link>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="sectionCard ukde-panel">
        <h2>Governance posture snapshot</h2>
        <ul className="projectMetaList">
          <li>
            <span>Audit integrity chain</span>
            <strong>
              {auditIntegrity.ok && auditIntegrity.data
                ? auditIntegrity.data.isValid
                  ? "valid"
                  : "mismatch detected"
                : "unavailable"}
            </strong>
          </li>
          <li>
            <span>Security posture</span>
            <strong>
              {securityStatus.ok && securityStatus.data
                ? securityStatus.data.exportGatewayState
                : "unavailable"}
            </strong>
          </li>
          <li>
            <span>Operations overview</span>
            <strong>
              {operationsOverview && operationsOverview.ok && operationsOverview.data
                ? `${operationsOverview.data.requestCount} requests`
                : roleMode.isAdmin
                  ? "unavailable"
                  : "read-only routes only"}
            </strong>
          </li>
        </ul>
      </section>
    </main>
  );
}
