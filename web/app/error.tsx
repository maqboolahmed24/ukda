"use client";

import { useEffect } from "react";

import { RouteErrorState } from "../components/route-error-state";
import { routeErrorCopy } from "../lib/route-state-copy";

const CHUNK_RELOAD_SESSION_KEY_PREFIX = "ukde.chunk-reload.";

function isChunkLoadError(error: Error | null | undefined): boolean {
  const signature = `${error?.name ?? ""} ${error?.message ?? ""}`.toLowerCase();
  return (
    signature.includes("chunkloaderror") ||
    signature.includes("loading chunk") ||
    signature.includes("chunk load failed")
  );
}

export default function GlobalError({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (!isChunkLoadError(error)) {
      return;
    }

    const reloadKey = `${CHUNK_RELOAD_SESSION_KEY_PREFIX}${window.location.pathname}`;
    try {
      if (window.sessionStorage.getItem(reloadKey) === "1") {
        return;
      }
      window.sessionStorage.setItem(reloadKey, "1");
    } catch {
      // no-op: if storage is unavailable, continue to reload once.
    }
    window.location.reload();
  }, [error]);

  return (
    <RouteErrorState {...routeErrorCopy.app} reset={reset} />
  );
}
