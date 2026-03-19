import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import { getAdminRecoveryStatus } from "../../../../../lib/recovery";
import {
  adminOperationsPath,
  adminOperationsTimelinesPath,
  adminPath,
  adminRecoveryDrillsPath
} from "../../../../../lib/routes";

export const dynamic = "force-dynamic";

function modeTone(mode: string): "success" | "warning" | "danger" | "neutral" {
  if (mode === "ACTIVE") {
    return "warning";
  }
  if (mode === "STANDBY") {
    return "success";
  }
  return "neutral";
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toISOString();
}

export default async function AdminRecoveryStatusPage() {
  await requirePlatformRole(["ADMIN"]);
  const statusResult = await getAdminRecoveryStatus();

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform recovery"
        meta={<StatusChip tone="danger">ADMIN</StatusChip>}
        secondaryActions={[
          { href: adminRecoveryDrillsPath, label: "Recovery drills" },
          { href: adminOperationsTimelinesPath, label: "Operations timelines" },
          { href: adminOperationsPath, label: "Operations overview" },
          { href: adminPath, label: "Back to admin" }
        ]}
        summary="Current degraded-mode posture and queue/restore recovery readiness."
        title="Recovery status"
      />

      {!statusResult.ok || !statusResult.data ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Recovery status unavailable"
            description={statusResult.detail ?? "Unable to load recovery status."}
          />
        </section>
      ) : (
        <>
          <section className="sectionCard ukde-panel">
            <div className="auditIntegrityRow">
              <StatusChip tone={modeTone(statusResult.data.mode)}>
                {statusResult.data.mode}
              </StatusChip>
              <StatusChip tone={statusResult.data.degraded ? "warning" : "success"}>
                {statusResult.data.degraded ? "DEGRADED" : "HEALTHY"}
              </StatusChip>
            </div>
            <p className="ukde-muted">{statusResult.data.summary}</p>
            <ul className="projectMetaList">
              <li>
                <span>Active drills</span>
                <strong>{statusResult.data.activeDrillCount}</strong>
              </li>
              <li>
                <span>Queue depth</span>
                <strong>{statusResult.data.queueDepth}</strong>
              </li>
              <li>
                <span>Dead-letter jobs</span>
                <strong>{statusResult.data.deadLetterCount}</strong>
              </li>
              <li>
                <span>Replay eligible jobs</span>
                <strong>{statusResult.data.replayEligibleCount}</strong>
              </li>
              <li>
                <span>Storage root</span>
                <strong>{statusResult.data.storageRoot}</strong>
              </li>
              <li>
                <span>Model artifact root</span>
                <strong>{statusResult.data.modelArtifactRoot}</strong>
              </li>
            </ul>
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Latest drill</h2>
            {!statusResult.data.latestDrill ? (
              <SectionState
                kind="no-results"
                title="No recovery drills recorded"
                description="Run a recovery drill to populate evidence-backed status history."
              />
            ) : (
              <ul className="projectMetaList">
                <li>
                  <span>Drill ID</span>
                  <strong>{statusResult.data.latestDrill.id}</strong>
                </li>
                <li>
                  <span>Scope</span>
                  <strong>{statusResult.data.latestDrill.scope}</strong>
                </li>
                <li>
                  <span>Status</span>
                  <strong>{statusResult.data.latestDrill.status}</strong>
                </li>
                <li>
                  <span>Started</span>
                  <strong>{formatTimestamp(statusResult.data.latestDrill.startedAt)}</strong>
                </li>
                <li>
                  <span>Finished</span>
                  <strong>{formatTimestamp(statusResult.data.latestDrill.finishedAt)}</strong>
                </li>
              </ul>
            )}
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Supported drill scopes</h2>
            <div className="auditTableWrap">
              <table className="auditTable">
                <thead>
                  <tr>
                    <th>Scope</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {statusResult.data.supportedScopes.map((scope) => (
                    <tr key={scope.scope}>
                      <td>{scope.scope}</td>
                      <td>{scope.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
