import { notFound, redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import { ProjectDocumentLayoutWorkspaceShell } from "../../../../../../../../components/project-document-layout-workspace-shell";
import { normalizePanelSectionParam } from "../../../../../../../../lib/panel-sections";
import {
  getProjectDocument,
  getProjectDocumentLayoutPageOverlay,
  getProjectDocumentLayoutPageRecallStatus,
  getProjectDocumentLayoutOverview,
  listProjectDocumentLayoutPageRescueCandidates,
  listProjectDocumentLayoutRunPages,
  listProjectDocumentLayoutRuns
} from "../../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../../lib/projects";
import {
  projectDocumentLayoutWorkspacePath,
  projectsPath
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

export default async function ProjectDocumentLayoutWorkspacePage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<{ page?: string; panel?: string; runId?: string }>;
}>) {
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const requestedPage = toPage(query.page);
  const panelParam = normalizePanelSectionParam(query.panel);
  const requestedRunId =
    typeof query.runId === "string" && query.runId.trim().length > 0
      ? query.runId.trim()
      : null;

  if (panelParam.shouldRedirect) {
    redirect(
      projectDocumentLayoutWorkspacePath(projectId, documentId, {
        page: requestedPage,
        panel: panelParam.value,
        runId: requestedRunId
      })
    );
  }

  const [documentResult, overviewResult, runsResult, workspaceResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectDocumentLayoutOverview(projectId, documentId),
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
          title="Layout workspace unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for layout workspace."
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
  const pagesResult =
    selectedRunId !== null
      ? await listProjectDocumentLayoutRunPages(projectId, document.id, selectedRunId, {
          pageSize: 500
        })
      : null;
  const pages = pagesResult?.ok && pagesResult.data ? pagesResult.data.items : [];

  if (selectedRunId === null) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No layout run selected"
            description="Queue or activate a layout run, then open the workspace."
          />
        </section>
      </main>
    );
  }

  if (pagesResult !== null && !pagesResult.ok) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Workspace pages unavailable"
            description={pagesResult.detail ?? "Layout page rows could not be loaded."}
          />
        </section>
      </main>
    );
  }

  const totalPages = pages.length;
  const resolvedPage = totalPages > 0 ? Math.min(requestedPage, totalPages) : 1;
  const selectedPage = pages.find((item) => item.pageIndex + 1 === resolvedPage) ?? pages[0] ?? null;
  const overlayResult =
    selectedRunId !== null && selectedPage !== null
      ? await getProjectDocumentLayoutPageOverlay(
          projectId,
          document.id,
          selectedRunId,
          selectedPage.pageId
        )
      : null;
  const recallStatusResult =
    selectedRunId !== null && selectedPage !== null
      ? await getProjectDocumentLayoutPageRecallStatus(
          projectId,
          document.id,
          selectedRunId,
          selectedPage.pageId
        )
      : null;
  const rescueCandidatesResult =
    selectedRunId !== null && selectedPage !== null
      ? await listProjectDocumentLayoutPageRescueCandidates(
          projectId,
          document.id,
          selectedRunId,
          selectedPage.pageId
        )
      : null;
  const overlayPayload =
    overlayResult && overlayResult.ok && overlayResult.data
      ? overlayResult.data
      : null;
  const overlayNotReady = Boolean(
    overlayResult && !overlayResult.ok && overlayResult.status === 409
  );
  const overlayError =
    overlayResult && !overlayResult.ok && overlayResult.status !== 409
      ? overlayResult.detail ?? "Layout overlay could not be loaded."
      : null;
  const recallStatus =
    recallStatusResult && recallStatusResult.ok && recallStatusResult.data
      ? recallStatusResult.data
      : null;
  const recallStatusError =
    recallStatusResult && !recallStatusResult.ok
      ? recallStatusResult.detail ?? "Recall status could not be loaded."
      : null;
  const rescueCandidates =
    rescueCandidatesResult && rescueCandidatesResult.ok && rescueCandidatesResult.data
      ? rescueCandidatesResult.data.items
      : [];
  const rescueCandidatesError =
    rescueCandidatesResult && !rescueCandidatesResult.ok
      ? rescueCandidatesResult.detail ?? "Rescue candidates could not be loaded."
      : null;
  const canEditReadingOrder =
    workspaceResult.ok &&
    workspaceResult.data &&
    (workspaceResult.data.currentUserRole === "PROJECT_LEAD" ||
      workspaceResult.data.currentUserRole === "REVIEWER" ||
      (!workspaceResult.data.isMember && workspaceResult.data.canAccessSettings));
  const canEditLayout = canEditReadingOrder;
  return (
    <main className="homeLayout layoutWorkspacePage">
      <ProjectDocumentLayoutWorkspaceShell
        canEditLayout={Boolean(canEditLayout)}
        canEditReadingOrder={Boolean(canEditReadingOrder)}
        documentId={document.id}
        documentName={document.originalFilename}
        initialPanelSection={panelParam.value ?? "context"}
        overlayError={overlayError}
        overlayNotReady={overlayNotReady}
        overlayPayload={overlayPayload}
        pages={pages}
        projectId={projectId}
        recallStatus={recallStatus}
        recallStatusError={recallStatusError}
        rescueCandidates={rescueCandidates}
        rescueCandidatesError={rescueCandidatesError}
        runs={runs}
        selectedPageNumber={resolvedPage}
        selectedRunId={selectedRunId}
      />
    </main>
  );
}
