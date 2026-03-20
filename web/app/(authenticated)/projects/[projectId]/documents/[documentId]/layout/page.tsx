import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { DocumentLayoutRunActions } from "../../../../../../../components/document-layout-run-actions";
import { DocumentLayoutTriageSurface } from "../../../../../../../components/document-layout-triage-surface";
import { DocumentPipelineLiveStatus } from "../../../../../../../components/document-pipeline-live-status";
import {
  getProjectDocument,
  getProjectDocumentLayoutRun,
  getProjectDocumentLayoutOverview,
  listProjectDocumentLayoutRunPages,
  listProjectDocumentLayoutRuns
} from "../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../lib/projects";
import {
  projectDocumentLayoutPath,
  projectDocumentLayoutRunPath,
  projectDocumentLayoutWorkspacePath,
  projectDocumentViewerPath,
  projectsPath
} from "../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

type LayoutTab = "overview" | "runs" | "triage";

function resolveTab(raw: string | undefined): LayoutTab {
  if (raw === "runs" || raw === "triage") {
    return raw;
  }
  return "overview";
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

export default async function ProjectDocumentLayoutPage({
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

  const [documentResult, workspaceResult, overviewResult, runsResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectWorkspace(projectId),
    getProjectDocumentLayoutOverview(projectId, documentId),
    listProjectDocumentLayoutRuns(projectId, documentId, { pageSize: 50 })
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
          title="Layout route unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for layout analysis."
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

  const runs = runsResult.ok && runsResult.data ? runsResult.data.items : [];
  const activeRunId =
    overviewResult.ok && overviewResult.data?.activeRun
      ? overviewResult.data.activeRun.id
      : null;
  const selectedRunId = requestedRunId ?? activeRunId ?? (runs[0]?.id ?? null);
  const selectedRunResult =
    selectedRunId !== null
      ? await getProjectDocumentLayoutRun(projectId, document.id, selectedRunId)
      : null;
  const selectedRun =
    selectedRunResult && selectedRunResult.ok && selectedRunResult.data
      ? selectedRunResult.data
      : selectedRunId !== null
        ? runs.find((run) => run.id === selectedRunId) ?? null
        : null;

  const triageResult =
    selectedRunId !== null
      ? await listProjectDocumentLayoutRunPages(projectId, document.id, selectedRunId, {
          pageSize: 500
        })
      : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Layout analysis</p>
        <h2>{document.originalFilename}</h2>
        <p className="ukde-muted">
          Canonical route family for layout overview, page triage, and run lineage.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            aria-current={tab === "overview" ? "page" : undefined}
            href={projectDocumentLayoutPath(projectId, document.id, {
              runId: selectedRunId
            })}
          >
            Layout overview
          </Link>
          <Link
            className="secondaryButton"
            aria-current={tab === "triage" ? "page" : undefined}
            href={projectDocumentLayoutPath(projectId, document.id, {
              tab: "triage",
              runId: selectedRunId
            })}
          >
            Page triage
          </Link>
          <Link
            className="secondaryButton"
            aria-current={tab === "runs" ? "page" : undefined}
            href={projectDocumentLayoutPath(projectId, document.id, {
              tab: "runs",
              runId: selectedRunId
            })}
          >
            Runs
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentViewerPath(projectId, document.id, 1)}
          >
            Open viewer
          </Link>
          {selectedRunId ? (
            <Link
              className="secondaryButton"
              href={projectDocumentLayoutWorkspacePath(projectId, document.id, {
                page: 1,
                runId: selectedRunId
              })}
            >
              Open workspace
            </Link>
          ) : null}
        </div>
      </section>

      <DocumentPipelineLiveStatus documentId={document.id} projectId={projectId} />

      <DocumentLayoutRunActions
        activationGate={selectedRun?.activationGate ?? null}
        canMutate={Boolean(canMutate)}
        documentId={document.id}
        inputPreprocessRunId={selectedRun?.inputPreprocessRunId}
        isActiveProjection={selectedRun?.isActiveProjection}
        projectId={projectId}
        runId={selectedRun?.id}
        runStatus={selectedRun?.status}
      />

      {tab === "overview" ? (
        <section className="sectionCard ukde-panel">
          <h3>Layout overview</h3>
          {!overviewResult.ok ? (
            <SectionState
              kind="degraded"
              title="Layout overview unavailable"
              description={overviewResult.detail ?? "Layout summary could not be loaded."}
            />
          ) : (
            <>
              <ul className="projectMetaList">
                <li>
                  <span>Active run</span>
                  <strong>{overviewResult.data?.activeRun?.id ?? "None"}</strong>
                </li>
                <li>
                  <span>Latest run</span>
                  <strong>{overviewResult.data?.latestRun?.id ?? "None"}</strong>
                </li>
                <li>
                  <span>Total runs</span>
                  <strong>{overviewResult.data?.totalRuns ?? 0}</strong>
                </li>
                <li>
                  <span>Page count</span>
                  <strong>{overviewResult.data?.pageCount ?? 0}</strong>
                </li>
                <li>
                  <span>Downstream transcription state</span>
                  <strong>
                    {overviewResult.data?.projection?.downstreamTranscriptionState ??
                      "NOT_STARTED"}
                  </strong>
                </li>
                <li>
                  <span>Downstream invalidated reason</span>
                  <strong>
                    {overviewResult.data?.projection
                      ?.downstreamTranscriptionInvalidatedReason ?? "None"}
                  </strong>
                </li>
              </ul>
              <ul className="projectMetaList">
                <li>
                  <span>Regions detected</span>
                  <strong>{overviewResult.data?.summary.regionsDetected ?? "Not available"}</strong>
                </li>
                <li>
                  <span>Lines detected</span>
                  <strong>{overviewResult.data?.summary.linesDetected ?? "Not available"}</strong>
                </li>
                <li>
                  <span>Pages with issues</span>
                  <strong>{overviewResult.data?.summary.pagesWithIssues ?? 0}</strong>
                </li>
                <li>
                  <span>Coverage percent</span>
                  <strong>
                    {typeof overviewResult.data?.summary.coveragePercent === "number"
                      ? `${overviewResult.data.summary.coveragePercent.toFixed(1)}%`
                      : "Not available"}
                  </strong>
                </li>
                <li>
                  <span>Structure confidence</span>
                  <strong>
                    {typeof overviewResult.data?.summary.structureConfidence === "number"
                      ? overviewResult.data.summary.structureConfidence.toFixed(4)
                      : "Not available"}
                  </strong>
                </li>
              </ul>
              {selectedRun ? (
                <div className="buttonRow">
                  <Link
                    className="secondaryButton"
                    href={projectDocumentLayoutRunPath(projectId, document.id, selectedRun.id)}
                  >
                    View run details
                  </Link>
                </div>
              ) : null}
            </>
          )}
        </section>
      ) : null}

      {tab === "triage" ? (
        <section className="sectionCard ukde-panel">
          <h3>Page triage</h3>
          {selectedRunId === null ? (
            <SectionState
              kind="empty"
              title="No layout run selected"
              description="Queue or activate a layout run to open page triage."
            />
          ) : triageResult === null || !triageResult.ok || !triageResult.data ? (
            <SectionState
              kind="degraded"
              title="Triage rows unavailable"
              description={
                triageResult?.detail ?? "Page-level layout results could not be loaded."
              }
            />
          ) : (
            <DocumentLayoutTriageSurface
              documentId={document.id}
              items={triageResult.data.items}
              projectId={projectId}
              runId={selectedRunId}
            />
          )}
        </section>
      ) : null}

      {tab === "runs" ? (
        <section className="sectionCard ukde-panel">
          <h3>Layout runs</h3>
          {!runsResult.ok ? (
            <SectionState
              kind="degraded"
              title="Runs unavailable"
              description={runsResult.detail ?? "Layout run list could not be loaded."}
            />
          ) : runs.length === 0 ? (
            <SectionState
              kind="empty"
              title="No layout runs yet"
              description="Run layout analysis to initialize segmentation run lineage."
            />
          ) : (
            <ul className="timelineList">
              {runs.map((run) => (
                <li key={run.id}>
                  <div className="auditIntegrityRow">
                    <Link href={projectDocumentLayoutRunPath(projectId, document.id, run.id)}>
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
                    </div>
                  </div>
                  <p className="ukde-muted">
                    Input preprocess run {run.inputPreprocessRunId} · created by{" "}
                    {run.createdBy}
                  </p>
                  {selectedRun && selectedRun.id === run.id ? (
                    <p className="ukde-muted">
                      {selectedRun.activationGate?.eligible
                        ? "Activation gate: eligible."
                        : `Activation gate blockers: ${
                            selectedRun.activationGate?.blockerCount ?? 0
                          }.`}
                    </p>
                  ) : null}
                  <div className="buttonRow">
                    <Link
                      className="secondaryButton"
                      href={projectDocumentLayoutWorkspacePath(projectId, document.id, {
                        page: 1,
                        runId: run.id
                      })}
                    >
                      Open workspace
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
    </main>
  );
}
