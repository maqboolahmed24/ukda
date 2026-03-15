"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  CorrectDocumentTranscriptionLineResponse,
  DocumentLayoutPageOverlay,
  DocumentTranscriptionLineVersionHistoryResponse,
  DocumentTranscriptionLineResult,
  DocumentTranscriptionPageResult,
  DocumentTranscriptionRun,
  DocumentTranscriptionTokenResult,
  RecordTranscriptVariantSuggestionDecisionResponse,
  TranscriptVariantLayer,
  TranscriptVariantSuggestion,
  TranscriptVariantSuggestionDecision,
  TranscriptionTokenSourceKind
} from "@ukde/contracts";
import { DetailsDrawer, SectionState, StatusChip } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";
import { projectDocumentPageImagePath } from "../lib/document-page-image";
import {
  projectDocumentTranscriptionWorkspacePath,
  type TranscriptionWorkspaceMode
} from "../lib/routes";

type ShellState = "Expanded" | "Balanced" | "Compact" | "Focus";
type VariantViewMode = "DIPLOMATIC" | "NORMALISED";

interface DocumentTranscriptionWorkspaceSurfaceProps {
  canAssistDecide: boolean;
  canEdit: boolean;
  documentId: string;
  initialLineId: string | null;
  initialMode: TranscriptionWorkspaceMode;
  initialOverlay: DocumentLayoutPageOverlay | null;
  initialOverlayError: string | null;
  initialTokenId: string | null;
  initialVariantLayers: TranscriptVariantLayer[];
  lines: DocumentTranscriptionLineResult[];
  pageId: string;
  pageNumber: number;
  pages: DocumentTranscriptionPageResult[];
  projectId: string;
  resolvedSourceKind: string;
  resolvedSourceRefId: string | null;
  reviewConfidenceThreshold: number;
  runId: string;
  runs: DocumentTranscriptionRun[];
  selectedRunInputLayoutRunId: string | null;
  selectedRunInputPreprocessRunId: string | null;
  tokens: DocumentTranscriptionTokenResult[];
  variantLayersUnavailableReason: string | null;
}

interface BoundingBox {
  height: number;
  width: number;
  x: number;
  y: number;
}

interface OverlayLineShape {
  bbox: BoundingBox;
  points: Array<{ x: number; y: number }>;
}

interface CharCue {
  char: string;
  confidence: number | null;
}

interface LineHistoryState {
  redo: string[];
  undo: string[];
}

const SHELL_STATES: ShellState[] = ["Expanded", "Balanced", "Compact", "Focus"];
const VIRTUAL_ROW_HEIGHT = 128;
const VIRTUAL_OVERSCAN = 5;

function isShellState(value: string | null): value is ShellState {
  return SHELL_STATES.includes(value as ShellState);
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

function resolveTone(status: string): "danger" | "neutral" | "success" | "warning" {
  if (status === "CURRENT" || status === "SUCCEEDED") {
    return "success";
  }
  if (status === "REFRESH_REQUIRED") {
    return "warning";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  return "neutral";
}

function formatConfidence(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "N/A";
  }
  return value.toFixed(3);
}

function isLowConfidenceLine(
  line: DocumentTranscriptionLineResult,
  threshold: number
): boolean {
  return typeof line.confLine === "number" && line.confLine < threshold;
}

function toSourceKind(value: string | null | undefined): TranscriptionTokenSourceKind | undefined {
  if (value === "LINE" || value === "RESCUE_CANDIDATE" || value === "PAGE_WINDOW") {
    return value;
  }
  return undefined;
}

function parseCharCuePreview(line: DocumentTranscriptionLineResult): CharCue[] {
  const preview = line.flagsJson.charBoxCuePreview;
  if (!Array.isArray(preview)) {
    return [];
  }
  const cues: CharCue[] = [];
  for (const item of preview) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const value = item as { char?: unknown; confidence?: unknown };
    if (typeof value.char !== "string" || value.char.length === 0) {
      continue;
    }
    cues.push({
      char: value.char.slice(0, 1),
      confidence:
        typeof value.confidence === "number" && Number.isFinite(value.confidence)
          ? value.confidence
          : null
    });
  }
  return cues;
}

function pointsToSvgPath(points: Array<{ x: number; y: number }>): string {
  if (points.length === 0) {
    return "";
  }
  const [first, ...rest] = points;
  const commands = [`M ${first.x} ${first.y}`];
  for (const point of rest) {
    commands.push(`L ${point.x} ${point.y}`);
  }
  commands.push("Z");
  return commands.join(" ");
}

function computeBoundingBox(points: Array<{ x: number; y: number }>): BoundingBox | null {
  if (points.length === 0) {
    return null;
  }
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  for (const point of points) {
    if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) {
      continue;
    }
    minX = Math.min(minX, point.x);
    minY = Math.min(minY, point.y);
    maxX = Math.max(maxX, point.x);
    maxY = Math.max(maxY, point.y);
  }
  if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) {
    return null;
  }
  return {
    x: minX,
    y: minY,
    width: Math.max(1, maxX - minX),
    height: Math.max(1, maxY - minY)
  };
}

function parseLineShapes(overlay: DocumentLayoutPageOverlay | null): Map<string, OverlayLineShape> {
  const map = new Map<string, OverlayLineShape>();
  if (!overlay) {
    return map;
  }
  for (const element of overlay.elements) {
    if (element.type !== "LINE") {
      continue;
    }
    const points = element.polygon
      .map((point) => ({
        x: Number(point.x),
        y: Number(point.y)
      }))
      .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
    const bbox = computeBoundingBox(points);
    if (!bbox) {
      continue;
    }
    map.set(element.id, { bbox, points });
  }
  return map;
}

function parseTokenBoundingBox(token: DocumentTranscriptionTokenResult): BoundingBox | null {
  const raw = token.bboxJson;
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const record = raw as Record<string, unknown>;
  const x = Number(record.x ?? record.left);
  const y = Number(record.y ?? record.top);
  const right = Number(record.right);
  const bottom = Number(record.bottom);
  const width = Number(
    record.w ?? record.width ?? (Number.isFinite(right) ? right - x : Number.NaN)
  );
  const height = Number(
    record.h ?? record.height ?? (Number.isFinite(bottom) ? bottom - y : Number.NaN)
  );
  if (
    !Number.isFinite(x) ||
    !Number.isFinite(y) ||
    !Number.isFinite(width) ||
    !Number.isFinite(height)
  ) {
    return null;
  }
  return {
    x,
    y,
    width: Math.max(1, width),
    height: Math.max(1, height)
  };
}

function resolveLineSourceContext(
  line: DocumentTranscriptionLineResult
): { sourceKind: TranscriptionTokenSourceKind; sourceRefId: string } {
  const sourceKind = toSourceKind(
    typeof line.flagsJson.sourceKind === "string" ? line.flagsJson.sourceKind : undefined
  );
  const sourceRefId =
    typeof line.flagsJson.sourceRefId === "string" && line.flagsJson.sourceRefId.trim().length > 0
      ? line.flagsJson.sourceRefId.trim()
      : line.lineId;
  return {
    sourceKind: sourceKind ?? "LINE",
    sourceRefId
  };
}

function rankSuggestionStatus(status: TranscriptVariantSuggestion["status"]): number {
  if (status === "ACCEPTED") {
    return 3;
  }
  if (status === "PENDING") {
    return 2;
  }
  return 1;
}

