"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type {
  DocumentProcessingRunKind,
  DocumentProcessingRunStatus,
  DocumentProcessingRunStatusResponse,
  DocumentStatus,
  DocumentTimelineEvent,
  DocumentTimelineResponse
} from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";

const STATUS_POLL_INTERVAL_MS = 5_000;
const STAGE_ORDER: DocumentProcessingRunKind[] = [
  "UPLOAD",
  "SCAN",
  "EXTRACTION",
  "THUMBNAIL_RENDER"
];
const ACTIVE_RUN_STATUSES: DocumentProcessingRunStatus[] = ["QUEUED", "RUNNING"];

export interface DocumentProcessingTimelineProps {
  documentStatus: DocumentStatus;
  initialErrorMessage?: string | null;
  initialItems: DocumentTimelineEvent[];
  projectId: string;
  documentId: string;
}

interface StageView {
  description: string;
  kind: DocumentProcessingRunKind;
  label: string;
  statusLabel: string;
  tone: "danger" | "neutral" | "success" | "warning";
}

function formatTimestamp(value: string): string {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return value;
  }
  return timestamp.toISOString();
}

function resolveRunKindCopy(runKind: DocumentProcessingRunKind): string {
  switch (runKind) {
    case "UPLOAD":
      return "Upload";
    case "SCAN":
      return "Scan";
    case "EXTRACTION":
      return "Extraction";
    case "THUMBNAIL_RENDER":
      return "Thumbnail rendering";
    default:
      return "Processing";
  }
}

