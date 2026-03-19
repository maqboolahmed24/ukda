import Link from "next/link";

import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../../lib/auth/session";
import {
  getAdminRiskAcceptance,
  listAdminRiskAcceptanceEvents
} from "../../../../../../lib/security";
import {
  adminSecurityRiskAcceptanceEventsPath,
  adminSecurityRiskAcceptancesPath
} from "../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toISOString();
}

function resolveNotice(status: string | undefined): { tone: "success" | "warning"; text: string } | null {
  if (status === "created") {
    return { tone: "success", text: "Risk acceptance created." };
  }
  if (status === "renewed") {
    return { tone: "success", text: "Risk acceptance renewed." };
  }
  if (status === "review-scheduled") {
    return { tone: "success", text: "Review schedule updated." };
  }
  if (status === "revoked") {
    return { tone: "success", text: "Risk acceptance revoked." };
  }
  if (status === "action-failed") {
    return { tone: "warning", text: "Risk acceptance action failed." };
  }
  if (status === "action-invalid") {
    return { tone: "warning", text: "Risk acceptance action was invalid." };
  }
  return null;
}

export default async function AdminRiskAcceptanceDetailPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ riskAcceptanceId: string }>;
  searchParams: Promise<{ status?: string }>;
}>) {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const { riskAcceptanceId } = await params;
  const { status } = await searchParams;
  const notice = resolveNotice(status);

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
          summary="Risk-acceptance detail retrieval failed for this identifier."
          title="Risk acceptance detail"
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
  const eventCount = eventsResult.ok && eventsResult.data ? eventsResult.data.items.length : 0;
  const canMutate = roleMode.isAdmin && acceptance.status !== "REVOKED";

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
          { href: adminSecurityRiskAcceptancesPath, label: "Back to risk acceptances" },
          {
            href: adminSecurityRiskAcceptanceEventsPath(acceptance.id),
            label: `Events (${eventCount})`
          }
        ]}
        summary="Risk-acceptance projection detail with admin-only renew/review/revoke actions."
        title={acceptance.id}
      />

      {notice ? (
        <section className="sectionCard ukde-panel">
          <StatusChip tone={notice.tone}>{notice.text}</StatusChip>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <ul className="projectMetaList">
          <li>
            <span>Acceptance ID</span>
            <strong>{acceptance.id}</strong>
          </li>
          <li>
            <span>Finding ID</span>
            <strong>{acceptance.findingId}</strong>
          </li>
          <li>
            <span>Status</span>
            <strong>{acceptance.status}</strong>
          </li>
          <li>
            <span>Approved by</span>
            <strong>{acceptance.approvedBy}</strong>
          </li>
          <li>
            <span>Accepted at</span>
            <strong>{formatTimestamp(acceptance.acceptedAt)}</strong>
          </li>
          <li>
            <span>Expires at</span>
            <strong>{formatTimestamp(acceptance.expiresAt)}</strong>
          </li>
          <li>
            <span>Review date</span>
            <strong>{formatTimestamp(acceptance.reviewDate)}</strong>
          </li>
          <li>
            <span>Revoked by</span>
            <strong>{acceptance.revokedBy ?? "n/a"}</strong>
          </li>
          <li>
            <span>Revoked at</span>
            <strong>{formatTimestamp(acceptance.revokedAt)}</strong>
          </li>
        </ul>
        <p className="ukde-muted">{acceptance.justification}</p>
      </section>

      {canMutate ? (
        <>
          <section className="sectionCard ukde-panel">
            <h2>Renew acceptance</h2>
            <form
              action={`${adminSecurityRiskAcceptancesPath}/${encodeURIComponent(acceptance.id)}/renew`}
              className="auditFilterForm"
              method="post"
            >
              <label htmlFor="renewJustification">Justification</label>
              <textarea
                id="renewJustification"
                name="justification"
                required
                rows={4}
                defaultValue={acceptance.justification}
              />
              <label htmlFor="renewExpiresAt">Expires at (optional)</label>
              <input id="renewExpiresAt" name="expiresAt" type="datetime-local" />
              <label htmlFor="renewReviewDate">Review date (optional)</label>
              <input id="renewReviewDate" name="reviewDate" type="datetime-local" />
              <input
                name="redirectTo"
                type="hidden"
                value={`${adminSecurityRiskAcceptancesPath}/${encodeURIComponent(acceptance.id)}`}
              />
              <button className="projectPrimaryButton" type="submit">
                Renew acceptance
              </button>
            </form>
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Schedule review</h2>
            <form
              action={`${adminSecurityRiskAcceptancesPath}/${encodeURIComponent(acceptance.id)}/review-schedule`}
              className="auditFilterForm"
              method="post"
            >
              <label htmlFor="reviewDate">Review date</label>
              <input id="reviewDate" name="reviewDate" required type="datetime-local" />
              <label htmlFor="reviewReason">Reason (optional)</label>
              <input id="reviewReason" name="reason" type="text" />
              <input
                name="redirectTo"
                type="hidden"
                value={`${adminSecurityRiskAcceptancesPath}/${encodeURIComponent(acceptance.id)}`}
              />
              <button className="secondaryButton" type="submit">
                Schedule review
              </button>
            </form>
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Revoke acceptance</h2>
            <form
              action={`${adminSecurityRiskAcceptancesPath}/${encodeURIComponent(acceptance.id)}/revoke`}
              className="auditFilterForm"
              method="post"
            >
              <label htmlFor="revokeReason">Reason</label>
              <textarea id="revokeReason" name="reason" required rows={3} />
              <input
                name="redirectTo"
                type="hidden"
                value={`${adminSecurityRiskAcceptancesPath}/${encodeURIComponent(acceptance.id)}`}
              />
              <button className="projectDangerButton" type="submit">
                Revoke acceptance
              </button>
            </form>
          </section>
        </>
      ) : (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Read-only view"
            description={
              roleMode.isAdmin
                ? "This acceptance is already revoked."
                : "Auditors can view acceptance detail and events, but cannot mutate lifecycle state."
            }
          />
        </section>
      )}
    </main>
  );
}
