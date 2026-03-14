import { redirect } from "next/navigation";

import { accessTierLabels, projectRoleLabels } from "@ukde/ui";
import { InlineAlert } from "@ukde/ui/primitives";

import { getProjectMembers } from "../../../../../lib/projects";
import { normalizeOptionalTextParam } from "../../../../../lib/url-state";

export const dynamic = "force-dynamic";

interface SettingsNotice {
  description: string;
  title: string;
  tone: "success" | "danger";
}

function resolveNotice(status?: string): SettingsNotice | null {
  switch (status) {
    case "member-added":
      return {
        tone: "success",
        title: "Member added",
        description: "Membership was added and audit events were recorded."
      };
    case "member-updated":
      return {
        tone: "success",
        title: "Role updated",
        description: "Member role was updated for this project."
      };
    case "member-removed":
      return {
        tone: "success",
        title: "Member removed",
        description: "Membership was removed from this project."
      };
    case "action-failed":
      return {
        tone: "danger",
        title: "Member action failed",
        description: "Check permissions and try the action again."
      };
    default:
      return null;
  }
}

export default async function ProjectSettingsPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ status?: string }>;
}>) {
  const { projectId } = await params;
  const query = await searchParams;
  const membersResult = await getProjectMembers(projectId);

  if (!membersResult.ok || !membersResult.data) {
    if (membersResult.status === 403) {
      redirect(`/projects/${projectId}/overview?error=settings-access`);
    }
    redirect("/projects?error=settings-route");
  }

  const response = membersResult.data;
  const notice = resolveNotice(normalizeOptionalTextParam(query.status));
  const leadCount = response.items.filter(
    (member) => member.role === "PROJECT_LEAD"
  ).length;

  return (
    <section className="settingsGrid">
      <article className="settingsCard ukde-panel">
        <p className="ukde-eyebrow">Project settings</p>
        <h3>{response.project.name}</h3>
        <p className="ukde-muted">{response.project.purpose}</p>
        <ul className="projectMetaList">
          <li>
            <span>Intended access tier</span>
            <strong>
              {accessTierLabels[response.project.intendedAccessTier]}
            </strong>
          </li>
          <li>
            <span>Baseline policy snapshot</span>
            <strong>{response.project.baselinePolicySnapshotId}</strong>
          </li>
          <li>
            <span>Current status</span>
            <strong>{response.project.status}</strong>
          </li>
        </ul>
      </article>

      <article className="settingsCard ukde-panel">
        <div className="settingsHeader">
          <div>
            <p className="ukde-eyebrow">Membership management</p>
            <h3>Project members</h3>
          </div>
        </div>
        {notice ? (
          <InlineAlert title={notice.title} tone={notice.tone}>
            {notice.description}
          </InlineAlert>
        ) : null}

        <ul className="memberList">
          {response.items.map((member) => {
            const cannotRemoveLead =
              member.role === "PROJECT_LEAD" && leadCount <= 1;
            return (
              <li className="memberRow" key={member.userId}>
                <div className="memberIdentity">
                  <strong>{member.displayName}</strong>
                  <span className="ukde-muted">{member.email}</span>
                </div>

                <div className="memberActions">
                  <span className="ukde-badge">
                    {projectRoleLabels[member.role]}
                  </span>
                  <form
                    action={`/projects/${projectId}/settings/change-role`}
                    method="post"
                  >
                    <input
                      name="member_user_id"
                      type="hidden"
                      value={member.userId}
                    />
                    <select
                      className="projectSelect"
                      defaultValue={member.role}
                      name="role"
                    >
                      <option value="PROJECT_LEAD">Project lead</option>
                      <option value="RESEARCHER">Researcher</option>
                      <option value="REVIEWER">Reviewer</option>
                    </select>
                    <button className="projectSecondaryButton" type="submit">
                      Update role
                    </button>
                  </form>
                  <form
                    action={`/projects/${projectId}/settings/remove-member`}
                    method="post"
                  >
                    <input
                      name="member_user_id"
                      type="hidden"
                      value={member.userId}
                    />
                    <button
                      className="projectDangerButton"
                      disabled={cannotRemoveLead}
                      type="submit"
                    >
                      Remove
                    </button>
                  </form>
                </div>
              </li>
            );
          })}
        </ul>

        <form
          action={`/projects/${projectId}/settings/add-member`}
          className="addMemberForm"
          method="post"
        >
          <label htmlFor="member-email">Add member by email</label>
          <input
            className="projectInput"
            id="member-email"
            name="member_email"
            placeholder="reviewer@local.ukde"
            required
            type="email"
          />
          <label htmlFor="member-role">Role</label>
          <select
            className="projectSelect"
            defaultValue="RESEARCHER"
            id="member-role"
            name="role"
          >
            <option value="PROJECT_LEAD">Project lead</option>
            <option value="RESEARCHER">Researcher</option>
            <option value="REVIEWER">Reviewer</option>
          </select>
          <button className="projectPrimaryButton" type="submit">
            Add member
          </button>
        </form>
      </article>
    </section>
  );
}
