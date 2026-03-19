"use client";

import { useEffect, useState } from "react";

import type { RecoveryStatusResponse } from "@ukde/contracts";
import { InlineAlert } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";

const POLL_INTERVAL_MS = 15_000;

interface RecoveryModeState {
  degraded: boolean;
  summary: string;
}

export function RecoveryModeBanner({
  pollingActive
}: {
  pollingActive: boolean;
}) {
  const [status, setStatus] = useState<RecoveryModeState | null>(null);
  const [disabledForRole, setDisabledForRole] = useState(false);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  useEffect(() => {
    if (!pollingActive || disabledForRole) {
      return;
    }
    let canceled = false;
    const poll = async () => {
      const result = await requestBrowserApi<RecoveryStatusResponse>({
        method: "GET",
        path: "/admin/recovery/status",
        cacheClass: "operations-live"
      });
      if (canceled) {
        return;
      }
      if (!result.ok || !result.data) {
        if (result.status === 401 || result.status === 403) {
          setDisabledForRole(true);
          setStatus(null);
          setErrorDetail(null);
          return;
        }
        setErrorDetail(result.detail ?? "Recovery status polling unavailable.");
        return;
      }
      setErrorDetail(null);
      setStatus({
        degraded: result.data.degraded,
        summary: result.data.summary
      });
    };
    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, POLL_INTERVAL_MS);
    return () => {
      canceled = true;
      window.clearInterval(timer);
    };
  }, [disabledForRole, pollingActive]);

  if (!pollingActive || disabledForRole) {
    return null;
  }

  if (status?.degraded) {
    return (
      <InlineAlert title="Recovery mode active" tone="warning">
        {status.summary} This indicates temporary degraded recovery posture, not permanent data loss.
      </InlineAlert>
    );
  }

  if (errorDetail) {
    return (
      <InlineAlert title="Recovery status polling degraded" tone="info">
        {errorDetail} This does not imply that the active run has failed.
      </InlineAlert>
    );
  }

  return null;
}
