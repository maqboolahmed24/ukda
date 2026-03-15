import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type {
  GovernanceArtifactStatus,
  GovernanceGenerationStatus,
  GovernanceReadinessStatus
} from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import {
  getProjectDocument,
  getProjectDocumentGovernanceRunLedgerStatus,
  getProjectDocumentGovernanceRunManifest,
  getProjectDocumentGovernanceRunManifestHash,
  getProjectDocumentGovernanceRunManifestStatus,
  listProjectDocumentGovernanceRunManifestEntries
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

function parseOptionalPositiveInt(value: string | undefined): number | undefined {
  if (typeof value !== "string" || value.trim().length === 0) {
    return undefined;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 1) {
    return undefined;
  }
  return parsed;
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

function buildManifestFilterHref(
  projectId: string,
  documentId: string,
  runId: string,
  filters: {
    category?: string;
    entryId?: string;
    page?: number;
    reviewState?: string;
    from?: string;
    to?: string;
    cursor?: number;
    limit?: number;
  }
): string {
  const params = new URLSearchParams();
  if (filters.category) {
    params.set("category", filters.category);
  }
  if (filters.entryId) {
    params.set("entryId", filters.entryId);
  }
  if (typeof filters.page === "number") {
    params.set("page", String(filters.page));
  }
  if (filters.reviewState) {
    params.set("reviewState", filters.reviewState);
  }
  if (filters.from) {
    params.set("from", filters.from);
  }
  if (filters.to) {
    params.set("to", filters.to);
  }
  if (typeof filters.cursor === "number" && filters.cursor > 0) {
    params.set("cursor", String(filters.cursor));
  }
  if (typeof filters.limit === "number" && filters.limit !== 100) {
    params.set("limit", String(filters.limit));
  }
  const query = params.toString();
  const basePath = projectDocumentGovernanceRunManifestPath(
    projectId,
    documentId,
    runId
  );
  return query.length > 0 ? `${basePath}?${query}` : basePath;
}

export default async function ProjectDocumentGovernanceRunManifestPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string; runId: string }>;
  searchParams: Promise<{
    category?: string;
    page?: string;
    reviewState?: string;
    from?: string;
    to?: string;
    entryId?: string;
    cursor?: string;
    limit?: string;
  }>;
}>) {
  const { projectId, documentId, runId } = await params;
  const query = await searchParams;

  const categoryFilter = parseOptionalText(query.category);
  const reviewStateFilter = parseOptionalText(query.reviewState);
  const fromFilter = parseOptionalText(query.from);
  const toFilter = parseOptionalText(query.to);
  const entryIdFilter = parseOptionalText(query.entryId);
  const pageFilter = parseOptionalPositiveInt(query.page);
  const cursorFilter = parseCursor(query.cursor);
  const limitFilter = parseLimit(query.limit);

  const [
    documentResult,
    manifestResult,
    statusResult,
    hashResult,
    entriesResult,
    ledgerStatusResult
  ] =
    await Promise.all([
      getProjectDocument(projectId, documentId),
      getProjectDocumentGovernanceRunManifest(projectId, documentId, runId),
      getProjectDocumentGovernanceRunManifestStatus(projectId, documentId, runId),
      getProjectDocumentGovernanceRunManifestHash(projectId, documentId, runId),
      listProjectDocumentGovernanceRunManifestEntries(projectId, documentId, runId, {
        category: categoryFilter,
        page: pageFilter,
        reviewState: reviewStateFilter,
        from: fromFilter,
        to: toFilter,
        cursor: cursorFilter,
        limit: limitFilter
      }),
      getProjectDocumentGovernanceRunLedgerStatus(projectId, documentId, runId)
    ]);

  if (!documentResult.ok || !manifestResult.ok || !statusResult.ok) {
    if (
      documentResult.status === 404 ||
      manifestResult.status === 404 ||
      statusResult.status === 404
    ) {
      notFound();
    }
    if (
      documentResult.status === 403 ||
      manifestResult.status === 403 ||
      statusResult.status === 403
    ) {
      redirect(projectsPath);
    }
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Manifest route unavailable"
          description={
            manifestResult.detail ??
            statusResult.detail ??
            documentResult.detail ??
            "Manifest lineage and status could not be loaded."
          }
        />
      </main>
    );
  }

  const document = documentResult.data;
  const manifest = manifestResult.data;
  const manifestStatus = statusResult.data;
  if (!document || !manifest || !manifestStatus) {
    notFound();
  }

  const manifestHash = hashResult.ok ? hashResult.data : null;
  const manifestEntries = entriesResult.ok ? entriesResult.data : null;
  const previousCursor =
    manifestEntries && cursorFilter > 0
      ? Math.max(0, cursorFilter - limitFilter)
      : null;
  const nextCursor = manifestEntries?.nextCursor ?? null;
  const selectedEntry =
    manifestEntries?.items.find((entry) => entry.entryId === entryIdFilter) ?? null;
  const canViewLedger = Boolean(ledgerStatusResult.ok && ledgerStatusResult.data);

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Governance manifest</p>
        <h2>{document.originalFilename}</h2>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentGovernancePath(projectId, document.id, {
              tab: "manifest",
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
            aria-current="page"
            href={projectDocumentGovernanceRunManifestPath(projectId, document.id, runId)}
          >
            Manifest
          </Link>
          {canViewLedger ? (
            <Link
              className="secondaryButton"
              href={projectDocumentGovernanceRunLedgerPath(projectId, document.id, runId)}
            >
              Evidence ledger
            </Link>
          ) : null}
          <Link
            className="secondaryButton"
            href={projectDocumentGovernanceRunEventsPath(projectId, document.id, runId)}
          >
            Events
          </Link>
        </div>
        {!canViewLedger ? (
          <p className="ukde-muted">
            Controlled evidence-ledger detail is restricted to administrator and
            auditor roles.
          </p>
        ) : null}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Manifest status</h3>
        <div className="buttonRow">
          <StatusChip tone={resolveArtifactTone(manifestStatus.status)}>
            {manifestStatus.status}
          </StatusChip>
          <StatusChip tone={resolveReadinessTone(manifestStatus.readinessStatus)}>
            {manifestStatus.readinessStatus}
          </StatusChip>
          <StatusChip tone={resolveGenerationTone(manifestStatus.generationStatus)}>
            {manifestStatus.generationStatus}
          </StatusChip>
          <StatusChip tone={manifest.internalOnly ? "warning" : "neutral"}>
            {manifest.internalOnly ? "Internal-only" : "Internal state unknown"}
          </StatusChip>
          <StatusChip tone={manifest.notExportApproved ? "warning" : "neutral"}>
            {manifest.notExportApproved ? "Not export-approved" : "Export-approved"}
          </StatusChip>
        </div>
        <ul className="projectMetaList">
          <li>
            <span>Attempt count</span>
            <strong>{manifestStatus.attemptCount}</strong>
          </li>
          <li>
            <span>Latest attempt ID</span>
            <strong>{manifest.latestAttempt?.id ?? "No attempt generated yet"}</strong>
          </li>
          <li>
            <span>Ready manifest ID</span>
            <strong>{manifestStatus.readyManifestId ?? "Not set"}</strong>
          </li>
          <li>
            <span>Latest manifest hash</span>
            <strong>{manifestStatus.latestManifestSha256 ?? "Not generated"}</strong>
          </li>
          <li>
            <span>Stream hash verification</span>
            <strong>
              {manifestHash ? (
                manifestHash.hashMatches ? (
                  "Verified"
                ) : (
                  "Mismatch"
                )
              ) : (
                "Unavailable"
              )}
            </strong>
          </li>
          <li>
            <span>Updated at</span>
            <strong>{new Date(manifestStatus.updatedAt).toISOString()}</strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Manifest entries</h3>
        <p className="ukde-muted">
          Screening-safe entries are filterable by category, page, review state, and
          decision timestamp. This view is internal-only and not export-approved.
        </p>
        <form
          className="buttonRow governanceFilterForm"
          method="get"
          action={projectDocumentGovernanceRunManifestPath(projectId, document.id, runId)}
        >
          <label>
            <span className="ukde-muted">Category</span>
            <input name="category" placeholder="Category" defaultValue={categoryFilter} />
          </label>
          <label>
            <span className="ukde-muted">Page</span>
            <input
              name="page"
              placeholder="Page"
              inputMode="numeric"
              defaultValue={pageFilter ? String(pageFilter) : ""}
            />
          </label>
          <label>
            <span className="ukde-muted">Review state</span>
            <input
              name="reviewState"
              placeholder="Review state"
              defaultValue={reviewStateFilter}
            />
          </label>
          <label>
            <span className="ukde-muted">From</span>
            <input name="from" placeholder="YYYY-MM-DD" defaultValue={fromFilter} />
          </label>
          <label>
            <span className="ukde-muted">To</span>
            <input name="to" placeholder="YYYY-MM-DD" defaultValue={toFilter} />
          </label>
          <label>
            <span className="ukde-muted">Limit</span>
            <input
              name="limit"
              placeholder="Limit"
              inputMode="numeric"
              defaultValue={String(limitFilter)}
            />
          </label>
          <button type="submit" className="secondaryButton">
            Apply filters
          </button>
          <Link
            className="secondaryButton"
            href={projectDocumentGovernanceRunManifestPath(projectId, document.id, runId)}
          >
            Clear
          </Link>
        </form>
        {!manifestEntries ? (
          <SectionState
            kind="degraded"
            title="Manifest entries unavailable"
            description={
              entriesResult.detail ??
              "Entries could not be loaded for this governance manifest."
            }
          />
        ) : manifestEntries.items.length === 0 ? (
          <SectionState
            kind="loading"
            title="No entries for current filters"
            description="Adjust filters or clear them to inspect the full screening-safe manifest entry set."
          />
        ) : (
          <>
            <table className="auditTable">
              <thead>
                <tr>
                  <th scope="col">Entry</th>
                  <th scope="col">Action</th>
                  <th scope="col">Category</th>
                  <th scope="col">Page</th>
                  <th scope="col">Line</th>
                  <th scope="col">Review state</th>
                  <th scope="col">Decision time</th>
                </tr>
              </thead>
              <tbody>
                {manifestEntries.items.map((entry) => (
                  <tr key={entry.entryId}>
                    <td>
                      <Link
                        href={buildManifestFilterHref(projectId, document.id, runId, {
                          category: categoryFilter,
                          entryId: entry.entryId,
                          page: pageFilter,
                          reviewState: reviewStateFilter,
                          from: fromFilter,
                          to: toFilter,
                          cursor: cursorFilter > 0 ? cursorFilter : undefined,
                          limit: limitFilter
                        })}
                      >
                        {entry.entryId}
                      </Link>
                    </td>
                    <td>
                      <StatusChip tone={resolveActionPresentation(entry.appliedAction).tone}>
                        {resolveActionPresentation(entry.appliedAction).label}
                      </StatusChip>
                    </td>
                    <td>{entry.category}</td>
                    <td>{entry.pageIndex ?? "?"}</td>
                    <td>{entry.lineId ?? "n/a"}</td>
                    <td>{entry.reviewState}</td>
                    <td>{entry.decisionTimestamp ?? "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="buttonRow">
              <span className="ukde-muted">
                Showing {manifestEntries.items.length} of {manifestEntries.totalCount} entries
              </span>
              {previousCursor !== null ? (
                <Link
                  className="secondaryButton"
                  href={buildManifestFilterHref(projectId, document.id, runId, {
                    category: categoryFilter,
                    entryId: entryIdFilter,
                    page: pageFilter,
                    reviewState: reviewStateFilter,
                    from: fromFilter,
                    to: toFilter,
                    cursor: previousCursor,
                    limit: limitFilter
                  })}
                >
                  Previous
                </Link>
              ) : null}
              {nextCursor !== null ? (
                <Link
                  className="secondaryButton"
                  href={buildManifestFilterHref(projectId, document.id, runId, {
                    category: categoryFilter,
                    entryId: entryIdFilter,
                    page: pageFilter,
                    reviewState: reviewStateFilter,
                    from: fromFilter,
                    to: toFilter,
                    cursor: nextCursor,
                    limit: limitFilter
                  })}
                >
                  Next
                </Link>
              ) : null}
            </div>
          </>
        )}
      </section>

      {entryIdFilter ? (
        <section className="sectionCard ukde-panel">
          <h3>Entry detail</h3>
          {!manifestEntries ? (
            <SectionState
              kind="degraded"
              title="Entry detail unavailable"
              description="Manifest entries must load before an entry detail can be resolved."
            />
          ) : selectedEntry ? (
            <ul className="projectMetaList">
              <li>
                <span>Entry ID</span>
                <strong>{selectedEntry.entryId}</strong>
              </li>
              <li>
                <span>Action</span>
                <strong>{resolveActionPresentation(selectedEntry.appliedAction).label}</strong>
              </li>
              <li>
                <span>Category</span>
                <strong>{selectedEntry.category}</strong>
              </li>
              <li>
                <span>Page / line</span>
                <strong>
                  {selectedEntry.pageIndex ?? "?"} / {selectedEntry.lineId ?? "n/a"}
                </strong>
              </li>
              <li>
                <span>Review state</span>
                <strong>{selectedEntry.reviewState}</strong>
              </li>
              <li>
                <span>Decision timestamp</span>
                <strong>{selectedEntry.decisionTimestamp ?? "n/a"}</strong>
              </li>
              <li>
                <span>Policy snapshot hash</span>
                <strong>{selectedEntry.policySnapshotHash ?? "Not set"}</strong>
              </li>
            </ul>
          ) : (
            <SectionState
              kind="degraded"
              title="Selected entry is outside current filter window"
              description="Adjust filters or pagination to load the selected entry in the current result set."
            />
          )}
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h3>Raw manifest JSON</h3>
        {!manifest.manifestJson ? (
          <SectionState
            kind="degraded"
            title="Raw manifest unavailable"
            description="No manifest JSON payload is available yet for this run."
          />
        ) : (
          <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {JSON.stringify(manifest.manifestJson, null, 2)}
          </pre>
        )}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Attempt lineage</h3>
        {manifest.overview.manifestAttempts.length === 0 ? (
          <SectionState
            kind="loading"
            title="Manifest generation not started"
            description="No manifest attempt exists yet. This state is expected before downstream artefact generation succeeds."
          />
        ) : (
          <ul className="projectMetaList">
            {manifest.overview.manifestAttempts.map((attempt) => (
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
