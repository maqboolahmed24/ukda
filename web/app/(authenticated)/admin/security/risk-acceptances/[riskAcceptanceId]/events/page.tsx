import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../../../lib/auth/session";
import {
  getAdminRiskAcceptance,
  listAdminRiskAcceptanceEvents
} from "../../../../../../../lib/security";
import {
  adminSecurityRiskAcceptanceDetailPath,
  adminSecurityRiskAcceptancesPath
} from "../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toISOString();
}

export default async function AdminRiskAcceptanceEventsPage({
  params
}: Readonly<{
  params: Promise<{ riskAcceptanceId: string }>;
}>) {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const { riskAcceptanceId } = await params;
  const [detailResult, eventsResult] = await Promise.all([
    getAdminRiskAcceptance(riskAcceptanceId),
    listAdminRiskAcceptanceEvents(riskAcceptanceId)
  ]);

  if (!detailResult.ok || !detailResult.data) {
    return (
      <main className="homeLayout">
        <PageHeader
          eyebrow="Platform security"
          secondaryActions={[
            { href: adminSecurityRiskAcceptancesPath, label: "Back to risk acceptances" }
          ]}
          summary="Risk-acceptance event retrieval failed for this identifier."
          title="Risk acceptance events"
        />
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Risk acceptance unavailable"
            description={detailResult.detail ?? "Unable to load risk acceptance detail."}
          />
        </section>
      </main>
    );
  }

  const acceptance = detailResult.data;
  const events = eventsResult.ok && eventsResult.data ? eventsResult.data.items : [];

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
          {
            href: adminSecurityRiskAcceptanceDetailPath(acceptance.id),
            label: "Acceptance detail"
          },
          { href: adminSecurityRiskAcceptancesPath, label: "Back to risk acceptances" }
        ]}
        summary="Append-only risk-acceptance event history."
        title={`${acceptance.id} events`}
      />

      <section className="sectionCard ukde-panel">
        {!eventsResult.ok ? (
          <SectionState
            kind="error"
            title="Risk-acceptance events unavailable"
            description={eventsResult.detail ?? "Unable to load risk-acceptance events."}
          />
        ) : events.length === 0 ? (
          <SectionState
            kind="no-results"
            title="No events recorded"
            description="No risk-acceptance lifecycle events are recorded for this acceptance."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Event ID</th>
                  <th>Type</th>
                  <th>Actor</th>
                  <th>Created</th>
                  <th>Expires at</th>
                  <th>Review date</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {events.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.eventType}</td>
                    <td>{item.actorUserId ?? "system"}</td>
                    <td>{formatTimestamp(item.createdAt)}</td>
                    <td>{formatTimestamp(item.expiresAt)}</td>
                    <td>{formatTimestamp(item.reviewDate)}</td>
                    <td>{item.reason ?? "n/a"}</td>
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
