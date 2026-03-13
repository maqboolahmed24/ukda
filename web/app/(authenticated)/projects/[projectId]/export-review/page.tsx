import Link from "next/link";
import { redirect } from "next/navigation";

import { listExportReviewQueue } from "../../../../../lib/exports";
import { getProjectSummary } from "../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectExportReviewPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{
    status?: string;
    agingBucket?: string;
    reviewerUserId?: string;
  }>;
}>) {
  const { projectId } = await params;
  const filters = await searchParams;
  const [projectResult, reviewResult] = await Promise.all([
    getProjectSummary(projectId),
    listExportReviewQueue(projectId, filters)
  ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Export gateway (Phase 0)</p>
        <h1>Export review queue</h1>
        <p className="ukde-muted">
          Review assignment, decisions, and release-pack delivery remain
          disabled until Phase 8 activates the single egress workflow.
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
            href={`/projects/${projectId}/export-requests`}
          >
            Request stub
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        {!reviewResult.ok || !reviewResult.data ? (
          <p className="ukde-muted">
            Export review stub unavailable: {reviewResult.detail ?? "unknown"}
          </p>
        ) : (
          <>
            <div className="auditIntegrityRow">
              <span className="ukde-badge">{reviewResult.data.status}</span>
              <span className="ukde-badge">{reviewResult.data.code}</span>
            </div>
            <p className="ukde-muted">{reviewResult.data.detail}</p>
            <p className="ukde-muted">
              Route {reviewResult.data.method} {reviewResult.data.route}
            </p>
            <div className="buttonRow">
              <button className="projectPrimaryButton" disabled type="button">
                Approve
              </button>
              <button className="projectDangerButton" disabled type="button">
                Reject
              </button>
              <button className="projectSecondaryButton" disabled type="button">
                Return for changes
              </button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
