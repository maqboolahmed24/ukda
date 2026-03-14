import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { DocumentTranscriptionRunActions } from "../../../../../../../../../components/document-transcription-run-actions";
import { DocumentTranscriptionRunStatus } from "../../../../../../../../../components/document-transcription-run-status";
import {
  getProjectDocument,
  getProjectDocumentActiveTranscriptionRun,
  getProjectDocumentTranscriptionRun,
  listProjectDocumentTranscriptionRunPageLines,
  listProjectDocumentTranscriptionRunPageTokens,
  listProjectDocumentTranscriptionRunPages,
  listProjectDocumentTranscriptionRuns
} from "../../../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../../../lib/projects";
import {
  projectDocumentTranscriptionComparePath,
  projectDocumentTranscriptionPath,
  projectDocumentTranscriptionRunPath,
  projectDocumentTranscriptionWorkspacePath,
  projectsPath
} from "../../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

export default async function ProjectDocumentTranscriptionRunDetailPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string; runId: string }>;
}>) {
  const { projectId, documentId, runId } = await params;
  const [
    documentResult,
    runResult,
    pagesResult,
    activeRunResult,
    runsResult,
    workspaceResult
  ] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectDocumentTranscriptionRun(projectId, documentId, runId),
    listProjectDocumentTranscriptionRunPages(projectId, documentId, runId, {
      pageSize: 500
    }),
    getProjectDocumentActiveTranscriptionRun(projectId, documentId),
    listProjectDocumentTranscriptionRuns(projectId, documentId, { pageSize: 50 }),
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
          title="Transcription run route unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for transcription run detail."
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

  const runPages = pagesResult.ok && pagesResult.data ? pagesResult.data.items : [];
  const perPageRows = await Promise.all(
    runPages.map(async (pageRow) => {
      const [linesResult, tokensResult] = await Promise.all([
        listProjectDocumentTranscriptionRunPageLines(
          projectId,
          document.id,
          run.id,
          pageRow.pageId
        ),
        listProjectDocumentTranscriptionRunPageTokens(
          projectId,
          document.id,
          run.id,
          pageRow.pageId
        )
      ]);
      return {
        pageId: pageRow.pageId,
        lineCount:
          linesResult.ok && linesResult.data ? linesResult.data.items.length : 0,
        tokenCount:
          tokensResult.ok && tokensResult.data ? tokensResult.data.items.length : 0,
        anchorRefreshRequired:
          linesResult.ok && linesResult.data
            ? linesResult.data.items.filter(
                (line) => line.tokenAnchorStatus !== "CURRENT"
              ).length
            : 0,
        lowConfidenceLines:
          linesResult.ok && linesResult.data
            ? linesResult.data.items.filter(
                (line) =>
                  typeof line.confLine === "number" && line.confLine < 0.75
              ).length
            : 0
      };
    })
  );
  const perPageIndex = new Map(perPageRows.map((row) => [row.pageId, row] as const));
  const lineCount = perPageRows.reduce((sum, row) => sum + row.lineCount, 0);
  const tokenCount = perPageRows.reduce((sum, row) => sum + row.tokenCount, 0);
  const anchorRefreshRequired = perPageRows.reduce(
    (sum, row) => sum + row.anchorRefreshRequired,
    0
  );
  const lowConfidenceLines = perPageRows.reduce(
    (sum, row) => sum + row.lowConfidenceLines,
    0
  );
  const activeRunId =
    activeRunResult.ok && activeRunResult.data?.run
      ? activeRunResult.data.run.id
      : null;
  const projection =
    activeRunResult.ok && activeRunResult.data?.projection
      ? activeRunResult.data.projection
      : null;
  const compareTarget =
    runsResult.ok && runsResult.data
      ? runsResult.data.items.find((candidate) => candidate.id !== run.id) ?? null
      : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Transcription run detail</p>
        <h2>{document.originalFilename}</h2>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentTranscriptionPath(projectId, document.id)}
          >
            Transcription overview
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentTranscriptionPath(projectId, document.id, {
              tab: "triage",
              runId: run.id
            })}
          >
            Open triage
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentTranscriptionWorkspacePath(projectId, document.id, {
              page: 1,
              runId: run.id
            })}
          >
            Open workspace
          </Link>
          {compareTarget ? (
            <Link
              className="secondaryButton"
              href={projectDocumentTranscriptionComparePath(
                projectId,
                document.id,
                run.id,
                compareTarget.id,
                { page: 1 }
              )}
            >
              Compare {run.id} vs {compareTarget.id}
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
            <span>Input layout run</span>
            <strong>{run.inputLayoutRunId}</strong>
          </li>
          <li>
            <span>Status</span>
            <strong>
              <DocumentTranscriptionRunStatus
                documentId={document.id}
                initialStatus={run.status}
                projectId={projectId}
                runId={run.id}
              />
            </strong>
          </li>
          <li>
            <span>Engine</span>
            <strong>{run.engine}</strong>
          </li>
          <li>
            <span>Model ID</span>
            <strong>{run.modelId}</strong>
          </li>
          <li>
            <span>Pipeline version</span>
            <strong>{run.pipelineVersion}</strong>
          </li>
          <li>
            <span>Attempt number</span>
            <strong>{run.attemptNumber}</strong>
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
            <span>Line count</span>
            <strong>{lineCount}</strong>
          </li>
          <li>
            <span>Token count</span>
            <strong>{tokenCount}</strong>
          </li>
          <li>
            <span>Low-confidence lines</span>
            <strong>{lowConfidenceLines}</strong>
          </li>
          <li>
            <span>Anchor refresh required</span>
            <strong>{anchorRefreshRequired}</strong>
          </li>
          <li>
            <span>Active projection match</span>
            <strong>{activeRunId === run.id ? "Yes" : "No"}</strong>
          </li>
          <li>
            <span>Redaction state</span>
            <strong>{projection?.downstreamRedactionState ?? "NOT_STARTED"}</strong>
          </li>
          <li>
            <span>Redaction invalidated reason</span>
            <strong>{projection?.downstreamRedactionInvalidatedReason ?? "None"}</strong>
          </li>
        </ul>
      </section>

      <DocumentTranscriptionRunActions
        canMutate={Boolean(canMutate)}
        documentId={document.id}
        inputLayoutRunId={run.inputLayoutRunId}
        inputPreprocessRunId={run.inputPreprocessRunId}
        isActiveProjection={run.isActiveProjection}
        projectId={projectId}
        runId={run.id}
        runStatus={run.status}
      />

      <section className="sectionCard ukde-panel">
        <h3>Per-page summary</h3>
        {runPages.length === 0 ? (
          <SectionState
            kind="empty"
            title="No page rows yet"
            description="Run page rows appear as transcription page jobs are materialized."
          />
        ) : (
          <ul className="timelineList">
            {runPages.map((pageRow) => {
              const aggregates = perPageIndex.get(pageRow.pageId);
              return (
                <li key={pageRow.pageId}>
                  <div className="auditIntegrityRow">
                    <span>Page {pageRow.pageIndex + 1}</span>
                    <StatusChip
                      tone={
                        pageRow.status === "SUCCEEDED"
                          ? "success"
                          : pageRow.status === "FAILED"
                            ? "danger"
                            : pageRow.status === "CANCELED"
                              ? "neutral"
                              : "warning"
                      }
                    >
                      {pageRow.status}
                    </StatusChip>
                  </div>
                  <p className="ukde-muted">
                    Lines {aggregates?.lineCount ?? 0} · tokens {aggregates?.tokenCount ?? 0} ·
                    low confidence {aggregates?.lowConfidenceLines ?? 0} · anchor refresh{" "}
                    {aggregates?.anchorRefreshRequired ?? 0}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
