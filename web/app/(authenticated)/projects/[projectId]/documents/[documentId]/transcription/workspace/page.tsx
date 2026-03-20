import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type { TranscriptionTokenSourceKind } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { DocumentTranscriptionWorkspaceSurface } from "../../../../../../../../components/document-transcription-workspace-surface";
import { normalizePanelSectionParam } from "../../../../../../../../lib/panel-sections";
import {
  getProjectDocument,
  getProjectDocumentLayoutPageOverlay,
  getProjectDocumentTranscriptionMetrics,
  getProjectDocumentTranscriptionOverview,
  listProjectDocumentTranscriptionRunPageLines,
  listProjectDocumentTranscriptionRunPageTokens,
  listProjectDocumentTranscriptionRunPageVariantLayers,
  listProjectDocumentTranscriptionRunPages,
  listProjectDocumentTranscriptionRuns
} from "../../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../../lib/projects";
import {
  projectDocumentTranscriptionComparePath,
  projectDocumentTranscriptionPath,
  projectDocumentTranscriptionWorkspacePath,
  projectsPath,
  type TranscriptionWorkspaceMode
} from "../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function toPage(value: string | undefined): number {
  if (!value) {
    return 1;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return 1;
  }
  return Math.max(1, parsed);
}

function toWorkspaceMode(value: string | undefined): TranscriptionWorkspaceMode {
  if (value === "as-on-page") {
    return "as-on-page";
  }
  return "reading-order";
}

function toSourceKind(value: string | undefined): TranscriptionTokenSourceKind | undefined {
  if (!value) {
    return undefined;
  }
  const normalized = value.trim().toUpperCase();
  if (
    normalized === "LINE" ||
    normalized === "RESCUE_CANDIDATE" ||
    normalized === "PAGE_WINDOW"
  ) {
    return normalized;
  }
  return undefined;
}

