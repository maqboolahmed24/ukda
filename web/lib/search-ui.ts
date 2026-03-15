import type { ProjectSearchHit } from "@ukde/contracts";

export interface SearchSnippetSegment {
  highlighted: boolean;
  text: string;
}

export interface SearchSnippetPreview {
  highlightKind: "NONE" | "QUERY" | "SPAN";
  prefixEllipsis: boolean;
  segments: SearchSnippetSegment[];
  suffixEllipsis: boolean;
}

export interface GroupedSearchHits {
  documentId: string;
  items: ProjectSearchHit[];
}

const MATCH_SPAN_START_KEYS = [
  "begin",
  "charStart",
  "from",
  "matchStart",
  "offset",
  "start",
  "startOffset"
] as const;
const MATCH_SPAN_END_KEYS = [
  "charEnd",
  "end",
  "endOffset",
  "matchEnd",
  "stop",
  "to"
] as const;
const MATCH_SPAN_LENGTH_KEYS = [
  "charLength",
  "length",
  "matchLength",
  "spanLength"
] as const;

interface HighlightRange {
  end: number;
  kind: "QUERY" | "SPAN";
  start: number;
}

function toFiniteInt(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.round(value);
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number.parseInt(value.trim(), 10);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function readFirstInt(
  record: Record<string, unknown>,
  keys: ReadonlyArray<string>
): number | null {
  for (const key of keys) {
    const parsed = toFiniteInt(record[key]);
    if (parsed !== null) {
      return parsed;
    }
  }
  return null;
}

function clampRange(
  start: number,
  end: number,
  textLength: number
): { end: number; start: number } | null {
  if (textLength <= 0) {
    return null;
  }
  const normalizedStart = Math.max(0, Math.min(start, textLength - 1));
  const normalizedEnd = Math.max(normalizedStart + 1, Math.min(end, textLength));
  if (normalizedEnd <= normalizedStart) {
    return null;
  }
  return { end: normalizedEnd, start: normalizedStart };
}

export function resolveMatchSpanRange(
  matchSpanJson: Record<string, unknown> | null,
  textLength: number
): { end: number; start: number } | null {
  if (!matchSpanJson || typeof matchSpanJson !== "object") {
    return null;
  }
  if (textLength <= 0) {
    return null;
  }

  const nestedSpan = matchSpanJson.span;
  if (nestedSpan && typeof nestedSpan === "object" && !Array.isArray(nestedSpan)) {
    const nested = resolveMatchSpanRange(
      nestedSpan as Record<string, unknown>,
      textLength
    );
    if (nested) {
      return nested;
    }
  }

  const indices = matchSpanJson.indices;
  if (Array.isArray(indices) && indices.length >= 2) {
    const start = toFiniteInt(indices[0]);
    const end = toFiniteInt(indices[1]);
    if (start !== null && end !== null) {
      return clampRange(start, end, textLength);
    }
  }

  const start = readFirstInt(matchSpanJson, MATCH_SPAN_START_KEYS);
  const end = readFirstInt(matchSpanJson, MATCH_SPAN_END_KEYS);
  const length = readFirstInt(matchSpanJson, MATCH_SPAN_LENGTH_KEYS);
  if (start === null) {
    return null;
  }
  if (end !== null) {
    return clampRange(start, end, textLength);
  }
  if (length !== null) {
    return clampRange(start, start + Math.max(1, length), textLength);
  }
  return null;
}

function normalizeQueryText(queryText: string): string | null {
  const normalized = queryText.trim();
  if (normalized.length === 0) {
    return null;
  }
  return normalized;
}

function resolveQueryRange(text: string, queryText: string): { end: number; start: number } | null {
  const normalizedQuery = normalizeQueryText(queryText);
  if (!normalizedQuery) {
    return null;
  }
  const index = text.toLocaleLowerCase().indexOf(normalizedQuery.toLocaleLowerCase());
  if (index < 0) {
    return null;
  }
  return { end: index + normalizedQuery.length, start: index };
}

function resolveHighlightRange(hit: ProjectSearchHit, queryText: string): HighlightRange | null {
  const text = hit.searchText ?? "";
  const spanRange = resolveMatchSpanRange(hit.matchSpanJson, text.length);
  if (spanRange) {
    return {
      ...spanRange,
      kind: "SPAN"
    };
  }

  const queryRange = resolveQueryRange(text, queryText);
  if (queryRange) {
    return {
      ...queryRange,
      kind: "QUERY"
    };
  }
  return null;
}

function withEllipsis(text: string): string {
  return text.replace(/^\s+|\s+$/g, "");
}

export function buildSearchSnippetPreview(
  hit: ProjectSearchHit,
  queryText: string,
  maxChars = 180
): SearchSnippetPreview {
  const text = hit.searchText?.trim() ?? "";
  if (!text) {
    return {
      highlightKind: "NONE",
      prefixEllipsis: false,
      segments: [
        {
          highlighted: false,
          text: "(No excerpt available.)"
        }
      ],
      suffixEllipsis: false
    };
  }

  const safeMaxChars = Math.max(24, Math.round(maxChars));
  const range = resolveHighlightRange(hit, queryText);
  if (!range) {
    const clipped = text.slice(0, safeMaxChars);
    return {
      highlightKind: "NONE",
      prefixEllipsis: false,
      segments: [
        {
          highlighted: false,
          text: withEllipsis(clipped)
        }
      ],
      suffixEllipsis: text.length > safeMaxChars
    };
  }

  const highlightedLength = range.end - range.start;
  let start = Math.max(0, range.start - Math.floor((safeMaxChars - highlightedLength) / 2));
  let end = Math.min(text.length, start + safeMaxChars);
  if (end - start < safeMaxChars) {
    start = Math.max(0, end - safeMaxChars);
  }
  if (range.end > end) {
    end = range.end;
    start = Math.max(0, end - safeMaxChars);
  }
  if (range.start < start) {
    start = range.start;
    end = Math.min(text.length, start + safeMaxChars);
  }

  const localStart = Math.max(0, range.start - start);
  const localEnd = Math.min(end - start, Math.max(localStart + 1, range.end - start));
  const snippet = text.slice(start, end);

  const before = snippet.slice(0, localStart);
  const highlighted = snippet.slice(localStart, localEnd);
  const after = snippet.slice(localEnd);
  const segments: SearchSnippetSegment[] = [];
  if (before.length > 0) {
    segments.push({ highlighted: false, text: before });
  }
  if (highlighted.length > 0) {
    segments.push({ highlighted: true, text: highlighted });
  }
  if (after.length > 0) {
    segments.push({ highlighted: false, text: after });
  }

  return {
    highlightKind: range.kind,
    prefixEllipsis: start > 0,
    segments: segments.length > 0 ? segments : [{ highlighted: false, text: snippet }],
    suffixEllipsis: end < text.length
  };
}

export function groupSearchHitsByDocument(
  items: ProjectSearchHit[]
): GroupedSearchHits[] {
  const byDocument = new Map<string, ProjectSearchHit[]>();
  for (const item of items) {
    const existing = byDocument.get(item.documentId);
    if (existing) {
      existing.push(item);
      continue;
    }
    byDocument.set(item.documentId, [item]);
  }
  return Array.from(byDocument.entries()).map(([documentId, groupedItems]) => ({
    documentId,
    items: groupedItems
  }));
}

export function buildSearchReturnQuery(input: {
  cursor?: number;
  documentId?: string;
  pageNumber?: number;
  q?: string;
  runId?: string;
  selectedHitId?: string;
}): string {
  const params = new URLSearchParams();
  const q = input.q?.trim();
  if (q) {
    params.set("q", q);
  }
  const documentId = input.documentId?.trim();
  if (documentId) {
    params.set("documentId", documentId);
  }
  const runId = input.runId?.trim();
  if (runId) {
    params.set("runId", runId);
  }
  if (typeof input.pageNumber === "number" && Number.isFinite(input.pageNumber)) {
    params.set("pageNumber", String(Math.max(1, Math.round(input.pageNumber))));
  }
  if (typeof input.cursor === "number" && Number.isFinite(input.cursor) && input.cursor > 0) {
    params.set("cursor", String(Math.max(0, Math.round(input.cursor))));
  }
  const selectedHitId = input.selectedHitId?.trim();
  if (selectedHitId) {
    params.set("selectedHit", selectedHitId);
  }
  return params.toString();
}

export function describeSearchHitProvenance(hit: ProjectSearchHit): string {
  if (hit.tokenId) {
    return "Token-anchored hit";
  }
  if (hit.sourceKind === "RESCUE_CANDIDATE") {
    return "Rescue candidate source";
  }
  if (hit.sourceKind === "PAGE_WINDOW") {
    return "Page-window source";
  }
  if (hit.matchSpanJson) {
    return "Exact fallback span";
  }
  return "Line-linked source";
}

export function parseOptionalInt(value: string | undefined): number | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return undefined;
  }
  return parsed;
}

export function parseOptionalText(value: string | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : undefined;
}
