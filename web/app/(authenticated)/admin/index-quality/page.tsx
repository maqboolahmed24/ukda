import Link from "next/link";

import type { IndexFreshnessStatus, ProjectSummary } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../lib/auth/session";
import { getAdminIndexQualitySummary } from "../../../../lib/indexes";
import { listMyProjects } from "../../../../lib/projects";
import {
  adminIndexQualityDetailPath,
  adminIndexQualityQueryAuditsPath,
  adminIndexQualitySummaryPath,
  adminPath
} from "../../../../lib/routes";

export const dynamic = "force-dynamic";

function freshnessTone(status: IndexFreshnessStatus): "success" | "warning" | "info" | "danger" {
  if (status === "current") {
    return "success";
  }
  if (status === "stale") {
    return "warning";
  }
  if (status === "missing") {
    return "info";
  }
  return "danger";
}

function pickProjectId(value: string | undefined): string | null {
  if (!value) {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function projectChipClass(projectId: string, selectedProjectId: string | null): string {
  if (projectId === selectedProjectId) {
    return "projectPrimaryButton";
  }
  return "projectSecondaryButton";
}

function renderProjectSelector(
  projects: ProjectSummary[],
  selectedProjectId: string | null
) {
  if (projects.length === 0) {
    return (
      <p className="ukde-muted">
        No project memberships are available for this session.
      </p>
    );
  }
  return (
    <div className="buttonRow">
      {projects.map((project) => (
        <Link
          className={projectChipClass(project.id, selectedProjectId)}
          href={adminIndexQualitySummaryPath(project.id)}
          key={project.id}
        >
          {project.name}
        </Link>
      ))}
    </div>
  );
}

export default async function AdminIndexQualityPage({
  searchParams
}: Readonly<{
  searchParams: Promise<{ projectId?: string }>;
}>) {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const { projectId: rawProjectId } = await searchParams;
  const selectedProjectId = pickProjectId(rawProjectId);
  const projects = await listMyProjects();
  const summaryResult = selectedProjectId
    ? await getAdminIndexQualitySummary(selectedProjectId)
    : null;
  const summaryData =
    summaryResult && summaryResult.ok && summaryResult.data ? summaryResult.data : null;
  const secondaryActions = [
    { href: adminPath, label: "Back to admin" },
    ...(selectedProjectId
      ? [
          {
            href: adminIndexQualityQueryAuditsPath(selectedProjectId),
            label: "Query audits"
          }
        ]
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
        summary="Recall-first search activation readiness, freshness status, and rollback context for index generations."
        title="Index quality"
      />

      <section className="sectionCard ukde-panel">
        <h3>Project scope</h3>
        {renderProjectSelector(projects, selectedProjectId)}
      </section>

      {!selectedProjectId ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="Select a project to inspect index quality"
            description="Choose a project scope to review freshness, blockers, and activation readiness."
          />
        </section>
      ) : !summaryData ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Index quality unavailable"
            description={summaryResult?.detail ?? "Unable to load index quality summary."}
          />
        </section>
      ) : (
        <>
          <section className="sectionCard ukde-panel">
            <ul className="projectMetaList">
              <li>
                <span>Project ID</span>
                <strong>{summaryData.projectId}</strong>
              </li>
              <li>
                <span>Projection updated</span>
                <strong>
                  {summaryData.projectionUpdatedAt
                    ? new Date(summaryData.projectionUpdatedAt).toISOString()
                    : "Not set"}
                </strong>
              </li>
              <li>
                <span>Index families</span>
                <strong>{summaryData.items.length}</strong>
              </li>
            </ul>
          </section>

          <section className="sectionCard ukde-panel">
            <h3>Freshness and activation posture</h3>
            <div className="ukde-grid" data-columns="3">
              {summaryData.items.map((item) => {
                const detailIndexId =
                  item.freshness.activeIndexId ?? item.freshness.latestSucceededIndexId;
                const detailHref = detailIndexId
                  ? `${adminIndexQualityDetailPath(item.kind, detailIndexId)}?projectId=${encodeURIComponent(summaryData.projectId)}`
                  : null;
                return (
                  <article className="statCard ukde-panel ukde-surface-raised" key={item.kind}>
                    <div className="auditIntegrityRow">
                      <h4>{item.kind}</h4>
                      <StatusChip tone={freshnessTone(item.freshness.status)}>
                        {item.freshness.status}
                      </StatusChip>
                    </div>
                    <ul className="projectMetaList">
                      <li>
                        <span>Active version</span>
                        <strong>{item.freshness.activeVersion ?? "none"}</strong>
                      </li>
                      <li>
                        <span>Latest SUCCEEDED version</span>
                        <strong>{item.freshness.latestSucceededVersion ?? "none"}</strong>
                      </li>
                      <li>
                        <span>Stale generation gap</span>
                        <strong>{item.freshness.staleGenerationGap ?? 0}</strong>
                      </li>
                      <li>
                        <span>Activation blockers</span>
                        <strong>{item.searchActivationBlockerCount}</strong>
                      </li>
                    </ul>
                    {item.searchCoverage ? (
                      <p className="ukde-muted">
                        eligible {item.searchCoverage.eligibleInputCount ?? "n/a"}, anchors{" "}
                        {item.searchCoverage.tokenAnchorValidInputCount ?? "n/a"}, geometry{" "}
                        {item.searchCoverage.tokenGeometryCoveredInputCount ?? "n/a"}
                      </p>
                    ) : null}
                    {item.freshness.reason ? (
                      <p className="ukde-muted">{item.freshness.reason}</p>
                    ) : null}
                    {detailHref ? (
                      <Link className="secondaryButton" href={detailHref}>
                        Open detail
                      </Link>
                    ) : null}
                  </article>
                );
              })}
            </div>
          </section>
        </>
      )}
    </main>
  );
}
