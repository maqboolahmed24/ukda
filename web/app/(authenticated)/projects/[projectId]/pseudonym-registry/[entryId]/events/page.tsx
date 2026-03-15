import Link from "next/link";
import { redirect } from "next/navigation";

import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { getProjectWorkspace } from "../../../../../../../lib/projects";
import {
  getProjectPseudonymRegistryEntry,
  listProjectPseudonymRegistryEntryEvents
} from "../../../../../../../lib/pseudonym-registry";
import {
  projectPseudonymRegistryEntryPath,
  projectPseudonymRegistryPath
} from "../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function resolveEventTone(
  eventType: "ENTRY_CREATED" | "ENTRY_REUSED" | "ENTRY_RETIRED"
): "danger" | "neutral" | "success" | "warning" {
  if (eventType === "ENTRY_CREATED") {
    return "success";
  }
  if (eventType === "ENTRY_RETIRED") {
    return "neutral";
  }
  return "warning";
}

export default async function ProjectPseudonymRegistryEntryEventsPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; entryId: string }>;
}>) {
  const { projectId, entryId } = await params;

  const [workspaceResult, entryResult, eventsResult] = await Promise.all([
    getProjectWorkspace(projectId),
    getProjectPseudonymRegistryEntry(projectId, entryId),
    listProjectPseudonymRegistryEntryEvents(projectId, entryId)
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=pseudonym-registry-access");
  }

  if (!entryResult.ok || !entryResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Registry entry unavailable"
            description={entryResult.detail ?? "Pseudonym registry entry could not be loaded."}
          />
          <div className="buttonRow">
            <Link className="secondaryButton" href={projectPseudonymRegistryPath(projectId)}>
              Back to registry
            </Link>
          </div>
        </section>
      </main>
    );
  }

  if (!eventsResult.ok || !eventsResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Registry events unavailable"
            description={
              eventsResult.detail ?? "Pseudonym registry events could not be loaded."
            }
          />
          <div className="buttonRow">
            <Link
              className="secondaryButton"
              href={projectPseudonymRegistryEntryPath(projectId, entryId)}
            >
              Back to entry
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const entry = entryResult.data;
  const events = eventsResult.data.items;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Pseudonym registry events</p>
        <h2>{entry.id}</h2>
        <p className="ukde-muted">
          Append-only entry timeline for deterministic alias lineage and run reuse.
        </p>
        <div className="buttonRow">
          <Link className="secondaryButton" href={projectPseudonymRegistryPath(projectId)}>
            Back to registry
          </Link>
          <Link
            className="secondaryButton"
            href={projectPseudonymRegistryEntryPath(projectId, entryId)}
          >
            Back to entry
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Timeline</h3>
        {events.length === 0 ? (
          <SectionState
            kind="empty"
            title="No registry events"
            description="Events are appended when entries are created, reused, or retired."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Run</th>
                  <th>Actor</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td>
                      <StatusChip tone={resolveEventTone(event.eventType)}>
                        {event.eventType}
                      </StatusChip>
                    </td>
                    <td>{event.runId}</td>
                    <td>{event.actorUserId ?? "system"}</td>
                    <td>{event.createdAt}</td>
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
