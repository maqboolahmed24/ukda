import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type {
  GovernanceArtifactStatus,
  GovernanceGenerationStatus,
  GovernanceReadinessStatus
} from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { DocumentPipelineLiveStatus } from "../../../../../../../components/document-pipeline-live-status";
import {
  getProjectDocument,
  getProjectDocumentGovernanceOverview,
  getProjectDocumentGovernanceRunLedgerStatus,
  getProjectDocumentGovernanceRunManifestStatus,
  listProjectDocumentGovernanceRuns
} from "../../../../../../../lib/documents";
import {
  projectDocumentGovernancePath,
  projectDocumentGovernanceRunEventsPath,
  projectDocumentGovernanceRunLedgerPath,
  projectDocumentGovernanceRunManifestPath,
  projectDocumentGovernanceRunOverviewPath,
  projectsPath
} from "../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

type GovernanceTab = "overview" | "runs" | "manifest" | "ledger";

function resolveTab(raw: string | undefined): GovernanceTab {
  if (raw === "runs" || raw === "manifest" || raw === "ledger") {
    return raw;
  }
  return "overview";
}

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

function resolveArtifactTone(
  status: GovernanceArtifactStatus
): "danger" | "neutral" | "success" | "warning" {
  if (status === "SUCCEEDED") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED" || status === "UNAVAILABLE") {
    return "neutral";
  }
  return "warning";
}

