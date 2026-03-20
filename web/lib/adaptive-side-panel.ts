import { useCallback, useEffect, useMemo, useState } from "react";
import type { ShellState } from "@ukde/contracts";
import {
  isPanelSection,
  type SidePanelSection
} from "./panel-sections";

export { normalizePanelSectionParam } from "./panel-sections";
export type { SidePanelSection } from "./panel-sections";

export interface SidePanelLayoutState {
  showAside: boolean;
  showDrawerToggle: boolean;
}

export interface BuildAdaptivePanelStorageKeyOptions {
  surface: string;
  projectId?: string | null;
  documentId?: string | null;
}

export interface UseAdaptiveSidePanelStateOptions {
  shellState: ShellState;
  storageSurface: string;
  projectId?: string | null;
  documentId?: string | null;
  initialSection?: SidePanelSection;
}

export interface UseAdaptiveSidePanelState {
  panelSection: SidePanelSection;
  setPanelSection: (section: SidePanelSection) => void;
  drawerOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
  showAside: boolean;
  showDrawerToggle: boolean;
  storageKey: string;
}

function normalizeStorageToken(
  value: string | null | undefined,
  fallback: string
): string {
  if (typeof value !== "string") {
    return fallback;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : fallback;
}

export function resolveSidePanelLayoutState(
  shellState: ShellState
): SidePanelLayoutState {
  const showAside = shellState === "Expanded" || shellState === "Balanced";
  return {
    showAside,
    showDrawerToggle: !showAside
  };
}

export function buildAdaptivePanelStorageKey(
  options: BuildAdaptivePanelStorageKeyOptions
): string {
  const surface = normalizeStorageToken(options.surface, "panel");
  const projectId = normalizeStorageToken(options.projectId, "global");
  const documentId = normalizeStorageToken(options.documentId, "");
  return documentId.length > 0
    ? `ukde.panel.v2:${surface}:${projectId}:${documentId}`
    : `ukde.panel.v2:${surface}:${projectId}`;
}

export function readPersistedPanelSection(
  storageKey: string
): SidePanelSection | undefined {
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) {
      return undefined;
    }
    const parsed = JSON.parse(raw) as { panelSection?: unknown };
    return typeof parsed.panelSection === "string" &&
      isPanelSection(parsed.panelSection)
      ? parsed.panelSection
      : undefined;
  } catch {
    return undefined;
  }
}

export function useAdaptiveSidePanelState({
  shellState,
  storageSurface,
  projectId,
  documentId,
  initialSection
}: UseAdaptiveSidePanelStateOptions): UseAdaptiveSidePanelState {
  const [panelSection, setPanelSection] = useState<SidePanelSection>(
    initialSection ?? "context"
  );
  const [drawerOpen, setDrawerOpen] = useState(false);

  const { showAside, showDrawerToggle } = useMemo(
    () => resolveSidePanelLayoutState(shellState),
    [shellState]
  );
  const storageKey = useMemo(
    () =>
      buildAdaptivePanelStorageKey({
        surface: storageSurface,
        projectId,
        documentId
      }),
    [documentId, projectId, storageSurface]
  );

  useEffect(() => {
    if (initialSection) {
      setPanelSection(initialSection);
      return;
    }
    const persisted = readPersistedPanelSection(storageKey);
    if (persisted) {
      setPanelSection(persisted);
    } else {
      setPanelSection("context");
    }
  }, [initialSection, storageKey]);

  useEffect(() => {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify({ panelSection }));
    } catch {}
  }, [panelSection, storageKey]);

  useEffect(() => {
    if (showAside) {
      setDrawerOpen(false);
    }
  }, [showAside]);

  const openDrawer = useCallback(() => setDrawerOpen(true), []);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  return {
    panelSection,
    setPanelSection,
    drawerOpen,
    openDrawer,
    closeDrawer,
    showAside,
    showDrawerToggle,
    storageKey
  };
}