export function DocumentTranscriptionWorkspaceSurface({
  canAssistDecide,
  canEdit,
  documentId,
  initialLineId,
  initialMode,
  initialOverlay,
  initialOverlayError,
  initialTokenId,
  initialVariantLayers,
  lines,
  pageId,
  pageNumber,
  pages,
  projectId,
  resolvedSourceKind,
  resolvedSourceRefId,
  reviewConfidenceThreshold,
  runId,
  runs,
  selectedRunInputLayoutRunId,
  selectedRunInputPreprocessRunId,
  tokens,
  variantLayersUnavailableReason
}: DocumentTranscriptionWorkspaceSurfaceProps) {
  const router = useRouter();
  const rootRef = useRef<HTMLElement | null>(null);
  const lineListRef = useRef<HTMLDivElement | null>(null);
  const [shellState, setShellState] = useState<ShellState>("Expanded");
  const [filmstripDrawerOpen, setFilmstripDrawerOpen] = useState(false);
  const [editorDrawerOpen, setEditorDrawerOpen] = useState(false);
  const [mode, setMode] = useState<TranscriptionWorkspaceMode>(initialMode);
  const [lineRows, setLineRows] = useState<DocumentTranscriptionLineResult[]>(lines);
  const [tokenRows, setTokenRows] = useState<DocumentTranscriptionTokenResult[]>(tokens);
  const [overlay, setOverlay] = useState<DocumentLayoutPageOverlay | null>(initialOverlay);
  const [overlayError, setOverlayError] = useState<string | null>(initialOverlayError);
  const [variantLayers, setVariantLayers] = useState<TranscriptVariantLayer[]>(
    initialVariantLayers
  );
  const [selectedLineId, setSelectedLineId] = useState<string | null>(initialLineId);
  const [selectedTokenId, setSelectedTokenId] = useState<string | null>(initialTokenId);
  const [highlightLowConfidence, setHighlightLowConfidence] = useState(true);
  const [assistCollapsed, setAssistCollapsed] = useState(true);
  const [variantView, setVariantView] = useState<VariantViewMode>("DIPLOMATIC");
  const [draftByLineId, setDraftByLineId] = useState<Record<string, string>>({});
  const [historyByLineId, setHistoryByLineId] = useState<Record<string, LineHistoryState>>({});
  const [savingLineIds, setSavingLineIds] = useState<Record<string, boolean>>({});
  const [savedAtByLineId, setSavedAtByLineId] = useState<Record<string, string>>({});
  const [lineListScrollTop, setLineListScrollTop] = useState(0);
  const [lineListHeight, setLineListHeight] = useState(360);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<{ detail: string; lineId: string } | null>(null);
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [lineHistory, setLineHistory] =
    useState<DocumentTranscriptionLineVersionHistoryResponse | null>(null);

  const lineById = useMemo(
    () => new Map(lineRows.map((line) => [line.lineId, line])),
    [lineRows]
  );
  const overlayLineShapes = useMemo(() => parseLineShapes(overlay), [overlay]);

  useEffect(() => {
    setMode(initialMode);
  }, [initialMode]);

  useEffect(() => {
    setLineRows(lines);
  }, [lines]);

  useEffect(() => {
    setTokenRows(tokens);
  }, [tokens]);

  useEffect(() => {
    setOverlay(initialOverlay);
    setOverlayError(initialOverlayError);
  }, [initialOverlay, initialOverlayError]);

  useEffect(() => {
    setVariantLayers(initialVariantLayers);
  }, [initialVariantLayers]);

  useEffect(() => {
    setSelectedLineId(initialLineId);
  }, [initialLineId, pageId, runId]);

  useEffect(() => {
    setSelectedTokenId(initialTokenId);
  }, [initialTokenId, pageId, runId]);

  useEffect(() => {
    setDraftByLineId({});
    setHistoryByLineId({});
    setSavingLineIds({});
    setSavedAtByLineId({});
    setConflict(null);
    setNotice(null);
    setError(null);
    setHistoryDrawerOpen(false);
    setHistoryLoading(false);
    setHistoryError(null);
    setLineHistory(null);
    setLineListScrollTop(0);
    if (lineListRef.current) {
      lineListRef.current.scrollTop = 0;
    }
  }, [pageId, runId]);

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
    if (shellState !== "Focus") {
      setFilmstripDrawerOpen(false);
    }
    if (shellState === "Expanded" || shellState === "Balanced") {
      setEditorDrawerOpen(false);
    }
  }, [shellState]);

  useEffect(() => {
    const element = lineListRef.current;
    if (!element) {
      return;
    }
    const syncHeight = () => {
      setLineListHeight(Math.max(180, Math.round(element.clientHeight || 0)));
    };
    syncHeight();
    const observer = new ResizeObserver(syncHeight);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const asOnPageOrderedLines = useMemo(() => {
    return [...lineRows].sort((a, b) => {
      const shapeA = overlayLineShapes.get(a.lineId);
      const shapeB = overlayLineShapes.get(b.lineId);
      if (shapeA && shapeB) {
        if (shapeA.bbox.y !== shapeB.bbox.y) {
          return shapeA.bbox.y - shapeB.bbox.y;
        }
        if (shapeA.bbox.x !== shapeB.bbox.x) {
          return shapeA.bbox.x - shapeB.bbox.x;
        }
      } else if (shapeA && !shapeB) {
        return -1;
      } else if (!shapeA && shapeB) {
        return 1;
      }
      return a.lineId.localeCompare(b.lineId);
    });
  }, [lineRows, overlayLineShapes]);

  const readingOrderOrderedLines = useMemo(() => {
    if (!overlay || overlay.readingOrder.length === 0) {
      return asOnPageOrderedLines;
    }
    const fallbackRank = new Map<string, number>();
    for (const [index, line] of asOnPageOrderedLines.entries()) {
      fallbackRank.set(line.lineId, index);
    }
    const lineIds = new Set(asOnPageOrderedLines.map((line) => line.lineId));
    const incomingCount = new Map<string, number>();
    const edges = new Map<string, string[]>();
    for (const lineId of lineIds) {
      incomingCount.set(lineId, 0);
      edges.set(lineId, []);
    }
    for (const edge of overlay.readingOrder) {
      if (!lineIds.has(edge.fromId) || !lineIds.has(edge.toId) || edge.fromId === edge.toId) {
        continue;
      }
      edges.get(edge.fromId)?.push(edge.toId);
      incomingCount.set(edge.toId, (incomingCount.get(edge.toId) ?? 0) + 1);
    }
    const queue = Array.from(lineIds).filter((lineId) => (incomingCount.get(lineId) ?? 0) === 0);
    queue.sort((a, b) => (fallbackRank.get(a) ?? 0) - (fallbackRank.get(b) ?? 0));
    const orderedIds: string[] = [];
    while (queue.length > 0) {
      const lineId = queue.shift();
      if (!lineId) {
        break;
      }
      orderedIds.push(lineId);
      for (const nextId of edges.get(lineId) ?? []) {
        const nextIncoming = (incomingCount.get(nextId) ?? 0) - 1;
        incomingCount.set(nextId, nextIncoming);
        if (nextIncoming === 0) {
          queue.push(nextId);
          queue.sort((a, b) => (fallbackRank.get(a) ?? 0) - (fallbackRank.get(b) ?? 0));
        }
      }
    }
    if (orderedIds.length !== lineIds.size) {
      const remaining = asOnPageOrderedLines
        .map((line) => line.lineId)
        .filter((lineId) => !orderedIds.includes(lineId));
      orderedIds.push(...remaining);
    }
    const orderedLines: DocumentTranscriptionLineResult[] = [];
    for (const lineId of orderedIds) {
      const line = lineById.get(lineId);
      if (line) {
        orderedLines.push(line);
      }
    }
    return orderedLines;
  }, [asOnPageOrderedLines, lineById, overlay]);

  const orderedLines = mode === "as-on-page" ? asOnPageOrderedLines : readingOrderOrderedLines;

  const selectedLine = useMemo(() => {
    if (selectedLineId && lineById.has(selectedLineId)) {
      return lineById.get(selectedLineId) ?? null;
    }
    return orderedLines[0] ?? null;
  }, [lineById, orderedLines, selectedLineId]);

  const selectedToken =
    selectedTokenId !== null
      ? tokenRows.find((token) => token.tokenId === selectedTokenId) ?? null
      : null;

  const selectedTokens = useMemo(() => {
    if (selectedLine) {
      return tokenRows.filter((token) => token.lineId === selectedLine.lineId);
    }
    if (selectedToken) {
      return [selectedToken];
    }
    return tokenRows;
  }, [selectedLine, selectedToken, tokenRows]);

  const currentSourceContext = useMemo(() => {
    if (selectedToken) {
      return {
        sourceKind: selectedToken.sourceKind,
        sourceRefId: selectedToken.sourceRefId
      };
    }
    if (selectedLine) {
      return resolveLineSourceContext(selectedLine);
    }
    return {
      sourceKind: toSourceKind(resolvedSourceKind) ?? "LINE",
      sourceRefId: resolvedSourceRefId
    };
  }, [resolvedSourceKind, resolvedSourceRefId, selectedLine, selectedToken]);

  const pageImagePath = projectDocumentPageImagePath(
    projectId,
    documentId,
    pageId,
    "preprocessed_gray",
    {
      runId: selectedRunInputPreprocessRunId ?? undefined
    }
  );

  const lowConfidenceLineIds = useMemo(
    () =>
      orderedLines
        .filter((line) => isLowConfidenceLine(line, reviewConfidenceThreshold))
        .map((line) => line.lineId),
    [orderedLines, reviewConfidenceThreshold]
  );

  const suggestionByLineId = useMemo(() => {
    const map = new Map<string, TranscriptVariantSuggestion>();
    for (const layer of variantLayers) {
      for (const suggestion of layer.suggestions) {
        if (!suggestion.lineId) {
          continue;
        }
        const existing = map.get(suggestion.lineId);
        if (!existing) {
          map.set(suggestion.lineId, suggestion);
          continue;
        }
        const rank = rankSuggestionStatus(suggestion.status);
        const existingRank = rankSuggestionStatus(existing.status);
        if (rank > existingRank) {
          map.set(suggestion.lineId, suggestion);
          continue;
        }
        if (
          rank === existingRank &&
          (suggestion.confidence ?? -1) > (existing.confidence ?? -1)
        ) {
          map.set(suggestion.lineId, suggestion);
        }
      }
    }
    return map;
  }, [variantLayers]);

  const allSuggestions = useMemo(() => {
    const items: Array<TranscriptVariantSuggestion & { layerId: string }> = [];
    for (const layer of variantLayers) {
      for (const suggestion of layer.suggestions) {
        items.push({ ...suggestion, layerId: layer.id });
      }
    }
    return items.sort((a, b) => {
      const rankDiff = rankSuggestionStatus(b.status) - rankSuggestionStatus(a.status);
      if (rankDiff !== 0) {
        return rankDiff;
      }
      if ((b.confidence ?? -1) !== (a.confidence ?? -1)) {
        return (b.confidence ?? -1) - (a.confidence ?? -1);
      }
      return a.id.localeCompare(b.id);
    });
  }, [variantLayers]);

  const dirtyLineIds = useMemo(
    () =>
      Object.keys(draftByLineId).filter((lineId) => {
        const line = lineById.get(lineId);
        if (!line) {
          return false;
        }
        return draftByLineId[lineId] !== line.textDiplomatic;
      }),
    [draftByLineId, lineById]
  );

  const selectedLineIndex = selectedLine
    ? orderedLines.findIndex((line) => line.lineId === selectedLine.lineId)
    : -1;

  const virtualWindow = useMemo(() => {
    const start = Math.max(
      0,
      Math.floor(lineListScrollTop / VIRTUAL_ROW_HEIGHT) - VIRTUAL_OVERSCAN
    );
    const visibleCount =
      Math.ceil(lineListHeight / VIRTUAL_ROW_HEIGHT) + VIRTUAL_OVERSCAN * 2;
    const end = Math.min(orderedLines.length, start + visibleCount);
    return {
      bottomPadding: Math.max(0, (orderedLines.length - end) * VIRTUAL_ROW_HEIGHT),
      end,
      start,
      topPadding: Math.max(0, start * VIRTUAL_ROW_HEIGHT),
      visible: orderedLines.slice(start, end)
    };
  }, [lineListHeight, lineListScrollTop, orderedLines]);

  useEffect(() => {
    if (!selectedLine || !lineListRef.current) {
      return;
    }
    const index = orderedLines.findIndex((line) => line.lineId === selectedLine.lineId);
    if (index < 0) {
      return;
    }
    const element = lineListRef.current;
    const itemTop = index * VIRTUAL_ROW_HEIGHT;
    const itemBottom = itemTop + VIRTUAL_ROW_HEIGHT;
    if (itemTop < element.scrollTop) {
      element.scrollTop = itemTop;
      return;
    }
    if (itemBottom > element.scrollTop + element.clientHeight) {
      element.scrollTop = itemBottom - element.clientHeight;
    }
  }, [orderedLines, selectedLine]);

  const updateRoute = useCallback(
    (options: {
      lineId?: string | null;
      mode?: TranscriptionWorkspaceMode;
      page?: number;
      runId?: string;
      sourceKind?: TranscriptionTokenSourceKind;
      sourceRefId?: string | null;
      tokenId?: string | null;
    }) => {
      const nextLineId =
        options.lineId === null
          ? undefined
          : (options.lineId ?? selectedLine?.lineId ?? undefined);
      const nextTokenId =
        options.tokenId === null
          ? undefined
          : (options.tokenId ?? selectedToken?.tokenId ?? undefined);
      const path = projectDocumentTranscriptionWorkspacePath(projectId, documentId, {
        lineId: nextLineId,
        mode: options.mode ?? mode,
        page: options.page ?? pageNumber,
        runId: options.runId ?? runId,
        sourceKind: options.sourceKind ?? currentSourceContext.sourceKind,
        sourceRefId:
          options.sourceRefId !== undefined
            ? options.sourceRefId
            : currentSourceContext.sourceRefId,
        tokenId: nextTokenId
      });
      router.push(path, { scroll: false });
    },
    [
      currentSourceContext.sourceKind,
      currentSourceContext.sourceRefId,
      documentId,
      mode,
      pageNumber,
      projectId,
      router,
      runId,
      selectedLine?.lineId,
      selectedToken?.tokenId
    ]
  );

  const openLine = useCallback(
    (lineId: string) => {
      const line = lineById.get(lineId);
      const source = line ? resolveLineSourceContext(line) : { sourceKind: "LINE" as const, sourceRefId: lineId };
      setSelectedLineId(lineId);
      setSelectedTokenId(null);
      updateRoute({
        lineId,
        sourceKind: source.sourceKind,
        sourceRefId: source.sourceRefId,
        tokenId: null
      });
    },
    [lineById, updateRoute]
  );

  const openToken = useCallback(
    (token: DocumentTranscriptionTokenResult) => {
      setSelectedTokenId(token.tokenId);
      setSelectedLineId(token.lineId ?? null);
      updateRoute({
        lineId: token.lineId ?? null,
        sourceKind: token.sourceKind,
        sourceRefId: token.sourceRefId,
        tokenId: token.tokenId
      });
    },
    [updateRoute]
  );

  const moveLine = useCallback(
    (offset: -1 | 1) => {
      if (orderedLines.length === 0) {
        return;
      }
      const baseIndex = selectedLineIndex >= 0 ? selectedLineIndex : 0;
      const nextIndex = Math.max(0, Math.min(orderedLines.length - 1, baseIndex + offset));
      openLine(orderedLines[nextIndex].lineId);
    },
    [openLine, orderedLines, selectedLineIndex]
  );

  const moveToNextLowConfidenceLine = useCallback(() => {
    if (lowConfidenceLineIds.length === 0) {
      return;
    }
    const currentIndex =
      selectedLine !== null ? lowConfidenceLineIds.indexOf(selectedLine.lineId) : -1;
    const nextIndex =
      currentIndex < 0 || currentIndex >= lowConfidenceLineIds.length - 1
        ? 0
        : currentIndex + 1;
    openLine(lowConfidenceLineIds[nextIndex]);
  }, [lowConfidenceLineIds, openLine, selectedLine]);

  const setLineDraft = useCallback(
    (lineId: string, nextText: string, recordHistory: boolean) => {
      const line = lineById.get(lineId);
      if (!line) {
        return;
      }
      const current = draftByLineId[lineId] ?? line.textDiplomatic;
      if (current === nextText) {
        return;
      }
      if (recordHistory) {
        setHistoryByLineId((state) => {
          const history = state[lineId] ?? { undo: [], redo: [] };
          return {
            ...state,
            [lineId]: {
              undo: [...history.undo, current].slice(-40),
              redo: []
            }
          };
        });
      }
      setDraftByLineId((state) => {
        const next = { ...state };
        if (nextText === line.textDiplomatic) {
          delete next[lineId];
        } else {
          next[lineId] = nextText;
        }
        return next;
      });
      if (conflict?.lineId === lineId) {
        setConflict(null);
      }
      setError(null);
    },
    [conflict, draftByLineId, lineById]
  );

  const undoDraft = useCallback(() => {
    if (!selectedLine) {
      return;
    }
    const lineId = selectedLine.lineId;
    const history = historyByLineId[lineId];
    if (!history || history.undo.length === 0) {
      return;
    }
    const currentText = draftByLineId[lineId] ?? selectedLine.textDiplomatic;
    const previousText = history.undo[history.undo.length - 1];
    setHistoryByLineId((state) => ({
      ...state,
      [lineId]: {
        undo: history.undo.slice(0, -1),
        redo: [...history.redo, currentText].slice(-40)
      }
    }));
    setLineDraft(lineId, previousText, false);
  }, [draftByLineId, historyByLineId, selectedLine, setLineDraft]);

  const redoDraft = useCallback(() => {
    if (!selectedLine) {
      return;
    }
    const lineId = selectedLine.lineId;
    const history = historyByLineId[lineId];
    if (!history || history.redo.length === 0) {
      return;
    }
    const currentText = draftByLineId[lineId] ?? selectedLine.textDiplomatic;
    const nextText = history.redo[history.redo.length - 1];
    setHistoryByLineId((state) => ({
      ...state,
      [lineId]: {
        undo: [...history.undo, currentText].slice(-40),
        redo: history.redo.slice(0, -1)
      }
    }));
    setLineDraft(lineId, nextText, false);
  }, [draftByLineId, historyByLineId, selectedLine, setLineDraft]);

  const reloadLinesAndTokens = useCallback(async () => {
    const lineQuery = new URLSearchParams();
    lineQuery.set("workspaceView", "true");
    if (selectedLine?.lineId) {
      lineQuery.set("lineId", selectedLine.lineId);
    }
    if (selectedTokenId) {
      lineQuery.set("tokenId", selectedTokenId);
    }
    if (currentSourceContext.sourceKind) {
      lineQuery.set("sourceKind", currentSourceContext.sourceKind);
    }
    if (currentSourceContext.sourceRefId) {
      lineQuery.set("sourceRefId", currentSourceContext.sourceRefId);
    }
    const lineResult = await requestBrowserApi<{
      items: DocumentTranscriptionLineResult[];
    }>({
      cacheClass: "operations-live",
      method: "GET",
      path: `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/lines?${lineQuery.toString()}`
    });
    if (lineResult.ok && lineResult.data) {
      setLineRows(lineResult.data.items);
    }
    const tokenResult = await requestBrowserApi<{
      items: DocumentTranscriptionTokenResult[];
    }>({
      cacheClass: "operations-live",
      method: "GET",
      path: `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/tokens`
    });
    if (tokenResult.ok && tokenResult.data) {
      setTokenRows(tokenResult.data.items);
    }
  }, [
    currentSourceContext.sourceKind,
    currentSourceContext.sourceRefId,
    documentId,
    pageId,
    projectId,
    runId,
    selectedLine,
    selectedTokenId
  ]);

  const openLineHistory = useCallback(
    async (lineId: string) => {
      setHistoryDrawerOpen(true);
      setHistoryLoading(true);
      setHistoryError(null);
      const response =
        await requestBrowserApi<DocumentTranscriptionLineVersionHistoryResponse>({
          cacheClass: "operations-live",
          method: "GET",
          path: `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/lines/${lineId}/versions`
        });
      if (!response.ok || !response.data) {
        setLineHistory(null);
        setHistoryError(response.detail ?? "Line version history unavailable.");
        setHistoryLoading(false);
        return;
      }
      setLineHistory(response.data);
      setHistoryLoading(false);
    },
    [documentId, pageId, projectId, runId]
  );

  const saveLine = useCallback(
    async (lineId: string, moveAfterSave: boolean) => {
      if (!canEdit || variantView !== "DIPLOMATIC") {
        return;
      }
      const line = lineById.get(lineId);
      if (!line) {
        return;
      }
      const draft = draftByLineId[lineId] ?? line.textDiplomatic;
      if (draft === line.textDiplomatic) {
        if (moveAfterSave) {
          moveLine(1);
        }
        return;
      }
      if (!draft.trim()) {
        setError("Line text cannot be empty.");
        return;
      }

      setSavingLineIds((state) => ({ ...state, [lineId]: true }));
      setError(null);
      setNotice(null);
      try {
        const response = await requestBrowserApi<CorrectDocumentTranscriptionLineResponse>({
          body: JSON.stringify({
            textDiplomatic: draft,
            versionEtag: line.versionEtag
          }),
          cacheClass: "operations-live",
          headers: {
            "Content-Type": "application/json"
          },
          method: "PATCH",
          path: `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/lines/${lineId}`
        });
        if (!response.ok || !response.data) {
          if (response.status === 409) {
            setConflict({
              detail:
                response.detail ??
                "Another reviewer saved a newer edit. Reload the latest line state before retrying.",
              lineId
            });
            await reloadLinesAndTokens();
            return;
          }
          setError(response.detail ?? "Line save failed.");
          return;
        }
        setLineRows((state) =>
          state.map((item) => (item.lineId === lineId ? response.data!.line : item))
        );
        setDraftByLineId((state) => {
          const next = { ...state };
          delete next[lineId];
          return next;
        });
        setHistoryByLineId((state) => {
          const next = { ...state };
          delete next[lineId];
          return next;
        });
        setSavedAtByLineId((state) => ({
          ...state,
          [lineId]: new Date().toISOString()
        }));
        setConflict((state) => (state?.lineId === lineId ? null : state));
        if (response.data.downstreamRedactionInvalidated) {
          setNotice(
            "Saved. Downstream redaction basis is now STALE until privacy review reruns."
          );
        } else {
          setNotice("Saved.");
        }
        if (moveAfterSave) {
          moveLine(1);
        }
      } finally {
        setSavingLineIds((state) => {
          const next = { ...state };
          delete next[lineId];
          return next;
        });
      }
    },
    [
      canEdit,
      documentId,
      draftByLineId,
      lineById,
      moveLine,
      pageId,
      projectId,
      reloadLinesAndTokens,
      runId,
      variantView
    ]
  );

  const saveAllDirtyLines = useCallback(async () => {
    for (const lineId of dirtyLineIds) {
      await saveLine(lineId, false);
    }
  }, [dirtyLineIds, saveLine]);

  const discardLineDraft = useCallback(
    (lineId: string) => {
      setDraftByLineId((state) => {
        const next = { ...state };
        delete next[lineId];
        return next;
      });
      setHistoryByLineId((state) => {
        const next = { ...state };
        delete next[lineId];
        return next;
      });
      setConflict((state) => (state?.lineId === lineId ? null : state));
      setNotice("Local draft discarded.");
    },
    []
  );

  const recordSuggestionDecision = useCallback(
    async (suggestionId: string, decision: TranscriptVariantSuggestionDecision) => {
      if (!canAssistDecide) {
        return;
      }
      const response =
        await requestBrowserApi<RecordTranscriptVariantSuggestionDecisionResponse>({
          body: JSON.stringify({ decision }),
          cacheClass: "operations-live",
          headers: {
            "Content-Type": "application/json"
          },
          method: "POST",
          path: `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/pages/${pageId}/variant-layers/NORMALISED/suggestions/${suggestionId}/decision`
        });
      if (!response.ok || !response.data) {
        setError(response.detail ?? "Assist decision could not be recorded.");
        return;
      }
      setVariantLayers((state) =>
        state.map((layer) => ({
          ...layer,
          suggestions: layer.suggestions.map((suggestion) =>
            suggestion.id === response.data!.suggestion.id
              ? response.data!.suggestion
              : suggestion
          )
        }))
      );
      setNotice("Assist decision recorded.");
    },
    [canAssistDecide, documentId, pageId, projectId, runId]
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.target instanceof Node) || !rootRef.current?.contains(event.target)) {
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (selectedLine) {
          void saveLine(selectedLine.lineId, false);
        }
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) {
          redoDraft();
        } else {
          undoDraft();
        }
        return;
      }
      if (!event.metaKey && !event.ctrlKey && !event.altKey && !isTextEntryTarget(event.target)) {
        if (event.key === "ArrowUp") {
          event.preventDefault();
          moveLine(-1);
          return;
        }
        if (event.key === "ArrowDown") {
          event.preventDefault();
          moveLine(1);
          return;
        }
      }
      if (event.altKey && event.key.toLowerCase() === "n") {
        event.preventDefault();
        moveToNextLowConfidenceLine();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [moveLine, moveToNextLowConfidenceLine, redoDraft, saveLine, selectedLine, undoDraft]);

  const selectedLineShape = selectedLine
    ? overlayLineShapes.get(selectedLine.lineId) ?? null
    : null;
  const selectedTokenBox = selectedToken ? parseTokenBoundingBox(selectedToken) : null;
  const showEditorAside = shellState === "Expanded" || shellState === "Balanced";
  const showFilmstripAside = shellState !== "Focus";

  const saveStatus = useMemo(() => {
    const savingCount = Object.keys(savingLineIds).length;
    if (savingCount > 0) {
      return {
        label: `Saving ${savingCount} line${savingCount === 1 ? "" : "s"}`,
        tone: "warning" as const
      };
    }
    if (conflict) {
      return { label: "Conflict detected", tone: "danger" as const };
    }
    if (dirtyLineIds.length > 0) {
      return {
        label: `${dirtyLineIds.length} unsaved edit${dirtyLineIds.length === 1 ? "" : "s"}`,
        tone: "warning" as const
      };
    }
    return { label: "All edits saved", tone: "success" as const };
  }, [conflict, dirtyLineIds.length, savingLineIds]);

  const modeLabel = mode === "as-on-page" ? "As on page" : "Reading order";

  return (
    <section className="transcriptionWorkspaceRoot" ref={rootRef}>
      <div className="transcriptionWorkspaceToolbar">
        <div className="buttonRow transcriptionWorkspaceToolbarMain">
          <StatusChip tone={saveStatus.tone}>{saveStatus.label}</StatusChip>
          <StatusChip tone="neutral">
            {modeLabel} · {orderedLines.length} line(s)
          </StatusChip>
          <StatusChip tone="neutral">
            {lowConfidenceLineIds.length} low-confidence line(s)
          </StatusChip>
          <button
            className="secondaryButton"
            type="button"
            onClick={() => {
              const nextMode: TranscriptionWorkspaceMode =
                mode === "reading-order" ? "as-on-page" : "reading-order";
              setMode(nextMode);
              updateRoute({
                lineId: selectedLine?.lineId ?? null,
                mode: nextMode,
                sourceKind:
                  selectedLine !== null
                    ? resolveLineSourceContext(selectedLine).sourceKind
                    : toSourceKind(resolvedSourceKind),
                sourceRefId:
                  selectedLine !== null
                    ? resolveLineSourceContext(selectedLine).sourceRefId
                    : resolvedSourceRefId,
                tokenId: selectedToken?.tokenId ?? null
              });
            }}
          >
            Switch mode ({mode === "reading-order" ? "As on page" : "Reading order"})
          </button>
          <button
            className="secondaryButton"
            type="button"
            onClick={() => moveLine(-1)}
            disabled={selectedLineIndex <= 0}
          >
            Previous line
          </button>
          <button
            className="secondaryButton"
            type="button"
            onClick={() => moveLine(1)}
            disabled={
              selectedLineIndex < 0 || selectedLineIndex >= orderedLines.length - 1
            }
          >
            Next line
          </button>
          <button
            className="secondaryButton"
            type="button"
            onClick={moveToNextLowConfidenceLine}
            disabled={lowConfidenceLineIds.length === 0}
          >
            Next issue (Alt+N)
          </button>
          <button
            className="secondaryButton"
            type="button"
            onClick={() => {
              if (selectedLine) {
                void saveLine(selectedLine.lineId, false);
              }
            }}
            disabled={!canEdit || !selectedLine || variantView !== "DIPLOMATIC"}
          >
            Save line (Ctrl/Cmd+S)
          </button>
          <button
            className="secondaryButton"
            type="button"
            onClick={() => {
              void saveAllDirtyLines();
            }}
            disabled={!canEdit || dirtyLineIds.length === 0 || variantView !== "DIPLOMATIC"}
          >
            Save all
          </button>
          <button
            className="secondaryButton"
            type="button"
            onClick={undoDraft}
            disabled={!selectedLine || !(historyByLineId[selectedLine.lineId]?.undo.length > 0)}
          >
            Undo
          </button>
          <button
            className="secondaryButton"
            type="button"
            onClick={redoDraft}
            disabled={!selectedLine || !(historyByLineId[selectedLine.lineId]?.redo.length > 0)}
          >
            Redo
          </button>
          <button
            className="secondaryButton"
            type="button"
            onClick={() => {
              if (selectedLine) {
                void openLineHistory(selectedLine.lineId);
              }
            }}
            disabled={!selectedLine}
          >
            Line history
          </button>
          <button
            className="secondaryButton"
            type="button"
            onClick={() => setHighlightLowConfidence((value) => !value)}
          >
            {highlightLowConfidence ? "Hide low-confidence highlight" : "Highlight low-confidence"}
          </button>
          {!showFilmstripAside ? (
            <button
              className="secondaryButton"
              type="button"
              onClick={() => setFilmstripDrawerOpen(true)}
            >
              Open filmstrip
            </button>
          ) : null}
          {!showEditorAside ? (
            <button
              className="secondaryButton"
              type="button"
              onClick={() => setEditorDrawerOpen(true)}
            >
              Open transcript panel
            </button>
          ) : null}
        </div>
        <div className="buttonRow transcriptionWorkspaceToolbarSub">
          <label className="documentViewerRunSelector">
            Run
            <select
              value={runId}
              onChange={(event) => {
                const nextRunId = event.target.value;
                updateRoute({
                  lineId: null,
                  runId: nextRunId,
                  sourceKind: "LINE",
                  sourceRefId: null,
                  tokenId: null
                });
              }}
            >
              {runs.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.id} · {run.status}
                  {run.isActiveProjection ? " · active" : ""}
                </option>
              ))}
            </select>
          </label>
          <p className="documentViewerShortcutHint">
            Shortcuts: <span className="ukde-kbd">Ctrl/Cmd+S</span> save,{" "}
            <span className="ukde-kbd">Enter</span> save-and-next,{" "}
            <span className="ukde-kbd">Up/Down</span> line navigation,{" "}
            <span className="ukde-kbd">Ctrl/Cmd+Z</span> undo.
          </p>
        </div>
      </div>

      {notice ? (
        <SectionState
          className="sectionCard ukde-panel"
          kind="success"
          title="Workspace update"
          description={notice}
        />
      ) : null}
      {error ? (
        <SectionState
          className="sectionCard ukde-panel"
          kind="degraded"
          title="Workspace action failed"
          description={error}
        />
      ) : null}
      {conflict ? (
        <SectionState
          className="sectionCard ukde-panel"
          kind="degraded"
          title="Edit conflict detected"
          description={conflict.detail}
          actions={
            <button
              className="secondaryButton"
              type="button"
              onClick={() => {
                void reloadLinesAndTokens();
              }}
            >
              Reload latest line state
            </button>
          }
        />
      ) : null}

      <div
        className="documentViewerWorkspace transcriptionWorkspace"
        data-workspace-state={shellState}
      >
        {showFilmstripAside ? (
          <aside className="documentViewerFilmstrip transcriptionFilmstrip" aria-label="Page filmstrip">
            <h2>Page filmstrip</h2>
            <ul>
              {pages.map((page) => {
                const itemPageNumber = page.pageIndex + 1;
                const selected = itemPageNumber === pageNumber;
                const thumbPath = projectDocumentPageImagePath(
                  projectId,
                  documentId,
                  page.pageId,
                  "thumb"
                );
                return (
                  <li key={page.pageId}>
                    <button
                      className="documentViewerFilmstripLink layoutFilmstripButton"
                      aria-current={selected ? "page" : undefined}
                      type="button"
                      onClick={() => {
                        setSelectedTokenId(null);
                        setSelectedLineId(null);
                        updateRoute({
                          lineId: null,
                          page: itemPageNumber,
                          sourceKind: "LINE",
                          sourceRefId: null,
                          tokenId: null
                        });
                      }}
                    >
                      <img
                        alt={`Page ${itemPageNumber} thumbnail`}
                        className="documentViewerFilmstripThumb"
                        src={thumbPath}
                        width={60}
                        height={84}
                      />
                      <span>
                        <span>Page {itemPageNumber}</span>
                        <span className="ukde-muted"> · {page.status}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </aside>
        ) : null}

        <section className="documentViewerCanvas transcriptionCanvas" aria-label="Source canvas">
          <div className="documentViewerCanvasViewport transcriptionCanvasViewport">
            {overlayError ? (
              <SectionState
                kind="degraded"
                title="Overlay unavailable"
                description={overlayError}
              />
            ) : null}
            <div className="transcriptionCanvasStage">
              <img
                alt={`Page ${pageNumber} source`}
                className="transcriptionCanvasImage"
                src={pageImagePath}
              />
              {overlay ? (
                <svg
                  className="transcriptionOverlay"
                  viewBox={`0 0 ${overlay.page.width} ${overlay.page.height}`}
                  aria-label="Transcription overlay"
                >
                  {Array.from(overlayLineShapes.entries()).map(([lineId, shape]) => {
                    const line = lineById.get(lineId);
                    const lowConfidence =
                      line !== undefined &&
                      isLowConfidenceLine(line, reviewConfidenceThreshold);
                    const selected = selectedLine?.lineId === lineId;
                    return (
                      <path
                        key={lineId}
                        className="transcriptionOverlayLine"
                        data-low={
                          highlightLowConfidence && lowConfidence ? "true" : undefined
                        }
                        data-selected={selected ? "true" : undefined}
                        d={pointsToSvgPath(shape.points)}
                        onClick={() => openLine(lineId)}
                      />
                    );
                  })}
                  {selectedTokenBox ? (
                    <rect
                      className="transcriptionOverlayToken"
                      x={selectedTokenBox.x}
                      y={selectedTokenBox.y}
                      width={selectedTokenBox.width}
                      height={selectedTokenBox.height}
                    />
                  ) : null}
                </svg>
              ) : null}
            </div>
          </div>
        </section>

        {showEditorAside ? (
          <aside className="documentViewerInspector transcriptionEditor" aria-label="Transcript editor">
            <h2>Transcript panel</h2>
            <div className="buttonRow transcriptionVariantToggle">
              <button
                className="secondaryButton"
                type="button"
                aria-pressed={variantView === "DIPLOMATIC"}
                onClick={() => setVariantView("DIPLOMATIC")}
              >
                Diplomatic
              </button>
              <button
                className="secondaryButton"
                type="button"
                aria-pressed={variantView === "NORMALISED"}
                onClick={() => setVariantView("NORMALISED")}
                disabled={allSuggestions.length === 0}
              >
                Normalised
              </button>
            </div>
            {variantView === "NORMALISED" ? (
              <p className="ukde-muted transcriptionModeHint">
                Normalised view is read-only and stays separate from diplomatic edits.
              </p>
            ) : null}
            <div
              className="transcriptionLineList"
              ref={lineListRef}
              onScroll={(event) => {
                setLineListScrollTop((event.target as HTMLDivElement).scrollTop);
              }}
            >
              <div style={{ height: `${virtualWindow.topPadding}px` }} />
              {virtualWindow.visible.map((line) => {
                const lineText = draftByLineId[line.lineId] ?? line.textDiplomatic;
                const lowConfidence = isLowConfidenceLine(line, reviewConfidenceThreshold);
                const dirty = draftByLineId[line.lineId] !== undefined;
                const selected = selectedLine?.lineId === line.lineId;
                const suggestion = suggestionByLineId.get(line.lineId);
                const normalisedText = suggestion?.suggestionText ?? line.textDiplomatic;
                return (
                  <article
                    className="transcriptionLineRow"
                    data-dirty={dirty ? "true" : undefined}
                    data-low={highlightLowConfidence && lowConfidence ? "true" : undefined}
                    data-selected={selected ? "true" : undefined}
                    key={line.lineId}
                    style={{ minHeight: `${VIRTUAL_ROW_HEIGHT - 4}px` }}
                  >
                    <div className="transcriptionLineRowHeader">
                      <button
                        className="secondaryButton"
                        type="button"
                        onClick={() => openLine(line.lineId)}
                      >
                        {line.lineId}
                      </button>
                      <div className="buttonRow">
                        <StatusChip tone={resolveTone(line.tokenAnchorStatus)}>
                          {line.tokenAnchorStatus}
                        </StatusChip>
                        <StatusChip tone={lowConfidence ? "warning" : "success"}>
                          {line.confidenceBand}
                        </StatusChip>
                        <StatusChip tone="neutral">{formatConfidence(line.confLine)}</StatusChip>
                        {dirty ? (
                          <StatusChip tone="warning">Edited</StatusChip>
                        ) : savedAtByLineId[line.lineId] ? (
                          <StatusChip tone="success">Saved</StatusChip>
                        ) : null}
                      </div>
                    </div>
                    {variantView === "NORMALISED" ? (
                      <p className="transcriptionLineReadOnly">{normalisedText}</p>
                    ) : (
                      <textarea
                        className="transcriptionLineDraft"
                        value={lineText}
                        onFocus={() => {
                          if (selectedLine?.lineId !== line.lineId) {
                            openLine(line.lineId);
                          }
                        }}
                        onChange={(event) =>
                          setLineDraft(line.lineId, event.target.value, true)
                        }
                        onKeyDown={(event) => {
                          if (
                            event.key === "Enter" &&
                            !event.shiftKey &&
                            !event.ctrlKey &&
                            !event.metaKey &&
                            !event.altKey
                          ) {
                            event.preventDefault();
                            void saveLine(line.lineId, true);
                          }
                        }}
                        rows={2}
                      />
                    )}
                    <div className="buttonRow transcriptionLineRowActions">
                      <button
                        className="secondaryButton"
                        type="button"
                        onClick={() => void saveLine(line.lineId, false)}
                        disabled={
                          !canEdit ||
                          variantView !== "DIPLOMATIC" ||
                          !dirty ||
                          Boolean(savingLineIds[line.lineId])
                        }
                      >
                        {savingLineIds[line.lineId] ? "Saving..." : "Save"}
                      </button>
                      <button
                        className="secondaryButton"
                        type="button"
                        onClick={() => discardLineDraft(line.lineId)}
                        disabled={!dirty}
                      >
                        Discard
                      </button>
                      <button
                        className="secondaryButton"
                        type="button"
                        onClick={() => {
                          void openLineHistory(line.lineId);
                        }}
                      >
                        History
                      </button>
                    </div>
                  </article>
                );
              })}
              <div style={{ height: `${virtualWindow.bottomPadding}px` }} />
            </div>
            <div className="buttonRow transcriptionEditorFooter">
              <button
                className="secondaryButton"
                type="button"
                onClick={() => {
                  setDraftByLineId({});
                  setHistoryByLineId({});
                  setNotice("All local drafts discarded.");
                }}
                disabled={dirtyLineIds.length === 0}
              >
                Discard all drafts
              </button>
            </div>
          </aside>
        ) : null}
      </div>

      <section className="sectionCard ukde-panel transcriptionInspectorGrid">
        <div>
          <h3>Selected line confidence</h3>
          {selectedLine ? (
            <>
              <ul className="projectMetaList">
                <li>
                  <span>Line ID</span>
                  <strong>{selectedLine.lineId}</strong>
                </li>
                <li>
                  <span>Confidence</span>
                  <strong>{formatConfidence(selectedLine.confLine)}</strong>
                </li>
                <li>
                  <span>Band</span>
                  <strong>{selectedLine.confidenceBand}</strong>
                </li>
                <li>
                  <span>Basis</span>
                  <strong>{selectedLine.confidenceBasis}</strong>
                </li>
                <li>
                  <span>Char-box payload</span>
                  <strong>{selectedLine.charBoxesKey ?? "Unavailable for this line"}</strong>
                </li>
              </ul>
              <h4>Per-character confidence cues</h4>
              {(() => {
                const cues = parseCharCuePreview(selectedLine);
                if (cues.length === 0) {
                  return (
                    <p className="ukde-muted">
                      {selectedLine.charBoxesKey
                        ? "Character confidence payload exists, but preview cues are unavailable in this response."
                        : "Character confidence cues unavailable for this line."}
                    </p>
                  );
                }
                return (
                  <p aria-label="Character confidence cues">
                    {cues.map((cue, index) => (
                      <span
                        key={`${cue.char}-${index}`}
                        style={{
                          display: "inline-block",
                          marginRight: "0.12rem",
                          padding: "0.05rem 0.12rem",
                          borderRadius: "0.2rem",
                          backgroundColor:
                            cue.confidence === null
                              ? "rgba(126, 126, 126, 0.2)"
                              : cue.confidence < reviewConfidenceThreshold
                                ? "rgba(220, 142, 52, 0.25)"
                                : "rgba(76, 166, 87, 0.25)"
                        }}
                      >
                        {cue.char}
                      </span>
                    ))}
                  </p>
                );
              })()}
            </>
          ) : (
            <p className="ukde-muted">
              No line is selected. Source-only token context is active.
            </p>
          )}
        </div>

        <div>
          <h3>Line crop preview</h3>
          {selectedLine && selectedLineShape && overlay ? (
            <div className="transcriptionLineCropPreview">
              <svg
                className="transcriptionLineCropSvg"
                viewBox={`${Math.max(0, selectedLineShape.bbox.x - 20)} ${Math.max(
                  0,
                  selectedLineShape.bbox.y - 16
                )} ${selectedLineShape.bbox.width + 40} ${selectedLineShape.bbox.height + 32}`}
              >
                <image
                  href={pageImagePath}
                  x={0}
                  y={0}
                  width={overlay.page.width}
                  height={overlay.page.height}
                  preserveAspectRatio="none"
                />
                <path
                  className="transcriptionLineCropOutline"
                  d={pointsToSvgPath(selectedLineShape.points)}
                />
              </svg>
            </div>
          ) : (
            <p className="ukde-muted">
              Line geometry unavailable for this page/run context.
            </p>
          )}
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Token anchors</h3>
        {selectedTokens.length === 0 ? (
          <p className="ukde-muted">No tokens available for the current selection.</p>
        ) : (
          <ul className="timelineList">
            {selectedTokens.map((token) => (
              <li key={token.tokenId}>
                <div className="auditIntegrityRow">
                  <button
                    className="secondaryButton"
                    type="button"
                    onClick={() => openToken(token)}
                  >
                    {token.tokenText}
                  </button>
                  <div className="buttonRow">
                    <StatusChip tone="neutral">{token.sourceKind}</StatusChip>
                    <StatusChip tone="neutral">{formatConfidence(token.tokenConfidence)}</StatusChip>
                  </div>
                </div>
                <p className="ukde-muted">
                  tokenId {token.tokenId} · sourceRef {token.sourceRefId}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="sectionCard ukde-panel transcriptionAssistSection">
        <div className="auditIntegrityRow">
          <h3>Assist panel</h3>
          <button
            className="secondaryButton"
            type="button"
            onClick={() => setAssistCollapsed((value) => !value)}
          >
            {assistCollapsed ? "Expand assist" : "Collapse assist"}
          </button>
        </div>
        {assistCollapsed ? null : variantLayersUnavailableReason ? (
          <SectionState
            kind="degraded"
            title="Assist unavailable"
            description={variantLayersUnavailableReason}
          />
        ) : allSuggestions.length === 0 ? (
          <SectionState
            kind="empty"
            title="No assist suggestions"
            description="Normalised variant suggestions are not available for this page."
          />
        ) : (
          <ul className="timelineList">
            {allSuggestions.map((suggestion) => (
              <li key={suggestion.id}>
                <div className="auditIntegrityRow">
                  <strong>{suggestion.lineId ?? "Page-level suggestion"}</strong>
                  <div className="buttonRow">
                    <StatusChip tone="neutral">{suggestion.status}</StatusChip>
                    <StatusChip tone="neutral">
                      {formatConfidence(suggestion.confidence)}
                    </StatusChip>
                  </div>
                </div>
                <p>{suggestion.suggestionText}</p>
                <p className="ukde-muted">
                  {typeof suggestion.metadataJson.reason === "string" &&
                  suggestion.metadataJson.reason.trim().length > 0
                    ? suggestion.metadataJson.reason
                    : "No explicit reason provided."}
                </p>
                <div className="buttonRow">
                  <button
                    className="secondaryButton"
                    type="button"
                    disabled={!canAssistDecide || suggestion.status !== "PENDING"}
                    onClick={() => {
                      void recordSuggestionDecision(suggestion.id, "ACCEPT");
                    }}
                  >
                    Accept
                  </button>
                  <button
                    className="secondaryButton"
                    type="button"
                    disabled={!canAssistDecide || suggestion.status !== "PENDING"}
                    onClick={() => {
                      void recordSuggestionDecision(suggestion.id, "REJECT");
                    }}
                  >
                    Reject
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <DetailsDrawer
        description="Filmstrip drawer"
        open={filmstripDrawerOpen}
        onClose={() => setFilmstripDrawerOpen(false)}
        title="Page filmstrip"
      >
        <div className="transcriptionDrawerList">
          {pages.map((page) => {
            const itemPageNumber = page.pageIndex + 1;
            return (
              <button
                key={page.pageId}
                className="secondaryButton"
                type="button"
                onClick={() => {
                  setFilmstripDrawerOpen(false);
                  updateRoute({
                    lineId: null,
                    page: itemPageNumber,
                    sourceKind: "LINE",
                    sourceRefId: null,
                    tokenId: null
                  });
                }}
              >
                Page {itemPageNumber} · {page.status}
              </button>
            );
          })}
        </div>
      </DetailsDrawer>

      <DetailsDrawer
        description="Transcript editor drawer"
        open={editorDrawerOpen}
        onClose={() => setEditorDrawerOpen(false)}
        title="Transcript panel"
      >
        {selectedLine ? (
          <div className="transcriptionDrawerEditor">
            <p className="ukde-muted">
              {selectedLine.lineId} · {formatConfidence(selectedLine.confLine)} ·{" "}
              {selectedLine.confidenceBand}
            </p>
            {variantView === "NORMALISED" ? (
              <p className="transcriptionLineReadOnly">
                {suggestionByLineId.get(selectedLine.lineId)?.suggestionText ??
                  selectedLine.textDiplomatic}
              </p>
            ) : (
              <textarea
                className="transcriptionLineDraft"
                value={draftByLineId[selectedLine.lineId] ?? selectedLine.textDiplomatic}
                rows={4}
                onChange={(event) =>
                  setLineDraft(selectedLine.lineId, event.target.value, true)
                }
              />
            )}
            <div className="buttonRow">
              <button
                className="secondaryButton"
                type="button"
                onClick={() => void saveLine(selectedLine.lineId, false)}
                disabled={!canEdit || variantView !== "DIPLOMATIC"}
              >
                Save
              </button>
              <button
                className="secondaryButton"
                type="button"
                onClick={() => setEditorDrawerOpen(false)}
              >
                Close
              </button>
            </div>
          </div>
        ) : (
          <SectionState
            kind="empty"
            title="No selected line"
            description="Select a line from the list or overlay."
          />
        )}
      </DetailsDrawer>

      <DetailsDrawer
        description="Line version history drawer"
        open={historyDrawerOpen}
        onClose={() => setHistoryDrawerOpen(false)}
        title="Line version history"
      >
        {historyLoading ? (
          <SectionState
            kind="loading"
            title="Loading line history"
            description="Fetching immutable transcript version lineage for this line."
          />
        ) : historyError ? (
          <SectionState
            kind="degraded"
            title="Line history unavailable"
            description={historyError}
          />
        ) : lineHistory ? (
          <div className="transcriptionDrawerEditor">
            <p className="ukde-muted">
              Run {lineHistory.runId} · Page {pageNumber} · Line {lineHistory.lineId}
            </p>
            <ul className="timelineList">
              {lineHistory.versions.map((entry) => (
                <li key={entry.version.id}>
                  <div className="auditIntegrityRow">
                    <strong>{entry.version.id}</strong>
                    <div className="buttonRow">
                      <StatusChip tone={entry.isActive ? "success" : "neutral"}>
                        {entry.isActive ? "Active" : "Superseded"}
                      </StatusChip>
                      <StatusChip tone="neutral">{entry.sourceType}</StatusChip>
                    </div>
                  </div>
                  <p className="ukde-muted">{entry.version.textDiplomatic}</p>
                  <p className="ukde-muted">
                    Edited by {entry.version.editorUserId} at{" "}
                    {new Date(entry.version.createdAt).toISOString()}
                    {entry.version.editReason ? ` · ${entry.version.editReason}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <SectionState
            kind="empty"
            title="No version history selected"
            description="Select a line and open history to inspect immutable transcript lineage."
          />
        )}
      </DetailsDrawer>
    </section>
  );
}
