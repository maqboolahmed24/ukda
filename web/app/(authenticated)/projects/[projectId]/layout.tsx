import { redirect } from "next/navigation";

import { ProjectSectionHeader } from "../../../../components/project-section-header";
import { ProjectSideNav } from "../../../../components/project-side-nav";
import { WorkspaceHeader } from "../../../../components/workspace-header";
import {
  readCsrfToken,
  requireCurrentSession
} from "../../../../lib/auth/session";
import { getProjectWorkspace, listMyProjects } from "../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectWorkspaceLayout({
  children,
  params
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ projectId: string }>;
}>) {
  const { projectId } = await params;
  const session = await requireCurrentSession();
  const csrfToken = await readCsrfToken();
  const [projects, workspaceResult] = await Promise.all([
    listMyProjects(),
    getProjectWorkspace(projectId)
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    if (workspaceResult.status === 401) {
      redirect("/login");
    }
    redirect("/projects?error=project-access");
  }

  const workspace = workspaceResult.data;

  return (
    <main className="workspaceRoot">
      <WorkspaceHeader
        currentProject={workspace}
        csrfToken={csrfToken}
        projects={projects}
        session={session}
      />

      <section className="projectWorkspaceFrame">
        <ProjectSideNav
          canAccessMemberWorkspace={workspace.isMember}
          canAccessSettings={workspace.canAccessSettings}
          projectId={projectId}
        />

        <div className="projectWorkspaceMain">
          <ProjectSectionHeader projectName={workspace.name} />
          <div className="projectContentHost">{children}</div>
        </div>
      </section>
    </main>
  );
}
