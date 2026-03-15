import Link from "next/link";
import { redirect } from "next/navigation";
import type { ProjectRole, SessionResponse } from "@ukde/contracts";

import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../../lib/auth/session";
import {
  buildWorkspacePathFromEntityOccurrence,
  getProjectEntityDetail,
  getProjectEntityOccurrences
} from "../../../../../../lib/entities";
import { getProjectWorkspace } from "../../../../../../lib/projects";
import {
  parseOptionalInt,
  parseOptionalText
} from "../../../../../../lib/search-ui";
import {
  projectEntitiesPath,
  projectOverviewPath
} from "../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function canUseEntityWorkspace(
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

function buildListQuery(input: {
  cursor?: number;
  entityType?: string;
  q?: string;
}): string {
  const params = new URLSearchParams();
  if (input.q && input.q.trim().length > 0) {
    params.set("q", input.q.trim());
  }
  if (input.entityType && input.entityType.trim().length > 0) {
    params.set("entityType", input.entityType.trim());
  }
  if (typeof input.cursor === "number" && Number.isFinite(input.cursor) && input.cursor > 0) {
    params.set("cursor", String(Math.max(0, Math.round(input.cursor))));
  }
  return params.toString();
}

function buildOccurrenceQuery(cursor?: number): string {
  const params = new URLSearchParams();
  if (typeof cursor === "number" && Number.isFinite(cursor) && cursor > 0) {
    params.set("occCursor", String(Math.max(0, Math.round(cursor))));
  }
  return params.toString();
}

function withOptionalQuery(path: string, query: string): string {
  return query.length > 0 ? `${path}?${query}` : path;
}

function confidenceBand(confidenceSummaryJson: Record<string, unknown>): string {
  const band = confidenceSummaryJson.band;
  return typeof band === "string" && band.trim().length > 0
    ? band.trim()
    : "UNKNOWN";
}

function confidenceAverage(confidenceSummaryJson: Record<string, unknown>): string {
  const average = confidenceSummaryJson.average;
  if (typeof average === "number") {
    return average.toFixed(3);
  }
  return "n/a";
}

