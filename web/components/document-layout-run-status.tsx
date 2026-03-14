"use client";

import { useEffect, useState } from "react";
import type {
  DocumentLayoutRunStatusResponse,
  LayoutRunStatus
} from "@ukde/contracts";
import { InlineAlert, StatusChip } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";

const POLL_INTERVAL_MS = 5_000;

function resolveTone(status: LayoutRunStatus): "danger" | "neutral" | "success" | "warning" {
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

export function DocumentLayoutRunStatus({
  projectId,
  documentId,
  runId,
  initialStatus
}: {
  documentId: string;
  initialStatus: LayoutRunStatus;
  projectId: string;
  runId: string;
}) {
  const [status, setStatus] = useState<LayoutRunStatus>(initialStatus);
  const [pollError, setPollError] = useState<string | null>(null);

  useEffect(() => {
    setStatus(initialStatus);
  }, [initialStatus]);

  useEffect(() => {
    if (!(status === "QUEUED" || status === "RUNNING")) {
      return;
    }
    let canceled = false;
    const poll = async () => {
      const result = await requestBrowserApi<DocumentLayoutRunStatusResponse>({
        method: "GET",
        path: `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}/status`,
        cacheClass: "operations-live"
      });
      if (canceled) {
        return;
      }
      if (!result.ok || !result.data) {
        setPollError(result.detail ?? "Layout run status polling unavailable.");
        return;
      }
      setPollError(null);
      setStatus(result.data.status);
    };
    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, POLL_INTERVAL_MS);
    return () => {
      canceled = true;
      window.clearInterval(timer);
    };
  }, [documentId, projectId, runId, status]);

  return (
    <div>
      <StatusChip tone={resolveTone(status)}>{status}</StatusChip>
      {pollError ? (
        <InlineAlert title="Polling degraded" tone="warning">
          {pollError}
        </InlineAlert>
      ) : null}
    </div>
  );
}
