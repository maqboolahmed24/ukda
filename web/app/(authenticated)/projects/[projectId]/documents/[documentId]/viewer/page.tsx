import { notFound, redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import { ProjectDocumentViewerShell } from "../../../../../../../components/project-document-viewer-shell";
import {
  getProjectDocument,
  getProjectDocumentActivePreprocessRun,
  getProjectDocumentPage,
  listProjectDocumentPages,
  listProjectDocumentPreprocessRuns
} from "../../../../../../../lib/documents";
import {
  projectDocumentPreprocessingComparePath,
  projectDocumentViewerPath,
  projectsPath
} from "../../../../../../../lib/routes";
import { normalizeViewerUrlState } from "../../../../../../../lib/url-state";

export const dynamic = "force-dynamic";

export default async function ProjectDocumentViewerPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<{
    comparePair?: string;
    mode?: string;
    page?: string;
    runId?: string;
    zoom?: string;
  }>;
}>) {
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const viewerState = normalizeViewerUrlState({
    comparePair: query.comparePair,
    mode: query.mode,
    page: query.page,
    runId: query.runId,
    zoom: query.zoom
  });
  if (viewerState.shouldRedirect) {
    redirect(
      projectDocumentViewerPath(projectId, documentId, viewerState.page, {
        comparePair: viewerState.comparePair,
        mode: viewerState.mode,
        runId: viewerState.runId,
        zoom: viewerState.zoom
      })
    );
  }

  const documentResult = await getProjectDocument(projectId, documentId);
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
          title="Viewer route unavailable"
          description={
            documentResult.detail ??
            "The viewer route could not load document metadata."
          }
        />
      </main>
    );
  }

  const document = documentResult.data;
  if (!document) {
    notFound();
  }

  const [pagesResult, preprocessRunsResult, activePreprocessRunResult] = await Promise.all([
    listProjectDocumentPages(projectId, document.id),
    listProjectDocumentPreprocessRuns(projectId, document.id, { pageSize: 25 }),
    getProjectDocumentActivePreprocessRun(projectId, document.id)
  ]);
  if (!pagesResult.ok) {
    if (pagesResult.status === 404) {
      notFound();
    }
    if (pagesResult.status === 403) {
      redirect(projectsPath);
    }
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Viewer pages unavailable"
          description={
            pagesResult.detail ??
            "The viewer route could not load page metadata."
          }
        />
      </main>
    );
  }

  const pages = pagesResult.data?.items ?? [];
  const preprocessRuns =
    preprocessRunsResult.ok && preprocessRunsResult.data
      ? preprocessRunsResult.data.items
      : [];
  const activePreprocessRunId =
    activePreprocessRunResult.ok && activePreprocessRunResult.data?.run
      ? activePreprocessRunResult.data.run.id
      : null;
  const preprocessingComparePath =
    preprocessRuns.length >= 2
      ? projectDocumentPreprocessingComparePath(
          projectId,
          document.id,
          preprocessRuns[1].id,
          preprocessRuns[0].id
        )
      : preprocessRuns.length === 1
        ? projectDocumentPreprocessingComparePath(
            projectId,
            document.id,
            undefined,
            preprocessRuns[0].id
          )
      : undefined;
  const inferredPageCount =
    pages.length > 0 ? pages.length : Math.max(0, document.pageCount ?? 0);
  const currentPage = viewerState.page;

  if (inferredPageCount > 0 && currentPage > inferredPageCount) {
    redirect(
      projectDocumentViewerPath(projectId, document.id, inferredPageCount, {
        comparePair: viewerState.comparePair,
        mode: viewerState.mode,
        runId: viewerState.runId,
        zoom: viewerState.zoom
      })
    );
  }

  const currentPageRecord = pages.find(
    (page) => page.pageIndex === currentPage - 1
  );

  let currentPageDetail = null;
  let currentPageError: string | null = null;

  if (currentPageRecord) {
    const currentPageResult = await getProjectDocumentPage(
      projectId,
      document.id,
      currentPageRecord.id
    );
    if (!currentPageResult.ok || !currentPageResult.data) {
      currentPageError =
        currentPageResult.detail ??
        "The selected page could not be loaded from the document page API.";
    } else {
      currentPageDetail = currentPageResult.data;
    }
  }

  return (
    <main className="homeLayout">
      <ProjectDocumentViewerShell
        activePreprocessRunId={activePreprocessRunId}
        currentPage={currentPage}
        currentPageDetail={currentPageDetail}
        currentPageError={currentPageError}
        documentId={document.id}
        documentName={document.originalFilename}
        documentStatus={document.status}
        initialComparePair={viewerState.comparePair}
        initialRunId={viewerState.runId}
        initialViewerMode={viewerState.mode}
        initialZoomPercent={viewerState.zoom}
        pageCount={inferredPageCount}
        pages={pages}
        preprocessRuns={preprocessRuns}
        preprocessingComparePath={preprocessingComparePath}
        projectId={projectId}
      />
    </main>
  );
}
