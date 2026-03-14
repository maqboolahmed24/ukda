import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import {
  compareProjectDocumentTranscriptionRuns,
  getProjectDocument,
  listProjectDocumentTranscriptionRuns,
  recordProjectDocumentTranscriptionCompareDecisions
} from "../../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../../lib/projects";
import {
  projectDocumentTranscriptionComparePath,
  projectDocumentTranscriptionPath,
  projectDocumentTranscriptionRunPath,
  projectsPath
} from "../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function resolvePage(raw: string | undefined): number {
  const parsed = raw ? Number.parseInt(raw, 10) : NaN;
  if (!Number.isFinite(parsed)) {
    return 1;
  }
  return Math.max(1, parsed);
}

function resolveTone(status: string): "danger" | "neutral" | "success" | "warning" {
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

export default async function ProjectDocumentTranscriptionComparePage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<{
    baseRunId?: string;
    candidateRunId?: string;
    lineId?: string;
    page?: string;
    tokenId?: string;
  }>;
}>) {
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const selectedPage = resolvePage(query.page);
  const selectedLineId = query.lineId?.trim() || undefined;
  const selectedTokenId = query.tokenId?.trim() || undefined;

  const [documentResult, runsResult, workspaceResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
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
          title="Transcription compare unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for transcription compare."
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
  }

  const compareResult =
    resolvedBaseRunId && resolvedCandidateRunId
      ? await compareProjectDocumentTranscriptionRuns(
          projectId,
          document.id,
          resolvedBaseRunId,
          resolvedCandidateRunId
        )
      : null;

  const canDecide =
    workspaceResult.ok &&
    workspaceResult.data &&
    (workspaceResult.data.currentUserRole === "PROJECT_LEAD" ||
      workspaceResult.data.currentUserRole === "REVIEWER" ||
      (!workspaceResult.data.isMember && workspaceResult.data.canAccessSettings));

  async function recordDecision(formData: FormData) {
    "use server";
    if (!resolvedBaseRunId || !resolvedCandidateRunId) {
      return;
    }
    const pageId = String(formData.get("pageId") ?? "").trim();
    const lineId = String(formData.get("lineId") ?? "").trim();
    const tokenId = String(formData.get("tokenId") ?? "").trim();
    const decision = String(formData.get("decision") ?? "").trim();
    const decisionEtag = String(formData.get("decisionEtag") ?? "").trim();
    if (!pageId || !decision) {
      return;
    }
    await recordProjectDocumentTranscriptionCompareDecisions(projectId, documentId, {
      baseRunId: resolvedBaseRunId,
      candidateRunId: resolvedCandidateRunId,
      items: [
        {
          pageId,
          lineId: lineId || undefined,
          tokenId: tokenId || undefined,
          decision: decision === "PROMOTE_CANDIDATE" ? "PROMOTE_CANDIDATE" : "KEEP_BASE",
          decisionEtag: decisionEtag || undefined
        }
      ]
    });
    redirect(
      projectDocumentTranscriptionComparePath(
        projectId,
        documentId,
        resolvedBaseRunId,
        resolvedCandidateRunId,
        {
          page: selectedPage,
          lineId: selectedLineId,
          tokenId: selectedTokenId
        }
      )
    );
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Transcription compare</p>
        <h2>{document.originalFilename}</h2>
        <p className="ukde-muted">
          Governed base-versus-candidate diffs. Decisions are explicit and append-only.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentTranscriptionPath(projectId, document.id, { tab: "runs" })}
          >
            Back to transcription runs
          </Link>
          {resolvedBaseRunId && resolvedCandidateRunId ? (
            <Link
              className="secondaryButton"
              href={projectDocumentTranscriptionComparePath(
                projectId,
                document.id,
                resolvedBaseRunId,
                resolvedCandidateRunId,
                { page: selectedPage, lineId: selectedLineId, tokenId: selectedTokenId }
              )}
            >
              Keep compare context
            </Link>
          ) : null}
        </div>
      </section>

      {!resolvedBaseRunId || !resolvedCandidateRunId ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="Select base and candidate runs"
            description="At least two runs are required to open transcription compare mode."
          />
        </section>
      ) : null}

      {compareResult && !compareResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Compare data unavailable"
            description={
              compareResult.detail ??
              "Compared runs must share preprocess/layout basis and layout snapshot hash."
            }
          />
        </section>
      ) : null}

      {compareResult && compareResult.ok && compareResult.data ? (
        <>
          <section className="sectionCard ukde-panel">
            <h3>Compare summary</h3>
            <ul className="projectMetaList">
              <li>
                <span>Base run</span>
                <strong>
                  <Link
                    href={projectDocumentTranscriptionRunPath(
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
                    href={projectDocumentTranscriptionRunPath(
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
                <span>Changed lines</span>
                <strong>{compareResult.data.changedLineCount}</strong>
              </li>
              <li>
                <span>Changed tokens</span>
                <strong>{compareResult.data.changedTokenCount}</strong>
              </li>
              <li>
                <span>Changed confidence entries</span>
                <strong>{compareResult.data.changedConfidenceCount}</strong>
              </li>
              <li>
                <span>Base engine</span>
                <strong>{String(compareResult.data.baseEngineMetadata.engine ?? "unknown")}</strong>
              </li>
              <li>
                <span>Candidate engine</span>
                <strong>{String(compareResult.data.candidateEngineMetadata.engine ?? "unknown")}</strong>
              </li>
            </ul>
          </section>

          <section className="sectionCard ukde-panel">
            <h3>Page-level diff shell</h3>
            {compareResult.data.items.length === 0 ? (
              <SectionState
                kind="empty"
                title="No diff rows available"
                description="Compared runs loaded, but no page-level rows were returned."
              />
            ) : (
              <ul className="timelineList">
                {compareResult.data.items.map((page) => (
                  <li key={page.pageId}>
                    <div className="auditIntegrityRow">
                      <span>Page {page.pageIndex + 1}</span>
                      <StatusChip tone={resolveTone(page.base?.status ?? "FAILED")}>
                        Base {page.base?.status ?? "N/A"}
                      </StatusChip>
                      <StatusChip tone={resolveTone(page.candidate?.status ?? "FAILED")}>
                        Candidate {page.candidate?.status ?? "N/A"}
                      </StatusChip>
                    </div>
                    <p className="ukde-muted">
                      Lines changed {page.changedLineCount} · tokens changed {page.changedTokenCount} ·
                      confidence deltas {page.changedConfidenceCount}
                    </p>
                    <p className="ukde-muted">
                      Output availability: base XML{" "}
                      {page.outputAvailability.basePageXml ? "yes" : "no"} / candidate XML{" "}
                      {page.outputAvailability.candidatePageXml ? "yes" : "no"} / base hOCR{" "}
                      {page.outputAvailability.baseHocr ? "yes" : "no"} / candidate hOCR{" "}
                      {page.outputAvailability.candidateHocr ? "yes" : "no"}
                    </p>
                    {page.lineDiffs.slice(0, 6).map((line) => (
                      <div key={`${page.pageId}:${line.lineId}`} className="ukde-panel">
                        <p className="ukde-muted">
                          Line {line.lineId} · changed {line.changed ? "yes" : "no"} ·
                          confidence delta{" "}
                          {typeof line.confidenceDelta === "number"
                            ? line.confidenceDelta.toFixed(3)
                            : "n/a"}
                        </p>
                        <p className="ukde-muted">
                          Base: {line.base?.textDiplomatic || "<empty>"} · Candidate:{" "}
                          {line.candidate?.textDiplomatic || "<empty>"}
                        </p>
                        {canDecide ? (
                          <form action={recordDecision} className="buttonRow">
                            <input type="hidden" name="pageId" value={page.pageId} />
                            <input type="hidden" name="lineId" value={line.lineId} />
                            <input type="hidden" name="tokenId" value="" />
                            <input
                              type="hidden"
                              name="decisionEtag"
                              value={line.decision?.decisionEtag ?? ""}
                            />
                            <button className="secondaryButton" name="decision" value="KEEP_BASE">
                              Keep base
                            </button>
                            <button
                              className="secondaryButton"
                              name="decision"
                              value="PROMOTE_CANDIDATE"
                            >
                              Promote candidate
                            </button>
                          </form>
                        ) : (
                          <p className="ukde-muted">
                            Decision controls are limited to PROJECT_LEAD, REVIEWER, and ADMIN.
                          </p>
                        )}
                      </div>
                    ))}
                    {page.tokenDiffs.slice(0, 4).map((token) => (
                      <div key={`${page.pageId}:${token.tokenId}`} className="ukde-panel">
                        <p className="ukde-muted">
                          Token {token.tokenId} · changed {token.changed ? "yes" : "no"} · base{" "}
                          {token.base?.tokenText || "<empty>"} · candidate{" "}
                          {token.candidate?.tokenText || "<empty>"}
                        </p>
                        {canDecide ? (
                          <form action={recordDecision} className="buttonRow">
                            <input type="hidden" name="pageId" value={page.pageId} />
                            <input type="hidden" name="lineId" value={token.lineId ?? ""} />
                            <input type="hidden" name="tokenId" value={token.tokenId} />
                            <input
                              type="hidden"
                              name="decisionEtag"
                              value={token.decision?.decisionEtag ?? ""}
                            />
                            <button className="secondaryButton" name="decision" value="KEEP_BASE">
                              Keep base
                            </button>
                            <button
                              className="secondaryButton"
                              name="decision"
                              value="PROMOTE_CANDIDATE"
                            >
                              Promote candidate
                            </button>
                          </form>
                        ) : null}
                      </div>
                    ))}
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
