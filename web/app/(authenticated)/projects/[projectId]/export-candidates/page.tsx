import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import { listExportCandidates } from "../../../../../lib/exports";
import { getProjectSummary } from "../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectExportCandidatesPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string }>;
}>) {
  const { projectId } = await params;
  const [projectResult, candidatesResult] = await Promise.all([
    getProjectSummary(projectId),
    listExportCandidates(projectId)
  ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  const items = candidatesResult.ok && candidatesResult.data
    ? candidatesResult.data.items
    : [];

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Export candidates</h1>
        <p className="ukde-muted">
          Immutable candidate snapshots are pinned to governance and policy lineage.
          Start submission from an eligible snapshot.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests`}
          >
            View request history
          </Link>
        </div>
      </section>

      {!candidatesResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Candidate list unavailable"
            description={candidatesResult.detail ?? "Unknown failure"}
          />
        </section>
      ) : items.length === 0 ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No eligible candidates yet"
            description="Candidates appear after approved governance-ready outputs are frozen."
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <table className="ukde-data-table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Kind</th>
                <th>Source phase</th>
                <th>Created</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <code>{item.id}</code>
                  </td>
                  <td>{item.candidateKind}</td>
                  <td>{item.sourcePhase}</td>
                  <td>{new Date(item.createdAt).toLocaleString()}</td>
                  <td>
                    <div className="buttonRow">
                      <Link
                        className="secondaryButton"
                        href={`/projects/${projectId}/export-candidates/${item.id}`}
                      >
                        Details
                      </Link>
                      <Link
                        className="projectPrimaryButton"
                        href={`/projects/${projectId}/export-requests/new?candidateId=${encodeURIComponent(item.id)}`}
                      >
                        New request
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
