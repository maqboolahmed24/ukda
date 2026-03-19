import Link from "next/link";
import { redirect } from "next/navigation";
import type { ProjectRole, SessionResponse } from "@ukde/contracts";

import { SectionState } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../../../lib/auth/session";
import {
  getProjectDerivativeDetail,
  getProjectDerivativeStatus
} from "../../../../../../../lib/derivatives";
import { getProjectWorkspace } from "../../../../../../../lib/projects";
import {
  projectDerivativePath,
  projectDerivativePreviewPath,
  projectDerivativesPath,
  projectOverviewPath
} from "../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function canUseDerivativeWorkspace(
  session: SessionResponse,
  projectRole: ProjectRole | null | undefined
): boolean {
  const platformRoles = new Set(session.user.platformRoles);
  if (platformRoles.has("ADMIN")) {
    return true;
  }
  if (platformRoles.has("AUDITOR")) {
    return false;
  }
  return (
    projectRole === "PROJECT_LEAD" ||
    projectRole === "RESEARCHER" ||
    projectRole === "REVIEWER"
  );
}

export default async function ProjectDerivativeStatusPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; derivativeId: string }>;
}>) {
  const { projectId, derivativeId } = await params;
  const [session, workspaceResult, detailResult, statusResult] = await Promise.all([
    requireCurrentSession(),
    getProjectWorkspace(projectId),
    getProjectDerivativeDetail(projectId, derivativeId),
    getProjectDerivativeStatus(projectId, derivativeId)
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=member-route");
  }
  if (!canUseDerivativeWorkspace(session, workspaceResult.data.currentUserRole)) {
    redirect(projectOverviewPath(projectId));
  }

  if (!detailResult.ok || !detailResult.data || !statusResult.ok || !statusResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind={detailResult.status === 404 ? "empty" : "error"}
            title={
              detailResult.status === 404
                ? "Derivative snapshot not found"
                : "Derivative status unavailable"
            }
            description={detailResult.detail ?? statusResult.detail ?? "Derivative status query failed."}
          />
          <div className="buttonRow">
            <Link className="secondaryButton" href={projectDerivativesPath(projectId)}>
              Back to derivatives
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const snapshot = detailResult.data.derivative;
  const status = statusResult.data;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Derivative status</p>
        <h2>{snapshot.id}</h2>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDerivativePath(projectId, snapshot.id)}
          >
            Back to detail
          </Link>
          <Link
            className="secondaryButton"
            href={projectDerivativePreviewPath(projectId, snapshot.id)}
          >
            Open preview
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Lifecycle</h3>
        <ul className="projectMetaList">
          <li>
            <span>Status</span>
            <strong>{status.status}</strong>
          </li>
          <li>
            <span>Derivative index generation</span>
            <strong>{status.derivativeIndexId}</strong>
          </li>
          <li>
            <span>Candidate snapshot</span>
            <strong>{status.candidateSnapshotId ?? "-"}</strong>
          </li>
          <li>
            <span>Started at</span>
            <strong>{status.startedAt ? new Date(status.startedAt).toISOString() : "-"}</strong>
          </li>
          <li>
            <span>Finished at</span>
            <strong>{status.finishedAt ? new Date(status.finishedAt).toISOString() : "-"}</strong>
          </li>
          <li>
            <span>Failure reason</span>
            <strong>{status.failureReason ?? "-"}</strong>
          </li>
        </ul>
      </section>
    </main>
  );
}
