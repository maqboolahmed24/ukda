import Link from "next/link";

import { SecurityPreferencesCard } from "../../../../components/security-preferences-card";
import { requirePlatformRole } from "../../../../lib/auth/session";
import { getSecurityStatus } from "../../../../lib/security";

export const dynamic = "force-dynamic";

export default async function AdminSecurityPage() {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const statusResult = await getSecurityStatus();
  const isAdmin = session.user.platformRoles.includes("ADMIN");

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Platform security</p>
        <h1>Security status</h1>
        <p className="ukde-muted">
          Controlled-environment posture, deny-by-default egress checks, and
          export gateway state.
        </p>
        <div className="buttonRow">
          <Link className="secondaryButton" href="/admin">
            Back to admin
          </Link>
          <Link className="secondaryButton" href="/admin/operations">
            Operations
          </Link>
          <Link className="secondaryButton" href="/admin/audit">
            Audit viewer
          </Link>
        </div>
      </section>

      {!statusResult.ok || !statusResult.data ? (
        <section className="sectionCard ukde-panel">
          <p className="ukde-muted">
            Security status unavailable: {statusResult.detail ?? "unknown"}
          </p>
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
                {isAdmin ? "ADMIN (full access)" : "AUDITOR (read-only)"}
              </strong>
            </li>
          </ul>
          <p className="ukde-muted">{statusResult.data.egressTestDetail}</p>
          <p className="ukde-muted">
            Outbound allowlist: {statusResult.data.outboundAllowlist.join(", ")}
          </p>
        </section>
      )}

      <SecurityPreferencesCard />
    </main>
  );
}
