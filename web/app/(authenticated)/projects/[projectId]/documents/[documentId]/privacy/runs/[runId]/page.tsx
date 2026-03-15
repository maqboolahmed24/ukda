import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import {
  activateProjectDocumentRedactionRun,
  cancelProjectDocumentRedactionRun,
  completeProjectDocumentRedactionRunReview,
  getProjectDocument,
  getProjectDocumentActiveRedactionRun,
  getProjectDocumentRedactionRun,
  getProjectDocumentRedactionRunReview,
  getProjectDocumentRedactionRunStatus,
  listProjectDocumentRedactionRunEvents,
  listProjectDocumentRedactionRunPages,
  listProjectDocumentRedactionRuns,
  startProjectDocumentRedactionRunReview
} from "../../../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../../../lib/projects";
import {
  projectDocumentPrivacyComparePath,
  projectDocumentPrivacyPath,
  projectDocumentPrivacyRunEventsPath,
  projectDocumentPrivacyRunPath,
  projectDocumentPrivacyWorkspacePath,
  projectsPath
} from "../../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

type ReviewActionBlockerCode =
  | "RUN_PAGE_QUEUE_UNAVAILABLE"
  | "RUN_REVIEW_ALREADY_STARTED"
  | "RUN_REVIEW_NOT_OPEN"
  | "PAGE_REVIEW_NOT_STARTED"
  | "PAGE_REVIEW_NOT_APPROVED"
  | "SECOND_REVIEW_PENDING"
  | "PREVIEW_NOT_READY";

type ReviewActionBlocker = {
  code: ReviewActionBlockerCode;
  count: number;
  message: string;
  pageNumbers: number[];
};

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

