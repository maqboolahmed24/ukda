import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import { resolveCurrentSession } from "../../../../../lib/auth/session";
import {
  claimExportRequestReview,
  decideExportRequest,
  getExportRequest,
  getExportRequestEvents,
  getExportRequestReleasePack,
  getExportRequestReviewEvents,
  getExportRequestReviews,
  listExportRequests,
  listExportReviewQueue,
  releaseExportRequestReview,
  startExportRequestReview
} from "../../../../../lib/exports";
import { getProjectSummary } from "../../../../../lib/projects";
import { normalizeOptionalTextParam } from "../../../../../lib/url-state";

export const dynamic = "force-dynamic";

type QueueFilters = {
  status?: string;
  agingBucket?: string;
  reviewerUserId?: string;
};

const STATUS_OPTIONS = [
  "",
  "SUBMITTED",
  "RESUBMITTED",
  "IN_REVIEW",
  "APPROVED",
  "RETURNED",
  "REJECTED",
  "EXPORTED"
];
const AGING_OPTIONS = ["", "UNSTARTED", "NO_SLA", "ON_TRACK", "DUE_SOON", "OVERDUE"];

function toQueueHref(projectId: string, filters: QueueFilters, requestId?: string): string {
  const query = new URLSearchParams();
  if (filters.status) {
    query.set("status", filters.status);
  }
  if (filters.agingBucket) {
    query.set("agingBucket", filters.agingBucket);
  }
  if (filters.reviewerUserId) {
    query.set("reviewerUserId", filters.reviewerUserId);
  }
  if (requestId) {
    query.set("requestId", requestId);
  }
  const encoded = query.toString();
  return encoded
    ? `/projects/${projectId}/export-review?${encoded}`
    : `/projects/${projectId}/export-review`;
}

function withNotice(baseHref: string, key: string, value: string): string {
  const [path, existing] = baseHref.split("?");
  const query = new URLSearchParams(existing ?? "");
  query.set(key, value);
  return `${path}?${query.toString()}`;
}

function formatTime(value: string | null | undefined): string {
  if (!value) {
    return "Not set";
  }
  return new Date(value).toLocaleString();
}

