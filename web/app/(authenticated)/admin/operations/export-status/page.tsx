import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../lib/auth/session";
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
  const securityStatus = await getSecurityStatus();
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

          <section className="sectionCard ukde-panel">
            <SectionState
              kind="disabled"
              title="Detailed export queue telemetry is not yet implemented"
              description="Phase-11 export-status pipeline APIs land later. This surface currently exposes gateway readiness signals only."
            />
          </section>
        </>
      )}
    </main>
  );
}
