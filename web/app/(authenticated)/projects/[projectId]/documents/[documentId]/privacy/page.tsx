import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import {
  createProjectDocumentRedactionRun,
  getProjectDocument,
  getProjectDocumentRedactionOverview,
  listProjectDocumentRedactionRunPages,
  listProjectDocumentRedactionRuns
} from "../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../lib/projects";
import {
  projectDocumentPrivacyComparePath,
  projectDocumentPrivacyPath,
  projectDocumentPrivacyPreviewPath,
  projectDocumentPrivacyRunPath,
  projectDocumentPrivacyWorkspacePath,
  projectsPath
} from "../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

type PrivacyTab = "overview" | "triage" | "runs";

type RedactionRunStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELED";

type RedactionReviewStatus =
  | "NOT_STARTED"
  | "IN_REVIEW"
  | "APPROVED"
  | "CHANGES_REQUESTED";

function resolveTab(raw: string | undefined): PrivacyTab {
  if (raw === "triage" || raw === "runs") {
    return raw;
  }
  return "overview";
}

function resolveStatusTone(
  status: RedactionRunStatus
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

function resolveReviewTone(
  status: RedactionReviewStatus
): "danger" | "neutral" | "success" | "warning" {
  if (status === "APPROVED") {
    return "success";
  }
  if (status === "CHANGES_REQUESTED") {
    return "danger";
  }
  if (status === "IN_REVIEW") {
    return "warning";
  }
  return "neutral";
}

function parseBooleanFlag(raw: string | undefined): boolean {
  if (!raw) {
    return false;
  }
  const normalized = raw.trim().toLowerCase();
  return normalized === "1" || normalized === "true" || normalized === "yes";
}

export default async function ProjectDocumentPrivacyPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<{
    category?: string;
    directIdentifiersOnly?: string;
    notice?: string;
    runId?: string;
    tab?: string;
    unresolvedOnly?: string;
  }>;
}>) {
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const tab = resolveTab(query.tab);
  const requestedRunId =
    typeof query.runId === "string" && query.runId.trim().length > 0
      ? query.runId.trim()
      : null;
  const category =
    typeof query.category === "string" && query.category.trim().length > 0
      ? query.category.trim()
      : undefined;
  const unresolvedOnly = parseBooleanFlag(query.unresolvedOnly);
  const directIdentifiersOnly = parseBooleanFlag(query.directIdentifiersOnly);

  const [documentResult, workspaceResult, overviewResult, runsResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectWorkspace(projectId),
    getProjectDocumentRedactionOverview(projectId, documentId),
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
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Privacy route unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for privacy review."
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

  const selectedRun = selectedRunId
    ? runs.find((run) => run.id === selectedRunId) ?? null
    : null;

  const triageResult =
    selectedRunId !== null
      ? await listProjectDocumentRedactionRunPages(projectId, resolvedDocument.id, selectedRunId, {
          category,
          unresolvedOnly,
          directIdentifiersOnly,
          pageSize: 500
        })
      : null;

  const triageRows = triageResult?.ok && triageResult.data ? triageResult.data.items : [];

  async function createRunAction() {
    "use server";
    const result = await createProjectDocumentRedactionRun(projectId, resolvedDocument.id);
    if (!result.ok || !result.data) {
      redirect(
        projectDocumentPrivacyPath(projectId, resolvedDocument.id, {
          tab,
          runId: selectedRunId
        })
      );
    }
    redirect(
      `${projectDocumentPrivacyPath(projectId, resolvedDocument.id, {
        runId: result.data.id
      })}&notice=run_created`
    );
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Privacy review</p>
        <h2>{resolvedDocument.originalFilename}</h2>
        <p className="ukde-muted">
          Canonical privacy route family with explicit active-run projection, triage queue,
          run history, and safeguarded preview access.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            aria-current={tab === "overview" ? "page" : undefined}
            href={projectDocumentPrivacyPath(projectId, resolvedDocument.id, {
              runId: selectedRunId
            })}
          >
            Overview
          </Link>
          <Link
            className="secondaryButton"
            aria-current={tab === "triage" ? "page" : undefined}
            href={projectDocumentPrivacyPath(projectId, resolvedDocument.id, {
              tab: "triage",
              runId: selectedRunId
            })}
          >
            Triage
          </Link>
          <Link
            className="secondaryButton"
            aria-current={tab === "runs" ? "page" : undefined}
            href={projectDocumentPrivacyPath(projectId, resolvedDocument.id, {
              tab: "runs",
              runId: selectedRunId
            })}
          >
            Runs
          </Link>
          {selectedRunId ? (
            <Link
              className="secondaryButton"
              href={projectDocumentPrivacyWorkspacePath(projectId, resolvedDocument.id, {
                page: 1,
                runId: selectedRunId
              })}
            >
              Open active workspace
            </Link>
          ) : null}
          {selectedRunId ? (
            <Link
              className="secondaryButton"
              href={projectDocumentPrivacyRunPath(projectId, resolvedDocument.id, selectedRunId)}
            >
              Complete review
            </Link>
          ) : null}
          {runs.length >= 2 ? (
            <Link
              className="secondaryButton"
              href={projectDocumentPrivacyComparePath(
                projectId,
                resolvedDocument.id,
                runs[1].id,
                runs[0].id,
                { page: 1 }
              )}
            >
              Compare runs
            </Link>
          ) : null}
          {canMutate ? (
            <form action={createRunAction}>
              <button className="secondaryButton" type="submit">
                Create privacy review run
              </button>
            </form>
          ) : null}
        </div>
      </section>

      {query.notice === "run_created" ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="success"
            title="Privacy run created"
            description="A new privacy run was created and is available in the runs list."
          />
        </section>
      ) : null}

      {tab === "overview" ? (
        <section className="sectionCard ukde-panel">
          <h3>Overview</h3>
          {!overviewResult.ok ? (
            <SectionState
              kind="degraded"
              title="Overview unavailable"
              description={
                overviewResult.detail ?? "Privacy overview could not be loaded."
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
                  <span>Findings by category</span>
                  <strong>
                    {overviewResult.data?.findingsByCategory
                      ? Object.entries(overviewResult.data.findingsByCategory)
                          .map(([key, value]) => `${key}:${value}`)
                          .join(" · ")
                      : "None"}
                  </strong>
                </li>
                <li>
                  <span>Unresolved findings</span>
                  <strong>{overviewResult.data?.unresolvedFindings ?? 0}</strong>
                </li>
                <li>
                  <span>Auto-applied</span>
                  <strong>{overviewResult.data?.autoAppliedFindings ?? 0}</strong>
                </li>
                <li>
                  <span>Needs review</span>
                  <strong>{overviewResult.data?.needsReviewFindings ?? 0}</strong>
                </li>
                <li>
                  <span>Overridden</span>
                  <strong>{overviewResult.data?.overriddenFindings ?? 0}</strong>
                </li>
                <li>
                  <span>Pages blocked for review</span>
                  <strong>{overviewResult.data?.pagesBlockedForReview ?? 0}</strong>
                </li>
                <li>
                  <span>Safeguarded previews ready</span>
                  <strong>
                    {overviewResult.data
                      ? `${overviewResult.data.previewReadyPages}/${overviewResult.data.previewTotalPages}`
                      : "0/0"}
                  </strong>
                </li>
                <li>
                  <span>Safeguarded preview failures</span>
                  <strong>{overviewResult.data?.previewFailedPages ?? 0}</strong>
                </li>
              </ul>
              {selectedRun ? (
                <div className="buttonRow">
                  <Link
                    className="secondaryButton"
                    href={projectDocumentPrivacyRunPath(projectId, resolvedDocument.id, selectedRun.id)}
                  >
                    View selected run
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
              description="Create or select a privacy run to open triage."
            />
          ) : !triageResult || !triageResult.ok ? (
            <SectionState
              kind="degraded"
              title="Triage queue unavailable"
              description={triageResult?.detail ?? "Triage rows could not be loaded."}
            />
          ) : triageRows.length === 0 ? (
            <SectionState
              kind="empty"
              title="No triage rows"
              description="No pages matched the current triage filters."
            />
          ) : (
            <>
              <ul className="projectMetaList">
                <li>
                  <span>Category filter</span>
                  <strong>{category ?? "All"}</strong>
                </li>
                <li>
                  <span>Unresolved only</span>
                  <strong>{unresolvedOnly ? "Yes" : "No"}</strong>
                </li>
                <li>
                  <span>Direct identifiers only</span>
                  <strong>{directIdentifiersOnly ? "Yes" : "No"}</strong>
                </li>
              </ul>
              <table>
                <thead>
                  <tr>
                    <th>Page</th>
                    <th>Findings</th>
                    <th>Unresolved</th>
                    <th>Review status</th>
                    <th>Last reviewed by</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {triageRows.map((row) => (
                    <tr key={row.pageId}>
                      <td>{row.pageIndex + 1}</td>
                      <td>{row.findingCount}</td>
                      <td>{row.unresolvedCount}</td>
                      <td>
                        <StatusChip tone={resolveReviewTone(row.reviewStatus)}>
                          {row.reviewStatus}
                        </StatusChip>
                      </td>
                      <td>{row.lastReviewedBy ?? "Not reviewed"}</td>
                      <td>
                        <details>
                          <summary>Open details</summary>
                          <div className="panelCard panelSubtle">
                            <p className="ukde-muted">
                              Preview status: {row.previewStatus ?? "PENDING"}
                            </p>
                            {row.previewStatus === "READY" ? (
                              <img
                                alt={`Safeguarded preview for page ${row.pageIndex + 1}`}
                                src={projectDocumentPrivacyPreviewPath(
                                  projectId,
                                  resolvedDocument.id,
                                  selectedRunId,
                                  row.pageId
                                )}
                                style={{ maxWidth: "100%", borderRadius: "0.5rem" }}
                              />
                            ) : null}
                            <p className="ukde-muted">Top findings</p>
                            {row.topFindings.length === 0 ? (
                              <p className="ukde-muted">None</p>
                            ) : (
                              <ul className="timelineList">
                                {row.topFindings.map((finding) => (
                                  <li key={finding.id}>
                                    <div className="auditIntegrityRow">
                                      <span>{finding.category}</span>
                                      <StatusChip
                                        tone={
                                          finding.decisionStatus === "NEEDS_REVIEW"
                                            ? "warning"
                                            : "neutral"
                                        }
                                      >
                                        {finding.decisionStatus}
                                      </StatusChip>
                                    </div>
                                    <p className="ukde-muted">
                                      Confidence{" "}
                                      {typeof finding.confidence === "number"
                                        ? finding.confidence.toFixed(3)
                                        : "n/a"}{" "}
                                      · Basis {finding.basisPrimary}
                                    </p>
                                  </li>
                                ))}
                              </ul>
                            )}
                            <div className="buttonRow">
                              <Link
                                className="secondaryButton"
                                href={projectDocumentPrivacyWorkspacePath(
                                  projectId,
                                  resolvedDocument.id,
                                  {
                                    page: row.pageIndex + 1,
                                    runId: selectedRunId,
                                    findingId: row.topFindings[0]?.id
                                  }
                                )}
                              >
                                Open in workspace
                              </Link>
                            </div>
                          </div>
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>
      ) : null}

      {tab === "runs" ? (
        <section className="sectionCard ukde-panel">
          <h3>Runs</h3>
          {!runsResult.ok ? (
            <SectionState
              kind="degraded"
              title="Run list unavailable"
              description={runsResult.detail ?? "Redaction runs could not be loaded."}
            />
          ) : runs.length === 0 ? (
            <SectionState
              kind="empty"
              title="No runs yet"
              description="Create a privacy run to begin review and safeguarded preview generation."
            />
          ) : (
            <ul className="timelineList">
              {runs.map((run) => (
                <li key={run.id}>
                  <div className="auditIntegrityRow">
                    <span>{run.id}</span>
                    <StatusChip tone={resolveStatusTone(run.status)}>{run.status}</StatusChip>
                    {run.isActiveProjection ? (
                      <StatusChip tone="success">ACTIVE</StatusChip>
                    ) : null}
                  </div>
                  <p className="ukde-muted">
                    Kind {run.runKind} · detectors {run.detectorsVersion} · transcription basis{" "}
                    {run.inputTranscriptionRunId}
                  </p>
                  <div className="buttonRow">
                    <Link
                      className="secondaryButton"
                      href={projectDocumentPrivacyRunPath(projectId, resolvedDocument.id, run.id)}
                    >
                      Run detail
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