export default async function ProjectExportReviewPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{
    status?: string;
    agingBucket?: string;
    reviewerUserId?: string;
    requestId?: string;
    notice?: string;
    error?: string;
  }>;
}>) {
  const { projectId } = await params;
  const query = await searchParams;
  const filters: QueueFilters = {
    status: normalizeOptionalTextParam(query.status),
    agingBucket: normalizeOptionalTextParam(query.agingBucket),
    reviewerUserId: normalizeOptionalTextParam(query.reviewerUserId)
  };
  const selectedRequestId = normalizeOptionalTextParam(query.requestId);
  const [projectResult, queueResult, session] = await Promise.all([
    getProjectSummary(projectId),
    listExportReviewQueue(projectId, filters),
    resolveCurrentSession()
  ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }
  if (!session) {
    redirect("/login");
  }

  const queueItems = queueResult.ok && queueResult.data ? queueResult.data.items : [];
  const selectedQueueItem =
    queueItems.find((item) => item.request.id === selectedRequestId) ?? queueItems[0] ?? null;
  const selectedRequest = selectedQueueItem?.request ?? null;
  const selectedRequestHref = selectedRequest
    ? toQueueHref(projectId, filters, selectedRequest.id)
    : toQueueHref(projectId, filters);
  const canMutate = queueResult.ok && queueResult.data ? !queueResult.data.readOnly : false;

  const [requestResult, reviewsResult, eventsResult, reviewEventsResult, releasePackResult, historyResult, requesterHistoryResult] =
    selectedRequest
      ? await Promise.all([
          getExportRequest(projectId, selectedRequest.id),
          getExportRequestReviews(projectId, selectedRequest.id),
          getExportRequestEvents(projectId, selectedRequest.id),
          getExportRequestReviewEvents(projectId, selectedRequest.id),
          getExportRequestReleasePack(projectId, selectedRequest.id),
          listExportRequests(projectId, { limit: 8 }),
          listExportRequests(projectId, {
            requesterId: selectedRequest.submittedBy,
            limit: 8
          })
        ])
      : await Promise.all([
          Promise.resolve(null),
          Promise.resolve(null),
          Promise.resolve(null),
          Promise.resolve(null),
          Promise.resolve(null),
          listExportRequests(projectId, { limit: 8 }),
          Promise.resolve(null)
        ]);

  const activeReview =
    selectedQueueItem && selectedQueueItem.activeReviewId
      ? selectedQueueItem.reviews.find(
          (review) => review.id === selectedQueueItem.activeReviewId
        ) ?? null
      : null;
  const activeReviewAssignedToSelf =
    activeReview?.assignedReviewerUserId === session.user.id;
  const activeReviewAssignedToOther =
    Boolean(activeReview?.assignedReviewerUserId) && !activeReviewAssignedToSelf;

  const claimAction = async (formData: FormData) => {
    "use server";
    const currentProjectId = String(formData.get("projectId") ?? "").trim();
    const currentRequestId = String(formData.get("exportRequestId") ?? "").trim();
    const currentReviewId = String(formData.get("reviewId") ?? "").trim();
    const currentReviewEtag = String(formData.get("reviewEtag") ?? "").trim();
    const redirectTo = String(formData.get("redirectTo") ?? "").trim();
    if (!currentProjectId || !currentRequestId || !currentReviewId || !currentReviewEtag) {
      redirect(withNotice(redirectTo || `/projects/${projectId}/export-review`, "error", "claim_invalid"));
    }
    const result = await claimExportRequestReview(
      currentProjectId,
      currentRequestId,
      currentReviewId,
      { reviewEtag: currentReviewEtag }
    );
    if (!result.ok) {
      redirect(withNotice(redirectTo || `/projects/${projectId}/export-review`, "error", "claim_failed"));
    }
    redirect(withNotice(redirectTo || `/projects/${projectId}/export-review`, "notice", "claimed"));
  };

  const releaseAction = async (formData: FormData) => {
    "use server";
    const currentProjectId = String(formData.get("projectId") ?? "").trim();
    const currentRequestId = String(formData.get("exportRequestId") ?? "").trim();
    const currentReviewId = String(formData.get("reviewId") ?? "").trim();
    const currentReviewEtag = String(formData.get("reviewEtag") ?? "").trim();
    const redirectTo = String(formData.get("redirectTo") ?? "").trim();
    if (!currentProjectId || !currentRequestId || !currentReviewId || !currentReviewEtag) {
      redirect(withNotice(redirectTo || `/projects/${projectId}/export-review`, "error", "release_invalid"));
    }
    const result = await releaseExportRequestReview(
      currentProjectId,
      currentRequestId,
      currentReviewId,
      { reviewEtag: currentReviewEtag }
    );
    if (!result.ok) {
      redirect(withNotice(redirectTo || `/projects/${projectId}/export-review`, "error", "release_failed"));
    }
    redirect(withNotice(redirectTo || `/projects/${projectId}/export-review`, "notice", "released"));
  };

  const startAction = async (formData: FormData) => {
    "use server";
    const currentProjectId = String(formData.get("projectId") ?? "").trim();
    const currentRequestId = String(formData.get("exportRequestId") ?? "").trim();
    const currentReviewId = String(formData.get("reviewId") ?? "").trim();
    const currentReviewEtag = String(formData.get("reviewEtag") ?? "").trim();
    const redirectTo = String(formData.get("redirectTo") ?? "").trim();
    if (!currentProjectId || !currentRequestId || !currentReviewId || !currentReviewEtag) {
      redirect(withNotice(redirectTo || `/projects/${projectId}/export-review`, "error", "start_invalid"));
    }
    const result = await startExportRequestReview(currentProjectId, currentRequestId, {
      reviewId: currentReviewId,
      reviewEtag: currentReviewEtag
    });
    if (!result.ok) {
      redirect(withNotice(redirectTo || `/projects/${projectId}/export-review`, "error", "start_failed"));
    }
    redirect(withNotice(redirectTo || `/projects/${projectId}/export-review`, "notice", "started"));
  };

  const decisionAction = async (formData: FormData) => {
    "use server";
    const currentProjectId = String(formData.get("projectId") ?? "").trim();
    const currentRequestId = String(formData.get("exportRequestId") ?? "").trim();
    const currentReviewId = String(formData.get("reviewId") ?? "").trim();
    const currentReviewEtag = String(formData.get("reviewEtag") ?? "").trim();
    const currentDecision = String(formData.get("decision") ?? "").trim().toUpperCase();
    const currentDecisionReason = String(formData.get("decisionReason") ?? "");
    const currentReturnComment = String(formData.get("returnComment") ?? "");
    const redirectTo = String(formData.get("redirectTo") ?? "").trim();
    if (!currentProjectId || !currentRequestId || !currentReviewId || !currentReviewEtag) {
      redirect(withNotice(redirectTo || `/projects/${projectId}/export-review`, "error", "decision_invalid"));
    }
    const result = await decideExportRequest(currentProjectId, currentRequestId, {
      reviewId: currentReviewId,
      reviewEtag: currentReviewEtag,
      decision:
        currentDecision === "APPROVE" || currentDecision === "REJECT" || currentDecision === "RETURN"
          ? currentDecision
          : "RETURN",
      decisionReason: currentDecisionReason || undefined,
      returnComment: currentReturnComment || undefined
    });
    if (!result.ok) {
      redirect(withNotice(redirectTo || `/projects/${projectId}/export-review`, "error", "decision_failed"));
    }
    redirect(withNotice(redirectTo || `/projects/${projectId}/export-review`, "notice", "decision_recorded"));
  };

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Export review queue</h1>
        <p className="ukde-muted">
          Reviewer queue for governed release decisions with optimistic-lock review stages.
        </p>
        {query.notice ? (
          <p className="ukde-muted">Action completed: {query.notice}</p>
        ) : null}
        {query.error ? (
          <SectionState
            kind="error"
            title="Action failed"
            description={`The requested workflow mutation failed (${query.error}). Refresh and retry with the latest review stage ETag.`}
          />
        ) : null}
        <form className="ukde-form-stack" method="get">
          <div className="detailGrid">
            <div>
              <label className="ukde-form-label" htmlFor="status">
                Status
              </label>
              <select className="ukde-input" defaultValue={filters.status ?? ""} id="status" name="status">
                {STATUS_OPTIONS.map((value) => (
                  <option key={value || "all-status"} value={value}>
                    {value || "All open"}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="ukde-form-label" htmlFor="agingBucket">
                Aging bucket
              </label>
              <select
                className="ukde-input"
                defaultValue={filters.agingBucket ?? ""}
                id="agingBucket"
                name="agingBucket"
              >
                {AGING_OPTIONS.map((value) => (
                  <option key={value || "all-aging"} value={value}>
                    {value || "Any aging"}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="ukde-form-label" htmlFor="reviewerUserId">
                Reviewer user id
              </label>
              <input
                className="ukde-input"
                defaultValue={filters.reviewerUserId ?? ""}
                id="reviewerUserId"
                name="reviewerUserId"
                placeholder="reviewer id"
                type="text"
              />
            </div>
          </div>
          <div className="buttonRow">
            <button className="projectPrimaryButton" type="submit">
              Apply filters
            </button>
            <Link className="secondaryButton" href={`/projects/${projectId}/export-requests`}>
              Request history
            </Link>
          </div>
        </form>
      </section>

      {!queueResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Queue unavailable"
            description={queueResult.detail ?? "Failed to load export review queue."}
          />
        </section>
      ) : queueItems.length === 0 ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="Queue is empty"
            description="No requests match the current status, aging, and reviewer filters."
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <table className="ukde-data-table">
            <thead>
              <tr>
                <th>Request</th>
                <th>Status</th>
                <th>Risk path</th>
                <th>Aging</th>
                <th>SLA due</th>
                <th>Active stage</th>
                <th>Assigned reviewer</th>
              </tr>
            </thead>
            <tbody>
              {queueItems.map((item) => (
                <tr key={item.request.id}>
                  <td>
                    <Link className="secondaryButton" href={toQueueHref(projectId, filters, item.request.id)}>
                      {item.request.id}
                    </Link>
                  </td>
                  <td>{item.request.status}</td>
                  <td>
                    {item.request.riskClassification} / {item.request.reviewPath}
                    {item.request.requiresSecondReview ? " (dual)" : ""}
                  </td>
                  <td>{item.agingBucket}</td>
                  <td>{formatTime(item.request.slaDueAt)}</td>
                  <td>{item.activeReviewStage ?? "None"}</td>
                  <td>{item.activeReviewAssignedReviewerUserId ?? "Unassigned"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {!selectedRequest ? null : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Decision surface</h2>
          <p className="ukde-muted">
            Active request <code>{selectedRequest.id}</code> revision {selectedRequest.requestRevision}{" "}
            by {selectedRequest.submittedBy}.
          </p>
          {queueResult.data?.readOnly ? (
            <SectionState
              kind="degraded"
              title="Read-only auditor mode"
              description="Queue, release pack, and history surfaces are view-only for auditors."
            />
          ) : null}
          {!activeReview ? (
            <SectionState
              kind="degraded"
              title="No active required stage"
              description="This request revision is terminal or has no pending required review stage."
            />
          ) : (
            <>
              <div className="detailGrid">
                <div>
                  <h3 className="sectionTitle">Active stage</h3>
                  <p className="ukde-muted">
                    {activeReview.reviewStage} · {activeReview.status}
                  </p>
                  <p className="ukde-muted">
                    Assigned reviewer: {activeReview.assignedReviewerUserId ?? "Unassigned"}
                  </p>
                  <p className="ukde-muted">
                    Stage ETag <code>{activeReview.reviewEtag}</code>
                  </p>
                  {activeReviewAssignedToOther ? (
                    <p className="ukde-muted">
                      This stage is currently assigned to another reviewer. Claim/start/decision writes will conflict.
                    </p>
                  ) : null}
                </div>
                <div>
                  <h3 className="sectionTitle">SLA signals</h3>
                  <p className="ukde-muted">Aging bucket: {selectedQueueItem?.agingBucket ?? "N/A"}</p>
                  <p className="ukde-muted">SLA due: {formatTime(selectedRequest.slaDueAt)}</p>
                  <p className="ukde-muted">
                    Last queue activity: {formatTime(selectedRequest.lastQueueActivityAt)}
                  </p>
                  <p className="ukde-muted">
                    First review started: {formatTime(selectedRequest.firstReviewStartedAt)}
                  </p>
                </div>
              </div>

              <div className="buttonRow" role="toolbar" aria-label="Export review controls">
                <form action={claimAction}>
                  <input name="projectId" type="hidden" value={projectId} />
                  <input name="exportRequestId" type="hidden" value={selectedRequest.id} />
                  <input name="reviewId" type="hidden" value={activeReview.id} />
                  <input name="reviewEtag" type="hidden" value={activeReview.reviewEtag} />
                  <input name="redirectTo" type="hidden" value={selectedRequestHref} />
                  <button className="projectSecondaryButton" disabled={!canMutate} type="submit">
                    Claim
                  </button>
                </form>
                <form action={releaseAction}>
                  <input name="projectId" type="hidden" value={projectId} />
                  <input name="exportRequestId" type="hidden" value={selectedRequest.id} />
                  <input name="reviewId" type="hidden" value={activeReview.id} />
                  <input name="reviewEtag" type="hidden" value={activeReview.reviewEtag} />
                  <input name="redirectTo" type="hidden" value={selectedRequestHref} />
                  <button className="projectSecondaryButton" disabled={!canMutate} type="submit">
                    Release
                  </button>
                </form>
                <form action={startAction}>
                  <input name="projectId" type="hidden" value={projectId} />
                  <input name="exportRequestId" type="hidden" value={selectedRequest.id} />
                  <input name="reviewId" type="hidden" value={activeReview.id} />
                  <input name="reviewEtag" type="hidden" value={activeReview.reviewEtag} />
                  <input name="redirectTo" type="hidden" value={selectedRequestHref} />
                  <button className="projectPrimaryButton" disabled={!canMutate} type="submit">
                    Start review
                  </button>
                </form>
              </div>

              <form action={decisionAction} className="ukde-form-stack">
                <input name="projectId" type="hidden" value={projectId} />
                <input name="exportRequestId" type="hidden" value={selectedRequest.id} />
                <input name="reviewId" type="hidden" value={activeReview.id} />
                <input name="reviewEtag" type="hidden" value={activeReview.reviewEtag} />
                <input name="redirectTo" type="hidden" value={selectedRequestHref} />
                <label className="ukde-form-label" htmlFor="decisionReason">
                  Decision reason (required for reject)
                </label>
                <textarea className="ukde-input" id="decisionReason" name="decisionReason" rows={3} />
                <label className="ukde-form-label" htmlFor="returnComment">
                  Return comment (required for return)
                </label>
                <textarea className="ukde-input" id="returnComment" name="returnComment" rows={3} />
                <div className="buttonRow">
                  <button className="projectPrimaryButton" disabled={!canMutate} name="decision" type="submit" value="APPROVE">
                    Approve
                  </button>
                  <button className="projectDangerButton" disabled={!canMutate} name="decision" type="submit" value="REJECT">
                    Reject
                  </button>
                  <button className="projectSecondaryButton" disabled={!canMutate} name="decision" type="submit" value="RETURN">
                    Return for changes
                  </button>
                </div>
              </form>
            </>
          )}
        </section>
      )}

      {selectedRequest ? (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Release pack and timeline</h2>
          {!releasePackResult || !releasePackResult.ok || !releasePackResult.data ? (
            <SectionState
              kind="error"
              title="Release pack unavailable"
              description={releasePackResult?.detail ?? "Unable to load frozen release pack."}
            />
          ) : (
            <>
              <p className="ukde-muted">
                Frozen release pack hash <code>{releasePackResult.data.releasePackSha256}</code>
              </p>
              <p className="ukde-muted">
                Created at {formatTime(releasePackResult.data.releasePackCreatedAt)}
              </p>
              <p className="ukde-muted">
                Final decision reason: {selectedRequest.finalDecisionReason ?? "None"}
              </p>
              <p className="ukde-muted">
                Final return comment: {selectedRequest.finalReturnComment ?? "None"}
              </p>
            </>
          )}
          {!eventsResult || !eventsResult.ok || !eventsResult.data ? (
            <SectionState
              kind="error"
              title="Request timeline unavailable"
              description={eventsResult?.detail ?? "Unable to load request events."}
            />
          ) : (
            <table className="ukde-data-table">
              <thead>
                <tr>
                  <th>Event</th>
                  <th>From</th>
                  <th>To</th>
                  <th>Actor</th>
                  <th>Reason</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {eventsResult.data.items.map((event) => (
                  <tr key={event.id}>
                    <td>{event.eventType}</td>
                    <td>{event.fromStatus ?? "None"}</td>
                    <td>{event.toStatus}</td>
                    <td>{event.actorUserId ?? "system"}</td>
                    <td>{event.reason ?? "None"}</td>
                    <td>{formatTime(event.createdAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ) : null}

      {selectedRequest ? (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Review stage history</h2>
          {!reviewsResult || !reviewsResult.ok || !reviewsResult.data ? (
            <SectionState
              kind="error"
              title="Current review stages unavailable"
              description={reviewsResult?.detail ?? "Unable to load review stages."}
            />
          ) : (
            <table className="ukde-data-table">
              <thead>
                <tr>
                  <th>Stage</th>
                  <th>Status</th>
                  <th>Assigned</th>
                  <th>Acted by</th>
                  <th>Decision reason</th>
                  <th>Return comment</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {reviewsResult.data.items.map((review) => (
                  <tr key={review.id}>
                    <td>{review.reviewStage}</td>
                    <td>{review.status}</td>
                    <td>{review.assignedReviewerUserId ?? "Unassigned"}</td>
                    <td>{review.actedByUserId ?? "Pending"}</td>
                    <td>{review.decisionReason ?? "None"}</td>
                    <td>{review.returnComment ?? "None"}</td>
                    <td>{formatTime(review.updatedAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!reviewEventsResult || !reviewEventsResult.ok || !reviewEventsResult.data ? (
            <SectionState
              kind="error"
              title="Review event history unavailable"
              description={reviewEventsResult?.detail ?? "Unable to load review events."}
            />
          ) : (
            <table className="ukde-data-table">
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Stage</th>
                  <th>Actor</th>
                  <th>Decision reason</th>
                  <th>Return comment</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {reviewEventsResult.data.items.map((event) => (
                  <tr key={event.id}>
                    <td>{event.eventType}</td>
                    <td>{event.reviewStage}</td>
                    <td>{event.actorUserId ?? "system"}</td>
                    <td>{event.decisionReason ?? "None"}</td>
                    <td>{event.returnComment ?? "None"}</td>
                    <td>{formatTime(event.createdAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Export history</h2>
        {!historyResult.ok || !historyResult.data ? (
          <SectionState
            kind="error"
            title="Project history unavailable"
            description={historyResult.detail ?? "Unable to load project export history."}
          />
        ) : (
          <table className="ukde-data-table">
            <thead>
              <tr>
                <th>Request</th>
                <th>Status</th>
                <th>Requester</th>
                <th>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {historyResult.data.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <Link className="secondaryButton" href={toQueueHref(projectId, filters, item.id)}>
                      {item.id}
                    </Link>
                  </td>
                  <td>{item.status}</td>
                  <td>{item.submittedBy}</td>
                  <td>{formatTime(item.submittedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {selectedRequest && requesterHistoryResult ? (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Requester history</h2>
          {!requesterHistoryResult.ok || !requesterHistoryResult.data ? (
            <SectionState
              kind="error"
              title="Requester history unavailable"
              description={requesterHistoryResult.detail ?? "Unable to load requester-specific history."}
            />
          ) : (
            <table className="ukde-data-table">
              <thead>
                <tr>
                  <th>Request</th>
                  <th>Status</th>
                  <th>Revision</th>
                  <th>Submitted</th>
                </tr>
              </thead>
              <tbody>
                {requesterHistoryResult.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link className="secondaryButton" href={toQueueHref(projectId, filters, item.id)}>
                        {item.id}
                      </Link>
                    </td>
                    <td>{item.status}</td>
                    <td>{item.requestRevision}</td>
                    <td>{formatTime(item.submittedAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ) : null}

      {requestResult && !requestResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Selected request unavailable"
            description={requestResult.detail ?? "Unable to load request detail projection."}
          />
        </section>
      ) : null}
    </main>
  );
}
