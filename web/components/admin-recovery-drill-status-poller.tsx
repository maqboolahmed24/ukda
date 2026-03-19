"use client";

import { useEffect, useState } from "react";

import type { RecoveryDrillStatusResponse, RecoveryDrillStatus } from "@ukde/contracts";
import { InlineAlert, StatusChip } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";

const POLL_INTERVAL_MS = 5_000;

function statusTone(status: RecoveryDrillStatus): "success" | "warning" | "danger" | "neutral" | "info" {
  if (status === "SUCCEEDED") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  if (status === "RUNNING") {
    return "info";
  }
  return "warning";
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toISOString();
}

export function AdminRecoveryDrillStatusPoller({
  drillId,
  initialStatus
}: {
  drillId: string;
  initialStatus: RecoveryDrillStatusResponse;
}) {
  const [status, setStatus] = useState(initialStatus);
  const [pollError, setPollError] = useState<string | null>(null);
  const shouldPoll = status.status === "QUEUED" || status.status === "RUNNING";

  useEffect(() => {
    setStatus(initialStatus);
    setPollError(null);
  }, [initialStatus]);

  useEffect(() => {
    if (!shouldPoll) {
      return;
    }
    let canceled = false;
    const poll = async () => {
      const result = await requestBrowserApi<RecoveryDrillStatusResponse>({
        method: "GET",
        path: `/admin/recovery/drills/${encodeURIComponent(drillId)}/status`,
        cacheClass: "operations-live"
      });
      if (canceled) {
        return;
      }
      if (!result.ok || !result.data) {
        setPollError(result.detail ?? "Recovery drill status polling unavailable.");
        return;
      }
      setPollError(null);
      setStatus(result.data);
    };
    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, POLL_INTERVAL_MS);
    return () => {
      canceled = true;
      window.clearInterval(timer);
    };
  }, [drillId, shouldPoll]);

  return (
    <div className="ukde-stack-sm">
      <StatusChip tone={statusTone(status.status)}>{status.status}</StatusChip>
      <ul className="projectMetaList">
        <li>
          <span>Started</span>
          <strong>{formatTimestamp(status.startedAt)}</strong>
        </li>
        <li>
          <span>Finished</span>
          <strong>{formatTimestamp(status.finishedAt)}</strong>
        </li>
        <li>
          <span>Canceled</span>
          <strong>{formatTimestamp(status.canceledAt)}</strong>
        </li>
      </ul>
      {pollError ? (
        <InlineAlert title="Status polling degraded" tone="warning">
          {pollError} Recovery drill execution may still be progressing server-side.
        </InlineAlert>
      ) : null}
    </div>
  );
}
