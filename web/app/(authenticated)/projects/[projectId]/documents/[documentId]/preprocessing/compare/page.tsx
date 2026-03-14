import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import {
  compareProjectDocumentPreprocessRuns,
  getProjectDocument,
  getProjectDocumentPreprocessRun,
  listProjectDocumentPreprocessRuns
} from "../../../../../../../../lib/documents";
import {
  projectDocumentPreprocessingComparePath,
  projectDocumentPreprocessingPath,
  projectDocumentPreprocessingQualityPath,
  projectDocumentPreprocessingRunPath,
  projectDocumentViewerPath,
  projectsPath,
  type ViewerComparePair,
  type ViewerMode
} from "../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function resolveViewerMode(raw: string | undefined): ViewerMode {
  if (raw === "compare" || raw === "preprocessed") {
    return raw;
  }
  return "original";
}

function resolvePage(raw: string | undefined): number {
  const parsed = raw ? Number.parseInt(raw, 10) : NaN;
  if (!Number.isFinite(parsed)) {
    return 1;
  }
  return Math.max(1, parsed);
}

function resolveViewerComparePair(raw: string | undefined): ViewerComparePair {
  if (raw === "original_binary" || raw === "gray_binary") {
    return raw;
  }
  return "original_gray";
}

function resolveTone(status: string): "danger" | "neutral" | "success" | "warning" {
  if (status === "SUCCEEDED" || status === "PASS") {
    return "success";
  }
  if (status === "FAILED" || status === "BLOCKED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  return "warning";
}

export default async function ProjectDocumentPreprocessComparePage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<{
    baseRunId?: string;
    candidateRunId?: string;
    page?: string;
    viewerComparePair?: string;
    viewerMode?: string;
    viewerRunId?: string;
  }>;
}>) {
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const viewerMode = resolveViewerMode(query.viewerMode);
  const viewerComparePair = resolveViewerComparePair(query.viewerComparePair);
  const viewerPage = resolvePage(query.page);

  const [documentResult, runsResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    listProjectDocumentPreprocessRuns(projectId, documentId, { pageSize: 25 })
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
          title="Preprocess compare unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for preprocess compare."
          }
        />
      </main>
    );
  }
  const document = documentResult.data;
  if (!document) {
    notFound();
  }

  const availableRuns = runsResult.ok && runsResult.data ? runsResult.data.items : [];
  const selectedBaseRunId = query.baseRunId?.trim() || undefined;
  const selectedCandidateRunId = query.candidateRunId?.trim() || undefined;

  let resolvedBaseRunId = selectedBaseRunId;
  let resolvedCandidateRunId = selectedCandidateRunId;

  if (!resolvedBaseRunId && !resolvedCandidateRunId && availableRuns.length >= 2) {
    resolvedBaseRunId = availableRuns[1].id;
    resolvedCandidateRunId = availableRuns[0].id;
  } else if (
    !resolvedBaseRunId &&
    !resolvedCandidateRunId &&
    availableRuns.length === 1
  ) {
    resolvedCandidateRunId = availableRuns[0].id;
  }

  const compareResult =
    resolvedBaseRunId && resolvedCandidateRunId
      ? await compareProjectDocumentPreprocessRuns(
          projectId,
          document.id,
          resolvedBaseRunId,
          resolvedCandidateRunId
        )
      : null;

  const singleRunId =
    !resolvedBaseRunId && resolvedCandidateRunId ? resolvedCandidateRunId : null;
  const singleRunResult = singleRunId
    ? await getProjectDocumentPreprocessRun(projectId, document.id, singleRunId)
    : null;
  const singleRun = singleRunResult?.ok ? singleRunResult.data : null;

  const viewerBackPath = projectDocumentViewerPath(
    projectId,
    document.id,
    viewerPage,
    {
      comparePair: viewerMode === "compare" ? viewerComparePair : undefined,
      mode: viewerMode,
      runId: query.viewerRunId?.trim() || resolvedCandidateRunId || undefined
    }
  );
  const qualityPath = projectDocumentPreprocessingQualityPath(projectId, document.id, {
    runId: resolvedCandidateRunId ?? resolvedBaseRunId ?? undefined
  });
  const stableComparePath = projectDocumentPreprocessingComparePath(
    projectId,
    document.id,
    resolvedBaseRunId,
    resolvedCandidateRunId,
    {
      page: viewerPage,
      viewerComparePair: viewerMode === "compare" ? viewerComparePair : undefined,
      viewerMode,
      viewerRunId: query.viewerRunId?.trim() || resolvedCandidateRunId || undefined
    }
  );

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Preprocessing compare</p>
        <h2>{document.originalFilename}</h2>
        <p className="ukde-muted">
          Canonical preprocessing diagnostics surface for run-level before/after analysis.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentPreprocessingPath(projectId, document.id)}
          >
            Back to preprocessing
          </Link>
          <Link className="secondaryButton" href={qualityPath}>
            Open quality table
          </Link>
          <Link className="secondaryButton" href={viewerBackPath}>
            Back to viewer
          </Link>
          <Link className="secondaryButton" href={stableComparePath}>
            Keep this compare context
          </Link>
        </div>
      </section>

      {!resolvedBaseRunId && !resolvedCandidateRunId ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="Select run context for comparison"
            description="Pick a candidate and optional baseline run to open canonical diagnostics."
          />
          {availableRuns.length >= 2 ? (
            <div className="buttonRow">
              <Link
                className="secondaryButton"
                href={projectDocumentPreprocessingComparePath(
                  projectId,
                  document.id,
                  availableRuns[1].id,
                  availableRuns[0].id,
                  {
                    page: viewerPage,
                    viewerComparePair:
                      viewerMode === "compare" ? viewerComparePair : undefined,
                    viewerMode
                  }
                )}
              >
                Compare latest two runs
              </Link>
            </div>
          ) : null}
        </section>
      ) : null}

      {singleRunId && singleRun ? (
        <section className="sectionCard ukde-panel">
          <h3>Single-run diagnostics</h3>
          <p className="ukde-muted">
            Only one preprocess run is currently available. This route stays in
            single-run mode until another run is available.
          </p>
          <ul className="projectMetaList">
            <li>
              <span>Run</span>
              <strong>
                <Link
                  href={projectDocumentPreprocessingRunPath(
                    projectId,
                    document.id,
                    singleRun.id
                  )}
                >
                  {singleRun.id}
                </Link>
              </strong>
            </li>
            <li>
              <span>Status</span>
              <strong>
                <StatusChip tone={resolveTone(singleRun.status)}>
                  {singleRun.status}
                </StatusChip>
              </strong>
            </li>
            <li>
              <span>Profile</span>
              <strong>{singleRun.profileId}</strong>
            </li>
          </ul>
        </section>
      ) : null}

      {compareResult && !compareResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Compare data unavailable"
            description={compareResult.detail ?? "Compare API request failed."}
          />
        </section>
      ) : null}

      {compareResult && compareResult.ok && compareResult.data ? (
        <>
          <section className="sectionCard ukde-panel">
            <h3>Run comparison summary</h3>
            <ul className="projectMetaList">
              <li>
                <span>Base run</span>
                <strong>
                  <Link
                    href={projectDocumentPreprocessingRunPath(
                      projectId,
                      document.id,
                      compareResult.data.baseRun.id
                    )}
                  >
                    {compareResult.data.baseRun.id}
                  </Link>
                </strong>
              </li>
              <li>
                <span>Candidate run</span>
                <strong>
                  <Link
                    href={projectDocumentPreprocessingRunPath(
                      projectId,
                      document.id,
                      compareResult.data.candidateRun.id
                    )}
                  >
                    {compareResult.data.candidateRun.id}
                  </Link>
                </strong>
              </li>
              <li>
                <span>Base blocked pages</span>
                <strong>{compareResult.data.baseBlockedCount}</strong>
              </li>
              <li>
                <span>Candidate blocked pages</span>
                <strong>{compareResult.data.candidateBlockedCount}</strong>
              </li>
              <li>
                <span>Base warning count</span>
                <strong>{compareResult.data.baseWarningCount}</strong>
              </li>
              <li>
                <span>Candidate warning count</span>
                <strong>{compareResult.data.candidateWarningCount}</strong>
              </li>
            </ul>
          </section>

          <section className="sectionCard ukde-panel">
            <h3>Page diagnostics</h3>
            {compareResult.data.items.length === 0 ? (
              <SectionState
                kind="empty"
                title="No shared page results to compare"
                description="Runs were loaded but did not return per-page diagnostics."
              />
            ) : (
              <ul className="timelineList">
                {compareResult.data.items.map((item) => (
                  <li key={item.pageId}>
                    <div className="auditIntegrityRow">
                      <span>Page {item.pageIndex + 1}</span>
                      <StatusChip tone={resolveTone(item.base?.qualityGateStatus ?? "REVIEW_REQUIRED")}>
                        Base {item.base?.qualityGateStatus ?? "N/A"}
                      </StatusChip>
                      <StatusChip tone={resolveTone(item.candidate?.qualityGateStatus ?? "REVIEW_REQUIRED")}>
                        Candidate {item.candidate?.qualityGateStatus ?? "N/A"}
                      </StatusChip>
                    </div>
                    <p className="ukde-muted">
                      Δ warnings {item.warningDelta >= 0 ? "+" : ""}
                      {item.warningDelta} ·
                      Base warnings{" "}
                      {item.base?.warningsJson.length
                        ? item.base.warningsJson.join(", ")
                        : "none"}{" "}
                      · Candidate warnings{" "}
                      {item.candidate?.warningsJson.length
                        ? item.candidate.warningsJson.join(", ")
                        : "none"}{" "}
                      · Candidate gray{" "}
                      {item.outputAvailability.candidateGray ? "available" : "missing"}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </main>
  );
}
