import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import {
  compareProjectDocumentRedactionRuns,
  getProjectDocument,
  listProjectDocumentRedactionRuns
} from "../../../../../../../../lib/documents";
import {
  projectDocumentPrivacyPath,
  projectDocumentPrivacyRunPath,
  projectDocumentPrivacyWorkspacePath,
  projectsPath
} from "../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

const DECISION_STATUS_ORDER = [
  "AUTO_APPLIED",
  "NEEDS_REVIEW",
  "APPROVED",
  "OVERRIDDEN",
  "FALSE_POSITIVE"
] as const;
const ACTION_TYPE_ORDER = ["MASK", "PSEUDONYMIZE", "GENERALIZE"] as const;

function toOptionalToken(value: string | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  const normalized = value.trim();
  if (!normalized) {
    return undefined;
  }
  return normalized;
}

function toPage(value: string | undefined): number | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return undefined;
  }
  return Math.max(1, parsed);
}

function resolveDeltaTone(
  delta: number
): "danger" | "neutral" | "success" | "warning" {
  if (delta > 0) {
    return "success";
  }
  if (delta < 0) {
    return "danger";
  }
  return "neutral";
}

export default async function ProjectDocumentPrivacyComparePage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<{
    baseRunId?: string;
    candidateRunId?: string;
    findingId?: string;
    lineId?: string;
    page?: string;
    tokenId?: string;
  }>;
}>) {
  const pageLayoutClassName = "homeLayout homeLayout--privacy-compare";
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const selectedPage = toPage(query.page);
  const selectedFindingId = toOptionalToken(query.findingId);
  const selectedLineId = toOptionalToken(query.lineId);
  const selectedTokenId = toOptionalToken(query.tokenId);

  const [documentResult, runsResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    listProjectDocumentRedactionRuns(projectId, documentId, { pageSize: 50 })
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
          title="Privacy compare unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for privacy compare."
          }
        />
      </main>
    );
  }

  const document = documentResult.data;
  if (!document) {
    notFound();
  }

  const availableRuns =
    runsResult.ok && runsResult.data ? runsResult.data.items : [];
  let baseRunId = toOptionalToken(query.baseRunId);
  let candidateRunId = toOptionalToken(query.candidateRunId);

  if (!baseRunId && !candidateRunId && availableRuns.length >= 2) {
    baseRunId = availableRuns[1].id;
    candidateRunId = availableRuns[0].id;
  }

  const compareResult =
    baseRunId && candidateRunId
      ? await compareProjectDocumentRedactionRuns(
          projectId,
          document.id,
          baseRunId,
          candidateRunId,
          {
            page: selectedPage,
            findingId: selectedFindingId,
            lineId: selectedLineId,
            tokenId: selectedTokenId
          }
        )
      : null;

  const compareData =
    compareResult && compareResult.ok && compareResult.data
      ? compareResult.data
      : null;
  const candidateSupersedesBase = Boolean(
    compareData &&
    compareData.candidateRun.supersedesRedactionRunId === compareData.baseRun.id
  );
  const baseSupersedesCandidate = Boolean(
    compareData &&
    compareData.baseRun.supersedesRedactionRunId === compareData.candidateRun.id
  );
  const compareActionState =
    compareData?.compareActionState ?? "NOT_YET_AVAILABLE";

  return (
    <main className={pageLayoutClassName}>
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Privacy compare</p>
        <h2>{document.originalFilename}</h2>
        <p className="ukde-muted">
          Compare run projections by page review state, decision count changes,
          and safeguarded preview status deltas.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentPrivacyPath(projectId, document.id, {
              tab: "runs"
            })}
          >
            Back to runs
          </Link>
          {baseRunId ? (
            <Link
              className="secondaryButton"
              href={projectDocumentPrivacyRunPath(
                projectId,
                document.id,
                baseRunId
              )}
            >
              Base run detail
            </Link>
          ) : null}
          {candidateRunId ? (
            <Link
              className="secondaryButton"
              href={projectDocumentPrivacyRunPath(
                projectId,
                document.id,
                candidateRunId
              )}
            >
              Candidate run detail
            </Link>
          ) : null}
        </div>
      </section>

      {!baseRunId || !candidateRunId ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="Select base and candidate runs"
            description="At least two privacy runs are required for compare mode."
          />
        </section>
      ) : null}

      {compareResult && !compareResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Compare unavailable"
            description={
              compareResult.detail ?? "Could not load privacy run comparison."
            }
          />
        </section>
      ) : null}

      {compareData ? (
        <>
          <section className="sectionCard ukde-panel">
            <h3>Rerun lineage</h3>
            <ul className="projectMetaList">
              <li>
                <span>Candidate supersedes base</span>
                <strong>{candidateSupersedesBase ? "Yes" : "No"}</strong>
              </li>
              <li>
                <span>Base supersedes candidate</span>
                <strong>{baseSupersedesCandidate ? "Yes" : "No"}</strong>
              </li>
              <li>
                <span>Base supersedes run</span>
                <strong>
                  {compareData.baseRun.supersedesRedactionRunId ?? "None"}
                </strong>
              </li>
              <li>
                <span>Base superseded by run</span>
                <strong>
                  {compareData.baseRun.supersededByRedactionRunId ?? "None"}
                </strong>
              </li>
              <li>
                <span>Candidate supersedes run</span>
                <strong>
                  {compareData.candidateRun.supersedesRedactionRunId ?? "None"}
                </strong>
              </li>
              <li>
                <span>Candidate superseded by run</span>
                <strong>
                  {compareData.candidateRun.supersededByRedactionRunId ??
                    "None"}
                </strong>
              </li>
            </ul>
          </section>

          <section className="sectionCard ukde-panel">
            <h3>Compare summary</h3>
            <ul className="projectMetaList">
              <li>
                <span>Base run</span>
                <strong>{compareData.baseRun.id}</strong>
              </li>
              <li>
                <span>Candidate run</span>
                <strong>{compareData.candidateRun.id}</strong>
              </li>
              <li>
                <span>Changed pages</span>
                <strong>{compareData.changedPageCount}</strong>
              </li>
              <li>
                <span>Changed decisions</span>
                <strong>{compareData.changedDecisionCount}</strong>
              </li>
              <li>
                <span>Changed actions</span>
                <strong>{compareData.changedActionCount}</strong>
              </li>
              <li>
                <span>Action compare state</span>
                <strong>{compareData.compareActionState}</strong>
              </li>
              <li>
                <span>Base policy revision</span>
                <strong>
                  {compareData.baseRun.policyId
                    ? `${compareData.baseRun.policyId} (v${compareData.baseRun.policyVersion ?? "?"})`
                    : "Baseline snapshot only"}
                </strong>
              </li>
              <li>
                <span>Candidate policy revision</span>
                <strong>
                  {compareData.candidateRun.policyId
                    ? `${compareData.candidateRun.policyId} (v${compareData.candidateRun.policyVersion ?? "?"})`
                    : "Baseline snapshot only"}
                </strong>
              </li>
              <li>
                <span>Candidate policy status</span>
                <strong>
                  {compareData.candidatePolicyStatus ?? "Unknown"}
                </strong>
              </li>
              <li>
                <span>Comparison-only candidate</span>
                <strong>
                  {compareData.comparisonOnlyCandidate ? "Yes" : "No"}
                </strong>
              </li>
              <li>
                <span>Page filter</span>
                <strong>{selectedPage ?? "All"}</strong>
              </li>
              <li>
                <span>Finding filter</span>
                <strong>{selectedFindingId ?? "None"}</strong>
              </li>
              <li>
                <span>Line filter</span>
                <strong>{selectedLineId ?? "None"}</strong>
              </li>
              <li>
                <span>Token filter</span>
                <strong>{selectedTokenId ?? "None"}</strong>
              </li>
            </ul>
          </section>

          {compareData.comparisonOnlyCandidate ? (
            <section className="sectionCard ukde-panel">
              <SectionState
                kind="degraded"
                title="Comparison-only candidate"
                description="Candidate run is pinned to a validated DRAFT policy and is compare-only until policy activation."
              />
            </section>
          ) : null}

          {compareData.preActivationWarnings.length > 0 ? (
            <section className="sectionCard ukde-panel">
              <h3>Pre-activation warnings</h3>
              <ul className="timelineList">
                {compareData.preActivationWarnings.map((warning) => (
                  <li key={warning.code}>
                    <div className="auditIntegrityRow">
                      <StatusChip tone="warning">{warning.code}</StatusChip>
                      <span>{warning.severity}</span>
                    </div>
                    <p className="ukde-muted">{warning.message}</p>
                    {warning.affectedCategories.length > 0 ? (
                      <p className="ukde-muted">
                        Affected categories:{" "}
                        {warning.affectedCategories.join(", ")}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="sectionCard ukde-panel">
            {compareActionState !== "AVAILABLE" ? (
              <SectionState
                kind="degraded"
                title={
                  compareActionState === "NOT_YET_RERUN"
                    ? "Action compare pending rerun"
                    : "Action compare not yet available"
                }
                description={
                  compareActionState === "NOT_YET_RERUN"
                    ? "Select a policy rerun pair to compare masked, pseudonymized, and generalized outputs."
                    : "One or more page previews are not ready yet. Re-open compare after preview rendering completes."
                }
              />
            ) : null}
            <h3>Page deltas</h3>
            {compareData.items.length === 0 ? (
              <SectionState
                kind="empty"
                title="No compare rows"
                description="No page deltas matched the selected compare filters."
              />
            ) : (
              <table>
                  <thead>
                    <tr>
                      <th>Page</th>
                      <th>Base findings</th>
                      <th>Candidate findings</th>
                      <th>Changed decisions</th>
                      <th>Changed actions</th>
                      <th>Decision deltas</th>
                      <th>Action deltas</th>
                      <th>Action compare</th>
                      <th>Review changed</th>
                      <th>Second review changed</th>
                      <th>Preview ready delta</th>
                      <th>Base preview</th>
                      <th>Candidate preview</th>
                      <th>Workspace links</th>
                    </tr>
                  </thead>
                  <tbody>
                    {compareData.items.map((item) => (
                      <tr key={item.pageId}>
                        <td>{item.pageIndex + 1}</td>
                        <td>{item.baseFindingCount}</td>
                        <td>{item.candidateFindingCount}</td>
                        <td>{item.changedDecisionCount}</td>
                        <td>{item.changedActionCount}</td>
                        <td>
                          <ul className="projectMetaList">
                            {DECISION_STATUS_ORDER.filter(
                              (status) =>
                                item.decisionStatusDeltas[status] !== 0
                            ).map((status) => (
                              <li key={`${item.pageId}:${status}`}>
                                <span>{status}</span>
                                <StatusChip
                                  tone={resolveDeltaTone(
                                    item.decisionStatusDeltas[status]
                                  )}
                                >
                                  {item.decisionStatusDeltas[status] > 0
                                    ? "+"
                                    : ""}
                                  {item.decisionStatusDeltas[status]}
                                </StatusChip>
                              </li>
                            ))}
                            {DECISION_STATUS_ORDER.every(
                              (status) =>
                                item.decisionStatusDeltas[status] === 0
                            ) ? (
                              <li>
                                <span>None</span>
                                <StatusChip tone="neutral">0</StatusChip>
                              </li>
                            ) : null}
                          </ul>
                        </td>
                        <td>
                          <ul className="projectMetaList">
                            {ACTION_TYPE_ORDER.filter(
                              (action) => item.actionTypeDeltas[action] !== 0
                            ).map((action) => (
                              <li key={`${item.pageId}:${action}`}>
                                <span>{action}</span>
                                <StatusChip
                                  tone={resolveDeltaTone(
                                    item.actionTypeDeltas[action]
                                  )}
                                >
                                  {item.actionTypeDeltas[action] > 0 ? "+" : ""}
                                  {item.actionTypeDeltas[action]}
                                </StatusChip>
                              </li>
                            ))}
                            {ACTION_TYPE_ORDER.every(
                              (action) => item.actionTypeDeltas[action] === 0
                            ) ? (
                              <li>
                                <span>None</span>
                                <StatusChip tone="neutral">0</StatusChip>
                              </li>
                            ) : null}
                          </ul>
                        </td>
                        <td>
                          <StatusChip
                            tone={
                              item.actionCompareState === "AVAILABLE"
                                ? "success"
                                : "warning"
                            }
                          >
                            {item.actionCompareState}
                          </StatusChip>
                        </td>
                        <td>
                          <StatusChip
                            tone={
                              item.changedReviewStatus ? "warning" : "neutral"
                            }
                          >
                            {item.changedReviewStatus ? "YES" : "NO"}
                          </StatusChip>
                        </td>
                        <td>
                          <StatusChip
                            tone={
                              item.changedSecondReviewStatus
                                ? "warning"
                                : "neutral"
                            }
                          >
                            {item.changedSecondReviewStatus ? "YES" : "NO"}
                          </StatusChip>
                        </td>
                        <td>
                          <StatusChip
                            tone={resolveDeltaTone(item.previewReadyDelta)}
                          >
                            {item.previewReadyDelta > 0 ? "+" : ""}
                            {item.previewReadyDelta}
                          </StatusChip>
                        </td>
                        <td>{item.basePreviewStatus ?? "PENDING"}</td>
                        <td>{item.candidatePreviewStatus ?? "PENDING"}</td>
                        <td>
                          <div className="buttonRow">
                            <Link
                              className="secondaryButton"
                              href={projectDocumentPrivacyWorkspacePath(
                                projectId,
                                document.id,
                                {
                                  page: item.pageIndex + 1,
                                  runId: compareData.candidateRun.id,
                                  findingId: selectedFindingId,
                                  lineId: selectedLineId,
                                  tokenId: selectedTokenId
                                }
                              )}
                            >
                              Open candidate
                            </Link>
                            <Link
                              className="secondaryButton"
                              href={projectDocumentPrivacyWorkspacePath(
                                projectId,
                                document.id,
                                {
                                  page: item.pageIndex + 1,
                                  runId: compareData.baseRun.id,
                                  findingId: selectedFindingId,
                                  lineId: selectedLineId,
                                  tokenId: selectedTokenId
                                }
                              )}
                            >
                              Open base
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            )}
          </section>
        </>
      ) : null}
    </main>
  );
}
