"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { DocumentLayoutPageResult } from "@ukde/contracts";
import { DetailsDrawer, SectionState, StatusChip } from "@ukde/ui/primitives";

import { projectDocumentLayoutWorkspacePath } from "../lib/routes";

interface DocumentLayoutTriageSurfaceProps {
  documentId: string;
  items: DocumentLayoutPageResult[];
  projectId: string;
  runId: string;
}

interface LayoutTriageRow {
  coveragePercent: number | null;
  hasOverlaps: boolean;
  item: DocumentLayoutPageResult;
  lineCount: number | null;
  missingLines: boolean;
  missedTextRiskScore: number | null;
  rescueCandidateCount: number;
  regionCount: number | null;
  uncertainStructure: boolean;
}

function toMetricNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return null;
}

function toIntegerLabel(value: number | null): string {
  if (value === null) {
    return "N/A";
  }
  return String(Math.max(0, Math.round(value)));
}

function toPercentLabel(value: number | null): string {
  if (value === null) {
    return "N/A";
  }
  return `${Math.max(0, Math.min(100, value)).toFixed(1)}%`;
}

function resolveTone(
  status: string
): "danger" | "neutral" | "success" | "warning" {
  if (status === "SUCCEEDED" || status === "COMPLETE") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  return "warning";
}