export default async function ProjectDocumentGovernancePage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<{ runId?: string; tab?: string }>;
}>) {
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const tab = resolveTab(query.tab);
  const requestedRunId =
    typeof query.runId === "string" && query.runId.trim().length > 0
      ? query.runId.trim()
      : null;

  const [documentResult, overviewResult, runsResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectDocumentGovernanceOverview(projectId, documentId),
    listProjectDocumentGovernanceRuns(projectId, documentId)
  ]);

  if (!documentResult.ok) {
    if (documentResult.status === 404) {
      notFound();
    }
    if (documentResult.status === 403) {
      redirect(projectsPath);
    }
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Governance route unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for governance routes."
          }
        />
      </main>
    );
  }

  if (!overviewResult.ok || !runsResult.ok) {
    if (overviewResult.status === 403 || runsResult.status === 403) {
      redirect(projectsPath);
    }
    if (overviewResult.status === 404 || runsResult.status === 404) {
      notFound();
    }
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Governance data unavailable"
          description={
            overviewResult.detail ??
            runsResult.detail ??
            "Governance overview and run listings could not be loaded."
          }
        />
      </main>
    );
  }

  const document = documentResult.data;
  const overview = overviewResult.data;
  const runs = runsResult.data?.items ?? [];
  if (!document || !overview) {
    notFound();
  }

  const selectedRunId = requestedRunId ?? overview.activeRunId ?? (runs[0]?.runId ?? null);
  const selectedRun = selectedRunId
    ? runs.find((item) => item.runId === selectedRunId) ?? null
    : null;

  const [manifestStatusResult, ledgerStatusResult] = selectedRunId
    ? await Promise.all([
        getProjectDocumentGovernanceRunManifestStatus(projectId, document.id, selectedRunId),
        getProjectDocumentGovernanceRunLedgerStatus(projectId, document.id, selectedRunId)
      ])
    : [null, null];

  const canViewLedger = Boolean(
    ledgerStatusResult && ledgerStatusResult.ok && ledgerStatusResult.data
  );
  const showLedgerTab = canViewLedger;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Governance</p>
        <h2>{document.originalFilename}</h2>
        <p className="ukde-muted">
          Phase 6 governance routes expose screening-safe manifest lineage and controlled ledger
          state for approved privacy runs.
        </p>
        {!canViewLedger && selectedRunId ? (
          <p className="ukde-muted">
            Controlled evidence-ledger detail is restricted to administrator and auditor
            roles.
          </p>
        ) : null}
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            aria-current={tab === "overview" ? "page" : undefined}
            href={projectDocumentGovernancePath(projectId, document.id, {
              runId: selectedRunId
            })}
          >
            Overview
          </Link>
          <Link
            className="secondaryButton"
            aria-current={tab === "runs" ? "page" : undefined}
            href={projectDocumentGovernancePath(projectId, document.id, {
              tab: "runs",
              runId: selectedRunId
            })}
          >
            Runs
          </Link>
          {selectedRunId ? (
            <Link
              className="secondaryButton"
              aria-current={tab === "manifest" ? "page" : undefined}
              href={projectDocumentGovernancePath(projectId, document.id, {
                tab: "manifest",
                runId: selectedRunId
              })}
            >
              Manifest
            </Link>
          ) : (
            <button className="secondaryButton" type="button" disabled>
              Manifest
            </button>
          )}
          {showLedgerTab && selectedRunId ? (
            <Link
              className="secondaryButton"
              aria-current={tab === "ledger" ? "page" : undefined}
              href={projectDocumentGovernancePath(projectId, document.id, {
                tab: "ledger",
                runId: selectedRunId
              })}
            >
              Evidence ledger
            </Link>
          ) : null}
        </div>
      </section>

      <DocumentPipelineLiveStatus documentId={document.id} projectId={projectId} />

      {tab === "overview" ? (
        <section className="sectionCard ukde-panel">
          <h3>Overview</h3>
          <ul className="projectMetaList">
            <li>
              <span>Active run</span>
              <strong>{overview.activeRunId ?? "None"}</strong>
            </li>
            <li>
              <span>Total runs</span>
              <strong>{overview.totalRuns}</strong>
            </li>
            <li>
              <span>Approved runs</span>
              <strong>{overview.approvedRuns}</strong>
            </li>
            <li>
              <span>Ready runs</span>
              <strong>{overview.readyRuns}</strong>
            </li>
            <li>
              <span>Pending runs</span>
              <strong>{overview.pendingRuns}</strong>
            </li>
            <li>
              <span>Failed runs</span>
              <strong>{overview.failedRuns}</strong>
            </li>
            <li>
              <span>Latest run</span>
              <strong>{overview.latestRunId ?? "None"}</strong>
            </li>
            <li>
              <span>Latest ready run</span>
              <strong>{overview.latestReadyRunId ?? "None"}</strong>
            </li>
          </ul>
          {overview.latestRun ? (
            <div className="buttonRow">
              <StatusChip tone={resolveReadinessTone(overview.latestRun.readinessStatus)}>
                {overview.latestRun.readinessStatus}
              </StatusChip>
              <StatusChip tone={resolveGenerationTone(overview.latestRun.generationStatus)}>
                {overview.latestRun.generationStatus}
              </StatusChip>
              <StatusChip tone="neutral">{overview.latestRun.runStatus}</StatusChip>
            </div>
          ) : (
            <SectionState
              kind="loading"
              title="No governance runs yet"
              description="Governance state appears after a privacy run reaches approved reviewed output."
            />
          )}
        </section>
      ) : null}

      {tab === "runs" ? (
        <section className="sectionCard ukde-panel">
          <h3>Runs</h3>
          {runs.length === 0 ? (
            <SectionState
              kind="loading"
              title="No governance runs to list"
              description="When approved privacy runs exist, this table will show run-level readiness and lineage."
            />
          ) : (
            <ul className="projectMetaList">
              {runs.map((run) => (
                <li key={run.runId}>
                  <span>{run.runId}</span>
                  <strong>
                    <StatusChip tone={resolveReadinessTone(run.readinessStatus)}>
                      {run.readinessStatus}
                    </StatusChip>
                    {" "}
                    <StatusChip tone={resolveGenerationTone(run.generationStatus)}>
                      {run.generationStatus}
                    </StatusChip>
                    {" "}
                    <Link
                      href={projectDocumentGovernanceRunOverviewPath(
                        projectId,
                        document.id,
                        run.runId
                      )}
                    >
                      Open run
                    </Link>
                    {" · "}
                    <Link
                      href={projectDocumentGovernanceRunEventsPath(
                        projectId,
                        document.id,
                        run.runId
                      )}
                    >
                      Events
                    </Link>
                    {" · "}
                    <Link
                      href={projectDocumentGovernanceRunManifestPath(
                        projectId,
                        document.id,
                        run.runId
                      )}
                    >
                      Manifest
                    </Link>
                    {canViewLedger ? (
                      <>
                        {" · "}
                        <Link
                          href={projectDocumentGovernanceRunLedgerPath(
                            projectId,
                            document.id,
                            run.runId
                          )}
                        >
                          Evidence ledger
                        </Link>
                      </>
                    ) : null}
                  </strong>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {tab === "manifest" ? (
        <section className="sectionCard ukde-panel">
          <h3>Manifest</h3>
          {!selectedRunId ? (
            <SectionState
              kind="degraded"
              title="Manifest unavailable"
              description="Select a governance run to inspect manifest status and attempt lineage."
            />
          ) : !manifestStatusResult || !manifestStatusResult.ok || !manifestStatusResult.data ? (
            <SectionState
              kind="degraded"
              title="Manifest status unavailable"
              description={
                manifestStatusResult?.detail ??
                "Manifest status could not be loaded for this governance run."
              }
            />
          ) : (
            <>
              <div className="buttonRow">
                <StatusChip tone={resolveArtifactTone(manifestStatusResult.data.status)}>
                  {manifestStatusResult.data.status}
                </StatusChip>
                <StatusChip tone={resolveReadinessTone(manifestStatusResult.data.readinessStatus)}>
                  {manifestStatusResult.data.readinessStatus}
                </StatusChip>
                <StatusChip tone={resolveGenerationTone(manifestStatusResult.data.generationStatus)}>
                  {manifestStatusResult.data.generationStatus}
                </StatusChip>
              </div>
              <ul className="projectMetaList">
                <li>
                  <span>Run ID</span>
                  <strong>{selectedRun?.runId ?? selectedRunId}</strong>
                </li>
                <li>
                  <span>Attempt count</span>
                  <strong>{manifestStatusResult.data.attemptCount}</strong>
                </li>
                <li>
                  <span>Ready manifest ID</span>
                  <strong>{manifestStatusResult.data.readyManifestId ?? "Not set"}</strong>
                </li>
                <li>
                  <span>Latest manifest hash</span>
                  <strong>{manifestStatusResult.data.latestManifestSha256 ?? "Not generated"}</strong>
                </li>
              </ul>
              <div className="buttonRow">
                <Link
                  className="secondaryButton"
                  href={projectDocumentGovernanceRunManifestPath(projectId, document.id, selectedRunId)}
                >
                  Open manifest detail
                </Link>
                <Link
                  className="secondaryButton"
                  href={projectDocumentGovernanceRunEventsPath(projectId, document.id, selectedRunId)}
                >
                  Open run events
                </Link>
              </div>
            </>
          )}
        </section>
      ) : null}

      {tab === "ledger" ? (
        <section className="sectionCard ukde-panel">
          <h3>Evidence ledger</h3>
          {!selectedRunId ? (
            <SectionState
              kind="degraded"
              title="Evidence ledger unavailable"
              description="Select a governance run to inspect controlled evidence-ledger state."
            />
          ) : !canViewLedger || !ledgerStatusResult || !ledgerStatusResult.data ? (
            <SectionState
              kind="degraded"
              title="Ledger access restricted"
              description="Evidence-ledger reads are controlled-only and available to administrator or auditor roles."
            />
          ) : (
            <>
              <div className="buttonRow">
                <StatusChip tone={resolveArtifactTone(ledgerStatusResult.data.status)}>
                  {ledgerStatusResult.data.status}
                </StatusChip>
                <StatusChip tone={resolveReadinessTone(ledgerStatusResult.data.readinessStatus)}>
                  {ledgerStatusResult.data.readinessStatus}
                </StatusChip>
                <StatusChip tone="neutral">
                  {ledgerStatusResult.data.ledgerVerificationStatus}
                </StatusChip>
              </div>
              <ul className="projectMetaList">
                <li>
                  <span>Run ID</span>
                  <strong>{selectedRun?.runId ?? selectedRunId}</strong>
                </li>
                <li>
                  <span>Attempt count</span>
                  <strong>{ledgerStatusResult.data.attemptCount}</strong>
                </li>
                <li>
                  <span>Ready ledger ID</span>
                  <strong>{ledgerStatusResult.data.readyLedgerId ?? "Not set"}</strong>
                </li>
                <li>
                  <span>Latest ledger hash</span>
                  <strong>{ledgerStatusResult.data.latestLedgerSha256 ?? "Not generated"}</strong>
                </li>
              </ul>
              <div className="buttonRow">
                <Link
                  className="secondaryButton"
                  href={projectDocumentGovernanceRunLedgerPath(projectId, document.id, selectedRunId)}
                >
                  Open ledger detail
                </Link>
                <Link
                  className="secondaryButton"
                  href={projectDocumentGovernanceRunEventsPath(projectId, document.id, selectedRunId)}
                >
                  Open run events
                </Link>
              </div>
            </>
          )}
        </section>
      ) : null}
    </main>
  );
}
