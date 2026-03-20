import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { DocumentPipelineLiveStatus } from "../../../../../../../components/document-pipeline-live-status";
import { DocumentTranscriptionRunActions } from "../../../../../../../components/document-transcription-run-actions";
import { DocumentTranscriptionTriageSurface } from "../../../../../../../components/document-transcription-triage-surface";
import {
  getProjectDocument,
  getProjectDocumentTranscriptionMetrics,
  getProjectDocumentTranscriptionOverview,
  getProjectDocumentTranscriptionRun,
  getProjectDocumentTranscriptionTriage,
  listProjectDocumentTranscriptionRunPages,
  listProjectDocumentTranscriptionRuns
} from "../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../lib/projects";
import {
  projectDocumentTranscriptionPath,
  projectDocumentTranscriptionRunPath,
  projectDocumentTranscriptionWorkspacePath,
  projectDocumentViewerPath,
  projectsPath
} from "../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

type TranscriptionTab = "overview" | "triage" | "runs" | "artefacts";
type TranscriptionStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";

function resolveTab(raw: string | undefined): TranscriptionTab {
  if (raw === "triage" || raw === "runs" || raw === "artefacts") {
    return raw;
  }
  return "overview";
}

function resolveTranscriptionStatus(
  raw: string | undefined
): TranscriptionStatus | undefined {
  if (!raw) {
    return undefined;
  }
  const normalized = raw.trim().toUpperCase();
  if (
    normalized === "QUEUED" ||
    normalized === "RUNNING" ||
    normalized === "SUCCEEDED" ||
    normalized === "FAILED" ||
    normalized === "CANCELED"
  ) {
    return normalized;
  }
  return undefined;
}

