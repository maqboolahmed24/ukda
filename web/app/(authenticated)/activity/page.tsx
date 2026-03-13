import Link from "next/link";

import { listMyActivity } from "../../../lib/audit";

export const dynamic = "force-dynamic";

export default async function MyActivityPage() {
  const activityResult = await listMyActivity(60);
  const items =
    activityResult.ok && activityResult.data ? activityResult.data.items : [];

  return (
    <main className="homeLayout">
      <section
        className="sectionCard ukde-panel"
        aria-labelledby="my-activity-title"
      >
        <p className="ukde-eyebrow">Current user surface</p>
        <h1 id="my-activity-title">My activity</h1>
        <p className="ukde-muted">
          This route shows your own recent auditable actions and remains
          separate from project-scoped activity.
        </p>
        <div className="buttonRow">
          <Link className="secondaryButton" href="/projects">
            Back to projects
          </Link>
          <Link className="secondaryButton" href="/admin/audit">
            Open admin audit
          </Link>
        </div>
      </section>

      <section
        className="sectionCard ukde-panel"
        aria-labelledby="my-activity-events-title"
      >
        <h2 id="my-activity-events-title">Recent events</h2>
        {!activityResult.ok ? (
          <p className="ukde-muted">
            Activity read failed: {activityResult.detail ?? "unknown"}
          </p>
        ) : items.length === 0 ? (
          <p className="ukde-muted">No recent events for this user.</p>
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Event</th>
                  <th>Project</th>
                  <th>Request ID</th>
                </tr>
              </thead>
              <tbody>
                {items.map((event) => (
                  <tr key={event.id}>
                    <td>{new Date(event.timestamp).toISOString()}</td>
                    <td>{event.eventType}</td>
                    <td>{event.projectId ?? "-"}</td>
                    <td>{event.requestId}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
