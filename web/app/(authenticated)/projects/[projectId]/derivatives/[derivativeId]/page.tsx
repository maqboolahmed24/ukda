import Link from "next/link";
import { redirect } from "next/navigation";
import type { ProjectRole, SessionResponse } from "@ukde/contracts";

import { InlineAlert, SectionState } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../../lib/auth/session";
import {
  getProjectDerivativeDetail,
  getProjectDerivativeStatus
} from "../../../../../../lib/derivatives";
import { getProjectWorkspace } from "../../../../../../lib/projects";
import {
  projectDerivativePreviewPath,
  projectDerivativesPath,
  projectDerivativeStatusPath,
  projectOverviewPath
} from "../../../../../../lib/routes";

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

function canFreezeDerivative(
  session: SessionResponse,
  projectRole: ProjectRole | null | undefined
): boolean {
  if (session.user.platformRoles.includes("ADMIN")) {
    return true;
  }
  return projectRole === "PROJECT_LEAD" || projectRole === "REVIEWER";
}

function resolveNotice(status: string | undefined): {
  title: string;
  description: string;
  tone: "success" | "warning" | "danger";
} | null {
  switch (status) {
    case "frozen":
      return {
        title: "Candidate snapshot created",
        description:
          "This derivative snapshot is now frozen as an immutable Phase 8 candidate.",
        tone: "success"
      };
    case "freeze-existing":
      return {
        title: "Existing candidate reused",
        description:
          "This derivative snapshot was already frozen; the existing candidate linkage was returned.",
        tone: "warning"
      };
    case "freeze-failed":
      return {
        title: "Candidate freeze failed",
        description:
          "Freeze was rejected by lifecycle, suppression, anti-join, or permission gates.",
        tone: "danger"
      };
    default:
      return null;
  }
}

function backHref(projectId: string, scope: string | undefined): string {
  if (scope?.trim().toLowerCase() === "historical") {
    return `${projectDerivativesPath(projectId)}?scope=historical`;
  }
  return projectDerivativesPath(projectId);
}

export default async function ProjectDerivativeDetailPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; derivativeId: string }>;
  searchParams: Promise<{ scope?: string; status?: string }>;
}>) {
  const { projectId, derivativeId } = await params;
  const query = await searchParams;
  const scope =
    typeof query.scope === "string" && query.scope.trim().length > 0
      ? query.scope.trim()
      : undefined;
  const status =
    typeof query.status === "string" && query.status.trim().length > 0
      ? query.status.trim()
      : undefined;
  const notice = resolveNotice(status);

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
                : "Derivative detail unavailable"
            }
            description={detailResult.detail ?? statusResult.detail ?? "Derivative query failed."}
          />
          <div className="buttonRow">
            <Link className="secondaryButton" href={backHref(projectId, scope)}>
              Back to derivatives
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const snapshot = detailResult.data.derivative;
  const canFreeze = canFreezeDerivative(session, workspaceResult.data.currentUserRole);
  const freezeDisabled =
    snapshot.status !== "SUCCEEDED" ||
    Boolean(snapshot.supersededByDerivativeSnapshotId);

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Derivative snapshot</p>
        <h2>{snapshot.id}</h2>
        <p className="ukde-muted">
          Safeguarded internal derivative snapshot pinned to one derivative-index generation.
        </p>
        <div className="buttonRow">
          <Link className="secondaryButton" href={backHref(projectId, scope)}>
            Back to derivatives
          </Link>
          <Link
            className="secondaryButton"
            href={projectDerivativeStatusPath(projectId, snapshot.id)}
          >
            Open status
          </Link>
          <Link
            className="secondaryButton"
            href={projectDerivativePreviewPath(projectId, snapshot.id)}
          >
            Open preview
          </Link>
        </div>
      </section>

      {notice ? (
        <InlineAlert title={notice.title} tone={notice.tone}>
          {notice.description}
        </InlineAlert>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h3>Snapshot metadata</h3>
        <ul className="projectMetaList">
          <li>
            <span>Derivative kind</span>
            <strong>{snapshot.derivativeKind}</strong>
          </li>
          <li>
            <span>Derivative index generation</span>
            <strong>{snapshot.derivativeIndexId}</strong>
          </li>
          <li>
            <span>Status</span>
            <strong>{statusResult.data.status}</strong>
          </li>
          <li>
            <span>Policy version reference</span>
            <strong>{snapshot.policyVersionRef}</strong>
          </li>
          <li>
            <span>Snapshot SHA256</span>
            <strong>{snapshot.snapshotSha256 ?? "-"}</strong>
          </li>
          <li>
            <span>Storage key</span>
            <strong>{snapshot.storageKey ?? "-"}</strong>
          </li>
          <li>
            <span>Candidate snapshot</span>
            <strong>{snapshot.candidateSnapshotId ?? "-"}</strong>
          </li>
          <li>
            <span>Superseded by</span>
            <strong>{snapshot.supersededByDerivativeSnapshotId ?? "-"}</strong>
          </li>
          <li>
            <span>Created at</span>
            <strong>{new Date(snapshot.createdAt).toISOString()}</strong>
          </li>
          <li>
            <span>Finished at</span>
            <strong>
              {snapshot.finishedAt ? new Date(snapshot.finishedAt).toISOString() : "-"}
            </strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Source snapshot JSON</h3>
        <div className="auditTableWrap">
          <pre>{JSON.stringify(snapshot.sourceSnapshotJson, null, 2)}</pre>
        </div>
      </section>

      {canFreeze ? (
        <section className="sectionCard ukde-panel">
          <h3>Candidate freeze</h3>
          <p className="ukde-muted">
            Freeze creates or reuses an immutable Phase 8 candidate snapshot for this
            unsuperseded successful derivative snapshot.
          </p>
          <form
            action={`/projects/${projectId}/derivatives/${snapshot.id}/candidate-snapshots`}
            method="post"
          >
            <button
              className="projectPrimaryButton"
              disabled={freezeDisabled}
              type="submit"
            >
              Freeze candidate snapshot
            </button>
          </form>
        </section>
      ) : null}
    </main>
  );
}