function resolveRunStatusTone(
  status: DocumentProcessingRunStatus
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

function isActiveRunStatus(status: DocumentProcessingRunStatus): boolean {
  return ACTIVE_RUN_STATUSES.includes(status);
}

function resolveStageView(items: DocumentTimelineEvent[]): StageView[] {
  const latestByKind = new Map<DocumentProcessingRunKind, DocumentTimelineEvent>();
  for (const event of items) {
    if (!latestByKind.has(event.runKind)) {
      latestByKind.set(event.runKind, event);
    }
  }

  return STAGE_ORDER.map((kind, index) => {
    const latest = latestByKind.get(kind);
    if (latest) {
      if (latest.status === "SUCCEEDED") {
        return {
          kind,
          label: resolveRunKindCopy(kind),
          tone: "success",
          statusLabel: "Succeeded",
          description: "Latest attempt completed."
        };
      }
      if (latest.status === "FAILED") {
        return {
          kind,
          label: resolveRunKindCopy(kind),
          tone: "danger",
          statusLabel: "Failed",
          description: latest.failureReason ?? "Latest attempt failed."
        };
      }
      if (latest.status === "CANCELED") {
        return {
          kind,
          label: resolveRunKindCopy(kind),
          tone: "neutral",
          statusLabel: "Canceled",
          description: "Latest attempt was canceled."
        };
      }
      return {
        kind,
        label: resolveRunKindCopy(kind),
        tone: "warning",
        statusLabel: latest.status === "QUEUED" ? "Queued" : "Running",
        description:
          latest.status === "QUEUED"
            ? "Attempt is queued."
            : "Attempt is in progress."
      };
    }

    let blockedByPriorTerminal = false;
    for (let previousIndex = 0; previousIndex < index; previousIndex += 1) {
      const prior = latestByKind.get(STAGE_ORDER[previousIndex]);
      if (prior && (prior.status === "FAILED" || prior.status === "CANCELED")) {
        blockedByPriorTerminal = true;
        break;
      }
    }

    if (blockedByPriorTerminal) {
      return {
        kind,
        label: resolveRunKindCopy(kind),
        tone: "neutral",
        statusLabel: "Not reached",
        description:
          "A prior stage failed or was canceled, so this stage did not run."
      };
    }

    return {
      kind,
      label: resolveRunKindCopy(kind),
      tone: "neutral",
      statusLabel: "Not started",
      description: "No attempt has been recorded yet."
    };
  });
}

function mergeRunStatus(
  items: DocumentTimelineEvent[],
  updates: DocumentProcessingRunStatusResponse[]
): { items: DocumentTimelineEvent[]; settledRunIds: string[] } {
  if (updates.length === 0) {
    return { items, settledRunIds: [] };
  }
  const updateMap = new Map(updates.map((entry) => [entry.runId, entry]));
  const settledRunIds: string[] = [];
  const nextItems = items.map((event) => {
    const update = updateMap.get(event.id);
    if (!update) {
      return event;
    }
    if (
      isActiveRunStatus(event.status) &&
      !isActiveRunStatus(update.status)
    ) {
      settledRunIds.push(event.id);
    }
    return {
      ...event,
      status: update.status,
      failureReason: update.failureReason,
      startedAt: update.startedAt,
      finishedAt: update.finishedAt,
      canceledAt: update.canceledAt
    };
  });
  return { items: nextItems, settledRunIds };
}

export function DocumentProcessingTimeline({
  documentStatus,
  initialErrorMessage = null,
  initialItems,
  projectId,
  documentId
}: DocumentProcessingTimelineProps) {
  const [timelineItems, setTimelineItems] =
    useState<DocumentTimelineEvent[]>(initialItems);
  const timelineItemsRef = useRef<DocumentTimelineEvent[]>(initialItems);
  const [timelineError, setTimelineError] = useState<string | null>(
    initialErrorMessage
  );
  const [pollError, setPollError] = useState<string | null>(null);

  useEffect(() => {
    setTimelineItems(initialItems);
    timelineItemsRef.current = initialItems;
  }, [initialItems]);

  useEffect(() => {
    setTimelineError(initialErrorMessage);
  }, [initialErrorMessage]);

  useEffect(() => {
    timelineItemsRef.current = timelineItems;
  }, [timelineItems]);

  const activeRunIds = useMemo(
    () =>
      timelineItems
        .filter((item) => isActiveRunStatus(item.status))
        .map((item) => item.id),
    [timelineItems]
  );
  const activeRunIdsKey = activeRunIds.join(",");
  const stageViews = useMemo(
    () => resolveStageView(timelineItems),
    [timelineItems]
  );

  useEffect(() => {
    if (timelineError || !activeRunIdsKey) {
      return;
    }

    let canceled = false;
    const runIds = activeRunIdsKey.split(",").filter((value) => value);

    const pollRunStatuses = async () => {
      const statusResults = await Promise.all(
        runIds.map((runId) =>
          requestBrowserApi<DocumentProcessingRunStatusResponse>({
            method: "GET",
            path: `/projects/${projectId}/documents/${documentId}/processing-runs/${runId}/status`,
            cacheClass: "operations-live"
          })
        )
      );
      if (canceled) {
        return;
      }

      const updates = statusResults
        .filter((result) => result.ok && result.data)
        .map((result) => result.data as DocumentProcessingRunStatusResponse);
      if (updates.length === 0) {
        setPollError(
          "Active status polling is temporarily unavailable. Timeline data remains visible."
        );
        return;
      }

      setPollError(null);
      const merged = mergeRunStatus(timelineItemsRef.current, updates);
      timelineItemsRef.current = merged.items;
      setTimelineItems(merged.items);
      if (merged.settledRunIds.length === 0) {
        return;
      }

      const timelineRefresh = await requestBrowserApi<DocumentTimelineResponse>({
        method: "GET",
        path: `/projects/${projectId}/documents/${documentId}/processing-runs`,
        cacheClass: "operations-live"
      });
      if (canceled) {
        return;
      }
      if (timelineRefresh.ok && timelineRefresh.data) {
        setTimelineItems(timelineRefresh.data.items);
      }
    };

    void pollRunStatuses();
    const timer = window.setInterval(() => {
      void pollRunStatuses();
    }, STATUS_POLL_INTERVAL_MS);

    return () => {
      canceled = true;
      window.clearInterval(timer);
    };
  }, [activeRunIdsKey, documentId, projectId, timelineError]);

  if (timelineError) {
    return (
      <SectionState
        kind="degraded"
        title="Timeline unavailable"
        description={timelineError}
      />
    );
  }

  if (timelineItems.length === 0) {
    return (
      <SectionState
        kind="empty"
        title="No processing timeline entries yet"
        description="Timeline events will appear after the first attempt is recorded."
      />
    );
  }

  return (
    <div className="documentProcessingTimeline">
      <ol className="documentProcessingStageList">
        {stageViews.map((stage) => (
          <li
            className="documentProcessingStageItem"
            data-stage={stage.kind.toLowerCase()}
            key={stage.kind}
          >
            <div className="auditIntegrityRow">
              <strong>{stage.label}</strong>
              <StatusChip tone={stage.tone}>{stage.statusLabel}</StatusChip>
            </div>
            <p className="ukde-muted">{stage.description}</p>
          </li>
        ))}
      </ol>

      <ol className="timelineList">
        {timelineItems.map((event) => (
          <li key={event.id}>
            <div className="auditIntegrityRow">
              <StatusChip tone={resolveRunStatusTone(event.status)}>
                {resolveRunKindCopy(event.runKind)}
              </StatusChip>
              <span className="ukde-muted">
                {formatTimestamp(event.finishedAt ?? event.startedAt ?? event.createdAt)}
              </span>
            </div>
            <p className="ukde-muted">Status: {event.status}</p>
            <p className="ukde-muted">Attempt: {event.attemptNumber}</p>
            {event.failureReason ? (
              <p className="ukde-muted">{event.failureReason}</p>
            ) : null}
          </li>
        ))}
      </ol>

      <p className="ukde-muted" aria-live="polite">
        {activeRunIds.length > 0
          ? "Active attempts are polled through per-run status endpoints."
          : documentStatus === "READY"
            ? "All current attempts are in a terminal state."
            : "No active attempts are currently running."}
      </p>
      {pollError ? (
        <p className="ukde-muted" role="status">
          {pollError}
        </p>
      ) : null}
    </div>
  );
}
