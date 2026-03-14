"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type {
  DocumentTranscriptionMetricsResponse,
  DocumentTranscriptionTriagePage,
  UpdateDocumentTranscriptionTriageAssignmentResponse
} from "@ukde/contracts";
import { DetailsDrawer, SectionState, StatusChip } from "@ukde/ui/primitives";

import { projectDocumentTranscriptionWorkspacePath } from "../lib/routes";

interface DocumentTranscriptionTriageSurfaceProps {
  canAssign: boolean;
  documentId: string;
  items: DocumentTranscriptionTriagePage[];
  metrics: DocumentTranscriptionMetricsResponse | null;
  projectId: string;
  runId: string;
}

function resolveTone(
  status: string
): "danger" | "neutral" | "success" | "warning" {
  if (status === "SUCCEEDED") {
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

function formatConfidence(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "N/A";
  }
  return value.toFixed(3);
}

function formatAssignmentStamp(value: string | null): string {
  if (!value) {
    return "Not assigned";
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Date(parsed).toISOString();
}

export function DocumentTranscriptionTriageSurface({
  canAssign,
  documentId,
  items,
  metrics,
  projectId,
  runId
}: DocumentTranscriptionTriageSurfaceProps) {
  const [rows, setRows] = useState<DocumentTranscriptionTriagePage[]>(items);
  const [lowConfidenceOnly, setLowConfidenceOnly] = useState(false);
  const [failedOnly, setFailedOnly] = useState(false);
  const [confidenceBelow, setConfidenceBelow] = useState<number | null>(null);
  const [detailPageId, setDetailPageId] = useState<string | null>(null);
  const [assignmentDraft, setAssignmentDraft] = useState("");
  const [assignmentPending, setAssignmentPending] = useState(false);
  const [assignmentMessage, setAssignmentMessage] = useState<string | null>(null);

  useEffect(() => {
    setRows(items);
  }, [items]);

  const filteredRows = useMemo(() => {
    const next = rows.filter((item) => {
      if (lowConfidenceOnly && item.lowConfidenceLines <= 0) {
        return false;
      }
      if (failedOnly && item.status !== "FAILED") {
        return false;
      }
      if (
        typeof confidenceBelow === "number" &&
        Number.isFinite(confidenceBelow) &&
        !(
          typeof item.minConfidence === "number" &&
          item.minConfidence < confidenceBelow
        )
      ) {
        return false;
      }
      return true;
    });
    return [...next].sort((a, b) => {
      if (b.rankingScore !== a.rankingScore) {
        return b.rankingScore - a.rankingScore;
      }
      if (a.pageIndex !== b.pageIndex) {
        return a.pageIndex - b.pageIndex;
      }
      return a.pageId.localeCompare(b.pageId);
    });
  }, [rows, lowConfidenceOnly, failedOnly, confidenceBelow]);

  const activeRow = useMemo(
    () => rows.find((item) => item.pageId === detailPageId) ?? null,
    [detailPageId, rows]
  );

  useEffect(() => {
    if (!activeRow) {
      setAssignmentDraft("");
      setAssignmentMessage(null);
      return;
    }
    setAssignmentDraft(activeRow.reviewerAssignmentUserId ?? "");
    setAssignmentMessage(null);
  }, [activeRow]);

  async function saveAssignment() {
    if (!activeRow || !canAssign) {
      return;
    }
    setAssignmentPending(true);
    setAssignmentMessage(null);
    try {
      const response = await fetch(
        `/projects/${projectId}/documents/${documentId}/transcription/triage/pages/${activeRow.pageId}/assignment`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            runId,
            reviewerUserId:
              assignmentDraft.trim().length > 0 ? assignmentDraft.trim() : undefined
          })
        }
      );
      const payload = (await response.json()) as
        | UpdateDocumentTranscriptionTriageAssignmentResponse
        | { detail?: string };
      if (!response.ok || !("item" in payload)) {
        setAssignmentMessage(
          ("detail" in payload && payload.detail) ||
            "Assignment update failed."
        );
        return;
      }
      setRows((current) =>
        current.map((row) => (row.pageId === payload.item.pageId ? payload.item : row))
      );
      setAssignmentMessage("Reviewer assignment updated.");
    } catch {
      setAssignmentMessage("Assignment update failed.");
    } finally {
      setAssignmentPending(false);
    }
  }

  if (rows.length === 0) {
    return (
      <SectionState
        kind="empty"
        title="No triage rows yet"
        description="Triage rows appear after a transcription run has page outputs."
      />
    );
  }

  return (
    <>
      {metrics ? (
        <section className="qualityTriageActionBar">
          <p className="ukde-muted">
            {metrics.pageCount} pages · {metrics.lineCount} lines · {metrics.lowConfidenceLineCount} low-confidence lines · {metrics.percentLinesBelowThreshold.toFixed(2)}% below threshold
          </p>
        </section>
      ) : null}
      <section className="qualityTriageControls">
        <label className="qualityTriageCheckbox">
          <input
            type="checkbox"
            checked={lowConfidenceOnly}
            onChange={(event) => setLowConfidenceOnly(event.target.checked)}
          />
          Low confidence only
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
          Confidence below
          <input
            type="number"
            step="0.01"
            min={0}
            max={1}
            value={
              typeof confidenceBelow === "number" && Number.isFinite(confidenceBelow)
                ? confidenceBelow
                : ""
            }
            onChange={(event) => {
              const raw = Number.parseFloat(event.target.value);
              setConfidenceBelow(Number.isFinite(raw) ? raw : null);
            }}
            placeholder="0.85"
          />
        </label>
      </section>

      {filteredRows.length === 0 ? (
        <SectionState
          kind="empty"
          title="No rows match current filters"
          description="Adjust low-confidence, failed, or confidence-below filters."
        />
      ) : (
        <div className="qualityTriageTableWrap">
          <table className="ukde-data-table qualityTriageTable">
            <caption className="sr-only">Transcription triage rows</caption>
            <thead>
              <tr>
                <th scope="col">Page</th>
                <th scope="col">Low confidence</th>
                <th scope="col">Min / Avg</th>
                <th scope="col">Issues</th>
                <th scope="col">Status</th>
                <th scope="col">Score</th>
                <th scope="col">Assignment</th>
                <th scope="col" className="sr-only">
                  Open
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => (
                <tr key={row.pageId}>
                  <td>Page {row.pageIndex + 1}</td>
                  <td>{row.lowConfidenceLines}</td>
                  <td>
                    {formatConfidence(row.minConfidence)} / {formatConfidence(row.avgConfidence)}
                  </td>
                  <td>{row.issues.length > 0 ? row.issues.join(", ") : "none"}</td>
                  <td>
                    <StatusChip tone={resolveTone(row.status)}>{row.status}</StatusChip>
                  </td>
                  <td>{row.rankingScore.toFixed(2)}</td>
                  <td>{row.reviewerAssignmentUserId ?? "Unassigned"}</td>
                  <td>
                    <button
                      className="secondaryButton"
                      type="button"
                      onClick={() => setDetailPageId(row.pageId)}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <DetailsDrawer
        description="Transcription triage detail drawer"
        onClose={() => setDetailPageId(null)}
        open={Boolean(activeRow)}
        title={activeRow ? `Page ${activeRow.pageIndex + 1} transcription` : "Transcription"}
      >
        {activeRow ? (
          <div className="qualityDetailsDrawerBody">
            <ul className="projectMetaList">
              <li>
                <span>Run ID</span>
                <strong>{runId}</strong>
              </li>
              <li>
                <span>Status</span>
                <strong>{activeRow.status}</strong>
              </li>
              <li>
                <span>Line count</span>
                <strong>{activeRow.lineCount}</strong>
              </li>
              <li>
                <span>Token count</span>
                <strong>{activeRow.tokenCount}</strong>
              </li>
              <li>
                <span>Low-confidence lines</span>
                <strong>{activeRow.lowConfidenceLines}</strong>
              </li>
              <li>
                <span>Min confidence</span>
                <strong>{formatConfidence(activeRow.minConfidence)}</strong>
              </li>
              <li>
                <span>Average confidence</span>
                <strong>{formatConfidence(activeRow.avgConfidence)}</strong>
              </li>
              <li>
                <span>Confidence bands</span>
                <strong>
                  H {activeRow.confidenceBands.HIGH} · M {activeRow.confidenceBands.MEDIUM} · L {activeRow.confidenceBands.LOW} · U {activeRow.confidenceBands.UNKNOWN}
                </strong>
              </li>
              <li>
                <span>Ranking rationale</span>
                <strong>{activeRow.rankingRationale}</strong>
              </li>
              <li>
                <span>Assigned reviewer</span>
                <strong>{activeRow.reviewerAssignmentUserId ?? "Unassigned"}</strong>
              </li>
              <li>
                <span>Assignment updated</span>
                <strong>{formatAssignmentStamp(activeRow.reviewerAssignmentUpdatedAt)}</strong>
              </li>
            </ul>
            {canAssign ? (
              <section className="qualityTriageControls">
                <label>
                  Reviewer user ID
                  <input
                    type="text"
                    value={assignmentDraft}
                    onChange={(event) => setAssignmentDraft(event.target.value)}
                    placeholder="user-2"
                  />
                </label>
                <div className="buttonRow">
                  <button
                    className="secondaryButton"
                    type="button"
                    onClick={() => void saveAssignment()}
                    disabled={assignmentPending}
                  >
                    {assignmentPending ? "Saving..." : "Update assignment"}
                  </button>
                  <button
                    className="secondaryButton"
                    type="button"
                    onClick={() => setAssignmentDraft("")}
                    disabled={assignmentPending}
                  >
                    Clear draft
                  </button>
                </div>
                {assignmentMessage ? <p className="ukde-muted">{assignmentMessage}</p> : null}
              </section>
            ) : null}
            <div className="buttonRow">
              <Link
                className="secondaryButton"
                href={projectDocumentTranscriptionWorkspacePath(projectId, documentId, {
                  page: activeRow.pageIndex + 1,
                  runId
                })}
              >
                Open workspace
              </Link>
            </div>
          </div>
        ) : null}
      </DetailsDrawer>
    </>
  );
}
