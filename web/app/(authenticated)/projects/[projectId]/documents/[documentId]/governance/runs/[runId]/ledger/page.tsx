import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type {
  GovernanceArtifactStatus,
  GovernanceGenerationStatus,
  GovernanceLedgerEntriesView,
  GovernanceLedgerVerificationStatus,
  GovernanceReadinessStatus
} from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../../../../../../lib/auth/session";
import {
  getProjectDocument,
  getProjectDocumentGovernanceRunLedger,
  getProjectDocumentGovernanceRunLedgerStatus,
  getProjectDocumentGovernanceRunLedgerSummary,
  getProjectDocumentGovernanceRunLedgerVerifyRunStatus,
  getProjectDocumentGovernanceRunLedgerVerifyStatus,
  listProjectDocumentGovernanceRunLedgerEntries,
  listProjectDocumentGovernanceRunLedgerVerifyRuns,
  postProjectDocumentGovernanceRunLedgerVerify,
  postProjectDocumentGovernanceRunLedgerVerifyRunCancel
} from "../../../../../../../../../../lib/documents";
import {
  projectDocumentGovernancePath,
  projectDocumentGovernanceRunEventsPath,
  projectDocumentGovernanceRunLedgerPath,
  projectDocumentGovernanceRunManifestPath,
  projectDocumentGovernanceRunOverviewPath,
  projectsPath
} from "../../../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function resolveArtifactTone(
  status: GovernanceArtifactStatus
): "danger" | "neutral" | "success" | "warning" {
  if (status === "SUCCEEDED") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "UNAVAILABLE" || status === "CANCELED") {
    return "neutral";
  }
  return "warning";
}

function resolveReadinessTone(
  status: GovernanceReadinessStatus
): "danger" | "neutral" | "success" | "warning" {
  if (status === "READY") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  return "warning";
}

function resolveGenerationTone(
  status: GovernanceGenerationStatus
): "danger" | "neutral" | "success" | "warning" {
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  if (status === "RUNNING") {
    return "warning";
  }
  return "success";
}

function resolveVerificationTone(
  status: GovernanceLedgerVerificationStatus
): "danger" | "neutral" | "success" | "warning" {
  if (status === "VALID") {
    return "success";
  }
  if (status === "INVALID") {
    return "danger";
  }
  return "warning";
}

function resolveActionPresentation(action: string): {
  label: string;
  tone: "danger" | "neutral" | "success" | "warning" | "info";
} {
  if (action === "PSEUDONYMIZE") {
    return { label: "Pseudonymized", tone: "info" };
  }
  if (action === "GENERALIZE") {
    return { label: "Generalized", tone: "neutral" };
  }
  if (action === "MASK") {
    return { label: "Masked", tone: "warning" };
  }
  return { label: action, tone: "neutral" };
}

function parseOptionalText(value: string | undefined): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function parseEntriesView(value: string | undefined): GovernanceLedgerEntriesView {
  if (value === "timeline") {
    return "timeline";
  }
  return "list";
}

function parseCursor(value: string | undefined): number {
  if (typeof value !== "string" || value.trim().length === 0) {
    return 0;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return 0;
  }
  return parsed;
}

function parseLimit(value: string | undefined): number {
  if (typeof value !== "string" || value.trim().length === 0) {
    return 100;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return 100;
  }
  return Math.max(1, Math.min(200, parsed));
}

function canCancelVerificationRun(status: GovernanceArtifactStatus): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

function buildLedgerHref(
  projectId: string,
  documentId: string,
  runId: string,
  options: {
    view?: GovernanceLedgerEntriesView;
    cursor?: number;
    limit?: number;
    rowId?: string;
    verificationRunId?: string;
    notice?: string;
    error?: string;
  }
): string {
  const params = new URLSearchParams();
  if (options.view) {
    params.set("view", options.view);
  }
  if (typeof options.cursor === "number" && options.cursor > 0) {
    params.set("cursor", String(options.cursor));
  }
  if (typeof options.limit === "number" && options.limit !== 100) {
    params.set("limit", String(options.limit));
  }
  if (options.rowId && options.rowId.trim().length > 0) {
    params.set("rowId", options.rowId.trim());
  }
  if (options.verificationRunId && options.verificationRunId.trim().length > 0) {
    params.set("verificationRunId", options.verificationRunId.trim());
  }
  if (options.notice && options.notice.trim().length > 0) {
    params.set("notice", options.notice.trim());
  }
  if (options.error && options.error.trim().length > 0) {
    params.set("error", options.error.trim());
  }
  const query = params.toString();
  const basePath = projectDocumentGovernanceRunLedgerPath(projectId, documentId, runId);
  return query.length > 0 ? `${basePath}?${query}` : basePath;
}

