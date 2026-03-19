"use client";

import { useEffect, useState } from "react";

import type { ProjectIndexStatusResponse } from "@ukde/contracts";
import { InlineAlert, InlineState, StatusChip } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";
import { queryCachePolicy } from "../lib/data/cache-policy";

const TERMINAL_STATUSES = new Set(["SUCCEEDED", "FAILED", "CANCELED"]);

function resolveStatusTone(
  status: ProjectIndexStatusResponse["status"]
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

interface IndexStatusPollerProps {
  statusUrl: string;
  initialStatus: ProjectIndexStatusResponse;
  pollMs?: number;
}

export function IndexStatusPoller({
  statusUrl,
  initialStatus,
  pollMs = queryCachePolicy["operations-live"].pollIntervalMs ?? 4000
}: IndexStatusPollerProps) {
  const [status, setStatus] = useState<ProjectIndexStatusResponse>(initialStatus);
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
        const result = await requestBrowserApi<ProjectIndexStatusResponse>({
          cacheClass: "operations-live",
          path: statusUrl,
          signal: controller.signal
        });
        if (!result.ok || !result.data) {
          if (active) {
            setError(result.detail ?? `status endpoint returned ${result.status}`);
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
      <p className="ukde-eyebrow">Live index status</p>
      <div className="auditIntegrityRow">
        <StatusChip tone={resolveStatusTone(status.status)}>
          {status.status}
        </StatusChip>
      </div>
      <p className="ukde-muted">
        {isTerminal
          ? "Generation reached a terminal state."
          : "Polling status endpoint for active updates."}
      </p>
      {status.cancelRequested ? (
        <p className="ukde-muted">
          Cancellation requested. A running generation remains active until worker cooperative shutdown completes.
        </p>
      ) : null}
      {status.failureReason ? (
        <InlineAlert title="Safe failure summary" tone="danger">
          {status.failureReason}
        </InlineAlert>
      ) : null}
      {error ? (
        <InlineState
          kind="degraded"
          title="Status polling degraded"
          description={`${error}. Generation execution may continue server-side; this does not mean data loss or a terminal failure.`}
        />
      ) : null}
    </section>
  );
}
