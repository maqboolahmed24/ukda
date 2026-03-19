import Link from "next/link";

import type { CapacityTestStatus, CapacityTestKind } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import { listAdminCapacityTests } from "../../../../../lib/capacity";
import {
  adminCapacityTestDetailPath,
  adminCapacityTestsPath,
  adminOperationsPath,
  adminOperationsTimelinesPath,
  adminPath,
  withQuery
} from "../../../../../lib/routes";
import { normalizeCursorParam } from "../../../../../lib/url-state";

export const dynamic = "force-dynamic";

const TEST_KIND_OPTIONS: CapacityTestKind[] = ["BENCHMARK", "LOAD", "SOAK"];

function statusTone(status: CapacityTestStatus): "success" | "warning" | "danger" | "info" {
  if (status === "SUCCEEDED") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "RUNNING") {
    return "info";
  }
  return "warning";
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toISOString();
}

function resolveRunNotice(status: string | undefined): { tone: "success" | "warning"; text: string } | null {
  if (status === "run-created") {
    return {
      tone: "success",
      text: "Capacity test run persisted. Evidence generation is complete for this run."
    };
  }
  if (status === "run-failed") {
    return {
      tone: "warning",
      text: "Capacity test run request failed. Existing evidence remains unchanged."
    };
  }
  if (status === "run-invalid") {
    return {
      tone: "warning",
      text: "Capacity run request was invalid. Choose a scenario and test kind."
    };
  }
  return null;
}

export default async function AdminCapacityTestsPage({
  searchParams
}: Readonly<{
  searchParams: Promise<{
    cursor?: string;
    status?: string;
  }>;
}>) {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const rawFilters = await searchParams;
  const cursor = normalizeCursorParam(rawFilters.cursor);
  const runNotice = resolveRunNotice(rawFilters.status);
  const testsResult = await listAdminCapacityTests({
    cursor,
    pageSize: 50
  });

  const responseData = testsResult.ok && testsResult.data ? testsResult.data : null;
  const items = responseData?.items ?? [];
  const scenarioCatalog = responseData?.scenarioCatalog ?? [];

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform operations"
        meta={
          <StatusChip tone={roleMode.isAdmin ? "danger" : "warning"}>
            {roleMode.isAdmin ? "ADMIN" : "AUDITOR read-only"}
          </StatusChip>
        }
        secondaryActions={[
          { href: adminOperationsPath, label: "Operations overview" },
          { href: adminOperationsTimelinesPath, label: "Timelines" },
          { href: adminPath, label: "Back to admin" }
        ]}
        summary="Persisted benchmark, load, and soak evidence for throughput, p95, warm-start, and capacity envelopes."
        title="Capacity tests"
      />

      {runNotice ? (
        <section className="sectionCard ukde-panel">
          <StatusChip tone={runNotice.tone}>{runNotice.text}</StatusChip>
        </section>
      ) : null}

      {roleMode.isAdmin ? (
        <section className="sectionCard ukde-panel">
          <h2>Run capacity scenario</h2>
          {scenarioCatalog.length === 0 ? (
            <SectionState
              kind="degraded"
              title="Scenario catalog unavailable"
              description="Capacity scenarios are unavailable. Existing run history remains readable."
            />
          ) : (
            <form action={`${adminCapacityTestsPath}/run`} className="auditFilterForm" method="post">
              <label htmlFor="scenario-name">Scenario</label>
              <select defaultValue={scenarioCatalog[0]?.name} id="scenario-name" name="scenarioName">
                {scenarioCatalog.map((scenario) => (
                  <option key={scenario.name} value={scenario.name}>
                    {scenario.name}
                  </option>
                ))}
              </select>
              <label htmlFor="test-kind">Test kind</label>
              <select defaultValue="BENCHMARK" id="test-kind" name="testKind">
                {TEST_KIND_OPTIONS.map((kind) => (
                  <option key={kind} value={kind}>
                    {kind}
                  </option>
                ))}
              </select>
              <input name="redirectTo" type="hidden" value={adminCapacityTestsPath} />
              <button className="projectPrimaryButton" type="submit">
                Run test
              </button>
            </form>
          )}
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Auditor read-only mode"
            description="Auditors can inspect persisted capacity evidence but cannot create or rerun scenarios."
          />
        </section>
      )}

      <section className="sectionCard ukde-panel">
        {!testsResult.ok ? (
          <SectionState
            kind="error"
            title="Capacity tests unavailable"
            description={testsResult.detail ?? "Unable to load capacity test runs."}
          />
        ) : items.length === 0 ? (
          <SectionState
            kind="no-results"
            title="No capacity tests recorded"
            description="Create a benchmark, load, or soak run to persist evidence."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Scenario</th>
                  <th>Kind</th>
                  <th>Status</th>
                  <th>Started by</th>
                  <th>Results</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{formatTimestamp(item.createdAt)}</td>
                    <td>
                      <Link href={adminCapacityTestDetailPath(item.id)}>{item.scenarioName}</Link>
                    </td>
                    <td>{item.testKind}</td>
                    <td>
                      <StatusChip tone={statusTone(item.status)}>{item.status}</StatusChip>
                    </td>
                    <td>{item.startedBy}</td>
                    <td>{item.resultsKey ? "Persisted" : "Pending"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {typeof responseData?.nextCursor === "number" ? (
          <div className="buttonRow">
            <Link
              className="secondaryButton"
              href={withQuery(adminCapacityTestsPath, {
                cursor: responseData.nextCursor
              })}
            >
              Next page
            </Link>
          </div>
        ) : null}
      </section>
    </main>
  );
}
