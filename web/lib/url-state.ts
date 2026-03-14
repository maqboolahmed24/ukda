interface IntegerNormalizationOptions {
  defaultValue: number;
  minimum?: number;
  maximum?: number;
}

export interface NormalizedIntegerParam {
  value: number;
  canonicalValue: string;
  shouldRedirect: boolean;
}

export interface NormalizedViewerZoomParam {
  value: number;
  canonicalValue: string | undefined;
  shouldRedirect: boolean;
}

export interface NormalizedViewerUrlState {
  mode: ViewerMode;
  page: number;
  comparePair: ViewerComparePair;
  runId: string | undefined;
  shouldRedirect: boolean;
  zoom: number;
}

export type ViewerMode = "original" | "preprocessed" | "compare";
export type ViewerComparePair =
  | "original_gray"
  | "original_binary"
  | "gray_binary";

interface NormalizedViewerModeParam {
  value: ViewerMode;
  canonicalValue: string | undefined;
  shouldRedirect: boolean;
}

interface NormalizedViewerRunIdParam {
  value: string | undefined;
  canonicalValue: string | undefined;
  shouldRedirect: boolean;
}

interface NormalizedViewerComparePairParam {
  value: ViewerComparePair;
  canonicalValue: string | undefined;
  shouldRedirect: boolean;
}

const DIGITS_ONLY = /^[0-9]+$/;
const ISO_DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
export const VIEWER_ZOOM_MIN = 25;
export const VIEWER_ZOOM_MAX = 400;
export const VIEWER_ZOOM_DEFAULT = 100;
const VIEWER_MODES: readonly ViewerMode[] = [
  "original",
  "preprocessed",
  "compare"
] as const;
const VIEWER_COMPARE_PAIRS: readonly ViewerComparePair[] = [
  "original_gray",
  "original_binary",
  "gray_binary"
] as const;

function clamp(value: number, minimum: number, maximum?: number): number {
  if (value < minimum) {
    return minimum;
  }
  if (typeof maximum === "number" && value > maximum) {
    return maximum;
  }
  return value;
}

function normalizeIntegerParam(
  raw: string | undefined,
  { defaultValue, minimum = 0, maximum }: IntegerNormalizationOptions
): NormalizedIntegerParam {
  const parsedFromRaw =
    typeof raw === "string" && DIGITS_ONLY.test(raw) ? Number(raw) : NaN;
  const hasNumericRaw = Number.isFinite(parsedFromRaw);
  const normalized = clamp(
    hasNumericRaw ? parsedFromRaw : defaultValue,
    minimum,
    maximum
  );
  const canonicalValue = String(normalized);
  const shouldRedirect = raw !== canonicalValue;

  return {
    value: normalized,
    canonicalValue,
    shouldRedirect
  };
}

export function normalizeViewerPageParam(
  raw: string | undefined
): NormalizedIntegerParam {
  return normalizeIntegerParam(raw, {
    defaultValue: 1,
    minimum: 1
  });
}

export function normalizeViewerZoomParam(
  raw: string | undefined
): NormalizedViewerZoomParam {
  if (typeof raw !== "string") {
    return {
      value: VIEWER_ZOOM_DEFAULT,
      canonicalValue: undefined,
      shouldRedirect: false
    };
  }
  const parsed =
    DIGITS_ONLY.test(raw) && Number.isFinite(Number(raw)) ? Number(raw) : NaN;
  if (!Number.isFinite(parsed)) {
    return {
      value: VIEWER_ZOOM_DEFAULT,
      canonicalValue: undefined,
      shouldRedirect: true
    };
  }

  const rounded = Math.round(parsed);
  const clamped = clamp(rounded, VIEWER_ZOOM_MIN, VIEWER_ZOOM_MAX);
  const canonicalValue =
    clamped === VIEWER_ZOOM_DEFAULT ? undefined : String(clamped);
  const shouldRedirect = raw !== String(clamped) || canonicalValue === undefined;
  return {
    value: clamped,
    canonicalValue,
    shouldRedirect
  };
}

