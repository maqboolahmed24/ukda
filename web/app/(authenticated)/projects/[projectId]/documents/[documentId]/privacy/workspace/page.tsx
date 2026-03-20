import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type { DocumentRedactionFinding } from "@ukde/contracts";
import { SectionState } from "@ukde/ui/primitives";

import { PrivacyWorkspaceSurface } from "../../../../../../../../components/privacy-workspace-surface";
import { normalizePanelSectionParam } from "../../../../../../../../lib/panel-sections";
import {
  getProjectDocument,
  getProjectDocumentRedactionOverview,
  getProjectDocumentRedactionRun,
  getProjectDocumentRedactionRunPagePreviewStatus,
  getProjectDocumentRedactionRunPageReview,
  listProjectDocumentRedactionRunPageEvents,
  listProjectDocumentRedactionRunPageFindings,
  listProjectDocumentRedactionRunPages,
  listProjectDocumentRedactionRuns,
  listProjectDocumentPages,
  listProjectDocumentTranscriptionRunPageLines,
  patchProjectDocumentRedactionFinding,
  patchProjectDocumentRedactionPageReview
} from "../../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../../lib/projects";
import {
  projectDocumentPrivacyPath,
  projectDocumentPrivacyRunPath,
  projectDocumentPrivacyWorkspacePath,
  projectsPath,
  type PanelSection
} from "../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

type PrivacyWorkspaceMode = "controlled" | "safeguarded";

type WorkspaceSearchParams = {
  error?: string;
  findingId?: string;
  highlights?: string;
  lineId?: string;
  mode?: string;
  notice?: string;
  panel?: string;
  page?: string;
  runId?: string;
  tokenId?: string;
};

const UNRESOLVED_STATUSES = new Set(["NEEDS_REVIEW", "OVERRIDDEN", "FALSE_POSITIVE"]);

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

function toOptionalToken(value: string | undefined): string | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }
  return normalized;
}

function isHighlightsEnabled(value: string | undefined): boolean {
  return value !== "off";
}

function resolveWorkspaceMode(value: string | undefined): PrivacyWorkspaceMode {
  if (value === "controlled") {
    return "controlled";
  }
  return "safeguarded";
}

function isUnresolvedFinding(status: string): boolean {
  return UNRESOLVED_STATUSES.has(status);
}

function resolveFindingLineId(finding: DocumentRedactionFinding): string | null {
  return finding.geometry.lineId ?? finding.lineId ?? null;
}

function resolveFindingTokenId(finding: DocumentRedactionFinding): string | null {
  return finding.geometry.tokenIds[0] ?? null;
}

function appendWorkspaceSignals(options: {
  basePath: string;
  error?: string | null;
  notice?: string | null;
  showHighlights: boolean;
}): string {
  const params = new URLSearchParams();
  if (!options.showHighlights) {
    params.set("highlights", "off");
  }
  if (options.notice) {
    params.set("notice", options.notice);
  }
  if (options.error) {
    params.set("error", options.error);
  }
  const query = params.toString();
  if (!query) {
    return options.basePath;
  }
  return `${options.basePath}&${query}`;
}

function resolveNoticeMessage(notice: string | null): string | null {
  if (!notice) {
    return null;
  }
  if (notice === "finding_updated") {
    return "Finding decision was recorded and appended to decision history.";
  }
  if (notice === "page_approved") {
    return "Page review status is now APPROVED.";
  }
  return notice;
}

async function resolveFirstUnresolvedFindingForPage(options: {
  documentId: string;
  pageId: string;
  projectId: string;
  runId: string;
}): Promise<DocumentRedactionFinding | null> {
  const result = await listProjectDocumentRedactionRunPageFindings(
    options.projectId,
    options.documentId,
    options.runId,
    options.pageId,
    {
      unresolvedOnly: true,
      workspaceView: true
    }
  );
  if (!result.ok || !result.data) {
    return null;
  }
  return result.data.items.find((item) => isUnresolvedFinding(item.decisionStatus)) ?? null;
}

