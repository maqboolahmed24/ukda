"use client";

import { useEffect, useRef, useState } from "react";
import { InlineAlert, SectionState, StatusChip } from "@ukde/ui/primitives";

import { queryCachePolicy } from "../lib/data/cache-policy";
import { requestBrowserApi } from "../lib/data/browser-api-client";
import {
  normalizePipelinePhaseOrder,
  toPipelineStatusTone,
  type DocumentPipelinePhase,
  type DocumentPipelinePhaseStatus,
  type DocumentPipelineStatusResponse
} from "../lib/pipeline-status";

const DEFAULT_POLL_MS = queryCachePolicy["operations-live"].pollIntervalMs ?? 4_000;

function usePrefersReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setPrefersReducedMotion(media.matches);
    apply();

    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", apply);
      return () => media.removeEventListener("change", apply);
    }

    media.addListener(apply);
    return () => media.removeListener(apply);
  }, []);

  return prefersReducedMotion;
}

function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

function resolveStatusLabel(status: DocumentPipelinePhaseStatus): string {
  switch (status) {
    case "NOT_STARTED":
      return "Not started";
    case "QUEUED":
      return "Queued";
    case "RUNNING":
      return "Running";
    case "SUCCEEDED":
      return "Succeeded";
    case "FAILED":
      return "Failed";
    case "CANCELED":
      return "Canceled";
    case "DEGRADED":
      return "Degraded";
    default:
      return "Unknown";
  }
}

function resolveOverallStatus(phases: DocumentPipelinePhase[]): DocumentPipelinePhaseStatus {
  if (phases.some((phase) => phase.status === "DEGRADED")) {
    return "DEGRADED";
  }
  if (phases.some((phase) => phase.status === "FAILED")) {
    return "FAILED";
  }
  if (phases.some((phase) => phase.status === "RUNNING")) {
    return "RUNNING";
  }
  if (phases.some((phase) => phase.status === "QUEUED")) {
    return "QUEUED";
  }
  if (phases.every((phase) => phase.status === "SUCCEEDED")) {
    return "SUCCEEDED";
  }
  if (phases.some((phase) => phase.status === "CANCELED")) {
    return "CANCELED";
  }
  return "NOT_STARTED";
}

function resolveOverallDetail(
  phases: DocumentPipelinePhase[],
  overallStatus: DocumentPipelinePhaseStatus
): string {
  if (overallStatus === "SUCCEEDED") {
    return "All document phases reached terminal success states.";
  }
  if (overallStatus === "FAILED") {
    return "At least one phase failed. Polling degradation is reported separately.";
  }
  if (overallStatus === "DEGRADED") {
    return "At least one phase feed is degraded. Last good phase state remains visible.";
  }
  const activeCount = phases.filter(
    (phase) => phase.status === "RUNNING" || phase.status === "QUEUED"
  ).length;
  if (activeCount > 0) {
    return `${activeCount} phase${activeCount === 1 ? "" : "s"} currently active.`;
  }
  return "Awaiting phase activity.";
}

