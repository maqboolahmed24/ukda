import Link from "next/link";
import { redirect } from "next/navigation";
import type { ProjectRole, SessionResponse } from "@ukde/contracts";

import { InlineAlert, SectionState, StatusChip } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../../../lib/auth/session";
import {
  getProjectDerivativeDetail,
  getProjectDerivativePreview
} from "../../../../../../../lib/derivatives";
import { getProjectWorkspace } from "../../../../../../../lib/projects";
import {
  projectDerivativePath,
  projectDerivativesPath,
  projectDerivativeStatusPath,
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

function suppressedFieldCount(payload: Record<string, unknown>): number {
  const fields = payload.fields;
  if (!fields || typeof fields !== "object" || Array.isArray(fields)) {
    return 0;
  }
  return Object.keys(fields).length;
}

export default async function ProjectDerivativePreviewPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; derivativeId: string }>;
  searchParams: Promise<{ status?: string }>;
}>) {
  const { projectId, derivativeId } = await params;
  const query = await searchParams;
  const statusParam =
    typeof query.status === "string" && query.status.trim().length > 0
      ? query.status.trim()
      : undefined;
  const notice = resolveNotice(statusParam);

  const [session, workspaceResult, detailResult, previewResult] = await Promise.all([
    requireCurrentSession(),
    getProjectWorkspace(projectId),
    getProjectDerivativeDetail(projectId, derivativeId),
    getProjectDerivativePreview(projectId, derivativeId)
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=member-route");
  }
  if (!canUseDerivativeWorkspace(session, workspaceResult.data.currentUserRole)) {
    redirect(projectOverviewPath(projectId));
  }

  if (!detailResult.ok || !detailResult.data || !previewResult.ok || !previewResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind={detailResult.status === 404 ? "empty" : "error"}
            title={
              detailResult.status === 404
                ? "Derivative snapshot not found"
                : "Derivative preview unavailable"
            }
            description={detailResult.detail ?? previewResult.detail ?? "Derivative preview query failed."}
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
  const preview = previewResult.data;
  const canFreeze = canFreezeDerivative(session, workspaceResult.data.currentUserRole);
  const freezeDisabled =
    snapshot.status !== "SUCCEEDED" ||
    Boolean(snapshot.supersededByDerivativeSnapshotId);

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Derivative preview</p>
        <h2>{snapshot.id}</h2>
        <p className="ukde-muted">
          Preview rows are scoped to one derivative snapshot and one derivative index generation.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDerivativePath(projectId, snapshot.id)}
          >
            Back to detail
          </Link>
          <Link
            className="secondaryButton"
            href={projectDerivativeStatusPath(projectId, snapshot.id)}
          >
            Open status
          </Link>
        </div>
      </section>

      {notice ? (
        <InlineAlert title={notice.title} tone={notice.tone}>
          {notice.description}
        </InlineAlert>
      ) : null}

      <section className="sectionCard ukde-panel">
        <div className="projectSearchResultsHeader">
          <div>
            <h3>Preview rows</h3>
            <p className="ukde-muted">
              Generation: <strong>{preview.derivativeIndexId}</strong>
            </p>
          </div>
          <StatusChip tone="neutral">
            {preview.previewCount} row{preview.previewCount === 1 ? "" : "s"}
          </StatusChip>
        </div>
        {preview.rows.length === 0 ? (
          <SectionState
            kind="empty"
            title="No preview rows"
            description="This snapshot currently has no persisted derivative preview rows."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Kind</th>
                  <th>Suppressed fields</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td>{row.derivativeKind}</td>
                    <td>{suppressedFieldCount(row.suppressedFieldsJson)}</td>
                    <td>{new Date(row.createdAt).toISOString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {preview.rows.length > 0 ? (
        <section className="sectionCard ukde-panel">
          <h3>Sample payload</h3>
          <div className="auditTableWrap">
            <pre>{JSON.stringify(preview.rows[0].displayPayloadJson, null, 2)}</pre>
          </div>
          <h3>Suppressed fields</h3>
          <div className="auditTableWrap">
            <pre>{JSON.stringify(preview.rows[0].suppressedFieldsJson, null, 2)}</pre>
          </div>
        </section>
      ) : null}

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
