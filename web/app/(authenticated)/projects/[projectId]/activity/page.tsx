import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { requireCurrentSession } from "../../../../../lib/auth/session";
import {
  adminAuditPath,
  projectOverviewPath,
  projectsPath,
  withQuery
} from "../../../../../lib/routes";
import { getProjectSummary } from "../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectActivityPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string }>;
}>) {
  const session = await requireCurrentSession();
  const { projectId } = await params;
  const projectResult = await getProjectSummary(projectId);

  if (!projectResult.ok || !projectResult.data) {
    redirect(withQuery(projectsPath, { error: "member-route" }));
  }

  const hasPlatformAuditAccess =
    session.user.platformRoles.includes("ADMIN") ||
    session.user.platformRoles.includes("AUDITOR");

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Project-scoped governance"
        secondaryActions={[
          { href: projectOverviewPath(projectId), label: "Back to overview" },
          ...(hasPlatformAuditAccess
            ? [{ href: adminAuditPath, label: "Open platform audit" }]
            : [])
        ]}
        summary="Project activity remains scoped to project membership and does not replace platform-level audit routes."
        title="Project activity"
      />

      <section className="sectionCard ukde-panel">
        <ul className="projectMetaList">
          <li>
            <span>Ownership boundary</span>
            <strong>Project membership and project purpose</strong>
          </li>
          <li>
            <span>Platform audit boundary</span>
            <strong>Cross-project compliance and operator traces</strong>
          </li>
          <li>
            <span>Current state</span>
            <strong>Timeline scaffold pending later prompt implementation</strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <SectionState
          className="projectPlaceholder"
          kind="disabled"
          eyebrow="Project activity"
          title="Activity timeline scaffold"
          description="This route remains project-scoped and membership-gated. Append-only timeline details land in later prompts."
        />
      </section>
    </main>
  );
}
