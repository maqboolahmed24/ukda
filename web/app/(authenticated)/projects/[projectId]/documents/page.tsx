import { redirect } from "next/navigation";

import { getProjectSummary } from "../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectDocumentsPage({
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
      <p className="ukde-eyebrow">Documents</p>
      <h3>Document-library route scaffold</h3>
      <p className="ukde-muted">
        The navigation and membership contract for project documents is active.
        Full ingest and library workflows are owned by Phase 1 prompts.
      </p>
    </section>
  );
}
