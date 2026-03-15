import Link from "next/link";
import { redirect } from "next/navigation";

import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { compareProjectPolicy } from "../../../../../../../lib/policies";
import { getProjectWorkspace } from "../../../../../../../lib/projects";
import {
  projectPoliciesPath,
  projectPolicyPath
} from "../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "null";
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}

function resolveTopLevelSection(path: string): string {
  if (!path.startsWith("$")) {
    return "root";
  }
  const normalized = path.replace(/^\$\./, "");
  if (!normalized) {
    return "root";
  }
  const segment = normalized.split(".")[0] ?? "root";
  return segment.split("[")[0] ?? "root";
}

export default async function ProjectPolicyComparePage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; policyId: string }>;
  searchParams: Promise<{
    against?: string;
    againstBaselineSnapshotId?: string;
  }>;
}>) {
  const { projectId, policyId } = await params;
  const query = await searchParams;
  const against = typeof query.against === "string" ? query.against.trim() : "";
  const againstBaselineSnapshotId =
    typeof query.againstBaselineSnapshotId === "string"
      ? query.againstBaselineSnapshotId.trim()
      : "";

  const targetCount =
    Number(Boolean(against)) + Number(Boolean(againstBaselineSnapshotId));
  if (targetCount !== 1) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <p className="ukde-eyebrow">Policy compare</p>
          <h2>Select exactly one comparison target</h2>
          <SectionState
            kind="disabled"
            title="Comparison target is ambiguous"
            description={
              "Use either `against` or `againstBaselineSnapshotId` in the URL query, but never both."
            }
          />
          <div className="buttonRow">
            <Link
              className="secondaryButton"
              href={projectPolicyPath(projectId, policyId)}
            >
              Back to policy detail
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const [workspaceResult, compareResult] = await Promise.all([
    getProjectWorkspace(projectId),
    compareProjectPolicy(projectId, policyId, {
      against: against || null,
      againstBaselineSnapshotId: againstBaselineSnapshotId || null
    })
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=policies-access");
  }

  if (!compareResult.ok || !compareResult.data) {
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Policy compare unavailable"
          description={compareResult.detail ?? "Policy compare request failed."}
        />
      </main>
    );
  }

  const comparison = compareResult.data;
  const sectionCounts = new Map<string, number>();
  for (const difference of comparison.differences) {
    const section = resolveTopLevelSection(difference.path);
    sectionCounts.set(section, (sectionCounts.get(section) ?? 0) + 1);
  }
  const orderedSections = Array.from(sectionCounts.entries()).sort(
    (left, right) => left[0].localeCompare(right[0])
  );

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Policy compare</p>
        <h2>{comparison.sourcePolicy.id}</h2>
        <p className="ukde-muted">
          {comparison.targetKind === "POLICY"
            ? `Compared against policy revision ${comparison.targetPolicy?.id ?? "unknown"}.`
            : `Compared against baseline snapshot ${comparison.targetBaselineSnapshotId}.`}
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectPolicyPath(projectId, policyId)}
          >
            Back to policy detail
          </Link>
          <Link
            className="secondaryButton"
            href={projectPoliciesPath(projectId)}
          >
            Back to policy list
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <ul className="projectMetaList">
          <li>
            <span>Difference count</span>
            <strong>{comparison.differenceCount}</strong>
          </li>
          <li>
            <span>Source hash</span>
            <strong>{comparison.sourceRulesSha256}</strong>
          </li>
          <li>
            <span>Target hash</span>
            <strong>{comparison.targetRulesSha256}</strong>
          </li>
          <li>
            <span>Target kind</span>
            <strong>{comparison.targetKind}</strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Rule differences</h3>
        {orderedSections.length > 0 ? (
          <div className="policyCompareSectionSummary">
            {orderedSections.map(([section, count]) => (
              <StatusChip key={section}>
                {section} ({count})
              </StatusChip>
            ))}
          </div>
        ) : null}
        {comparison.differences.length === 0 ? (
          <SectionState
            kind="empty"
            title="No rule differences"
            description="Source and target policies resolve to the same rules JSON payload."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Section</th>
                  <th>Path</th>
                  <th>Source</th>
                  <th>Target</th>
                </tr>
              </thead>
              <tbody>
                {comparison.differences.map((difference) => (
                  <tr key={difference.path}>
                    <td>{resolveTopLevelSection(difference.path)}</td>
                    <td>{difference.path}</td>
                    <td>{stringifyValue(difference.before)}</td>
                    <td>{stringifyValue(difference.after)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
