import Link from "next/link";
import { redirect } from "next/navigation";

import { SectionState } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../lib/auth/session";
import {
  listApprovedModels,
  listProjectModelAssignments
} from "../../../../../lib/model-assignments";
import { getProjectWorkspace } from "../../../../../lib/projects";
import {
  projectModelAssignmentPath,
  projectModelAssignmentsPath
} from "../../../../../lib/routes";

export const dynamic = "force-dynamic";

interface StatusNotice {
  description: string;
  title: string;
  tone: "success" | "warning" | "danger";
}

function resolveNotice(status?: string): StatusNotice | null {
  switch (status) {
    case "created":
      return {
        title: "Assignment created",
        description: "Draft model assignment row was created.",
        tone: "success"
      };
    case "activated":
      return {
        title: "Assignment activated",
        description: "Selected assignment is now ACTIVE for its role.",
        tone: "success"
      };
    case "retired":
      return {
        title: "Assignment retired",
        description: "Selected assignment was retired successfully.",
        tone: "success"
      };
    case "action-failed":
      return {
        title: "Assignment action failed",
        description: "Validate role compatibility and permissions, then retry.",
        tone: "danger"
      };
    default:
      return null;
  }
}

export default async function ProjectModelAssignmentsPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ status?: string }>;
}>) {
  const { projectId } = await params;
  const [session, workspaceResult, assignmentsResult, approvedModelsResult, query] =
    await Promise.all([
      requireCurrentSession(),
      getProjectWorkspace(projectId),
      listProjectModelAssignments(projectId),
      listApprovedModels({ status: "APPROVED" }),
      searchParams
    ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=model-assignments-access");
  }

  if (!assignmentsResult.ok || !approvedModelsResult.ok) {
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Model assignments unavailable"
          description={
            assignmentsResult.detail ??
            approvedModelsResult.detail ??
            "Model assignment data could not be loaded."
          }
        />
      </main>
    );
  }

  const workspace = workspaceResult.data;
  const assignments = assignmentsResult.data?.items ?? [];
  const approvedModels = approvedModelsResult.data?.items ?? [];
  const role = workspace.currentUserRole;
  const canMutate =
    session.user.platformRoles.includes("ADMIN") || role === "PROJECT_LEAD";
  const notice = resolveNotice(
    typeof query.status === "string" ? query.status.trim() : undefined
  );

  const byRole = new Map<string, string>();
  for (const assignment of assignments) {
    if (assignment.status === "ACTIVE" && !byRole.has(assignment.modelRole)) {
      byRole.set(assignment.modelRole, assignment.id);
    }
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Transcription model governance</p>
        <h2>Project model assignments</h2>
        <p className="ukde-muted">
          Assign APPROVED catalog models to stable role keys without changing
          workflow routes.
        </p>
      </section>

      {notice ? (
        <section className="sectionCard ukde-panel">
          <p className="ukde-muted">
            {notice.title}: {notice.description}
          </p>
        </section>
      ) : null}

      {canMutate ? (
        <section className="sectionCard ukde-panel">
          <h3>Create assignment</h3>
          <form
            action={`/projects/${projectId}/model-assignments/create`}
            className="jobsCreateForm"
            method="post"
          >
            <label>
              Role
              <select defaultValue="TRANSCRIPTION_PRIMARY" name="model_role">
                <option value="TRANSCRIPTION_PRIMARY">TRANSCRIPTION_PRIMARY</option>
                <option value="TRANSCRIPTION_FALLBACK">TRANSCRIPTION_FALLBACK</option>
                <option value="ASSIST">ASSIST</option>
              </select>
            </label>
            <label>
              Approved model
              <select name="approved_model_id" required>
                {approvedModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.modelRole} :: {model.modelFamily} {model.modelVersion}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Reason
              <input
                defaultValue="Initial role-map assignment"
                name="assignment_reason"
                required
                type="text"
              />
            </label>
            <button className="projectPrimaryButton" type="submit">
              Create assignment
            </button>
          </form>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        {assignments.length === 0 ? (
          <SectionState
            kind="empty"
            title="No project model assignments"
            description="Create a DRAFT assignment and activate it when ready."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Role</th>
                  <th>Approved model</th>
                  <th>Status</th>
                  <th>Reason</th>
                  <th>Created</th>
                  <th>Lifecycle</th>
                </tr>
              </thead>
              <tbody>
                {assignments.map((assignment) => {
                  const isActiveForRole = byRole.get(assignment.modelRole) === assignment.id;
                  return (
                    <tr key={assignment.id}>
                      <td>
                        <Link href={projectModelAssignmentPath(projectId, assignment.id)}>
                          {assignment.id}
                        </Link>
                      </td>
                      <td>{assignment.modelRole}</td>
                      <td>{assignment.approvedModelId}</td>
                      <td>{assignment.status}</td>
                      <td>{assignment.assignmentReason}</td>
                      <td>{new Date(assignment.createdAt).toISOString()}</td>
                      <td>
                        {canMutate ? (
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
                        ) : isActiveForRole ? (
                          "Active"
                        ) : (
                          "-"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