export default async function ProjectEntityDetailPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; entityId: string }>;
  searchParams: Promise<{
    cursor?: string;
    entityType?: string;
    occCursor?: string;
    q?: string;
  }>;
}>) {
  const { projectId, entityId } = await params;
  const query = await searchParams;

  const q = parseOptionalText(query.q);
  const entityType = parseOptionalText(query.entityType)?.toUpperCase();
  const listCursorRaw = parseOptionalInt(query.cursor);
  const listCursor =
    typeof listCursorRaw === "number" && listCursorRaw > 0 ? listCursorRaw : 0;
  const occCursorRaw = parseOptionalInt(query.occCursor);
  const occCursor =
    typeof occCursorRaw === "number" && occCursorRaw > 0 ? occCursorRaw : 0;

  const [session, workspaceResult, detailResult, occurrencesResult] = await Promise.all([
    requireCurrentSession(),
    getProjectWorkspace(projectId),
    getProjectEntityDetail(projectId, entityId),
    getProjectEntityOccurrences(projectId, entityId, {
      cursor: occCursor,
      limit: 25
    })
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=member-route");
  }
  if (!canUseEntityWorkspace(session, workspaceResult.data.currentUserRole)) {
    redirect(projectOverviewPath(projectId));
  }

  const backHref = withOptionalQuery(
    projectEntitiesPath(projectId),
    buildListQuery({
      cursor: listCursor,
      entityType,
      q
    })
  );

  if (!detailResult.ok || !detailResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind={detailResult.status === 409 ? "empty" : "error"}
            title={
              detailResult.status === 409
                ? "No active entity index"
                : "Entity detail unavailable"
            }
            description={
              detailResult.detail ??
              "Entity detail could not be loaded from the active entity index."
            }
          />
          <div className="buttonRow">
            <Link className="secondaryButton" href={backHref}>
              Back to entities
            </Link>
          </div>
        </section>
      </main>
    );
  }

  if (!occurrencesResult.ok || !occurrencesResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind={occurrencesResult.status === 409 ? "empty" : "error"}
            title={
              occurrencesResult.status === 409
                ? "No active entity index"
                : "Entity occurrences unavailable"
            }
            description={
              occurrencesResult.detail ??
              "Occurrence query failed for the active entity index."
            }
          />
          <div className="buttonRow">
            <Link className="secondaryButton" href={backHref}>
              Back to entities
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const entity = detailResult.data.entity;
  const nextOccCursor = occurrencesResult.data.nextCursor;
  const firstOccurrencesHref = withOptionalQuery(
    `${projectEntitiesPath(projectId)}/${entity.id}`,
    buildListQuery({
      cursor: listCursor,
      entityType,
      q
    })
  );
  const nextOccurrencesHref =
    typeof nextOccCursor === "number"
      ? withOptionalQuery(
          `${projectEntitiesPath(projectId)}/${entity.id}`,
          [
            buildListQuery({
              cursor: listCursor,
              entityType,
              q
            }),
            buildOccurrenceQuery(nextOccCursor)
          ]
            .filter((segment) => segment.length > 0)
            .join("&")
        )
      : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Entity detail</p>
        <h2>{entity.displayValue}</h2>
        <p className="ukde-muted">
          Canonicalized controlled entity and occurrence lineage scoped to one active entity index generation.
        </p>
        <div className="buttonRow">
          <Link className="secondaryButton" href={backHref}>
            Back to entities
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <ul className="projectMetaList">
          <li>
            <span>Entity index</span>
            <strong>{detailResult.data.entityIndexId}</strong>
          </li>
          <li>
            <span>Entity type</span>
            <strong>{entity.entityType}</strong>
          </li>
          <li>
            <span>Canonical value</span>
            <strong>{entity.canonicalValue}</strong>
          </li>
          <li>
            <span>Occurrences</span>
            <strong>{entity.occurrenceCount}</strong>
          </li>
          <li>
            <span>Confidence band</span>
            <strong>
              <StatusChip tone="info">{confidenceBand(entity.confidenceSummaryJson)}</StatusChip>
            </strong>
          </li>
          <li>
            <span>Average confidence</span>
            <strong>{confidenceAverage(entity.confidenceSummaryJson)}</strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Occurrences</h3>
        {occurrencesResult.data.items.length === 0 ? (
          <SectionState
            kind="empty"
            title="No occurrences"
            description="No provenance-linked occurrences were returned for this entity in the active index."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Page</th>
                  <th>Run</th>
                  <th>Source</th>
                  <th>Basis</th>
                  <th>Confidence</th>
                  <th>Open</th>
                </tr>
              </thead>
              <tbody>
                {occurrencesResult.data.items.map((occurrence) => {
                  const fallbackWorkspacePath = buildWorkspacePathFromEntityOccurrence(
                    projectId,
                    occurrence
                  );
                  const workspacePath =
                    occurrence.workspacePath && occurrence.workspacePath.length > 0
                      ? occurrence.workspacePath
                      : fallbackWorkspacePath;
                  return (
                    <tr key={occurrence.id}>
                      <td>{occurrence.pageNumber}</td>
                      <td>{occurrence.runId}</td>
                      <td>
                        {occurrence.sourceKind}:{occurrence.sourceRefId}
                      </td>
                      <td>
                        {occurrence.occurrenceSpanBasisKind}
                        {occurrence.occurrenceSpanBasisRef
                          ? ` (${occurrence.occurrenceSpanBasisRef})`
                          : ""}
                      </td>
                      <td>{occurrence.confidence.toFixed(3)}</td>
                      <td>
                        <a className="projectSecondaryButton" href={workspacePath}>
                          Open
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="projectSearchPagination">
          {occCursor > 0 ? (
            <Link className="projectSecondaryButton" href={firstOccurrencesHref}>
              First page
            </Link>
          ) : null}
          {nextOccurrencesHref ? (
            <Link className="projectSecondaryButton" href={nextOccurrencesHref}>
              Next page
            </Link>
          ) : null}
        </div>
      </section>
    </main>
  );
}
