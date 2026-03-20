"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  startTransition,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import type {
  DocumentPageVariantsResponse,
  DocumentPreprocessRun,
  DocumentStatus,
  ProjectDocumentPage,
  ProjectDocumentPageDetail,
  ShellState
} from "@ukde/contracts";

import {
  Drawer,
  DetailsDrawer,
  SectionState,
  StatusChip,
  Toolbar
} from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";
import { projectDocumentPageImagePath } from "../lib/document-page-image";
import {
  projectDocumentPreprocessingComparePath,
  projectDocumentPreprocessingQualityPath,
  projectDocumentIngestStatusPath,
  projectDocumentPath,
  projectDocumentPreprocessingPath,
  type ViewerComparePair,
  type ViewerMode,
  projectDocumentViewerPath,
  projectDocumentsPath
} from "../lib/routes";
import {
  VIEWER_ZOOM_DEFAULT,
  VIEWER_ZOOM_MAX,
  VIEWER_ZOOM_MIN
} from "../lib/url-state";
import {
  useAdaptiveSidePanelState,
  type SidePanelSection
} from "../lib/adaptive-side-panel";

const ZOOM_STEP_PERCENT = 10;
const FILMSTRIP_SCROLL_STORAGE_PREFIX = "ukde.viewer.filmstrip-scroll";
const PANEL_PRESET_STORAGE_PREFIX = "ukde.viewer.panel-presets";
const PROCESSING_STATUSES: Set<DocumentStatus> = new Set([
  "UPLOADING",
  "QUEUED",
  "SCANNING",
  "EXTRACTING"
]);
const DOCUMENT_STATUS_TONES: Record<
  DocumentStatus,
  "danger" | "neutral" | "success" | "warning"
> = {
  UPLOADING: "warning",
  QUEUED: "warning",
  SCANNING: "warning",
  EXTRACTING: "warning",
  READY: "success",
  FAILED: "danger",
  CANCELED: "neutral"
};
const FILMSTRIP_PRESET_WIDTHS: Record<"default" | "narrow" | "wide", number> = {
  narrow: 160,
  default: 206,
  wide: 252
};
const INSPECTOR_PRESET_WIDTHS: Record<"default" | "narrow" | "wide", number> = {
  narrow: 228,
  default: 268,
  wide: 316
};
const VIEWER_WORKSPACE_STATES: ShellState[] = [
  "Expanded",
  "Balanced",
  "Compact",
  "Focus"
];
const VIEWER_MODES: readonly ViewerMode[] = [
  "original",
  "preprocessed",
  "compare"
];
const VIEWER_COMPARE_PAIRS: readonly ViewerComparePair[] = [
  "original_gray",
  "original_binary",
  "gray_binary"
];

type PanelPreset = "default" | "narrow" | "wide";

interface PanOffset {
  x: number;
  y: number;
}

interface DragState {
  originPan: PanOffset;
  pointerId: number;
  startX: number;
  startY: number;
}

interface ViewportSize {
  height: number;
  width: number;
}

interface ProjectDocumentViewerShellProps {
  activePreprocessRunId: string | null;
  currentPage: number;
  currentPageDetail: ProjectDocumentPageDetail | null;
  currentPageError: string | null;
  documentId: string;
  documentName: string;
  documentStatus: DocumentStatus;
  initialComparePair: ViewerComparePair;
  initialPanelSection: SidePanelSection;
  initialRunId?: string;
  initialViewerMode: ViewerMode;
  initialZoomPercent: number;
  pageCount: number;
  pages: ProjectDocumentPage[];
  preprocessRuns: DocumentPreprocessRun[];
  preprocessingComparePath?: string;
  projectId: string;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function normalizeRotation(rotation: number): number {
  const bounded = rotation % 360;
  return bounded < 0 ? bounded + 360 : bounded;
}

function roundZoomPercent(value: number): number {
  return Math.round(value);
}

function isTextEntryTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  if (target.isContentEditable) {
    return true;
  }
  const tagName = target.tagName.toUpperCase();
  return tagName === "INPUT" || tagName === "SELECT" || tagName === "TEXTAREA";
}

function isShellState(value: string | null): value is ShellState {
  return VIEWER_WORKSPACE_STATES.includes(value as ShellState);
}

function formatMetricValue(value: unknown): string {
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (typeof value === "string") {
    return value;
  }
  if (value === null || typeof value === "undefined") {
    return "N/A";
  }
  try {
    return JSON.stringify(value);
  } catch {
    return "N/A";
  }
}

function resolvePanelWidth(
  state: ShellState,
  preset: PanelPreset,
  widths: Record<PanelPreset, number>
): number {
  const base = widths[preset];
  if (state === "Balanced") {
    return Math.max(144, Math.round(base * 0.86));
  }
  if (state === "Compact") {
    return Math.max(126, Math.round(base * 0.72));
  }
  if (state === "Focus") {
    return Math.max(108, Math.round(base * 0.62));
  }
  return base;
}

function resolveCanvasStateCopy({
  currentPage,
  currentPageDetail,
  currentPageError,
  documentStatus,
  pageCount
}: {
  currentPage: number;
  currentPageDetail: ProjectDocumentPageDetail | null;
  currentPageError: string | null;
  documentStatus: DocumentStatus;
  pageCount: number;
}): {
  description: string;
  kind: "degraded" | "disabled" | "empty" | "error" | "loading";
  title: string;
} | null {
  if (currentPageError) {
    return {
      kind: "error",
      title: "Page metadata unavailable",
      description: currentPageError
    };
  }

  if (!currentPageDetail) {
    if (PROCESSING_STATUSES.has(documentStatus)) {
      return {
        kind: "loading",
        title: `Page ${currentPage} is still processing`,
        description: "Extraction and thumbnail rendering are still in progress."
      };
    }
    if (documentStatus === "READY" && pageCount === 0) {
      return {
        kind: "degraded",
        title: "No pages are available yet",
        description:
          "Document status is READY but page records are absent. Review timeline entries for extraction outcomes."
      };
    }
    if (documentStatus === "FAILED" || documentStatus === "CANCELED") {
      return {
        kind: "error",
        title: "Viewer is not available for this document",
        description:
          "Latest ingest is not in a ready state. Use ingest status to review the last reached stage."
      };
    }
    return {
      kind: "empty",
      title: "No page selected",
      description:
        "Select a page from the filmstrip once page records are available."
    };
  }

  if (
    currentPageDetail.status === "FAILED" ||
    currentPageDetail.status === "CANCELED"
  ) {
    return {
      kind: "error",
      title: `Page ${currentPage} is unavailable`,
      description:
        currentPageDetail.failureReason ??
        "This page cannot be rendered in the viewer."
    };
  }

  if (currentPageDetail.status === "PENDING") {
    return {
      kind: "loading",
      title: `Page ${currentPage} is still processing`,
      description: "Extraction and thumbnail rendering are still in progress."
    };
  }

  if (
    currentPageDetail.status === "READY" &&
    !currentPageDetail.derivedImageAvailable
  ) {
    return {
      kind: "degraded",
      title: `Page ${currentPage} metadata is ready but image bytes are pending`,
      description:
        "Refresh shortly. The same-origin proxy endpoint will serve the image when materialized."
    };
  }

  return null;
}

