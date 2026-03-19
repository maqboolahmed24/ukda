import Link from "next/link";

import type { CapacityEnvelopeStatus, CapacityTestStatus } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../../components/page-header";
import { resolveAdminRoleMode } from "../../../../../../lib/admin-console";
import { requirePlatformRole } from "../../../../../../lib/auth/session";
import {
  getAdminCapacityTest,
  getAdminCapacityTestResults
} from "../../../../../../lib/capacity";
import {
  adminCapacityTestsPath,
  adminOperationsPath,
  adminPath
} from "../../../../../../lib/routes";

export const dynamic = "force-dynamic";

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

function gateTone(status: CapacityEnvelopeStatus): "success" | "warning" | "info" | "danger" {
  if (status === "MEETING") {
    return "success";
  }
  if (status === "BREACHING") {
    return "danger";
  }
  return "warning";
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toISOString();
}

function formatMs(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "n/a";
  }
  return `${value.toFixed(2)} ms`;
}

function formatPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "n/a";
  }
  return `${value.toFixed(3)}%`;
}

export default async function AdminCapacityTestDetailPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ testRunId: string }>;
  searchParams: Promise<{ status?: string }>;
}>) {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const roleMode = resolveAdminRoleMode(session);
  const { testRunId } = await params;
  const { status } = await searchParams;
  const runResult = await getAdminCapacityTest(testRunId);

  if (!runResult.ok || !runResult.data) {
    return (
      <main className="homeLayout">
        <PageHeader
          eyebrow="Platform operations"
          secondaryActions={[
            { href: adminCapacityTestsPath, label: "Back to capacity tests" },
            { href: adminPath, label: "Back to admin" }
          ]}
          summary="Capacity evidence retrieval failed for this run identifier."
          title="Capacity test detail"
        />
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Capacity test unavailable"
            description={runResult.detail ?? "Unable to load capacity test detail."}
          />
        </section>
      </main>
    );
  }

  const detail = runResult.data;
  const resultsResult = detail.hasResults
    ? await getAdminCapacityTestResults(testRunId)
    : null;
  const results =
    resultsResult && resultsResult.ok && resultsResult.data ? resultsResult.data : null;

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
          { href: adminCapacityTestsPath, label: "Back to capacity tests" },
          { href: adminOperationsPath, label: "Operations overview" },
          { href: adminPath, label: "Back to admin" }
        ]}
        summary="Run-level benchmark, load, or soak evidence persisted with deterministic result identifiers."
        title={detail.run.scenarioName}
      />

      {status === "run-created" ? (
        <section className="sectionCard ukde-panel">
          <StatusChip tone="success">Capacity test run persisted.</StatusChip>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <div className="auditIntegrityRow">
          <h2>Run status</h2>
          <StatusChip tone={statusTone(detail.run.status)}>{detail.run.status}</StatusChip>
        </div>
        <ul className="projectMetaList">
          <li>
            <span>Run ID</span>
            <strong>{detail.run.id}</strong>
          </li>
          <li>
            <span>Kind</span>
            <strong>{detail.run.testKind}</strong>
          </li>
          <li>
            <span>Started by</span>
            <strong>{detail.run.startedBy}</strong>
          </li>
          <li>
            <span>Created</span>
            <strong>{formatTimestamp(detail.run.createdAt)}</strong>
          </li>
          <li>
            <span>Started</span>
            <strong>{formatTimestamp(detail.run.startedAt)}</strong>
          </li>
          <li>
            <span>Finished</span>
            <strong>{formatTimestamp(detail.run.finishedAt)}</strong>
          </li>
        </ul>
        {detail.run.failureReason ? (
          <SectionState
            kind="degraded"
            title="Run failed"
            description={detail.run.failureReason}
          />
        ) : null}
      </section>

      {!detail.hasResults ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Evidence pending"
            description="This run has not persisted benchmark/load/soak evidence yet."
          />
        </section>
      ) : !resultsResult?.ok || !results ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Evidence unavailable"
            description={resultsResult?.detail ?? "Unable to load results payload."}
          />
        </section>
      ) : (
        <>
          <section className="sectionCard ukde-panel">
            <h2>Gate summary</h2>
            <div className="ukde-grid" data-columns="3">
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Critical flow p95</p>
                <h3>{results.results.gates.criticalFlowP95Meeting ? "MEETING" : "BREACHING"}</h3>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Throughput target</p>
                <h3>{results.results.gates.throughputMeeting ? "MEETING" : "BREACHING"}</h3>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">24h soak</p>
                <h3>{results.results.gates.soakPassed ? "PASSED" : "FAILED"}</h3>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">GPU SLO</p>
                <h3>{results.results.gates.gpuSloMeeting ? "MEETING" : "BREACHING"}</h3>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Warm start</p>
                <h3>{results.results.gates.warmStartMeeting ? "MEETING" : "BREACHING"}</h3>
              </article>
              <article className="statCard ukde-panel ukde-stat">
                <p className="ukde-eyebrow">Envelope coverage</p>
                <h3>{results.results.gates.capacityEnvelopesMeeting ? "MEETING" : "BREACHING"}</h3>
              </article>
            </div>
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Critical flow p95</h2>
            <div className="auditTableWrap">
              <table className="auditTable">
                <thead>
                  <tr>
                    <th>Flow</th>
                    <th>Observed p95</th>
                    <th>Gate</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Upload</td>
                    <td>{formatMs(results.results.criticalFlowP95Ms.uploadMs)}</td>
                    <td>{results.results.criticalFlowGateStatus.upload}</td>
                  </tr>
                  <tr>
                    <td>Viewer render</td>
                    <td>{formatMs(results.results.criticalFlowP95Ms.viewerRenderMs)}</td>
                    <td>{results.results.criticalFlowGateStatus.viewerRender}</td>
                  </tr>
                  <tr>
                    <td>Inference</td>
                    <td>{formatMs(results.results.criticalFlowP95Ms.inferenceMs)}</td>
                    <td>{results.results.criticalFlowGateStatus.inference}</td>
                  </tr>
                  <tr>
                    <td>Review workspace</td>
                    <td>{formatMs(results.results.criticalFlowP95Ms.reviewWorkspaceMs)}</td>
                    <td>{results.results.criticalFlowGateStatus.reviewWorkspace}</td>
                  </tr>
                  <tr>
                    <td>Search</td>
                    <td>{formatMs(results.results.criticalFlowP95Ms.searchMs)}</td>
                    <td>{results.results.criticalFlowGateStatus.search}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Capacity envelopes</h2>
            <div className="auditTableWrap">
              <table className="auditTable">
                <thead>
                  <tr>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Requests</th>
                    <th>Error rate</th>
                    <th>p95 latency</th>
                    <th>Warm-start p95</th>
                  </tr>
                </thead>
                <tbody>
                  {results.results.capacityEnvelopes.map((envelope) => (
                    <tr key={envelope.role}>
                      <td>{envelope.role}</td>
                      <td>
                        <StatusChip tone={gateTone(envelope.status)}>{envelope.status}</StatusChip>
                      </td>
                      <td>{envelope.requestCount}</td>
                      <td>{formatPercent(envelope.errorRatePercent)}</td>
                      <td>{formatMs(envelope.p95LatencyMs)}</td>
                      <td>{formatMs(envelope.warmStartP95Ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Evidence artifact</h2>
            <ul className="projectMetaList">
              <li>
                <span>Results key</span>
                <strong>{results.resultsKey}</strong>
              </li>
              <li>
                <span>Results SHA-256</span>
                <strong>{results.resultsSha256}</strong>
              </li>
              <li>
                <span>Soak observed hours</span>
                <strong>{results.results.soak.observedHours}</strong>
              </li>
              <li>
                <span>GPU avg utilization</span>
                <strong>{formatPercent(results.results.gpu.avgUtilizationPercent)}</strong>
              </li>
              <li>
                <span>Warm-start p95</span>
                <strong>{formatMs(results.results.warmStart.observedP95Ms)}</strong>
              </li>
            </ul>
            {results.results.notes.length > 0 ? (
              <div className="ukde-stack-sm">
                {results.results.notes.map((note) => (
                  <p className="ukde-muted" key={note}>
                    {note}
                  </p>
                ))}
              </div>
            ) : null}
          </section>
        </>
      )}
    </main>
  );
}
