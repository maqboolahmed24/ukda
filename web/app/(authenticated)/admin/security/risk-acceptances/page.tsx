import Link from "next/link";

import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import {
  listAdminRiskAcceptances,
  listAdminSecurityFindings
} from "../../../../../lib/security";
import {
  adminPath,
  adminSecurityFindingDetailPath,
  adminSecurityFindingsPath,
  adminSecurityRiskAcceptanceDetailPath,
  adminSecurityRiskAcceptancesPath
} from "../../../../../lib/routes";

export const dynamic = "force-dynamic";

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toISOString();
}

function parseStatus(
  value: string | undefined
): "ACTIVE" | "EXPIRED" | "REVOKED" | undefined {
  if (value === "ACTIVE" || value === "EXPIRED" || value === "REVOKED") {
    return value;
  }
  return undefined;
}

export default async function AdminSecurityRiskAcceptancesPage({
  searchParams
}: Readonly<{
  searchParams: Promise<{
    findingId?: string;
    status?: string;
  }>;
}>) {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const filters = await searchParams;
  const findingId =
    typeof filters.findingId === "string" && filters.findingId.trim()
      ? filters.findingId.trim()
      : undefined;
  const statusFilter = parseStatus(filters.status);

  const [acceptancesResult, findingsResult] = await Promise.all([
    listAdminRiskAcceptances({
      findingId,
      status: statusFilter
    }),
    listAdminSecurityFindings()
  ]);
  const acceptances =
    acceptancesResult.ok && acceptancesResult.data
      ? acceptancesResult.data.items
      : [];
  const findings =
    findingsResult.ok && findingsResult.data ? findingsResult.data.items : [];

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
          { href: adminSecurityFindingsPath, label: "Security findings" },
          { href: adminPath, label: "Back to admin" }
        ]}
        summary="Risk-acceptance list and filters across findings, with append-only lifecycle detail links."
        title="Risk acceptances"
      />

      <section className="sectionCard ukde-panel">
        <h2>Filters</h2>
        <form action={adminSecurityRiskAcceptancesPath} className="auditFilterForm" method="get">
          <label htmlFor="findingId">Finding</label>
          <select defaultValue={findingId ?? ""} id="findingId" name="findingId">
            <option value="">All findings</option>
            {findings.map((finding) => (
              <option key={finding.id} value={finding.id}>
                {finding.id}
              </option>
            ))}
          </select>
          <label htmlFor="status">Status</label>
          <select defaultValue={statusFilter ?? ""} id="status" name="status">
            <option value="">All statuses</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="EXPIRED">EXPIRED</option>
            <option value="REVOKED">REVOKED</option>
          </select>
          <button className="projectPrimaryButton" type="submit">
            Apply filters
          </button>
          <Link className="secondaryButton" href={adminSecurityRiskAcceptancesPath}>
            Reset
          </Link>
        </form>
      </section>

      <section className="sectionCard ukde-panel">
        {!acceptancesResult.ok ? (
          <SectionState
            kind="error"
            title="Risk acceptances unavailable"
            description={acceptancesResult.detail ?? "Unable to load risk acceptances."}
          />
        ) : acceptances.length === 0 ? (
          <SectionState
            kind="no-results"
            title="No risk acceptances found"
            description="Adjust filters or create an acceptance from a finding detail route."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Acceptance</th>
                  <th>Finding</th>
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
                    <td>
                      <Link href={adminSecurityFindingDetailPath(item.findingId)}>
                        {item.findingId}
                      </Link>
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
