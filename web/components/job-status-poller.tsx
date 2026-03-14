"use client";

import { useEffect, useState } from "react";

import type { ProjectJobStatusResponse } from "@ukde/contracts";
import { InlineAlert, InlineState, StatusChip } from "@ukde/ui/primitives";

import { queryCachePolicy } from "../lib/data/cache-policy";
import { requestBrowserApi } from "../lib/data/browser-api-client";

const TERMINAL_STATUSES = new Set(["SUCCEEDED", "FAILED", "CANCELED"]);

function resolveStatusTone(
  status: ProjectJobStatusResponse["status"]
): "success" | "warning" | "danger" | "info" {
  switch (status) {
    case "SUCCEEDED":
      return "success";
    case "FAILED":
      return "danger";
    case "CANCELED":
      return "warning";
    case "RUNNING":
      return "info";
    default:
      return "warning";
  }
}

interface JobStatusPollerProps {
  statusUrl: string;
  initialStatus: ProjectJobStatusResponse;
  pollMs?: number;
}

export function JobStatusPoller({
  statusUrl,
  initialStatus,
  pollMs = queryCachePolicy["operations-live"].pollIntervalMs ?? 4000
}: JobStatusPollerProps) {
  const [status, setStatus] = useState<ProjectJobStatusResponse>(initialStatus);
  const [error, setError] = useState<string | null>(null);
  const isTerminal = TERMINAL_STATUSES.has(status.status);

  useEffect(() => {
    if (isTerminal) {
      return;
    }
    let active = true;
    const interval = window.setInterval(async () => {
      const controller = new AbortController();
      try {
        const result = await requestBrowserApi<ProjectJobStatusResponse>({
          cacheClass: "operations-live",
          path: statusUrl,
          signal: controller.signal
        });
        if (!result.ok || !result.data) {
          if (active) {
            setError(
              result.detail ?? `status endpoint returned ${result.status}`
            );
          }
          return;
        }
        if (active) {
          setStatus(result.data);
          setError(null);
        }
      } catch {
        if (active) {
          setError("status polling failed");
        }
      } finally {
        controller.abort();
      }
    }, pollMs);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [isTerminal, pollMs, status.status, statusUrl]);

  return (
    <section className="settingsCard ukde-panel" aria-live="polite">
      <p className="ukde-eyebrow">Live status</p>
      <div className="auditIntegrityRow">
        <StatusChip tone={resolveStatusTone(status.status)}>
          {status.status}
        </StatusChip>
        <span className="ukde-muted">
          delivery attempts: {status.attempts}/{status.maxAttempts}
        </span>
      </div>
      <p className="ukde-muted">
        {isTerminal
          ? "Run reached a terminal state."
          : "Polling status endpoint for active updates."}
      </p>
      {status.cancelRequested ? (
        <p className="ukde-muted">
          Cancellation requested and waiting for worker acknowledgement.
        </p>
      ) : null}
      {status.errorCode ? (
        <InlineAlert title="Safe failure summary" tone="danger">
          {status.errorCode}
          {status.errorMessage ? `: ${status.errorMessage}` : ""}
        </InlineAlert>
      ) : null}
      {error ? (
        <InlineState
          kind="degraded"
          title="Status polling degraded"
          description={error}
        />
      ) : null}
    </section>
  );
}
