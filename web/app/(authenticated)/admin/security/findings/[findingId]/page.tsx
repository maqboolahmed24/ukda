import Link from "next/link";

import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../../lib/auth/session";
import {
  getAdminSecurityFinding,
  listAdminRiskAcceptances
} from "../../../../../../lib/security";
import {
  adminSecurityFindingsPath,
  adminSecurityRiskAcceptanceDetailPath,
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
  if (status === "accept-created") {
    return {
      tone: "success",
      text: "Risk acceptance created."
    };
  }
  if (status === "accept-failed") {
    return {
      tone: "warning",
      text: "Risk acceptance create failed."
    };
  }
  if (status === "accept-invalid") {
    return {
      tone: "warning",
      text: "Provide justification and an expiry or review date."
    };
  }
  return null;
}

export default async function AdminSecurityFindingDetailPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ findingId: string }>;
  searchParams: Promise<{ status?: string }>;
}>) {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const { findingId } = await params;
  const { status } = await searchParams;
  const notice = resolveNotice(status);

  const [findingResult, acceptancesResult] = await Promise.all([
    getAdminSecurityFinding(findingId),
    listAdminRiskAcceptances({ findingId })
  ]);

  if (!findingResult.ok || !findingResult.data) {
    return (
      <main className="homeLayout">
        <PageHeader
          eyebrow="Platform security"
          secondaryActions={[
            { href: adminSecurityFindingsPath, label: "Back to findings" },
            { href: adminSecurityRiskAcceptancesPath, label: "Risk acceptances" }
          ]}
          summary="Security finding detail retrieval failed for this finding identifier."
          title="Security finding detail"
        />
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Security finding unavailable"
            description={findingResult.detail ?? "Unable to load security finding detail."}
          />
        </section>
      </main>
    );
  }

  const finding = findingResult.data;
  const acceptances =
    acceptancesResult.ok && acceptancesResult.data ? acceptancesResult.data.items : [];
  const canCreateAcceptance = roleMode.isAdmin && finding.status !== "RESOLVED";

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
          { href: adminSecurityFindingsPath, label: "Back to findings" },
          { href: adminSecurityRiskAcceptancesPath, label: "Risk acceptances" }
        ]}
        summary="Security finding detail with linked risk acceptances and remediation context."
        title={finding.id}
      />

      {notice ? (
        <section className="sectionCard ukde-panel">
          <StatusChip tone={notice.tone}>{notice.text}</StatusChip>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <ul className="projectMetaList">
          <li>
            <span>Finding ID</span>
            <strong>{finding.id}</strong>
          </li>
          <li>
            <span>Severity</span>
            <strong>{finding.severity}</strong>
          </li>
          <li>
            <span>Status</span>
            <strong>{finding.status}</strong>
          </li>
          <li>
            <span>Owner</span>
            <strong>{finding.ownerUserId}</strong>
          </li>
          <li>
            <span>Source</span>
            <strong>{finding.source}</strong>
          </li>
          <li>
            <span>Opened</span>
            <strong>{formatTimestamp(finding.openedAt)}</strong>
          </li>
          <li>
            <span>Resolved</span>
            <strong>{formatTimestamp(finding.resolvedAt)}</strong>
          </li>
        </ul>
        {finding.resolutionSummary ? (
          <p className="ukde-muted">{finding.resolutionSummary}</p>
        ) : null}
      </section>

      {canCreateAcceptance ? (
        <section className="sectionCard ukde-panel">
          <h2>Create risk acceptance</h2>
          <form
            action={`${adminSecurityFindingsPath}/${encodeURIComponent(finding.id)}/accept`}
            className="auditFilterForm"
            method="post"
          >
            <label htmlFor="justification">Justification</label>
            <textarea
              id="justification"
              name="justification"
              required
              rows={4}
              placeholder="Document why acceptance is required and what mitigation is in place."
            />
            <label htmlFor="expiresAt">Expires at (optional)</label>
            <input id="expiresAt" name="expiresAt" type="datetime-local" />
            <label htmlFor="reviewDate">Review date (optional)</label>
            <input id="reviewDate" name="reviewDate" type="datetime-local" />
            <input
              name="redirectTo"
              type="hidden"
              value={`${adminSecurityFindingsPath}/${encodeURIComponent(finding.id)}`}
            />
            <button className="projectPrimaryButton" type="submit">
              Create acceptance
            </button>
          </form>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h2>Linked risk acceptances</h2>
        {acceptances.length === 0 ? (
          <SectionState
            kind="no-results"
            title="No risk acceptances"
            description="No risk acceptances are currently linked to this finding."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Acceptance</th>
                  <th>Status</th>
                  <th>Approved by</th>
                  <th>Accepted</th>
                  <th>Expires</th>
                  <th>Review date</th>
                </tr>
              </thead>
              <tbody>
                {acceptances.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link href={adminSecurityRiskAcceptanceDetailPath(item.id)}>{item.id}</Link>
                    </td>
                    <td>{item.status}</td>
                    <td>{item.approvedBy}</td>
                    <td>{formatTimestamp(item.acceptedAt)}</td>
                    <td>{formatTimestamp(item.expiresAt)}</td>
                    <td>{formatTimestamp(item.reviewDate)}</td>
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
