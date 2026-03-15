import Link from "next/link";
import { redirect } from "next/navigation";

import type { IndexKind, ProjectIndex } from "@ukde/contracts";
import { InlineAlert, SectionState } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../lib/auth/session";
import {
  getProjectActiveIndexes,
  listProjectIndexes,
  projectIndexKindLabel
} from "../../../../../lib/indexes";
import { getProjectWorkspace } from "../../../../../lib/projects";
import {
  projectDerivativeIndexPath,
  projectEntityIndexPath,
  projectSearchIndexPath
} from "../../../../../lib/routes";

export const dynamic = "force-dynamic";

const INDEX_KINDS: readonly IndexKind[] = ["SEARCH", "ENTITY", "DERIVATIVE"];
const REBUILD_SOURCE_SNAPSHOT_TEMPLATE = JSON.stringify(
  {
    policyPinned: true,
    snapshotRefs: ["active-transcription", "active-privacy", "active-governance"]
  },
  null,
  2
);
const REBUILD_PARAMETERS_TEMPLATE = JSON.stringify(
  {
    pipelineVersion: "10.0",
    includeTokenAnchors: true
  },
  null,
  2
);

function resolveNotice(status?: string): {
  title: string;
  description: string;
  tone: "success" | "warning" | "danger";
} | null {
  switch (status) {
    case "rebuild-created":
      return {
        title: "Rebuild queued",
        description: "A new index generation was queued.",
        tone: "success"
      };
    case "rebuild-existing":
      return {
        title: "Equivalent generation reused",
        description:
          "Equivalent queued/running/succeeded generation already exists for this dedupe key.",
        tone: "warning"
      };
    case "activated":
      return {
        title: "Generation activated",
        description: "Active projection was updated without cloning history.",
        tone: "success"
      };
    case "cancel-terminal":
      return {
        title: "Generation canceled",
        description: "A queued generation transitioned to CANCELED.",
        tone: "success"
      };
    case "cancel-requested":
      return {
        title: "Cancellation requested",
        description:
          "A running generation now waits for worker-cooperative shutdown.",
        tone: "warning"
      };
    case "invalid-json":
      return {
        title: "Invalid JSON payload",
        description:
          "Source snapshot and build parameters must both be JSON objects.",
        tone: "danger"
      };
    case "action-failed":
      return {
        title: "Index action failed",
        description: "Rebuild, cancel, or activate request failed.",
        tone: "danger"
      };
    default:
      return null;
  }
}

function detailPath(projectId: string, kind: IndexKind, indexId: string): string {
  if (kind === "SEARCH") {
    return projectSearchIndexPath(projectId, indexId);
  }
  if (kind === "ENTITY") {
    return projectEntityIndexPath(projectId, indexId);
  }
  return projectDerivativeIndexPath(projectId, indexId);
}

function resolveActiveIndexId(
  projection:
    | {
        activeSearchIndexId: string | null;
        activeEntityIndexId: string | null;
        activeDerivativeIndexId: string | null;
      }
    | null
    | undefined,
  kind: IndexKind
): string | null {
  if (!projection) {
    return null;
  }
  if (kind === "SEARCH") {
    return projection.activeSearchIndexId;
  }
  if (kind === "ENTITY") {
    return projection.activeEntityIndexId;
  }
  return projection.activeDerivativeIndexId;
}

