import Link from "next/link";

import type { RecoveryDrillStatusResponse } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { AdminRecoveryDrillStatusPoller } from "../../../../../../components/admin-recovery-drill-status-poller";
import { PageHeader } from "../../../../../../components/page-header";
import { requirePlatformRole } from "../../../../../../lib/auth/session";
import {
  getAdminRecoveryDrill,
  getAdminRecoveryDrillStatus
} from "../../../../../../lib/recovery";
import {
  adminRecoveryDrillEvidencePath,
  adminRecoveryDrillsPath,
  adminRecoveryStatusPath
} from "../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toISOString();
}

function resolveNotice(status: string | undefined): { tone: "success" | "warning"; text: string } | null {
  if (status === "cancel-complete") {
    return {
      tone: "success",
      text: "Recovery drill was canceled."
    };
  }
  if (status === "cancel-failed") {
    return {
      tone: "warning",
      text: "Recovery drill cancel request failed."
    };
  }
  if (status === "cancel-invalid") {
    return {
      tone: "warning",
      text: "Recovery drill cancel request was invalid."
    };
  }
  return null;
}

export default async function AdminRecoveryDrillDetailPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ drillId: string }>;
  searchParams: Promise<{ status?: string }>;
}>) {
  await requirePlatformRole(["ADMIN"]);
  const { drillId } = await params;
  const { status } = await searchParams;
  const notice = resolveNotice(status);
  const [detailResult, statusResult] = await Promise.all([
    getAdminRecoveryDrill(drillId),
    getAdminRecoveryDrillStatus(drillId)
  ]);

  if (!detailResult.ok || !detailResult.data) {
    return (
      <main className="homeLayout">
        <PageHeader
          eyebrow="Platform recovery"
          secondaryActions={[
            { href: adminRecoveryDrillsPath, label: "Back to recovery drills" },
            { href: adminRecoveryStatusPath, label: "Recovery status" }
          ]}
          summary="Recovery drill detail retrieval failed for this drill identifier."
          title="Recovery drill detail"
        />
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Recovery drill unavailable"
            description={detailResult.detail ?? "Unable to load recovery drill detail."}
          />
        </section>
      </main>
    );
  }

  const detail = detailResult.data;
  const statusPayload: RecoveryDrillStatusResponse = statusResult.ok && statusResult.data
    ? statusResult.data
    : {
        drillId: detail.drill.id,
        status: detail.drill.status,
        startedAt: detail.drill.startedAt,
        finishedAt: detail.drill.finishedAt,
        canceledAt: detail.drill.canceledAt
      };
  const cancelable = statusPayload.status === "QUEUED" || statusPayload.status === "RUNNING";

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform recovery"
        meta={<StatusChip tone="danger">ADMIN</StatusChip>}
        secondaryActions={[
          { href: adminRecoveryDrillsPath, label: "Back to recovery drills" },
          { href: adminRecoveryStatusPath, label: "Recovery status" }
        ]}
        summary="Drill detail polls status endpoint for live progress and exposes evidence links."
        title={detail.drill.id}
      />

      {notice ? (
        <section className="sectionCard ukde-panel">
          <StatusChip tone={notice.tone}>{notice.text}</StatusChip>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h2>Drill status</h2>
        <AdminRecoveryDrillStatusPoller drillId={detail.drill.id} initialStatus={statusPayload} />
      </section>

      <section className="sectionCard ukde-panel">
        <h2>Drill metadata</h2>
        <ul className="projectMetaList">
          <li>
            <span>Drill ID</span>
            <strong>{detail.drill.id}</strong>
          </li>
          <li>
            <span>Scope</span>
            <strong>{detail.drill.scope}</strong>
          </li>
          <li>
            <span>Started by</span>
            <strong>{detail.drill.startedBy}</strong>
          </li>
          <li>
            <span>Created</span>
            <strong>{formatTimestamp(detail.drill.createdAt)}</strong>
          </li>
          <li>
            <span>Started</span>
            <strong>{formatTimestamp(detail.drill.startedAt)}</strong>
          </li>
          <li>
            <span>Finished</span>
            <strong>{formatTimestamp(detail.drill.finishedAt)}</strong>
          </li>
          <li>
            <span>Canceled by</span>
            <strong>{detail.drill.canceledBy ?? "n/a"}</strong>
          </li>
          <li>
            <span>Canceled at</span>
            <strong>{formatTimestamp(detail.drill.canceledAt)}</strong>
          </li>
          <li>
            <span>Evidence storage key</span>
            <strong>{detail.drill.evidenceStorageKey ?? "n/a"}</strong>
          </li>
          <li>
            <span>Evidence SHA-256</span>
            <strong>{detail.drill.evidenceStorageSha256 ?? "n/a"}</strong>
          </li>
        </ul>
        {detail.drill.failureReason ? (
          <SectionState kind="degraded" title="Failure reason" description={detail.drill.failureReason} />
        ) : null}
      </section>

      <section className="sectionCard ukde-panel">
        <div className="buttonRow">
          {detail.hasEvidence ? (
            <Link className="secondaryButton" href={adminRecoveryDrillEvidencePath(detail.drill.id)}>
              Open evidence
            </Link>
          ) : (
            <StatusChip tone="warning">Evidence pending</StatusChip>
          )}
          {cancelable ? (
            <form action={`${adminRecoveryDrillsPath}/${encodeURIComponent(detail.drill.id)}/cancel`} method="post">
              <input
                name="redirectTo"
                type="hidden"
                value={`${adminRecoveryDrillsPath}/${encodeURIComponent(detail.drill.id)}`}
              />
              <button className="projectDangerButton" type="submit">
                Cancel drill
              </button>
            </form>
          ) : null}
        </div>
      </section>
    </main>
  );
}
