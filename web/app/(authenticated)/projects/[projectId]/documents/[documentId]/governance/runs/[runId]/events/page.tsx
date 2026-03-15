import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import {
  getProjectDocument,
  getProjectDocumentGovernanceRunLedgerStatus,
  listProjectDocumentGovernanceRunEvents
} from "../../../../../../../../../../lib/documents";
import {
  projectDocumentGovernancePath,
  projectDocumentGovernanceRunEventsPath,
  projectDocumentGovernanceRunLedgerPath,
  projectDocumentGovernanceRunManifestPath,
  projectDocumentGovernanceRunOverviewPath,
  projectsPath
} from "../../../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

export default async function ProjectDocumentGovernanceRunEventsPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string; runId: string }>;
}>) {
  const { projectId, documentId, runId } = await params;
  const [documentResult, eventsResult, ledgerStatusResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    listProjectDocumentGovernanceRunEvents(projectId, documentId, runId),
    getProjectDocumentGovernanceRunLedgerStatus(projectId, documentId, runId)
  ]);

  if (!documentResult.ok || !eventsResult.ok) {
    if (documentResult.status === 404 || eventsResult.status === 404) {
      notFound();
    }
    if (documentResult.status === 403 || eventsResult.status === 403) {
      redirect(projectsPath);
    }
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Governance events unavailable"
          description={
            eventsResult.detail ??
            documentResult.detail ??
            "Governance run events could not be loaded."
          }
        />
      </main>
    );
  }

  const document = documentResult.data;
  const events = eventsResult.data?.items ?? [];
  if (!document) {
    notFound();
  }
  const canViewLedger = Boolean(
    ledgerStatusResult.ok && ledgerStatusResult.data
  );

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Governance events</p>
        <h2>{document.originalFilename}</h2>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentGovernancePath(projectId, document.id, {
              tab: "runs",
              runId
            })}
          >
            Governance tab
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentGovernanceRunOverviewPath(projectId, document.id, runId)}
          >
            Run overview
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentGovernanceRunManifestPath(projectId, document.id, runId)}
          >
            Manifest
          </Link>
          {canViewLedger ? (
            <Link
              className="secondaryButton"
              href={projectDocumentGovernanceRunLedgerPath(projectId, document.id, runId)}
            >
              Evidence ledger
            </Link>
          ) : null}
          <Link
            className="secondaryButton"
            aria-current="page"
            href={projectDocumentGovernanceRunEventsPath(projectId, document.id, runId)}
          >
            Events
          </Link>
        </div>
        {!canViewLedger ? (
          <p className="ukde-muted">
            Controlled evidence-ledger detail is restricted to administrator and
            auditor roles.
          </p>
        ) : null}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Append-only timeline</h3>
        {events.length === 0 ? (
          <SectionState
            kind="loading"
            title="No governance events yet"
            description="Event history appears as manifest, ledger, verification, and readiness transitions are appended."
          />
        ) : (
          <ul className="projectMetaList">
            {events.map((event) => (
              <li key={event.id}>
                <span>{event.eventType}</span>
                <strong>
                  {new Date(event.createdAt).toISOString()}
                  {" · "}
                  {event.screeningSafe ? (
                    <StatusChip tone="success">SCREENING-SAFE</StatusChip>
                  ) : (
                    <StatusChip tone="warning">CONTROLLED</StatusChip>
                  )}
                  {" · "}
                  {event.reason ?? "No reason recorded"}
                </strong>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
