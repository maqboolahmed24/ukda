import Link from "next/link";
import { redirect } from "next/navigation";

import type { IndexKind } from "@ukde/contracts";
import { InlineAlert, SectionState } from "@ukde/ui/primitives";

import { IndexStatusPoller } from "./index-status-poller";
import { requireCurrentSession } from "../lib/auth/session";
import {
  getProjectIndex,
  getProjectIndexStatus,
  projectIndexKindLabel
} from "../lib/indexes";
import { getProjectWorkspace } from "../lib/projects";
import {
  projectDerivativeIndexPath,
  projectEntityIndexPath,
  projectIndexesPath,
  projectSearchIndexPath
} from "../lib/routes";

interface ProjectIndexDetailProps {
  kind: IndexKind;
  projectId: string;
  indexId: string;
  status?: string;
}

function resolveNotice(status?: string): {
  title: string;
  description: string;
  tone: "success" | "warning" | "danger";
} | null {
  switch (status) {
    case "rebuild-created":
      return {
        title: "Rebuild queued",
        description: "A new generation was created and queued.",
        tone: "success"
      };
    case "rebuild-existing":
      return {
        title: "Equivalent generation reused",
        description:
          "A queued/running/succeeded generation with the same dedupe input already exists.",
        tone: "warning"
      };
    case "activated":
      return {
        title: "Generation activated",
        description:
          "Active projection now points to this SUCCEEDED generation.",
        tone: "success"
      };
    case "cancel-terminal":
      return {
        title: "Generation canceled",
        description: "A queued generation transitioned directly to CANCELED.",
        tone: "success"
      };
    case "cancel-requested":
      return {
        title: "Cancellation requested",
        description:
          "Running cancellation waits for worker cooperative shutdown.",
        tone: "warning"
      };
    case "action-failed":
      return {
        title: "Action failed",
        description:
          "The request failed due to permission, lifecycle, or validation conflict.",
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

function statusPath(projectId: string, kind: IndexKind, indexId: string): string {
  if (kind === "SEARCH") {
    return `/projects/${projectId}/indexes/search/${indexId}/status`;
  }
  if (kind === "ENTITY") {
    return `/projects/${projectId}/indexes/entity/${indexId}/status`;
  }
  return `/projects/${projectId}/indexes/derivative/${indexId}/status`;
}

export async function ProjectIndexDetail({
  kind,
  projectId,
  indexId,
  status
}: ProjectIndexDetailProps) {
  const [session, workspaceResult, indexResult, statusResult] = await Promise.all([
    requireCurrentSession(),
    getProjectWorkspace(projectId),
    getProjectIndex(projectId, kind, indexId),
    getProjectIndexStatus(projectId, kind, indexId)
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=member-route");
  }
  if (
    !indexResult.ok ||
    !indexResult.data ||
    !statusResult.ok ||
    !statusResult.data
  ) {
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Index detail unavailable"
          description={
            indexResult.detail ?? statusResult.detail ?? "Index detail fetch failed."
          }
        />
      </main>
    );
  }

  const index = indexResult.data;
  const statusPayload = statusResult.data;
  const notice = resolveNotice(status);
  const canMutate = session.user.platformRoles.includes("ADMIN");
  const label = projectIndexKindLabel(kind);

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">{label} index</p>
        <h2>{index.id}</h2>
        <div className="buttonRow">
          <Link className="secondaryButton" href={projectIndexesPath(projectId)}>
            Back to indexes
          </Link>
        </div>
      </section>

      {notice ? (
        <InlineAlert title={notice.title} tone={notice.tone}>
          {notice.description}
        </InlineAlert>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h3>Lifecycle</h3>
        <ul className="projectMetaList">
          <li>
            <span>Status</span>
            <strong>{index.status}</strong>
          </li>
          <li>
            <span>Version</span>
            <strong>{index.version}</strong>
          </li>
          <li>
            <span>Dedupe key</span>
            <strong>{index.rebuildDedupeKey.slice(0, 24)}…</strong>
          </li>
          <li>
            <span>Created by</span>
            <strong>{index.createdBy}</strong>
          </li>
          <li>
            <span>Created at</span>
            <strong>{new Date(index.createdAt).toISOString()}</strong>
          </li>
          <li>
            <span>Started at</span>
            <strong>{index.startedAt ? new Date(index.startedAt).toISOString() : "-"}</strong>
          </li>
          <li>
            <span>Finished at</span>
            <strong>{index.finishedAt ? new Date(index.finishedAt).toISOString() : "-"}</strong>
          </li>
          <li>
            <span>Canceled at</span>
            <strong>{index.canceledAt ? new Date(index.canceledAt).toISOString() : "-"}</strong>
          </li>
          <li>
            <span>Failure reason</span>
            <strong>{index.failureReason ?? "-"}</strong>
          </li>
          <li>
            <span>Activated by</span>
            <strong>{index.activatedBy ?? "-"}</strong>
          </li>
          <li>
            <span>Activated at</span>
            <strong>{index.activatedAt ? new Date(index.activatedAt).toISOString() : "-"}</strong>
          </li>
          <li>
            <span>Supersedes</span>
            <strong>
              {index.supersedesIndexId ? (
                <Link href={detailPath(projectId, kind, index.supersedesIndexId)}>
                  {index.supersedesIndexId}
                </Link>
              ) : (
                "none"
              )}
            </strong>
          </li>
          <li>
            <span>Superseded by</span>
            <strong>
              {index.supersededByIndexId ? (
                <Link href={detailPath(projectId, kind, index.supersededByIndexId)}>
                  {index.supersededByIndexId}
                </Link>
              ) : (
                "none"
              )}
            </strong>
          </li>
        </ul>
      </section>

      <IndexStatusPoller
        initialStatus={statusPayload}
        statusUrl={statusPath(projectId, kind, indexId)}
      />

      <section className="sectionCard ukde-panel">
        <h3>Snapshot and build inputs</h3>
        <p className="ukde-muted">
          Source snapshot and normalized build parameters remain stored per generation for deterministic rebuild dedupe and lineage inspection.
        </p>
        <div className="auditTableWrap">
          <pre>{JSON.stringify(index.sourceSnapshotJson, null, 2)}</pre>
        </div>
        <div className="auditTableWrap">
          <pre>{JSON.stringify(index.buildParametersJson, null, 2)}</pre>
        </div>
      </section>

      {canMutate ? (
        <section className="sectionCard ukde-panel">
          <h3>Admin actions</h3>
          <div className="jobsActionRow">
            <form action={`/projects/${projectId}/indexes/activate`} method="post">
              <input name="kind" type="hidden" value={kind} />
              <input name="index_id" type="hidden" value={index.id} />
              <button
                className="projectSecondaryButton"
                disabled={index.status !== "SUCCEEDED"}
                type="submit"
              >
                Activate generation
              </button>
            </form>
            <form action={`/projects/${projectId}/indexes/cancel`} method="post">
              <input name="kind" type="hidden" value={kind} />
              <input name="index_id" type="hidden" value={index.id} />
              <button
                className="projectDangerButton"
                disabled={!(index.status === "QUEUED" || index.status === "RUNNING")}
                type="submit"
              >
                Cancel generation
              </button>
            </form>
          </div>
        </section>
      ) : null}
    </main>
  );
}
