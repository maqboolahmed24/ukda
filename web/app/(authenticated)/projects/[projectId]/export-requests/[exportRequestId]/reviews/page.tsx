import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import {
  getExportRequest,
  getExportRequestReviewEvents,
  getExportRequestReviews
} from "../../../../../../../lib/exports";
import { getProjectSummary } from "../../../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectExportRequestReviewsPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; exportRequestId: string }>;
}>) {
  const { projectId, exportRequestId } = await params;
  const [projectResult, requestResult, reviewsResult, reviewEventsResult] =
    await Promise.all([
      getProjectSummary(projectId),
      getExportRequest(projectId, exportRequestId),
      getExportRequestReviews(projectId, exportRequestId),
      getExportRequestReviewEvents(projectId, exportRequestId)
    ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  if (!requestResult.ok || !requestResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Request unavailable"
            description={requestResult.detail ?? "Unknown request failure."}
          />
          <div className="buttonRow">
            <Link className="secondaryButton" href={`/projects/${projectId}/export-requests`}>
              Back to history
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const request = requestResult.data;
  const reviews = reviewsResult.ok && reviewsResult.data ? reviewsResult.data.items : [];
  const reviewEvents =
    reviewEventsResult.ok && reviewEventsResult.data
      ? reviewEventsResult.data.items
      : [];
  const isTerminalLocked = ["APPROVED", "EXPORTED", "REJECTED", "RETURNED"].includes(
    request.status
  );

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Review read surface</h1>
        <p className="ukde-muted">
          Requester-visible review stages and append-only review events for{" "}
          <code>{request.id}</code>.
        </p>
        <p className="ukde-muted">
          Review path: {request.reviewPath} · Requires second review:{" "}
          {request.requiresSecondReview ? "Yes" : "No"}
        </p>
        <p className="ukde-muted">
          Lock state: {isTerminalLocked ? "Locked terminal revision" : "Mutable active revision"}
        </p>
        <p className="ukde-muted">
          Final decision reason: {request.finalDecisionReason ?? "None"}
        </p>
        <p className="ukde-muted">
          Final return comment: {request.finalReturnComment ?? "None"}
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${exportRequestId}`}
          >
            Back to request detail
          </Link>
        </div>
      </section>

      {!reviewsResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Reviews unavailable"
            description={reviewsResult.detail ?? "Unable to load review stages."}
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Current review stages</h2>
          {reviews.length === 0 ? (
            <SectionState
              kind="empty"
              title="No review stages available"
              description="Review stages are created on request submission."
            />
          ) : (
            <table className="ukde-data-table">
              <thead>
                <tr>
                  <th>Stage</th>
                  <th>Required</th>
                  <th>Status</th>
                  <th>Assigned reviewer</th>
                  <th>Decision reason</th>
                  <th>Return comment</th>
                  <th>Review ETag</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map((review) => (
                  <tr key={review.id}>
                    <td>{review.reviewStage}</td>
                    <td>{review.isRequired ? "Yes" : "No"}</td>
                    <td>{review.status}</td>
                    <td>{review.assignedReviewerUserId ?? "Unassigned"}</td>
                    <td>{review.decisionReason ?? "None"}</td>
                    <td>{review.returnComment ?? "None"}</td>
                    <td>
                      <code>{review.reviewEtag}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {!reviewEventsResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Review events unavailable"
            description={reviewEventsResult.detail ?? "Unable to load review events."}
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Review event history</h2>
          {reviewEvents.length === 0 ? (
            <SectionState
              kind="empty"
              title="No review events recorded"
              description="Review event history appears once review stages are created."
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
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {reviewEvents.map((event) => (
                  <tr key={event.id}>
                    <td>{event.eventType}</td>
                    <td>{event.reviewStage}</td>
                    <td>{event.actorUserId ?? "system"}</td>
                    <td>{event.decisionReason ?? "None"}</td>
                    <td>{event.returnComment ?? "None"}</td>
                    <td>{new Date(event.createdAt).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </main>
  );
}
