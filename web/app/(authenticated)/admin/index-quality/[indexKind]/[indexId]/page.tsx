import Link from "next/link";

import type { IndexKind } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../../lib/auth/session";
import { getAdminIndexQualityDetail } from "../../../../../../lib/indexes";
import {
  adminIndexQualityQueryAuditsPath,
  adminIndexQualitySummaryPath,
  adminPath
} from "../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function parseIndexKind(value: string): IndexKind | null {
  const normalized = value.trim().toUpperCase();
  if (normalized === "SEARCH") {
    return "SEARCH";
  }
  if (normalized === "ENTITY") {
    return "ENTITY";
  }
  if (normalized === "DERIVATIVE") {
    return "DERIVATIVE";
  }
  return null;
}

export default async function AdminIndexQualityDetailPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ indexId: string; indexKind: string }>;
  searchParams: Promise<{ projectId?: string }>;
}>) {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const { indexId, indexKind } = await params;
  const { projectId: projectIdParam } = await searchParams;
  const normalizedKind = parseIndexKind(indexKind);

  if (normalizedKind === null) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Invalid index kind"
            description="indexKind must be SEARCH, ENTITY, or DERIVATIVE."
          />
        </section>
      </main>
    );
  }

  const detailResult = await getAdminIndexQualityDetail(normalizedKind, indexId);
  if (!detailResult.ok || !detailResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Index quality detail unavailable"
            description={detailResult.detail ?? "Unable to load index quality detail."}
          />
        </section>
      </main>
    );
  }

  const detail = detailResult.data;
  const projectId = detail.projectId;
  const summaryHref = adminIndexQualitySummaryPath(projectIdParam ?? projectId);
  const secondaryActions = [
    { href: adminPath, label: "Back to admin" },
    { href: summaryHref, label: "Back to summary" },
    { href: adminIndexQualityQueryAuditsPath(projectId), label: "Query audits" }
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
        summary="Per-generation recall-first activation posture and rollback context."
        title={`${detail.kind} index quality detail`}
      />

      <section className="sectionCard ukde-panel">
        <h3>Generation</h3>
        <ul className="projectMetaList">
          <li>
            <span>Project ID</span>
            <strong>{projectId}</strong>
          </li>
          <li>
            <span>Index ID</span>
            <strong>{detail.index.id}</strong>
          </li>
          <li>
            <span>Status</span>
            <strong>{detail.index.status}</strong>
          </li>
          <li>
            <span>Version</span>
            <strong>{detail.index.version}</strong>
          </li>
          <li>
            <span>Created at</span>
            <strong>{new Date(detail.index.createdAt).toISOString()}</strong>
          </li>
          <li>
            <span>Active generation</span>
            <strong>{detail.isActiveGeneration ? "yes" : "no"}</strong>
          </li>
          <li>
            <span>Latest SUCCEEDED generation</span>
            <strong>{detail.isLatestSucceededGeneration ? "yes" : "no"}</strong>
          </li>
          <li>
            <span>Rollback eligible</span>
            <strong>{detail.rollbackEligible ? "yes" : "no"}</strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Freshness</h3>
        <div className="auditIntegrityRow">
          <StatusChip
            tone={
              detail.freshness.status === "current"
                ? "success"
                : detail.freshness.status === "stale"
                  ? "warning"
                  : detail.freshness.status === "missing"
                    ? "info"
                    : "danger"
            }
          >
            {detail.freshness.status}
          </StatusChip>
        </div>
        <ul className="projectMetaList">
          <li>
            <span>Active index ID</span>
            <strong>{detail.freshness.activeIndexId ?? "none"}</strong>
          </li>
          <li>
            <span>Latest SUCCEEDED index ID</span>
            <strong>{detail.freshness.latestSucceededIndexId ?? "none"}</strong>
          </li>
          <li>
            <span>Blocked codes</span>
            <strong>
              {detail.freshness.blockedCodes.length > 0
                ? detail.freshness.blockedCodes.join(", ")
                : "none"}
            </strong>
          </li>
        </ul>
        {detail.freshness.reason ? (
          <p className="ukde-muted">{detail.freshness.reason}</p>
        ) : null}
      </section>

      {detail.searchCoverage ? (
        <section className="sectionCard ukde-panel">
          <h3>Search coverage</h3>
          <ul className="projectMetaList">
            <li>
              <span>Eligible inputs</span>
              <strong>{detail.searchCoverage.eligibleInputCount ?? "n/a"}</strong>
            </li>
            <li>
              <span>Token-anchor valid inputs</span>
              <strong>{detail.searchCoverage.tokenAnchorValidInputCount ?? "n/a"}</strong>
            </li>
            <li>
              <span>Token-geometry covered inputs</span>
              <strong>{detail.searchCoverage.tokenGeometryCoveredInputCount ?? "n/a"}</strong>
            </li>
            <li>
              <span>Historical line-only excluded</span>
              <strong>{detail.searchCoverage.historicalLineOnlyExcludedCount}</strong>
            </li>
            <li>
              <span>Line-only fallback marker</span>
              <strong>
                {detail.searchCoverage.historicalLineOnlyFallbackAllowed
                  ? "present"
                  : "missing"}
              </strong>
            </li>
          </ul>
          {detail.searchCoverage.historicalLineOnlyFallbackReason ? (
            <p className="ukde-muted">
              fallback reason: {detail.searchCoverage.historicalLineOnlyFallbackReason}
            </p>
          ) : null}
        </section>
      ) : null}

      {detail.searchActivationEvaluation ? (
        <section className="sectionCard ukde-panel">
          <h3>Activation gate evaluation</h3>
          <p className="ukde-muted">
            {detail.searchActivationEvaluation.passed
              ? "Recall-first activation gates pass for this generation."
              : "Recall-first activation blockers are present."}
          </p>
          <div className="auditTableWrap">
            <table>
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {detail.searchActivationEvaluation.blockers.length > 0 ? (
                  detail.searchActivationEvaluation.blockers.map((blocker) => (
                    <tr key={blocker.code}>
                      <td>
                        <code>{blocker.code}</code>
                      </td>
                      <td>{blocker.message}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={2}>No blockers</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h3>Snapshot and build metadata</h3>
        <div className="auditTableWrap">
          <pre>{JSON.stringify(detail.index.sourceSnapshotJson, null, 2)}</pre>
        </div>
        <div className="auditTableWrap">
          <pre>{JSON.stringify(detail.index.buildParametersJson, null, 2)}</pre>
        </div>
      </section>
    </main>
  );
}
