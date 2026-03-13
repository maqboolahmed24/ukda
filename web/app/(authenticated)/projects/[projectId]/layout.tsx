import { redirect } from "next/navigation";

import { ProjectSectionHeader } from "../../../../components/project-section-header";
import { requireCurrentSession } from "../../../../lib/auth/session";
import { getProjectWorkspace } from "../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectWorkspaceLayout({
  children,
  params
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ projectId: string }>;
}>) {
  const { projectId } = await params;
  await requireCurrentSession();
  const workspaceResult = await getProjectWorkspace(projectId);

  if (!workspaceResult.ok || !workspaceResult.data) {
    if (workspaceResult.status === 401) {
      redirect("/login");
    }
    redirect("/projects?error=project-access");
  }

  const workspace = workspaceResult.data;

  return (
    <section className="projectWorkspaceMain">
      <ProjectSectionHeader projectName={workspace.name} />
      <div className="projectContentHost">{children}</div>
    </section>
  );
}