export function ProjectDocumentViewerShell({
  activePreprocessRunId,
  currentPage,
  currentPageDetail,
  currentPageError,
  documentId,
  documentName,
  documentStatus,
  initialComparePair,
  initialPanelSection,
  initialRunId,
  initialViewerMode,
  initialZoomPercent,
  pageCount,
  pages,
  preprocessRuns,
  preprocessingComparePath,
  projectId
}: ProjectDocumentViewerShellProps) {
  const router = useRouter();
  const [viewerMode, setViewerMode] = useState<ViewerMode>(initialViewerMode);
  const [comparePair, setComparePair] =
    useState<ViewerComparePair>(initialComparePair);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(
    initialRunId ?? activePreprocessRunId
  );
  const [shellState, setShellState] = useState<ShellState>("Expanded");
  const [filmstripDrawerOpen, setFilmstripDrawerOpen] = useState(false);
  const [pageDetail, setPageDetail] =
    useState<ProjectDocumentPageDetail | null>(currentPageDetail);
  const [zoomPercent, setZoomPercent] = useState(initialZoomPercent);
  const [filmstripPreset, setFilmstripPreset] = useState<PanelPreset>("default");
  const [inspectorPreset, setInspectorPreset] = useState<PanelPreset>("default");
  const [panOffset, setPanOffset] = useState<PanOffset>({ x: 0, y: 0 });
  const [pageJumpValue, setPageJumpValue] = useState(String(currentPage));
  const [rotationSaving, setRotationSaving] = useState(false);
  const [rotationError, setRotationError] = useState<string | null>(null);
  const [viewportSize, setViewportSize] = useState<ViewportSize>({
    width: 0,
    height: 0
  });
  const [isDragging, setIsDragging] = useState(false);
  const [canvasImageFailed, setCanvasImageFailed] = useState(false);
  const [canvasImageFailureKind, setCanvasImageFailureKind] = useState<
    "forbidden" | "missing" | "session" | "unknown"
  >("unknown");
  const [pageVariants, setPageVariants] =
    useState<DocumentPageVariantsResponse | null>(null);
  const [pageVariantsLoading, setPageVariantsLoading] = useState(false);
  const [pageVariantsError, setPageVariantsError] = useState<string | null>(null);
  const [compareOriginalImageFailed, setCompareOriginalImageFailed] =
    useState(false);
  const [comparePreprocessedImageFailed, setComparePreprocessedImageFailed] =
    useState(false);
  const [copyLinkStatus, setCopyLinkStatus] = useState<
    "idle" | "copied" | "failed"
  >("idle");

  const dragStateRef = useRef<DragState | null>(null);
  const filmstripRef = useRef<HTMLElement | null>(null);
  const canvasRef = useRef<HTMLElement | null>(null);
  const canvasViewportRef = useRef<HTMLDivElement | null>(null);

  const totalPages = Math.max(1, pageCount);
  const selectedRun = preprocessRuns.find((run) => run.id === selectedRunId) ?? null;
  const resolvedRunId =
    pageVariants?.resolvedRunId ?? selectedRun?.id ?? activePreprocessRunId;
  const compareBaseRunId =
    preprocessRuns.find((run) => run.id !== resolvedRunId)?.id ?? null;
  const runRequired = viewerMode !== "original";
  const hasRunContext = Boolean(resolvedRunId);
  const runContextError = runRequired && !hasRunContext
    ? "No active preprocess run is available. Activate a run or select one explicitly."
    : null;
  const normalizedRotation = normalizeRotation(pageDetail?.viewerRotation ?? 0);
  const rotationSwapsAxes = normalizedRotation % 180 !== 0;

  const intrinsicWidth = pageDetail?.width ?? 1;
  const intrinsicHeight = pageDetail?.height ?? 1;
  const transformedWidth = rotationSwapsAxes ? intrinsicHeight : intrinsicWidth;
  const transformedHeight = rotationSwapsAxes
    ? intrinsicWidth
    : intrinsicHeight;

  const imageScale = zoomPercent / 100;
  const scaledWidth = transformedWidth * imageScale;
  const scaledHeight = transformedHeight * imageScale;
  const maxPanX = Math.max((scaledWidth - viewportSize.width) / 2, 0);
  const maxPanY = Math.max((scaledHeight - viewportSize.height) / 2, 0);

  const originalPageImagePath =
    pageDetail?.id &&
    pageDetail.status === "READY" &&
    pageDetail.derivedImageAvailable
      ? projectDocumentPageImagePath(
          projectId,
          documentId,
          pageDetail.id,
          "full"
        )
      : null;
  const preprocessedGrayVariant =
    pageVariants?.variants.find((variant) => variant.imageVariant === "preprocessed_gray") ??
    null;
  const preprocessedBinVariant =
    pageVariants?.variants.find((variant) => variant.imageVariant === "preprocessed_bin") ??
    null;
  const preprocessedGrayImagePath =
    pageDetail?.id &&
    pageDetail.status === "READY" &&
    resolvedRunId
      ? projectDocumentPageImagePath(
          projectId,
          documentId,
          pageDetail.id,
          "preprocessed_gray",
          { runId: resolvedRunId }
        )
      : null;
  const preprocessedBinImagePath =
    pageDetail?.id &&
    pageDetail.status === "READY" &&
    resolvedRunId
      ? projectDocumentPageImagePath(
          projectId,
          documentId,
          pageDetail.id,
          "preprocessed_bin",
          { runId: resolvedRunId }
        )
      : null;
  const comparePairNeedsGray =
    comparePair === "original_gray" || comparePair === "gray_binary";
  const comparePairNeedsBin =
    comparePair === "original_binary" || comparePair === "gray_binary";
  const compareGrayUnavailable =
    comparePairNeedsGray &&
    preprocessedGrayVariant !== null &&
    !preprocessedGrayVariant.available;
  const compareBinUnavailable =
    comparePairNeedsBin &&
    preprocessedBinVariant !== null &&
    !preprocessedBinVariant.available;
  const compareLeftLabel =
    comparePair === "gray_binary" ? "Gray" : "Original";
  const compareRightLabel =
    comparePair === "original_gray"
      ? "Gray"
      : comparePair === "original_binary"
        ? "Binary"
        : "Binary";
  const compareLeftImagePath =
    comparePair === "gray_binary" ? preprocessedGrayImagePath : originalPageImagePath;
  const compareRightImagePath =
    comparePair === "original_gray"
      ? preprocessedGrayImagePath
      : comparePair === "original_binary"
        ? preprocessedBinImagePath
        : preprocessedBinImagePath;
  const singleCanvasImagePath =
    viewerMode === "preprocessed" ? preprocessedGrayImagePath : originalPageImagePath;
  const primaryVariantUnavailable =
    viewerMode === "preprocessed" &&
    preprocessedGrayVariant !== null &&
    !preprocessedGrayVariant.available;
  const compareVariantUnavailable =
    viewerMode === "compare" && (compareGrayUnavailable || compareBinUnavailable);
  const compareUnavailableLabel =
    compareBinUnavailable && compareGrayUnavailable
      ? "grayscale and binary outputs"
      : compareBinUnavailable
        ? "binary output"
        : "grayscale output";

  const canvasState = resolveCanvasStateCopy({
    currentPage,
    currentPageDetail: pageDetail,
    currentPageError,
    documentStatus,
    pageCount
  });
  const effectiveCanvasState =
    singleCanvasImagePath && canvasImageFailed
      ? {
          kind: "error" as const,
          title:
            canvasImageFailureKind === "session"
              ? "Session expired while loading page image"
              : canvasImageFailureKind === "forbidden"
                ? "Access to this page image is denied"
                : canvasImageFailureKind === "missing"
                  ? `Page ${currentPage} image is missing`
                  : `Page ${currentPage} image is unavailable`,
          description:
            canvasImageFailureKind === "session"
              ? "Re-authenticate and retry the route. URL context is preserved."
              : canvasImageFailureKind === "forbidden"
                ? "Your current role no longer has access to this page in the current project scope."
                : canvasImageFailureKind === "missing"
                  ? "The derived page asset is no longer present. Review ingest status for the last extraction attempt."
                  : "Image delivery failed or your session may have expired. Review ingest status before retrying."
        }
      : runContextError
        ? {
            kind: "error" as const,
            title: "Preprocess run selection is required",
            description: runContextError
          }
        : viewerMode !== "original" && pageVariantsLoading
          ? {
              kind: "loading" as const,
              title: "Loading preprocess variant context",
              description: "Resolving run-scoped variants and metrics for this page."
            }
          : viewerMode !== "original" && pageVariantsError
            ? {
                kind: "error" as const,
                title: "Preprocess variants unavailable",
                description: pageVariantsError
              }
            : primaryVariantUnavailable || compareVariantUnavailable
              ? {
                  kind: "degraded" as const,
                  title: "Preprocessed image is not ready for this page",
                  description:
                    `Selected run did not materialize ${compareUnavailableLabel} for this page yet.`
                }
              : canvasState;

  const canPan =
    viewerMode !== "compare" &&
    Boolean(singleCanvasImagePath) &&
    (maxPanX > 0.5 || maxPanY > 0.5);
  const filmstripScrollStorageKey = `${FILMSTRIP_SCROLL_STORAGE_PREFIX}:${projectId}:${documentId}`;
  const panelPresetStorageKey = `${PANEL_PRESET_STORAGE_PREFIX}:${projectId}`;
  const {
    closeDrawer: closeInspectorDrawer,
    drawerOpen: inspectorDrawerOpen,
    openDrawer: openInspectorDrawer,
    panelSection: inspectorPanelSection,
    setPanelSection: setInspectorPanelSection,
    showAside: showInspectorAside,
    showDrawerToggle: showInspectorDrawerToggle
  } = useAdaptiveSidePanelState({
    shellState,
    storageSurface: "viewer-inspector",
    projectId,
    documentId,
    initialSection: initialPanelSection
  });

  const currentViewerPath = projectDocumentViewerPath(
    projectId,
    documentId,
    currentPage,
    {
      comparePair: viewerMode === "compare" ? comparePair : undefined,
      mode: viewerMode,
      panel: inspectorPanelSection,
      runId: resolvedRunId ?? undefined,
      zoom: zoomPercent
    }
  );
  const currentIngestStatusPath = projectDocumentIngestStatusPath(
    projectId,
    documentId,
    { page: currentPage, zoom: zoomPercent }
  );
  const currentDocumentPath = projectDocumentPath(projectId, documentId);
  const currentPreprocessingPath = projectDocumentPreprocessingPath(
    projectId,
    documentId
  );
  const currentQualityPath = projectDocumentPreprocessingQualityPath(
    projectId,
    documentId,
    {
      runId: resolvedRunId ?? undefined,
      pageSize: 25
    }
  );
  const currentComparePath = projectDocumentPreprocessingComparePath(
    projectId,
    documentId,
    compareBaseRunId,
    resolvedRunId,
    {
      page: currentPage,
      viewerComparePair: viewerMode === "compare" ? comparePair : undefined,
      viewerMode: viewerMode,
      viewerRunId: resolvedRunId ?? undefined
    }
  );
  const preferredComparePath =
    currentComparePath || preprocessingComparePath || currentPreprocessingPath;
  const backToDocumentsPath = projectDocumentsPath(projectId);
  const showFilmstripAside = shellState !== "Focus";
  const filmstripWidth = resolvePanelWidth(
    shellState,
    filmstripPreset,
    FILMSTRIP_PRESET_WIDTHS
  );
  const inspectorWidth = resolvePanelWidth(
    shellState,
    inspectorPreset,
    INSPECTOR_PRESET_WIDTHS
  );
  const workspaceStyle = {
    "--viewer-filmstrip-width": `${filmstripWidth}px`,
    "--viewer-inspector-width": `${inspectorWidth}px`
  } as CSSProperties;
  const canvasRecoveryActions = (
    <div className="buttonRow">
      <Link className="secondaryButton" href={currentIngestStatusPath}>
        View ingest status
      </Link>
      <Link className="secondaryButton" href={currentDocumentPath}>
        Open document
      </Link>
      <Link className="secondaryButton" href={currentPreprocessingPath}>
        Open preprocessing
      </Link>
      <Link className="secondaryButton" href={backToDocumentsPath}>
        Back to documents
      </Link>
    </div>
  );

  useEffect(() => {
    setPageDetail(currentPageDetail);
  }, [currentPageDetail]);

  useEffect(() => {
    setViewerMode(initialViewerMode);
  }, [initialViewerMode]);

  useEffect(() => {
    setComparePair(initialComparePair);
  }, [initialComparePair]);

  useEffect(() => {
    if (initialRunId && initialRunId !== selectedRunId) {
      setSelectedRunId(initialRunId);
      return;
    }
    if (!initialRunId && !selectedRunId && activePreprocessRunId) {
      setSelectedRunId(activePreprocessRunId);
    }
  }, [activePreprocessRunId, initialRunId, selectedRunId]);

  useEffect(() => {
    if (!selectedRunId) {
      return;
    }
    if (preprocessRuns.some((run) => run.id === selectedRunId)) {
      return;
    }
    setSelectedRunId(activePreprocessRunId ?? null);
  }, [activePreprocessRunId, preprocessRuns, selectedRunId]);

  useEffect(() => {
    const shellElement =
      document.querySelector<HTMLElement>(".authenticatedShell");
    if (!shellElement) {
      return;
    }
    const syncShellState = () => {
      const raw = shellElement.getAttribute("data-shell-state");
      if (isShellState(raw)) {
        setShellState(raw);
      }
    };
    syncShellState();
    const observer = new MutationObserver(syncShellState);
    observer.observe(shellElement, {
      attributes: true,
      attributeFilter: ["data-shell-state"]
    });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(panelPresetStorageKey);
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw) as {
        filmstrip?: unknown;
        inspector?: unknown;
      };
      if (
        parsed.filmstrip === "default" ||
        parsed.filmstrip === "narrow" ||
        parsed.filmstrip === "wide"
      ) {
        setFilmstripPreset(parsed.filmstrip);
      }
      if (
        parsed.inspector === "default" ||
        parsed.inspector === "narrow" ||
        parsed.inspector === "wide"
      ) {
        setInspectorPreset(parsed.inspector);
      }
    } catch {}
  }, [panelPresetStorageKey]);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        panelPresetStorageKey,
        JSON.stringify({
          filmstrip: filmstripPreset,
          inspector: inspectorPreset
        })
      );
    } catch {}
  }, [filmstripPreset, inspectorPreset, panelPresetStorageKey]);

  useEffect(() => {
    if (showInspectorAside) {
      closeInspectorDrawer();
    }
    if (shellState !== "Focus") {
      setFilmstripDrawerOpen(false);
    }
  }, [closeInspectorDrawer, shellState, showInspectorAside]);

  useEffect(() => {
    setPageJumpValue(String(currentPage));
    setPanOffset({ x: 0, y: 0 });
    setRotationError(null);
    setCanvasImageFailed(false);
    setCanvasImageFailureKind("unknown");
    setCompareOriginalImageFailed(false);
    setComparePreprocessedImageFailed(false);
  }, [currentPage, pageDetail?.id]);

  useEffect(() => {
    setZoomPercent(initialZoomPercent);
    setPanOffset({ x: 0, y: 0 });
  }, [currentPage, initialZoomPercent]);

  useEffect(() => {
    if (viewerMode === "original") {
      setPageVariants(null);
      setPageVariantsLoading(false);
      setPageVariantsError(null);
      return;
    }
    if (!pageDetail?.id) {
      setPageVariants(null);
      setPageVariantsLoading(false);
      setPageVariantsError(null);
      return;
    }

    let canceled = false;
    const runIdQuery =
      selectedRunId && selectedRunId.trim().length > 0
        ? `?runId=${encodeURIComponent(selectedRunId.trim())}`
        : "";
    setPageVariantsLoading(true);
    setPageVariantsError(null);

    const loadVariants = async () => {
      const result = await requestBrowserApi<DocumentPageVariantsResponse>({
        method: "GET",
        path: `/projects/${projectId}/documents/${documentId}/pages/${pageDetail.id}/variants${runIdQuery}`,
        cacheClass: "operations-live"
      });
      if (canceled) {
        return;
      }
      setPageVariantsLoading(false);
      if (!result.ok || !result.data) {
        setPageVariants(null);
        setPageVariantsError(
          result.detail ?? "Preprocess variant metadata could not be loaded."
        );
        return;
      }
      setPageVariants(result.data);
      setPageVariantsError(null);
    };
    void loadVariants();
    return () => {
      canceled = true;
    };
  }, [documentId, pageDetail?.id, projectId, selectedRunId, viewerMode]);

  useEffect(() => {
    const filmstrip = filmstripRef.current;
    if (!filmstrip) {
      return;
    }
    try {
      const saved = window.sessionStorage.getItem(filmstripScrollStorageKey);
      const parsed = saved ? Number(saved) : NaN;
      if (Number.isFinite(parsed) && parsed >= 0) {
        filmstrip.scrollTop = parsed;
      }
    } catch {}

    const handleScroll = () => {
      try {
        window.sessionStorage.setItem(
          filmstripScrollStorageKey,
          String(Math.max(0, Math.round(filmstrip.scrollTop)))
        );
      } catch {}
    };

    filmstrip.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      filmstrip.removeEventListener("scroll", handleScroll);
    };
  }, [filmstripScrollStorageKey, pages.length]);

  useEffect(() => {
    if (copyLinkStatus === "idle") {
      return;
    }
    const timer = window.setTimeout(() => {
      setCopyLinkStatus("idle");
    }, 2200);
    return () => window.clearTimeout(timer);
  }, [copyLinkStatus]);

  useEffect(() => {
    if (!canvasImageFailed || !pageDetail?.id) {
      return;
    }
    let canceled = false;
    const probeImageFailure = async () => {
      const result = await requestBrowserApi<ProjectDocumentPageDetail>({
        method: "GET",
        path: `/projects/${projectId}/documents/${documentId}/pages/${pageDetail.id}`,
        cacheClass: "operations-live"
      });
      if (canceled) {
        return;
      }
      if (result.status === 401) {
        setCanvasImageFailureKind("session");
        return;
      }
      if (result.status === 403) {
        setCanvasImageFailureKind("forbidden");
        return;
      }
      if (result.status === 404) {
        setCanvasImageFailureKind("missing");
        return;
      }
      setCanvasImageFailureKind("unknown");
    };
    void probeImageFailure();
    return () => {
      canceled = true;
    };
  }, [canvasImageFailed, documentId, pageDetail?.id, projectId]);

  useEffect(() => {
    const viewport = canvasViewportRef.current;
    if (!viewport) {
      setViewportSize({ width: 0, height: 0 });
      return;
    }

    const measureViewport = () => {
      const bounds = viewport.getBoundingClientRect();
      setViewportSize({
        width: bounds.width,
        height: bounds.height
      });
    };

    measureViewport();
    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(measureViewport);
      observer.observe(viewport);
    } else {
      window.addEventListener("resize", measureViewport);
    }

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measureViewport);
    };
  }, [
    originalPageImagePath,
    pageDetail?.id,
    preprocessedBinImagePath,
    preprocessedGrayImagePath,
    singleCanvasImagePath,
    comparePair,
    viewerMode
  ]);

  useEffect(() => {
    setPanOffset((current) => ({
      x: clamp(current.x, -maxPanX, maxPanX),
      y: clamp(current.y, -maxPanY, maxPanY)
    }));
  }, [maxPanX, maxPanY]);

  const navigateToPage = (targetPage: number) => {
    const bounded = clamp(targetPage, 1, totalPages);
    if (bounded === currentPage) {
      return;
    }
    startTransition(() => {
      router.push(
        projectDocumentViewerPath(projectId, documentId, bounded, {
          comparePair: viewerMode === "compare" ? comparePair : undefined,
          mode: viewerMode,
          panel: inspectorPanelSection,
          runId: resolvedRunId ?? undefined,
          zoom: zoomPercent
        }),
        { scroll: false }
      );
    });
  };

  const setZoomWithinBounds = (nextZoom: number) => {
    const bounded = clamp(
      roundZoomPercent(nextZoom),
      VIEWER_ZOOM_MIN,
      VIEWER_ZOOM_MAX
    );
    if (bounded === zoomPercent) {
      return;
    }
    setZoomPercent(bounded);
    setPanOffset({ x: 0, y: 0 });
    startTransition(() => {
      router.replace(
        projectDocumentViewerPath(projectId, documentId, currentPage, {
          comparePair: viewerMode === "compare" ? comparePair : undefined,
          mode: viewerMode,
          panel: inspectorPanelSection,
          runId: resolvedRunId ?? undefined,
          zoom: bounded
        }),
        { scroll: false }
      );
    });
  };

  const applyFitWidth = () => {
    if (!pageDetail || viewportSize.width <= 0) {
      return;
    }
    const usableWidth = Math.max(0, viewportSize.width - 24);
    const fitPercent = (usableWidth / transformedWidth) * 100;
    setZoomWithinBounds(fitPercent);
  };

  const copyInternalViewerLink = async (): Promise<void> => {
    const href = new URL(currentViewerPath, window.location.origin).toString();
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(href);
      } else {
        const probe = document.createElement("textarea");
        probe.value = href;
        probe.setAttribute("readonly", "true");
        probe.style.position = "fixed";
        probe.style.opacity = "0";
        document.body.appendChild(probe);
        probe.select();
        document.execCommand("copy");
        document.body.removeChild(probe);
      }
      setCopyLinkStatus("copied");
    } catch {
      setCopyLinkStatus("failed");
    }
  };

  const rotateClockwise = async () => {
    if (!pageDetail || rotationSaving) {
      return;
    }
    setRotationSaving(true);
    setRotationError(null);
    const nextRotation = normalizeRotation(pageDetail.viewerRotation + 90);
    const result = await requestBrowserApi<ProjectDocumentPageDetail>({
      method: "PATCH",
      path: `/projects/${projectId}/documents/${documentId}/pages/${pageDetail.id}`,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ viewerRotation: nextRotation }),
      cacheClass: "operations-live"
    });
    setRotationSaving(false);
    if (!result.ok || !result.data) {
      setRotationError(result.detail ?? "Rotation could not be persisted.");
      return;
    }
    setPageDetail(result.data);
    setPanOffset({ x: 0, y: 0 });
  };

  const syncViewerUrlState = (
    mode: ViewerMode,
    runId: string | null,
    zoom: number,
    nextComparePair: ViewerComparePair,
    panel?: SidePanelSection
  ) => {
    const resolvedPanel = panel ?? inspectorPanelSection;
    startTransition(() => {
      router.replace(
        projectDocumentViewerPath(projectId, documentId, currentPage, {
          comparePair: mode === "compare" ? nextComparePair : undefined,
          mode,
          panel: resolvedPanel,
          runId: runId ?? undefined,
          zoom
        }),
        { scroll: false }
      );
    });
  };

  const handleViewerModeChange = (nextMode: ViewerMode) => {
    if (nextMode === viewerMode) {
      return;
    }
    const nextRunId =
      nextMode === "original" ? selectedRunId : selectedRunId ?? activePreprocessRunId;
    setViewerMode(nextMode);
    setCanvasImageFailed(false);
    setCanvasImageFailureKind("unknown");
    syncViewerUrlState(nextMode, nextRunId, zoomPercent, comparePair);
  };

  const handleRunSelectionChange = (nextRunId: string | null) => {
    const normalized =
      nextRunId && nextRunId.trim().length > 0 ? nextRunId.trim() : null;
    if (normalized === selectedRunId) {
      return;
    }
    setSelectedRunId(normalized);
    syncViewerUrlState(viewerMode, normalized, zoomPercent, comparePair);
  };

  const handleComparePairChange = (nextPair: ViewerComparePair) => {
    if (nextPair === comparePair) {
      return;
    }
    setComparePair(nextPair);
    syncViewerUrlState(viewerMode, selectedRunId, zoomPercent, nextPair);
  };

  const handleInspectorPanelSectionChange = (nextSection: SidePanelSection) => {
    if (nextSection === inspectorPanelSection) {
      return;
    }
    setInspectorPanelSection(nextSection);
    syncViewerUrlState(
      viewerMode,
      selectedRunId,
      zoomPercent,
      comparePair,
      nextSection
    );
  };

  const toolbarActions = useMemo(
    () => [
      {
        id: "previous-page",
        label: "Previous page",
        disabled: currentPage <= 1,
        onAction: () => navigateToPage(currentPage - 1)
      },
      {
        id: "next-page",
        label: "Next page",
        disabled: currentPage >= totalPages,
        onAction: () => navigateToPage(currentPage + 1)
      },
      {
        id: "zoom-out",
        label: "Zoom out",
        disabled: zoomPercent <= VIEWER_ZOOM_MIN,
        onAction: () => setZoomWithinBounds(zoomPercent - ZOOM_STEP_PERCENT)
      },
      {
        id: "zoom-in",
        label: "Zoom in",
        disabled: zoomPercent >= VIEWER_ZOOM_MAX,
        onAction: () => setZoomWithinBounds(zoomPercent + ZOOM_STEP_PERCENT)
      },
      {
        id: "fit-width",
        label: "Fit width",
        disabled: !pageDetail,
        onAction: applyFitWidth
      },
      {
        id: "rotate",
        label: rotationSaving ? "Rotate (saving...)" : "Rotate",
        disabled: !pageDetail || rotationSaving,
        onAction: () => {
          void rotateClockwise();
        }
      },
      {
        id: "toggle-filmstrip",
        label:
          shellState === "Focus"
            ? filmstripDrawerOpen
              ? "Close filmstrip"
              : "Filmstrip drawer"
            : "Filmstrip visible",
        disabled: shellState !== "Focus",
        onAction: () => setFilmstripDrawerOpen((open) => !open),
        pressed: shellState === "Focus" ? filmstripDrawerOpen : undefined
      },
      {
        id: "toggle-inspector",
        label: showInspectorAside
          ? "Inspector visible"
          : inspectorDrawerOpen
            ? "Close inspector"
            : "Inspector drawer",
        disabled: !showInspectorDrawerToggle,
        onAction: () =>
          inspectorDrawerOpen ? closeInspectorDrawer() : openInspectorDrawer(),
        pressed: showInspectorAside ? undefined : inspectorDrawerOpen
      }
    ],
    [
      closeInspectorDrawer,
      currentPage,
      filmstripDrawerOpen,
      inspectorDrawerOpen,
      openInspectorDrawer,
      pageDetail,
      rotationSaving,
      shellState,
      showInspectorDrawerToggle,
      showInspectorAside,
      totalPages,
      zoomPercent
    ]
  );

  const handleWorkspaceKeyDown = (
    event: ReactKeyboardEvent<HTMLDivElement>
  ) => {
    if (isTextEntryTarget(event.target)) {
      return;
    }
    const active =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const inCanvas = Boolean(active && canvasRef.current?.contains(active));
    const inFilmstrip = Boolean(
      active && filmstripRef.current?.contains(active)
    );

    if (event.key === "ArrowLeft" && (inCanvas || inFilmstrip)) {
      event.preventDefault();
      navigateToPage(currentPage - 1);
      return;
    }
    if (event.key === "ArrowRight" && (inCanvas || inFilmstrip)) {
      event.preventDefault();
      navigateToPage(currentPage + 1);
      return;
    }
    if (
      event.key === "+" ||
      event.key === "NumpadAdd" ||
      (event.key === "=" && event.shiftKey)
    ) {
      event.preventDefault();
      setZoomWithinBounds(zoomPercent + ZOOM_STEP_PERCENT);
      return;
    }
    if (event.key === "-" || event.key === "NumpadSubtract") {
      event.preventDefault();
      setZoomWithinBounds(zoomPercent - ZOOM_STEP_PERCENT);
      return;
    }
    if (event.key === "r" || event.key === "R") {
      event.preventDefault();
      void rotateClockwise();
    }
  };

  const handlePanStart = (event: ReactPointerEvent<HTMLElement>) => {
    if (!canPan) {
      return;
    }
    event.preventDefault();
    dragStateRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originPan: panOffset
    };
    setIsDragging(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePanMove = (event: ReactPointerEvent<HTMLElement>) => {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }
    event.preventDefault();
    const deltaX = event.clientX - dragState.startX;
    const deltaY = event.clientY - dragState.startY;
    setPanOffset({
      x: clamp(dragState.originPan.x + deltaX, -maxPanX, maxPanX),
      y: clamp(dragState.originPan.y + deltaY, -maxPanY, maxPanY)
    });
  };

  const handlePanEnd = (event: ReactPointerEvent<HTMLElement>) => {
    const dragState = dragStateRef.current;
    if (dragState && dragState.pointerId === event.pointerId) {
      dragStateRef.current = null;
      setIsDragging(false);
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
    }
  };

  const compareCanvasFailureState =
    viewerMode === "compare" &&
    (compareOriginalImageFailed || comparePreprocessedImageFailed)
      ? {
          kind: "error" as const,
          title: "Compare image delivery failed",
          description:
            "One or more compare panes failed to load. Retry or switch to single-image mode."
        }
      : null;
  const renderedCanvasState = compareCanvasFailureState ?? effectiveCanvasState;

  const metricsRows = Object.entries(preprocessedGrayVariant?.metricsJson ?? {}).slice(
    0,
    8
  );
  const warningChips = preprocessedGrayVariant?.warningsJson ?? [];
  const viewerModeLabel =
    viewerMode === "original"
      ? "Original"
      : viewerMode === "preprocessed"
        ? "Preprocessed"
        : "Compare";
  const inspectorRunLabel =
    resolvedRunId ??
    (viewerMode === "original" ? "Original-only mode" : "No run resolved");
  const inspectorSectionTabs = (
    <div
      className="adaptiveSidePanelTabs"
      role="tablist"
      aria-label="Inspector sections"
    >
      <button
        aria-selected={inspectorPanelSection === "context"}
        className="secondaryButton"
        onClick={() => handleInspectorPanelSectionChange("context")}
        role="tab"
        type="button"
      >
        Context
      </button>
      <button
        aria-selected={inspectorPanelSection === "insights"}
        className="secondaryButton"
        onClick={() => handleInspectorPanelSectionChange("insights")}
        role="tab"
        type="button"
      >
        Insights
      </button>
      <button
        aria-selected={inspectorPanelSection === "actions"}
        className="secondaryButton"
        onClick={() => handleInspectorPanelSectionChange("actions")}
        role="tab"
        type="button"
      >
        Actions
      </button>
    </div>
  );
  const inspectorContextContent = (
    <>
      <ul className="projectMetaList">
        <li>
          <span>Document</span>
          <strong>{documentName}</strong>
        </li>
        <li>
          <span>Current page</span>
          <strong>{currentPage}</strong>
        </li>
        <li>
          <span>Total pages</span>
          <strong>{totalPages}</strong>
        </li>
        <li>
          <span>Viewer mode</span>
          <strong>{viewerModeLabel}</strong>
        </li>
        <li>
          <span>Run context</span>
          <strong>{inspectorRunLabel}</strong>
        </li>
        <li>
          <span>Page status</span>
          <strong>{pageDetail?.status ?? "Unavailable"}</strong>
        </li>
        <li>
          <span>Dimensions</span>
          <strong>
            {pageDetail ? `${pageDetail.width} × ${pageDetail.height}` : "Unavailable"}
          </strong>
        </li>
        <li>
          <span>DPI</span>
          <strong>{typeof pageDetail?.dpi === "number" ? pageDetail.dpi : "Unknown"}</strong>
        </li>
        <li>
          <span>Rotation</span>
          <strong>{pageDetail ? `${pageDetail.viewerRotation}°` : "Unavailable"}</strong>
        </li>
      </ul>
      <div className="auditIntegrityRow">
        <StatusChip tone={DOCUMENT_STATUS_TONES[documentStatus]}>
          {documentStatus}
        </StatusChip>
      </div>
    </>
  );
  const inspectorInsightsContent = (
    <>
      <ul className="projectMetaList">
        <li>
          <span>Variant status</span>
          <strong>
            {viewerMode === "original"
              ? "N/A"
              : preprocessedGrayVariant?.resultStatus ?? "Unavailable"}
          </strong>
        </li>
        <li>
          <span>Quality gate</span>
          <strong>
            {viewerMode === "original"
              ? "N/A"
              : preprocessedGrayVariant?.qualityGateStatus ?? "Unavailable"}
          </strong>
        </li>
      </ul>
      {warningChips.length > 0 ? (
        <div className="documentViewerWarningChips" aria-label="Page warning chips">
          {warningChips.map((warning) => (
            <span className="statusBadge" key={warning}>
              {warning}
            </span>
          ))}
        </div>
      ) : (
        <p className="ukde-muted">No warnings for the resolved preprocess page result.</p>
      )}
      {metricsRows.length > 0 ? (
        <ul className="projectMetaList">
          {metricsRows.map(([key, value]) => (
            <li key={key}>
              <span>{key}</span>
              <strong>{formatMetricValue(value)}</strong>
            </li>
          ))}
        </ul>
      ) : (
        <p className="ukde-muted">
          Metrics become visible once a preprocess run result is available for this page.
        </p>
      )}
      {viewerMode === "compare" ? (
        <p className="ukde-muted">
          Viewer compare is an in-context reading aid. Full run diagnostics remain on the
          canonical preprocessing compare route.
        </p>
      ) : null}
    </>
  );
  const inspectorActionsContent = (
    <div className="buttonRow">
      <Link className="secondaryButton" href={currentQualityPath}>
        Open quality table
      </Link>
      {viewerMode === "compare" ? (
        <Link className="secondaryButton" href={preferredComparePath}>
          Open preprocessing compare
        </Link>
      ) : null}
      <Link className="secondaryButton" href={currentDocumentPath}>
        Open document
      </Link>
      <Link className="secondaryButton" href={currentIngestStatusPath}>
        View ingest status
      </Link>
      <Link className="secondaryButton" href={currentPreprocessingPath}>
        Open preprocessing
      </Link>
      <Link className="secondaryButton" href={backToDocumentsPath}>
        Back to documents
      </Link>
    </div>
  );
  const inspectorContent = (
    <>
      {inspectorSectionTabs}
      {inspectorPanelSection === "context"
        ? inspectorContextContent
        : inspectorPanelSection === "insights"
          ? inspectorInsightsContent
          : inspectorActionsContent}
    </>
  );

  return (
    <>
      <section className="documentViewerToolbar ukde-panel">
        <div className="documentViewerToolbarRow">
          <Toolbar
            actions={toolbarActions}
            label="Document viewer controls"
            overflowActions={[
              {
                id: "document-detail",
                label: "Document detail",
                href: currentDocumentPath
              },
              {
                id: "ingest-status",
                label: "View ingest status",
                href: currentIngestStatusPath
              },
              {
                id: "preprocessing",
                label: "Open preprocessing",
                href: currentPreprocessingPath
              },
              {
                id: "preprocess-quality",
                label: "Open quality table",
                href: currentQualityPath
              },
              {
                id: "preprocess-compare",
                label: "Open preprocessing compare",
                href: preferredComparePath
              },
              {
                id: "filmstrip-width-narrow",
                label: "Filmstrip width: narrow",
                onSelect: () => setFilmstripPreset("narrow")
              },
              {
                id: "filmstrip-width-default",
                label: "Filmstrip width: default",
                onSelect: () => setFilmstripPreset("default")
              },
              {
                id: "filmstrip-width-wide",
                label: "Filmstrip width: wide",
                onSelect: () => setFilmstripPreset("wide")
              },
              {
                id: "inspector-width-narrow",
                label: "Inspector width: narrow",
                onSelect: () => setInspectorPreset("narrow")
              },
              {
                id: "inspector-width-default",
                label: "Inspector width: default",
                onSelect: () => setInspectorPreset("default")
              },
              {
                id: "inspector-width-wide",
                label: "Inspector width: wide",
                onSelect: () => setInspectorPreset("wide")
              },
              {
                id: "copy-viewer-link",
                label: "Copy internal link",
                onSelect: () => {
                  void copyInternalViewerLink();
                }
              }
            ]}
          />
          <div className="documentViewerModeSelector" role="group" aria-label="Viewer mode">
            {VIEWER_MODES.map((mode) => (
              <button
                aria-pressed={viewerMode === mode}
                className="secondaryButton"
                key={mode}
                onClick={() => handleViewerModeChange(mode)}
                type="button"
              >
                {mode === "original"
                  ? "Original"
                  : mode === "preprocessed"
                    ? "Preprocessed"
                    : "Compare"}
              </button>
            ))}
          </div>
          {viewerMode !== "original" ? (
            <label className="documentViewerRunSelector" htmlFor="viewer-run-selector">
              <span>Run</span>
              <select
                className="ukde-field"
                id="viewer-run-selector"
                onChange={(event) => {
                  const nextValue = event.target.value || null;
                  handleRunSelectionChange(nextValue);
                }}
                value={selectedRunId ?? ""}
              >
                <option value="">Active run</option>
                {preprocessRuns.map((run) => (
                  <option key={run.id} value={run.id}>
                    {run.id} · {run.status}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {viewerMode === "compare" ? (
            <label className="documentViewerRunSelector" htmlFor="viewer-compare-pair-selector">
              <span>Compare</span>
              <select
                className="ukde-field"
                id="viewer-compare-pair-selector"
                onChange={(event) => {
                  handleComparePairChange(event.target.value as ViewerComparePair);
                }}
                value={comparePair}
              >
                {VIEWER_COMPARE_PAIRS.map((pair) => {
                  const label =
                    pair === "original_gray"
                      ? "Original vs Gray"
                      : pair === "original_binary"
                        ? "Original vs Binary"
                        : "Gray vs Binary";
                  const disabled =
                    ((pair === "original_binary" || pair === "gray_binary") &&
                      preprocessedBinVariant !== null &&
                      !preprocessedBinVariant.available) ||
                    (pair === "gray_binary" &&
                      preprocessedGrayVariant !== null &&
                      !preprocessedGrayVariant.available);
                  return (
                    <option key={pair} value={pair} disabled={disabled}>
                      {label}
                      {disabled ? " (binary unavailable)" : ""}
                    </option>
                  );
                })}
              </select>
            </label>
          ) : null}
          <form
            className="documentViewerPageJump"
            onSubmit={(event) => {
              event.preventDefault();
              const parsed = Number.parseInt(pageJumpValue, 10);
              if (!Number.isFinite(parsed)) {
                setPageJumpValue(String(currentPage));
                return;
              }
              navigateToPage(parsed);
            }}
          >
            <label htmlFor="viewer-page-jump">Page</label>
            <input
              className="ukde-field"
              id="viewer-page-jump"
              inputMode="numeric"
              max={totalPages}
              min={1}
              onChange={(event) => setPageJumpValue(event.target.value)}
              type="number"
              value={pageJumpValue}
            />
            <span aria-hidden>/ {totalPages}</span>
            <button className="ukde-button" type="submit">
              Go
            </button>
          </form>
          <p className="documentViewerZoomReadout" aria-live="polite">
            Zoom {zoomPercent}%
          </p>
        </div>
        <p className="documentViewerLinkStatus" aria-live="polite">
          {copyLinkStatus === "copied"
            ? "Internal viewer link copied."
            : copyLinkStatus === "failed"
              ? "Internal link copy failed."
              : ""}
        </p>
        <p className="documentViewerShortcutHint">
          Shortcuts: <span className="ukde-kbd">←</span>/<span className="ukde-kbd">→</span>{" "}
          page, <span className="ukde-kbd">+</span>/<span className="ukde-kbd">-</span>{" "}
          zoom, <span className="ukde-kbd">R</span> rotate.
        </p>
        <p className="ukde-muted">Workspace mode: {shellState}</p>
        {rotationError ? (
          <p className="ukde-muted" role="alert">
            {rotationError}
          </p>
        ) : null}
      </section>

      <section
        className="documentViewerWorkspace ukde-panel"
        aria-label="Viewer workspace"
        data-workspace-state={shellState}
        onKeyDownCapture={handleWorkspaceKeyDown}
        style={workspaceStyle}
      >
        {showFilmstripAside ? (
          <aside
            className="documentViewerFilmstrip"
            aria-label="Filmstrip"
            ref={filmstripRef}
          >
          <h2>Pages</h2>
          {pages.length === 0 ? (
            <SectionState
              kind="empty"
              title="No page thumbnails"
              description="Thumbnails appear once extraction and rendering succeed."
            />
          ) : (
            <ul>
              {pages.map((page) => {
                const pageNumber = page.pageIndex + 1;
                const thumbnailPath =
                  page.status === "READY"
                    ? projectDocumentPageImagePath(
                        projectId,
                        documentId,
                        page.id,
                        "thumb"
                      )
                    : null;
                return (
                  <li key={page.id}>
                    <Link
                      aria-current={
                        pageNumber === currentPage ? "page" : undefined
                      }
                      className="documentViewerFilmstripLink"
                      href={projectDocumentViewerPath(
                        projectId,
                        documentId,
                        pageNumber,
                        {
                          comparePair:
                            viewerMode === "compare" ? comparePair : undefined,
                          mode: viewerMode,
                          panel: inspectorPanelSection,
                          runId: resolvedRunId ?? undefined,
                          zoom: zoomPercent
                        }
                      )}
                    >
                      {thumbnailPath ? (
                        <img
                          alt=""
                          className="documentViewerFilmstripThumb"
                          height={84}
                          src={thumbnailPath}
                          width={60}
                        />
                      ) : (
                        <span
                          className="documentViewerFilmstripThumbPlaceholder"
                          data-status={page.status.toLowerCase()}
                        >
                          {page.status === "PENDING"
                            ? "Pending"
                            : "Unavailable"}
                        </span>
                      )}
                      <span>Page {pageNumber}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
          </aside>
        ) : null}

        <section
          className="documentViewerCanvas"
          aria-label="Canvas"
          ref={canvasRef}
          tabIndex={0}
        >
          {viewerMode === "compare" &&
          compareLeftImagePath &&
          compareRightImagePath &&
          !renderedCanvasState ? (
            <div
              className="documentViewerCanvasViewport documentViewerCompareViewport"
              ref={canvasViewportRef}
              tabIndex={0}
            >
              <div className="documentViewerCompareSplit" role="group" aria-label="Before and after compare">
                <figure className="documentViewerComparePane" data-pane="original">
                  <figcaption>{compareLeftLabel}</figcaption>
                  <img
                    alt={`${documentName} page ${currentPage} ${compareLeftLabel.toLowerCase()}`}
                    className="documentViewerImage"
                    draggable={false}
                    height={pageDetail?.height ?? intrinsicHeight}
                    onError={() => setCompareOriginalImageFailed(true)}
                    onLoad={() => setCompareOriginalImageFailed(false)}
                    src={compareLeftImagePath}
                    style={{
                      transform: `scale(${imageScale}) rotate(${normalizedRotation}deg)`
                    }}
                    width={pageDetail?.width ?? intrinsicWidth}
                  />
                </figure>
                <figure className="documentViewerComparePane" data-pane="preprocessed">
                  <figcaption>{compareRightLabel}</figcaption>
                  <img
                    alt={`${documentName} page ${currentPage} ${compareRightLabel.toLowerCase()}`}
                    className="documentViewerImage"
                    draggable={false}
                    height={pageDetail?.height ?? intrinsicHeight}
                    onError={() => setComparePreprocessedImageFailed(true)}
                    onLoad={() => setComparePreprocessedImageFailed(false)}
                    src={compareRightImagePath}
                    style={{
                      transform: `scale(${imageScale}) rotate(${normalizedRotation}deg)`
                    }}
                    width={pageDetail?.width ?? intrinsicWidth}
                  />
                </figure>
              </div>
            </div>
          ) : viewerMode !== "compare" &&
            singleCanvasImagePath &&
            !canvasImageFailed ? (
            <div
              className="documentViewerCanvasViewport"
              ref={canvasViewportRef}
              tabIndex={0}
            >
              <figure
                className="documentViewerImageFrame"
                data-dragging={isDragging ? "yes" : "no"}
                data-pan-enabled={canPan ? "yes" : "no"}
                onPointerCancel={handlePanEnd}
                onPointerDown={handlePanStart}
                onPointerMove={handlePanMove}
                onPointerUp={handlePanEnd}
              >
                <img
                  alt={`${documentName} page ${currentPage}`}
                  className="documentViewerImage"
                  draggable={false}
                  height={pageDetail?.height ?? intrinsicHeight}
                  onError={() => setCanvasImageFailed(true)}
                  onLoad={() => setCanvasImageFailed(false)}
                  src={singleCanvasImagePath}
                  style={{
                    transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${imageScale}) rotate(${normalizedRotation}deg)`
                  }}
                  width={pageDetail?.width ?? intrinsicWidth}
                />
              </figure>
            </div>
          ) : renderedCanvasState ? (
            <SectionState
              actions={canvasRecoveryActions}
              kind={renderedCanvasState.kind}
              title={renderedCanvasState.title}
              description={renderedCanvasState.description}
            />
          ) : null}
        </section>

        {showInspectorAside ? (
          <aside className="documentViewerInspector" aria-label="Inspector">
            <h2>Inspector</h2>
            {inspectorContent}
          </aside>
        ) : null}
      </section>

      <DetailsDrawer
        description="Inspector drawer path for compact and focus work regions."
        onClose={closeInspectorDrawer}
        open={inspectorDrawerOpen}
        title="Viewer inspector"
      >
        {inspectorContent}
      </DetailsDrawer>

      <Drawer
        description="Filmstrip drawer for focus mode."
        onClose={() => setFilmstripDrawerOpen(false)}
        open={filmstripDrawerOpen}
        side="left"
        title="Filmstrip"
      >
        {pages.length === 0 ? (
          <SectionState
            kind="empty"
            title="No page thumbnails"
            description="Thumbnails appear once extraction and rendering succeed."
          />
        ) : (
          <ul className="documentViewerDrawerFilmstripList">
            {pages.map((page) => {
              const pageNumber = page.pageIndex + 1;
              const thumbnailPath =
                page.status === "READY"
                  ? projectDocumentPageImagePath(
                      projectId,
                      documentId,
                      page.id,
                      "thumb"
                    )
                  : null;
              return (
                <li key={page.id}>
                  <Link
                    aria-current={pageNumber === currentPage ? "page" : undefined}
                    className="documentViewerFilmstripLink"
                    href={projectDocumentViewerPath(
                      projectId,
                      documentId,
                      pageNumber,
                      {
                        comparePair:
                          viewerMode === "compare" ? comparePair : undefined,
                        mode: viewerMode,
                        panel: inspectorPanelSection,
                        runId: resolvedRunId ?? undefined,
                        zoom: zoomPercent
                      }
                    )}
                    onClick={() => setFilmstripDrawerOpen(false)}
                  >
                    {thumbnailPath ? (
                      <img
                        alt=""
                        className="documentViewerFilmstripThumb"
                        height={84}
                        src={thumbnailPath}
                        width={60}
                      />
                    ) : (
                      <span
                        className="documentViewerFilmstripThumbPlaceholder"
                        data-status={page.status.toLowerCase()}
                      >
                        {page.status === "PENDING" ? "Pending" : "Unavailable"}
                      </span>
                    )}
                    <span>Page {pageNumber}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </Drawer>
    </>
  );
}
