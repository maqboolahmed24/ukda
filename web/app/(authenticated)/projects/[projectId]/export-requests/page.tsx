import Link from "next/link";
import { redirect } from "next/navigation";

import { listExportRequests } from "../../../../../lib/exports";
import { getProjectSummary } from "../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectExportRequestsPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{
    status?: string;
    requesterId?: string;
    candidateKind?: string;
    cursor?: string;
  }>;
}>) {
  const { projectId } = await params;
  const filters = await searchParams;
  const [projectResult, exportResult] = await Promise.all([
    getProjectSummary(projectId),
    listExportRequests(projectId, filters)
  ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Export gateway (Phase 0)</p>
        <h1>Export requests</h1>
        <p className="ukde-muted">
          Request submission and review state are reserved for Phase 8. This
          surface remains read-only and disabled by design.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-candidates`}
          >
            Candidate stub
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-review`}
          >
            Review queue stub
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        {!exportResult.ok || !exportResult.data ? (
          <p className="ukde-muted">
            Export request stub unavailable: {exportResult.detail ?? "unknown"}
          </p>
        ) : (
          <>
            <div className="auditIntegrityRow">
              <span className="ukde-badge">{exportResult.data.status}</span>
              <span className="ukde-badge">{exportResult.data.code}</span>
            </div>
            <p className="ukde-muted">{exportResult.data.detail}</p>
            <p className="ukde-muted">
              Route {exportResult.data.method} {exportResult.data.route}
            </p>
            <div className="buttonRow">
              <button className="projectPrimaryButton" disabled type="button">
                Submit export request
              </button>
              <button className="projectSecondaryButton" disabled type="button">
                Start review
              </button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