export default async function ProjectDocumentGovernanceRunLedgerPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string; runId: string }>;
  searchParams: Promise<{
    cursor?: string;
    error?: string;
    limit?: string;
    notice?: string;
    rowId?: string;
    verificationRunId?: string;
    view?: string;
  }>;
}>) {
  const { projectId, documentId, runId } = await params;
  const query = await searchParams;
  const session = await requireCurrentSession();

  const viewFilter = parseEntriesView(query.view);
  const cursorFilter = parseCursor(query.cursor);
  const limitFilter = parseLimit(query.limit);
  const rowIdFilter = parseOptionalText(query.rowId);
  const verificationRunIdFilter = parseOptionalText(query.verificationRunId);
  const noticeCode = parseOptionalText(query.notice);
  const errorCode = parseOptionalText(query.error);

  const isAdmin = session.user.platformRoles.includes("ADMIN");

  const [documentResult, ledgerResult, statusResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectDocumentGovernanceRunLedger(projectId, documentId, runId),
    getProjectDocumentGovernanceRunLedgerStatus(projectId, documentId, runId)
  ]);

  if (!documentResult.ok) {
    if (documentResult.status === 404) {
      notFound();
    }
    if (documentResult.status === 403) {
      redirect(projectsPath);
    }
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Ledger route unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for ledger detail."
          }
        />
      </main>
    );
  }

  if (ledgerResult.status === 403 || statusResult.status === 403) {
    const document = documentResult.data;
    if (!document) {
      notFound();
    }
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <p className="ukde-eyebrow">Governance evidence ledger</p>
          <h2>{document.originalFilename}</h2>
          <div className="buttonRow">
            <Link
              className="secondaryButton"
              href={projectDocumentGovernanceRunOverviewPath(projectId, document.id, runId)}
            >
              Run overview
            </Link>
            <Link
              className="secondaryButton"
              href={projectDocumentGovernanceRunManifestPath(projectId, document.id, runId)}
            >
              Manifest
            </Link>
            <Link
              className="secondaryButton"
              href={projectDocumentGovernancePath(projectId, document.id, {
                tab: "overview",
                runId
              })}
            >
              Governance overview
            </Link>
          </div>
        </section>
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Ledger access restricted"
            description="Evidence-ledger reads are controlled-only and available to administrator or auditor roles."
          />
        </section>
      </main>
    );
  }

  if (!ledgerResult.ok || !statusResult.ok) {
    if (ledgerResult.status === 404 || statusResult.status === 404) {
      notFound();
    }
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Ledger detail unavailable"
          description={
            ledgerResult.detail ??
            statusResult.detail ??
            "Ledger lineage and status could not be loaded."
          }
        />
      </main>
    );
  }

  const document = documentResult.data;
  const ledger = ledgerResult.data;
  const ledgerStatus = statusResult.data;
  if (!document || !ledger || !ledgerStatus) {
    notFound();
  }
  const resolvedDocument = document;

  const [entriesResult, summaryResult, verifyStatusResult, verifyRunsResult, verifyDetailResult] =
    await Promise.all([
      listProjectDocumentGovernanceRunLedgerEntries(projectId, resolvedDocument.id, runId, {
        cursor: cursorFilter,
        limit: limitFilter,
        view: viewFilter
      }),
      getProjectDocumentGovernanceRunLedgerSummary(projectId, resolvedDocument.id, runId),
      getProjectDocumentGovernanceRunLedgerVerifyStatus(projectId, resolvedDocument.id, runId),
      listProjectDocumentGovernanceRunLedgerVerifyRuns(projectId, resolvedDocument.id, runId),
      verificationRunIdFilter
        ? getProjectDocumentGovernanceRunLedgerVerifyRunStatus(
            projectId,
            resolvedDocument.id,
            runId,
            verificationRunIdFilter
          )
        : Promise.resolve(null)
    ]);

  const ledgerEntries = entriesResult.ok ? entriesResult.data : null;
  const ledgerSummary = summaryResult.ok ? summaryResult.data : null;
  const verifyStatus = verifyStatusResult.ok ? verifyStatusResult.data : null;
  const verifyRuns = verifyRunsResult.ok ? verifyRunsResult.data : null;
  const verifyDetail =
    verifyDetailResult !== null && verifyDetailResult.ok ? verifyDetailResult.data : null;

  const previousCursor =
    ledgerEntries && cursorFilter > 0 ? Math.max(0, cursorFilter - limitFilter) : null;
  const nextCursor = ledgerEntries?.nextCursor ?? null;
  const selectedLedgerRow =
    ledgerEntries?.items.find((item) => item.rowId === rowIdFilter) ?? null;
  const selectedVerificationRun =
    verifyDetail?.attempt ??
    verifyRuns?.items.find((item) => item.id === verificationRunIdFilter) ??
    null;

  const currentLedgerState = {
    view: viewFilter,
    cursor: cursorFilter > 0 ? cursorFilter : undefined,
    limit: limitFilter,
    rowId: rowIdFilter,
    verificationRunId: verificationRunIdFilter
  };

  const buildCurrentLedgerHref = (overrides?: {
    cursor?: number;
    error?: string;
    notice?: string;
    rowId?: string;
    verificationRunId?: string;
    view?: GovernanceLedgerEntriesView;
  }): string =>
    buildLedgerHref(projectId, resolvedDocument.id, runId, {
      view: overrides?.view ?? currentLedgerState.view,
      cursor: typeof overrides?.cursor === "number" ? overrides.cursor : currentLedgerState.cursor,
      limit: currentLedgerState.limit,
      rowId:
        typeof overrides?.rowId !== "undefined"
          ? overrides.rowId
          : currentLedgerState.rowId,
      verificationRunId:
        typeof overrides?.verificationRunId !== "undefined"
          ? overrides.verificationRunId
          : currentLedgerState.verificationRunId,
      notice: overrides?.notice,
      error: overrides?.error
    });

  async function requestVerificationAction() {
    "use server";
    const result = await postProjectDocumentGovernanceRunLedgerVerify(
      projectId,
      resolvedDocument.id,
      runId
    );
    if (!result.ok || !result.data) {
      redirect(
        buildLedgerHref(projectId, resolvedDocument.id, runId, {
          ...currentLedgerState,
          error: "verify_request_failed"
        })
      );
    }
    redirect(
      buildLedgerHref(projectId, resolvedDocument.id, runId, {
        ...currentLedgerState,
        notice: "verify_requested",
        verificationRunId: result.data.attempt.id
      })
    );
  }

  async function cancelVerificationAction(formData: FormData) {
    "use server";
    const verificationRunId = String(formData.get("verificationRunId") ?? "").trim();
    if (!verificationRunId) {
      redirect(
        buildLedgerHref(projectId, resolvedDocument.id, runId, {
          ...currentLedgerState,
          error: "verify_cancel_missing"
        })
      );
    }
    const result = await postProjectDocumentGovernanceRunLedgerVerifyRunCancel(
      projectId,
      resolvedDocument.id,
      runId,
      verificationRunId
    );
    if (!result.ok || !result.data) {
      redirect(
        buildLedgerHref(projectId, resolvedDocument.id, runId, {
          ...currentLedgerState,
          error: "verify_cancel_failed",
          verificationRunId
        })
      );
    }
    redirect(
      buildLedgerHref(projectId, resolvedDocument.id, runId, {
        ...currentLedgerState,
        notice: "verify_canceled",
        verificationRunId: result.data.attempt.id
      })
    );
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Governance evidence ledger</p>
        <h2>{document.originalFilename}</h2>
        <p className="ukde-muted">
          Controlled evidence is internal-only, append-only, and available only to
          administrator and auditor roles.
        </p>
        {noticeCode === "verify_requested" ? (
          <p className="ukde-muted">Ledger re-verification request accepted.</p>
        ) : null}
        {noticeCode === "verify_canceled" ? (
          <p className="ukde-muted">Verification attempt canceled.</p>
        ) : null}
        {errorCode ? (
          <p className="ukde-muted">Ledger action could not be completed ({errorCode}).</p>
        ) : null}
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentGovernancePath(projectId, document.id, {
              tab: "ledger",
              runId
            })}
          >
            Governance tab
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentGovernanceRunOverviewPath(projectId, document.id, runId)}
          >
            Run overview
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentGovernanceRunManifestPath(projectId, document.id, runId)}
          >
            Manifest
          </Link>
          <Link
            className="secondaryButton"
            aria-current="page"
            href={projectDocumentGovernanceRunLedgerPath(projectId, document.id, runId)}
          >
            Evidence ledger
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentGovernanceRunEventsPath(projectId, document.id, runId)}
          >
            Events
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Ledger status</h3>
        <div className="buttonRow" role="toolbar" aria-label="Ledger status badges">
          <StatusChip tone={resolveArtifactTone(ledgerStatus.status)}>
            {ledgerStatus.status}
          </StatusChip>
          <StatusChip tone={resolveReadinessTone(ledgerStatus.readinessStatus)}>
            {ledgerStatus.readinessStatus}
          </StatusChip>
          <StatusChip tone={resolveGenerationTone(ledgerStatus.generationStatus)}>
            {ledgerStatus.generationStatus}
          </StatusChip>
          <StatusChip tone={resolveVerificationTone(ledgerStatus.ledgerVerificationStatus)}>
            {ledgerStatus.ledgerVerificationStatus}
          </StatusChip>
          <StatusChip tone={ledger.internalOnly ? "warning" : "neutral"}>
            {ledger.internalOnly ? "Internal-only" : "Internal state unknown"}
          </StatusChip>
        </div>
        <ul className="projectMetaList">
          <li>
            <span>Attempt count</span>
            <strong>{ledgerStatus.attemptCount}</strong>
          </li>
          <li>
            <span>Latest attempt ID</span>
            <strong>{ledger.latestAttempt?.id ?? "No attempt generated yet"}</strong>
          </li>
          <li>
            <span>Ready ledger ID</span>
            <strong>{ledgerStatus.readyLedgerId ?? "Not set"}</strong>
          </li>
          <li>
            <span>Latest ledger hash</span>
            <strong>{ledgerStatus.latestLedgerSha256 ?? "Not generated"}</strong>
          </li>
          <li>
            <span>Stream hash verification</span>
            <strong>
              {ledger.streamSha256
                ? ledger.hashMatches
                  ? "Verified"
                  : "Mismatch"
                : "Unavailable"}
            </strong>
          </li>
          <li>
            <span>Last verified at</span>
            <strong>{verifyStatus?.lastVerifiedAt ?? "Not recorded"}</strong>
          </li>
          <li>
            <span>Updated at</span>
            <strong>{new Date(ledgerStatus.updatedAt).toISOString()}</strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Diff summary</h3>
        {!ledgerSummary ? (
          <SectionState
            kind="degraded"
            title="Ledger summary unavailable"
            description={
              summaryResult.detail ??
              "Diff and impact summary could not be loaded for this run."
            }
          />
        ) : (
          <>
            <div className="buttonRow">
              <StatusChip tone={resolveVerificationTone(ledgerSummary.verificationStatus)}>
                {ledgerSummary.verificationStatus}
              </StatusChip>
              <StatusChip tone={ledgerSummary.hashChainValid ? "success" : "danger"}>
                {ledgerSummary.hashChainValid ? "Integrity chain valid" : "Integrity mismatch"}
              </StatusChip>
            </div>
            <ul className="projectMetaList">
              <li>
                <span>Row count</span>
                <strong>{ledgerSummary.rowCount}</strong>
              </li>
              <li>
                <span>Hash-chain head</span>
                <strong>{ledgerSummary.hashChainHead ?? "Unavailable"}</strong>
              </li>
              <li>
                <span>Override count</span>
                <strong>{ledgerSummary.overrideCount}</strong>
              </li>
              <li>
                <span>Assist references</span>
                <strong>{ledgerSummary.assistReferenceCount}</strong>
              </li>
            </ul>
            <div className="buttonRow">
              {Object.entries(ledgerSummary.categoryCounts).map(([category, count]) => (
                <StatusChip key={`category-${category}`} tone="neutral">
                  {category}: {count}
                </StatusChip>
              ))}
              {Object.entries(ledgerSummary.actionCounts).map(([action, count]) => (
                <StatusChip key={`action-${action}`} tone="neutral">
                  {action}: {count}
                </StatusChip>
              ))}
            </div>
          </>
        )}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Evidence entries</h3>
        <div className="buttonRow" role="toolbar" aria-label="Ledger entry controls">
          <Link
            className="secondaryButton"
            aria-current={viewFilter === "list" ? "page" : undefined}
            href={buildCurrentLedgerHref({ view: "list", cursor: 0 })}
          >
            List view
          </Link>
          <Link
            className="secondaryButton"
            aria-current={viewFilter === "timeline" ? "page" : undefined}
            href={buildCurrentLedgerHref({ view: "timeline", cursor: 0 })}
          >
            Timeline view
          </Link>
        </div>

        {!ledgerEntries ? (
          <SectionState
            kind="degraded"
            title="Ledger entries unavailable"
            description={
              entriesResult.detail ??
              "Entries could not be loaded for this controlled evidence ledger."
            }
          />
        ) : ledgerEntries.items.length === 0 ? (
          <SectionState
            kind="loading"
            title="No ledger entries"
            description="Ledger entries appear after successful evidence-ledger generation."
          />
        ) : viewFilter === "timeline" ? (
          <ol className="timelineList">
            {ledgerEntries.items.map((entry) => (
              <li key={entry.rowId}>
                <div className="buttonRow">
                  <StatusChip tone="neutral">#{entry.rowIndex + 1}</StatusChip>
                  <StatusChip tone={resolveActionPresentation(entry.actionType).tone}>
                    {resolveActionPresentation(entry.actionType).label}
                  </StatusChip>
                  <StatusChip tone="neutral">{entry.category}</StatusChip>
                </div>
                <p>
                  <strong>{entry.rowId}</strong>
                </p>
                <p className="ukde-muted">
                  finding {entry.findingId} · page {entry.pageIndex ?? "?"} · line {entry.lineId ?? "n/a"}
                </p>
                <p className="ukde-muted">{entry.decisionTimestamp ?? "No decision timestamp"}</p>
                <Link
                  className="secondaryButton"
                  href={buildCurrentLedgerHref({ rowId: entry.rowId })}
                >
                  Inspect row
                </Link>
              </li>
            ))}
          </ol>
        ) : (
          <table className="auditTable">
            <thead>
              <tr>
                <th scope="col">Row</th>
                <th scope="col">Finding</th>
                <th scope="col">Category</th>
                <th scope="col">Action</th>
                <th scope="col">Page</th>
                <th scope="col">Line</th>
                <th scope="col">Decision time</th>
                <th scope="col">Hash</th>
              </tr>
            </thead>
            <tbody>
              {ledgerEntries.items.map((entry) => (
                <tr key={entry.rowId}>
                  <td>
                    <Link href={buildCurrentLedgerHref({ rowId: entry.rowId })}>{entry.rowId}</Link>
                  </td>
                  <td>{entry.findingId}</td>
                  <td>{entry.category}</td>
                  <td>{resolveActionPresentation(entry.actionType).label}</td>
                  <td>{entry.pageIndex ?? "?"}</td>
                  <td>{entry.lineId ?? "n/a"}</td>
                  <td>{entry.decisionTimestamp ?? "n/a"}</td>
                  <td>{entry.rowHash}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {ledgerEntries ? (
          <div className="buttonRow">
            <span className="ukde-muted">
              Showing {ledgerEntries.items.length} of {ledgerEntries.totalCount} entries
            </span>
            {previousCursor !== null ? (
              <Link
                className="secondaryButton"
                href={buildCurrentLedgerHref({ cursor: previousCursor })}
              >
                Previous
              </Link>
            ) : null}
            {nextCursor !== null ? (
              <Link
                className="secondaryButton"
                href={buildCurrentLedgerHref({ cursor: nextCursor })}
              >
                Next
              </Link>
            ) : null}
          </div>
        ) : null}
      </section>

      {rowIdFilter ? (
        <section className="sectionCard ukde-panel">
          <h3>Row detail</h3>
          {!ledgerEntries ? (
            <SectionState
              kind="degraded"
              title="Row detail unavailable"
              description="Ledger entries must load before row detail can be resolved."
            />
          ) : selectedLedgerRow ? (
            <>
              <ul className="projectMetaList">
                <li>
                  <span>Row ID</span>
                  <strong>{selectedLedgerRow.rowId}</strong>
                </li>
                <li>
                  <span>Row hash</span>
                  <strong>{selectedLedgerRow.rowHash}</strong>
                </li>
                <li>
                  <span>Previous hash</span>
                  <strong>{selectedLedgerRow.prevHash}</strong>
                </li>
                <li>
                  <span>Actor</span>
                  <strong>{selectedLedgerRow.actorUserId ?? "system"}</strong>
                </li>
                <li>
                  <span>Override reason</span>
                  <strong>{selectedLedgerRow.overrideReason ?? "Not set"}</strong>
                </li>
              </ul>
              <h4>Before/after references</h4>
              <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {JSON.stringify(
                  {
                    beforeTextRef: selectedLedgerRow.beforeTextRef,
                    afterTextRef: selectedLedgerRow.afterTextRef
                  },
                  null,
                  2
                )}
              </pre>
              <h4>Detector evidence</h4>
              <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {JSON.stringify(selectedLedgerRow.detectorEvidence, null, 2)}
              </pre>
            </>
          ) : (
            <SectionState
              kind="degraded"
              title="Selected row is outside current view"
              description="Adjust pagination or view mode to load the selected row in the current result set."
            />
          )}
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h3>Verification history</h3>
        <div className="buttonRow" role="toolbar" aria-label="Ledger verification controls">
          <StatusChip
            tone={resolveVerificationTone(
              verifyStatus?.verificationStatus ?? ledgerStatus.ledgerVerificationStatus
            )}
          >
            {verifyStatus?.verificationStatus ?? ledgerStatus.ledgerVerificationStatus}
          </StatusChip>
          {isAdmin ? (
            <form action={requestVerificationAction}>
              <button className="secondaryButton" type="submit">
                Trigger re-verification
              </button>
            </form>
          ) : (
            <StatusChip tone="neutral">Read-only auditor mode</StatusChip>
          )}
        </div>

        {!verifyRuns ? (
          <SectionState
            kind="degraded"
            title="Verification history unavailable"
            description={
              verifyRunsResult.detail ??
              "Verification attempt history could not be loaded for this run."
            }
          />
        ) : verifyRuns.items.length === 0 ? (
          <SectionState
            kind="loading"
            title="No verification attempts yet"
            description="Verification history appears when ledger verification is queued or completed."
          />
        ) : (
          <table className="auditTable">
            <thead>
              <tr>
                <th scope="col">Attempt</th>
                <th scope="col">Status</th>
                <th scope="col">Result</th>
                <th scope="col">Created</th>
                <th scope="col">Finished</th>
              </tr>
            </thead>
            <tbody>
              {verifyRuns.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <Link href={buildCurrentLedgerHref({ verificationRunId: item.id })}>
                      {item.id}
                    </Link>
                  </td>
                  <td>{item.status}</td>
                  <td>{item.verificationResult ?? "n/a"}</td>
                  <td>{item.createdAt}</td>
                  <td>{item.finishedAt ?? "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {verificationRunIdFilter ? (
          !selectedVerificationRun ? (
            <SectionState
              kind="degraded"
              title="Verification attempt detail unavailable"
              description="The selected verification attempt could not be loaded."
            />
          ) : (
            <>
              <h4>Selected verification attempt</h4>
              <ul className="projectMetaList">
                <li>
                  <span>Attempt ID</span>
                  <strong>{selectedVerificationRun.id}</strong>
                </li>
                <li>
                  <span>Status</span>
                  <strong>{selectedVerificationRun.status}</strong>
                </li>
                <li>
                  <span>Result</span>
                  <strong>{selectedVerificationRun.verificationResult ?? "n/a"}</strong>
                </li>
                <li>
                  <span>Failure reason</span>
                  <strong>{selectedVerificationRun.failureReason ?? "n/a"}</strong>
                </li>
                <li>
                  <span>Started</span>
                  <strong>{selectedVerificationRun.startedAt ?? "n/a"}</strong>
                </li>
                <li>
                  <span>Finished</span>
                  <strong>{selectedVerificationRun.finishedAt ?? "n/a"}</strong>
                </li>
              </ul>
              {selectedVerificationRun.resultJson ? (
                <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                  {JSON.stringify(selectedVerificationRun.resultJson, null, 2)}
                </pre>
              ) : null}
              {isAdmin && canCancelVerificationRun(selectedVerificationRun.status) ? (
                <form action={cancelVerificationAction} className="buttonRow">
                  <input
                    name="verificationRunId"
                    type="hidden"
                    value={selectedVerificationRun.id}
                  />
                  <button className="secondaryButton" type="submit">
                    Cancel verification attempt
                  </button>
                </form>
              ) : null}
            </>
          )
        ) : null}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Attempt lineage</h3>
        {ledger.overview.ledgerAttempts.length === 0 ? (
          <SectionState
            kind="loading"
            title="Ledger generation not started"
            description="No controlled ledger attempt exists yet. This state is expected until evidence-ledger generation runs."
          />
        ) : (
          <ul className="projectMetaList">
            {ledger.overview.ledgerAttempts.map((attempt) => (
              <li key={attempt.id}>
                <span>{attempt.id}</span>
                <strong>
                  attempt {attempt.attemptNumber} · {attempt.status}
                  {" · "}
                  source hash {attempt.sourceReviewSnapshotSha256}
                </strong>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