function resolveConfidenceThreshold(raw: string | undefined): number | undefined {
  if (!raw) {
    return undefined;
  }
  const parsed = Number.parseFloat(raw);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function resolveRunTone(
  status: string
): "danger" | "neutral" | "success" | "warning" {
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

export default async function ProjectDocumentTranscriptionPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<{
    confidenceBelow?: string;
    runId?: string;
    status?: string;
    tab?: string;
  }>;
}>) {
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const tab = resolveTab(query.tab);
  const triageStatus = resolveTranscriptionStatus(query.status);
  const confidenceBelow = resolveConfidenceThreshold(query.confidenceBelow);
  const requestedRunId =
    typeof query.runId === "string" && query.runId.trim().length > 0
      ? query.runId.trim()
      : null;

  const [documentResult, workspaceResult, overviewResult, runsResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectWorkspace(projectId),
    getProjectDocumentTranscriptionOverview(projectId, documentId),
    listProjectDocumentTranscriptionRuns(projectId, documentId, { pageSize: 50 })
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
          title="Transcription route unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for transcription."
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
      ? await getProjectDocumentTranscriptionRun(projectId, document.id, selectedRunId)
      : null;
  const selectedRun =
    selectedRunResult && selectedRunResult.ok && selectedRunResult.data
      ? selectedRunResult.data
      : selectedRunId !== null
        ? runs.find((run) => run.id === selectedRunId) ?? null
        : null;
  const triageResult =
    selectedRunId !== null
      ? await getProjectDocumentTranscriptionTriage(projectId, document.id, {
          pageSize: 500,
          runId: selectedRunId,
          status: triageStatus,
          confidenceBelow
        })
      : null;
  const metricsResult =
    selectedRunId !== null
      ? await getProjectDocumentTranscriptionMetrics(projectId, document.id, {
          runId: selectedRunId,
          confidenceBelow
        })
      : null;
  const artefactPagesResult =
    selectedRunId !== null
      ? await listProjectDocumentTranscriptionRunPages(
          projectId,
          document.id,
          selectedRunId,
          { pageSize: 500 }
        )
      : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Transcription</p>
        <h2>{document.originalFilename}</h2>
        <p className="ukde-muted">
          Canonical route family for transcription overview, triage, runs, artefacts,
          and deep-linkable workspace context.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            aria-current={tab === "overview" ? "page" : undefined}
            href={projectDocumentTranscriptionPath(projectId, document.id, {
              runId: selectedRunId
            })}
          >
            Overview
          </Link>
          <Link
            className="secondaryButton"
            aria-current={tab === "triage" ? "page" : undefined}
            href={projectDocumentTranscriptionPath(projectId, document.id, {
              tab: "triage",
              runId: selectedRunId
            })}
          >
            Triage
          </Link>
          <Link
            className="secondaryButton"
            aria-current={tab === "runs" ? "page" : undefined}
            href={projectDocumentTranscriptionPath(projectId, document.id, {
              tab: "runs",
              runId: selectedRunId
            })}
          >
            Runs
          </Link>
          <Link
            className="secondaryButton"
            aria-current={tab === "artefacts" ? "page" : undefined}
            href={projectDocumentTranscriptionPath(projectId, document.id, {
              tab: "artefacts",
              runId: selectedRunId
            })}
          >
            Artefacts
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
              href={projectDocumentTranscriptionWorkspacePath(
                projectId,
                document.id,
                {
                  page: 1,
                  runId: selectedRunId
                }
              )}
            >
              Open workspace
            </Link>
          ) : null}
        </div>
      </section>

      <DocumentPipelineLiveStatus documentId={document.id} projectId={projectId} />

      <DocumentTranscriptionRunActions
        canMutate={Boolean(canMutate)}
        documentId={document.id}
        inputLayoutRunId={selectedRun?.inputLayoutRunId}
        inputPreprocessRunId={selectedRun?.inputPreprocessRunId}
        isActiveProjection={selectedRun?.isActiveProjection}
        projectId={projectId}
        runId={selectedRun?.id}
        runStatus={selectedRun?.status}
      />

      {tab === "overview" ? (
        <section className="sectionCard ukde-panel">
          <h3>Transcription overview</h3>
          {!overviewResult.ok ? (
            <SectionState
              kind="degraded"
              title="Overview unavailable"
              description={
                overviewResult.detail ?? "Transcription summary could not be loaded."
              }
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
                  <span>Active line count</span>
                  <strong>{overviewResult.data?.activeLineCount ?? 0}</strong>
                </li>
                <li>
                  <span>Active token count</span>
                  <strong>{overviewResult.data?.activeTokenCount ?? 0}</strong>
                </li>
                <li>
                  <span>Anchor refresh required</span>
                  <strong>{overviewResult.data?.activeAnchorRefreshRequired ?? 0}</strong>
                </li>
                <li>
                  <span>Low-confidence lines</span>
                  <strong>{overviewResult.data?.activeLowConfidenceLines ?? 0}</strong>
                </li>
                <li>
                  <span>Downstream redaction state</span>
                  <strong>
                    {overviewResult.data?.projection?.downstreamRedactionState ??
                      "NOT_STARTED"}
                  </strong>
                </li>
              </ul>
              {selectedRun ? (
                <div className="buttonRow">
                  <Link
                    className="secondaryButton"
                    href={projectDocumentTranscriptionRunPath(
                      projectId,
                      document.id,
                      selectedRun.id
                    )}
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
          <h3>Triage queue</h3>
          {selectedRunId === null ? (
            <SectionState
              kind="empty"
              title="No run selected"
              description="Queue or activate a transcription run to open triage."
            />
          ) : triageResult === null || !triageResult.ok || !triageResult.data ? (
            <SectionState
              kind="degraded"
              title="Triage unavailable"
              description={
                triageResult?.detail ?? "Page-level triage rows could not be loaded."
              }
            />
          ) : (
            <DocumentTranscriptionTriageSurface
              canAssign={Boolean(canMutate)}
              documentId={document.id}
              items={triageResult.data.items}
              metrics={
                metricsResult && metricsResult.ok && metricsResult.data
                  ? metricsResult.data
                  : null
              }
              projectId={projectId}
              runId={selectedRunId}
            />
          )}
        </section>
      ) : null}

      {tab === "runs" ? (
        <section className="sectionCard ukde-panel">
          <h3>Transcription runs</h3>
          {!runsResult.ok ? (
            <SectionState
              kind="degraded"
              title="Runs unavailable"
              description={runsResult.detail ?? "Run history could not be loaded."}
            />
          ) : runs.length === 0 ? (
            <SectionState
              kind="empty"
              title="No transcription runs yet"
              description="Queue the first transcription run to initialize lineage."
            />
          ) : (
            <ul className="timelineList">
              {runs.map((run) => (
                <li key={run.id}>
                  <div className="auditIntegrityRow">
                    <Link
                      href={projectDocumentTranscriptionRunPath(
                        projectId,
                        document.id,
                        run.id
                      )}
                    >
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
                    Engine {run.engine} · model {run.modelId} · attempt{" "}
                    {run.attemptNumber} · created{" "}
                    {new Date(run.createdAt).toISOString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {tab === "artefacts" ? (
        <section className="sectionCard ukde-panel">
          <h3>Run artefacts</h3>
          {selectedRunId === null ? (
            <SectionState
              kind="empty"
              title="No run selected"
              description="Select a run to inspect PAGE-XML and model-response artefact references."
            />
          ) : artefactPagesResult === null ||
            !artefactPagesResult.ok ||
            !artefactPagesResult.data ? (
            <SectionState
              kind="degraded"
              title="Artefacts unavailable"
              description={
                artefactPagesResult?.detail ??
                "Page artefact records could not be loaded."
              }
            />
          ) : artefactPagesResult.data.items.length === 0 ? (
            <SectionState
              kind="empty"
              title="No artefacts yet"
              description="Inference output artefacts will appear once page processing starts."
            />
          ) : (
            <ul className="timelineList">
              {artefactPagesResult.data.items.map((pageRow) => (
                <li key={pageRow.pageId}>
                  <div className="auditIntegrityRow">
                    <span>Page {pageRow.pageIndex + 1}</span>
                    <StatusChip tone={resolveRunTone(pageRow.status)}>
                      {pageRow.status}
                    </StatusChip>
                  </div>
                  <p className="ukde-muted">
                    PAGE-XML {pageRow.pagexmlOutKey ? "available" : "pending"} · raw
                    response {pageRow.rawModelResponseSha256 ? "available" : "pending"} · HOCR{" "}
                    {pageRow.hocrOutKey ? "available" : "pending"}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
    </main>
  );
}