export function normalizeViewerUrlState(params: {
  comparePair?: string;
  mode?: string;
  page?: string;
  runId?: string;
  zoom?: string;
}): NormalizedViewerUrlState {
  const page = normalizeViewerPageParam(params.page);
  const zoom = normalizeViewerZoomParam(params.zoom);
  const mode = normalizeViewerModeParam(params.mode);
  const comparePair = normalizeViewerComparePairParam(params.comparePair);
  const runId = normalizeViewerRunIdParam(params.runId);
  const canonicalRunId =
    mode.value === "original" ? undefined : runId.value;
  return {
    mode: mode.value,
    page: page.value,
    comparePair: mode.value === "compare" ? comparePair.value : "original_gray",
    runId: canonicalRunId,
    zoom: zoom.value,
    shouldRedirect:
      page.shouldRedirect ||
      zoom.shouldRedirect ||
      mode.shouldRedirect ||
      comparePair.shouldRedirect ||
      runId.shouldRedirect ||
      (mode.value === "original" && typeof runId.value === "string") ||
      (mode.value !== "compare" && typeof params.comparePair === "string")
  };
}

export function normalizeViewerModeParam(
  raw: string | undefined
): NormalizedViewerModeParam {
  if (typeof raw !== "string") {
    return {
      value: "original",
      canonicalValue: undefined,
      shouldRedirect: false
    };
  }
  const normalized = raw.trim().toLowerCase();
  if (!VIEWER_MODES.includes(normalized as ViewerMode)) {
    return {
      value: "original",
      canonicalValue: undefined,
      shouldRedirect: true
    };
  }
  if (normalized === "original") {
    return {
      value: "original",
      canonicalValue: undefined,
      shouldRedirect: true
    };
  }
  return {
    value: normalized as ViewerMode,
    canonicalValue: normalized,
    shouldRedirect: raw !== normalized
  };
}

export function normalizeViewerRunIdParam(
  raw: string | undefined
): NormalizedViewerRunIdParam {
  if (typeof raw !== "string") {
    return {
      value: undefined,
      canonicalValue: undefined,
      shouldRedirect: false
    };
  }
  const trimmed = raw.trim();
  if (!trimmed) {
    return {
      value: undefined,
      canonicalValue: undefined,
      shouldRedirect: true
    };
  }
  return {
    value: trimmed,
    canonicalValue: trimmed,
    shouldRedirect: raw !== trimmed
  };
}

export function normalizeViewerComparePairParam(
  raw: string | undefined
): NormalizedViewerComparePairParam {
  if (typeof raw !== "string") {
    return {
      value: "original_gray",
      canonicalValue: undefined,
      shouldRedirect: false
    };
  }
  const normalized = raw.trim().toLowerCase().replace("-", "_");
  if (!VIEWER_COMPARE_PAIRS.includes(normalized as ViewerComparePair)) {
    return {
      value: "original_gray",
      canonicalValue: undefined,
      shouldRedirect: true
    };
  }
  if (normalized === "original_gray") {
    return {
      value: "original_gray",
      canonicalValue: undefined,
      shouldRedirect: true
    };
  }
  return {
    value: normalized as ViewerComparePair,
    canonicalValue: normalized,
    shouldRedirect: raw !== normalized
  };
}

export function normalizeCursorParam(raw: string | undefined): number {
  return normalizeIntegerParam(raw, {
    defaultValue: 0,
    minimum: 0
  }).value;
}

export function normalizeOptionalTextParam(
  raw: string | undefined
): string | undefined {
  if (typeof raw !== "string") {
    return undefined;
  }
  const trimmed = raw.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function normalizeOptionalDateParam(
  raw: string | undefined
): string | undefined {
  if (typeof raw !== "string") {
    return undefined;
  }
  const trimmed = raw.trim();
  if (!trimmed) {
    return undefined;
  }
  if (!ISO_DATE_ONLY.test(trimmed)) {
    return undefined;
  }
  const [year, month, day] = trimmed.split("-").map((part) => Number(part));
  if (
    !Number.isInteger(year) ||
    !Number.isInteger(month) ||
    !Number.isInteger(day)
  ) {
    return undefined;
  }
  const parsed = new Date(Date.UTC(year, month - 1, day));
  const matchesSource =
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day;
  return matchesSource ? trimmed : undefined;
}

export function normalizeOptionalEnumParam<T extends string>(
  raw: string | undefined,
  allowedValues: readonly T[]
): T | undefined {
  if (typeof raw !== "string") {
    return undefined;
  }
  return allowedValues.includes(raw as T) ? (raw as T) : undefined;
}