async function resolveNextUnresolvedHref(options: {
  currentFindingId: string | null;
  currentPageIndex: number;
  documentId: string;
  findings: DocumentRedactionFinding[];
  mode: PrivacyWorkspaceMode;
  panel: PanelSection;
  pages: Array<{ pageId: string; pageIndex: number; unresolvedCount: number }>;
  projectId: string;
  runId: string;
  showHighlights: boolean;
}): Promise<string | null> {
  const unresolvedCurrentPageFindings = options.findings.filter((finding) =>
    isUnresolvedFinding(finding.decisionStatus)
  );
  if (unresolvedCurrentPageFindings.length > 0) {
    if (options.currentFindingId) {
      const selectedIndex = unresolvedCurrentPageFindings.findIndex(
        (finding) => finding.id === options.currentFindingId
      );
      if (selectedIndex >= 0 && selectedIndex + 1 < unresolvedCurrentPageFindings.length) {
        const nextFinding = unresolvedCurrentPageFindings[selectedIndex + 1];
        const basePath = projectDocumentPrivacyWorkspacePath(
          options.projectId,
          options.documentId,
          {
            page: options.currentPageIndex + 1,
            runId: options.runId,
            findingId: nextFinding.id,
            lineId: resolveFindingLineId(nextFinding) ?? undefined,
            mode: options.mode,
            panel: options.panel,
            tokenId: resolveFindingTokenId(nextFinding) ?? undefined
          }
        );
        return appendWorkspaceSignals({
          basePath,
          showHighlights: options.showHighlights
        });
      }
    }
    if (!options.currentFindingId) {
      const nextFinding = unresolvedCurrentPageFindings[0];
      const basePath = projectDocumentPrivacyWorkspacePath(
        options.projectId,
        options.documentId,
        {
          page: options.currentPageIndex + 1,
          runId: options.runId,
          findingId: nextFinding.id,
          lineId: resolveFindingLineId(nextFinding) ?? undefined,
          mode: options.mode,
          panel: options.panel,
          tokenId: resolveFindingTokenId(nextFinding) ?? undefined
        }
      );
      return appendWorkspaceSignals({
        basePath,
        showHighlights: options.showHighlights
      });
    }
  }

  const orderedPages = [...options.pages].sort(
    (left, right) => left.pageIndex - right.pageIndex
  );
  const currentPagePosition = orderedPages.findIndex(
    (page) => page.pageIndex === options.currentPageIndex
  );
  if (currentPagePosition < 0) {
    return null;
  }

  for (let offset = 1; offset <= orderedPages.length; offset += 1) {
    const candidate = orderedPages[(currentPagePosition + offset) % orderedPages.length];
    if (candidate.unresolvedCount <= 0) {
      continue;
    }
    const unresolvedFinding = await resolveFirstUnresolvedFindingForPage({
      projectId: options.projectId,
      documentId: options.documentId,
      runId: options.runId,
      pageId: candidate.pageId
    });
    if (!unresolvedFinding) {
      continue;
    }
    const basePath = projectDocumentPrivacyWorkspacePath(
      options.projectId,
      options.documentId,
      {
        page: candidate.pageIndex + 1,
        runId: options.runId,
        findingId: unresolvedFinding.id,
        lineId: resolveFindingLineId(unresolvedFinding) ?? undefined,
        mode: options.mode,
        panel: options.panel,
        tokenId: resolveFindingTokenId(unresolvedFinding) ?? undefined
      }
    );
    return appendWorkspaceSignals({
      basePath,
      showHighlights: options.showHighlights
    });
  }

  return null;
}

