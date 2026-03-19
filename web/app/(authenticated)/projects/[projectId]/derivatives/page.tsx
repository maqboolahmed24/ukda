import Link from "next/link";
import { redirect } from "next/navigation";
import type {
  ProjectRole,
  ProjectDerivativeSnapshot,
  SessionResponse
} from "@ukde/contracts";

import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../lib/auth/session";
import { getProjectDerivatives } from "../../../../../lib/derivatives";
import { getProjectWorkspace } from "../../../../../lib/projects";
import {
  projectDerivativePath,
  projectDerivativesPath,
  projectIndexesPath,
  projectOverviewPath
} from "../../../../../lib/routes";

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

function normalizeScope(value: string | undefined): "active" | "historical" {
  if (value?.trim().toLowerCase() === "historical") {
    return "historical";
  }
  return "active";
}

function scopeHref(projectId: string, scope: "active" | "historical"): string {
  return scope === "historical"
    ? `${projectDerivativesPath(projectId)}?scope=historical`
    : projectDerivativesPath(projectId);
}

function detailHref(
  projectId: string,
  derivative: ProjectDerivativeSnapshot,
  scope: "active" | "historical"
): string {
  if (scope === "historical") {
    return `${projectDerivativePath(projectId, derivative.id)}?scope=historical`;
  }
  return projectDerivativePath(projectId, derivative.id);
}

export default async function ProjectDerivativesPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ scope?: string }>;
}>) {
  const { projectId } = await params;
  const query = await searchParams;
  const scope = normalizeScope(query.scope);

  const [session, workspaceResult, derivativesResult] = await Promise.all([
    requireCurrentSession(),
    getProjectWorkspace(projectId),
    getProjectDerivatives(projectId, { scope })
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=member-route");
  }
  if (!canUseDerivativeWorkspace(session, workspaceResult.data.currentUserRole)) {
    redirect(projectOverviewPath(projectId));
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Safeguarded derivatives</p>
        <h2>Derivative snapshots</h2>
        <p className="ukde-muted">
          Internal safeguarded previews only. Any release path still requires Phase
          8 export approval from a frozen candidate snapshot.
        </p>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Scope</h3>
        <div className="buttonRow">
          <Link
            className="projectSecondaryButton"
            href={scopeHref(projectId, "active")}
          >
            Active generation
          </Link>
          <Link
            className="projectSecondaryButton"
            href={scopeHref(projectId, "historical")}
          >
            Historical unsuperseded
          </Link>
        </div>
      </section>

      {!derivativesResult.ok || !derivativesResult.data ? (
        derivativesResult.status === 409 && scope === "active" ? (
          <section className="sectionCard ukde-panel">
            <SectionState
              kind="empty"
              title="No active derivative index"
              description="Activate a SUCCEEDED derivative index generation before opening active derivative snapshots."
            />
            <div className="buttonRow">
              <Link className="secondaryButton" href={projectIndexesPath(projectId)}>
                Open indexes
              </Link>
              <Link
                className="secondaryButton"
                href={scopeHref(projectId, "historical")}
              >
                View historical snapshots
              </Link>
            </div>
          </section>
        ) : (
          <section className="sectionCard ukde-panel">
            <SectionState
              kind="error"
              title="Derivative list unavailable"
              description={derivativesResult.detail ?? "Derivative list query failed."}
            />
          </section>
        )
      ) : derivativesResult.data.items.length === 0 ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No derivative snapshots"
            description="No derivative snapshots were returned for this scope."
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <div className="projectSearchResultsHeader">
            <div>
              <h3>Snapshots</h3>
              <p className="ukde-muted">
                Scope: <strong>{derivativesResult.data.scope}</strong>
                {" · "}
                Active derivative index:{" "}
                <strong>{derivativesResult.data.activeDerivativeIndexId ?? "-"}</strong>
              </p>
            </div>
            <StatusChip tone="neutral">
              {derivativesResult.data.items.length} item
              {derivativesResult.data.items.length === 1 ? "" : "s"}
            </StatusChip>
          </div>
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Snapshot</th>
                  <th>Kind</th>
                  <th>Status</th>
                  <th>Generation</th>
                  <th>Candidate</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {derivativesResult.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link href={detailHref(projectId, item, scope)}>{item.id}</Link>
                    </td>
                    <td>{item.derivativeKind}</td>
                    <td>{item.status}</td>
                    <td>
                      {item.derivativeIndexId}
                      {item.isActiveGeneration ? " (active)" : ""}
                    </td>
                    <td>{item.candidateSnapshotId ?? "-"}</td>
                    <td>{new Date(item.createdAt).toISOString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
