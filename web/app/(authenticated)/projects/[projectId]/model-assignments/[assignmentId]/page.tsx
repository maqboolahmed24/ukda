import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { SectionState } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../../lib/auth/session";
import {
  getProjectModelAssignment,
  listApprovedModels
} from "../../../../../../lib/model-assignments";
import { getProjectWorkspace } from "../../../../../../lib/projects";
import {
  projectModelAssignmentDatasetsPath,
  projectModelAssignmentsPath
} from "../../../../../../lib/routes";

export const dynamic = "force-dynamic";

export default async function ProjectModelAssignmentDetailPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; assignmentId: string }>;
}>) {
  const { projectId, assignmentId } = await params;
  const [session, workspaceResult, assignmentResult, approvedModelsResult] =
    await Promise.all([
      requireCurrentSession(),
      getProjectWorkspace(projectId),
      getProjectModelAssignment(projectId, assignmentId),
      listApprovedModels()
    ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=model-assignment-access");
  }
  if (assignmentResult.status === 404) {
    notFound();
  }
  if (!assignmentResult.ok || !assignmentResult.data) {
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Model assignment unavailable"
          description={assignmentResult.detail ?? "Model assignment read failed."}
        />
      </main>
    );
  }

  const assignment = assignmentResult.data;
  const approvedModel =
    approvedModelsResult.ok && approvedModelsResult.data
      ? approvedModelsResult.data.items.find(
          (candidate) => candidate.id === assignment.approvedModelId
        )
      : null;
  const role = workspaceResult.data.currentUserRole;
  const canMutate =
    session.user.platformRoles.includes("ADMIN") || role === "PROJECT_LEAD";

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Project assignment detail</p>
        <h2>{assignment.id}</h2>
        <p className="ukde-muted">
          Stable model role binding with auditable activation and retirement
          lifecycle fields.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectModelAssignmentsPath(projectId)}
          >
            Back to assignments
          </Link>
          <Link
            className="secondaryButton"
            href={projectModelAssignmentDatasetsPath(projectId, assignment.id)}
          >
            View datasets
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <ul className="projectMetaList">
          <li>
            <span>Role</span>
            <strong>{assignment.modelRole}</strong>
          </li>
          <li>
            <span>Status</span>
            <strong>{assignment.status}</strong>
          </li>
          <li>
            <span>Approved model</span>
            <strong>{assignment.approvedModelId}</strong>
          </li>
          <li>
            <span>Created by</span>
            <strong>{assignment.createdBy}</strong>
          </li>
          <li>
            <span>Created at</span>
            <strong>{new Date(assignment.createdAt).toISOString()}</strong>
          </li>
          <li>
            <span>Activated by</span>
            <strong>{assignment.activatedBy ?? "-"}</strong>
          </li>
          <li>
            <span>Activated at</span>
            <strong>
              {assignment.activatedAt
                ? new Date(assignment.activatedAt).toISOString()
                : "-"}
            </strong>
          </li>
          <li>
            <span>Retired by</span>
            <strong>{assignment.retiredBy ?? "-"}</strong>
          </li>
          <li>
            <span>Retired at</span>
            <strong>
              {assignment.retiredAt
                ? new Date(assignment.retiredAt).toISOString()
                : "-"}
            </strong>
          </li>
          <li>
            <span>Reason</span>
            <strong>{assignment.assignmentReason}</strong>
          </li>
          <li>
            <span>Resolved family</span>
            <strong>{approvedModel?.modelFamily ?? "-"}</strong>
          </li>
          <li>
            <span>Resolved version</span>
            <strong>{approvedModel?.modelVersion ?? "-"}</strong>
          </li>
        </ul>
      </section>

      {canMutate ? (
        <section className="sectionCard ukde-panel">
          <h3>Lifecycle actions</h3>
          <div className="jobsActionRow">
            <form
              action={`${projectModelAssignmentsPath(projectId)}/${assignment.id}/activate`}
              method="post"
            >
              <button
                className="projectSecondaryButton"
                disabled={assignment.status === "ACTIVE"}
                type="submit"
              >
                Activate
              </button>
            </form>
            <form
              action={`${projectModelAssignmentsPath(projectId)}/${assignment.id}/retire`}
              method="post"
            >
              <button
                className="projectDangerButton"
                disabled={assignment.status === "RETIRED"}
                type="submit"
              >
                Retire
              </button>
            </form>
          </div>
        </section>
      ) : null}
    </main>
  );
}