export default async function ProjectIndexesPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ status?: string }>;
}>) {
  const { projectId } = await params;
  const query = await searchParams;

  const [session, workspaceResult, activeResult, searchResult, entityResult, derivativeResult] =
    await Promise.all([
      requireCurrentSession(),
      getProjectWorkspace(projectId),
      getProjectActiveIndexes(projectId),
      listProjectIndexes(projectId, "SEARCH"),
      listProjectIndexes(projectId, "ENTITY"),
      listProjectIndexes(projectId, "DERIVATIVE")
    ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=member-route");
  }

  const notice = resolveNotice(
    typeof query.status === "string" ? query.status.trim() : undefined
  );
  const canMutate = session.user.platformRoles.includes("ADMIN");
  const activeProjection = activeResult.ok && activeResult.data ? activeResult.data.projection : null;
  const listByKind: Record<IndexKind, ProjectIndex[] | null> = {
    SEARCH: searchResult.ok && searchResult.data ? searchResult.data.items : null,
    ENTITY: entityResult.ok && entityResult.data ? entityResult.data.items : null,
    DERIVATIVE:
      derivativeResult.ok && derivativeResult.data ? derivativeResult.data.items : null
  };

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Project indexes</p>
        <h2>Discovery index management</h2>
        <p className="ukde-muted">
          Explicit versioned search, entity, and derivative index generations with deterministic rebuild dedupe and projection-based activation.
        </p>
      </section>

      {notice ? (
        <InlineAlert title={notice.title} tone={notice.tone}>
          {notice.description}
        </InlineAlert>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h3>Active projection</h3>
        {!activeResult.ok ? (
          <SectionState
            kind="error"
            title="Active projection unavailable"
            description={activeResult.detail ?? "Projection fetch failed."}
          />
        ) : !activeProjection ? (
          <SectionState
            kind="empty"
            title="No active pointers yet"
            description="Activate a SUCCEEDED generation for each index family when ready."
          />
        ) : (
          <ul className="projectMetaList">
            <li>
              <span>Active search index</span>
              <strong>{activeProjection.activeSearchIndexId ?? "-"}</strong>
            </li>
            <li>
              <span>Active entity index</span>
              <strong>{activeProjection.activeEntityIndexId ?? "-"}</strong>
            </li>
            <li>
              <span>Active derivative index</span>
              <strong>{activeProjection.activeDerivativeIndexId ?? "-"}</strong>
            </li>
            <li>
              <span>Projection updated</span>
              <strong>{new Date(activeProjection.updatedAt).toISOString()}</strong>
            </li>
          </ul>
        )}
      </section>

      {canMutate ? (
        <section className="sectionCard ukde-panel">
          <h3>Queue rebuild</h3>
          <form action={`/projects/${projectId}/indexes/rebuild`} method="post">
            <label>
              Index kind
              <select defaultValue="SEARCH" name="kind">
                {INDEX_KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {projectIndexKindLabel(kind)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Source snapshot JSON
              <textarea
                className="projectTextAreaInput"
                defaultValue={REBUILD_SOURCE_SNAPSHOT_TEMPLATE}
                name="source_snapshot_json"
                rows={8}
              />
            </label>
            <label>
              Build parameters JSON
              <textarea
                className="projectTextAreaInput"
                defaultValue={REBUILD_PARAMETERS_TEMPLATE}
                name="build_parameters_json"
                rows={6}
              />
            </label>
            <label>
              <input name="force" type="checkbox" value="1" /> Force rebuild
              (skip dedupe reuse)
            </label>
            <button className="projectPrimaryButton" type="submit">
              Queue rebuild
            </button>
          </form>
        </section>
      ) : null}

      {INDEX_KINDS.map((kind) => {
        const rows = listByKind[kind];
        const title = `${projectIndexKindLabel(kind)} indexes`;
        const activeId = resolveActiveIndexId(activeProjection, kind);

        return (
          <section className="sectionCard ukde-panel" key={kind}>
            <h3>{title}</h3>
            {rows === null ? (
              <SectionState
                kind="error"
                title={`${title} unavailable`}
                description="Index listing failed."
              />
            ) : rows.length === 0 ? (
              <SectionState
                kind="empty"
                title={`No ${projectIndexKindLabel(kind).toLowerCase()} generations`}
                description="Queue the first rebuild to start append-only lineage."
              />
            ) : (
              <div className="auditTableWrap">
                <table className="auditTable">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Version</th>
                      <th>Status</th>
                      <th>Created</th>
                      <th>Active</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <Link href={detailPath(projectId, kind, row.id)}>{row.id}</Link>
                        </td>
                        <td>{row.version}</td>
                        <td>{row.status}</td>
                        <td>{new Date(row.createdAt).toISOString()}</td>
                        <td>{activeId === row.id ? "Yes" : "No"}</td>
                        <td>
                          {canMutate ? (
                            <div className="jobsActionRow">
                              <form action={`/projects/${projectId}/indexes/activate`} method="post">
                                <input name="kind" type="hidden" value={kind} />
                                <input name="index_id" type="hidden" value={row.id} />
                                <button
                                  className="projectSecondaryButton"
                                  disabled={row.status !== "SUCCEEDED"}
                                  type="submit"
                                >
                                  Activate
                                </button>
                              </form>
                              <form action={`/projects/${projectId}/indexes/cancel`} method="post">
                                <input name="kind" type="hidden" value={kind} />
                                <input name="index_id" type="hidden" value={row.id} />
                                <button
                                  className="projectDangerButton"
                                  disabled={!(row.status === "QUEUED" || row.status === "RUNNING")}
                                  type="submit"
                                >
                                  Cancel
                                </button>
                              </form>
                            </div>
                          ) : (
                            "-"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        );
      })}
    </main>
  );
}
