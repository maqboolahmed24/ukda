import Link from "next/link";
import { redirect } from "next/navigation";

import { SectionState } from "@ukde/ui/primitives";

import { getProjectActivePolicy } from "../../../../../../lib/policies";
import { getProjectWorkspace } from "../../../../../../lib/projects";
import {
  projectPoliciesPath,
  projectPolicyPath
} from "../../../../../../lib/routes";

export const dynamic = "force-dynamic";

export default async function ProjectActivePolicyPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string }>;
}>) {
  const { projectId } = await params;
  const [workspaceResult, activeResult] = await Promise.all([
    getProjectWorkspace(projectId),
    getProjectActivePolicy(projectId)
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=policies-access");
  }

  if (!activeResult.ok || !activeResult.data) {
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Active policy unavailable"
          description={activeResult.detail ?? "Active policy projection could not be loaded."}
        />
      </main>
    );
  }

  const active = activeResult.data;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Policy projection</p>
        <h2>Active policy</h2>
        <div className="buttonRow">
          <Link className="secondaryButton" href={projectPoliciesPath(projectId)}>
            Back to policy list
          </Link>
        </div>
      </section>

      {active.policy ? (
        <section className="sectionCard ukde-panel">
          <ul className="projectMetaList">
            <li>
              <span>Policy ID</span>
              <strong>
                <Link href={projectPolicyPath(projectId, active.policy.id)}>
                  {active.policy.id}
                </Link>
              </strong>
            </li>
            <li>
              <span>Status</span>
              <strong>{active.policy.status}</strong>
            </li>
            <li>
              <span>Validation</span>
              <strong>{active.policy.validationStatus}</strong>
            </li>
            <li>
              <span>Version</span>
              <strong>{active.policy.version}</strong>
            </li>
            <li>
              <span>Family</span>
              <strong>{active.policy.policyFamilyId}</strong>
            </li>
            <li>
              <span>Activated by</span>
              <strong>{active.policy.activatedBy ?? "-"}</strong>
            </li>
            <li>
              <span>Activated at</span>
              <strong>
                {active.policy.activatedAt
                  ? new Date(active.policy.activatedAt).toISOString()
                  : "-"}
              </strong>
            </li>
          </ul>
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No active policy"
            description="No policy is currently projected as ACTIVE for this project."
          />
        </section>
      )}
    </main>
  );
}
