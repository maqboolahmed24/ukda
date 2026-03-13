import Link from "next/link";
import { redirect } from "next/navigation";

import { JobStatusPoller } from "../../../../../../components/job-status-poller";
import { requireCurrentSession } from "../../../../../../lib/auth/session";
import {
  getProjectJob,
  getProjectJobStatus,
  listProjectJobEvents
} from "../../../../../../lib/jobs";
import { getProjectSummary } from "../../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectJobDetailPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; jobId: string }>;
}>) {
  const { projectId, jobId } = await params;
  const [session, projectResult, jobResult, statusResult, eventsResult] =
    await Promise.all([
      requireCurrentSession(),
      getProjectSummary(projectId),
      getProjectJob(projectId, jobId),
      getProjectJobStatus(projectId, jobId),
      listProjectJobEvents(projectId, jobId, { cursor: 0, pageSize: 200 })
    ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }
  if (
    !jobResult.ok ||
    !jobResult.data ||
    !statusResult.ok ||
    !statusResult.data
  ) {
    redirect(`/projects/${projectId}/jobs?status=job-unavailable`);
  }

  const project = projectResult.data;
  const job = jobResult.data;
  const statusPayload = statusResult.data;
  const events =
    eventsResult.ok && eventsResult.data ? eventsResult.data.items : [];
  const isAdmin = session.user.platformRoles.includes("ADMIN");
  const role = project.currentUserRole;
  const canMutateJobs =
    isAdmin || role === "PROJECT_LEAD" || role === "REVIEWER";

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Project jobs</p>
        <h1>Job detail</h1>
        <p className="ukde-muted">{job.id}</p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/jobs`}
          >
            Back to jobs
          </Link>
        </div>
      </section>

      <div className="projectSectionGrid">
        <section className="projectDetailCard ukde-panel">
          <p className="ukde-eyebrow">Run metadata</p>
          <h3>{job.type}</h3>
          <ul className="projectMetaList">
            <li>
              <span>Status</span>
              <strong>{job.status}</strong>
            </li>
            <li>
              <span>Attempt number</span>
              <strong>{job.attemptNumber}</strong>
            </li>
            <li>
              <span>Delivery attempts</span>
              <strong>
                {job.attempts}/{job.maxAttempts}
              </strong>
            </li>
            <li>
              <span>Created by</span>
              <strong>{job.createdBy}</strong>
            </li>
            <li>
              <span>Created</span>
              <strong>{new Date(job.createdAt).toISOString()}</strong>
            </li>
            <li>
              <span>Started</span>
              <strong>
                {job.startedAt ? new Date(job.startedAt).toISOString() : "-"}
              </strong>
            </li>
            <li>
              <span>Finished</span>
              <strong>
                {job.finishedAt ? new Date(job.finishedAt).toISOString() : "-"}
              </strong>
            </li>
          </ul>
        </section>

        <JobStatusPoller
          initialStatus={statusPayload}
          statusUrl={`/projects/${projectId}/jobs/${jobId}/status`}
        />
      </div>

      <section className="sectionCard ukde-panel">
        <h2>Retry lineage</h2>
        <ul className="projectMetaList">
          <li>
            <span>Supersedes</span>
            <strong>
              {job.supersedesJobId ? (
                <Link
                  href={`/projects/${projectId}/jobs/${job.supersedesJobId}`}
                >
                  {job.supersedesJobId}
                </Link>
              ) : (
                "none"
              )}
            </strong>
          </li>
          <li>
            <span>Superseded by</span>
            <strong>
              {job.supersededByJobId ? (
                <Link
                  href={`/projects/${projectId}/jobs/${job.supersededByJobId}`}
                >
                  {job.supersededByJobId}
                </Link>
              ) : (
                "none"
              )}
            </strong>
          </li>
          <li>
            <span>Dedupe key</span>
            <strong>{job.dedupeKey.slice(0, 16)}…</strong>
          </li>
        </ul>
        {job.errorCode ? (
          <p className="ukde-muted">
            Error: {job.errorCode}
            {job.errorMessage ? ` (${job.errorMessage})` : ""}
          </p>
        ) : null}
      </section>

      {canMutateJobs ? (
        <section className="sectionCard ukde-panel">
          <h2>Actions</h2>
          <div className="jobsActionRow">
            <form action={`/projects/${projectId}/jobs/retry`} method="post">
              <input name="job_id" type="hidden" value={job.id} />
              <button
                className="projectSecondaryButton"
                disabled={
                  !(job.status === "FAILED" || job.status === "CANCELED")
                }
                type="submit"
              >
                Retry job
              </button>
            </form>
            <form action={`/projects/${projectId}/jobs/cancel`} method="post">
              <input name="job_id" type="hidden" value={job.id} />
              <button
                className="projectDangerButton"
                disabled={
                  !(job.status === "QUEUED" || job.status === "RUNNING")
                }
                type="submit"
              >
                Cancel job
              </button>
            </form>
          </div>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h2>Append-only events</h2>
        {events.length === 0 ? (
          <p className="ukde-muted">No events have been recorded yet.</p>
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Event</th>
                  <th>From</th>
                  <th>To</th>
                  <th>Actor</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td>{event.id}</td>
                    <td>{event.eventType}</td>
                    <td>{event.fromStatus ?? "-"}</td>
                    <td>{event.toStatus}</td>
                    <td>{event.actorUserId ?? "-"}</td>
                    <td>{new Date(event.createdAt).toISOString()}</td>
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
