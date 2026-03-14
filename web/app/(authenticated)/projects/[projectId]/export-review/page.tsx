import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import { listExportReviewQueue } from "../../../../../lib/exports";
import { getProjectSummary } from "../../../../../lib/projects";
import { normalizeOptionalTextParam } from "../../../../../lib/url-state";

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
  const rawFilters = await searchParams;
  const filters = {
    status: normalizeOptionalTextParam(rawFilters.status),
    agingBucket: normalizeOptionalTextParam(rawFilters.agingBucket),
    reviewerUserId: normalizeOptionalTextParam(rawFilters.reviewerUserId)
  };
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
        <SectionState
          kind="disabled"
          eyebrow="Export gateway (Phase 0)"
          title="Export review queue"
          description="Review assignment, decisions, and release-pack delivery remain disabled until Phase 8 activates the single egress workflow."
        />
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
          <SectionState
            kind="error"
            title="Export review stub unavailable"
            description={reviewResult.detail ?? "Unknown failure"}
          />
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
