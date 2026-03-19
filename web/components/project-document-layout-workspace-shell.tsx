"use client";

import { useRouter } from "next/navigation";
import { startTransition, useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import type { MouseEvent, PointerEvent } from "react";
import type {
  DocumentLayoutReadingOrderGroup,
  DocumentLayoutPageRecallStatusResponse,
  DocumentLayoutPageOverlay,
  DocumentLayoutPageResult,
  DocumentLayoutRescueCandidate,
  DocumentLayoutRun,
  LayoutElementsPatchOperation,
  LayoutOverlayElement,
  LayoutOverlayLineElement,
  LayoutReadingOrderMode,
  LayoutOverlayPoint,
  LayoutOverlayRegionElement,
  UpdateDocumentLayoutElementsResponse,
  UpdateDocumentLayoutReadingOrderResponse,
  ShellState
} from "@ukde/contracts";
import {
  DetailsDrawer,
  Drawer,
  SectionState,
  StatusChip,
  Toolbar,
  type ToolbarAction
} from "@ukde/ui/primitives";

import { projectDocumentPageImagePath } from "../lib/document-page-image";
import { requestBrowserApi } from "../lib/data/browser-api-client";
import {
  projectDocumentLayoutPath,
  projectDocumentLayoutWorkspacePath
} from "../lib/routes";

interface ProjectDocumentLayoutWorkspaceShellProps {
  canEditLayout: boolean;
  canEditReadingOrder: boolean;
  documentId: string;
  documentName: string;
  overlayError: string | null;
  overlayNotReady: boolean;
  overlayPayload: DocumentLayoutPageOverlay | null;
  pages: DocumentLayoutPageResult[];
  projectId: string;
  recallStatus: DocumentLayoutPageRecallStatusResponse | null;
  recallStatusError: string | null;
  rescueCandidates: DocumentLayoutRescueCandidate[];
  rescueCandidatesError: string | null;
  runs: DocumentLayoutRun[];
  selectedPageNumber: number;
  selectedRunId: string;
}

interface OverlayCenter {
  x: number;
  y: number;
}

type InspectorTab = "geometry" | "reading-order";

interface ReadingOrderDragState {
  fromGroupId: string;
  regionId: string;
}

type LayoutEditTool =
  | "SELECT_PAN"
  | "DRAW_REGION"
  | "EDIT_VERTICES"
  | "SPLIT_LINE"
  | "MERGE_LINES"
  | "DELETE_ELEMENT"
  | "ASSIGN_REGION_TYPE";

interface LayoutEditSnapshot {
  overlay: DocumentLayoutPageOverlay;
  operations: LayoutElementsPatchOperation[];
}

interface LayoutEditSession {
  overlay: DocumentLayoutPageOverlay;
  operations: LayoutElementsPatchOperation[];
  undoStack: LayoutEditSnapshot[];
  redoStack: LayoutEditSnapshot[];
  versionEtag: string;
}

interface LayoutVertexDragState {
  elementId: string;
  pointerId: number;
  originalPoints: LayoutOverlayPoint[];
  points: LayoutOverlayPoint[];
  vertexIndex: number;
}

type WorkspaceMode = "INSPECT" | "READING_ORDER" | "EDIT";
type PageImageLoadState = "idle" | "loading" | "loaded" | "error";

type WorkspaceTransitionAction =
  | {
      kind: "NAVIGATE";
      page: number;
      runId: string;
    }
  | {
      kind: "OPEN_TRIAGE";
    }
  | {
      kind: "SET_MODE";
      mode: WorkspaceMode;
    };

const WORKSPACE_STATES: readonly ShellState[] = [
  "Expanded",
  "Balanced",
  "Compact",
  "Focus"
];
const PANEL_WIDTH_STORAGE_PREFIX = "ukde.layout.workspace.panel-widths";
const FILMSTRIP_WIDTH_RANGE = { min: 8.5, max: 18 };
const INSPECTOR_WIDTH_RANGE = { min: 12, max: 22 };
const FILMSTRIP_WIDTH_PRESETS: Record<"default" | "narrow" | "wide", number> = {
  narrow: 10.5,
  default: 13,
  wide: 15.5
};
const INSPECTOR_WIDTH_PRESETS: Record<"default" | "narrow" | "wide", number> = {
  narrow: 14.5,
  default: 16.75,
  wide: 19.5
};
const PAGE_IMAGE_MAX_RETRY_ATTEMPTS = 1;

function isShellState(value: string | null): value is ShellState {
  return WORKSPACE_STATES.includes(value as ShellState);
}

function clampNumber(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function formatMetricCount(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(Math.round(value));
  }
  if (typeof value === "string" && value.trim().length > 0) {
    return value.trim();
  }
  return "N/A";
}

function formatMetricPercent(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${Math.max(0, Math.min(100, value)).toFixed(2)}%`;
  }
  return "N/A";
}

function polygonToPoints(points: LayoutOverlayPoint[]): string {
  return points.map((point) => `${point.x},${point.y}`).join(" ");
}

function resolveCenter(points: LayoutOverlayPoint[]): OverlayCenter | null {
  if (points.length === 0) {
    return null;
  }
  let sumX = 0;
  let sumY = 0;
  for (const point of points) {
    sumX += point.x;
    sumY += point.y;
  }
  return {
    x: sumX / points.length,
    y: sumY / points.length
  };
}

function isRegionElement(element: LayoutOverlayElement): element is LayoutOverlayRegionElement {
  return element.type === "REGION";
}

function isLineElement(element: LayoutOverlayElement): element is LayoutOverlayLineElement {
  return element.type === "LINE";
}

function resolveElementSortKey(element: LayoutOverlayElement): [number, number, string] {
  const center = resolveCenter(element.polygon);
  return [center?.y ?? 0, center?.x ?? 0, element.id];
}

function compareElementSort(a: LayoutOverlayElement, b: LayoutOverlayElement): number {
  const [aY, aX, aId] = resolveElementSortKey(a);
  const [bY, bX, bId] = resolveElementSortKey(b);
  if (aY !== bY) {
    return aY - bY;
  }
  if (aX !== bX) {
    return aX - bX;
  }
  return aId.localeCompare(bId);
}

function resolveRunTone(status: string): "danger" | "neutral" | "success" | "warning" {
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

function resolvePageTone(status: string): "danger" | "neutral" | "success" | "warning" {
  if (status === "SUCCEEDED" || status === "COMPLETE") {
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

function resolveRescueTone(status: string): "danger" | "neutral" | "success" | "warning" {
  if (status === "ACCEPTED" || status === "RESOLVED") {
    return "success";
  }
  if (status === "REJECTED") {
    return "neutral";
  }
  return "warning";
}

function cloneReadingOrderGroups(
  groups: DocumentLayoutReadingOrderGroup[]
): DocumentLayoutReadingOrderGroup[] {
  return groups.map((group) => ({
    id: group.id,
    ordered: group.ordered,
    regionIds: [...group.regionIds]
  }));
}

function resolveDefaultReadingOrderMode(
  groups: DocumentLayoutReadingOrderGroup[]
): LayoutReadingOrderMode {
  if (groups.length === 0) {
    return "WITHHELD";
  }
  return groups.every((group) => group.ordered) ? "ORDERED" : "UNORDERED";
}

function areReadingOrderGroupsEqual(
  left: DocumentLayoutReadingOrderGroup[],
  right: DocumentLayoutReadingOrderGroup[]
): boolean {
  if (left.length !== right.length) {
    return false;
  }
  for (let index = 0; index < left.length; index += 1) {
    const leftGroup = left[index];
    const rightGroup = right[index];
    if (
      leftGroup.id !== rightGroup.id ||
      leftGroup.ordered !== rightGroup.ordered ||
      leftGroup.regionIds.length !== rightGroup.regionIds.length
    ) {
      return false;
    }
    for (let regionIndex = 0; regionIndex < leftGroup.regionIds.length; regionIndex += 1) {
      if (leftGroup.regionIds[regionIndex] !== rightGroup.regionIds[regionIndex]) {
        return false;
      }
    }
  }
  return true;
}

function resolveFallbackReadingOrderGroups(
  regions: LayoutOverlayRegionElement[],
  mode: LayoutReadingOrderMode
): DocumentLayoutReadingOrderGroup[] {
  if (mode === "WITHHELD" || regions.length === 0) {
    return [];
  }
  return [
    {
      id: "g-0001",
      ordered: mode === "ORDERED",
      regionIds: regions.map((region) => region.id)
    }
  ];
}

function cloneOverlayPoint(point: LayoutOverlayPoint): LayoutOverlayPoint {
  return { x: point.x, y: point.y };
}

function cloneLayoutOverlay(overlay: DocumentLayoutPageOverlay): DocumentLayoutPageOverlay {
  return {
    schemaVersion: overlay.schemaVersion,
    runId: overlay.runId,
    pageId: overlay.pageId,
    pageIndex: overlay.pageIndex,
    page: {
      width: overlay.page.width,
      height: overlay.page.height
    },
    elements: overlay.elements.map((element) =>
      element.type === "REGION"
        ? {
            ...element,
            childIds: [...element.childIds],
            polygon: element.polygon.map(cloneOverlayPoint)
          }
        : {
            ...element,
            polygon: element.polygon.map(cloneOverlayPoint),
            baseline: Array.isArray(element.baseline)
              ? element.baseline.map(cloneOverlayPoint)
              : undefined
          }
    ),
    readingOrder: overlay.readingOrder.map((edge) => ({
      fromId: edge.fromId,
      toId: edge.toId
    })),
    readingOrderGroups: overlay.readingOrderGroups.map((group) => ({
      id: group.id,
      ordered: group.ordered,
      regionIds: [...group.regionIds]
    })),
    readingOrderMeta: { ...overlay.readingOrderMeta }
  };
}

function cloneLayoutEditSnapshot(snapshot: LayoutEditSnapshot): LayoutEditSnapshot {
  return {
    overlay: cloneLayoutOverlay(snapshot.overlay),
    operations: snapshot.operations.map((operation) => ({
      ...operation,
      polygon: Array.isArray(operation.polygon)
        ? operation.polygon.map(cloneOverlayPoint)
        : undefined,
      baseline: Array.isArray(operation.baseline)
        ? operation.baseline.map(cloneOverlayPoint)
        : operation.baseline,
      lineIds: Array.isArray(operation.lineIds) ? [...operation.lineIds] : undefined
    }))
  };
}

function clampPointToPage(
  point: LayoutOverlayPoint,
  width: number,
  height: number
): LayoutOverlayPoint {
  return {
    x: Math.max(0, Math.min(width, point.x)),
    y: Math.max(0, Math.min(height, point.y))
  };
}

function resolveBoundingBox(points: LayoutOverlayPoint[]): {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
} | null {
  if (points.length === 0) {
    return null;
  }
  let minX = points[0].x;
  let maxX = points[0].x;
  let minY = points[0].y;
  let maxY = points[0].y;
  for (const point of points) {
    minX = Math.min(minX, point.x);
    maxX = Math.max(maxX, point.x);
    minY = Math.min(minY, point.y);
    maxY = Math.max(maxY, point.y);
  }
  return { minX, maxX, minY, maxY };
}

function rectanglePolygon(
  minX: number,
  minY: number,
  maxX: number,
  maxY: number
): LayoutOverlayPoint[] {
  return [
    { x: minX, y: minY },
    { x: maxX, y: minY },
    { x: maxX, y: maxY },
    { x: minX, y: maxY }
  ];
}

function resolveNextOverlayId(prefix: "line" | "region", elements: LayoutOverlayElement[]): string {
  const pattern = new RegExp(`^${prefix}-(\\d+)$`);
  let maxValue = 0;
  for (const element of elements) {
    const match = pattern.exec(element.id);
    if (!match) {
      continue;
    }
    const parsed = Number.parseInt(match[1] ?? "", 10);
    if (Number.isFinite(parsed)) {
      maxValue = Math.max(maxValue, parsed);
    }
  }
  const next = maxValue + 1;
  return `${prefix}-${String(next).padStart(4, "0")}`;
}

function areOverlayPointsEqual(
  left: LayoutOverlayPoint[],
  right: LayoutOverlayPoint[]
): boolean {
  if (left.length !== right.length) {
    return false;
  }
  for (let index = 0; index < left.length; index += 1) {
    if (left[index].x !== right[index].x || left[index].y !== right[index].y) {
      return false;
    }
  }
  return true;
}

function resolveWorkspaceModeLabel(mode: WorkspaceMode): string {
  if (mode === "EDIT") {
    return "edit mode";
  }
  if (mode === "READING_ORDER") {
    return "reading-order mode";
  }
  return "inspect mode";
}

function resolvePendingTransitionSummary(action: WorkspaceTransitionAction): string {
  if (action.kind === "NAVIGATE") {
    return `open page ${action.page}`;
  }
  if (action.kind === "OPEN_TRIAGE") {
    return "open triage";
  }
  return `switch to ${resolveWorkspaceModeLabel(action.mode)}`;
}

function resolveUnsavedSummary(options: {
  layoutEditHasChanges: boolean;
  layoutOperationCount: number;
  readingOrderHasChanges: boolean;
}): string {
  const { layoutEditHasChanges, layoutOperationCount, readingOrderHasChanges } = options;
  if (layoutEditHasChanges && readingOrderHasChanges) {
    return `${layoutOperationCount} unsaved geometry edit${layoutOperationCount === 1 ? "" : "s"} and unsaved reading-order changes`;
  }
  if (layoutEditHasChanges) {
    return `${layoutOperationCount} unsaved geometry edit${layoutOperationCount === 1 ? "" : "s"}`;
  }
  return "Unsaved reading-order changes";
}

export function ProjectDocumentLayoutWorkspaceShell({
  canEditLayout,
  canEditReadingOrder,
  documentId,
  documentName,
  overlayError,
  overlayNotReady,
  overlayPayload,
  pages,
  projectId,
  recallStatus,
  recallStatusError,
  rescueCandidates,
  rescueCandidatesError,
  runs,
  selectedPageNumber,
  selectedRunId
}: ProjectDocumentLayoutWorkspaceShellProps) {
  const router = useRouter();
  const overlaySvgRef = useRef<SVGSVGElement | null>(null);
  const pageImageRef = useRef<HTMLImageElement | null>(null);
  const latestResolvedImagePathRef = useRef<string | null>(null);
  const [shellState, setShellState] = useState<ShellState>("Expanded");
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("geometry");
  const [showRegions, setShowRegions] = useState(true);
  const [showLines, setShowLines] = useState(true);
  const [showBaselines, setShowBaselines] = useState(true);
  const [showReadingOrder, setShowReadingOrder] = useState(true);
  const [overlayOpacityPercent, setOverlayOpacityPercent] = useState(72);
  const [hoveredElementId, setHoveredElementId] = useState<string | null>(null);
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null);
  const [filmstripCollapsed, setFilmstripCollapsed] = useState(false);
  const [filmstripDrawerOpen, setFilmstripDrawerOpen] = useState(false);
  const [inspectorDrawerOpen, setInspectorDrawerOpen] = useState(false);
  const [zoomPercent, setZoomPercent] = useState(100);
  const [pageImageState, setPageImageState] = useState<{
    retryAttempt: number;
    status: PageImageLoadState;
  }>({
    retryAttempt: 0,
    status: "idle"
  });
  const [readingOrderBaseGroups, setReadingOrderBaseGroups] = useState<
    DocumentLayoutReadingOrderGroup[]
  >([]);
  const [readingOrderDraftGroups, setReadingOrderDraftGroups] = useState<
    DocumentLayoutReadingOrderGroup[]
  >([]);
  const [readingOrderBaseMode, setReadingOrderBaseMode] = useState<LayoutReadingOrderMode>(
    "WITHHELD"
  );
  const [readingOrderDraftMode, setReadingOrderDraftMode] = useState<LayoutReadingOrderMode>(
    "WITHHELD"
  );
  const [readingOrderVersionEtag, setReadingOrderVersionEtag] = useState<string | null>(null);
  const [readingOrderSaving, setReadingOrderSaving] = useState(false);
  const [readingOrderError, setReadingOrderError] = useState<string | null>(null);
  const [readingOrderNotice, setReadingOrderNotice] = useState<string | null>(null);
  const [readingOrderConflict, setReadingOrderConflict] = useState(false);
  const [readingOrderDragState, setReadingOrderDragState] = useState<ReadingOrderDragState | null>(
    null
  );
  const [layoutEditMode, setLayoutEditMode] = useState(false);
  const [layoutEditTool, setLayoutEditTool] = useState<LayoutEditTool>("SELECT_PAN");
  const [layoutEditSession, setLayoutEditSession] = useState<LayoutEditSession | null>(null);
  const [layoutEditSaving, setLayoutEditSaving] = useState(false);
  const [layoutEditError, setLayoutEditError] = useState<string | null>(null);
  const [layoutEditNotice, setLayoutEditNotice] = useState<string | null>(null);
  const [layoutEditConflict, setLayoutEditConflict] = useState(false);
  const [pendingRegionPoints, setPendingRegionPoints] = useState<LayoutOverlayPoint[]>([]);
  const [mergeLineSelection, setMergeLineSelection] = useState<string[]>([]);
  const [vertexDragState, setVertexDragState] = useState<LayoutVertexDragState | null>(null);
  const [filmstripWidthRem, setFilmstripWidthRem] = useState(13);
  const [inspectorWidthRem, setInspectorWidthRem] = useState(16.75);
  const [pendingTransitionAction, setPendingTransitionAction] =
    useState<WorkspaceTransitionAction | null>(null);

  const selectedPage =
    pages.find((item) => item.pageIndex + 1 === selectedPageNumber) ?? pages[0] ?? null;
  const workspaceOverlay =
    layoutEditMode && layoutEditSession ? layoutEditSession.overlay : overlayPayload;

  const regions: LayoutOverlayRegionElement[] = [];
  const lines: LayoutOverlayLineElement[] = [];
  const elementById = new Map<string, LayoutOverlayElement>();
  if (workspaceOverlay) {
    const sorted = [...workspaceOverlay.elements].sort(compareElementSort);
    for (const element of sorted) {
      elementById.set(element.id, element);
      if (isRegionElement(element)) {
        regions.push(element);
      } else if (isLineElement(element)) {
        lines.push(element);
      }
    }
  }
  const hasBaselines = lines.some(
    (line) => Array.isArray(line.baseline) && line.baseline.length >= 2
  );
  const hasReadingOrder = Boolean(workspaceOverlay && workspaceOverlay.readingOrder.length > 0);

  const selectedElement =
    selectedElementId && elementById.has(selectedElementId)
      ? elementById.get(selectedElementId) ?? null
      : null;
  const selectedRegionId =
    selectedElement?.type === "REGION"
      ? selectedElement.id
      : selectedElement?.type === "LINE"
        ? selectedElement.parentId
        : null;
  const filteredLines = selectedRegionId
    ? lines.filter((line) => line.parentId === selectedRegionId)
    : lines;
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? null;
  const layoutEditHasChanges = Boolean(layoutEditSession && layoutEditSession.operations.length > 0);
  const layoutEditOperationCount = layoutEditSession?.operations.length ?? 0;
  const layoutEditCanUndo = Boolean(layoutEditSession && layoutEditSession.undoStack.length > 0);
  const layoutEditCanRedo = Boolean(layoutEditSession && layoutEditSession.redoStack.length > 0);
  const readingOrderHasChanges =
    readingOrderDraftMode !== readingOrderBaseMode ||
    !areReadingOrderGroupsEqual(readingOrderDraftGroups, readingOrderBaseGroups);
  const workspaceMode: WorkspaceMode = layoutEditMode
    ? "EDIT"
    : inspectorTab === "reading-order"
      ? "READING_ORDER"
      : "INSPECT";
  const hasUnsavedChanges = layoutEditHasChanges || readingOrderHasChanges;
  const hasConflict = layoutEditConflict || readingOrderConflict;
  const paneStorageKey = `${PANEL_WIDTH_STORAGE_PREFIX}:${projectId}:${documentId}`;
  const workspaceStyle = {
    "--viewer-filmstrip-width": `${filmstripWidthRem}rem`,
    "--viewer-inspector-width": `${inspectorWidthRem}rem`
  } as CSSProperties;

  const centers = new Map<string, OverlayCenter>();
  for (const element of elementById.values()) {
    const center = resolveCenter(element.polygon);
    if (center) {
      centers.set(element.id, center);
    }
  }

  const canvasWidth = workspaceOverlay?.page.width ?? 1200;
  const canvasHeight = workspaceOverlay?.page.height ?? 1800;
  const scale = Math.max(0.5, Math.min(4, zoomPercent / 100));
  const stageStyle = {
    width: `${Math.round(canvasWidth * scale)}px`,
    height: `${Math.round(canvasHeight * scale)}px`
  };
  const overlayStyle = { opacity: overlayOpacityPercent / 100 };

  const showInspectorAside = shellState === "Expanded" || shellState === "Balanced";
  const showFilmstripAside = shellState !== "Focus" && !filmstripCollapsed;
  const canUseCanvas = Boolean(workspaceOverlay && selectedPage);
  const imagePath =
    selectedPage && selectedRunId
      ? projectDocumentPageImagePath(
          projectId,
          documentId,
          selectedPage.pageId,
          "preprocessed_gray",
          { runId: selectedRunId }
        )
      : null;
  const resolvedImagePath =
    imagePath && pageImageState.retryAttempt > 0
      ? `${imagePath}${imagePath.includes("?") ? "&" : "?"}retry=${pageImageState.retryAttempt}`
      : imagePath;
  const pageImageFailed = pageImageState.status === "error";

  useEffect(() => {
    latestResolvedImagePathRef.current = resolvedImagePath;
  }, [resolvedImagePath]);

  useEffect(() => {
    const shellElement = document.querySelector<HTMLElement>(".authenticatedShell");
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
    if (showInspectorAside) {
      setInspectorDrawerOpen(false);
    }
    if (shellState !== "Focus") {
      setFilmstripDrawerOpen(false);
    }
  }, [shellState, showInspectorAside]);

  useEffect(() => {
    setHoveredElementId(null);
    setSelectedElementId(null);
    setInspectorTab("geometry");
    setLayoutEditMode(false);
    setLayoutEditTool("SELECT_PAN");
    setLayoutEditSession(null);
    setLayoutEditSaving(false);
    setLayoutEditError(null);
    setLayoutEditNotice(null);
    setPendingRegionPoints([]);
    setMergeLineSelection([]);
    setVertexDragState(null);
    setReadingOrderSaving(false);
    setReadingOrderError(null);
    setReadingOrderNotice(null);
    setReadingOrderConflict(false);
    setReadingOrderDragState(null);
    setLayoutEditConflict(false);
    setPendingTransitionAction(null);
  }, [selectedRunId, selectedPage?.pageId]);

  useEffect(() => {
    if (!imagePath) {
      setPageImageState({
        retryAttempt: 0,
        status: "idle"
      });
      return;
    }
    const imageElement = pageImageRef.current;
    const imageAlreadyLoaded = Boolean(
      imageElement &&
        imageElement.complete &&
        imageElement.naturalWidth > 0 &&
        imageElement.naturalHeight > 0
    );
    if (imageAlreadyLoaded) {
      setPageImageState({
        retryAttempt: 0,
        status: "loaded"
      });
      return;
    }
    setPageImageState({
      retryAttempt: 0,
      status: "loading"
    });
  }, [imagePath]);

  useEffect(() => {
    const requestPath = resolvedImagePath;
    if (pageImageState.status !== "loading") {
      return;
    }
    if (!requestPath || latestResolvedImagePathRef.current !== requestPath) {
      return;
    }
    const imageElement = pageImageRef.current;
    if (!imageElement || !imageElement.complete) {
      return;
    }
    setPageImageState((current) => {
      if (
        current.status !== "loading" ||
        !requestPath ||
        latestResolvedImagePathRef.current !== requestPath
      ) {
        return current;
      }
      if (imageElement.naturalWidth > 0 && imageElement.naturalHeight > 0) {
        return {
          retryAttempt: current.retryAttempt,
          status: "loaded"
        };
      }
      if (current.retryAttempt < PAGE_IMAGE_MAX_RETRY_ATTEMPTS) {
        return {
          retryAttempt: current.retryAttempt + 1,
          status: "loading"
        };
      }
      return {
        retryAttempt: current.retryAttempt,
        status: "error"
      };
    });
  }, [pageImageState.status, resolvedImagePath]);

  useEffect(() => {
    const overlayRegions = overlayPayload
      ? overlayPayload.elements.filter(isRegionElement)
      : [];
    const overlayHasBaselines = overlayPayload
      ? overlayPayload.elements.some(
          (element) =>
            isLineElement(element) &&
            Array.isArray(element.baseline) &&
            element.baseline.length >= 2
        )
      : false;
    const overlayHasReadingOrder = Boolean(
      overlayPayload && overlayPayload.readingOrder.length > 0
    );
    if (!overlayHasBaselines) {
      setShowBaselines(false);
    }
    if (!overlayHasReadingOrder) {
      setShowReadingOrder(false);
    }
    const overlayMode = overlayPayload?.readingOrderMeta?.mode;
    const nextMode: LayoutReadingOrderMode =
      overlayMode === "ORDERED" || overlayMode === "UNORDERED" || overlayMode === "WITHHELD"
        ? overlayMode
        : resolveDefaultReadingOrderMode(overlayPayload?.readingOrderGroups ?? []);
    const nextGroups =
      overlayPayload && overlayPayload.readingOrderGroups.length > 0
        ? cloneReadingOrderGroups(overlayPayload.readingOrderGroups)
        : resolveFallbackReadingOrderGroups(overlayRegions, nextMode);
    setReadingOrderBaseGroups(nextGroups);
    setReadingOrderDraftGroups(cloneReadingOrderGroups(nextGroups));
    setReadingOrderBaseMode(nextMode);
    setReadingOrderDraftMode(nextMode);
    setReadingOrderVersionEtag(
      typeof overlayPayload?.readingOrderMeta?.versionEtag === "string" &&
        overlayPayload.readingOrderMeta.versionEtag.trim().length > 0
        ? overlayPayload.readingOrderMeta.versionEtag.trim()
        : null
    );
    setReadingOrderSaving(false);
    setReadingOrderError(null);
    setReadingOrderNotice(null);
    setReadingOrderConflict(false);
    setReadingOrderDragState(null);
  }, [overlayPayload]);

  useEffect(() => {
    if (!layoutEditMode) {
      setPendingRegionPoints([]);
      setMergeLineSelection([]);
      setVertexDragState(null);
      return;
    }
    if (layoutEditTool !== "DRAW_REGION") {
      setPendingRegionPoints([]);
    }
    if (layoutEditTool !== "MERGE_LINES") {
      setMergeLineSelection([]);
    }
    if (layoutEditTool !== "EDIT_VERTICES") {
      setVertexDragState(null);
    }
  }, [layoutEditMode, layoutEditTool]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(paneStorageKey);
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw) as {
        filmstripWidthRem?: unknown;
        inspectorWidthRem?: unknown;
      };
      if (typeof parsed.filmstripWidthRem === "number" && Number.isFinite(parsed.filmstripWidthRem)) {
        setFilmstripWidthRem(
          clampNumber(
            parsed.filmstripWidthRem,
            FILMSTRIP_WIDTH_RANGE.min,
            FILMSTRIP_WIDTH_RANGE.max
          )
        );
      }
      if (typeof parsed.inspectorWidthRem === "number" && Number.isFinite(parsed.inspectorWidthRem)) {
        setInspectorWidthRem(
          clampNumber(
            parsed.inspectorWidthRem,
            INSPECTOR_WIDTH_RANGE.min,
            INSPECTOR_WIDTH_RANGE.max
          )
        );
      }
    } catch {}
  }, [paneStorageKey]);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        paneStorageKey,
        JSON.stringify({
          filmstripWidthRem,
          inspectorWidthRem
        })
      );
    } catch {}
  }, [filmstripWidthRem, inspectorWidthRem, paneStorageKey]);

  useEffect(() => {
    if (!hasUnsavedChanges) {
      return;
    }
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [hasUnsavedChanges]);

  const toggleActions: ToolbarAction[] = [
    {
      id: "toggle-regions",
      label: `Regions (${regions.length})`,
      onAction: () => setShowRegions((value) => !value),
      pressed: showRegions,
      disabled: !workspaceOverlay || regions.length === 0
    },
    {
      id: "toggle-lines",
      label: `Lines (${lines.length})`,
      onAction: () => setShowLines((value) => !value),
      pressed: showLines,
      disabled: !workspaceOverlay || lines.length === 0
    },
    {
      id: "toggle-baselines",
      label: "Baselines",
      onAction: () => setShowBaselines((value) => !value),
      pressed: showBaselines,
      disabled: !workspaceOverlay || !hasBaselines
    },
    {
      id: "toggle-reading-order",
      label: "Reading order",
      onAction: () => setShowReadingOrder((value) => !value),
      pressed: showReadingOrder,
      disabled: !workspaceOverlay || !hasReadingOrder
    }
  ];
  const layoutEditToolOptions: Array<{ id: LayoutEditTool; label: string }> = [
    { id: "SELECT_PAN", label: "Select/pan" },
    { id: "DRAW_REGION", label: "Draw region" },
    { id: "EDIT_VERTICES", label: "Edit vertices" },
    { id: "SPLIT_LINE", label: "Split line" },
    { id: "MERGE_LINES", label: "Merge lines" },
    { id: "DELETE_ELEMENT", label: "Delete" },
    { id: "ASSIGN_REGION_TYPE", label: "Assign type" }
  ];
  const triagePath = projectDocumentLayoutPath(projectId, documentId, {
    tab: "triage",
    runId: selectedRunId
  });

  const navigateToWorkspace = (page: number, runId: string): void => {
    const href = projectDocumentLayoutWorkspacePath(projectId, documentId, {
      page,
      runId
    });
    startTransition(() => {
      router.push(href, { scroll: false });
    });
  };

  const openTriage = (): void => {
    startTransition(() => {
      router.push(triagePath, { scroll: false });
    });
  };

  const resolvePointFromClient = (clientX: number, clientY: number): LayoutOverlayPoint | null => {
    const svg = overlaySvgRef.current;
    if (!svg) {
      return null;
    }
    const rect = svg.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      return null;
    }
    const x = ((clientX - rect.left) / rect.width) * canvasWidth;
    const y = ((clientY - rect.top) / rect.height) * canvasHeight;
    return clampPointToPage({ x, y }, canvasWidth, canvasHeight);
  };

  const reconcileOverlayState = (
    overlay: DocumentLayoutPageOverlay
  ): DocumentLayoutPageOverlay => {
    const next = cloneLayoutOverlay(overlay);
    const regionsOnly = next.elements.filter(isRegionElement);
    const linesOnly = next.elements.filter(isLineElement);
    const regionById = new Map<string, LayoutOverlayRegionElement>();
    for (const region of regionsOnly) {
      regionById.set(region.id, region);
    }
    for (const region of regionsOnly) {
      const currentChildIds = [...region.childIds];
      const actualLineIds = linesOnly
        .filter((line) => line.parentId === region.id)
        .map((line) => line.id);
      const ordered = currentChildIds.filter((lineId) => actualLineIds.includes(lineId));
      for (const lineId of actualLineIds) {
        if (!ordered.includes(lineId)) {
          ordered.push(lineId);
        }
      }
      region.childIds = ordered;
    }
    const validRegionIds = new Set(regionsOnly.map((region) => region.id));
    const excludedRegionIds = new Set(
      regionsOnly
        .filter((region) => region.includeInReadingOrder === false)
        .map((region) => region.id)
    );
    next.readingOrderGroups = next.readingOrderGroups
      .map((group) => ({
        id: group.id,
        ordered: group.ordered,
        regionIds: group.regionIds.filter(
          (regionId) =>
            validRegionIds.has(regionId) && !excludedRegionIds.has(regionId)
        )
      }))
      .filter((group) => group.regionIds.length > 0);
    if (next.readingOrderGroups.length === 0) {
      next.readingOrderMeta.mode = "WITHHELD";
      next.readingOrderMeta.orderWithheld = true;
    } else if (next.readingOrderGroups.every((group) => group.ordered)) {
      next.readingOrderMeta.mode = "ORDERED";
      next.readingOrderMeta.orderWithheld = false;
    } else {
      next.readingOrderMeta.mode = "UNORDERED";
      next.readingOrderMeta.orderWithheld = false;
    }
    next.readingOrderMeta.schemaVersion = 1;
    next.readingOrderMeta.source = "MANUAL_OVERRIDE";
    const validElementIds = new Set(next.elements.map((element) => element.id));
    next.readingOrder = next.readingOrder.filter(
      (edge) =>
        validElementIds.has(edge.fromId) &&
        validElementIds.has(edge.toId) &&
        !excludedRegionIds.has(edge.fromId) &&
        !excludedRegionIds.has(edge.toId)
    );
    return next;
  };

  const stageLayoutEdit = (
    mutator: (overlay: DocumentLayoutPageOverlay) => void,
    operations: LayoutElementsPatchOperation[]
  ): void => {
    if (operations.length === 0) {
      return;
    }
    setLayoutEditSession((session) => {
      if (!session) {
        return session;
      }
      const baseSnapshot: LayoutEditSnapshot = {
        overlay: cloneLayoutOverlay(session.overlay),
        operations: session.operations.map((operation) => ({
          ...operation,
          polygon: Array.isArray(operation.polygon)
            ? operation.polygon.map(cloneOverlayPoint)
            : undefined,
          baseline: Array.isArray(operation.baseline)
            ? operation.baseline.map(cloneOverlayPoint)
            : operation.baseline,
          lineIds: Array.isArray(operation.lineIds) ? [...operation.lineIds] : undefined
        }))
      };
      const nextOverlay = cloneLayoutOverlay(session.overlay);
      mutator(nextOverlay);
      return {
        ...session,
        overlay: reconcileOverlayState(nextOverlay),
        operations: [...session.operations, ...operations],
        undoStack: [...session.undoStack, baseSnapshot].slice(-80),
        redoStack: []
      };
    });
    setLayoutEditError(null);
    setLayoutEditNotice(null);
  };

  const enterLayoutEditMode = (): boolean => {
    if (!canEditLayout) {
      setLayoutEditError("Manual geometry edits require a reviewer-capable project role.");
      return false;
    }
    if (!overlayPayload) {
      setLayoutEditError("Overlay payload is unavailable for manual edit mode.");
      return false;
    }
    const versionEtag =
      typeof overlayPayload.readingOrderMeta.versionEtag === "string" &&
      overlayPayload.readingOrderMeta.versionEtag.trim().length > 0
        ? overlayPayload.readingOrderMeta.versionEtag.trim()
        : null;
    if (!versionEtag) {
      setLayoutEditError("Layout version metadata is unavailable. Refresh before editing.");
      return false;
    }
    setLayoutEditMode(true);
    setLayoutEditTool("SELECT_PAN");
    setLayoutEditSession({
      overlay: cloneLayoutOverlay(overlayPayload),
      operations: [],
      undoStack: [],
      redoStack: [],
      versionEtag
    });
    setPendingRegionPoints([]);
    setMergeLineSelection([]);
    setVertexDragState(null);
    setLayoutEditError(null);
    setLayoutEditNotice(null);
    setLayoutEditConflict(false);
    return true;
  };

  const exitLayoutEditMode = (): void => {
    setLayoutEditMode(false);
    setLayoutEditTool("SELECT_PAN");
    setLayoutEditSession(null);
    setPendingRegionPoints([]);
    setMergeLineSelection([]);
    setVertexDragState(null);
    setLayoutEditSaving(false);
    setLayoutEditConflict(false);
  };

  const discardLayoutEdits = (): void => {
    if (!overlayPayload || !layoutEditSession) {
      return;
    }
    const versionEtag =
      typeof overlayPayload.readingOrderMeta.versionEtag === "string" &&
      overlayPayload.readingOrderMeta.versionEtag.trim().length > 0
        ? overlayPayload.readingOrderMeta.versionEtag.trim()
        : layoutEditSession.versionEtag;
    setLayoutEditSession({
      overlay: cloneLayoutOverlay(overlayPayload),
      operations: [],
      undoStack: [],
      redoStack: [],
      versionEtag
    });
    setPendingRegionPoints([]);
    setMergeLineSelection([]);
    setVertexDragState(null);
    setLayoutEditError(null);
    setLayoutEditNotice("Unsaved edits discarded.");
    setLayoutEditConflict(false);
  };

  const undoLayoutEdit = (): void => {
    setLayoutEditSession((session) => {
      if (!session || session.undoStack.length === 0) {
        return session;
      }
      const previous = cloneLayoutEditSnapshot(
        session.undoStack[session.undoStack.length - 1]
      );
      const currentSnapshot: LayoutEditSnapshot = {
        overlay: cloneLayoutOverlay(session.overlay),
        operations: session.operations.map((operation) => ({ ...operation }))
      };
      return {
        ...session,
        overlay: previous.overlay,
        operations: previous.operations,
        undoStack: session.undoStack.slice(0, -1),
        redoStack: [...session.redoStack, currentSnapshot]
      };
    });
    setLayoutEditError(null);
    setLayoutEditNotice(null);
  };

  const redoLayoutEdit = (): void => {
    setLayoutEditSession((session) => {
      if (!session || session.redoStack.length === 0) {
        return session;
      }
      const nextSnapshot = cloneLayoutEditSnapshot(
        session.redoStack[session.redoStack.length - 1]
      );
      const currentSnapshot: LayoutEditSnapshot = {
        overlay: cloneLayoutOverlay(session.overlay),
        operations: session.operations.map((operation) => ({ ...operation }))
      };
      return {
        ...session,
        overlay: nextSnapshot.overlay,
        operations: nextSnapshot.operations,
        undoStack: [...session.undoStack, currentSnapshot],
        redoStack: session.redoStack.slice(0, -1)
      };
    });
    setLayoutEditError(null);
    setLayoutEditNotice(null);
  };

  const saveLayoutEdits = async (): Promise<boolean> => {
    if (!selectedPage || !layoutEditSession || layoutEditSaving) {
      return false;
    }
    if (layoutEditSession.operations.length === 0) {
      setLayoutEditNotice("No staged edits to save.");
      return true;
    }
    setLayoutEditSaving(true);
    setLayoutEditError(null);
    setLayoutEditNotice(null);
    setLayoutEditConflict(false);
    const result = await requestBrowserApi<UpdateDocumentLayoutElementsResponse>({
      method: "PATCH",
      path: `/projects/${projectId}/documents/${documentId}/layout-runs/${selectedRunId}/pages/${selectedPage.pageId}/elements`,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        versionEtag: layoutEditSession.versionEtag,
        operations: layoutEditSession.operations
      })
    });
    setLayoutEditSaving(false);
    if (!result.ok || !result.data) {
      if (result.status === 409) {
        setLayoutEditConflict(true);
        setLayoutEditError(
          "Layout changed in another session. Reload the latest overlay or discard local edits."
        );
        return false;
      }
      setLayoutEditConflict(false);
      setLayoutEditError(result.detail ?? "Layout edit save failed.");
      return false;
    }
    setLayoutEditConflict(false);
    const savedOverlay = cloneLayoutOverlay(result.data.overlay);
    setLayoutEditSession({
      overlay: savedOverlay,
      operations: [],
      undoStack: [],
      redoStack: [],
      versionEtag: result.data.versionEtag
    });
    setPendingRegionPoints([]);
    setMergeLineSelection([]);
    setVertexDragState(null);
    setLayoutEditNotice(
      result.data.downstreamTranscriptionInvalidated
        ? "Edits saved. Transcription basis marked STALE for this active run."
        : "Edits saved."
    );

    const savedRegions = savedOverlay.elements.filter(isRegionElement);
    const savedMode = savedOverlay.readingOrderMeta.mode;
    const nextMode: LayoutReadingOrderMode =
      savedMode === "ORDERED" || savedMode === "UNORDERED" || savedMode === "WITHHELD"
        ? savedMode
        : resolveDefaultReadingOrderMode(savedOverlay.readingOrderGroups);
    const nextGroups =
      savedOverlay.readingOrderGroups.length > 0
        ? cloneReadingOrderGroups(savedOverlay.readingOrderGroups)
        : resolveFallbackReadingOrderGroups(savedRegions, nextMode);
    setReadingOrderBaseGroups(nextGroups);
    setReadingOrderDraftGroups(cloneReadingOrderGroups(nextGroups));
    setReadingOrderBaseMode(nextMode);
    setReadingOrderDraftMode(nextMode);
    setReadingOrderVersionEtag(result.data.versionEtag);
    setReadingOrderError(null);
    setReadingOrderNotice(null);

    startTransition(() => {
      router.refresh();
    });
    return true;
  };

  const updateElementPolygon = (elementId: string, polygon: LayoutOverlayPoint[]): void => {
    if (!layoutEditSession) {
      return;
    }
    const element = layoutEditSession.overlay.elements.find((entry) => entry.id === elementId);
    if (!element) {
      return;
    }
    const nextPolygon = polygon.map((point) =>
      clampPointToPage(point, canvasWidth, canvasHeight)
    );
    stageLayoutEdit(
      (overlay) => {
        const target = overlay.elements.find((entry) => entry.id === elementId);
        if (!target) {
          return;
        }
        target.polygon = nextPolygon.map(cloneOverlayPoint);
      },
      [
        {
          kind: element.type === "REGION" ? "MOVE_REGION" : "MOVE_LINE",
          regionId: element.type === "REGION" ? element.id : undefined,
          lineId: element.type === "LINE" ? element.id : undefined,
          polygon: nextPolygon.map(cloneOverlayPoint)
        }
      ]
    );
  };

  const commitPendingRegion = (): void => {
    if (!layoutEditSession || pendingRegionPoints.length < 3) {
      return;
    }
    const regionId = resolveNextOverlayId("region", layoutEditSession.overlay.elements);
    const regionPolygon = pendingRegionPoints.map((point) =>
      clampPointToPage(point, canvasWidth, canvasHeight)
    );
    stageLayoutEdit(
      (overlay) => {
        overlay.elements.push({
          id: regionId,
          type: "REGION",
          parentId: null,
          childIds: [],
          regionType: "TEXT",
          includeInReadingOrder: true,
          polygon: regionPolygon.map(cloneOverlayPoint)
        });
      },
      [
        {
          kind: "ADD_REGION",
          regionId,
          regionType: "TEXT",
          includeInReadingOrder: true,
          polygon: regionPolygon.map(cloneOverlayPoint)
        }
      ]
    );
    setPendingRegionPoints([]);
    setSelectedElementId(regionId);
  };

  const splitSelectedLine = (): void => {
    if (!layoutEditSession || !selectedElement || selectedElement.type !== "LINE") {
      return;
    }
    const bounds = resolveBoundingBox(selectedElement.polygon);
    if (!bounds) {
      return;
    }
    const minHeight = bounds.maxY - bounds.minY;
    if (minHeight < 8) {
      setLayoutEditError("Selected line is too small to split safely.");
      return;
    }
    const midY = (bounds.minY + bounds.maxY) / 2;
    const topPolygon = rectanglePolygon(bounds.minX, bounds.minY, bounds.maxX, midY);
    const bottomPolygon = rectanglePolygon(bounds.minX, midY, bounds.maxX, bounds.maxY);
    const topBaselineY = bounds.minY + (midY - bounds.minY) * 0.7;
    const bottomBaselineY = midY + (bounds.maxY - midY) * 0.7;
    const topBaseline = [
      { x: bounds.minX + 4, y: topBaselineY },
      { x: bounds.maxX - 4, y: topBaselineY }
    ];
    const bottomBaseline = [
      { x: bounds.minX + 4, y: bottomBaselineY },
      { x: bounds.maxX - 4, y: bottomBaselineY }
    ];
    const newLineId = resolveNextOverlayId("line", layoutEditSession.overlay.elements);
    const parentRegionId = selectedElement.parentId;
    if (!parentRegionId) {
      setLayoutEditError("Selected line is not attached to a region.");
      return;
    }
    const region = regions.find((entry) => entry.id === parentRegionId);
    const reorderedLineIds = region
      ? [...region.childIds]
      : lines
          .filter((line) => line.parentId === parentRegionId)
          .map((line) => line.id);
    const lineIndex = reorderedLineIds.indexOf(selectedElement.id);
    if (lineIndex >= 0) {
      reorderedLineIds.splice(lineIndex + 1, 0, newLineId);
    } else {
      reorderedLineIds.push(newLineId);
    }
    stageLayoutEdit(
      (overlay) => {
        const targetLine = overlay.elements.find((element) => element.id === selectedElement.id);
        if (!targetLine || targetLine.type !== "LINE") {
          return;
        }
        targetLine.polygon = topPolygon.map(cloneOverlayPoint);
        targetLine.baseline = topBaseline.map(cloneOverlayPoint);
        overlay.elements.push({
          id: newLineId,
          type: "LINE",
          parentId: parentRegionId,
          polygon: bottomPolygon.map(cloneOverlayPoint),
          baseline: bottomBaseline.map(cloneOverlayPoint)
        });
        const targetRegion = overlay.elements.find((element) => element.id === parentRegionId);
        if (targetRegion && targetRegion.type === "REGION") {
          targetRegion.childIds = [...reorderedLineIds];
        }
      },
      [
        {
          kind: "MOVE_LINE",
          lineId: selectedElement.id,
          polygon: topPolygon.map(cloneOverlayPoint)
        },
        {
          kind: "MOVE_BASELINE",
          lineId: selectedElement.id,
          baseline: topBaseline.map(cloneOverlayPoint)
        },
        {
          kind: "ADD_LINE",
          lineId: newLineId,
          parentRegionId,
          polygon: bottomPolygon.map(cloneOverlayPoint),
          baseline: bottomBaseline.map(cloneOverlayPoint)
        },
        {
          kind: "REORDER_REGION_LINES",
          regionId: parentRegionId,
          lineIds: reorderedLineIds
        }
      ]
    );
    setSelectedElementId(newLineId);
  };

  const mergeSelectedLines = (): void => {
    if (!layoutEditSession || mergeLineSelection.length !== 2) {
      return;
    }
    const [firstLineId, secondLineId] = mergeLineSelection;
    const first = lines.find((line) => line.id === firstLineId);
    const second = lines.find((line) => line.id === secondLineId);
    if (!first || !second) {
      return;
    }
    if (!first.parentId || first.parentId !== second.parentId) {
      setLayoutEditError("Select two lines from the same region to merge.");
      return;
    }
    const firstBounds = resolveBoundingBox(first.polygon);
    const secondBounds = resolveBoundingBox(second.polygon);
    if (!firstBounds || !secondBounds) {
      return;
    }
    const mergedBounds = {
      minX: Math.min(firstBounds.minX, secondBounds.minX),
      maxX: Math.max(firstBounds.maxX, secondBounds.maxX),
      minY: Math.min(firstBounds.minY, secondBounds.minY),
      maxY: Math.max(firstBounds.maxY, secondBounds.maxY)
    };
    const mergedPolygon = rectanglePolygon(
      mergedBounds.minX,
      mergedBounds.minY,
      mergedBounds.maxX,
      mergedBounds.maxY
    );
    const baselineY = mergedBounds.maxY - Math.max(2, (mergedBounds.maxY - mergedBounds.minY) * 0.2);
    const mergedBaseline = [
      { x: mergedBounds.minX + 4, y: baselineY },
      { x: mergedBounds.maxX - 4, y: baselineY }
    ];
    const regionLineIds = regions.find((region) => region.id === first.parentId)?.childIds ?? [];
    const reorderedLineIds = regionLineIds.filter((lineId) => lineId !== secondLineId);
    stageLayoutEdit(
      (overlay) => {
        const primary = overlay.elements.find((element) => element.id === firstLineId);
        if (!primary || primary.type !== "LINE") {
          return;
        }
        primary.polygon = mergedPolygon.map(cloneOverlayPoint);
        primary.baseline = mergedBaseline.map(cloneOverlayPoint);
        overlay.elements = overlay.elements.filter((element) => element.id !== secondLineId);
        const region = overlay.elements.find((element) => element.id === first.parentId);
        if (region && region.type === "REGION") {
          region.childIds = [...reorderedLineIds];
        }
      },
      [
        {
          kind: "MOVE_LINE",
          lineId: firstLineId,
          polygon: mergedPolygon.map(cloneOverlayPoint)
        },
        {
          kind: "MOVE_BASELINE",
          lineId: firstLineId,
          baseline: mergedBaseline.map(cloneOverlayPoint)
        },
        {
          kind: "DELETE_LINE",
          lineId: secondLineId
        },
        {
          kind: "REORDER_REGION_LINES",
          regionId: first.parentId,
          lineIds: reorderedLineIds
        }
      ]
    );
    setMergeLineSelection([]);
    setSelectedElementId(firstLineId);
  };

  const deleteSelectedElement = (): void => {
    if (!layoutEditSession || !selectedElement) {
      return;
    }
    const targetId = selectedElement.id;
    if (selectedElement.type === "REGION") {
      stageLayoutEdit(
        (overlay) => {
          overlay.elements = overlay.elements.filter(
            (element) => element.id !== targetId && element.parentId !== targetId
          );
        },
        [{ kind: "DELETE_REGION", regionId: targetId }]
      );
    } else {
      stageLayoutEdit(
        (overlay) => {
          overlay.elements = overlay.elements.filter((element) => element.id !== targetId);
          const parent = overlay.elements.find((element) => element.id === selectedElement.parentId);
          if (parent && parent.type === "REGION") {
            parent.childIds = parent.childIds.filter((lineId) => lineId !== targetId);
          }
        },
        [{ kind: "DELETE_LINE", lineId: targetId }]
      );
    }
    setSelectedElementId(null);
  };

  const setRegionType = (regionId: string, regionType: string): void => {
    if (!regionType.trim()) {
      return;
    }
    stageLayoutEdit(
      (overlay) => {
        const target = overlay.elements.find((element) => element.id === regionId);
        if (!target || target.type !== "REGION") {
          return;
        }
        target.regionType = regionType;
      },
      [{ kind: "RETAG_REGION", regionId, regionType }]
    );
  };

  const setRegionReadingOrderIncluded = (regionId: string, includeInReadingOrder: boolean): void => {
    stageLayoutEdit(
      (overlay) => {
        const target = overlay.elements.find((element) => element.id === regionId);
        if (!target || target.type !== "REGION") {
          return;
        }
        target.includeInReadingOrder = includeInReadingOrder;
      },
      [
        {
          kind: "SET_REGION_READING_ORDER_INCLUDED",
          regionId,
          includeInReadingOrder
        }
      ]
    );
  };

  const assignLineToRegion = (lineId: string, parentRegionId: string): void => {
    const region = regions.find((entry) => entry.id === parentRegionId);
    const lineOrder = region ? [...region.childIds] : [];
    const afterLineId = lineOrder.length > 0 ? lineOrder[lineOrder.length - 1] : undefined;
    const resolvedAfterLineId =
      afterLineId && afterLineId !== lineId ? afterLineId : undefined;
    stageLayoutEdit(
      (overlay) => {
        const target = overlay.elements.find((element) => element.id === lineId);
        if (!target || target.type !== "LINE") {
          return;
        }
        target.parentId = parentRegionId;
      },
      [
        {
          kind: "ASSIGN_LINE_REGION",
          lineId,
          parentRegionId,
          afterLineId: resolvedAfterLineId
        }
      ]
    );
  };

  const reorderLineInRegion = (
    regionId: string,
    lineId: string,
    direction: "up" | "down"
  ): void => {
    const region = regions.find((entry) => entry.id === regionId);
    if (!region) {
      return;
    }
    const lineIds = [...region.childIds];
    const currentIndex = lineIds.indexOf(lineId);
    if (currentIndex < 0) {
      return;
    }
    const nextIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
    if (nextIndex < 0 || nextIndex >= lineIds.length) {
      return;
    }
    const [moved] = lineIds.splice(currentIndex, 1);
    lineIds.splice(nextIndex, 0, moved);
    stageLayoutEdit(
      (overlay) => {
        const target = overlay.elements.find((element) => element.id === regionId);
        if (!target || target.type !== "REGION") {
          return;
        }
        target.childIds = [...lineIds];
      },
      [{ kind: "REORDER_REGION_LINES", regionId, lineIds }]
    );
  };

  useEffect(() => {
    if (!layoutEditMode) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      const modifierPressed = event.metaKey || event.ctrlKey;
      if (!modifierPressed) {
        return;
      }
      const key = event.key.toLowerCase();
      if (key === "z" && !event.shiftKey) {
        if (!layoutEditCanUndo || layoutEditSaving) {
          return;
        }
        event.preventDefault();
        undoLayoutEdit();
        return;
      }
      if (key === "z" && event.shiftKey) {
        if (!layoutEditCanRedo || layoutEditSaving) {
          return;
        }
        event.preventDefault();
        redoLayoutEdit();
        return;
      }
      if (key === "s") {
        if (!layoutEditHasChanges || layoutEditSaving || !selectedPage) {
          return;
        }
        event.preventDefault();
        void saveLayoutEdits();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [
    layoutEditCanRedo,
    layoutEditCanUndo,
    layoutEditHasChanges,
    layoutEditMode,
    layoutEditSaving,
    selectedPage
  ]);

  const moveReadingOrderGroup = (fromIndex: number, toIndex: number): void => {
    if (fromIndex === toIndex) {
      return;
    }
    setReadingOrderDraftGroups((current) => {
      if (
        fromIndex < 0 ||
        toIndex < 0 ||
        fromIndex >= current.length ||
        toIndex >= current.length
      ) {
        return current;
      }
      const next = cloneReadingOrderGroups(current);
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      return next;
    });
  };

  const moveReadingOrderRegion = (
    drag: ReadingOrderDragState,
    targetGroupId: string,
    targetIndex: number
  ): void => {
    setReadingOrderDraftGroups((current) => {
      const next = cloneReadingOrderGroups(current);
      const sourceGroup = next.find((group) => group.id === drag.fromGroupId);
      const targetGroup = next.find((group) => group.id === targetGroupId);
      if (!sourceGroup || !targetGroup) {
        return current;
      }
      const sourceIndex = sourceGroup.regionIds.indexOf(drag.regionId);
      if (sourceIndex < 0) {
        return current;
      }
      sourceGroup.regionIds.splice(sourceIndex, 1);
      const boundedTargetIndex = Math.max(
        0,
        Math.min(targetGroup.regionIds.length, targetIndex)
      );
      const adjustedTargetIndex =
        sourceGroup.id === targetGroup.id && sourceIndex < boundedTargetIndex
          ? boundedTargetIndex - 1
          : boundedTargetIndex;
      targetGroup.regionIds.splice(adjustedTargetIndex, 0, drag.regionId);
      return next.filter((group) => group.regionIds.length > 0);
    });
  };

  const saveReadingOrder = async (): Promise<boolean> => {
    if (!selectedPage || !canEditReadingOrder || readingOrderSaving) {
      return false;
    }
    if (layoutEditMode) {
      setReadingOrderError(
        "Exit geometry edit mode before saving reading-order changes."
      );
      return false;
    }
    if (!readingOrderVersionEtag) {
      setReadingOrderError(
        "Reading-order version is unavailable. Refresh the workspace before saving."
      );
      return false;
    }
    setReadingOrderSaving(true);
    setReadingOrderError(null);
    setReadingOrderNotice(null);
    setReadingOrderConflict(false);
    const result = await requestBrowserApi<UpdateDocumentLayoutReadingOrderResponse>({
      method: "PATCH",
      path: `/projects/${projectId}/documents/${documentId}/layout-runs/${selectedRunId}/pages/${selectedPage.pageId}/reading-order`,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        versionEtag: readingOrderVersionEtag,
        mode: readingOrderDraftMode,
        groups: readingOrderDraftGroups
      })
    });
    setReadingOrderSaving(false);
    if (!result.ok || !result.data) {
      if (result.status === 409) {
        setReadingOrderConflict(true);
        setReadingOrderError(
          "Reading order changed in another session. Reload the latest order or discard local edits."
        );
        return false;
      }
      setReadingOrderConflict(false);
      setReadingOrderError(result.detail ?? "Reading-order save failed.");
      return false;
    }
    setReadingOrderConflict(false);
    const nextGroups = cloneReadingOrderGroups(result.data.groups);
    setReadingOrderBaseGroups(nextGroups);
    setReadingOrderDraftGroups(cloneReadingOrderGroups(nextGroups));
    setReadingOrderBaseMode(result.data.mode);
    setReadingOrderDraftMode(result.data.mode);
    setReadingOrderVersionEtag(result.data.versionEtag);
    setReadingOrderNotice("Reading order saved.");
    startTransition(() => {
      router.refresh();
    });
    return true;
  };

  const revertReadingOrderDraft = (notice: string | null = null): void => {
    setReadingOrderDraftGroups(cloneReadingOrderGroups(readingOrderBaseGroups));
    setReadingOrderDraftMode(readingOrderBaseMode);
    setReadingOrderError(null);
    setReadingOrderConflict(false);
    setReadingOrderNotice(notice);
  };

  const saveUnsavedChanges = async (): Promise<boolean> => {
    let saved = true;
    if (layoutEditHasChanges) {
      saved = (await saveLayoutEdits()) && saved;
    }
    if (readingOrderHasChanges) {
      saved = (await saveReadingOrder()) && saved;
    }
    return saved;
  };

  const discardUnsavedChanges = (): void => {
    if (layoutEditHasChanges) {
      discardLayoutEdits();
    }
    if (readingOrderHasChanges) {
      revertReadingOrderDraft("Unsaved reading-order changes discarded.");
    }
  };

  const applyWorkspaceMode = (mode: WorkspaceMode): boolean => {
    if (mode === "EDIT") {
      setInspectorTab("geometry");
      if (layoutEditMode) {
        return true;
      }
      return enterLayoutEditMode();
    }
    if (layoutEditMode) {
      exitLayoutEditMode();
    }
    setInspectorTab(mode === "READING_ORDER" ? "reading-order" : "geometry");
    return true;
  };

  const executeTransitionAction = (action: WorkspaceTransitionAction): void => {
    if (action.kind === "NAVIGATE") {
      navigateToWorkspace(action.page, action.runId);
      return;
    }
    if (action.kind === "OPEN_TRIAGE") {
      openTriage();
      return;
    }
    applyWorkspaceMode(action.mode);
  };

  const requestTransitionAction = (action: WorkspaceTransitionAction): void => {
    if (
      action.kind === "NAVIGATE" &&
      action.page === selectedPageNumber &&
      action.runId === selectedRunId
    ) {
      return;
    }
    if (action.kind === "SET_MODE" && action.mode === workspaceMode) {
      return;
    }
    if (hasUnsavedChanges) {
      setPendingTransitionAction(action);
      return;
    }
    executeTransitionAction(action);
  };

  const cancelPendingTransition = (): void => {
    setPendingTransitionAction(null);
  };

  const saveAndContinuePendingTransition = async (): Promise<void> => {
    if (!pendingTransitionAction) {
      return;
    }
    const action = pendingTransitionAction;
    const saved = await saveUnsavedChanges();
    if (!saved) {
      return;
    }
    setPendingTransitionAction(null);
    executeTransitionAction(action);
  };

  const discardAndContinuePendingTransition = (): void => {
    if (!pendingTransitionAction) {
      return;
    }
    const action = pendingTransitionAction;
    discardUnsavedChanges();
    setPendingTransitionAction(null);
    executeTransitionAction(action);
  };

  useEffect(() => {
    if (!pendingTransitionAction) {
      return;
    }
    if (hasUnsavedChanges || layoutEditSaving || readingOrderSaving) {
      return;
    }
    const action = pendingTransitionAction;
    setPendingTransitionAction(null);
    executeTransitionAction(action);
  }, [
    executeTransitionAction,
    hasUnsavedChanges,
    layoutEditSaving,
    pendingTransitionAction,
    readingOrderSaving
  ]);

  const refreshWorkspaceFromServer = (): void => {
    startTransition(() => {
      router.refresh();
    });
  };

  const setFilmstripWidthPreset = (preset: "default" | "narrow" | "wide"): void => {
    setFilmstripWidthRem(
      clampNumber(
        FILMSTRIP_WIDTH_PRESETS[preset],
        FILMSTRIP_WIDTH_RANGE.min,
        FILMSTRIP_WIDTH_RANGE.max
      )
    );
  };

  const setInspectorWidthPreset = (preset: "default" | "narrow" | "wide"): void => {
    setInspectorWidthRem(
      clampNumber(
        INSPECTOR_WIDTH_PRESETS[preset],
        INSPECTOR_WIDTH_RANGE.min,
        INSPECTOR_WIDTH_RANGE.max
      )
    );
  };

  const handleCanvasBackgroundClick = (event: MouseEvent<SVGRectElement>): void => {
    if (layoutEditMode && layoutEditTool === "DRAW_REGION") {
      const nextPoint = resolvePointFromClient(event.clientX, event.clientY);
      if (!nextPoint) {
        return;
      }
      setPendingRegionPoints((current) => [...current, nextPoint]);
      return;
    }
    setSelectedElementId(null);
    if (layoutEditMode && layoutEditTool === "MERGE_LINES") {
      setMergeLineSelection([]);
    }
  };

  const beginVertexDrag = (
    elementId: string,
    vertexIndex: number,
    event: PointerEvent<SVGCircleElement>
  ): void => {
    if (!layoutEditMode || layoutEditTool !== "EDIT_VERTICES" || !selectedElement) {
      return;
    }
    if (selectedElement.id !== elementId) {
      return;
    }
    const target = event.currentTarget;
    target.setPointerCapture(event.pointerId);
    setVertexDragState({
      elementId,
      pointerId: event.pointerId,
      vertexIndex,
      originalPoints: selectedElement.polygon.map(cloneOverlayPoint),
      points: selectedElement.polygon.map(cloneOverlayPoint)
    });
  };

  const handlePageImageError = (): void => {
    const requestPath = resolvedImagePath;
    setPageImageState((current) => {
      if (!requestPath || latestResolvedImagePathRef.current !== requestPath) {
        return current;
      }
      if (current.retryAttempt < PAGE_IMAGE_MAX_RETRY_ATTEMPTS) {
        return {
          retryAttempt: current.retryAttempt + 1,
          status: "loading"
        };
      }
      return {
        retryAttempt: current.retryAttempt,
        status: "error"
      };
    });
  };

  const handlePageImageLoad = (): void => {
    const requestPath = resolvedImagePath;
    setPageImageState((current) => {
      if (!requestPath || latestResolvedImagePathRef.current !== requestPath) {
        return current;
      }
      if (current.status === "loaded") {
        return current;
      }
      return {
        retryAttempt: current.retryAttempt,
        status: "loaded"
      };
    });
  };

  const updateVertexDrag = (event: PointerEvent<SVGCircleElement>): void => {
    setVertexDragState((current) => {
      if (!current || current.pointerId !== event.pointerId) {
        return current;
      }
      const nextPoint = resolvePointFromClient(event.clientX, event.clientY);
      if (!nextPoint) {
        return current;
      }
      const nextPoints = [...current.points];
      nextPoints[current.vertexIndex] = nextPoint;
      return {
        ...current,
        points: nextPoints
      };
    });
  };

  const endVertexDrag = (event: PointerEvent<SVGCircleElement>): void => {
    const state = vertexDragState;
    if (!state || state.pointerId !== event.pointerId) {
      return;
    }
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setVertexDragState(null);
    if (!areOverlayPointsEqual(state.originalPoints, state.points)) {
      updateElementPolygon(state.elementId, state.points);
    }
  };

  const readingOrderPanel = (
    <>
      <ul className="projectMetaList">
        <li>
          <span>Mode</span>
          <strong>{workspaceOverlay?.readingOrderMeta.mode ?? readingOrderDraftMode}</strong>
        </li>
        <li>
          <span>Source</span>
          <strong>{workspaceOverlay?.readingOrderMeta.source ?? "Unknown"}</strong>
        </li>
        <li>
          <span>Ambiguity score</span>
          <strong>
            {typeof workspaceOverlay?.readingOrderMeta.ambiguityScore === "number"
              ? workspaceOverlay.readingOrderMeta.ambiguityScore.toFixed(3)
              : "N/A"}
          </strong>
        </li>
        <li>
          <span>Column certainty</span>
          <strong>
            {typeof workspaceOverlay?.readingOrderMeta.columnCertainty === "number"
              ? workspaceOverlay.readingOrderMeta.columnCertainty.toFixed(3)
              : "N/A"}
          </strong>
        </li>
      </ul>
      <label className="documentViewerRunSelector" htmlFor="reading-order-mode">
        <span>Reading-order mode</span>
        <select
          id="reading-order-mode"
          disabled={!canEditReadingOrder || readingOrderSaving || layoutEditMode}
          onChange={(event) => {
            const nextMode = event.target.value as LayoutReadingOrderMode;
            setReadingOrderDraftMode(nextMode);
            if (nextMode === "WITHHELD") {
              setReadingOrderDraftGroups([]);
            } else if (readingOrderDraftGroups.length === 0) {
              setReadingOrderDraftGroups(resolveFallbackReadingOrderGroups(regions, nextMode));
            }
          }}
          value={readingOrderDraftMode}
        >
          <option value="ORDERED">ORDERED</option>
          <option value="UNORDERED">UNORDERED</option>
          <option value="WITHHELD">WITHHELD</option>
        </select>
      </label>
      {readingOrderDraftMode === "WITHHELD" ? (
        <SectionState
          kind="degraded"
          title="Order withheld"
          description="Strict order is withheld for this page until ambiguity is resolved."
        />
      ) : readingOrderDraftGroups.length === 0 ? (
        <SectionState
          kind="empty"
          title="No reading-order groups"
          description="Create groups by switching mode or refreshing the page overlay."
        />
      ) : (
        <ul className="layoutInspectorList" role="tree">
          {readingOrderDraftGroups.map((group, groupIndex) => (
            <li key={group.id} role="treeitem">
              <div className="layoutInspectorButton" data-selected={undefined}>
                <span>{group.id}</span>
                <span>{group.regionIds.length} regions</span>
              </div>
              <div className="buttonRow layoutReadingOrderControls">
                <label className="layoutReadingOrderCheckbox">
                  <input
                    checked={group.ordered}
                    disabled={!canEditReadingOrder || readingOrderSaving || layoutEditMode}
                    onChange={(event) => {
                      const checked = event.target.checked;
                      setReadingOrderDraftGroups((current) =>
                        current.map((entry) =>
                          entry.id === group.id
                            ? { ...entry, ordered: checked }
                            : entry
                        )
                      );
                    }}
                    type="checkbox"
                  />
                  Ordered group
                </label>
                <button
                  className="secondaryButton"
                  disabled={
                    !canEditReadingOrder ||
                    readingOrderSaving ||
                    layoutEditMode ||
                    groupIndex === 0
                  }
                  onClick={() => moveReadingOrderGroup(groupIndex, groupIndex - 1)}
                  type="button"
                >
                  Group up
                </button>
                <button
                  className="secondaryButton"
                  disabled={
                    !canEditReadingOrder ||
                    readingOrderSaving ||
                    layoutEditMode ||
                    groupIndex >= readingOrderDraftGroups.length - 1
                  }
                  onClick={() => moveReadingOrderGroup(groupIndex, groupIndex + 1)}
                  type="button"
                >
                  Group down
                </button>
              </div>
              <ul
                className="layoutInspectorList layoutReadingOrderList"
                onDragOver={(event) => {
                  if (!canEditReadingOrder || readingOrderSaving || !readingOrderDragState) {
                    return;
                  }
                  event.preventDefault();
                }}
                onDrop={(event) => {
                  if (!readingOrderDragState || !canEditReadingOrder || readingOrderSaving) {
                    return;
                  }
                  event.preventDefault();
                  moveReadingOrderRegion(
                    readingOrderDragState,
                    group.id,
                    group.regionIds.length
                  );
                  setReadingOrderDragState(null);
                }}
              >
                {group.regionIds.map((regionId, regionIndex) => (
                  <li key={`${group.id}:${regionId}`}>
                    <button
                      className="layoutInspectorButton"
                      data-selected={selectedRegionId === regionId ? "true" : undefined}
                      draggable={canEditReadingOrder && !readingOrderSaving && !layoutEditMode}
                      onClick={() => setSelectedElementId(regionId)}
                      onDragStart={() =>
                        setReadingOrderDragState({
                          regionId,
                          fromGroupId: group.id
                        })
                      }
                      onDragEnd={() => setReadingOrderDragState(null)}
                      onDragOver={(event) => {
                        if (
                          !canEditReadingOrder ||
                          readingOrderSaving ||
                          !readingOrderDragState
                        ) {
                          return;
                        }
                        event.preventDefault();
                      }}
                      onDrop={(event) => {
                        if (
                          !readingOrderDragState ||
                          !canEditReadingOrder ||
                          readingOrderSaving
                        ) {
                          return;
                        }
                        event.preventDefault();
                        moveReadingOrderRegion(readingOrderDragState, group.id, regionIndex);
                        setReadingOrderDragState(null);
                      }}
                      type="button"
                    >
                      <span>{regionId}</span>
                      <span>Drag to reorder</span>
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
      <div className="buttonRow">
        <button
          className="secondaryButton"
          disabled={
            !canEditReadingOrder ||
            !readingOrderHasChanges ||
            readingOrderSaving ||
            layoutEditMode
          }
          onClick={() => {
            void saveReadingOrder();
          }}
          type="button"
        >
          {readingOrderSaving ? "Saving..." : "Save reading order"}
        </button>
        <button
          className="secondaryButton"
          disabled={!readingOrderHasChanges || readingOrderSaving}
          onClick={() => revertReadingOrderDraft("Unsaved reading-order changes discarded.")}
          type="button"
        >
          Revert
        </button>
      </div>
      {!canEditReadingOrder ? (
        <p className="ukde-muted">
          Reading-order edits require a reviewer-capable project role.
        </p>
      ) : layoutEditMode ? (
        <p className="ukde-muted">
          Reading-order save is disabled while geometry edit mode is active.
        </p>
      ) : null}
      {readingOrderHasChanges ? (
        <p className="ukde-muted">Unsaved reading-order changes.</p>
      ) : null}
      {readingOrderError ? (
        <SectionState kind="degraded" title="Save failed" description={readingOrderError} />
      ) : null}
      {readingOrderConflict ? (
        <div className="buttonRow layoutWorkspaceConflictActions">
          <button
            className="secondaryButton"
            onClick={refreshWorkspaceFromServer}
            type="button"
          >
            Reload latest order
          </button>
          <button
            className="secondaryButton"
            onClick={() =>
              revertReadingOrderDraft("Local reading-order draft discarded after conflict.")
            }
            type="button"
          >
            Discard local draft
          </button>
        </div>
      ) : null}
      {readingOrderNotice ? (
        <SectionState kind="success" title="Saved" description={readingOrderNotice} />
      ) : null}
    </>
  );

  const filmstripPanel = (
    <>
      <h2>Page filmstrip</h2>
      {pages.length === 0 ? (
        <SectionState
          kind="empty"
          title="No pages available"
          description="Page rows will appear when layout page results are available."
        />
      ) : (
        <ul>
          {pages.map((page) => (
            <li key={page.pageId}>
              <button
                aria-current={page.pageIndex + 1 === selectedPageNumber ? "page" : undefined}
                className="documentViewerFilmstripLink layoutFilmstripButton"
                onClick={() =>
                  requestTransitionAction({
                    kind: "NAVIGATE",
                    page: page.pageIndex + 1,
                    runId: selectedRunId
                  })
                }
                type="button"
              >
                <span
                  className="documentViewerFilmstripThumbPlaceholder"
                  data-status={page.status === "FAILED" || page.status === "CANCELED" ? "failed" : undefined}
                >
                  Page {page.pageIndex + 1}
                </span>
                <span>
                  <strong>Page {page.pageIndex + 1}</strong>
                  <span className="qualityTriageSubStatus">{page.status}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );

  const inspectorPanel = (
    <>
      <h2>Inspector</h2>
      {!selectedPage ? (
        <SectionState
          kind="empty"
          title="No page selected"
          description="Choose a page from the filmstrip to inspect metrics and geometry."
        />
      ) : (
        <>
          <div className="buttonRow layoutInspectorTabs">
            <button
              className="secondaryButton"
              data-selected={workspaceMode !== "READING_ORDER" ? "true" : undefined}
              onClick={() =>
                requestTransitionAction({
                  kind: "SET_MODE",
                  mode: "INSPECT"
                })
              }
              type="button"
            >
              Geometry
            </button>
            <button
              className="secondaryButton"
              data-selected={workspaceMode === "READING_ORDER" ? "true" : undefined}
              onClick={() =>
                requestTransitionAction({
                  kind: "SET_MODE",
                  mode: "READING_ORDER"
                })
              }
              type="button"
            >
              Reading order
            </button>
          </div>
          {inspectorTab === "geometry" ? (
            <>
          <div className="buttonRow">
            <StatusChip tone={resolvePageTone(selectedPage.status)}>{selectedPage.status}</StatusChip>
            <StatusChip tone={resolvePageTone(selectedPage.pageRecallStatus)}>
              {selectedPage.pageRecallStatus}
            </StatusChip>
          </div>
          <ul className="projectMetaList">
            <li>
              <span>Run ID</span>
              <strong>{selectedRunId}</strong>
            </li>
            <li>
              <span>Page</span>
              <strong>{selectedPage.pageIndex + 1}</strong>
            </li>
            <li>
              <span>Regions</span>
              <strong>
                {workspaceOverlay
                  ? regions.length
                  : formatMetricCount(
                      selectedPage.metricsJson.num_regions ??
                        selectedPage.metricsJson.regions_detected
                    )}
              </strong>
            </li>
            <li>
              <span>Lines</span>
              <strong>
                {workspaceOverlay
                  ? lines.length
                  : formatMetricCount(
                      selectedPage.metricsJson.num_lines ??
                        selectedPage.metricsJson.lines_detected
                    )}
              </strong>
            </li>
            <li>
              <span>Region coverage</span>
              <strong>
                {formatMetricPercent(
                  selectedPage.metricsJson.region_coverage_percent ??
                    selectedPage.metricsJson.coverage_percent
                )}
              </strong>
            </li>
            <li>
              <span>Line coverage</span>
              <strong>
                {formatMetricPercent(
                  selectedPage.metricsJson.line_coverage_percent ??
                    selectedPage.metricsJson.coverage_percent
                )}
              </strong>
            </li>
            <li>
              <span>Reading edges</span>
              <strong>{workspaceOverlay ? workspaceOverlay.readingOrder.length : 0}</strong>
            </li>
          </ul>

          <h3>Warnings</h3>
          {selectedPage.warningsJson.length === 0 ? (
            <p className="ukde-muted">No warning codes on this page result.</p>
          ) : (
            <div className="documentViewerWarningChips">
              {selectedPage.warningsJson.map((warningCode) => (
                <StatusChip key={warningCode} tone="warning">
                  {warningCode}
                </StatusChip>
              ))}
            </div>
          )}

          <h3>Recall risk</h3>
          {recallStatusError ? (
            <SectionState
              kind="degraded"
              title="Recall status unavailable"
              description={recallStatusError}
            />
          ) : recallStatus ? (
            <>
              <ul className="projectMetaList">
                <li>
                  <span>Recall check version</span>
                  <strong>{recallStatus.recallCheckVersion ?? "Not persisted"}</strong>
                </li>
                <li>
                  <span>Missed-text risk score</span>
                  <strong>
                    {typeof recallStatus.missedTextRiskScore === "number"
                      ? recallStatus.missedTextRiskScore.toFixed(3)
                      : "N/A"}
                  </strong>
                </li>
                <li>
                  <span>Unresolved count</span>
                  <strong>{recallStatus.unresolvedCount}</strong>
                </li>
              </ul>
              {recallStatus.blockerReasonCodes.length === 0 ? (
                <p className="ukde-muted">No activation blockers on this page.</p>
              ) : (
                <div className="documentViewerWarningChips">
                  {recallStatus.blockerReasonCodes.map((code) => (
                    <StatusChip key={code} tone="warning">
                      {code}
                    </StatusChip>
                  ))}
                </div>
              )}
            </>
          ) : (
            <p className="ukde-muted">Recall status has not been loaded for this page.</p>
          )}

          <h3>Rescue candidates</h3>
          {rescueCandidatesError ? (
            null
          ) : rescueCandidates.length === 0 ? (
            <p className="ukde-muted">No rescue candidates for this page.</p>
          ) : (
            <ul className="layoutInspectorList">
              {rescueCandidates.map((candidate) => {
                const bbox = candidate.geometryJson.bbox as
                  | { x?: number; y?: number; width?: number; height?: number }
                  | undefined;
                const bboxLabel =
                  bbox &&
                  typeof bbox.x === "number" &&
                  typeof bbox.y === "number" &&
                  typeof bbox.width === "number" &&
                  typeof bbox.height === "number"
                    ? `${Math.round(bbox.x)},${Math.round(bbox.y)} · ${Math.round(bbox.width)}×${Math.round(bbox.height)}`
                    : "Geometry unavailable";
                return (
                  <li key={candidate.id}>
                    <div className="layoutInspectorButton" data-selected={undefined}>
                      <span>{candidate.candidateKind}</span>
                      <span>{bboxLabel}</span>
                      <span>
                        <StatusChip tone={resolveRescueTone(candidate.status)}>
                          {candidate.status}
                        </StatusChip>
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {layoutEditMode ? (
            <section className="layoutEditInspectorPanel">
              <h3>Edit session</h3>
              <p className="ukde-muted">
                Tool: {layoutEditToolOptions.find((tool) => tool.id === layoutEditTool)?.label}
              </p>
              {selectedElement?.type === "REGION" ? (
                <>
                  <label className="documentViewerRunSelector" htmlFor="region-type-input">
                    <span>Region type</span>
                    <select
                      id="region-type-input"
                      disabled={layoutEditSaving}
                      onChange={(event) =>
                        setRegionType(selectedElement.id, event.target.value)
                      }
                      value={selectedElement.regionType ?? "TEXT"}
                    >
                      <option value="TEXT">TEXT</option>
                      <option value="HEADER">HEADER</option>
                      <option value="MARGINALIA">MARGINALIA</option>
                      <option value="FOOTNOTE">FOOTNOTE</option>
                      <option value="TABLE">TABLE</option>
                      <option value="IMAGE">IMAGE</option>
                      <option value="OTHER">OTHER</option>
                    </select>
                  </label>
                  <label className="layoutReadingOrderCheckbox">
                    <input
                      checked={selectedElement.includeInReadingOrder !== false}
                      disabled={layoutEditSaving}
                      onChange={(event) =>
                        setRegionReadingOrderIncluded(selectedElement.id, event.target.checked)
                      }
                      type="checkbox"
                    />
                    Include in reading order
                  </label>
                </>
              ) : null}
              {selectedElement?.type === "LINE" ? (
                <>
                  <label className="documentViewerRunSelector" htmlFor="line-region-assignment">
                    <span>Assign to region</span>
                    <select
                      id="line-region-assignment"
                      disabled={layoutEditSaving}
                      onChange={(event) =>
                        assignLineToRegion(selectedElement.id, event.target.value)
                      }
                      value={selectedElement.parentId ?? ""}
                    >
                      {regions.map((region) => (
                        <option key={region.id} value={region.id}>
                          {region.id}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selectedElement.parentId ? (
                    <div className="buttonRow">
                      <button
                        className="secondaryButton"
                        disabled={layoutEditSaving}
                        onClick={() =>
                          reorderLineInRegion(selectedElement.parentId ?? "", selectedElement.id, "up")
                        }
                        type="button"
                      >
                        Line up
                      </button>
                      <button
                        className="secondaryButton"
                        disabled={layoutEditSaving}
                        onClick={() =>
                          reorderLineInRegion(
                            selectedElement.parentId ?? "",
                            selectedElement.id,
                            "down"
                          )
                        }
                        type="button"
                      >
                        Line down
                      </button>
                    </div>
                  ) : null}
                  <div className="buttonRow">
                    <button
                      className="secondaryButton"
                      disabled={layoutEditSaving || layoutEditTool !== "SPLIT_LINE"}
                      onClick={splitSelectedLine}
                      type="button"
                    >
                      Split selected line
                    </button>
                  </div>
                </>
              ) : null}
              {selectedElement && layoutEditTool === "EDIT_VERTICES" ? (
                <div className="layoutEditVerticesList">
                  {selectedElement.polygon.map((point, index) => (
                    <label key={`${selectedElement.id}-vertex-${index}`}>
                      <span>V{index + 1}</span>
                      <input
                        disabled={layoutEditSaving}
                        onChange={(event) => {
                          const nextX = Number.parseFloat(event.target.value);
                          if (!Number.isFinite(nextX)) {
                            return;
                          }
                          const nextPolygon = selectedElement.polygon.map((entry, pointIndex) =>
                            pointIndex === index ? { x: nextX, y: entry.y } : entry
                          );
                          updateElementPolygon(selectedElement.id, nextPolygon);
                        }}
                        type="number"
                        value={point.x.toFixed(1)}
                      />
                      <input
                        disabled={layoutEditSaving}
                        onChange={(event) => {
                          const nextY = Number.parseFloat(event.target.value);
                          if (!Number.isFinite(nextY)) {
                            return;
                          }
                          const nextPolygon = selectedElement.polygon.map((entry, pointIndex) =>
                            pointIndex === index ? { x: entry.x, y: nextY } : entry
                          );
                          updateElementPolygon(selectedElement.id, nextPolygon);
                        }}
                        type="number"
                        value={point.y.toFixed(1)}
                      />
                    </label>
                  ))}
                </div>
              ) : null}
              {selectedElement && layoutEditTool === "DELETE_ELEMENT" ? (
                <div className="buttonRow">
                  <button
                    className="secondaryButton"
                    disabled={layoutEditSaving}
                    onClick={deleteSelectedElement}
                    type="button"
                  >
                    Delete selected {selectedElement.type === "REGION" ? "region" : "line"}
                  </button>
                </div>
              ) : null}
              <p className="ukde-muted">
                Save creates a new immutable layout version and refreshes artifacts for this page.
              </p>
            </section>
          ) : null}

          <div className="layoutInspectorHeadingRow">
            <h3>Region tree</h3>
            <button
              className="secondaryButton"
              disabled={!selectedElementId}
              onClick={() => {
                setSelectedElementId(null);
                if (layoutEditMode && layoutEditTool === "MERGE_LINES") {
                  setMergeLineSelection([]);
                }
              }}
              type="button"
            >
              Clear selection
            </button>
          </div>
          {regions.length === 0 ? (
            <p className="ukde-muted">No region geometry available for this page.</p>
          ) : (
            <ul className="layoutInspectorList" role="tree">
              {regions.map((region) => {
                const lineCount = lines.filter((line) => line.parentId === region.id).length;
                const selected = selectedRegionId === region.id;
                return (
                  <li key={region.id} role="treeitem" aria-selected={selected}>
                    <button
                      className="layoutInspectorButton"
                      data-selected={selected ? "true" : undefined}
                      onClick={() => setSelectedElementId(region.id)}
                      onFocus={() => setHoveredElementId(region.id)}
                      onMouseEnter={() => setHoveredElementId(region.id)}
                      onMouseLeave={() => setHoveredElementId(null)}
                      type="button"
                    >
                      <span>{region.id}</span>
                      <span>{lineCount} lines</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          <h3>
            Line list
            {selectedRegionId ? (
              <span className="ukde-muted"> (filtered by {selectedRegionId})</span>
            ) : null}
          </h3>
          {filteredLines.length === 0 ? (
            <p className="ukde-muted">No line geometry for the current filter.</p>
          ) : (
            <ul className="layoutInspectorList">
              {filteredLines.map((line) => {
                const selected = selectedElementId === line.id;
                const mergeSelected = mergeLineSelection.includes(line.id);
                return (
                  <li key={line.id}>
                    <button
                      className="layoutInspectorButton"
                      data-selected={selected ? "true" : undefined}
                      onClick={() => {
                        if (layoutEditMode && layoutEditTool === "MERGE_LINES") {
                          setMergeLineSelection((current) => {
                            if (current.includes(line.id)) {
                              return current.filter((entry) => entry !== line.id);
                            }
                            if (current.length >= 2) {
                              return [current[1], line.id];
                            }
                            return [...current, line.id];
                          });
                        }
                        setSelectedElementId(line.id);
                      }}
                      onFocus={() => setHoveredElementId(line.id)}
                      onMouseEnter={() => setHoveredElementId(line.id)}
                      onMouseLeave={() => setHoveredElementId(null)}
                      type="button"
                    >
                      <span>{line.id}</span>
                      <span>{mergeSelected ? "Merge selected" : line.parentId}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
            </>
          ) : (
            readingOrderPanel
          )}
        </>
      )}
    </>
  );

  return (
    <>
      <section className="sectionCard ukde-panel documentViewerToolbar">
        <p className="ukde-eyebrow">Layout workspace</p>
        <h2>{documentName}</h2>
        <div className="documentViewerToolbarRow layoutWorkspaceToolbarRow">
            <label
              className="documentViewerRunSelector layoutWorkspaceToolbarCluster layoutWorkspaceToolbarCluster--run"
              htmlFor="layout-run-selector"
            >
              <span>Run selector</span>
              <select
                id="layout-run-selector"
                onChange={(event) =>
                  requestTransitionAction({
                    kind: "NAVIGATE",
                    page: selectedPageNumber,
                    runId: event.target.value
                  })
                }
                value={selectedRunId}
              >
                {runs.map((run) => (
                  <option key={run.id} value={run.id}>
                    {run.id} · {run.status}
                  </option>
                ))}
              </select>
            </label>

            <div
              className="documentViewerModeSelector layoutWorkspaceToolbarCluster layoutWorkspaceToolbarCluster--mode"
              role="group"
              aria-label="Workspace mode"
            >
              <button
                aria-pressed={workspaceMode === "INSPECT"}
                className="secondaryButton"
                onClick={() =>
                  requestTransitionAction({
                    kind: "SET_MODE",
                    mode: "INSPECT"
                  })
                }
                type="button"
              >
                Inspect
              </button>
              <button
                aria-pressed={workspaceMode === "READING_ORDER"}
                className="secondaryButton"
                onClick={() =>
                  requestTransitionAction({
                    kind: "SET_MODE",
                    mode: "READING_ORDER"
                  })
                }
                type="button"
              >
                Reading order
              </button>
              <button
                aria-pressed={workspaceMode === "EDIT"}
                className="secondaryButton"
                disabled={!canEditLayout || !workspaceOverlay}
                onClick={() =>
                  requestTransitionAction({
                    kind: "SET_MODE",
                    mode: "EDIT"
                  })
                }
                type="button"
              >
                Edit
              </button>
            </div>

            <div className="layoutWorkspaceToolbarCluster layoutWorkspaceToolbarCluster--overlays">
              <Toolbar actions={toggleActions} label="Layout overlay controls" />
            </div>

            <label
              className="layoutWorkspaceOpacity layoutWorkspaceToolbarCluster layoutWorkspaceToolbarCluster--opacity"
              htmlFor="layout-overlay-opacity"
            >
              <span>Overlay opacity</span>
              <input
                id="layout-overlay-opacity"
                max={100}
                min={15}
                onChange={(event) => {
                  const next = Number.parseInt(event.target.value, 10);
                  if (!Number.isFinite(next)) {
                    return;
                  }
                  setOverlayOpacityPercent(Math.max(15, Math.min(100, next)));
                }}
                step={1}
                type="range"
                value={overlayOpacityPercent}
              />
              <strong>{overlayOpacityPercent}%</strong>
            </label>

            <div className="buttonRow layoutWorkspacePrimaryActions layoutWorkspaceToolbarCluster layoutWorkspaceToolbarCluster--actions">
              {workspaceMode === "EDIT" ? (
                <>
                  <button
                    className="secondaryButton"
                    disabled={!layoutEditCanUndo || layoutEditSaving}
                    onClick={undoLayoutEdit}
                    type="button"
                  >
                    Undo
                  </button>
                  <button
                    className="secondaryButton"
                    disabled={!layoutEditCanRedo || layoutEditSaving}
                    onClick={redoLayoutEdit}
                    type="button"
                  >
                    Redo
                  </button>
                  <button
                    className="secondaryButton"
                    disabled={!layoutEditHasChanges || layoutEditSaving}
                    onClick={discardLayoutEdits}
                    type="button"
                  >
                    Discard
                  </button>
                  <button
                    className="secondaryButton"
                    disabled={!layoutEditHasChanges || layoutEditSaving}
                    onClick={() => {
                      void saveLayoutEdits();
                    }}
                    type="button"
                  >
                    {layoutEditSaving ? "Saving..." : "Save edits"}
                  </button>
                </>
              ) : workspaceMode === "READING_ORDER" ? (
                <>
                  <button
                    className="secondaryButton"
                    disabled={!readingOrderHasChanges || readingOrderSaving}
                    onClick={() =>
                      revertReadingOrderDraft("Unsaved reading-order changes discarded.")
                    }
                    type="button"
                  >
                    Discard
                  </button>
                  <button
                    className="secondaryButton"
                    disabled={
                      !canEditReadingOrder ||
                      !readingOrderHasChanges ||
                      readingOrderSaving ||
                      layoutEditMode
                    }
                    onClick={() => {
                      void saveReadingOrder();
                    }}
                    type="button"
                  >
                    {readingOrderSaving ? "Saving..." : "Save order"}
                  </button>
                </>
              ) : null}
              <button
                className="secondaryButton"
                onClick={() =>
                  requestTransitionAction({
                    kind: "OPEN_TRIAGE"
                  })
                }
                type="button"
              >
                Open triage
              </button>
            </div>

            <details className="layoutWorkspaceOverflowPanel layoutWorkspaceToolbarCluster layoutWorkspaceToolbarCluster--overflow">
              <summary>Workspace tools</summary>
              <div className="layoutWorkspaceOverflowBody">
                <div className="buttonRow">
                  <button
                    className="secondaryButton"
                    onClick={() => setZoomPercent((value) => Math.max(50, value - 10))}
                    type="button"
                  >
                    Zoom out
                  </button>
                  <button
                    className="secondaryButton"
                    onClick={() => setZoomPercent(100)}
                    type="button"
                  >
                    Fit
                  </button>
                  <button
                    className="secondaryButton"
                    onClick={() => setZoomPercent((value) => Math.min(400, value + 10))}
                    type="button"
                  >
                    Zoom in
                  </button>
                </div>
                <div className="buttonRow">
                  <button
                    className="secondaryButton"
                    onClick={() => {
                      if (shellState === "Focus") {
                        setFilmstripDrawerOpen((open) => !open);
                        return;
                      }
                      setFilmstripCollapsed((collapsed) => !collapsed);
                    }}
                    type="button"
                  >
                    {shellState === "Focus"
                      ? filmstripDrawerOpen
                        ? "Close filmstrip"
                        : "Open filmstrip"
                      : filmstripCollapsed
                        ? "Show filmstrip"
                        : "Hide filmstrip"}
                  </button>
                  {!showInspectorAside ? (
                    <button
                      className="secondaryButton"
                      onClick={() => setInspectorDrawerOpen((open) => !open)}
                      type="button"
                    >
                      {inspectorDrawerOpen ? "Close inspector" : "Inspector drawer"}
                    </button>
                  ) : null}
                </div>
                <div className="layoutWorkspacePaneControls">
                  <span>Filmstrip width</span>
                  <div className="buttonRow">
                    <button
                      className="secondaryButton"
                      onClick={() => setFilmstripWidthPreset("narrow")}
                      type="button"
                    >
                      Narrow
                    </button>
                    <button
                      className="secondaryButton"
                      onClick={() => setFilmstripWidthPreset("default")}
                      type="button"
                    >
                      Default
                    </button>
                    <button
                      className="secondaryButton"
                      onClick={() => setFilmstripWidthPreset("wide")}
                      type="button"
                    >
                      Wide
                    </button>
                  </div>
                </div>
                <div className="layoutWorkspacePaneControls">
                  <span>Inspector width</span>
                  <div className="buttonRow">
                    <button
                      className="secondaryButton"
                      onClick={() => setInspectorWidthPreset("narrow")}
                      type="button"
                    >
                      Narrow
                    </button>
                    <button
                      className="secondaryButton"
                      onClick={() => setInspectorWidthPreset("default")}
                      type="button"
                    >
                      Default
                    </button>
                    <button
                      className="secondaryButton"
                      onClick={() => setInspectorWidthPreset("wide")}
                      type="button"
                    >
                      Wide
                    </button>
                  </div>
                </div>
              </div>
            </details>
        </div>
        {pendingTransitionAction ? (
          <section className="layoutWorkspacePendingTransition" role="status" aria-live="polite">
            <p>
              Unsaved changes are staged. Save before you{" "}
              {resolvePendingTransitionSummary(pendingTransitionAction)}?
            </p>
            <div className="buttonRow">
              <button
                className="secondaryButton"
                disabled={layoutEditSaving || readingOrderSaving}
                onClick={() => {
                  void saveAndContinuePendingTransition();
                }}
                type="button"
              >
                {layoutEditSaving || readingOrderSaving
                  ? "Saving..."
                  : "Save and continue"}
              </button>
              <button
                className="secondaryButton"
                disabled={layoutEditSaving || readingOrderSaving}
                onClick={discardAndContinuePendingTransition}
                type="button"
              >
                Discard and continue
              </button>
              <button
                className="secondaryButton"
                onClick={cancelPendingTransition}
                type="button"
              >
                Cancel
              </button>
            </div>
          </section>
        ) : null}
        {layoutEditMode ? (
          <div className="buttonRow layoutEditToolRow" role="toolbar" aria-label="Layout edit tools">
            {layoutEditToolOptions.map((tool) => (
              <button
                key={tool.id}
                className="secondaryButton"
                data-selected={layoutEditTool === tool.id ? "true" : undefined}
                disabled={layoutEditSaving}
                onClick={() => setLayoutEditTool(tool.id)}
                type="button"
              >
                {tool.label}
              </button>
            ))}
            {layoutEditTool === "DRAW_REGION" ? (
              <>
                <button
                  className="secondaryButton"
                  disabled={pendingRegionPoints.length < 3 || layoutEditSaving}
                  onClick={commitPendingRegion}
                  type="button"
                >
                  Commit region
                </button>
                <button
                  className="secondaryButton"
                  disabled={pendingRegionPoints.length === 0 || layoutEditSaving}
                  onClick={() => setPendingRegionPoints([])}
                  type="button"
                >
                  Cancel draw
                </button>
              </>
            ) : null}
            {layoutEditTool === "MERGE_LINES" ? (
              <button
                className="secondaryButton"
                disabled={mergeLineSelection.length !== 2 || layoutEditSaving}
                onClick={mergeSelectedLines}
                type="button"
              >
                Merge selected lines
              </button>
            ) : null}
          </div>
        ) : null}
        <div className="buttonRow layoutWorkspaceToolbarMeta">
          {selectedRun ? (
            <StatusChip tone={resolveRunTone(selectedRun.status)}>
              Run {selectedRun.status}
            </StatusChip>
          ) : null}
          <StatusChip tone="neutral">
            {workspaceMode === "EDIT"
              ? "Edit mode"
              : workspaceMode === "READING_ORDER"
                ? "Reading-order mode"
                : "Inspect mode"}
          </StatusChip>
          <StatusChip tone="neutral">Zoom {zoomPercent}%</StatusChip>
          {hasUnsavedChanges ? (
            <StatusChip tone="warning">
              {resolveUnsavedSummary({
                layoutEditHasChanges,
                layoutOperationCount: layoutEditOperationCount,
                readingOrderHasChanges
              })}
            </StatusChip>
          ) : (
            <StatusChip tone="neutral">No unsaved changes</StatusChip>
          )}
          {hasConflict ? (
            <StatusChip tone="warning">Conflict detected</StatusChip>
          ) : null}
        </div>
        <p className="documentViewerShortcutHint">
          Shortcuts: <span className="ukde-kbd">Ctrl/Cmd+S</span> save,{" "}
          <span className="ukde-kbd">Ctrl/Cmd+Z</span> undo,{" "}
          <span className="ukde-kbd">Ctrl/Cmd+Shift+Z</span> redo.
        </p>
        {!canEditLayout ? (
          <p className="ukde-muted">
            Geometry edit mode requires a reviewer-capable project role.
          </p>
        ) : null}
        {layoutEditError ? (
          <SectionState kind="degraded" title="Edit save failed" description={layoutEditError} />
        ) : null}
        {layoutEditConflict ? (
          <div className="buttonRow layoutWorkspaceConflictActions">
            <button
              className="secondaryButton"
              onClick={refreshWorkspaceFromServer}
              type="button"
            >
              Reload latest overlay
            </button>
            <button
              className="secondaryButton"
              onClick={discardLayoutEdits}
              type="button"
            >
              Discard local edits
            </button>
          </div>
        ) : null}
        {layoutEditNotice ? (
          <SectionState kind="success" title="Edit status" description={layoutEditNotice} />
        ) : null}
      </section>

      <section
        className="sectionCard ukde-panel documentViewerWorkspace layoutWorkspace"
        data-filmstrip-collapsed={filmstripCollapsed ? "true" : undefined}
        data-image-state={pageImageState.status}
        data-workspace-mode={workspaceMode.toLowerCase()}
        data-workspace-state={shellState}
        style={workspaceStyle}
      >
        {showFilmstripAside ? (
          <aside className="documentViewerFilmstrip" aria-label="Layout page filmstrip">
            {filmstripPanel}
          </aside>
        ) : null}

        <section className="documentViewerCanvas layoutWorkspaceCanvas">
          <div className="documentViewerCanvasViewport layoutWorkspaceCanvasViewport">
            {!selectedPage ? (
              <SectionState
                kind="empty"
                title="No page selected"
                description="Select a page from the filmstrip to inspect overlay geometry."
              />
            ) : overlayNotReady ? (
              <SectionState
                kind="empty"
                title="Overlay not ready"
                description="Canonical overlay output has not been materialized for this page yet."
              />
            ) : overlayError ? (
              <SectionState
                kind="degraded"
                title="Overlay unavailable"
                description={overlayError}
              />
            ) : !canUseCanvas ? (
              <SectionState
                kind="empty"
                title="No overlay payload"
                description="Overlay payload is not available for this page."
              />
            ) : (
              <div className="layoutWorkspaceCanvasScroller" tabIndex={0}>
                <div className="layoutWorkspaceCanvasStage" style={stageStyle}>
                  {resolvedImagePath ? (
                    <img
                      alt={`Preprocessed page ${selectedPage.pageIndex + 1}`}
                      className="layoutWorkspacePageImage"
                      key={resolvedImagePath}
                      ref={pageImageRef}
                      onError={handlePageImageError}
                      onLoad={handlePageImageLoad}
                      src={resolvedImagePath}
                    />
                  ) : null}
                  {pageImageFailed ? (
                    <SectionState
                      className="layoutWorkspaceCanvasOverlayState"
                      kind="degraded"
                      title="Page image unavailable"
                      description="Overlay geometry is still available for inspection."
                    />
                  ) : null}
                  <svg
                    aria-label="Layout overlay geometry"
                    className="layoutWorkspaceOverlayLayer"
                    preserveAspectRatio="none"
                    ref={overlaySvgRef}
                    role="img"
                    style={overlayStyle}
                    viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
                  >
                    <defs>
                      <marker
                        id="layout-overlay-arrow"
                        markerHeight="8"
                        markerWidth="8"
                        orient="auto-start-reverse"
                        refX="7"
                        refY="4"
                      >
                        <path d="M 0 0 L 8 4 L 0 8 z" />
                      </marker>
                    </defs>
                    <rect
                      fill="transparent"
                      height={canvasHeight}
                      onClick={handleCanvasBackgroundClick}
                      width={canvasWidth}
                      x={0}
                      y={0}
                    />
                    {showRegions
                      ? regions.map((region) => {
                          const selected = selectedRegionId === region.id;
                          const hovered = hoveredElementId === region.id;
                          const displayPolygon =
                            vertexDragState && vertexDragState.elementId === region.id
                              ? vertexDragState.points
                              : region.polygon;
                          return (
                            <polygon
                              className="layoutOverlayRegion"
                              data-hovered={hovered ? "true" : undefined}
                              data-selected={selected ? "true" : undefined}
                              key={region.id}
                              onClick={(event) => {
                                if (layoutEditMode && layoutEditTool === "DRAW_REGION") {
                                  const nextPoint = resolvePointFromClient(
                                    event.clientX,
                                    event.clientY
                                  );
                                  if (nextPoint) {
                                    setPendingRegionPoints((current) => [
                                      ...current,
                                      nextPoint
                                    ]);
                                  }
                                  return;
                                }
                                event.stopPropagation();
                                if (
                                  layoutEditMode &&
                                  layoutEditTool === "DELETE_ELEMENT" &&
                                  selectedElementId === region.id
                                ) {
                                  deleteSelectedElement();
                                  return;
                                }
                                setSelectedElementId(region.id);
                              }}
                              onMouseEnter={() => setHoveredElementId(region.id)}
                              onMouseLeave={() => setHoveredElementId(null)}
                              points={polygonToPoints(displayPolygon)}
                            />
                          );
                        })
                      : null}
                    {showLines
                      ? lines.map((line) => {
                          const selected = selectedElementId === line.id;
                          const hovered = hoveredElementId === line.id;
                          const mergeSelected = mergeLineSelection.includes(line.id);
                          const displayPolygon =
                            vertexDragState && vertexDragState.elementId === line.id
                              ? vertexDragState.points
                              : line.polygon;
                          return (
                            <g key={line.id}>
                              <polygon
                                className="layoutOverlayLine"
                                data-hovered={hovered ? "true" : undefined}
                                data-merge-selected={mergeSelected ? "true" : undefined}
                                data-selected={selected ? "true" : undefined}
                                onClick={(event) => {
                                  if (layoutEditMode && layoutEditTool === "DRAW_REGION") {
                                    const nextPoint = resolvePointFromClient(
                                      event.clientX,
                                      event.clientY
                                    );
                                    if (nextPoint) {
                                      setPendingRegionPoints((current) => [
                                        ...current,
                                        nextPoint
                                      ]);
                                    }
                                    return;
                                  }
                                  event.stopPropagation();
                                  if (layoutEditMode && layoutEditTool === "MERGE_LINES") {
                                    setMergeLineSelection((current) => {
                                      if (current.includes(line.id)) {
                                        return current.filter((entry) => entry !== line.id);
                                      }
                                      if (current.length >= 2) {
                                        return [current[1], line.id];
                                      }
                                      return [...current, line.id];
                                    });
                                    setSelectedElementId(line.id);
                                    return;
                                  }
                                  if (
                                    layoutEditMode &&
                                    layoutEditTool === "DELETE_ELEMENT" &&
                                    selectedElementId === line.id
                                  ) {
                                    deleteSelectedElement();
                                    return;
                                  }
                                  setSelectedElementId(line.id);
                                }}
                                onMouseEnter={() => setHoveredElementId(line.id)}
                                onMouseLeave={() => setHoveredElementId(null)}
                                points={polygonToPoints(displayPolygon)}
                              />
                              {showBaselines &&
                              Array.isArray(line.baseline) &&
                              line.baseline.length >= 2 ? (
                                <polyline
                                  className="layoutOverlayBaseline"
                                  points={polygonToPoints(line.baseline)}
                                />
                              ) : null}
                            </g>
                          );
                        })
                      : null}
                    {layoutEditMode && layoutEditTool === "DRAW_REGION" && pendingRegionPoints.length > 0 ? (
                      <>
                        <polyline
                          className="layoutOverlayDraftPolyline"
                          points={polygonToPoints(pendingRegionPoints)}
                        />
                        {pendingRegionPoints.length >= 3 ? (
                          <polygon
                            className="layoutOverlayDraftPolygon"
                            points={polygonToPoints(pendingRegionPoints)}
                          />
                        ) : null}
                      </>
                    ) : null}
                    {layoutEditMode &&
                    layoutEditTool === "EDIT_VERTICES" &&
                    selectedElement &&
                    selectedElement.polygon.length > 0 ? (
                      (vertexDragState && vertexDragState.elementId === selectedElement.id
                        ? vertexDragState.points
                        : selectedElement.polygon
                      ).map((point, index) => (
                        <circle
                          className="layoutOverlayVertexHandle"
                          cx={point.x}
                          cy={point.y}
                          key={`${selectedElement.id}:vertex:${index}`}
                          onPointerCancel={endVertexDrag}
                          onPointerDown={(event) =>
                            beginVertexDrag(selectedElement.id, index, event)
                          }
                          onPointerMove={updateVertexDrag}
                          onPointerUp={endVertexDrag}
                          r={6}
                        />
                      ))
                    ) : null}
                    {showReadingOrder && workspaceOverlay
                      ? workspaceOverlay.readingOrder.map((edge) => {
                          const fromElement = elementById.get(edge.fromId);
                          const toElement = elementById.get(edge.toId);
                          if (!fromElement || !toElement) {
                            return null;
                          }
                          if (
                            (fromElement.type === "REGION" && !showRegions) ||
                            (fromElement.type === "LINE" && !showLines) ||
                            (toElement.type === "REGION" && !showRegions) ||
                            (toElement.type === "LINE" && !showLines)
                          ) {
                            return null;
                          }
                          const fromCenter = centers.get(edge.fromId);
                          const toCenter = centers.get(edge.toId);
                          if (!fromCenter || !toCenter) {
                            return null;
                          }
                          return (
                            <line
                              className="layoutOverlayReadingEdge"
                              key={`${edge.fromId}:${edge.toId}`}
                              markerEnd="url(#layout-overlay-arrow)"
                              x1={fromCenter.x}
                              x2={toCenter.x}
                              y1={fromCenter.y}
                              y2={toCenter.y}
                            />
                          );
                        })
                      : null}
                  </svg>
                </div>
              </div>
            )}
          </div>
        </section>

        {showInspectorAside ? (
          <aside className="documentViewerInspector" aria-label="Layout inspector">
            {inspectorPanel}
          </aside>
        ) : null}
      </section>

      <Drawer
        description="Filmstrip drawer path for focus workspace state."
        onClose={() => setFilmstripDrawerOpen(false)}
        open={filmstripDrawerOpen}
        side="left"
        title="Layout filmstrip"
      >
        {filmstripPanel}
      </Drawer>
      <DetailsDrawer
        description="Inspector drawer path for compact and focus workspace states."
        onClose={() => setInspectorDrawerOpen(false)}
        open={inspectorDrawerOpen}
        title="Layout inspector"
      >
        {inspectorPanel}
      </DetailsDrawer>
    </>
  );
}
