import Link from "next/link";
import { redirect } from "next/navigation";
import type { ProjectRole, SessionResponse } from "@ukde/contracts";

import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../lib/auth/session";
import { getProjectEntities } from "../../../../../lib/entities";
import { getProjectWorkspace } from "../../../../../lib/projects";
import {
  parseOptionalInt,
  parseOptionalText
} from "../../../../../lib/search-ui";
import {
  projectEntitiesPath,
  projectEntityPath,
  projectIndexesPath,
  projectOverviewPath
} from "../../../../../lib/routes";

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

function withOptionalQuery(path: string, query: string): string {
  return query.length > 0 ? `${path}?${query}` : path;
}

function resolveConfidenceBand(confidenceSummaryJson: Record<string, unknown>): string {
  const band = confidenceSummaryJson.band;
  if (typeof band === "string" && band.trim().length > 0) {
    return band.trim();
  }
  const average = confidenceSummaryJson.average;
  if (typeof average === "number") {
    if (average >= 0.85) {
      return "HIGH";
    }
    if (average >= 0.6) {
      return "MEDIUM";
    }
    return "LOW";
  }
  return "UNKNOWN";
}

export default async function ProjectEntitiesPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{
    cursor?: string;
    entityType?: string;
    q?: string;
  }>;
}>) {
  const { projectId } = await params;
  const query = await searchParams;
  const q = parseOptionalText(query.q);
  const entityType = parseOptionalText(query.entityType)?.toUpperCase();
  const cursorRaw = parseOptionalInt(query.cursor);
  const cursor = typeof cursorRaw === "number" && cursorRaw > 0 ? cursorRaw : 0;

  const [session, workspaceResult, entitiesResult] = await Promise.all([
    requireCurrentSession(),
    getProjectWorkspace(projectId),
    getProjectEntities(projectId, {
      cursor,
      entityType,
      limit: 25,
      q
    })
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=member-route");
  }
  if (!canUseEntityWorkspace(session, workspaceResult.data.currentUserRole)) {
    redirect(projectOverviewPath(projectId));
  }

  const nextCursor = entitiesResult.ok && entitiesResult.data ? entitiesResult.data.nextCursor : null;
  const firstPageHref = withOptionalQuery(
    projectEntitiesPath(projectId),
    buildListQuery({
      entityType,
      q
    })
  );
  const nextPageHref =
    typeof nextCursor === "number"
      ? withOptionalQuery(
          projectEntitiesPath(projectId),
          buildListQuery({
            cursor: nextCursor,
            entityType,
            q
          })
        )
      : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Controlled entities</p>
        <h2>Project entity discovery</h2>
        <p className="ukde-muted">
          Browse the active entity index generation and jump to provenance-preserving occurrence context.
        </p>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Filters</h3>
        <form action="" className="projectSearchQueryForm" method="get">
          <label className="documentsFilterField" htmlFor="project-entities-q">
            Query (optional)
            <input
              className="projectInput"
              defaultValue={q ?? ""}
              id="project-entities-q"
              name="q"
              type="text"
            />
          </label>
          <label className="documentsFilterField" htmlFor="project-entities-type">
            Entity type (optional)
            <select
              className="projectInput"
              defaultValue={entityType ?? ""}
              id="project-entities-type"
              name="entityType"
            >
              <option value="">All types</option>
              <option value="PERSON">PERSON</option>
              <option value="PLACE">PLACE</option>
              <option value="ORGANISATION">ORGANISATION</option>
              <option value="DATE">DATE</option>
            </select>
          </label>
          <div className="projectSearchFormActions">
            <button className="projectPrimaryButton" type="submit">
              Apply
            </button>
            <Link className="projectSecondaryButton" href={projectEntitiesPath(projectId)}>
              Clear
            </Link>
          </div>
        </form>
      </section>

      {!entitiesResult.ok || !entitiesResult.data ? (
        entitiesResult.status === 409 ? (
          <section className="sectionCard ukde-panel">
            <SectionState
              kind="empty"
              title="No active entity index"
              description="Activate a SUCCEEDED entity index generation before opening entity discovery."
            />
            <div className="buttonRow">
              <Link className="secondaryButton" href={projectIndexesPath(projectId)}>
                Open indexes
              </Link>
            </div>
          </section>
        ) : (
          <section className="sectionCard ukde-panel">
            <SectionState
              kind="error"
              title="Entity discovery unavailable"
              description={entitiesResult.detail ?? "Entity index query failed."}
            />
          </section>
        )
      ) : entitiesResult.data.items.length === 0 ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No entities found"
            description="The active entity index has no matching entities for this filter set."
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <div className="projectSearchResultsHeader">
            <div>
              <h3>Entities</h3>
              <p className="ukde-muted">
                Active entity index: <strong>{entitiesResult.data.entityIndexId}</strong>
              </p>
            </div>
            <StatusChip tone="neutral">
              {entitiesResult.data.items.length} item
              {entitiesResult.data.items.length === 1 ? "" : "s"}
            </StatusChip>
          </div>
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Display value</th>
                  <th>Type</th>
                  <th>Canonical value</th>
                  <th>Occurrences</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {entitiesResult.data.items.map((entity) => {
                  const detailHref = withOptionalQuery(
                    projectEntityPath(projectId, entity.id),
                    buildListQuery({
                      cursor,
                      entityType,
                      q
                    })
                  );
                  return (
                    <tr key={entity.id}>
                      <td>
                        <Link href={detailHref}>{entity.displayValue}</Link>
                      </td>
                      <td>{entity.entityType}</td>
                      <td>{entity.canonicalValue}</td>
                      <td>{entity.occurrenceCount}</td>
                      <td>{resolveConfidenceBand(entity.confidenceSummaryJson)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="projectSearchPagination">
            {cursor > 0 ? (
              <Link className="projectSecondaryButton" href={firstPageHref}>
                First page
              </Link>
            ) : null}
            {nextPageHref ? (
              <Link className="projectSecondaryButton" href={nextPageHref}>
                Next page
              </Link>
            ) : null}
          </div>
        </section>
      )}
    </main>
  );
}
