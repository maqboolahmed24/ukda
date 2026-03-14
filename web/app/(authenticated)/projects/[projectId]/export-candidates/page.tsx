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
  const [projectResult, exportResult] = await Promise.all([
    getProjectSummary(projectId),
    listExportCandidates(projectId)
  ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <SectionState
          kind="disabled"
          eyebrow="Export gateway (Phase 0)"
          title="Export candidates"
          description="Candidate listing is intentionally disabled until the Phase 8 screening workflow is implemented."
        />
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests`}
          >
            View export requests
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
          <SectionState
            kind="error"
            title="Export stub unavailable"
            description={exportResult.detail ?? "Unknown failure"}
          />
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
                Create candidate
              </button>
              <button className="projectSecondaryButton" disabled type="button">
                Download preview
              </button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
