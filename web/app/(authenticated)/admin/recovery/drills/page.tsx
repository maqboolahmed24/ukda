import Link from "next/link";

import type { RecoveryDrillScope, RecoveryDrillStatus } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import { listAdminRecoveryDrills } from "../../../../../lib/recovery";
import {
  adminOperationsTimelinesPath,
  adminPath,
  adminRecoveryDrillDetailPath,
  adminRecoveryDrillEvidencePath,
  adminRecoveryDrillsPath,
  adminRecoveryStatusPath,
  withQuery
} from "../../../../../lib/routes";
import { normalizeCursorParam } from "../../../../../lib/url-state";

export const dynamic = "force-dynamic";

const SCOPE_OPTIONS: RecoveryDrillScope[] = [
  "FULL_RECOVERY",
  "QUEUE_REPLAY",
  "STORAGE_INTERRUPT",
  "RESTORE_CLEAN_ENV"
];

function statusTone(status: RecoveryDrillStatus): "success" | "warning" | "danger" | "neutral" | "info" {
  if (status === "SUCCEEDED") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  if (status === "RUNNING") {
    return "info";
  }
  return "warning";
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toISOString();
}

function resolveRunNotice(status: string | undefined): { tone: "success" | "warning"; text: string } | null {
  if (status === "drill-created") {
    return {
      tone: "success",
      text: "Recovery drill run completed and evidence was persisted."
    };
  }
  if (status === "drill-failed") {
    return {
      tone: "warning",
      text: "Recovery drill run request failed."
    };
  }
  if (status === "drill-invalid") {
    return {
      tone: "warning",
      text: "Recovery drill request was invalid. Select a supported scope."
    };
  }
  return null;
}

export default async function AdminRecoveryDrillsPage({
  searchParams
}: Readonly<{
  searchParams: Promise<{
    cursor?: string;
    status?: string;
  }>;
}>) {
  await requirePlatformRole(["ADMIN"]);
  const rawFilters = await searchParams;
  const cursor = normalizeCursorParam(rawFilters.cursor);
  const runNotice = resolveRunNotice(rawFilters.status);
  const drillsResult = await listAdminRecoveryDrills({
    cursor,
    pageSize: 50
  });

  const responseData = drillsResult.ok && drillsResult.data ? drillsResult.data : null;
  const items = responseData?.items ?? [];
  const scopeCatalog = responseData?.scopeCatalog ?? [];

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform recovery"
        meta={<StatusChip tone="danger">ADMIN</StatusChip>}
        secondaryActions={[
          { href: adminRecoveryStatusPath, label: "Recovery status" },
          { href: adminOperationsTimelinesPath, label: "Operations timelines" },
          { href: adminPath, label: "Back to admin" }
        ]}
        summary="Create and review evidence-backed recovery drills with deterministic state transitions."
        title="Recovery drills"
      />

      {runNotice ? (
        <section className="sectionCard ukde-panel">
          <StatusChip tone={runNotice.tone}>{runNotice.text}</StatusChip>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h2>Run recovery drill</h2>
        <form action={`${adminRecoveryDrillsPath}/run`} className="auditFilterForm" method="post">
          <label htmlFor="scope">Scope</label>
          <select defaultValue="FULL_RECOVERY" id="scope" name="scope">
            {SCOPE_OPTIONS.map((scope) => (
              <option key={scope} value={scope}>
                {scope}
              </option>
            ))}
          </select>
          <input name="redirectTo" type="hidden" value={adminRecoveryDrillsPath} />
          <button className="projectPrimaryButton" type="submit">
            Run drill
          </button>
        </form>
        {scopeCatalog.length > 0 ? (
          <p className="ukde-muted">
            Scope catalog:{" "}
            {scopeCatalog.map((item) => `${item.scope} (${item.description})`).join("; ")}
          </p>
        ) : null}
      </section>

      <section className="sectionCard ukde-panel">
        {!drillsResult.ok ? (
          <SectionState
            kind="error"
            title="Recovery drills unavailable"
            description={drillsResult.detail ?? "Unable to load recovery drills."}
          />
        ) : items.length === 0 ? (
          <SectionState
            kind="no-results"
            title="No recovery drills recorded"
            description="Run a recovery drill to capture queue replay, chaos, and restore evidence."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Scope</th>
                  <th>Status</th>
                  <th>Started by</th>
                  <th>Started</th>
                  <th>Finished</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{formatTimestamp(item.createdAt)}</td>
                    <td>
                      <Link href={adminRecoveryDrillDetailPath(item.id)}>{item.scope}</Link>
                    </td>
                    <td>
                      <StatusChip tone={statusTone(item.status)}>{item.status}</StatusChip>
                    </td>
                    <td>{item.startedBy}</td>
                    <td>{formatTimestamp(item.startedAt)}</td>
                    <td>{formatTimestamp(item.finishedAt)}</td>
                    <td>
                      {item.evidenceStorageKey ? (
                        <Link href={adminRecoveryDrillEvidencePath(item.id)}>Open evidence</Link>
                      ) : (
                        "Pending"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {typeof responseData?.nextCursor === "number" ? (
          <div className="buttonRow">
            <Link
              className="secondaryButton"
              href={withQuery(adminRecoveryDrillsPath, {
                cursor: responseData.nextCursor
              })}
            >
              Next page
            </Link>
          </div>
        ) : null}
      </section>
    </main>
  );
}
