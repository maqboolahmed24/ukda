import { bootstrapShellStates, bootstrapSurfaces } from "@ukde/contracts";
import type { ShellState } from "@ukde/contracts";
import { shellStateNotes } from "@ukde/ui";

const DEFAULT_API_ORIGIN = "http://127.0.0.1:8000";

function normalizeApiOrigin(
  origin: string | undefined,
  fallback: string
): string {
  const value = origin?.trim();
  if (!value) {
    return fallback;
  }
  return value.replace(/\/+$/, "");
}

export function resolveApiOrigins(options?: {
  publicOrigin?: string;
  internalOrigin?: string;
}): {
  publicOrigin: string;
  internalOrigin: string;
} {
  const publicOrigin = normalizeApiOrigin(
    options?.publicOrigin ?? process.env.NEXT_PUBLIC_UKDE_API_ORIGIN,
    DEFAULT_API_ORIGIN
  );
  const internalOrigin = normalizeApiOrigin(
    options?.internalOrigin ?? process.env.UKDE_API_ORIGIN_INTERNAL,
    publicOrigin
  );

  return {
    publicOrigin,
    internalOrigin
  };
}

export function resolveApiOrigin(explicitOrigin?: string): string {
  return resolveApiOrigins({ publicOrigin: explicitOrigin }).publicOrigin;
}

export function listShellStates(): Array<{ state: ShellState; note: string }> {
  return bootstrapShellStates.map((state) => ({
    state,
    note: shellStateNotes[state]
  }));
}

export { bootstrapSurfaces };
