import Link from "next/link";
import { redirect } from "next/navigation";

import { InlineAlert, SectionState } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../lib/auth/session";
import { listProjectJobs } from "../../../../../lib/jobs";
import { getProjectSummary } from "../../../../../lib/projects";
import {
  projectJobPath,
  projectJobsPath,
  withQuery
} from "../../../../../lib/routes";
import {
  normalizeCursorParam,
  normalizeOptionalTextParam
} from "../../../../../lib/url-state";

interface JobNotice {
  description: string;
  title: string;
  tone: "success" | "warning" | "danger";
}

function resolveJobsNotice(status?: string | null): JobNotice | null {
  switch (status) {
    case "run-invalid":
      return {
        tone: "warning",
        title: "Job input is invalid",
        description: "Review logical key, mode, and attempt limits."
      };
    case "run-failed":
      return {
        tone: "danger",
        title: "Job was not queued",
        description: "The queue request failed before job creation completed."
      };
    case "retry-invalid":
    case "cancel-invalid":
      return {
        tone: "warning",
        title: "Job action is invalid",
        description: "Select a valid job before retrying or canceling."
      };
    case "job-unavailable":
      return {
        tone: "warning",
        title: "Job not available",
        description:
          "The requested job could not be loaded. Select another job from the list."
      };
    default:
      return null;
  }
}

export const dynamic = "force-dynamic";

export default async function ProjectJobsPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ cursor?: string; status?: string }>;
}>) {
  const { projectId } = await params;
  const filters = await searchParams;
  const [session, projectResult] = await Promise.all([
    requireCurrentSession(),
    getProjectSummary(projectId)
  ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  const cursor = normalizeCursorParam(filters.cursor);
  const jobsResult = await listProjectJobs(projectId, {
    cursor,
    pageSize: 50
  });
  const jobs = jobsResult.ok && jobsResult.data ? jobsResult.data.items : [];
  const nextCursor =
    jobsResult.ok && jobsResult.data ? jobsResult.data.nextCursor : null;

  const role = projectResult.data.currentUserRole;
  const isAdmin = session.user.platformRoles.includes("ADMIN");
  const canMutateJobs =
    isAdmin || role === "PROJECT_LEAD" || role === "REVIEWER";
  const statusNotice = resolveJobsNotice(
    normalizeOptionalTextParam(filters.status)
  );
  const defaultLogicalKey = `noop-${Date.now()}`;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Project jobs</p>
        <h2>Job runs</h2>
        <p className="ukde-muted">
          Queue state, retry lineage, and worker-executed NOOP validation runs.
        </p>
      </section>

      {statusNotice ? (
        <InlineAlert title={statusNotice.title} tone={statusNotice.tone}>
          {statusNotice.description}
        </InlineAlert>
      ) : null}

      {canMutateJobs ? (
        <section className="sectionCard ukde-panel">
          <h2>Run test job</h2>
          <form
            action={`/projects/${projectId}/jobs/run-noop`}
            className="jobsCreateForm"
            method="post"
          >
            <label>
              Logical key
              <input
                defaultValue={defaultLogicalKey}
                name="logical_key"
                required
                type="text"
              />
            </label>
            <label>
              Mode
              <select defaultValue="SUCCESS" name="mode">
                <option value="SUCCESS">SUCCESS</option>
                <option value="FAIL_ONCE">FAIL_ONCE</option>
                <option value="FAIL_ALWAYS">FAIL_ALWAYS</option>
              </select>
            </label>
            <label>
              Max attempts
              <input
                defaultValue="1"
                max="10"
                min="1"
                name="max_attempts"
                type="number"
              />
            </label>
            <button className="projectPrimaryButton" type="submit">
              Enqueue NOOP
            </button>
          </form>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        {!jobsResult.ok ? (
          <SectionState
            kind="error"
            title="Jobs list unavailable"
            description={jobsResult.detail ?? "Unknown failure"}
          />
        ) : jobs.length === 0 ? (
          <SectionState
            kind="empty"
            title="No jobs found"
            description="No jobs have been recorded for this project yet."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Attempt</th>
                  <th>Created</th>
                  <th>Started</th>
                  <th>Finished</th>
                  <th>Error</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <Link href={projectJobPath(projectId, job.id)}>
                        {job.id}
                      </Link>
                    </td>
                    <td>{job.type}</td>
                    <td>{job.status}</td>
                    <td>
                      {job.attemptNumber} ({job.attempts}/{job.maxAttempts})
                    </td>
                    <td>{new Date(job.createdAt).toISOString()}</td>
                    <td>
                      {job.startedAt
                        ? new Date(job.startedAt).toISOString()
                        : "-"}
                    </td>
                    <td>
                      {job.finishedAt
                        ? new Date(job.finishedAt).toISOString()
                        : "-"}
                    </td>
                    <td>{job.errorCode ?? "-"}</td>
                    <td>
                      {canMutateJobs ? (
                        <div className="jobsActionRow">
                          <form
                            action={`/projects/${projectId}/jobs/retry`}
                            method="post"
                          >
                            <input name="job_id" type="hidden" value={job.id} />
                            <button
                              className="projectSecondaryButton"
                              disabled={
                                !(
                                  job.status === "FAILED" ||
                                  job.status === "CANCELED"
                                )
                              }
                              type="submit"
                            >
                              Retry
                            </button>
                          </form>
                          <form
                            action={`/projects/${projectId}/jobs/cancel`}
                            method="post"
                          >
                            <input name="job_id" type="hidden" value={job.id} />
                            <button
                              className="projectDangerButton"
                              disabled={
                                !(
                                  job.status === "QUEUED" ||
                                  job.status === "RUNNING"
                                )
                              }
                              type="submit"
                            >
                              Cancel
                            </button>
                          </form>
                        </div>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {typeof nextCursor === "number" ? (
          <div className="buttonRow">
            <Link
              className="secondaryButton"
              href={withQuery(projectJobsPath(projectId), {
                cursor: nextCursor
              })}
            >
              Next page
            </Link>
          </div>
        ) : null}
      </section>
    </main>
  );
}