function resolveReviewTone(
  status: string
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

function withFeedback(path: string, options: { error?: string; notice?: string }): string {
  const params = new URLSearchParams();
  if (options.notice) {
    params.set("notice", options.notice);
  }
  if (options.error) {
    params.set("error", options.error);
  }
  const serialized = params.toString();
  if (!serialized) {
    return path;
  }
  return `${path}?${serialized}`;
}

function asPageNumbers(pages: Array<{ pageIndex: number }>): number[] {
  return pages.map((page) => page.pageIndex + 1);
}

export default async function ProjectDocumentPrivacyRunPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string; runId: string }>;
  searchParams: Promise<{ error?: string; notice?: string }>;
}>) {
  const { projectId, documentId, runId } = await params;
  const query = await searchParams;

  const [
    documentResult,
    runResult,
    runStatusResult,
    reviewResult,
    pagesResult,
    eventsResult,
    activeRunResult,
    runsResult,
    workspaceResult
  ] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectDocumentRedactionRun(projectId, documentId, runId),
    getProjectDocumentRedactionRunStatus(projectId, documentId, runId),
    getProjectDocumentRedactionRunReview(projectId, documentId, runId),
    listProjectDocumentRedactionRunPages(projectId, documentId, runId, {
      pageSize: 500
    }),
    listProjectDocumentRedactionRunEvents(projectId, documentId, runId),
    getProjectDocumentActiveRedactionRun(projectId, documentId),
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
          title="Privacy run unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for this privacy run."
          }
        />
      </main>
    );
  }

  if (!runResult.ok) {
    if (runResult.status === 404) {
      notFound();
    }
    if (runResult.status === 403) {
      redirect(projectsPath);
    }
  }

  const document = documentResult.data;
  const run = runResult.ok ? runResult.data : null;
  if (!document || !run) {
    notFound();
  }
  const resolvedDocument = document;
  const resolvedRun = run;

  const canMutate =
    workspaceResult.ok &&
    workspaceResult.data &&
    (workspaceResult.data.currentUserRole === "PROJECT_LEAD" ||
      workspaceResult.data.currentUserRole === "REVIEWER" ||
      (!workspaceResult.data.isMember && workspaceResult.data.canAccessSettings));

  const runStatus = runStatusResult.ok && runStatusResult.data ? runStatusResult.data : null;
  const runReview = reviewResult.ok && reviewResult.data ? reviewResult.data : null;
  const runPages = pagesResult.ok && pagesResult.data ? pagesResult.data.items : [];
  const runEvents = eventsResult.ok && eventsResult.data ? eventsResult.data.items : [];
  const activeRunId =
    activeRunResult.ok && activeRunResult.data?.run
      ? activeRunResult.data.run.id
      : null;
  const compareTargetRun =
    runsResult.ok && runsResult.data
      ? runsResult.data.items.find((item) => item.id !== resolvedRun.id) ?? null
      : null;

  const runPath = projectDocumentPrivacyRunPath(projectId, resolvedDocument.id, resolvedRun.id);
  const hasRunPageQueue = pagesResult.ok;
  const pagesNotStarted = runPages.filter((page) => page.reviewStatus === "NOT_STARTED");
  const pagesNotApproved = runPages.filter((page) => page.reviewStatus !== "APPROVED");
  const pagesWithPendingSecondReview = runPages.filter(
    (page) => page.requiresSecondReview && page.secondReviewStatus !== "APPROVED"
  );
  const pagesWithPreviewNotReady = runPages.filter((page) => page.previewStatus !== "READY");

  const startReviewBlockers: ReviewActionBlocker[] = [];
  if (!hasRunPageQueue) {
    startReviewBlockers.push({
      code: "RUN_PAGE_QUEUE_UNAVAILABLE",
      count: 1,
      message: "Run page queue is unavailable, so start-review eligibility cannot be verified.",
      pageNumbers: []
    });
  }
  if (runReview && runReview.reviewStatus !== "NOT_READY") {
    startReviewBlockers.push({
      code: "RUN_REVIEW_ALREADY_STARTED",
      count: 1,
      message: "Run review can only start when run review status is NOT_READY.",
      pageNumbers: []
    });
  }
  if (hasRunPageQueue && pagesNotStarted.length > 0) {
    startReviewBlockers.push({
      code: "PAGE_REVIEW_NOT_STARTED",
      count: pagesNotStarted.length,
      message: "Every page must enter review before run review can start.",
      pageNumbers: asPageNumbers(pagesNotStarted)
    });
  }

  const completionBlockers: ReviewActionBlocker[] = [];
  if (!hasRunPageQueue) {
    completionBlockers.push({
      code: "RUN_PAGE_QUEUE_UNAVAILABLE",
      count: 1,
      message: "Run page queue is unavailable, so completion eligibility cannot be verified.",
      pageNumbers: []
    });
  }
  if (!runReview || runReview.reviewStatus !== "IN_REVIEW") {
    completionBlockers.push({
      code: "RUN_REVIEW_NOT_OPEN",
      count: 1,
      message: "Run completion requires run review status IN_REVIEW.",
      pageNumbers: []
    });
  }
  if (hasRunPageQueue && pagesNotApproved.length > 0) {
    completionBlockers.push({
      code: "PAGE_REVIEW_NOT_APPROVED",
      count: pagesNotApproved.length,
      message: "Complete review is disabled until every page review is APPROVED.",
      pageNumbers: asPageNumbers(pagesNotApproved)
    });
  }
  if (hasRunPageQueue && pagesWithPendingSecondReview.length > 0) {
    completionBlockers.push({
      code: "SECOND_REVIEW_PENDING",
      count: pagesWithPendingSecondReview.length,
      message:
        "Complete review is disabled until every required second review is APPROVED by a distinct reviewer.",
      pageNumbers: asPageNumbers(pagesWithPendingSecondReview)
    });
  }
  if (hasRunPageQueue && pagesWithPreviewNotReady.length > 0) {
    completionBlockers.push({
      code: "PREVIEW_NOT_READY",
      count: pagesWithPreviewNotReady.length,
      message: "Complete review is disabled until every page preview status is READY.",
      pageNumbers: asPageNumbers(pagesWithPreviewNotReady)
    });
  }

  const canStartReview = Boolean(canMutate) && startReviewBlockers.length === 0;
  const canCompleteApproval = Boolean(canMutate) && completionBlockers.length === 0;
  const canRequestChanges = Boolean(canMutate) && runReview?.reviewStatus === "IN_REVIEW";
  const canActivateRun = Boolean(canMutate) && runReview?.reviewStatus === "APPROVED";

  async function startReviewAction() {
    "use server";
    const result = await startProjectDocumentRedactionRunReview(
      projectId,
      resolvedDocument.id,
      resolvedRun.id
    );
    if (!result.ok) {
      redirect(
        withFeedback(runPath, {
          error: result.detail ?? "Run review start failed."
        })
      );
    }
    redirect(withFeedback(runPath, { notice: "review_started" }));
  }

  async function completeReviewAction(formData: FormData) {
    "use server";
    const status = String(formData.get("reviewStatus") ?? "").trim();
    if (status !== "APPROVED" && status !== "CHANGES_REQUESTED") {
      redirect(withFeedback(runPath, { error: "Invalid review status." }));
    }
    const reason = String(formData.get("reason") ?? "").trim();
    const result = await completeProjectDocumentRedactionRunReview(
      projectId,
      resolvedDocument.id,
      resolvedRun.id,
      {
        reviewStatus: status,
        reason: reason.length > 0 ? reason : undefined
      }
    );
    if (!result.ok) {
      redirect(
        withFeedback(runPath, {
          error: result.detail ?? "Run review completion failed."
        })
      );
    }
    redirect(
      withFeedback(runPath, {
        notice: status === "APPROVED" ? "review_completed" : "changes_requested"
      })
    );
  }

  async function activateRunAction() {
    "use server";
    const result = await activateProjectDocumentRedactionRun(
      projectId,
      resolvedDocument.id,
      resolvedRun.id
    );
    if (!result.ok) {
      redirect(
        withFeedback(runPath, {
          error: result.detail ?? "Run activation failed."
        })
      );
    }
    redirect(withFeedback(runPath, { notice: "run_activated" }));
  }

  async function cancelRunAction() {
    "use server";
    const result = await cancelProjectDocumentRedactionRun(
      projectId,
      resolvedDocument.id,
      resolvedRun.id
    );
    if (!result.ok) {
      redirect(
        withFeedback(runPath, {
          error: result.detail ?? "Run cancellation failed."
        })
      );
    }
    redirect(withFeedback(runPath, { notice: "run_canceled" }));
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Privacy run detail</p>
        <h2>{resolvedDocument.originalFilename}</h2>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentPrivacyPath(projectId, resolvedDocument.id, { runId: resolvedRun.id })}
          >
            Privacy overview
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentPrivacyPath(projectId, resolvedDocument.id, {
              tab: "triage",
              runId: resolvedRun.id
            })}
          >
            Open triage
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentPrivacyWorkspacePath(projectId, resolvedDocument.id, {
              page: 1,
              runId: resolvedRun.id
            })}
          >
            Open workspace
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentPrivacyRunEventsPath(projectId, resolvedDocument.id, resolvedRun.id)}
          >
            Run events
          </Link>
          {compareTargetRun ? (
            <Link
              className="secondaryButton"
              href={projectDocumentPrivacyComparePath(
                projectId,
                resolvedDocument.id,
                resolvedRun.id,
                compareTargetRun.id,
                { page: 1 }
              )}
            >
              Compare runs
            </Link>
          ) : null}
        </div>
      </section>

      {query.notice ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="success"
            title="Privacy run updated"
            description={
              query.notice === "review_started"
                ? "Run review has started."
                : query.notice === "review_completed"
                  ? "Run review is approved and locked."
                  : query.notice === "changes_requested"
                    ? "Run review marked as changes requested."
                    : query.notice === "run_activated"
                      ? "Run is now the active redaction projection."
                      : "Run state updated successfully."
            }
          />
        </section>
      ) : null}

      {query.error ? (
        <section className="sectionCard ukde-panel">
          <SectionState kind="degraded" title="Run action failed" description={query.error} />
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h3>Run summary</h3>
        <div className="buttonRow">
          <StatusChip tone={resolveRunTone(resolvedRun.status)}>{resolvedRun.status}</StatusChip>
          <StatusChip tone={resolvedRun.isActiveProjection ? "success" : "neutral"}>
            {resolvedRun.isActiveProjection ? "ACTIVE PROJECTION" : "NON-ACTIVE"}
          </StatusChip>
          <StatusChip tone={resolvedRun.isSuperseded ? "neutral" : "warning"}>
            {resolvedRun.isSuperseded ? "SUPERSEDED" : "UNSUPERSEDED"}
          </StatusChip>
          {runReview ? (
            <StatusChip tone={resolveReviewTone(runReview.reviewStatus)}>
              REVIEW {runReview.reviewStatus}
            </StatusChip>
          ) : null}
        </div>
        <ul className="projectMetaList">
          <li>
            <span>Run ID</span>
            <strong>{resolvedRun.id}</strong>
          </li>
          <li>
            <span>Input transcription run</span>
            <strong>{resolvedRun.inputTranscriptionRunId}</strong>
          </li>
          <li>
            <span>Input layout run</span>
            <strong>{resolvedRun.inputLayoutRunId ?? "None"}</strong>
          </li>
          <li>
            <span>Run kind</span>
            <strong>{resolvedRun.runKind}</strong>
          </li>
          <li>
            <span>Policy snapshot</span>
            <strong>{resolvedRun.policySnapshotId}</strong>
          </li>
          <li>
            <span>Detectors version</span>
            <strong>{resolvedRun.detectorsVersion}</strong>
          </li>
          <li>
            <span>Active projection run</span>
            <strong>{activeRunId ?? "None"}</strong>
          </li>
          <li>
            <span>Status endpoint</span>
            <strong>{runStatus?.status ?? resolvedRun.status}</strong>
          </li>
          <li>
            <span>Failure reason</span>
            <strong>{runStatus?.failureReason ?? resolvedRun.failureReason ?? "None"}</strong>
          </li>
          <li>
            <span>Created at</span>
            <strong>{new Date(resolvedRun.createdAt).toISOString()}</strong>
          </li>
          <li>
            <span>Started at</span>
            <strong>{resolvedRun.startedAt ? new Date(resolvedRun.startedAt).toISOString() : "Not started"}</strong>
          </li>
          <li>
            <span>Finished at</span>
            <strong>{resolvedRun.finishedAt ? new Date(resolvedRun.finishedAt).toISOString() : "Not finished"}</strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Review state</h3>
        {!reviewResult.ok || !runReview ? (
          <SectionState
            kind="degraded"
            title="Run review unavailable"
            description={reviewResult.detail ?? "Run review projection could not be loaded."}
          />
        ) : (
          <>
            <ul className="projectMetaList">
              <li>
                <span>Review status</span>
                <strong>{runReview.reviewStatus}</strong>
              </li>
              <li>
                <span>Review started by</span>
                <strong>{runReview.reviewStartedBy ?? "Not started"}</strong>
              </li>
              <li>
                <span>Review started at</span>
                <strong>
                  {runReview.reviewStartedAt
                    ? new Date(runReview.reviewStartedAt).toISOString()
                    : "Not started"}
                </strong>
              </li>
              <li>
                <span>Approved by</span>
                <strong>{runReview.approvedBy ?? "Not approved"}</strong>
              </li>
              <li>
                <span>Approved at</span>
                <strong>
                  {runReview.approvedAt
                    ? new Date(runReview.approvedAt).toISOString()
                    : "Not approved"}
                </strong>
              </li>
              <li>
                <span>Locked at</span>
                <strong>
                  {runReview.lockedAt
                    ? new Date(runReview.lockedAt).toISOString()
                    : "Not locked"}
                </strong>
              </li>
            </ul>
            {canMutate ? (
              <div className="buttonRow">
                <form action={startReviewAction}>
                  <button className="secondaryButton" disabled={!canStartReview} type="submit">
                    Start review
                  </button>
                </form>
                <form action={completeReviewAction}>
                  <input type="hidden" name="reviewStatus" value="APPROVED" />
                  <button className="secondaryButton" disabled={!canCompleteApproval} type="submit">
                    Complete review
                  </button>
                </form>
                <form action={completeReviewAction}>
                  <input type="hidden" name="reviewStatus" value="CHANGES_REQUESTED" />
                  <input
                    type="hidden"
                    name="reason"
                    value="Manual reviewer change request from run detail."
                  />
                  <button className="secondaryButton" disabled={!canRequestChanges} type="submit">
                    Request changes
                  </button>
                </form>
                <form action={activateRunAction}>
                  <button className="secondaryButton" disabled={!canActivateRun} type="submit">
                    Activate run
                  </button>
                </form>
                <form action={cancelRunAction}>
                  <button className="secondaryButton" type="submit">
                    Cancel run
                  </button>
                </form>
              </div>
            ) : null}
            {startReviewBlockers.length > 0 ? (
              <div className="privacyWorkspaceSection">
                <h4>Start review blockers</h4>
                <ul className="timelineList">
                  {startReviewBlockers.map((blocker) => (
                    <li key={blocker.code}>
                      <div className="auditIntegrityRow">
                        <StatusChip tone="warning">{blocker.code}</StatusChip>
                        <span>{blocker.count}</span>
                      </div>
                      <p className="ukde-muted">{blocker.message}</p>
                      {blocker.pageNumbers.length > 0 ? (
                        <p className="ukde-muted">
                          Pages: {blocker.pageNumbers.join(", ")}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {completionBlockers.length > 0 ? (
              <div className="privacyWorkspaceSection">
                <h4>Completion blockers</h4>
                <ul className="timelineList">
                  {completionBlockers.map((blocker) => (
                    <li key={blocker.code}>
                      <div className="auditIntegrityRow">
                        <StatusChip tone="warning">{blocker.code}</StatusChip>
                        <span>{blocker.count}</span>
                      </div>
                      <p className="ukde-muted">{blocker.message}</p>
                      {blocker.pageNumbers.length > 0 ? (
                        <p className="ukde-muted">
                          Pages: {blocker.pageNumbers.join(", ")}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        )}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Page review queue</h3>
        {!pagesResult.ok ? (
          <SectionState
            kind="degraded"
            title="Run pages unavailable"
            description={pagesResult.detail ?? "Run page projections could not be loaded."}
          />
        ) : runPages.length === 0 ? (
          <SectionState
            kind="empty"
            title="No pages projected"
            description="Page-level privacy findings and review state will appear here once ready."
          />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Page</th>
                <th>Findings</th>
                <th>Unresolved</th>
                <th>Review status</th>
                <th>Second review</th>
                <th>Preview</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runPages.map((page) => (
                <tr key={page.pageId}>
                  <td>{page.pageIndex + 1}</td>
                  <td>{page.findingCount}</td>
                  <td>{page.unresolvedCount}</td>
                  <td>
                    <StatusChip tone={resolveReviewTone(page.reviewStatus)}>
                      {page.reviewStatus}
                    </StatusChip>
                  </td>
                  <td>
                    {page.requiresSecondReview ? (
                      <StatusChip tone={page.secondReviewStatus === "APPROVED" ? "success" : "warning"}>
                        {page.secondReviewStatus}
                      </StatusChip>
                    ) : (
                      <StatusChip tone="neutral">NOT_REQUIRED</StatusChip>
                    )}
                  </td>
                  <td>{page.previewStatus ?? "PENDING"}</td>
                  <td>
                    <div className="buttonRow">
                      <Link
                        className="secondaryButton"
                        href={projectDocumentPrivacyWorkspacePath(
                          projectId,
                          resolvedDocument.id,
                          {
                            page: page.pageIndex + 1,
                            runId: resolvedRun.id,
                            findingId: page.topFindings[0]?.id
                          }
                        )}
                      >
                        Workspace
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Latest run events</h3>
        {!eventsResult.ok ? (
          <SectionState
            kind="degraded"
            title="Run event timeline unavailable"
            description={eventsResult.detail ?? "Run events could not be loaded."}
          />
        ) : runEvents.length === 0 ? (
          <SectionState
            kind="empty"
            title="No timeline events"
            description="Append-only run events will appear here as decisions and reviews occur."
          />
        ) : (
          <ul className="timelineList">
            {runEvents.slice(0, 8).map((event) => (
              <li key={`${event.sourceTable}:${event.eventId}`}>
                <div className="auditIntegrityRow">
                  <span>{event.eventType}</span>
                  <span>{new Date(event.createdAt).toISOString()}</span>
                </div>
                <p className="ukde-muted">
                  {event.sourceTable} · actor {event.actorUserId}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
