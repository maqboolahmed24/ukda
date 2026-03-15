import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import {
  compareProjectDocumentTranscriptionRuns,
  finalizeProjectDocumentTranscriptionCompare,
  getProjectDocument,
  listProjectDocumentTranscriptionRuns,
  recordProjectDocumentTranscriptionCompareDecisions
} from "../../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../../lib/projects";
import {
  projectDocumentTranscriptionComparePath,
  projectDocumentTranscriptionPath,
  projectDocumentTranscriptionRunPath,
  projectDocumentTranscriptionWorkspacePath,
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
    error?: string;
    lineId?: string;
    notice?: string;
    page?: string;
    tokenId?: string;
  }>;
}>) {
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const selectedPage = resolvePage(query.page);
  const selectedLineId = query.lineId?.trim() || undefined;
  const selectedTokenId = query.tokenId?.trim() || undefined;
  const notice = query.notice?.trim() || undefined;
  const error = query.error?.trim() || undefined;

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
          resolvedCandidateRunId,
          {
            lineId: selectedLineId,
            page: selectedPage,
            tokenId: selectedTokenId
          }
        )
      : null;
  const compareData =
    compareResult && compareResult.ok && compareResult.data ? compareResult.data : null;

  const canDecide =
    workspaceResult.ok &&
    workspaceResult.data &&
    (workspaceResult.data.currentUserRole === "PROJECT_LEAD" ||
      workspaceResult.data.currentUserRole === "REVIEWER" ||
      (!workspaceResult.data.isMember && workspaceResult.data.canAccessSettings));

  function comparePathWithContext(extra?: { error?: string; notice?: string }) {
    return projectDocumentTranscriptionComparePath(
      projectId,
      documentId,
      resolvedBaseRunId,
      resolvedCandidateRunId,
      {
        page: selectedPage,
        lineId: selectedLineId,
        tokenId: selectedTokenId
      }
    ).concat(
      extra && (extra.error || extra.notice)
        ? `&${new URLSearchParams({
            ...(extra.error ? { error: extra.error } : {}),
            ...(extra.notice ? { notice: extra.notice } : {})
          }).toString()}`
        : ""
    );
  }

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
    const result = await recordProjectDocumentTranscriptionCompareDecisions(
      projectId,
      documentId,
      {
        baseRunId: resolvedBaseRunId,
        candidateRunId: resolvedCandidateRunId,
        items: [
          {
            pageId,
            lineId: lineId || undefined,
            tokenId: tokenId || undefined,
            decision:
              decision === "PROMOTE_CANDIDATE" ? "PROMOTE_CANDIDATE" : "KEEP_BASE",
            decisionEtag: decisionEtag || undefined
          }
        ]
      }
    );
    if (!result.ok) {
      redirect(comparePathWithContext({ error: result.detail ?? "decision_failed" }));
    }
    redirect(comparePathWithContext({ notice: "decision_saved" }));
  }

  async function finalizeCompare() {
    "use server";
    if (!resolvedBaseRunId || !resolvedCandidateRunId || !compareData) {
      return;
    }
    const pageScope =
      compareData.items.length === 1
        ? [compareData.items[0].pageId]
        : undefined;
    const result = await finalizeProjectDocumentTranscriptionCompare(
      projectId,
      documentId,
      {
        baseRunId: resolvedBaseRunId,
        candidateRunId: resolvedCandidateRunId,
        expectedCompareDecisionSnapshotHash: compareData.compareDecisionSnapshotHash,
        pageIds: pageScope
      }
    );
    if (!result.ok || !result.data) {
      redirect(comparePathWithContext({ error: result.detail ?? "finalize_failed" }));
    }
    redirect(
      projectDocumentTranscriptionRunPath(
        projectId,
        documentId,
        result.data.composedRun.id
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

      {notice ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="success"
            title="Compare update"
            description={
              notice === "decision_saved"
                ? "Compare decision saved."
                : "Compare operation completed."
            }
          />
        </section>
      ) : null}

      {error ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Compare action failed"
            description={error}
          />
        </section>
      ) : null}

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

      {compareData ? (
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
                      compareData.baseRun.id
                    )}
                  >
                    {compareData.baseRun.id}
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
                      compareData.candidateRun.id
                    )}
                  >
                    {compareData.candidateRun.id}
                  </Link>
                </strong>
              </li>
              <li>
                <span>Changed lines</span>
                <strong>{compareData.changedLineCount}</strong>
              </li>
              <li>
                <span>Changed tokens</span>
                <strong>{compareData.changedTokenCount}</strong>
              </li>
              <li>
                <span>Changed confidence entries</span>
                <strong>{compareData.changedConfidenceCount}</strong>
              </li>
              <li>
                <span>Base engine</span>
                <strong>{String(compareData.baseEngineMetadata.engine ?? "unknown")}</strong>
              </li>
              <li>
                <span>Candidate engine</span>
                <strong>{String(compareData.candidateEngineMetadata.engine ?? "unknown")}</strong>
              </li>
              <li>
                <span>Decision snapshot hash</span>
                <strong>{compareData.compareDecisionSnapshotHash}</strong>
              </li>
              <li>
                <span>Current decisions</span>
                <strong>{compareData.compareDecisionCount}</strong>
              </li>
              <li>
                <span>Decision events</span>
                <strong>{compareData.compareDecisionEventCount}</strong>
              </li>
            </ul>
            {canDecide ? (
              <form action={finalizeCompare} className="buttonRow">
                <button
                  className="secondaryButton"
                  type="submit"
                  disabled={compareData.compareDecisionCount < 1}
                >
                  Finalize into REVIEW_COMPOSED run
                </button>
              </form>
            ) : null}
          </section>

          <section className="sectionCard ukde-panel">
            <h3>Page-level diff shell</h3>
            {compareData.items.length === 0 ? (
              <SectionState
                kind="empty"
                title="No diff rows available"
                description="Compared runs loaded, but no page-level rows were returned."
              />
            ) : (
              <ul className="timelineList">
                {compareData.items.map((page) => (
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
                        <p className="ukde-muted">
                          Base source:{" "}
                          {String(
                            (line.base?.flagsJson?.lineage as { sourceType?: string } | undefined)
                              ?.sourceType ?? "ENGINE_OUTPUT"
                          )}{" "}
                          · Candidate source:{" "}
                          {String(
                            (line.candidate?.flagsJson?.lineage as { sourceType?: string } | undefined)
                              ?.sourceType ?? "ENGINE_OUTPUT"
                          )}
                        </p>
                        {line.decision ? (
                          <p className="ukde-muted">
                            Decision {line.decision.decision} by {line.decision.decidedBy} at{" "}
                            {new Date(line.decision.decidedAt).toISOString()}
                            {line.decision.decisionReason
                              ? ` · ${line.decision.decisionReason}`
                              : ""}
                          </p>
                        ) : null}
                        <div className="buttonRow">
                          <Link
                            className="secondaryButton"
                            href={projectDocumentTranscriptionWorkspacePath(
                              projectId,
                              document.id,
                              {
                                lineId: line.lineId,
                                page: page.pageIndex + 1,
                                runId: compareData.candidateRun.id,
                                tokenId: null
                              }
                            )}
                          >
                            Open in workspace
                          </Link>
                        </div>
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
                        {token.decision ? (
                          <p className="ukde-muted">
                            Decision {token.decision.decision} by {token.decision.decidedBy} at{" "}
                            {new Date(token.decision.decidedAt).toISOString()}
                            {token.decision.decisionReason
                              ? ` · ${token.decision.decisionReason}`
                              : ""}
                          </p>
                        ) : null}
                        <div className="buttonRow">
                          <Link
                            className="secondaryButton"
                            href={projectDocumentTranscriptionWorkspacePath(
                              projectId,
                              document.id,
                              {
                                lineId: token.lineId ?? undefined,
                                page: page.pageIndex + 1,
                                runId: compareData.candidateRun.id,
                                tokenId: token.tokenId
                              }
                            )}
                          >
                            Open token in workspace
                          </Link>
                        </div>
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
