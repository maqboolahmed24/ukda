import Link from "next/link";

import { accessTierLabels, projectRoleLabels } from "@ukde/ui";
import { InlineAlert, SectionState } from "@ukde/ui/primitives";

import { PageHeader } from "../../../components/page-header";
import { listMyProjects } from "../../../lib/projects";
import { normalizeOptionalTextParam } from "../../../lib/url-state";

interface ProjectsNotice {
  description: string;
  title: string;
  tone: "danger" | "warning";
}

function resolveProjectsNotice(error?: string): ProjectsNotice | null {
  switch (error) {
    case "create-invalid":
      return {
        tone: "warning",
        title: "Project details are incomplete",
        description:
          "Provide a project name, a clear purpose, and an intended access tier."
      };
    case "create-failed":
      return {
        tone: "danger",
        title: "Project creation did not complete",
        description:
          "No project was created. Check required fields and try again."
      };
    case "member-route":
    case "project-access":
      return {
        tone: "warning",
        title: "Project access unavailable",
        description:
          "That project is not available for the current session. Choose a project from this list."
      };
    case "settings-route":
      return {
        tone: "warning",
        title: "Project settings unavailable",
        description:
          "The requested settings route could not be opened for this session."
      };
    default:
      return null;
  }
}

export const dynamic = "force-dynamic";

export default async function ProjectsPage({
  searchParams
}: Readonly<{
  searchParams: Promise<{ error?: string }>;
}>) {
  const [projects, query] = await Promise.all([listMyProjects(), searchParams]);
  const notice = resolveProjectsNotice(normalizeOptionalTextParam(query.error));

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Projects"
        meta={<span className="ukde-badge">{projects.length} memberships</span>}
        summary="Purpose-bound project workspaces with role and access-tier boundaries."
        title="Projects workspace"
      />
      {notice ? (
        <InlineAlert title={notice.title} tone={notice.tone}>
          {notice.description}
        </InlineAlert>
      ) : null}

      <section className="projectsIndexGrid">
        <article
          className="projectsPanel ukde-panel"
          aria-labelledby="my-projects-title"
        >
          <div className="projectsPanelHeader">
            <p className="ukde-eyebrow">Memberships</p>
            <h2 id="my-projects-title">My project workspaces</h2>
          </div>

          {projects.length === 0 ? (
            <SectionState
              className="emptyProjectState"
              kind="zero"
              title="No project memberships yet"
              description="Create the first project to start the workspace lifecycle."
            />
          ) : (
            <ul className="projectList">
              {projects.map((project) => (
                <li key={project.id}>
                  <Link
                    className="projectCard"
                    href={`/projects/${project.id}/overview`}
                  >
                    <div>
                      <h3>{project.name}</h3>
                      <p className="ukde-muted">{project.purpose}</p>
                    </div>
                    <div className="projectCardMeta">
                      <span className="ukde-badge">
                        {accessTierLabels[project.intendedAccessTier]}
                      </span>
                      {project.currentUserRole ? (
                        <span className="ukde-badge">
                          {projectRoleLabels[project.currentUserRole]}
                        </span>
                      ) : null}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article
          className="projectsPanel ukde-panel"
          aria-labelledby="create-project-title"
        >
          <div className="projectsPanelHeader">
            <p className="ukde-eyebrow">Create project</p>
            <h2 id="create-project-title">Purpose-bound project workspace</h2>
            <p className="ukde-muted">
              Every project requires a clear purpose and intended access tier.
              New projects inherit the seeded baseline privacy policy snapshot.
            </p>
          </div>

          <form action="/projects/create" className="projectForm" method="post">
            <label htmlFor="project-name">Project name</label>
            <input
              className="projectInput"
              id="project-name"
              maxLength={180}
              minLength={2}
              name="name"
              placeholder="Victorian Parish Records"
              required
            />

            <label htmlFor="project-purpose">Purpose</label>
            <textarea
              className="projectTextarea"
              id="project-purpose"
              maxLength={3000}
              minLength={12}
              name="purpose"
              placeholder="Describe the research purpose and why this dataset is being processed."
              required
              rows={4}
            />

            <label htmlFor="project-tier">Intended access tier</label>
            <select
              className="projectSelect"
              defaultValue="CONTROLLED"
              id="project-tier"
              name="intended_access_tier"
            >
              <option value="CONTROLLED">Controlled</option>
              <option value="SAFEGUARDED">Safeguarded</option>
              <option value="OPEN">Open</option>
            </select>

            <button className="projectPrimaryButton" type="submit">
              Create project
            </button>
          </form>
        </article>
      </section>
    </main>
  );
}
