import { redirect } from "next/navigation";

import { getProjectSummary } from "../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectActivityPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string }>;
}>) {
  const { projectId } = await params;
  const projectResult = await getProjectSummary(projectId);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  return (
    <section className="projectPlaceholder ukde-panel">
      <p className="ukde-eyebrow">Project activity</p>
      <h3>Activity timeline scaffold</h3>
      <p className="ukde-muted">
        This route is reserved for project-scoped governance and activity
        events. Membership enforcement is active now; append-only audit timeline
        detail lands in the next prompt sequence.
      </p>
    </section>
  );
}
