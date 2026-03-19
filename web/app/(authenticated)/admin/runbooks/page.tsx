import Link from "next/link";

import type { AdminRunbook } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../components/page-header";
import { requirePlatformRole } from "../../../../lib/auth/session";
import { listAdminRunbooks } from "../../../../lib/launch-operations";
import {
  adminIncidentStatusPath,
  adminIncidentsPath,
  adminPath,
  adminRunbookDetailPath
} from "../../../../lib/routes";

export const dynamic = "force-dynamic";

function statusTone(
  status: AdminRunbook["status"]
): "success" | "warning" | "neutral" | "info" {
  if (status === "ACTIVE") {
    return "success";
  }
  if (status === "REVIEW_REQUIRED") {
    return "warning";
  }
  if (status === "DRAFT") {
    return "info";
  }
  return "neutral";
}

function formatTimestamp(value: string): string {
  return new Date(value).toISOString();
}

export default async function AdminRunbooksPage() {
  await requirePlatformRole(["ADMIN"]);
  const result = await listAdminRunbooks();
  const items = result.ok && result.data ? result.data.items : [];

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform operations"
        meta={<StatusChip tone="danger">ADMIN</StatusChip>}
        secondaryActions={[
          { href: adminIncidentsPath, label: "Incidents" },
          { href: adminIncidentStatusPath, label: "Incident status" },
          { href: adminPath, label: "Back to admin" }
        ]}
        summary="Canonical launch and rollback runbooks with ownership and review posture."
        title="Runbooks"
      />

      <section className="sectionCard ukde-panel">
        {!result.ok ? (
          <SectionState
            kind="error"
            title="Runbooks unavailable"
            description={result.detail ?? "Unable to load runbook records."}
          />
        ) : items.length === 0 ? (
          <SectionState
            kind="no-results"
            title="No runbooks registered"
            description="Launch catalog does not currently include any runbook records."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Runbook</th>
                  <th>Status</th>
                  <th>Owner</th>
                  <th>Last reviewed</th>
                  <th>Storage key</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link href={adminRunbookDetailPath(item.id)}>{item.title}</Link>
                      <p className="ukde-muted">
                        {item.id} · {item.slug}
                      </p>
                    </td>
                    <td>
                      <StatusChip tone={statusTone(item.status)}>{item.status}</StatusChip>
                    </td>
                    <td>{item.ownerUserId}</td>
                    <td>{formatTimestamp(item.lastReviewedAt)}</td>
                    <td>
                      <code>{item.storageKey}</code>
                    </td>
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
