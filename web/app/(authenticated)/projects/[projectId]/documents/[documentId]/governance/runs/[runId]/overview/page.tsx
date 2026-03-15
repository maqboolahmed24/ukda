import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type { GovernanceGenerationStatus, GovernanceReadinessStatus } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import {
  getProjectDocument,
  getProjectDocumentGovernanceRunLedgerStatus,
  getProjectDocumentGovernanceRunOverview
} from "../../../../../../../../../../lib/documents";
import {
  projectDocumentGovernancePath,
  projectDocumentGovernanceRunEventsPath,
  projectDocumentGovernanceRunLedgerPath,
  projectDocumentGovernanceRunManifestPath,
  projectDocumentGovernanceRunOverviewPath,
  projectsPath
} from "../../../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function resolveReadinessTone(
  status: GovernanceReadinessStatus
): "danger" | "neutral" | "success" | "warning" {
  if (status === "READY") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  return "warning";
}

function resolveGenerationTone(
  status: GovernanceGenerationStatus
): "danger" | "neutral" | "success" | "warning" {
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  if (status === "RUNNING") {
    return "warning";
  }
  return "success";
}

export default async function ProjectDocumentGovernanceRunOverviewPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string; runId: string }>;
}>) {
  const { projectId, documentId, runId } = await params;
  const [documentResult, overviewResult, ledgerStatusResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectDocumentGovernanceRunOverview(projectId, documentId, runId),
    getProjectDocumentGovernanceRunLedgerStatus(projectId, documentId, runId)
  ]);

  if (!documentResult.ok || !overviewResult.ok) {
    if (documentResult.status === 404 || overviewResult.status === 404) {
      notFound();
    }
    if (documentResult.status === 403 || overviewResult.status === 403) {
      redirect(projectsPath);
    }
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Governance run unavailable"
          description={
            overviewResult.detail ??
            documentResult.detail ??
            "Governance run overview could not be loaded."
          }
        />
      </main>
    );
  }

  const document = documentResult.data;
  const overview = overviewResult.data;
  if (!document || !overview) {
    notFound();
  }
  const canViewLedger = Boolean(
    ledgerStatusResult.ok && ledgerStatusResult.data
  );

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Governance run</p>
        <h2>{document.originalFilename}</h2>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentGovernancePath(projectId, document.id, {
              runId: runId
            })}
          >
            Governance overview
          </Link>
          <Link
            className="secondaryButton"
            aria-current="page"
            href={projectDocumentGovernanceRunOverviewPath(projectId, document.id, runId)}
          >
            Run overview
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentGovernanceRunManifestPath(projectId, document.id, runId)}
          >
            Manifest
          </Link>
          {canViewLedger ? (
            <Link
              className="secondaryButton"
              href={projectDocumentGovernanceRunLedgerPath(projectId, document.id, runId)}
            >
              Evidence ledger
            </Link>
          ) : null}
          <Link
            className="secondaryButton"
            href={projectDocumentGovernanceRunEventsPath(projectId, document.id, runId)}
          >
            Events
          </Link>
        </div>
        {!canViewLedger ? (
          <p className="ukde-muted">
            Controlled evidence-ledger detail is restricted to administrator and
            auditor roles.
          </p>
        ) : null}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Run status</h3>
        <div className="buttonRow">
          <StatusChip tone={resolveReadinessTone(overview.readiness.status)}>
            {overview.readiness.status}
          </StatusChip>
          <StatusChip tone={resolveGenerationTone(overview.readiness.generationStatus)}>
            {overview.readiness.generationStatus}
          </StatusChip>
          <StatusChip tone="neutral">{overview.run.runStatus}</StatusChip>
        </div>
        <ul className="projectMetaList">
          <li>
            <span>Run ID</span>
            <strong>{overview.run.runId}</strong>
          </li>
          <li>
            <span>Review status</span>
            <strong>{overview.run.reviewStatus ?? "Not reviewed"}</strong>
          </li>
          <li>
            <span>Approved snapshot key</span>
            <strong>{overview.run.approvedSnapshotKey ?? "Not pinned"}</strong>
          </li>
          <li>
            <span>Approved snapshot hash</span>
            <strong>{overview.run.approvedSnapshotSha256 ?? "Not pinned"}</strong>
          </li>
          <li>
            <span>Run output status</span>
            <strong>{overview.run.runOutputStatus ?? "Unavailable"}</strong>
          </li>
          <li>
            <span>Ready manifest ID</span>
            <strong>{overview.readiness.manifestId ?? "Not set"}</strong>
          </li>
          <li>
            <span>Ready ledger ID</span>
            <strong>{overview.readiness.ledgerId ?? "Not set"}</strong>
          </li>
          <li>
            <span>Ledger verification status</span>
            <strong>{overview.readiness.ledgerVerificationStatus}</strong>
          </li>
          <li>
            <span>Manifest attempts</span>
            <strong>{overview.manifestAttempts.length}</strong>
          </li>
          <li>
            <span>Ledger attempts</span>
            <strong>{overview.ledgerAttempts.length}</strong>
          </li>
          <li>
            <span>Updated at</span>
            <strong>{new Date(overview.readiness.updatedAt).toISOString()}</strong>
          </li>
        </ul>
      </section>
    </main>
  );
}
