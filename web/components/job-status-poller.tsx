"use client";

import { useEffect, useState } from "react";

import type { ProjectJobStatusResponse } from "@ukde/contracts";

const TERMINAL_STATUSES = new Set(["SUCCEEDED", "FAILED", "CANCELED"]);

interface JobStatusPollerProps {
  statusUrl: string;
  initialStatus: ProjectJobStatusResponse;
  pollMs?: number;
}

export function JobStatusPoller({
  statusUrl,
  initialStatus,
  pollMs = 4000
}: JobStatusPollerProps) {
  const [status, setStatus] = useState<ProjectJobStatusResponse>(initialStatus);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (TERMINAL_STATUSES.has(status.status)) {
      return;
    }
    let active = true;
    const interval = window.setInterval(async () => {
      try {
        const response = await fetch(statusUrl, {
          cache: "no-store",
          credentials: "same-origin"
        });
        if (!response.ok) {
          if (active) {
            setError(`status endpoint returned ${response.status}`);
          }
          return;
        }
        const parsed = (await response.json()) as ProjectJobStatusResponse;
        if (active) {
          setStatus(parsed);
          setError(null);
        }
      } catch {
        if (active) {
          setError("status polling failed");
        }
      }
    }, pollMs);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [pollMs, status.status, statusUrl]);

  return (
    <section className="settingsCard ukde-panel" aria-live="polite">
      <p className="ukde-eyebrow">Live status</p>
      <h3>{status.status}</h3>
      <p className="ukde-muted">
        delivery attempts: {status.attempts}/{status.maxAttempts}
      </p>
      {status.cancelRequested ? (
        <p className="ukde-muted">
          Cancellation requested and waiting for worker acknowledgement.
        </p>
      ) : null}
      {status.errorCode ? (
        <p className="ukde-muted">
          {status.errorCode}
          {status.errorMessage ? `: ${status.errorMessage}` : ""}
        </p>
      ) : null}
      {error ? <p className="ukde-muted">Polling: {error}</p> : null}
    </section>
  );
}
