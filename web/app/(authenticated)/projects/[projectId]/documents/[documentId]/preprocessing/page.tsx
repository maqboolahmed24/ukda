import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { DocumentPreprocessRunActions } from "../../../../../../../components/document-preprocess-run-actions";
import {
  getProjectDocument,
  getProjectDocumentPreprocessOverview,
  getProjectDocumentPreprocessQuality,
  listProjectDocumentPages,
  listProjectDocumentPreprocessRunPages,
  listProjectDocumentPreprocessRuns
} from "../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../lib/projects";
import {
  projectDocumentPreprocessingComparePath,
  projectDocumentPreprocessingPath,
  projectDocumentPreprocessingQualityPath,
  projectDocumentPreprocessingRunPath,
  projectDocumentViewerPath,
  projectsPath
} from "../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

type PreprocessingTab = "metadata" | "pages" | "runs";

function resolveTab(raw: string | undefined): PreprocessingTab {
  if (raw === "runs" || raw === "metadata") {
    return raw;
  }
  return "pages";
}

function resolveRunTone(status: string): "danger" | "neutral" | "success" | "warning" {
  if (status === "SUCCEEDED") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  return "warning";
}

export default async function ProjectDocumentPreprocessingPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<{ tab?: string }>;
}>) {
  const pageLayoutClassName = "homeLayout homeLayout--preprocessing";
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const tab = resolveTab(query.tab);

  const [documentResult, workspaceResult, overviewResult, runsResult, qualityResult, pagesResult] =
    await Promise.all([
      getProjectDocument(projectId, documentId),
      getProjectWorkspace(projectId),
      getProjectDocumentPreprocessOverview(projectId, documentId),
      listProjectDocumentPreprocessRuns(projectId, documentId, { pageSize: 25 }),
      getProjectDocumentPreprocessQuality(projectId, documentId, { pageSize: 25 }),
      listProjectDocumentPages(projectId, documentId)
    ]);

  if (!documentResult.ok) {
    if (documentResult.status === 404) {
      notFound();
    }
    if (documentResult.status === 403) {
      redirect(projectsPath);
    }
    return (
      <main className={pageLayoutClassName}>
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Preprocessing route unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for preprocessing."
          }
        />
      </main>
    );
  }

  const document = documentResult.data;
  if (!document) {
    notFound();
  }

  const canMutate =
    workspaceResult.ok &&
    workspaceResult.data &&
    (workspaceResult.data.currentUserRole === "PROJECT_LEAD" ||
      workspaceResult.data.currentUserRole === "REVIEWER" ||
      (!workspaceResult.data.isMember && workspaceResult.data.canAccessSettings));

  const runItems =
    runsResult.ok && runsResult.data ? runsResult.data.items : [];
  const runProgress =
    tab === "runs" && runsResult.ok && runsResult.data
      ? await Promise.all(
          runItems.map(async (run) => {
            const pageResult = await listProjectDocumentPreprocessRunPages(
              projectId,
              document.id,
              run.id,
              { pageSize: 500 }
            );
            if (!pageResult.ok || !pageResult.data) {
              return { runId: run.id, processed: 0, total: 0 };
            }
            const total = pageResult.data.items.length;
            const processed = pageResult.data.items.filter(
              (item) => item.status === "SUCCEEDED"
            ).length;
            return { runId: run.id, processed, total };
          })
        )
      : [];
  const runProgressIndex = new Map(
    runProgress.map((entry) => [entry.runId, entry] as const)
  );
  const compareHref =
    runItems.length >= 2
      ? projectDocumentPreprocessingComparePath(
          projectId,
          document.id,
          runItems[1].id,
          runItems[0].id
        )
      : null;

  return (
    <main className={pageLayoutClassName}>
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Preprocessing</p>
        <h2>{document.originalFilename}</h2>
        <p className="ukde-muted">
          Canonical route for preprocessing runs, quality diagnostics, and compare entrypoints.
        </p>
        <div className="buttonRow preprocessingOverviewNav">
          <Link
            className="secondaryButton"
            aria-current={tab === "pages" ? "page" : undefined}
            href={projectDocumentPreprocessingPath(projectId, document.id)}
          >
            Pages
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentPreprocessingQualityPath(projectId, document.id)}
          >
            Quality
          </Link>
          <Link
            className="secondaryButton"
            aria-current={tab === "runs" ? "page" : undefined}
            href={projectDocumentPreprocessingPath(projectId, document.id, {
              tab: "runs"
            })}
          >
            Processing runs
          </Link>
          <Link
            className="secondaryButton"
            aria-current={tab === "metadata" ? "page" : undefined}
            href={projectDocumentPreprocessingPath(projectId, document.id, {
              tab: "metadata"
            })}
          >
            Metadata
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentViewerPath(projectId, document.id, 1)}
          >
            Open viewer
          </Link>
          {compareHref ? (
            <Link className="secondaryButton" href={compareHref}>
              Compare runs
            </Link>
          ) : null}
        </div>
      </section>

      <DocumentPreprocessRunActions
        canMutate={Boolean(canMutate)}
        documentId={document.id}
        projectId={projectId}
      />

      {tab === "runs" ? (
        <section className="sectionCard ukde-panel">
          <h3>Processing runs</h3>
          {!runsResult.ok ? (
            <SectionState
              kind="degraded"
              title="Runs unavailable"
              description={runsResult.detail ?? "Preprocess run list could not be loaded."}
            />
          ) : runItems.length === 0 ? (
            <SectionState
              kind="empty"
              title="No preprocessing runs yet"
              description="Queue the first preprocessing run to initialize run lineage."
            />
          ) : (
            <ul className="timelineList">
              {runItems.map((run) => (
                <li key={run.id}>
                  <div className="auditIntegrityRow">
                    <Link href={projectDocumentPreprocessingRunPath(projectId, document.id, run.id)}>
                      Run {run.id}
                    </Link>
                    <div className="buttonRow">
                      <StatusChip tone={resolveRunTone(run.status)}>{run.status}</StatusChip>
                      {run.isActiveProjection ? (
                        <StatusChip tone="success">ACTIVE</StatusChip>
                      ) : null}
                      {run.isSuperseded ? (
                        <StatusChip tone="neutral">SUPERSEDED</StatusChip>
                      ) : null}
                      {run.isCurrentAttempt ? (
                        <StatusChip tone="warning">CURRENT ATTEMPT</StatusChip>
                      ) : null}
                      {run.isHistoricalAttempt ? (
                        <StatusChip tone="neutral">HISTORICAL</StatusChip>
                      ) : null}
                    </div>
                  </div>
                  <p className="ukde-muted">
                    Profile {run.profileId} · started by {run.createdBy} ·{" "}
                    {run.startedAt ? `started ${new Date(run.startedAt).toISOString()}` : "not started"} ·
                    pages processed {runProgressIndex.get(run.id)?.processed ?? 0}/
                    {runProgressIndex.get(run.id)?.total ?? 0}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {tab === "metadata" ? (
        <section className="sectionCard ukde-panel">
          <h3>Source metadata</h3>
          {!pagesResult.ok ? (
            <SectionState
              kind="degraded"
              title="Source metadata unavailable"
              description={pagesResult.detail ?? "Page metadata could not be loaded."}
            />
          ) : pagesResult.data && pagesResult.data.items.length > 0 ? (
            <ul className="projectMetaList">
              {pagesResult.data.items.slice(0, 10).map((page) => (
                <li key={page.id}>
                  <span>Page {page.pageIndex + 1}</span>
                  <strong>
                    {page.sourceWidth}×{page.sourceHeight} px · {page.sourceDpi ?? "Unknown"} DPI ·{" "}
                    {page.sourceColorMode}
                  </strong>
                </li>
              ))}
            </ul>
          ) : (
            <SectionState
              kind="empty"
              title="No page metadata yet"
              description="Source page metadata appears after ingest extraction materializes pages."
            />
          )}
        </section>
      ) : null}

      {tab === "pages" ? (
        <section className="sectionCard ukde-panel">
          <h3>Pages</h3>
          {!overviewResult.ok ? (
            <SectionState
              kind="degraded"
              title="Overview unavailable"
              description={
                overviewResult.detail ?? "Preprocessing overview could not be loaded."
              }
            />
          ) : !qualityResult.ok ? (
            <SectionState
              kind="degraded"
              title="Quality snapshot unavailable"
              description={qualityResult.detail ?? "Active run pages could not be loaded."}
            />
          ) : !qualityResult.data?.run ? (
            <SectionState
              kind="empty"
              title="No active preprocess run"
              description="Quality and page diagnostics resolve from the active projection when available."
            />
          ) : (
            <>
              {overviewResult.data?.projection ? (
                <ul className="projectMetaList">
                  <li>
                    <span>Active preprocess run</span>
                    <strong>{overviewResult.data.projection.activePreprocessRunId ?? "None"}</strong>
                  </li>
                  <li>
                    <span>Layout basis state</span>
                    <strong>{overviewResult.data.projection.downstreamImpact.layoutBasisState}</strong>
                  </li>
                  <li>
                    <span>Transcription basis state</span>
                    <strong>
                      {overviewResult.data.projection.downstreamImpact.transcriptionBasisState}
                    </strong>
                  </li>
                </ul>
              ) : null}
              <ul className="timelineList">
                {qualityResult.data.items.map((item) => (
                  <li key={item.pageId}>
                    <div className="auditIntegrityRow">
                      <span>Page {item.pageIndex + 1}</span>
                      <StatusChip tone={resolveRunTone(item.status)}>{item.status}</StatusChip>
                    </div>
                    <p className="ukde-muted">
                      Quality gate {item.qualityGateStatus} · warnings{" "}
                      {item.warningsJson.length > 0 ? item.warningsJson.join(", ") : "none"}
                    </p>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      ) : null}
    </main>
  );
}
