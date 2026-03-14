import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { DocumentPreprocessRunActions } from "../../../../../../../../../components/document-preprocess-run-actions";
import { DocumentPreprocessRunStatus } from "../../../../../../../../../components/document-preprocess-run-status";
import {
  getProjectDocument,
  getProjectDocumentActivePreprocessRun,
  getProjectDocumentPreprocessRun,
  listProjectDocumentPages,
  listProjectDocumentPreprocessRunPages,
  listProjectDocumentPreprocessRuns
} from "../../../../../../../../../lib/documents";
import {
  projectDocumentPreprocessingComparePath,
  projectDocumentPreprocessingPath,
  projectDocumentPreprocessingQualityPath,
  projectDocumentPreprocessingRunPath,
  projectsPath
} from "../../../../../../../../../lib/routes";
import { getProjectWorkspace } from "../../../../../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectDocumentPreprocessingRunDetailPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string; runId: string }>;
}>) {
  const { projectId, documentId, runId } = await params;

  const [
    documentResult,
    runResult,
    runPagesResult,
    activeRunResult,
    allRunsResult,
    pagesResult,
    workspaceResult
  ] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectDocumentPreprocessRun(projectId, documentId, runId),
    listProjectDocumentPreprocessRunPages(projectId, documentId, runId, {
      pageSize: 100
    }),
    getProjectDocumentActivePreprocessRun(projectId, documentId),
    listProjectDocumentPreprocessRuns(projectId, documentId, { pageSize: 25 }),
    listProjectDocumentPages(projectId, documentId),
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
          title="Preprocess run route unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for preprocess run detail."
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
  const runPages = runPagesResult.ok && runPagesResult.data ? runPagesResult.data.items : [];
  const documentPages =
    pagesResult.ok && pagesResult.data ? pagesResult.data.items : [];
  const totalWarnings = runPages.reduce(
    (sum, item) => sum + item.warningsJson.length,
    0
  );
  const blockedPages = runPages.filter(
    (item) => item.qualityGateStatus === "BLOCKED"
  ).length;
  const reviewPages = runPages.filter(
    (item) => item.qualityGateStatus === "REVIEW_REQUIRED"
  ).length;
  const passedPages = runPages.filter(
    (item) => item.qualityGateStatus === "PASS"
  ).length;
  const compareTarget =
    allRunsResult.ok && allRunsResult.data
      ? allRunsResult.data.items.find((item) => item.id !== run.id)
      : null;
  const supersedesRunId =
    allRunsResult.ok && allRunsResult.data
      ? (
          allRunsResult.data.items.find(
            (candidate) => candidate.supersededByRunId === run.id
          ) ?? null
        )?.id ?? null
      : null;
  const sourcePagesWithDpi = documentPages.filter(
    (page) => typeof page.sourceDpi === "number" && page.sourceDpi > 0
  );
  const sourceDpiValues = sourcePagesWithDpi.map((page) => page.sourceDpi ?? 0);
  const sourceDpiMin =
    sourceDpiValues.length > 0 ? Math.min(...sourceDpiValues) : null;
  const sourceDpiMax =
    sourceDpiValues.length > 0 ? Math.max(...sourceDpiValues) : null;
  const sourceDpiAvg =
    sourceDpiValues.length > 0
      ? Math.round(
          sourceDpiValues.reduce((sum, value) => sum + value, 0) /
            sourceDpiValues.length
        )
      : null;
  const metricsArtefacts = runPages.filter(
    (item) => Boolean(item.metricsObjectKey) && Boolean(item.metricsSha256)
  ).length;
  const grayArtefacts = runPages.filter(
    (item) => Boolean(item.outputObjectKeyGray) && Boolean(item.sha256Gray)
  ).length;
  const manifestAvailable = Boolean(run.manifestObjectKey && run.manifestSha256);
  const activeProjectionMatchesRun = activeRunId === run.id;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Preprocessing run detail</p>
        <h2>{document.originalFilename}</h2>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentPreprocessingPath(projectId, document.id)}
          >
            Pages
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentPreprocessingQualityPath(projectId, document.id, {
              runId: run.id
            })}
          >
            Quality
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentPreprocessingPath(projectId, document.id, {
              tab: "runs"
            })}
          >
            Processing runs
          </Link>
          {compareTarget ? (
            <Link
              className="secondaryButton"
              href={projectDocumentPreprocessingComparePath(
                projectId,
                document.id,
                compareTarget.id,
                run.id
              )}
            >
              Compare against {compareTarget.id}
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
            <span>Pages with PASS gate</span>
            <strong>{passedPages}</strong>
          </li>
          <li>
            <span>Pages requiring review</span>
            <strong>{reviewPages}</strong>
          </li>
          <li>
            <span>Blocked pages</span>
            <strong>{blockedPages}</strong>
          </li>
          <li>
            <span>Total warnings</span>
            <strong>{totalWarnings}</strong>
          </li>
        </ul>
        <ul className="projectMetaList">
          <li>
            <span>Run ID</span>
            <strong>{run.id}</strong>
          </li>
          <li>
            <span>Attempt</span>
            <strong>{run.attemptNumber}</strong>
          </li>
          <li>
            <span>Profile</span>
            <strong>
              {run.profileLabel || run.profileId} ({run.profileVersion ?? "v1"} / rev{" "}
              {run.profileRevision ?? 1})
            </strong>
          </li>
          <li>
            <span>Status</span>
            <strong>
              <DocumentPreprocessRunStatus
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
            <span>Current projection</span>
            <strong>{activeRunId ?? "No active run"}</strong>
          </li>
          <li>
            <span>Supersedes run</span>
            <strong>{supersedesRunId ?? "No predecessor in supersession chain"}</strong>
          </li>
          <li>
            <span>Manifest integrity</span>
            <strong>{manifestAvailable ? "Persisted and hashed" : "Not persisted"}</strong>
          </li>
          <li>
            <span>Superseded by</span>
            <strong>{run.supersededByRunId ?? "Not superseded"}</strong>
          </li>
        </ul>
      </section>

      <DocumentPreprocessRunActions
        canMutate={Boolean(canMutate)}
        documentId={document.id}
        isActiveProjection={run.isActiveProjection}
        projectId={projectId}
        runId={run.id}
        runStatus={run.status}
      />

      <section className="sectionCard ukde-panel">
        <h3>Provenance and projection contract</h3>
        <ul className="projectMetaList">
          <li>
            <span>Active projection mode</span>
            <strong>EXPLICIT_ACTIVATION</strong>
          </li>
          <li>
            <span>Downstream default consumer</span>
            <strong>Phase 3 layout analysis</strong>
          </li>
          <li>
            <span>This run is active default input</span>
            <strong>{activeProjectionMatchesRun ? "Yes" : "No"}</strong>
          </li>
          <li>
            <span>Layout basis state (if this run is active)</span>
            <strong>{run.downstreamImpact.layoutBasisState}</strong>
          </li>
          <li>
            <span>Layout basis run reference</span>
            <strong>{run.downstreamImpact.layoutBasisRunId ?? "Not started"}</strong>
          </li>
          <li>
            <span>Transcription basis state (if this run is active)</span>
            <strong>{run.downstreamImpact.transcriptionBasisState}</strong>
          </li>
          <li>
            <span>Transcription basis run reference</span>
            <strong>{run.downstreamImpact.transcriptionBasisRunId ?? "Not started"}</strong>
          </li>
          <li>
            <span>Profile params hash (registry)</span>
            <strong>{run.profileParamsHash ?? "Not recorded"}</strong>
          </li>
          <li>
            <span>Run params hash</span>
            <strong>{run.paramsHash}</strong>
          </li>
          <li>
            <span>Manifest object key</span>
            <strong>{run.manifestObjectKey ?? "Not persisted"}</strong>
          </li>
          <li>
            <span>Manifest SHA-256</span>
            <strong>{run.manifestSha256 ?? "Not persisted"}</strong>
          </li>
        </ul>
        <p className="ukde-muted">
          Downstream phases must resolve preprocessing input from the explicitly
          activated run only. Latest successful run inference is not allowed.
        </p>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Source and derived artefact summary</h3>
        <ul className="projectMetaList">
          <li>
            <span>Source pages</span>
            <strong>{documentPages.length}</strong>
          </li>
          <li>
            <span>Source DPI (min/avg/max)</span>
            <strong>
              {sourceDpiMin ?? "n/a"} / {sourceDpiAvg ?? "n/a"} /{" "}
              {sourceDpiMax ?? "n/a"}
            </strong>
          </li>
          <li>
            <span>Gray artefacts with hashes</span>
            <strong>
              {grayArtefacts} / {runPages.length}
            </strong>
          </li>
          <li>
            <span>Metrics artefacts with hashes</span>
            <strong>
              {metricsArtefacts} / {runPages.length}
            </strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Run parameters</h3>
        <details>
          <summary>Expanded parameters</summary>
          <pre>{JSON.stringify(run.paramsJson, null, 2)}</pre>
        </details>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Per-page lineage and results</h3>
        {!runPagesResult.ok ? (
          <SectionState
            kind="degraded"
            title="Run pages unavailable"
            description={runPagesResult.detail ?? "Per-page preprocess results could not be loaded."}
          />
        ) : runPagesResult.data && runPagesResult.data.items.length > 0 ? (
          <ul className="timelineList">
            {runPagesResult.data.items.map((item) => (
              <li key={item.pageId}>
                <div className="auditIntegrityRow">
                  <Link
                    href={projectDocumentPreprocessingRunPath(projectId, document.id, run.id)}
                  >
                    Page {item.pageIndex + 1}
                  </Link>
                  <span>{item.status}</span>
                  <span>{item.qualityGateStatus}</span>
                </div>
                <p className="ukde-muted">
                  Warnings{" "}
                  {item.warningsJson.length > 0 ? item.warningsJson.join(", ") : "none"}
                </p>
                <p className="ukde-muted">
                  Source result run: {item.sourceResultRunId ?? "unknown"} · input hash:{" "}
                  {item.inputSha256 ?? "unknown"}
                </p>
                <p className="ukde-muted">
                  Gray hash: {item.sha256Gray ?? "n/a"} · metrics hash:{" "}
                  {item.metricsSha256 ?? "n/a"}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <SectionState
            kind="empty"
            title="No per-page results recorded"
            description="This run has no page result rows yet."
          />
        )}
      </section>
    </main>
  );
}
