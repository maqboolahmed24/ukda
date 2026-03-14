"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  startTransition,
  useEffect,
  useMemo,
  useState
} from "react";
import type {
  DocumentPreprocessPageResult,
  DocumentPreprocessRun
} from "@ukde/contracts";
import {
  DetailsDrawer,
  InlineAlert,
  ModalDialog,
  SectionState,
  StatusChip
} from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";
import { projectDocumentPageImagePath } from "../lib/document-page-image";
import {
  projectDocumentPreprocessingComparePath,
  projectDocumentPreprocessingQualityPath,
  projectDocumentViewerPath
} from "../lib/routes";

type ProfileId = "AGGRESSIVE" | "BALANCED" | "BLEED_THROUGH" | "CONSERVATIVE";
type RerunScope = "FULL_DOCUMENT" | "PAGE_SUBSET";

const ADVANCED_RISK_CONFIRMATION_COPY =
  "Advanced full-document preprocessing can remove faint handwriting details. Confirm only when stronger cleanup is necessary and compare review will follow.";

const PROFILE_DESCRIPTIONS: Record<ProfileId, string> = {
  BALANCED: "Safe default profile for deterministic grayscale cleanup.",
  CONSERVATIVE: "Lower-intensity cleanup for fragile scans and faint handwriting.",
  AGGRESSIVE: "Stronger cleanup with optional adaptive binarization.",
  BLEED_THROUGH:
    "Advanced show-through reduction; best results use paired recto/verso pages."
};

interface DocumentQualityTriageFilters {
  blurMax?: number | null;
  compareBaseRunId?: string | null;
  failedOnly?: boolean;
  runId?: string | null;
  skewMax?: number | null;
  skewMin?: number | null;
  warning?: string | null;
}

interface DocumentQualityTriageSurfaceProps {
  canMutate: boolean;
  documentId: string;
  items: DocumentPreprocessPageResult[];
  projectId: string;
  run: DocumentPreprocessRun | null;
  runs: DocumentPreprocessRun[];
  searchState: DocumentQualityTriageFilters;
}

interface QualityRow {
  blurScore: number | null;
  dpiEstimate: number | null;
  item: DocumentPreprocessPageResult;
  skewDeg: number | null;
}

function toMetricNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return null;
}

function formatMetric(value: number | null, digits = 2): string {
  if (value === null) {
    return "N/A";
  }
  return value.toFixed(digits);
}

function parseInputNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number.parseFloat(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function resolveTone(status: string): "danger" | "neutral" | "success" | "warning" {
  if (status === "SUCCEEDED" || status === "PASS") {
    return "success";
  }
  if (status === "FAILED" || status === "BLOCKED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  return "warning";
}

function normalizeProfileId(value: string | undefined): ProfileId {
  if (
    value === "CONSERVATIVE" ||
    value === "AGGRESSIVE" ||
    value === "BLEED_THROUGH"
  ) {
    return value;
  }
  return "BALANCED";
}

function sortByTriagePriority(a: QualityRow, b: QualityRow): number {
  const blockedA = a.item.qualityGateStatus === "BLOCKED" ? 1 : 0;
  const blockedB = b.item.qualityGateStatus === "BLOCKED" ? 1 : 0;
  if (blockedA !== blockedB) {
    return blockedB - blockedA;
  }
  const failedA = a.item.status !== "SUCCEEDED" ? 1 : 0;
  const failedB = b.item.status !== "SUCCEEDED" ? 1 : 0;
  if (failedA !== failedB) {
    return failedB - failedA;
  }
  if (a.item.warningsJson.length !== b.item.warningsJson.length) {
    return b.item.warningsJson.length - a.item.warningsJson.length;
  }
  if (a.blurScore !== null && b.blurScore !== null && a.blurScore !== b.blurScore) {
    return a.blurScore - b.blurScore;
  }
  return a.item.pageIndex - b.item.pageIndex;
}

export function DocumentQualityTriageSurface({
  canMutate,
  documentId,
  items,
  projectId,
  run,
  runs,
  searchState
}: DocumentQualityTriageSurfaceProps) {
  const router = useRouter();
  const pathname = usePathname();

  const [warningFilter, setWarningFilter] = useState(searchState.warning ?? "");
  const [skewMin, setSkewMin] = useState<number | null>(searchState.skewMin ?? null);
  const [skewMax, setSkewMax] = useState<number | null>(searchState.skewMax ?? null);
  const [blurMax, setBlurMax] = useState<number | null>(searchState.blurMax ?? null);
  const [failedOnly, setFailedOnly] = useState(Boolean(searchState.failedOnly));
  const [compareBaseRunId, setCompareBaseRunId] = useState<string | null>(
    searchState.compareBaseRunId ?? null
  );

  const [selectedPageIds, setSelectedPageIds] = useState<Set<string>>(new Set());
  const [detailPageId, setDetailPageId] = useState<string | null>(null);

  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(1);
  const [rerunScope, setRerunScope] = useState<RerunScope>("FULL_DOCUMENT");
  const [profileId, setProfileId] = useState<ProfileId>(
    normalizeProfileId(run?.profileId)
  );
  const [advancedRiskConfirmed, setAdvancedRiskConfirmed] = useState(false);
  const [advancedRiskAcknowledgement, setAdvancedRiskAcknowledgement] =
    useState("");
  const [rerunPending, setRerunPending] = useState(false);
  const [rerunError, setRerunError] = useState<string | null>(null);

  const rows = useMemo<QualityRow[]>(
    () =>
      items.map((item) => ({
        item,
        skewDeg: toMetricNumber(item.metricsJson.skew_angle_deg),
        blurScore: toMetricNumber(item.metricsJson.blur_score),
        dpiEstimate: toMetricNumber(item.metricsJson.dpi_estimate)
      })),
    [items]
  );

  const warningOptions = useMemo(() => {
    const values = new Set<string>();
    for (const row of rows) {
      for (const warning of row.item.warningsJson) {
        values.add(warning);
      }
    }
    return Array.from(values).sort((a, b) => a.localeCompare(b));
  }, [rows]);

  const filteredRows = useMemo(() => {
    const filtered = rows.filter((row) => {
      if (warningFilter && !row.item.warningsJson.includes(warningFilter)) {
        return false;
      }
      if (typeof skewMin === "number" && (row.skewDeg === null || row.skewDeg < skewMin)) {
        return false;
      }
      if (typeof skewMax === "number" && (row.skewDeg === null || row.skewDeg > skewMax)) {
        return false;
      }
      if (typeof blurMax === "number" && (row.blurScore === null || row.blurScore > blurMax)) {
        return false;
      }
      if (
        failedOnly &&
        row.item.status === "SUCCEEDED" &&
        row.item.qualityGateStatus !== "BLOCKED"
      ) {
        return false;
      }
      return true;
    });
    filtered.sort(sortByTriagePriority);
    return filtered;
  }, [blurMax, failedOnly, rows, skewMax, skewMin, warningFilter]);

  const filteredPageIds = useMemo(
    () => filteredRows.map((row) => row.item.pageId),
    [filteredRows]
  );
  const selectedCount = selectedPageIds.size;
  const filteredSelectedCount = useMemo(
    () => filteredPageIds.filter((pageId) => selectedPageIds.has(pageId)).length,
    [filteredPageIds, selectedPageIds]
  );
  const allFilteredSelected =
    filteredPageIds.length > 0 && filteredSelectedCount === filteredPageIds.length;

  const activeDetailRow = useMemo(
    () => rows.find((row) => row.item.pageId === detailPageId) ?? null,
    [detailPageId, rows]
  );

  const compareBaseRun = useMemo(() => {
    if (!run) {
      return null;
    }
    const preferred =
      typeof compareBaseRunId === "string" && compareBaseRunId !== run.id
        ? runs.find((candidate) => candidate.id === compareBaseRunId) ?? null
        : null;
    if (preferred) {
      return preferred;
    }
    return runs.find((candidate) => candidate.id !== run.id) ?? null;
  }, [compareBaseRunId, run, runs]);

  const compareHref =
    run && compareBaseRun
      ? projectDocumentPreprocessingComparePath(
          projectId,
          documentId,
          compareBaseRun.id,
          run.id
        )
      : null;
  const advancedRiskRequired =
    rerunScope === "FULL_DOCUMENT" &&
    (profileId === "AGGRESSIVE" || profileId === "BLEED_THROUGH");

  useEffect(() => {
    setSelectedPageIds(new Set());
    setDetailPageId(null);
    setRerunScope("FULL_DOCUMENT");
    setProfileId(normalizeProfileId(run?.profileId));
    setAdvancedRiskConfirmed(false);
    setAdvancedRiskAcknowledgement("");
    setRerunError(null);
  }, [run?.id]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const setParam = (key: string, value: string | null) => {
      if (value === null || value.length === 0) {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    };

    setParam("warning", warningFilter || null);
    setParam("skewMin", skewMin === null ? null : String(skewMin));
    setParam("skewMax", skewMax === null ? null : String(skewMax));
    setParam("blurMax", blurMax === null ? null : String(blurMax));
    setParam("failedOnly", failedOnly ? "1" : null);
    setParam("compareBaseRunId", compareBaseRunId ?? null);
    if (run?.id) {
      setParam("runId", run.id);
    }

    const nextUrl = `${pathname}${params.toString() ? `?${params.toString()}` : ""}`;
    const currentUrl = `${window.location.pathname}${window.location.search}`;
    if (nextUrl !== currentUrl) {
      window.history.replaceState(window.history.state, "", nextUrl);
    }
  }, [
    blurMax,
    compareBaseRunId,
    failedOnly,
    pathname,
    run?.id,
    skewMax,
    skewMin,
    warningFilter
  ]);

  useEffect(() => {
    if (!advancedRiskRequired) {
      setAdvancedRiskConfirmed(false);
      setAdvancedRiskAcknowledgement("");
    }
  }, [advancedRiskRequired]);

  function togglePageSelection(pageId: string) {
    setSelectedPageIds((current) => {
      const next = new Set(current);
      if (next.has(pageId)) {
        next.delete(pageId);
      } else {
        next.add(pageId);
      }
      return next;
    });
  }

  function selectFilteredPages() {
    setSelectedPageIds((current) => {
      const next = new Set(current);
      for (const pageId of filteredPageIds) {
        next.add(pageId);
      }
      return next;
    });
  }

  function clearSelection() {
    setSelectedPageIds(new Set());
  }

  function toggleAllFiltered(checked: boolean) {
    setSelectedPageIds((current) => {
      const next = new Set(current);
      if (checked) {
        for (const pageId of filteredPageIds) {
          next.add(pageId);
        }
      } else {
        for (const pageId of filteredPageIds) {
          next.delete(pageId);
        }
      }
      return next;
    });
  }

  function openWizard() {
    if (!run) {
      return;
    }
    setWizardOpen(true);
    setWizardStep(1);
    setRerunScope(selectedCount > 0 ? "PAGE_SUBSET" : "FULL_DOCUMENT");
    setProfileId(normalizeProfileId(run.profileId));
    setAdvancedRiskConfirmed(false);
    setAdvancedRiskAcknowledgement("");
    setRerunError(null);
  }

  async function queueRerun() {
    if (!run) {
      return;
    }
    const targetPageIds =
      rerunScope === "PAGE_SUBSET" ? Array.from(selectedPageIds) : [];
    if (rerunScope === "PAGE_SUBSET" && targetPageIds.length === 0) {
      setRerunError("Selected-pages scope requires at least one selected page.");
      return;
    }
    if (advancedRiskRequired && !advancedRiskConfirmed) {
      setRerunError("Confirm advanced full-document risk posture before queueing rerun.");
      return;
    }

    setRerunPending(true);
    setRerunError(null);
    const result = await requestBrowserApi<{ id: string }>({
      method: "POST",
      path: `/projects/${projectId}/documents/${documentId}/preprocess-runs/${run.id}/rerun`,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profileId,
        targetPageIds: rerunScope === "PAGE_SUBSET" ? targetPageIds : undefined,
        advancedRiskConfirmed: advancedRiskRequired
          ? advancedRiskConfirmed
          : undefined,
        advancedRiskAcknowledgement: advancedRiskRequired
          ? advancedRiskAcknowledgement.trim() || ADVANCED_RISK_CONFIRMATION_COPY
          : undefined
      })
    });
    setRerunPending(false);

    if (!result.ok || !result.data) {
      setRerunError(result.detail ?? "Preprocessing rerun request failed.");
      return;
    }

    const selectedPageIndex =
      rerunScope === "PAGE_SUBSET"
        ? rows.find((row) => targetPageIds.includes(row.item.pageId))?.item.pageIndex
        : undefined;
    const reviewPath = projectDocumentPreprocessingComparePath(
      projectId,
      documentId,
      run.id,
      result.data.id,
      {
        page:
          typeof selectedPageIndex === "number" && Number.isFinite(selectedPageIndex)
            ? selectedPageIndex + 1
            : 1,
        viewerMode: "preprocessed",
        viewerRunId: result.data.id
      }
    );
    setWizardOpen(false);
    startTransition(() => {
      router.push(reviewPath);
      router.refresh();
    });
  }

  const activeFilterCopy: string[] = [];
  if (warningFilter) {
    activeFilterCopy.push(`Warning: ${warningFilter}`);
  }
  if (skewMin !== null || skewMax !== null) {
    activeFilterCopy.push(
      `Skew: ${skewMin === null ? "any" : skewMin} to ${skewMax === null ? "any" : skewMax}`
    );
  }
  if (blurMax !== null) {
    activeFilterCopy.push(`Blur <= ${blurMax}`);
  }
  if (failedOnly) {
    activeFilterCopy.push("Failed-only");
  }

  return (
    <>
      {!run ? (
        <SectionState
          kind="empty"
          title="No selected run"
          description="Select a preprocessing run to open quality triage."
        />
      ) : (
        <>
          <section className="qualityTriageControls">
            <label>
              Run
              <select
                value={run.id}
                onChange={(event) => {
                  const nextRunId = event.target.value;
                  startTransition(() => {
                    router.push(
                      projectDocumentPreprocessingQualityPath(projectId, documentId, {
                        runId: nextRunId,
                        warning: warningFilter || undefined,
                        skewMin,
                        skewMax,
                        blurMax,
                        failedOnly,
                        compareBaseRunId: compareBaseRunId ?? undefined
                      })
                    );
                  });
                }}
              >
                {runs.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.id} · {candidate.profileId} · {candidate.status}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Warning type
              <select
                value={warningFilter}
                onChange={(event) => setWarningFilter(event.target.value)}
              >
                <option value="">Any warning</option>
                {warningOptions.map((warning) => (
                  <option key={warning} value={warning}>
                    {warning}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Skew min
              <input
                type="number"
                step="0.01"
                value={skewMin ?? ""}
                onChange={(event) =>
                  setSkewMin(parseInputNumber(event.target.value))
                }
                placeholder="0.00"
              />
            </label>
            <label>
              Skew max
              <input
                type="number"
                step="0.01"
                value={skewMax ?? ""}
                onChange={(event) =>
                  setSkewMax(parseInputNumber(event.target.value))
                }
                placeholder="3.00"
              />
            </label>
            <label>
              Blur threshold
              <input
                type="number"
                step="0.01"
                value={blurMax ?? ""}
                onChange={(event) =>
                  setBlurMax(parseInputNumber(event.target.value))
                }
                placeholder="0.35"
              />
            </label>
            <label className="qualityTriageCheckbox">
              <input
                type="checkbox"
                checked={failedOnly}
                onChange={(event) => setFailedOnly(event.target.checked)}
              />
              Failed only
            </label>
            <label>
              Compare base
              <select
                value={compareBaseRunId ?? ""}
                onChange={(event) =>
                  setCompareBaseRunId(event.target.value || null)
                }
              >
                <option value="">Auto select base</option>
                {runs
                  .filter((candidate) => candidate.id !== run.id)
                  .map((candidate) => (
                    <option key={candidate.id} value={candidate.id}>
                      {candidate.id} · {candidate.profileId} · {candidate.status}
                    </option>
                  ))}
              </select>
            </label>
          </section>

          {activeFilterCopy.length > 0 ? (
            <p className="qualityTriageActiveFilters">{activeFilterCopy.join(" · ")}</p>
          ) : null}

          <section className="qualityTriageActionBar">
            <p className="ukde-muted">
              {filteredRows.length} page{filteredRows.length === 1 ? "" : "s"} in triage queue ·{" "}
              {selectedCount} selected
            </p>
            <div className="buttonRow">
              {canMutate ? (
                <button
                  className="secondaryButton"
                  type="button"
                  onClick={selectFilteredPages}
                  disabled={filteredRows.length === 0}
                >
                  Select filtered
                </button>
              ) : null}
              {canMutate ? (
                <button
                  className="secondaryButton"
                  type="button"
                  onClick={clearSelection}
                  disabled={selectedCount === 0}
                >
                  Clear selection
                </button>
              ) : null}
              {compareHref ? (
                <Link className="secondaryButton" href={compareHref}>
                  Compare runs
                </Link>
              ) : null}
              {canMutate ? (
                <button
                  className="secondaryButton"
                  type="button"
                  onClick={openWizard}
                  disabled={rerunPending}
                >
                  Re-run preprocessing
                </button>
              ) : null}
            </div>
          </section>

          {filteredRows.length === 0 ? (
            <SectionState
              kind="empty"
              title="No pages match current triage filters"
              description="Adjust warning/skew/blur/failed filters to restore queue rows."
            />
          ) : (
            <div className="qualityTriageTableWrap">
              <table className="ukde-data-table qualityTriageTable">
                <caption className="ukde-visually-hidden">
                  Document quality triage rows
                </caption>
                <thead>
                  <tr>
                    {canMutate ? (
                      <th scope="col">
                        <input
                          aria-label="Select all filtered pages"
                          type="checkbox"
                          checked={allFilteredSelected}
                          onChange={(event) => toggleAllFiltered(event.target.checked)}
                        />
                      </th>
                    ) : null}
                    <th scope="col">Page</th>
                    <th scope="col">Warnings</th>
                    <th scope="col">Skew</th>
                    <th scope="col">Blur score</th>
                    <th scope="col">DPI</th>
                    <th scope="col">Status</th>
                    <th scope="col">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((row) => (
                    <tr
                      key={row.item.pageId}
                      className={detailPageId === row.item.pageId ? "is-selected" : undefined}
                    >
                      {canMutate ? (
                        <td>
                          <input
                            aria-label={`Select page ${row.item.pageIndex + 1}`}
                            type="checkbox"
                            checked={selectedPageIds.has(row.item.pageId)}
                            onChange={() => togglePageSelection(row.item.pageId)}
                          />
                        </td>
                      ) : null}
                      <td>{row.item.pageIndex + 1}</td>
                      <td>
                        {row.item.warningsJson.length > 0
                          ? row.item.warningsJson.join(", ")
                          : "none"}
                      </td>
                      <td>{formatMetric(row.skewDeg)}</td>
                      <td>{formatMetric(row.blurScore, 3)}</td>
                      <td>
                        {row.dpiEstimate === null ? "N/A" : Math.round(row.dpiEstimate)}
                      </td>
                      <td>
                        <StatusChip tone={resolveTone(row.item.qualityGateStatus)}>
                          {row.item.qualityGateStatus}
                        </StatusChip>
                        <span className="qualityTriageSubStatus">{row.item.status}</span>
                      </td>
                      <td>
                        <button
                          className="secondaryButton"
                          type="button"
                          onClick={() => setDetailPageId(row.item.pageId)}
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <DetailsDrawer
        open={activeDetailRow !== null}
        onClose={() => setDetailPageId(null)}
        title={
          activeDetailRow
            ? `Page ${activeDetailRow.item.pageIndex + 1} quality details`
            : "Page quality details"
        }
        description="Before/after mini previews and per-page metrics for triage."
      >
        {activeDetailRow ? (
          <div className="qualityDetailsDrawerBody">
            <div className="qualityDetailsPreviewGrid">
              <figure>
                <figcaption>Before</figcaption>
                <img
                  alt={`Page ${activeDetailRow.item.pageIndex + 1} original preview`}
                  src={projectDocumentPageImagePath(
                    projectId,
                    documentId,
                    activeDetailRow.item.pageId,
                    "thumb"
                  )}
                />
              </figure>
              <figure>
                <figcaption>After</figcaption>
                {run &&
                activeDetailRow.item.status === "SUCCEEDED" &&
                activeDetailRow.item.outputObjectKeyGray ? (
                  <img
                    alt={`Page ${activeDetailRow.item.pageIndex + 1} preprocessed preview`}
                    src={projectDocumentPageImagePath(
                      projectId,
                      documentId,
                      activeDetailRow.item.pageId,
                      "preprocessed_gray",
                      {
                        runId: run.id
                      }
                    )}
                  />
                ) : (
                  <p className="ukde-muted">No preprocessed preview available.</p>
                )}
              </figure>
            </div>
            <ul className="projectMetaList">
              <li>
                <span>Skew</span>
                <strong>{formatMetric(toMetricNumber(activeDetailRow.item.metricsJson.skew_angle_deg))}</strong>
              </li>
              <li>
                <span>Blur score</span>
                <strong>{formatMetric(toMetricNumber(activeDetailRow.item.metricsJson.blur_score), 3)}</strong>
              </li>
              <li>
                <span>DPI estimate</span>
                <strong>
                  {toMetricNumber(activeDetailRow.item.metricsJson.dpi_estimate) === null
                    ? "N/A"
                    : Math.round(
                        toMetricNumber(activeDetailRow.item.metricsJson.dpi_estimate) ?? 0
                      )}
                </strong>
              </li>
              <li>
                <span>Warnings</span>
                <strong>
                  {activeDetailRow.item.warningsJson.length > 0
                    ? activeDetailRow.item.warningsJson.join(", ")
                    : "none"}
                </strong>
              </li>
              <li>
                <span>Status</span>
                <strong>
                  <StatusChip tone={resolveTone(activeDetailRow.item.qualityGateStatus)}>
                    {activeDetailRow.item.qualityGateStatus}
                  </StatusChip>
                </strong>
              </li>
            </ul>
            <div className="buttonRow">
              <Link
                className="secondaryButton"
                href={projectDocumentViewerPath(
                  projectId,
                  documentId,
                  activeDetailRow.item.pageIndex + 1,
                  {
                    mode: "preprocessed",
                    runId: run?.id ?? undefined
                  }
                )}
              >
                Open in viewer
              </Link>
            </div>
          </div>
        ) : null}
      </DetailsDrawer>

      <ModalDialog
        open={wizardOpen}
        onClose={() => {
          if (!rerunPending) {
            setWizardOpen(false);
          }
        }}
        title="Re-run preprocessing"
        description="Choose rerun scope, profile, and confirmation."
        footer={
          <div className="buttonRow">
            {wizardStep > 1 ? (
              <button
                className="secondaryButton"
                type="button"
                disabled={rerunPending}
                onClick={() => setWizardStep((current) => (current - 1) as 1 | 2 | 3)}
              >
                Back
              </button>
            ) : null}
            {wizardStep < 3 ? (
              <button
                className="secondaryButton"
                type="button"
                disabled={
                  rerunPending ||
                  (wizardStep === 1 && rerunScope === "PAGE_SUBSET" && selectedCount === 0)
                }
                onClick={() => setWizardStep((current) => (current + 1) as 1 | 2 | 3)}
              >
                Next
              </button>
            ) : (
              <button
                className="secondaryButton"
                type="button"
                disabled={
                  rerunPending || (advancedRiskRequired && !advancedRiskConfirmed)
                }
                onClick={() => {
                  void queueRerun();
                }}
              >
                {rerunPending ? "Queueing rerun..." : "Confirm and run"}
              </button>
            )}
          </div>
        }
      >
        {wizardStep === 1 ? (
          <div className="qualityWizardStep">
            <h3>Step 1: Scope</h3>
            <label className="qualityWizardChoice">
              <input
                type="radio"
                name="scope"
                checked={rerunScope === "FULL_DOCUMENT"}
                onChange={() => setRerunScope("FULL_DOCUMENT")}
              />
              Whole document
            </label>
            <label className="qualityWizardChoice">
              <input
                type="radio"
                name="scope"
                checked={rerunScope === "PAGE_SUBSET"}
                onChange={() => setRerunScope("PAGE_SUBSET")}
              />
              Selected pages ({selectedCount})
            </label>
          </div>
        ) : null}

        {wizardStep === 2 ? (
          <div className="qualityWizardStep">
            <h3>Step 2: Profile</h3>
            {(["BALANCED", "CONSERVATIVE"] as const).map((profile) => (
              <label className="qualityWizardChoice" key={profile}>
                <input
                  type="radio"
                  name="profile"
                  checked={profileId === profile}
                  onChange={() => setProfileId(profile)}
                />
                <span>
                  <strong>{profile}</strong>
                  <span className="ukde-muted"> {PROFILE_DESCRIPTIONS[profile]}</span>
                </span>
              </label>
            ))}
            <details
              className="qualityWizardAdvanced"
              open={profileId === "AGGRESSIVE" || profileId === "BLEED_THROUGH"}
            >
              <summary>Advanced profiles</summary>
              {(["AGGRESSIVE", "BLEED_THROUGH"] as const).map((profile) => (
                <label className="qualityWizardChoice" key={profile}>
                  <input
                    type="radio"
                    name="profile"
                    checked={profileId === profile}
                    onChange={() => setProfileId(profile)}
                  />
                  <span>
                    <strong>{profile}</strong>
                    <span className="ukde-muted"> {PROFILE_DESCRIPTIONS[profile]}</span>
                  </span>
                </label>
              ))}
            </details>
          </div>
        ) : null}

        {wizardStep === 3 ? (
          <div className="qualityWizardStep">
            <h3>Step 3: Confirm</h3>
            <ul className="projectMetaList">
              <li>
                <span>Scope</span>
                <strong>
                  {rerunScope === "PAGE_SUBSET"
                    ? `Selected pages (${selectedCount})`
                    : "Whole document"}
                </strong>
              </li>
              <li>
                <span>Profile</span>
                <strong>
                  {profileId} · {PROFILE_DESCRIPTIONS[profileId]}
                </strong>
              </li>
              <li>
                <span>Source run</span>
                <strong>{run?.id ?? "N/A"}</strong>
              </li>
            </ul>
            {advancedRiskRequired ? (
              <div className="qualityWizardRiskGate">
                <p className="ukde-muted">{ADVANCED_RISK_CONFIRMATION_COPY}</p>
                <label className="qualityWizardChoice">
                  <input
                    type="checkbox"
                    checked={advancedRiskConfirmed}
                    onChange={(event) =>
                      setAdvancedRiskConfirmed(event.target.checked)
                    }
                  />
                  I confirm advanced full-document processing for this rerun.
                </label>
                <label>
                  Confirmation note (optional)
                  <input
                    type="text"
                    maxLength={400}
                    value={advancedRiskAcknowledgement}
                    onChange={(event) =>
                      setAdvancedRiskAcknowledgement(event.target.value)
                    }
                    placeholder="Reason for stronger cleanup"
                  />
                </label>
              </div>
            ) : null}
            <details>
              <summary>Advanced parameters</summary>
              <p className="ukde-muted">
                Advanced parameters stay collapsed by default. This flow applies the selected
                profile and optional selected-page scope only.
              </p>
            </details>
          </div>
        ) : null}

        {rerunError ? (
          <InlineAlert title="Rerun request failed" tone="danger">
            {rerunError}
          </InlineAlert>
        ) : null}
      </ModalDialog>
    </>
  );
}
