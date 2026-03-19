"use client";

import { useEffect, useState } from "react";
import type { DocumentPreprocessRunStatusResponse, PreprocessRunStatus } from "@ukde/contracts";
import { InlineAlert, StatusChip } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";
import { RecoveryModeBanner } from "./recovery-mode-banner";

const POLL_INTERVAL_MS = 5_000;

function resolveTone(status: PreprocessRunStatus): "danger" | "neutral" | "success" | "warning" {
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

export function DocumentPreprocessRunStatus({
  projectId,
  documentId,
  runId,
  initialStatus
}: {
  documentId: string;
  initialStatus: PreprocessRunStatus;
  projectId: string;
  runId: string;
}) {
  const [status, setStatus] = useState<PreprocessRunStatus>(initialStatus);
  const [pollError, setPollError] = useState<string | null>(null);
  const isPollingActive = status === "QUEUED" || status === "RUNNING";

  useEffect(() => {
    setStatus(initialStatus);
  }, [initialStatus]);

  useEffect(() => {
    if (!isPollingActive) {
      return;
    }
    let canceled = false;
    const poll = async () => {
      const result = await requestBrowserApi<DocumentPreprocessRunStatusResponse>({
        method: "GET",
        path: `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/status`,
        cacheClass: "operations-live"
      });
      if (canceled) {
        return;
      }
      if (!result.ok || !result.data) {
        setPollError(result.detail ?? "Run status polling unavailable.");
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
  }, [documentId, isPollingActive, projectId, runId, status]);

  return (
    <div>
      <StatusChip tone={resolveTone(status)}>{status}</StatusChip>
      <RecoveryModeBanner pollingActive={isPollingActive} />
      {pollError ? (
        <InlineAlert title="Polling degraded" tone="warning">
          {pollError}. The run may still be processing server-side; this degraded state is distinct from run failure.
        </InlineAlert>
      ) : null}
    </div>
  );
}