export function DocumentLayoutTriageSurface({
  documentId,
  items,
  projectId,
  runId
}: DocumentLayoutTriageSurfaceProps) {
  const [missingLinesOnly, setMissingLinesOnly] = useState(false);
  const [overlapsOnly, setOverlapsOnly] = useState(false);
  const [lowCoverageOnly, setLowCoverageOnly] = useState(false);
  const [uncertainOnly, setUncertainOnly] = useState(false);
  const [detailPageId, setDetailPageId] = useState<string | null>(null);

  const rows = useMemo<LayoutTriageRow[]>(
    () =>
      items.map((item) => {
        const regionCount = toMetricNumber(
          item.metricsJson.region_count ?? item.metricsJson.regions_detected
        );
        const lineCount = toMetricNumber(
          item.metricsJson.line_count ?? item.metricsJson.lines_detected
        );
        const coveragePercent = toMetricNumber(
          item.metricsJson.coverage_percent ??
            item.metricsJson.coverage ??
            item.metricsJson.line_coverage_percent
        );
        const structureConfidence = toMetricNumber(
          item.metricsJson.structure_confidence ??
            item.metricsJson.reading_order_confidence
        );
        const missedTextRiskScore = toMetricNumber(
          item.metricsJson.missed_text_risk_score
        );
        const rescueCandidateCount = Math.max(
          0,
          Math.round(toMetricNumber(item.metricsJson.rescue_candidate_count) ?? 0)
        );
        const hasOverlaps =
          toMetricNumber(item.metricsJson.overlap_count) !== null &&
          (toMetricNumber(item.metricsJson.overlap_count) ?? 0) > 0;
        const missingLines = lineCount !== null && lineCount <= 0;
        const uncertainStructure =
          (structureConfidence !== null && structureConfidence < 0.75) ||
          item.pageRecallStatus !== "COMPLETE";

        return {
          item,
          regionCount,
          lineCount,
          coveragePercent,
          missedTextRiskScore,
          rescueCandidateCount,
          hasOverlaps:
            hasOverlaps || item.warningsJson.some((warning) => warning.includes("OVERLAP")),
          missingLines:
            missingLines || item.warningsJson.some((warning) => warning.includes("MISSING")),
          uncertainStructure
        };
      }),
    [items]
  );

  const filteredRows = useMemo(() => {
    const filtered = rows.filter((row) => {
      if (missingLinesOnly && !row.missingLines) {
        return false;
      }
      if (overlapsOnly && !row.hasOverlaps) {
        return false;
      }
      if (
        lowCoverageOnly &&
        (row.coveragePercent === null || row.coveragePercent >= 80)
      ) {
        return false;
      }
      if (uncertainOnly && !row.uncertainStructure) {
        return false;
      }
      return true;
    });
    filtered.sort((a, b) => a.item.pageIndex - b.item.pageIndex);
    return filtered;
  }, [lowCoverageOnly, missingLinesOnly, overlapsOnly, rows, uncertainOnly]);

  const activeRow = useMemo(
    () => rows.find((row) => row.item.pageId === detailPageId) ?? null,
    [detailPageId, rows]
  );

  if (rows.length === 0) {
    return (
      <SectionState
        kind="empty"
        title="No page triage rows yet"
        description="Page-level layout results appear after a layout run is queued."
      />
    );
  }

  return (
    <>
      <section className="qualityTriageControls">
        <label className="qualityTriageCheckbox">
          <input
            type="checkbox"
            checked={missingLinesOnly}
            onChange={(event) => setMissingLinesOnly(event.target.checked)}
          />
          Missing lines
        </label>
        <label className="qualityTriageCheckbox">
          <input
            type="checkbox"
            checked={overlapsOnly}
            onChange={(event) => setOverlapsOnly(event.target.checked)}
          />
          Overlaps
        </label>
        <label className="qualityTriageCheckbox">
          <input
            type="checkbox"
            checked={lowCoverageOnly}
            onChange={(event) => setLowCoverageOnly(event.target.checked)}
          />
          Low coverage
        </label>
        <label className="qualityTriageCheckbox">
          <input
            type="checkbox"
            checked={uncertainOnly}
            onChange={(event) => setUncertainOnly(event.target.checked)}
          />
          Complex or uncertain
        </label>
      </section>
      <div className="qualityTriageTableWrap">
        <table className="ukde-data-table qualityTriageTable">
          <caption className="sr-only">Layout page triage rows</caption>
          <thead>
            <tr>
              <th scope="col">Page</th>
              <th scope="col">Issues</th>
              <th scope="col">Regions</th>
              <th scope="col">Lines</th>
              <th scope="col">Coverage</th>
              <th scope="col">Status</th>
              <th scope="col" className="sr-only">
                Open
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const issueFlags: string[] = [];
              if (row.missingLines) {
                issueFlags.push("Missing lines");
              }
              if (row.hasOverlaps) {
                issueFlags.push("Overlaps");
              }
              if (row.coveragePercent !== null && row.coveragePercent < 80) {
                issueFlags.push("Low coverage");
              }
              if (row.uncertainStructure) {
                issueFlags.push("Uncertain structure");
              }
              if (row.rescueCandidateCount > 0) {
                issueFlags.push(`Rescue ${row.rescueCandidateCount}`);
              }
              return (
                <tr key={row.item.pageId}>
                  <td>Page {row.item.pageIndex + 1}</td>
                  <td>{issueFlags.length > 0 ? issueFlags.join(" · ") : "No major issues"}</td>
                  <td>{toIntegerLabel(row.regionCount)}</td>
                  <td>{toIntegerLabel(row.lineCount)}</td>
                  <td>{toPercentLabel(row.coveragePercent)}</td>
                  <td>
                    <div className="buttonRow">
                      <StatusChip tone={resolveTone(row.item.status)}>
                        {row.item.status}
                      </StatusChip>
                      <StatusChip tone={resolveTone(row.item.pageRecallStatus)}>
                        {row.item.pageRecallStatus}
                      </StatusChip>
                    </div>
                  </td>
                  <td>
                    <button
                      className="secondaryButton"
                      type="button"
                      onClick={() => setDetailPageId(row.item.pageId)}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <DetailsDrawer
        description="Layout triage detail drawer"
        onClose={() => setDetailPageId(null)}
        open={Boolean(activeRow)}
        title={
          activeRow
            ? `Page ${activeRow.item.pageIndex + 1} layout details`
            : "Layout details"
        }
      >
        {activeRow ? (
          <div className="qualityDetailsDrawerBody">
            <p className="ukde-muted">
              Overlay preview is not available yet for this run. Canonical PAGE-XML
              and overlay payload rendering is deferred to later prompts.
            </p>
            <ul className="projectMetaList">
              <li>
                <span>Run ID</span>
                <strong>{runId}</strong>
              </li>
              <li>
                <span>Status</span>
                <strong>{activeRow.item.status}</strong>
              </li>
              <li>
                <span>Recall status</span>
                <strong>{activeRow.item.pageRecallStatus}</strong>
              </li>
              <li>
                <span>Missed-text risk</span>
                <strong>
                  {typeof activeRow.missedTextRiskScore === "number"
                    ? activeRow.missedTextRiskScore.toFixed(3)
                    : "N/A"}
                </strong>
              </li>
              <li>
                <span>Rescue candidates</span>
                <strong>{activeRow.rescueCandidateCount}</strong>
              </li>
              <li>
                <span>Regions</span>
                <strong>{toIntegerLabel(activeRow.regionCount)}</strong>
              </li>
              <li>
                <span>Lines</span>
                <strong>{toIntegerLabel(activeRow.lineCount)}</strong>
              </li>
              <li>
                <span>Coverage</span>
                <strong>{toPercentLabel(activeRow.coveragePercent)}</strong>
              </li>
            </ul>
            <div className="buttonRow">
              <Link
                className="secondaryButton"
                href={projectDocumentLayoutWorkspacePath(projectId, documentId, {
                  page: activeRow.item.pageIndex + 1,
                  runId
                })}
              >
                Open in workspace
              </Link>
            </div>
          </div>
        ) : null}
      </DetailsDrawer>
    </>
  );
}
