import { redirect } from "next/navigation";

import { accessTierLabels, projectRoleLabels } from "@ukde/ui";
import { InlineAlert, SectionState } from "@ukde/ui/primitives";

import { getProjectJobsSummary } from "../../../../../lib/jobs";
import { getProjectSummary } from "../../../../../lib/projects";
import { normalizeOptionalTextParam } from "../../../../../lib/url-state";

interface OverviewNotice {
  description: string;
  title: string;
  tone: "success" | "warning";
}

function resolveOverviewNotice(
  created?: string,
  error?: string
): OverviewNotice | null {
  if (created === "1") {
    return {
      tone: "success",
      title: "Project created",
      description:
        "The project is available and membership boundaries are now active."
    };
  }
  if (error === "settings-access") {
    return {
      tone: "warning",
      title: "Settings access required",
      description:
        "Project settings are restricted to project leads and platform admins."
    };
  }
  return null;
}

export const dynamic = "force-dynamic";

export default async function ProjectOverviewPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ created?: string; error?: string }>;
}>) {
  const [{ projectId }, query] = await Promise.all([params, searchParams]);
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
  const jobsSummaryUnavailable = !jobsSummaryResult.ok || !jobsSummaryResult.data;
  const lastJobStatus =
    jobsSummaryResult.ok && jobsSummaryResult.data
      ? jobsSummaryResult.data.lastJobStatus
      : null;
  const notice = resolveOverviewNotice(
    normalizeOptionalTextParam(query.created),
    normalizeOptionalTextParam(query.error)
  );

  return (
    <>
      {notice ? (
        <InlineAlert title={notice.title} tone={notice.tone}>
          {notice.description}
        </InlineAlert>
      ) : null}
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
              <strong>
                {jobsSummaryUnavailable
                  ? "Unavailable"
                  : lastJobStatus ?? "No jobs yet"}
              </strong>
            </li>
          </ul>
          {jobsSummaryUnavailable ? (
            <SectionState
              kind="degraded"
              title="Job summary unavailable"
              description={
                jobsSummaryResult.detail ??
                "Run-level summary data could not be retrieved."
              }
            />
          ) : null}
        </article>
      </section>
    </>
  );
}
