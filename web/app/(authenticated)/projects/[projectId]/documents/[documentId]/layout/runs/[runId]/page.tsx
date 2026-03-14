import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { DocumentLayoutRunActions } from "../../../../../../../../../components/document-layout-run-actions";
import { DocumentLayoutRunStatus } from "../../../../../../../../../components/document-layout-run-status";
import {
  getProjectDocument,
  getProjectDocumentActiveLayoutRun,
  getProjectDocumentLayoutRun,
  listProjectDocumentLayoutRunPages,
  listProjectDocumentLayoutRuns
} from "../../../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../../../lib/projects";
import {
  projectDocumentLayoutPath,
  projectDocumentLayoutRunPath,
  projectDocumentLayoutWorkspacePath,
  projectsPath
} from "../../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function formatMetricCount(value: unknown): string {
  if (typeof value === "number") {
    return String(Math.round(value));
  }
  if (typeof value === "string" && value.trim().length > 0) {
    return value.trim();
  }
  return "N/A";
}

export default async function ProjectDocumentLayoutRunDetailPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string; runId: string }>;
}>) {
  const { projectId, documentId, runId } = await params;
  const [documentResult, runResult, pagesResult, activeRunResult, runsResult, workspaceResult] =
    await Promise.all([
      getProjectDocument(projectId, documentId),
      getProjectDocumentLayoutRun(projectId, documentId, runId),
      listProjectDocumentLayoutRunPages(projectId, documentId, runId, {
        pageSize: 500
      }),
      getProjectDocumentActiveLayoutRun(projectId, documentId),
      listProjectDocumentLayoutRuns(projectId, documentId, { pageSize: 50 }),
      getProjectWorkspace(projectId)
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
          title="Layout run route unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for layout run detail."
          }
        />
      </main>
    );
  }

  if (!runResult.ok) {
    if (runResult.status === 404) {
      notFound();
    }
    if (runResult.status === 403) {
      redirect(projectsPath);
    }
  }

  const document = documentResult.data;
  const run = runResult.ok ? runResult.data : null;
  if (!document || !run) {
    notFound();
  }

  const canMutate =
    workspaceResult.ok &&
    workspaceResult.data &&
    (workspaceResult.data.currentUserRole === "PROJECT_LEAD" ||
      workspaceResult.data.currentUserRole === "REVIEWER" ||
      (!workspaceResult.data.isMember && workspaceResult.data.canAccessSettings));

  const activeRunId =
    activeRunResult.ok && activeRunResult.data?.run
      ? activeRunResult.data.run.id
      : null;
  const activeProjection =
    activeRunResult.ok && activeRunResult.data?.projection
      ? activeRunResult.data.projection
      : null;
  const runPages = pagesResult.ok && pagesResult.data ? pagesResult.data.items : [];
  const completedPages = runPages.filter((item) => item.status === "SUCCEEDED").length;
  const recallRescuePages = runPages.filter(
    (item) => item.pageRecallStatus === "NEEDS_RESCUE"
  ).length;
  const manualReviewPages = runPages.filter(
    (item) => item.pageRecallStatus === "NEEDS_MANUAL_REVIEW"
  ).length;
  const compareTarget =
    runsResult.ok && runsResult.data
      ? runsResult.data.items.find((candidate) => candidate.id !== run.id) ?? null
      : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Layout run detail</p>
        <h2>{document.originalFilename}</h2>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentLayoutPath(projectId, document.id)}
          >
            Layout overview
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentLayoutPath(projectId, document.id, {
              tab: "triage",
              runId: run.id
            })}
          >
            Open triage
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentLayoutWorkspacePath(projectId, document.id, {
              page: 1,
              runId: run.id
            })}
          >
            Open workspace
          </Link>
          {compareTarget ? (
            <Link
              className="secondaryButton"
              href={projectDocumentLayoutRunPath(projectId, document.id, compareTarget.id)}
            >
              Open {compareTarget.id}
            </Link>
          ) : null}
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Run summary</h3>
        <div className="buttonRow">
          <StatusChip tone={run.isActiveProjection ? "success" : "neutral"}>
            {run.isActiveProjection ? "ACTIVE PROJECTION" : "NON-ACTIVE"}
          </StatusChip>
          <StatusChip tone={run.isSuperseded ? "neutral" : "warning"}>
            {run.isSuperseded ? "SUPERSEDED" : "UNSUPERSEDED"}
          </StatusChip>
          <StatusChip tone={run.isCurrentAttempt ? "warning" : "neutral"}>
            {run.isCurrentAttempt ? "CURRENT ATTEMPT" : "HISTORICAL ATTEMPT"}
          </StatusChip>
        </div>
        <ul className="projectMetaList">
          <li>
            <span>Run ID</span>
            <strong>{run.id}</strong>
          </li>
          <li>
            <span>Input preprocess run</span>
            <strong>{run.inputPreprocessRunId}</strong>
          </li>
          <li>
            <span>Status</span>
            <strong>
              <DocumentLayoutRunStatus
                documentId={document.id}
                initialStatus={run.status}
                projectId={projectId}
                runId={run.id}
              />
            </strong>
          </li>
          <li>
            <span>Pipeline version</span>
            <strong>{run.pipelineVersion}</strong>
          </li>
          <li>
            <span>Params hash</span>
            <strong>{run.paramsHash}</strong>
          </li>
          <li>
            <span>Created by</span>
            <strong>{run.createdBy}</strong>
          </li>
          <li>
            <span>Created at</span>
            <strong>{new Date(run.createdAt).toISOString()}</strong>
          </li>
          <li>
            <span>Started at</span>
            <strong>
              {run.startedAt ? new Date(run.startedAt).toISOString() : "Not started"}
            </strong>
          </li>
          <li>
            <span>Finished at</span>
            <strong>
              {run.finishedAt ? new Date(run.finishedAt).toISOString() : "Not finished"}
            </strong>
          </li>
        </ul>
        <ul className="projectMetaList">
          <li>
            <span>Total pages</span>
            <strong>{runPages.length}</strong>
          </li>
          <li>
            <span>Completed pages</span>
            <strong>{completedPages}</strong>
          </li>
          <li>
            <span>Needs rescue</span>
            <strong>{recallRescuePages}</strong>
          </li>
          <li>
            <span>Needs manual review</span>
            <strong>{manualReviewPages}</strong>
          </li>
          <li>
            <span>Active projection match</span>
            <strong>{activeRunId === run.id ? "Yes" : "No"}</strong>
          </li>
          <li>
            <span>Downstream transcription state</span>
            <strong>
              {activeProjection?.downstreamTranscriptionState ?? "NOT_STARTED"}
            </strong>
          </li>
          <li>
            <span>Downstream invalidated reason</span>
            <strong>
              {activeProjection?.downstreamTranscriptionInvalidatedReason ??
                "None"}
            </strong>
          </li>
        </ul>
      </section>

      <DocumentLayoutRunActions
        activationGate={run.activationGate ?? null}
        canMutate={Boolean(canMutate)}
        documentId={document.id}
        inputPreprocessRunId={run.inputPreprocessRunId}
        isActiveProjection={run.isActiveProjection}
        projectId={projectId}
        runId={run.id}
        runStatus={run.status}
      />

      <section className="sectionCard ukde-panel">
        <h3>Activation gate</h3>
        {!run.activationGate ? (
          <SectionState
            kind="degraded"
            title="Activation gate unavailable"
            description="Run readiness checks could not be resolved."
          />
        ) : run.activationGate.eligible ? (
          <p className="ukde-muted">
            Eligible for activation. If activated now, downstream transcription state
            becomes{" "}
            <strong>
              {run.activationGate.downstreamImpact.transcriptionStateAfterActivation}
            </strong>
            .
          </p>
        ) : (
          <>
            <p className="ukde-muted">
              Activation is blocked by {run.activationGate.blockerCount} gate check(s).
            </p>
            <ul className="timelineList">
              {run.activationGate.blockers.map((blocker) => (
                <li key={blocker.code}>
                  <strong>{blocker.code}</strong> - {blocker.message}
                  {blocker.pageNumbers.length > 0
                    ? ` (pages ${blocker.pageNumbers.join(", ")})`
                    : ""}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Page results</h3>
        {!pagesResult.ok ? (
          <SectionState
            kind="degraded"
            title="Run pages unavailable"
            description={pagesResult.detail ?? "Page-level layout results could not be loaded."}
          />
        ) : runPages.length === 0 ? (
          <SectionState
            kind="empty"
            title="No page rows yet"
            description="Layout page rows appear when the run seeds per-page scaffolding."
          />
        ) : (
          <div className="qualityTriageTableWrap">
            <table className="ukde-data-table qualityTriageTable">
              <caption className="sr-only">Layout run page rows</caption>
              <thead>
                <tr>
                  <th scope="col">Page</th>
                  <th scope="col">Status</th>
                  <th scope="col">Recall</th>
                  <th scope="col">Regions</th>
                  <th scope="col">Lines</th>
                  <th scope="col">Coverage</th>
                  <th scope="col">Workspace</th>
                </tr>
              </thead>
              <tbody>
                {runPages.map((page) => (
                  <tr key={page.pageId}>
                    <td>Page {page.pageIndex + 1}</td>
                    <td>{page.status}</td>
                    <td>{page.pageRecallStatus}</td>
                    <td>
                      {formatMetricCount(
                        page.metricsJson.region_count ??
                          page.metricsJson.regions_detected
                      )}
                    </td>
                    <td>
                      {formatMetricCount(
                        page.metricsJson.line_count ??
                          page.metricsJson.lines_detected
                      )}
                    </td>
                    <td>
                      {typeof page.metricsJson.coverage_percent === "number"
                        ? `${page.metricsJson.coverage_percent.toFixed(1)}%`
                        : "N/A"}
                    </td>
                    <td>
                      <Link
                        className="secondaryButton"
                        href={projectDocumentLayoutWorkspacePath(projectId, document.id, {
                          page: page.pageIndex + 1,
                          runId: run.id
                        })}
                      >
                        Open
                      </Link>
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