export default async function ProjectDocumentPrivacyWorkspacePage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<WorkspaceSearchParams>;
}>) {
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const requestedPage = toPage(query.page);
  const requestedRunId = toOptionalToken(query.runId);
  const selectedFindingId = toOptionalToken(query.findingId);
  const selectedLineId = toOptionalToken(query.lineId);
  const selectedTokenId = toOptionalToken(query.tokenId);
  const workspaceMode = resolveWorkspaceMode(query.mode);
  const panelParam = normalizePanelSectionParam(query.panel);
  const showHighlights = isHighlightsEnabled(query.highlights);

  if (panelParam.shouldRedirect) {
    redirect(
      projectDocumentPrivacyWorkspacePath(projectId, documentId, {
        findingId: selectedFindingId,
        lineId: selectedLineId,
        mode: workspaceMode,
        panel: panelParam.value,
        page: requestedPage,
        runId: requestedRunId,
        tokenId: selectedTokenId
      })
    );
  }

  const [documentResult, overviewResult, runsResult, workspaceResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectDocumentRedactionOverview(projectId, documentId),
    listProjectDocumentRedactionRuns(projectId, documentId, { pageSize: 50 }),
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
          title="Privacy workspace unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for privacy workspace."
          }
        />
      </main>
    );
  }

  const document = documentResult.data;
  if (!document) {
    notFound();
  }
  const resolvedDocument = document;

  const runs = runsResult.ok && runsResult.data ? runsResult.data.items : [];
  const activeRunId =
    overviewResult.ok && overviewResult.data?.activeRun
      ? overviewResult.data.activeRun.id
      : null;
  const resolvedRunId = requestedRunId ?? activeRunId ?? (runs[0]?.id ?? null);

  if (!resolvedRunId) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No privacy run selected"
            description="Create or activate a privacy run before opening workspace."
          />
        </section>
      </main>
    );
  }

  const runDetailResult = await getProjectDocumentRedactionRun(
    projectId,
    resolvedDocument.id,
    resolvedRunId
  );
  if (!runDetailResult.ok || !runDetailResult.data) {
    if (runDetailResult.status === 404) {
      notFound();
    }
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Run detail unavailable"
            description={runDetailResult.detail ?? "Selected run could not be loaded."}
          />
        </section>
      </main>
    );
  }
  const selectedRun = runDetailResult.data;

  const pagesResult = await listProjectDocumentRedactionRunPages(
    projectId,
    resolvedDocument.id,
    selectedRun.id,
    { pageSize: 500 }
  );

  if (!pagesResult.ok) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Workspace pages unavailable"
            description={pagesResult.detail ?? "Privacy workspace pages could not be loaded."}
          />
        </section>
      </main>
    );
  }

  const pages = pagesResult.data?.items ?? [];
  if (pages.length === 0) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No page projections yet"
            description="Findings and review projections appear once this run has page outputs."
          />
        </section>
      </main>
    );
  }

  const resolvedPage = Math.min(requestedPage, pages.length);
  const selectedPage =
    pages.find((item) => item.pageIndex + 1 === resolvedPage) ?? pages[0] ?? null;

  if (!selectedPage) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No selected page"
            description="Select a page from the privacy queue to open workspace context."
          />
        </section>
      </main>
    );
  }

  const [
    findingsResult,
    pageReviewResult,
    pageEventsResult,
    previewStatusResult,
    linesResult,
    documentPagesResult
  ] = await Promise.all([
    listProjectDocumentRedactionRunPageFindings(
      projectId,
      resolvedDocument.id,
      selectedRun.id,
      selectedPage.pageId,
      {
        findingId: selectedFindingId ?? undefined,
        lineId: selectedLineId ?? undefined,
        tokenId: selectedTokenId ?? undefined,
        workspaceView: true
      }
    ),
    getProjectDocumentRedactionRunPageReview(
      projectId,
      resolvedDocument.id,
      selectedRun.id,
      selectedPage.pageId
    ),
    listProjectDocumentRedactionRunPageEvents(
      projectId,
      resolvedDocument.id,
      selectedRun.id,
      selectedPage.pageId
    ),
    getProjectDocumentRedactionRunPagePreviewStatus(
      projectId,
      resolvedDocument.id,
      selectedRun.id,
      selectedPage.pageId
    ),
    listProjectDocumentTranscriptionRunPageLines(
      projectId,
      resolvedDocument.id,
      selectedRun.inputTranscriptionRunId,
      selectedPage.pageId,
      {
        lineId: selectedLineId ?? undefined,
        tokenId: selectedTokenId ?? undefined,
        workspaceView: true
      }
    ),
      listProjectDocumentPages(projectId, resolvedDocument.id)
  ]);

  const findings = findingsResult.ok && findingsResult.data ? findingsResult.data.items : [];
  const pageReview =
    pageReviewResult.ok && pageReviewResult.data ? pageReviewResult.data : null;
  const pageEvents = pageEventsResult.ok && pageEventsResult.data ? pageEventsResult.data.items : [];
  const previewStatus =
    previewStatusResult.ok && previewStatusResult.data
      ? previewStatusResult.data
      : null;
  const lines = linesResult.ok && linesResult.data ? linesResult.data.items : [];
  const documentPages =
    documentPagesResult.ok && documentPagesResult.data ? documentPagesResult.data.items : [];
  const selectedDocumentPage =
    documentPages.find((item) => item.id === selectedPage.pageId) ?? null;
  const pageWidth = selectedDocumentPage?.width ?? 1;
  const pageHeight = selectedDocumentPage?.height ?? 1;

  const nextUnresolvedHref = await resolveNextUnresolvedHref({
    projectId,
    documentId: resolvedDocument.id,
    runId: selectedRun.id,
    mode: workspaceMode,
    panel: panelParam.value ?? "context",
    showHighlights,
    pages: pages.map((item) => ({
      pageId: item.pageId,
      pageIndex: item.pageIndex,
      unresolvedCount: item.unresolvedCount
    })),
    currentPageIndex: selectedPage.pageIndex,
    findings,
    currentFindingId: selectedFindingId
  });

  const canMutate =
    workspaceResult.ok &&
    workspaceResult.data &&
    (workspaceResult.data.currentUserRole === "PROJECT_LEAD" ||
      workspaceResult.data.currentUserRole === "REVIEWER" ||
      (!workspaceResult.data.isMember && workspaceResult.data.canAccessSettings));

  async function patchFindingDecisionAction(formData: FormData) {
    "use server";

    const runId = toOptionalToken(String(formData.get("runId") ?? "")) ?? selectedRun.id;
    const pageNumber = toPage(String(formData.get("pageNumber") ?? String(resolvedPage)));
    const mode = resolveWorkspaceMode(String(formData.get("mode") ?? workspaceMode));
    const showHighlightsOnReturn =
      String(formData.get("highlights") ?? "on").trim().toLowerCase() !== "off";
    const panel = normalizePanelSectionParam(String(formData.get("panel") ?? "")).value ??
      panelParam.value ??
      "context";
    const findingId = toOptionalToken(String(formData.get("findingId") ?? ""));
    const decisionStatus = toOptionalToken(String(formData.get("decisionStatus") ?? ""));
    const decisionEtag = toOptionalToken(String(formData.get("decisionEtag") ?? ""));
    const reason = toOptionalToken(String(formData.get("reason") ?? ""));
    const actionType = toOptionalToken(String(formData.get("actionType") ?? ""));
    const returnLineId = toOptionalToken(String(formData.get("returnLineId") ?? ""));
    const returnTokenId = toOptionalToken(String(formData.get("returnTokenId") ?? ""));

    const buildReturnPath = (options: {
      error?: string | null;
      findingId?: string | null;
      notice?: string | null;
    }): string => {
      const basePath = projectDocumentPrivacyWorkspacePath(projectId, resolvedDocument.id, {
        page: pageNumber,
        runId,
        findingId: options.findingId ?? findingId ?? undefined,
        lineId: returnLineId ?? undefined,
        mode,
        panel,
        tokenId: returnTokenId ?? undefined
      });
      return appendWorkspaceSignals({
        basePath,
        error: options.error,
        notice: options.notice,
        showHighlights: showHighlightsOnReturn
      });
    };

    if (!findingId || !decisionStatus || !decisionEtag) {
      redirect(
        buildReturnPath({
          error: "Missing finding decision context for workspace mutation."
        })
      );
    }

    if (
      decisionStatus !== "APPROVED" &&
      decisionStatus !== "OVERRIDDEN" &&
      decisionStatus !== "FALSE_POSITIVE"
    ) {
      redirect(
        buildReturnPath({
          error: "Unsupported finding decision status."
        })
      );
    }

    if (
      (decisionStatus === "OVERRIDDEN" || decisionStatus === "FALSE_POSITIVE") &&
      !reason
    ) {
      redirect(
        buildReturnPath({
          error: "Reason is required for override and false-positive decisions."
        })
      );
    }

    const patchResult = await patchProjectDocumentRedactionFinding(
      projectId,
      resolvedDocument.id,
      runId,
      findingId,
      {
        decisionStatus: decisionStatus,
        decisionEtag,
        reason: reason ?? undefined,
        actionType:
          actionType === "MASK" ||
          actionType === "PSEUDONYMIZE" ||
          actionType === "GENERALIZE"
            ? actionType
            : undefined
      }
    );

    if (!patchResult.ok || !patchResult.data) {
      redirect(
        buildReturnPath({
          error:
            patchResult.detail ??
            "Finding decision update failed due to a stale decision tag or immutable run lock."
        })
      );
    }

    const updatedFinding = patchResult.data;
    redirect(
      buildReturnPath({
        findingId: updatedFinding.id,
        notice: "finding_updated"
      })
    );
  }

  async function patchPageReviewAction(formData: FormData) {
    "use server";

    const runId = toOptionalToken(String(formData.get("runId") ?? "")) ?? selectedRun.id;
    const pageId = toOptionalToken(String(formData.get("pageId") ?? "")) ?? selectedPage.pageId;
    const pageNumber = toPage(String(formData.get("pageNumber") ?? String(resolvedPage)));
    const mode = resolveWorkspaceMode(String(formData.get("mode") ?? workspaceMode));
    const showHighlightsOnReturn =
      String(formData.get("highlights") ?? "on").trim().toLowerCase() !== "off";
    const panel = normalizePanelSectionParam(String(formData.get("panel") ?? "")).value ??
      panelParam.value ??
      "context";
    const reviewStatus = toOptionalToken(String(formData.get("reviewStatus") ?? ""));
    const reviewEtag = toOptionalToken(String(formData.get("reviewEtag") ?? ""));
    const reason = toOptionalToken(String(formData.get("reason") ?? ""));
    const returnFindingId = toOptionalToken(String(formData.get("returnFindingId") ?? ""));
    const returnLineId = toOptionalToken(String(formData.get("returnLineId") ?? ""));
    const returnTokenId = toOptionalToken(String(formData.get("returnTokenId") ?? ""));

    const buildReturnPath = (options: {
      error?: string | null;
      notice?: string | null;
    }): string => {
      const basePath = projectDocumentPrivacyWorkspacePath(projectId, resolvedDocument.id, {
        page: pageNumber,
        runId,
        findingId: returnFindingId ?? undefined,
        lineId: returnLineId ?? undefined,
        mode,
        panel,
        tokenId: returnTokenId ?? undefined
      });
      return appendWorkspaceSignals({
        basePath,
        error: options.error,
        notice: options.notice,
        showHighlights: showHighlightsOnReturn
      });
    };

    if (!reviewStatus || !reviewEtag) {
      redirect(
        buildReturnPath({
          error: "Missing page review context for workspace mutation."
        })
      );
    }

    if (
      reviewStatus !== "NOT_STARTED" &&
      reviewStatus !== "IN_REVIEW" &&
      reviewStatus !== "APPROVED" &&
      reviewStatus !== "CHANGES_REQUESTED"
    ) {
      redirect(
        buildReturnPath({
          error: "Unsupported page review status."
        })
      );
    }

    const patchResult = await patchProjectDocumentRedactionPageReview(
      projectId,
      resolvedDocument.id,
      runId,
      pageId,
      {
        reviewStatus,
        reviewEtag,
        reason: reason ?? undefined
      }
    );

    if (!patchResult.ok || !patchResult.data) {
      redirect(
        buildReturnPath({
          error:
            patchResult.detail ??
            "Page review update failed due to a stale review tag or immutable run lock."
        })
      );
    }

    redirect(buildReturnPath({ notice: "page_approved" }));
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Privacy workspace</p>
        <h2>{resolvedDocument.originalFilename}</h2>
        <p className="ukde-muted">
          Fast reviewer workspace with deterministic deep links, append-only finding decisions,
          page approval gating, and controlled versus safeguarded preview context.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentPrivacyPath(projectId, resolvedDocument.id, {
              tab: "triage",
              runId: selectedRun.id
            })}
          >
            Back to triage
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentPrivacyRunPath(projectId, resolvedDocument.id, selectedRun.id)}
          >
            Run detail
          </Link>
        </div>
      </section>

      <PrivacyWorkspaceSurface
        canMutate={Boolean(canMutate)}
        documentId={resolvedDocument.id}
        findings={findings}
        findingsError={findingsResult.ok ? null : findingsResult.detail ?? "Findings unavailable."}
        initialPanelSection={panelParam.value ?? "context"}
        lineLoadError={linesResult.ok ? null : linesResult.detail ?? "Transcript context unavailable."}
        lines={lines}
        mode={workspaceMode}
        nextUnresolvedHref={nextUnresolvedHref}
        onPatchFindingAction={patchFindingDecisionAction}
        onPatchPageReviewAction={patchPageReviewAction}
        pageEvents={pageEvents}
        pageHeight={pageHeight}
        pageNumber={resolvedPage}
        pageReview={pageReview}
        pageReviewError={
          pageReviewResult.ok
            ? null
            : pageReviewResult.detail ?? "Page review projection unavailable."
        }
        pageWidth={pageWidth}
        pages={pages}
        policySnapshotJson={selectedRun.policySnapshotJson}
        previewStatus={previewStatus}
        previewStatusError={
          previewStatusResult.ok
            ? null
            : previewStatusResult.detail ?? "Preview status unavailable."
        }
        projectId={projectId}
        runId={selectedRun.id}
        selectedFindingId={selectedFindingId}
        selectedLineId={selectedLineId}
        selectedPage={selectedPage}
        selectedTokenId={selectedTokenId}
        serverError={toOptionalToken(query.error)}
        serverNotice={resolveNoticeMessage(toOptionalToken(query.notice))}
        showHighlights={showHighlights}
      />
    </main>
  );
}
