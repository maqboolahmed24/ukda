import { redirect } from "next/navigation";

import { accessTierLabels, projectRoleLabels } from "@ukde/ui";

import { getProjectJobsSummary } from "../../../../../lib/jobs";
import { getProjectSummary } from "../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectOverviewPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string }>;
}>) {
  const { projectId } = await params;
  const [projectResult, jobsSummaryResult] = await Promise.all([
    getProjectSummary(projectId),
    getProjectJobsSummary(projectId)
  ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  const project = projectResult.data;
  const runningJobs =
    jobsSummaryResult.ok && jobsSummaryResult.data
      ? jobsSummaryResult.data.runningJobs
      : 0;
  const lastJobStatus =
    jobsSummaryResult.ok && jobsSummaryResult.data
      ? jobsSummaryResult.data.lastJobStatus
      : null;

  return (
    <section className="projectSectionGrid">
      <article className="projectDetailCard ukde-panel">
        <p className="ukde-eyebrow">Project purpose</p>
        <h3>{project.name}</h3>
        <p className="ukde-muted">{project.purpose}</p>
      </article>

      <article className="projectDetailCard ukde-panel">
        <p className="ukde-eyebrow">Access and governance</p>
        <ul className="projectMetaList">
          <li>
            <span>Intended tier</span>
            <strong>{accessTierLabels[project.intendedAccessTier]}</strong>
          </li>
          <li>
            <span>Project role</span>
            <strong>
              {project.currentUserRole
                ? projectRoleLabels[project.currentUserRole]
                : "No direct membership"}
            </strong>
          </li>
          <li>
            <span>Status</span>
            <strong>{project.status}</strong>
          </li>
          <li>
            <span>Jobs running</span>
            <strong>{runningJobs}</strong>
          </li>
          <li>
            <span>Last job status</span>
            <strong>{lastJobStatus ?? "No jobs yet"}</strong>
          </li>
        </ul>
      </article>
    </section>
  );
}
