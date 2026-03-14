import Link from "next/link";
import { redirect } from "next/navigation";
import { InlineAlert, SectionState } from "@ukde/ui/primitives";

import { JobStatusPoller } from "../../../../../../components/job-status-poller";
import { requireCurrentSession } from "../../../../../../lib/auth/session";
import {
  getProjectJob,
  getProjectJobStatus,
  listProjectJobEvents
} from "../../../../../../lib/jobs";
import { getProjectSummary } from "../../../../../../lib/projects";
import {
  projectJobPath,
  projectJobsPath,
  withQuery
} from "../../../../../../lib/routes";
import { normalizeOptionalTextParam } from "../../../../../../lib/url-state";

export const dynamic = "force-dynamic";

interface JobDetailNotice {
  description: string;
  title: string;
  tone: "success" | "warning" | "danger";
}

function resolveJobDetailNotice(
  status?: string | null
): JobDetailNotice | null {
  switch (status) {
    case "run-queued":
      return {
        tone: "success",
        title: "Job queued",
        description: "The test job is queued and status updates are now live."
      };
    case "retry-created":
      return {
        tone: "success",
        title: "Retry queued",
        description: "A new retry attempt was created for this job."
      };
    case "retry-existing":
      return {
        tone: "warning",
        title: "Retry already in progress",
        description: "An active retry already exists for this logical job."
      };
    case "retry-failed":
      return {
        tone: "danger",
        title: "Retry did not start",
        description: "The retry request failed."
      };
    case "cancel-requested":
      return {
        tone: "warning",
        title: "Cancellation requested",
        description:
          "Cancellation was requested and is waiting for worker acknowledgement."
      };
    case "canceled":
      return {
        tone: "success",
        title: "Job canceled",
        description: "The job is now in a terminal canceled state."
      };
    case "cancel-failed":
      return {
        tone: "danger",
        title: "Cancellation did not complete",
        description: "The cancel request failed."
      };
    default:
      return null;
  }
}

export default async function ProjectJobDetailPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; jobId: string }>;
  searchParams: Promise<{ status?: string }>;
}>) {
  const [{ projectId, jobId }, query] = await Promise.all([params, searchParams]);
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
    redirect(
      withQuery(projectJobsPath(projectId), { status: "job-unavailable" })
    );
  }

  const project = projectResult.data;
  const job = jobResult.data;
  const statusPayload = statusResult.data;
  const events =
    eventsResult.ok && eventsResult.data ? eventsResult.data.items : [];
  const eventsError =
    !eventsResult.ok && eventsResult.detail
      ? eventsResult.detail
      : !eventsResult.ok
        ? "Unknown failure"
        : null;
  const isAdmin = session.user.platformRoles.includes("ADMIN");
  const role = project.currentUserRole;
  const canMutateJobs =
    isAdmin || role === "PROJECT_LEAD" || role === "REVIEWER";
  const notice = resolveJobDetailNotice(
    normalizeOptionalTextParam(query.status)
  );

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Project jobs</p>
        <h2>Job detail</h2>
        <p className="ukde-muted">{job.id}</p>
        <div className="buttonRow">
          <Link className="secondaryButton" href={projectJobsPath(projectId)}>
            Back to jobs
          </Link>
        </div>
      </section>

      {notice ? (
        <InlineAlert title={notice.title} tone={notice.tone}>
          {notice.description}
        </InlineAlert>
      ) : null}

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
                <Link href={projectJobPath(projectId, job.supersedesJobId)}>
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
                <Link href={projectJobPath(projectId, job.supersededByJobId)}>
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
          <InlineAlert title="Safe failure summary" tone="danger">
            {job.errorCode}
            {job.errorMessage ? `: ${job.errorMessage}` : ""}
          </InlineAlert>
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
        {eventsError ? (
          <SectionState
            kind="error"
            title="Job events unavailable"
            description={eventsError}
          />
        ) : events.length === 0 ? (
          <SectionState
            kind="empty"
            title="No events recorded yet"
            description="Append-only events will appear as the job progresses."
          />
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