function resolveTone(
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

export default async function ProjectDocumentTranscriptionWorkspacePage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<{
    lineId?: string;
    mode?: string;
    panel?: string;
    page?: string;
    runId?: string;
    sourceKind?: string;
    sourceRefId?: string;
    tokenId?: string;
  }>;
}>) {
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const requestedPage = toPage(query.page);
  const requestedMode = toWorkspaceMode(query.mode);
  const panelParam = normalizePanelSectionParam(query.panel);
  const requestedRunId =
    typeof query.runId === "string" && query.runId.trim().length > 0
      ? query.runId.trim()
      : null;
  const requestedLineId =
    typeof query.lineId === "string" && query.lineId.trim().length > 0
      ? query.lineId.trim()
      : null;
  const requestedTokenId =
    typeof query.tokenId === "string" && query.tokenId.trim().length > 0
      ? query.tokenId.trim()
      : null;
  const sourceKind = toSourceKind(query.sourceKind);
  const sourceRefId =
    typeof query.sourceRefId === "string" && query.sourceRefId.trim().length > 0
      ? query.sourceRefId.trim()
      : null;

  if (panelParam.shouldRedirect) {
    redirect(
      projectDocumentTranscriptionWorkspacePath(projectId, documentId, {
        lineId: requestedLineId,
        mode: requestedMode,
        panel: panelParam.value,
        page: requestedPage,
        runId: requestedRunId,
        sourceKind: sourceKind ?? null,
        sourceRefId,
        tokenId: requestedTokenId
      })
    );
  }

  const [documentResult, overviewResult, runsResult, workspaceResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectDocumentTranscriptionOverview(projectId, documentId),
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
          title="Transcription workspace unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for transcription workspace."
          }
        />
      </main>
    );
  }

  const document = documentResult.data;
  if (!document) {
    notFound();
  }

  const runs = runsResult.ok && runsResult.data ? runsResult.data.items : [];
  const activeRunId =
    overviewResult.ok && overviewResult.data?.activeRun
      ? overviewResult.data.activeRun.id
      : null;
  const selectedRunId = requestedRunId ?? activeRunId ?? (runs[0]?.id ?? null);
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? null;
  const compareTargetRun =
    selectedRunId !== null
      ? runs.find((run) => run.id !== selectedRunId) ?? null
      : null;

  if (selectedRunId === null || selectedRun === null) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No transcription run selected"
            description="Queue or activate a transcription run, then open workspace."
          />
        </section>
      </main>
    );
  }

  const pagesResult = await listProjectDocumentTranscriptionRunPages(
    projectId,
    document.id,
    selectedRunId,
    { pageSize: 500 }
  );
  if (!pagesResult.ok) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Workspace pages unavailable"
            description={pagesResult.detail ?? "Transcription page rows could not be loaded."}
          />
        </section>
      </main>
    );
  }

  const pages = pagesResult.data?.items ?? [];
  const totalPages = pages.length;
  const resolvedPage = totalPages > 0 ? Math.min(requestedPage, totalPages) : 1;
  const selectedPage =
    pages.find((item) => item.pageIndex + 1 === resolvedPage) ?? pages[0] ?? null;

  if (!selectedPage) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No page outputs yet"
            description="Page transcription results will appear once processing starts."
          />
        </section>
      </main>
    );
  }

  const [linesResult, tokensResult, metricsResult, overlayResult, variantLayersResult] =
    await Promise.all([
      listProjectDocumentTranscriptionRunPageLines(
        projectId,
        document.id,
        selectedRunId,
        selectedPage.pageId,
        {
          lineId: requestedLineId ?? undefined,
          tokenId: requestedTokenId ?? undefined,
          sourceKind,
          sourceRefId: sourceRefId ?? undefined,
          workspaceView: true
        }
      ),
      listProjectDocumentTranscriptionRunPageTokens(
        projectId,
        document.id,
        selectedRunId,
        selectedPage.pageId
      ),
      getProjectDocumentTranscriptionMetrics(projectId, document.id, {
        runId: selectedRunId
      }),
      getProjectDocumentLayoutPageOverlay(
        projectId,
        document.id,
        selectedRun.inputLayoutRunId,
        selectedPage.pageId
      ),
      listProjectDocumentTranscriptionRunPageVariantLayers(
        projectId,
        document.id,
        selectedRun.id,
        selectedPage.pageId,
        { variantKind: "NORMALISED" }
      )
    ]);

  const lines = linesResult.ok && linesResult.data ? linesResult.data.items : [];
  const tokens = tokensResult.ok && tokensResult.data ? tokensResult.data.items : [];
  const linesError = !linesResult.ok
    ? linesResult.detail ?? "Line rows could not be loaded."
    : null;
  const tokensError = !tokensResult.ok
    ? tokensResult.detail ?? "Token rows could not be loaded."
    : null;
  const overlayError = !overlayResult.ok
    ? overlayResult.detail ?? "Layout overlay could not be loaded."
    : null;
  const variantLayersUnavailableReason = !variantLayersResult.ok
    ? variantLayersResult.detail ?? "Assist suggestions are unavailable for this page."
    : null;

  const selectedTokenById =
    requestedTokenId !== null
      ? tokens.find((token) => token.tokenId === requestedTokenId) ?? null
      : null;
  const selectedTokenBySource =
    selectedTokenById === null && sourceKind !== undefined && sourceRefId !== null
      ? tokens.find(
          (token) =>
            token.sourceKind === sourceKind &&
            token.sourceRefId === sourceRefId &&
            (requestedLineId === null || token.lineId === requestedLineId)
        ) ?? null
      : null;
  const selectedToken = selectedTokenById ?? selectedTokenBySource;
  const selectedLineFromRequestedId =
    requestedLineId !== null
      ? lines.find((line) => line.lineId === requestedLineId) ?? null
      : null;
  const selectedLineFromToken =
    selectedToken && selectedToken.lineId
      ? lines.find((line) => line.lineId === selectedToken.lineId) ?? null
      : null;
  const hasExplicitTokenContext =
    requestedTokenId !== null || (sourceKind !== undefined && sourceRefId !== null);
  const selectedLine =
    selectedLineFromRequestedId ??
    selectedLineFromToken ??
    (hasExplicitTokenContext && selectedToken && selectedToken.lineId === null
      ? null
      : lines[0] ?? null);
  const resolvedSourceKind = selectedToken?.sourceKind ?? sourceKind ?? "LINE";
  const resolvedSourceRefId =
    selectedToken?.sourceRefId ?? sourceRefId ?? selectedLine?.lineId ?? null;
  const reviewConfidenceThreshold =
    metricsResult.ok && metricsResult.data
      ? metricsResult.data.reviewConfidenceThreshold
      : 0.85;

  const canEdit =
    workspaceResult.ok &&
    workspaceResult.data &&
    (workspaceResult.data.currentUserRole === "PROJECT_LEAD" ||
      workspaceResult.data.currentUserRole === "REVIEWER" ||
      (!workspaceResult.data.isMember && workspaceResult.data.canAccessSettings));

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Transcription workspace</p>
        <h2>{document.originalFilename}</h2>
        <p className="ukde-muted">
          Single-route correction workspace with deep-link-safe run/page/line/token context.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentTranscriptionPath(projectId, document.id, {
              runId: selectedRunId
            })}
          >
            Overview
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentTranscriptionPath(projectId, document.id, {
              tab: "triage",
              runId: selectedRunId
            })}
          >
            Triage
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentTranscriptionPath(projectId, document.id, {
              tab: "runs",
              runId: selectedRunId
            })}
          >
            Runs
          </Link>
          {compareTargetRun ? (
            <Link
              className="secondaryButton"
              href={projectDocumentTranscriptionComparePath(
                projectId,
                document.id,
                selectedRunId,
                compareTargetRun.id,
                {
                  page: resolvedPage,
                  lineId: requestedLineId,
                  tokenId: requestedTokenId
                }
              )}
            >
              Compare generations
            </Link>
          ) : null}
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Workspace context</h3>
        <ul className="projectMetaList">
          <li>
            <span>Run</span>
            <strong>{selectedRunId}</strong>
          </li>
          <li>
            <span>Run status</span>
            <strong>
              <StatusChip tone={resolveTone(selectedRun.status)}>{selectedRun.status}</StatusChip>
            </strong>
          </li>
          <li>
            <span>Page</span>
            <strong>
              {resolvedPage} / {Math.max(1, pages.length)}
            </strong>
          </li>
          <li>
            <span>Line context</span>
            <strong>{selectedLine?.lineId ?? requestedLineId ?? "Source-only context"}</strong>
          </li>
          <li>
            <span>Token context</span>
            <strong>{selectedToken?.tokenId ?? requestedTokenId ?? "None"}</strong>
          </li>
          <li>
            <span>Source</span>
            <strong>
              {resolvedSourceKind} · {resolvedSourceRefId ?? "N/A"}
            </strong>
          </li>
          <li>
            <span>Mode</span>
            <strong>{requestedMode === "as-on-page" ? "As on page" : "Reading order"}</strong>
          </li>
          <li>
            <span>Edit access</span>
            <strong>{canEdit ? "Enabled" : "Read-only"}</strong>
          </li>
        </ul>
      </section>

      {linesError ? (
        <section className="sectionCard ukde-panel">
          <SectionState kind="degraded" title="Lines unavailable" description={linesError} />
        </section>
      ) : null}
      {tokensError ? (
        <section className="sectionCard ukde-panel">
          <SectionState kind="degraded" title="Tokens unavailable" description={tokensError} />
        </section>
      ) : null}

      {!linesError && !tokensError ? (
        <section className="sectionCard ukde-panel">
          <DocumentTranscriptionWorkspaceSurface
            canAssistDecide={Boolean(canEdit)}
            canEdit={Boolean(canEdit)}
            documentId={document.id}
            initialLineId={selectedLine?.lineId ?? requestedLineId ?? null}
            initialMode={requestedMode}
            initialOverlay={overlayResult.ok ? overlayResult.data ?? null : null}
            initialOverlayError={overlayError}
            initialPanelSection={panelParam.value ?? "context"}
            initialTokenId={selectedToken?.tokenId ?? requestedTokenId ?? null}
            initialVariantLayers={
              variantLayersResult.ok && variantLayersResult.data
                ? variantLayersResult.data.items
                : []
            }
            lines={lines}
            pageId={selectedPage.pageId}
            pageNumber={resolvedPage}
            pages={pages}
            projectId={projectId}
            resolvedSourceKind={resolvedSourceKind}
            resolvedSourceRefId={resolvedSourceRefId}
            reviewConfidenceThreshold={reviewConfidenceThreshold}
            runId={selectedRunId}
            runs={runs}
            selectedRunInputLayoutRunId={selectedRun.inputLayoutRunId}
            selectedRunInputPreprocessRunId={selectedRun.inputPreprocessRunId}
            tokens={tokens}
            variantLayersUnavailableReason={variantLayersUnavailableReason}
          />
        </section>
      ) : null}
    </main>
  );
}
