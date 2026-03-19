import Link from "next/link";

import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import { listAdminSearchQueryAudits } from "../../../../../lib/indexes";
import { listMyProjects } from "../../../../../lib/projects";
import {
  adminIndexQualityQueryAuditsPath,
  adminIndexQualitySummaryPath,
  adminPath
} from "../../../../../lib/routes";

export const dynamic = "force-dynamic";

function parsePositiveInt(value: string | undefined, fallback: number): number {
  if (!value) {
    return fallback;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return parsed;
}

function sanitizeProjectId(value: string | undefined): string | null {
  if (!value) {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export default async function AdminIndexQualityQueryAuditsPage({
  searchParams
}: Readonly<{
  searchParams: Promise<{ cursor?: string; limit?: string; projectId?: string }>;
}>) {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const { cursor: rawCursor, limit: rawLimit, projectId: rawProjectId } = await searchParams;
  const cursor = Math.max(0, parsePositiveInt(rawCursor, 0));
  const limit = Math.max(1, Math.min(100, parsePositiveInt(rawLimit, 50)));
  const projectId = sanitizeProjectId(rawProjectId);
  const projects = await listMyProjects();
  const auditsResult = projectId
    ? await listAdminSearchQueryAudits(projectId, { cursor, limit })
    : null;
  const secondaryActions = [
    { href: adminPath, label: "Back to admin" },
    ...(projectId
      ? [{ href: adminIndexQualitySummaryPath(projectId), label: "Index quality summary" }]
      : [])
  ];

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform governance"
        meta={
          <StatusChip tone={roleMode.isAdmin ? "danger" : "warning"}>
            {roleMode.isAdmin ? "ADMIN" : "AUDITOR read-only"}
          </StatusChip>
        }
        secondaryActions={secondaryActions}
        summary="Controlled search query-audit stream with normalized query hashes and controlled query-text references."
        title="Index query audits"
      />

      <section className="sectionCard ukde-panel">
        <h3>Project scope</h3>
        {projects.length === 0 ? (
          <p className="ukde-muted">No project memberships are available for this session.</p>
        ) : (
          <div className="buttonRow">
            {projects.map((project) => (
              <Link
                className={project.id === projectId ? "projectPrimaryButton" : "projectSecondaryButton"}
                href={adminIndexQualityQueryAuditsPath(project.id)}
                key={project.id}
              >
                {project.name}
              </Link>
            ))}
          </div>
        )}
      </section>

      {!projectId ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="Select a project to inspect query audits"
            description="Choose a project scope to inspect normalized query hashes and controlled query-text references."
          />
        </section>
      ) : !auditsResult || !auditsResult.ok || !auditsResult.data ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Query audits unavailable"
            description={auditsResult?.detail ?? "Unable to load search query audits."}
          />
        </section>
      ) : auditsResult.data.items.length === 0 ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No query audits yet"
            description="Search-query audit rows appear here after controlled search execution."
          />
        </section>
      ) : (
        <>
          <section className="sectionCard ukde-panel">
            <p className="ukde-muted">
              Raw query text is stored in controlled audit storage and referenced by{" "}
              <code>queryTextKey</code>. This surface intentionally shows hashes and keys only.
            </p>
            <div className="auditTableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Created</th>
                    <th>Actor</th>
                    <th>Search index</th>
                    <th>Query SHA-256</th>
                    <th>Query text key</th>
                    <th>Result count</th>
                    <th>Filters</th>
                  </tr>
                </thead>
                <tbody>
                  {auditsResult.data.items.map((item) => (
                    <tr key={item.id}>
                      <td>{new Date(item.createdAt).toISOString()}</td>
                      <td>{item.actorUserId}</td>
                      <td>{item.searchIndexId}</td>
                      <td>
                        <code>{item.querySha256.slice(0, 20)}…</code>
                      </td>
                      <td>
                        <code>{item.queryTextKey}</code>
                      </td>
                      <td>{item.resultCount}</td>
                      <td>
                        <code>{JSON.stringify(item.filtersJson)}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="sectionCard ukde-panel">
            <div className="buttonRow">
              <Link
                className="projectSecondaryButton"
                href={adminIndexQualityQueryAuditsPath(projectId, {
                  cursor: Math.max(0, cursor - limit),
                  limit
                })}
              >
                Previous
              </Link>
              <Link
                className="projectSecondaryButton"
                href={adminIndexQualityQueryAuditsPath(projectId, {
                  cursor: auditsResult.data.nextCursor ?? cursor,
                  limit
                })}
              >
                Next
              </Link>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
