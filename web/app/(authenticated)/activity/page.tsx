import { PageHeader } from "../../../components/page-header";
import { listMyActivity } from "../../../lib/audit";
import { SectionState } from "@ukde/ui/primitives";

export const dynamic = "force-dynamic";

export default async function MyActivityPage() {
  const activityResult = await listMyActivity(60);
  const items =
    activityResult.ok && activityResult.data ? activityResult.data.items : [];

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Current user surface"
        secondaryActions={[
          { href: "/projects", label: "Back to projects" },
          { href: "/admin/audit", label: "Open admin audit" }
        ]}
        summary="Your own recent auditable actions, separate from project-scoped activity."
        title="My activity"
      />

      <section
        className="sectionCard ukde-panel"
        aria-labelledby="my-activity-events-title"
      >
        <h2 id="my-activity-events-title">Recent events</h2>
        {!activityResult.ok ? (
          <SectionState
            kind="error"
            title="Activity read failed"
            description={activityResult.detail ?? "Unknown failure"}
          />
        ) : items.length === 0 ? (
          <SectionState
            kind="empty"
            title="No recent events"
            description="No auditable events were recorded for this user in the selected window."
          />
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
