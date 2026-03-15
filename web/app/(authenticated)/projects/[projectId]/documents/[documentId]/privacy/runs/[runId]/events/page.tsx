import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import {
  getProjectDocument,
  getProjectDocumentRedactionRun,
  listProjectDocumentRedactionRunEvents
} from "../../../../../../../../../../lib/documents";
import {
  projectDocumentPrivacyRunPath,
  projectDocumentPrivacyWorkspacePath,
  projectsPath
} from "../../../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

export default async function ProjectDocumentPrivacyRunEventsPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string; runId: string }>;
}>) {
  const { projectId, documentId, runId } = await params;

  const [documentResult, runResult, eventsResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectDocumentRedactionRun(projectId, documentId, runId),
    listProjectDocumentRedactionRunEvents(projectId, documentId, runId)
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
          title="Privacy events unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for privacy events."
          }
        />
      </main>
    );
  }

  if (!runResult.ok || !runResult.data) {
    if (runResult.status === 404) {
      notFound();
    }
    if (runResult.status === 403) {
      redirect(projectsPath);
    }
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="degraded"
          title="Run detail unavailable"
          description={runResult.detail ?? "Redaction run could not be loaded."}
        />
      </main>
    );
  }

  const document = documentResult.data;
  if (!document) {
    notFound();
  }
  const run = runResult.data;
  const eventItems = eventsResult.ok && eventsResult.data ? eventsResult.data.items : [];

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Privacy run events</p>
        <h2>{document.originalFilename}</h2>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentPrivacyRunPath(projectId, documentId, run.id)}
          >
            Back to run detail
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentPrivacyWorkspacePath(projectId, documentId, {
              page: 1,
              runId: run.id
            })}
          >
            Open workspace
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Append-only timeline</h3>
        {!eventsResult.ok ? (
          <SectionState
            kind="degraded"
            title="Run timeline unavailable"
            description={eventsResult.detail ?? "Run events could not be loaded."}
          />
        ) : eventItems.length === 0 ? (
          <SectionState
            kind="empty"
            title="No events yet"
            description="Timeline entries appear when decisions or review actions are recorded."
          />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Event</th>
                <th>Source table</th>
                <th>Page</th>
                <th>Finding</th>
                <th>Actor</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {eventItems.map((event) => (
                <tr key={`${event.sourceTable}:${event.eventId}`}>
                  <td>{new Date(event.createdAt).toISOString()}</td>
                  <td>{event.eventType}</td>
                  <td>{event.sourceTable}</td>
                  <td>{event.pageId ?? "-"}</td>
                  <td>{event.findingId ?? "-"}</td>
                  <td>{event.actorUserId}</td>
                  <td>{event.reason ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
