import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import { getExportRequest, getExportRequestEvents } from "../../../../../../../lib/exports";
import { getProjectSummary } from "../../../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectExportRequestEventsPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; exportRequestId: string }>;
}>) {
  const { projectId, exportRequestId } = await params;
  const [projectResult, requestResult, eventsResult] = await Promise.all([
    getProjectSummary(projectId),
    getExportRequest(projectId, exportRequestId),
    getExportRequestEvents(projectId, exportRequestId)
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

  const events = eventsResult.ok && eventsResult.data ? eventsResult.data.items : [];

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Request events</h1>
        <p className="ukde-muted">
          Append-only event history for request <code>{requestResult.data.id}</code>.
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

      {!eventsResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Event history unavailable"
            description={eventsResult.detail ?? "Unknown event history failure."}
          />
        </section>
      ) : events.length === 0 ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No events recorded"
            description="This request has not emitted request-level events yet."
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <table className="ukde-data-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>From</th>
                <th>To</th>
                <th>Actor</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td>{event.eventType}</td>
                  <td>{event.fromStatus ?? "None"}</td>
                  <td>{event.toStatus}</td>
                  <td>{event.actorUserId ?? "system"}</td>
                  <td>{new Date(event.createdAt).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
