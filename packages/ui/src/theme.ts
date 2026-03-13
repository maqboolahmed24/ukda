import type { ThemeMode, ThemePreference } from "@ukde/contracts";

export const THEME_PREFERENCE_STORAGE_KEY = "ukde.theme.preference";
export const THEME_PREFERENCE_EVENT = "ukde-theme-preference-change";

export const themePreferenceOptions: ThemePreference[] = [
  "system",
  "dark",
  "light"
];

export const themePreferenceLabels: Record<ThemePreference, string> = {
  system: "System",
  dark: "Dark",
  light: "Light"
};

export interface ThemeMediaState {
  prefersDark: boolean;
  prefersContrastMore: boolean;
  forcedColorsActive: boolean;
  reducedMotion: boolean;
  reducedTransparency: "reduce" | "no-preference" | "unsupported";
}

export interface ThemeRuntimeState extends ThemeMediaState {
  preference: ThemePreference;
  mode: ThemeMode;
  contrast: "more" | "no-preference" | "forced";
  motion: "reduce" | "no-preference";
}

const MEDIA_QUERIES = {
  prefersDark: "(prefers-color-scheme: dark)",
  prefersContrastMore: "(prefers-contrast: more)",
  forcedColorsActive: "(forced-colors: active)",
  reducedMotion: "(prefers-reduced-motion: reduce)",
  reducedTransparency: "(prefers-reduced-transparency: reduce)"
} as const;

type MediaQueryKey = keyof typeof MEDIA_QUERIES;

function resolveMediaQuery(
  targetWindow: Window,
  query: string
): MediaQueryList | null {
  if (typeof targetWindow.matchMedia !== "function") {
    return null;
  }
  try {
    return targetWindow.matchMedia(query);
  } catch {
    return null;
  }
}

function attachMediaListener(
  queryList: MediaQueryList,
  callback: () => void
): () => void {
  if (typeof queryList.addEventListener === "function") {
    queryList.addEventListener("change", callback);
    return () => queryList.removeEventListener("change", callback);
  }
  queryList.addListener(callback);
  return () => queryList.removeListener(callback);
}

function readQueryState(
  queryList: MediaQueryList | null
): "reduce" | "no-preference" | "unsupported" {
  if (!queryList) {
    return "unsupported";
  }
  if (queryList.media === "not all") {
    return "unsupported";
  }
  return queryList.matches ? "reduce" : "no-preference";
}

function isStorageAvailable(target: unknown): target is Storage {
  if (!target) {
    return false;
  }
  return (
    typeof target === "object" &&
    "getItem" in target &&
    "setItem" in target &&
    typeof (target as Storage).getItem === "function" &&
    typeof (target as Storage).setItem === "function"
  );
}

export function isThemePreference(value: string | null): value is ThemePreference {
  if (!value) {
    return false;
  }
  return themePreferenceOptions.includes(value as ThemePreference);
}

export function resolveThemeMode(
  preference: ThemePreference,
  prefersDark: boolean
): ThemeMode {
  if (preference === "dark") {
    return "dark";
  }
  if (preference === "light") {
    return "light";
  }
  return prefersDark ? "dark" : "light";
}

export function readStoredThemePreference(
  storage: Storage | null = isStorageAvailable(globalThis.localStorage)
    ? globalThis.localStorage
    : null
): ThemePreference {
  if (!isStorageAvailable(storage)) {
    return "system";
  }
  try {
    const value = storage.getItem(THEME_PREFERENCE_STORAGE_KEY);
    if (isThemePreference(value)) {
      return value;
    }
  } catch {
    return "system";
  }
  return "system";
}

export function setStoredThemePreference(
  preference: ThemePreference,
  storage: Storage | null = isStorageAvailable(globalThis.localStorage)
    ? globalThis.localStorage
    : null
): void {
  if (!isStorageAvailable(storage)) {
    return;
  }
  try {
    storage.setItem(THEME_PREFERENCE_STORAGE_KEY, preference);
  } catch {
    // Browsers may reject storage writes in private modes.
  }
}

export function readThemeMediaState(
  targetWindow: Window = window
): ThemeMediaState {
  const prefersDark = resolveMediaQuery(targetWindow, MEDIA_QUERIES.prefersDark);
  const prefersContrastMore = resolveMediaQuery(
    targetWindow,
    MEDIA_QUERIES.prefersContrastMore
  );
  const forcedColorsActive = resolveMediaQuery(
    targetWindow,
    MEDIA_QUERIES.forcedColorsActive
  );
  const reducedMotion = resolveMediaQuery(
    targetWindow,
    MEDIA_QUERIES.reducedMotion
  );
  const reducedTransparency = resolveMediaQuery(
    targetWindow,
    MEDIA_QUERIES.reducedTransparency
  );

  return {
    prefersDark: Boolean(prefersDark?.matches),
    prefersContrastMore: Boolean(prefersContrastMore?.matches),
    forcedColorsActive: Boolean(forcedColorsActive?.matches),
    reducedMotion: Boolean(reducedMotion?.matches),
    reducedTransparency: readQueryState(reducedTransparency)
  };
}

export function resolveThemeRuntime(
  preference: ThemePreference,
  mediaState: ThemeMediaState
): ThemeRuntimeState {
  return {
    ...mediaState,
    preference,
    mode: resolveThemeMode(preference, mediaState.prefersDark),
    contrast: mediaState.forcedColorsActive
      ? "forced"
      : mediaState.prefersContrastMore
        ? "more"
        : "no-preference",
    motion: mediaState.reducedMotion ? "reduce" : "no-preference"
  };
}

export function applyThemeRuntime(
  runtime: ThemeRuntimeState,
  targetElement: HTMLElement = document.documentElement
): ThemeRuntimeState {
  targetElement.dataset.themePreference = runtime.preference;
  targetElement.dataset.theme = runtime.mode;
  targetElement.dataset.themeContrast = runtime.contrast;
  targetElement.dataset.themeMotion = runtime.motion;
  targetElement.dataset.themeTransparency = runtime.reducedTransparency;
  targetElement.dataset.themeForcedColors = runtime.forcedColorsActive
    ? "active"
    : "inactive";
  return runtime;
}

export function syncThemeRuntime(
  preference: ThemePreference,
  targetWindow: Window = window,
  targetDocument: Document = document
): ThemeRuntimeState {
  const runtime = resolveThemeRuntime(
    preference,
    readThemeMediaState(targetWindow)
  );
  applyThemeRuntime(runtime, targetDocument.documentElement);
  return runtime;
}

export function subscribeThemeMediaChanges(
  callback: () => void,
  targetWindow: Window = window
): () => void {
  const queryLists = Object.values(MEDIA_QUERIES)
    .map((query) => resolveMediaQuery(targetWindow, query))
    .filter((queryList): queryList is MediaQueryList => queryList !== null);

  if (queryLists.length === 0) {
    return () => undefined;
  }

  const unsubscribers = queryLists.map((queryList) =>
    attachMediaListener(queryList, callback)
  );

  return () => {
    for (const unsubscribe of unsubscribers) {
      unsubscribe();
    }
  };
}

export function getThemeMediaQueries(): Record<MediaQueryKey, string> {
  return { ...MEDIA_QUERIES };
}