export function DocumentPipelineLiveStatus({
  documentId,
  projectId
}: {
  documentId: string;
  projectId: string;
}) {
  const [snapshot, setSnapshot] = useState<DocumentPipelineStatusResponse | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const snapshotRef = useRef<DocumentPipelineStatusResponse | null>(null);
  const prefersReducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    snapshotRef.current = snapshot;
  }, [snapshot]);

  useEffect(() => {
    let canceled = false;
    let timerId: number | null = null;
    let pollMs = DEFAULT_POLL_MS;

    const schedule = (nextPollMs: number) => {
      timerId = window.setTimeout(() => {
        void poll();
      }, nextPollMs);
    };

    const poll = async () => {
      const result = await requestBrowserApi<DocumentPipelineStatusResponse>({
        method: "GET",
        path: `/projects/${projectId}/documents/${documentId}/pipeline/status`,
        cacheClass: "operations-live"
      });

      if (canceled) {
        return;
      }

      if (!result.ok || !result.data) {
        setPollError(result.detail ?? "Pipeline status polling unavailable.");
        const fallbackMs =
          snapshotRef.current?.recommendedPollMs && snapshotRef.current.recommendedPollMs > 0
            ? snapshotRef.current.recommendedPollMs
            : pollMs;
        schedule(fallbackMs);
        return;
      }

      pollMs =
        typeof result.data.recommendedPollMs === "number" && result.data.recommendedPollMs > 0
          ? result.data.recommendedPollMs
          : DEFAULT_POLL_MS;
      setSnapshot(result.data);
      setPollError(null);
      schedule(pollMs);
    };

    void poll();

    return () => {
      canceled = true;
      if (timerId !== null) {
        window.clearTimeout(timerId);
      }
    };
  }, [documentId, projectId]);

  if (!snapshot) {
    return (
      <section
        className="sectionCard ukde-panel documentPipelineLiveStatus"
        aria-live="polite"
      >
        <p className="ukde-eyebrow">Live pipeline</p>
        <h3>End-to-end status</h3>
        <SectionState
          kind={pollError ? "degraded" : "loading"}
          title={pollError ? "Pipeline polling degraded" : "Loading live pipeline status"}
          description={
            pollError ??
            "Collecting ingest, preprocess, layout, transcription, privacy, and governance status."
          }
        />
      </section>
    );
  }

  const orderedPhases = normalizePipelinePhaseOrder(snapshot.phases);
  const phaseLabelById = new Map(
    orderedPhases.map((phase) => [phase.phaseId, phase.label] as const)
  );
  const overallStatus = resolveOverallStatus(orderedPhases);
  const degradedDetail = snapshot.errors
    .map((error) => `${phaseLabelById.get(error.phaseId) ?? error.phaseId}: ${error.detail}`)
    .join(" ");
  const overallDetail = resolveOverallDetail(orderedPhases, overallStatus);
  const pollSeconds = Math.max(1, Math.round(snapshot.recommendedPollMs / 1000));

  return (
    <section className="sectionCard ukde-panel documentPipelineLiveStatus" aria-live="polite">
      <p className="ukde-eyebrow">Live pipeline</p>
      <h3>End-to-end status</h3>
      <div className="documentPipelineOverall">
        <div className="auditIntegrityRow">
          <StatusChip tone={toPipelineStatusTone(overallStatus)}>
            {resolveStatusLabel(overallStatus)}
          </StatusChip>
          {typeof snapshot.overallPercent === "number" ? (
            <strong className="documentPipelineOverallPercent">
              {formatPercent(snapshot.overallPercent)}
            </strong>
          ) : (
            <span className="ukde-muted">Overall percent unavailable</span>
          )}
        </div>
        <p className="ukde-muted">{overallDetail}</p>
      </div>

      {pollError ? (
        <InlineAlert title="Status polling degraded" tone="warning">
          {pollError} Last successful pipeline state is still displayed.
        </InlineAlert>
      ) : null}
      {snapshot.degraded && degradedDetail.length > 0 ? (
        <InlineAlert title="Partial data degradation" tone="info">
          {degradedDetail}
        </InlineAlert>
      ) : null}

      <ul className="documentPipelinePhaseList">
        {orderedPhases.map((phase) => {
          const percent = typeof phase.percent === "number" ? phase.percent : null;
          const hasPercent = percent !== null;
          const reducedMotionClass = prefersReducedMotion
            ? " documentPipelineProgressFill--reduced-motion"
            : "";

          return (
            <li
              key={phase.phaseId}
              className="documentPipelinePhase"
              data-testid={`pipeline-phase-${phase.phaseId.toLowerCase()}`}
            >
              <div className="documentPipelinePhaseMeta">
                <div className="auditIntegrityRow">
                  <strong>{phase.label}</strong>
                  <StatusChip tone={toPipelineStatusTone(phase.status)}>
                    {resolveStatusLabel(phase.status)}
                  </StatusChip>
                </div>
                <div className="auditIntegrityRow">
                  {phase.completedUnits !== null && phase.totalUnits !== null ? (
                    <span className="ukde-muted">
                      {phase.completedUnits}/{phase.totalUnits}
                    </span>
                  ) : (
                    <span className="ukde-muted">Units unavailable</span>
                  )}
                  {hasPercent ? (
                    <strong
                      className="documentPipelinePhasePercent"
                      data-testid={`pipeline-percent-${phase.phaseId.toLowerCase()}`}
                    >
                      {formatPercent(percent)}
                    </strong>
                  ) : null}
                </div>
              </div>

              <div
                className="documentPipelineProgressTrack"
                role="progressbar"
                aria-label={`${phase.label} progress`}
                aria-valuemin={0}
                aria-valuemax={100}
                {...(hasPercent
                  ? {
                      "aria-valuenow": Math.round(percent),
                      "aria-valuetext": `${Math.round(percent)} percent`
                    }
                  : {
                      "aria-valuetext": `${resolveStatusLabel(phase.status)}`
                    })}
                data-testid={`pipeline-progress-${phase.phaseId.toLowerCase()}`}
              >
                {hasPercent ? (
                  <span
                    className={`documentPipelineProgressFill${reducedMotionClass}`}
                    style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
                  />
                ) : (
                  <span
                    className={`documentPipelineProgressFill documentPipelineProgressFill--indeterminate${reducedMotionClass}`}
                    data-testid={`pipeline-indeterminate-${phase.phaseId.toLowerCase()}`}
                  />
                )}
              </div>
              <p className="ukde-muted">{phase.detail}</p>
            </li>
          );
        })}
      </ul>

      <p className="ukde-muted">Polling every {pollSeconds}s using live operations policy.</p>
    </section>
  );
}
