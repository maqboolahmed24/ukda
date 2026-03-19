module.exports = [
"[externals]/next/dist/compiled/next-server/app-page-turbo.runtime.dev.js [external] (next/dist/compiled/next-server/app-page-turbo.runtime.dev.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/compiled/next-server/app-page-turbo.runtime.dev.js", () => require("next/dist/compiled/next-server/app-page-turbo.runtime.dev.js"));

module.exports = mod;
}),
"[project]/packages/ui/src/theme.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "THEME_PREFERENCE_EVENT",
    ()=>THEME_PREFERENCE_EVENT,
    "THEME_PREFERENCE_STORAGE_KEY",
    ()=>THEME_PREFERENCE_STORAGE_KEY,
    "applyThemeRuntime",
    ()=>applyThemeRuntime,
    "getThemeMediaQueries",
    ()=>getThemeMediaQueries,
    "isThemePreference",
    ()=>isThemePreference,
    "readStoredThemePreference",
    ()=>readStoredThemePreference,
    "readThemeMediaState",
    ()=>readThemeMediaState,
    "resolveThemeMode",
    ()=>resolveThemeMode,
    "resolveThemeRuntime",
    ()=>resolveThemeRuntime,
    "setStoredThemePreference",
    ()=>setStoredThemePreference,
    "subscribeThemeMediaChanges",
    ()=>subscribeThemeMediaChanges,
    "syncThemeRuntime",
    ()=>syncThemeRuntime,
    "themePreferenceLabels",
    ()=>themePreferenceLabels,
    "themePreferenceOptions",
    ()=>themePreferenceOptions
]);
const THEME_PREFERENCE_STORAGE_KEY = "ukde.theme.preference";
const THEME_PREFERENCE_EVENT = "ukde-theme-preference-change";
const themePreferenceOptions = [
    "system",
    "dark",
    "light"
];
const themePreferenceLabels = {
    system: "System",
    dark: "Dark",
    light: "Light"
};
const MEDIA_QUERIES = {
    prefersDark: "(prefers-color-scheme: dark)",
    prefersContrastMore: "(prefers-contrast: more)",
    forcedColorsActive: "(forced-colors: active)",
    reducedMotion: "(prefers-reduced-motion: reduce)",
    reducedTransparency: "(prefers-reduced-transparency: reduce)"
};
function resolveMediaQuery(targetWindow, query) {
    if (typeof targetWindow.matchMedia !== "function") {
        return null;
    }
    try {
        return targetWindow.matchMedia(query);
    } catch  {
        return null;
    }
}
function attachMediaListener(queryList, callback) {
    if (typeof queryList.addEventListener === "function") {
        queryList.addEventListener("change", callback);
        return ()=>queryList.removeEventListener("change", callback);
    }
    queryList.addListener(callback);
    return ()=>queryList.removeListener(callback);
}
function readQueryState(queryList) {
    if (!queryList) {
        return "unsupported";
    }
    if (queryList.media === "not all") {
        return "unsupported";
    }
    return queryList.matches ? "reduce" : "no-preference";
}
function isStorageAvailable(target) {
    if (!target) {
        return false;
    }
    return typeof target === "object" && "getItem" in target && "setItem" in target && typeof target.getItem === "function" && typeof target.setItem === "function";
}
function isThemePreference(value) {
    if (!value) {
        return false;
    }
    return themePreferenceOptions.includes(value);
}
function resolveThemeMode(preference, prefersDark) {
    if (preference === "dark") {
        return "dark";
    }
    if (preference === "light") {
        return "light";
    }
    return prefersDark ? "dark" : "light";
}
function readStoredThemePreference(storage = isStorageAvailable(globalThis.localStorage) ? globalThis.localStorage : null) {
    if (!isStorageAvailable(storage)) {
        return "system";
    }
    try {
        const value = storage.getItem(THEME_PREFERENCE_STORAGE_KEY);
        if (isThemePreference(value)) {
            return value;
        }
    } catch  {
        return "system";
    }
    return "system";
}
function setStoredThemePreference(preference, storage = isStorageAvailable(globalThis.localStorage) ? globalThis.localStorage : null) {
    if (!isStorageAvailable(storage)) {
        return;
    }
    try {
        storage.setItem(THEME_PREFERENCE_STORAGE_KEY, preference);
    } catch  {
    // Browsers may reject storage writes in private modes.
    }
}
function readThemeMediaState(targetWindow = window) {
    const prefersDark = resolveMediaQuery(targetWindow, MEDIA_QUERIES.prefersDark);
    const prefersContrastMore = resolveMediaQuery(targetWindow, MEDIA_QUERIES.prefersContrastMore);
    const forcedColorsActive = resolveMediaQuery(targetWindow, MEDIA_QUERIES.forcedColorsActive);
    const reducedMotion = resolveMediaQuery(targetWindow, MEDIA_QUERIES.reducedMotion);
    const reducedTransparency = resolveMediaQuery(targetWindow, MEDIA_QUERIES.reducedTransparency);
    return {
        prefersDark: Boolean(prefersDark?.matches),
        prefersContrastMore: Boolean(prefersContrastMore?.matches),
        forcedColorsActive: Boolean(forcedColorsActive?.matches),
        reducedMotion: Boolean(reducedMotion?.matches),
        reducedTransparency: readQueryState(reducedTransparency)
    };
}
function resolveThemeRuntime(preference, mediaState) {
    return {
        ...mediaState,
        preference,
        mode: resolveThemeMode(preference, mediaState.prefersDark),
        contrast: mediaState.forcedColorsActive ? "forced" : mediaState.prefersContrastMore ? "more" : "no-preference",
        motion: mediaState.reducedMotion ? "reduce" : "no-preference"
    };
}
function applyThemeRuntime(runtime, targetElement = document.documentElement) {
    targetElement.dataset.themePreference = runtime.preference;
    targetElement.dataset.theme = runtime.mode;
    targetElement.dataset.themeContrast = runtime.contrast;
    targetElement.dataset.themeMotion = runtime.motion;
    targetElement.dataset.themeTransparency = runtime.reducedTransparency;
    targetElement.dataset.themeForcedColors = runtime.forcedColorsActive ? "active" : "inactive";
    return runtime;
}
function syncThemeRuntime(preference, targetWindow = window, targetDocument = document) {
    const runtime = resolveThemeRuntime(preference, readThemeMediaState(targetWindow));
    applyThemeRuntime(runtime, targetDocument.documentElement);
    return runtime;
}
function subscribeThemeMediaChanges(callback, targetWindow = window) {
    const queryLists = Object.values(MEDIA_QUERIES).map((query)=>resolveMediaQuery(targetWindow, query)).filter((queryList)=>queryList !== null);
    if (queryLists.length === 0) {
        return ()=>undefined;
    }
    const unsubscribers = queryLists.map((queryList)=>attachMediaListener(queryList, callback));
    return ()=>{
        for (const unsubscribe of unsubscribers){
            unsubscribe();
        }
    };
}
function getThemeMediaQueries() {
    return {
        ...MEDIA_QUERIES
    };
}
}),
"[project]/packages/ui/src/tokens.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "baseTokenVariables",
    ()=>baseTokenVariables,
    "darkThemeColorTokens",
    ()=>darkThemeColorTokens,
    "elevationTokens",
    ()=>elevationTokens,
    "focusTokens",
    ()=>focusTokens,
    "lightThemeColorTokens",
    ()=>lightThemeColorTokens,
    "motionTokens",
    ()=>motionTokens,
    "radiusTokens",
    ()=>radiusTokens,
    "spacingTokens",
    ()=>spacingTokens,
    "themeColorTokens",
    ()=>themeColorTokens,
    "themeColorVariables",
    ()=>themeColorVariables,
    "themeTokens",
    ()=>themeTokens,
    "typographyTokens",
    ()=>typographyTokens
]);
const typographyTokens = {
    family: {
        sans: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif',
        serif: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif',
        mono: '"SF Mono", "Cascadia Code", "IBM Plex Mono", Menlo, Consolas, monospace'
    },
    weight: {
        regular: "400",
        medium: "500",
        semibold: "600",
        bold: "700"
    },
    scale: {
        shellTitle: {
            size: "clamp(1.25rem, 1.2vw + 1rem, 2rem)",
            lineHeight: "1.02",
            letterSpacing: "-0.04em",
            weight: "700"
        },
        pageTitle: {
            size: "clamp(1.2rem, 1vw + 1rem, 1.75rem)",
            lineHeight: "1.08",
            letterSpacing: "-0.03em",
            weight: "650"
        },
        sectionTitle: {
            size: "clamp(1.05rem, 0.6vw + 0.95rem, 1.4rem)",
            lineHeight: "1.12",
            letterSpacing: "-0.02em",
            weight: "620"
        },
        body: {
            size: "0.98rem",
            lineHeight: "1.45",
            letterSpacing: "0",
            weight: "500"
        },
        metadata: {
            size: "0.83rem",
            lineHeight: "1.34",
            letterSpacing: "0.03em",
            weight: "550"
        },
        microcopy: {
            size: "0.74rem",
            lineHeight: "1.3",
            letterSpacing: "0.04em",
            weight: "550"
        }
    }
};
const spacingTokens = {
    0: "0",
    1: "0.25rem",
    2: "0.5rem",
    3: "0.75rem",
    4: "1rem",
    5: "1.5rem",
    6: "2rem",
    7: "2.5rem",
    8: "3rem",
    9: "4rem"
};
const radiusTokens = {
    xs: "0.16rem",
    sm: "0.26rem",
    md: "0.38rem",
    lg: "0.52rem",
    xl: "0.68rem",
    pill: "1.02rem"
};
const elevationTokens = {
    0: "none",
    1: "0 10px 28px rgba(0, 0, 0, 0.2)",
    2: "0 20px 56px rgba(0, 0, 0, 0.28)",
    3: "0 30px 80px rgba(0, 0, 0, 0.36)"
};
const motionTokens = {
    duration: {
        instant: "0ms",
        quick: "120ms",
        standard: "180ms",
        deliberate: "260ms"
    },
    easing: {
        standard: "cubic-bezier(0.2, 0, 0, 1)",
        emphasized: "cubic-bezier(0.2, 0, 0, 1.2)",
        accelerate: "cubic-bezier(0.4, 0, 1, 1)",
        decelerate: "cubic-bezier(0, 0, 0.2, 1)"
    }
};
const focusTokens = {
    ringWidth: "2px",
    ringOffset: "2px",
    ringSoftSpread: "4px"
};
const darkThemeColorTokens = {
    background: {
        canvas: "#070b12",
        frame: "#0f1623",
        muted: "#131d2d"
    },
    surface: {
        quiet: "rgba(14, 22, 34, 0.7)",
        default: "rgba(18, 27, 41, 0.86)",
        raised: "#1a2539",
        overlay: "rgba(24, 35, 53, 0.94)",
        emphasis: "#22314a"
    },
    border: {
        subtle: "rgba(146, 166, 196, 0.16)",
        default: "rgba(146, 166, 196, 0.28)",
        strong: "rgba(165, 189, 222, 0.5)"
    },
    text: {
        primary: "#f2f6ff",
        muted: "#b6c3da",
        subtle: "#92a3bf",
        onAccent: "#08131f"
    },
    accent: {
        primary: "#8bb7ff",
        strong: "#b0ceff",
        soft: "rgba(139, 183, 255, 0.18)"
    },
    status: {
        success: "#95d9b6",
        warning: "#f1c786",
        danger: "#f3a4a4",
        info: "#89c8ff"
    },
    environment: {
        dev: "#87befe",
        staging: "#f1c786",
        prod: "#95d9b6",
        test: "#b6a5ff"
    },
    accessTier: {
        controlled: "#f1c786",
        safeguarded: "#95d9b6",
        open: "#9eb4cf"
    },
    focus: {
        ring: "#f4df9f",
        contrast: "rgba(10, 20, 34, 0.95)"
    }
};
const lightThemeColorTokens = {
    background: {
        canvas: "#f4f7fb",
        frame: "#e8edf5",
        muted: "#dfe6f0"
    },
    surface: {
        quiet: "rgba(255, 255, 255, 0.68)",
        default: "rgba(255, 255, 255, 0.92)",
        raised: "#ffffff",
        overlay: "rgba(255, 255, 255, 0.97)",
        emphasis: "#ecf3ff"
    },
    border: {
        subtle: "rgba(61, 79, 105, 0.14)",
        default: "rgba(61, 79, 105, 0.24)",
        strong: "rgba(37, 64, 102, 0.38)"
    },
    text: {
        primary: "#121b28",
        muted: "#4a5c73",
        subtle: "#61748c",
        onAccent: "#f5f8ff"
    },
    accent: {
        primary: "#225fbe",
        strong: "#174991",
        soft: "rgba(34, 95, 190, 0.14)"
    },
    status: {
        success: "#176242",
        warning: "#855b1f",
        danger: "#9d2f2f",
        info: "#245e95"
    },
    environment: {
        dev: "#245e95",
        staging: "#855b1f",
        prod: "#176242",
        test: "#6042ac"
    },
    accessTier: {
        controlled: "#855b1f",
        safeguarded: "#176242",
        open: "#4a5c73"
    },
    focus: {
        ring: "#1c57b0",
        contrast: "#ffffff"
    }
};
const themeColorTokens = {
    dark: darkThemeColorTokens,
    light: lightThemeColorTokens
};
function toThemeColorVariables(tokens) {
    return {
        "--ukde-color-bg-canvas": tokens.background.canvas,
        "--ukde-color-bg-frame": tokens.background.frame,
        "--ukde-color-bg-muted": tokens.background.muted,
        "--ukde-color-surface-quiet": tokens.surface.quiet,
        "--ukde-color-surface-default": tokens.surface.default,
        "--ukde-color-surface-raised": tokens.surface.raised,
        "--ukde-color-surface-overlay": tokens.surface.overlay,
        "--ukde-color-surface-emphasis": tokens.surface.emphasis,
        "--ukde-color-border-subtle": tokens.border.subtle,
        "--ukde-color-border-default": tokens.border.default,
        "--ukde-color-border-strong": tokens.border.strong,
        "--ukde-color-text-primary": tokens.text.primary,
        "--ukde-color-text-muted": tokens.text.muted,
        "--ukde-color-text-subtle": tokens.text.subtle,
        "--ukde-color-text-on-accent": tokens.text.onAccent,
        "--ukde-color-accent-primary": tokens.accent.primary,
        "--ukde-color-accent-strong": tokens.accent.strong,
        "--ukde-color-accent-soft": tokens.accent.soft,
        "--ukde-color-status-success": tokens.status.success,
        "--ukde-color-status-warning": tokens.status.warning,
        "--ukde-color-status-danger": tokens.status.danger,
        "--ukde-color-status-info": tokens.status.info,
        "--ukde-color-env-dev": tokens.environment.dev,
        "--ukde-color-env-staging": tokens.environment.staging,
        "--ukde-color-env-prod": tokens.environment.prod,
        "--ukde-color-env-test": tokens.environment.test,
        "--ukde-color-tier-controlled": tokens.accessTier.controlled,
        "--ukde-color-tier-safeguarded": tokens.accessTier.safeguarded,
        "--ukde-color-tier-open": tokens.accessTier.open,
        "--ukde-color-focus-ring": tokens.focus.ring,
        "--ukde-color-focus-contrast": tokens.focus.contrast
    };
}
const themeColorVariables = {
    dark: toThemeColorVariables(darkThemeColorTokens),
    light: toThemeColorVariables(lightThemeColorTokens)
};
const baseTokenVariables = {
    "--ukde-font-sans": typographyTokens.family.sans,
    "--ukde-font-serif": typographyTokens.family.serif,
    "--ukde-font-mono": typographyTokens.family.mono,
    "--ukde-type-shell-title-size": typographyTokens.scale.shellTitle.size,
    "--ukde-type-shell-title-line-height": typographyTokens.scale.shellTitle.lineHeight,
    "--ukde-type-shell-title-letter-spacing": typographyTokens.scale.shellTitle.letterSpacing,
    "--ukde-type-shell-title-weight": typographyTokens.scale.shellTitle.weight,
    "--ukde-type-page-title-size": typographyTokens.scale.pageTitle.size,
    "--ukde-type-page-title-line-height": typographyTokens.scale.pageTitle.lineHeight,
    "--ukde-type-page-title-letter-spacing": typographyTokens.scale.pageTitle.letterSpacing,
    "--ukde-type-page-title-weight": typographyTokens.scale.pageTitle.weight,
    "--ukde-type-section-title-size": typographyTokens.scale.sectionTitle.size,
    "--ukde-type-section-title-line-height": typographyTokens.scale.sectionTitle.lineHeight,
    "--ukde-type-section-title-letter-spacing": typographyTokens.scale.sectionTitle.letterSpacing,
    "--ukde-type-section-title-weight": typographyTokens.scale.sectionTitle.weight,
    "--ukde-type-body-size": typographyTokens.scale.body.size,
    "--ukde-type-body-line-height": typographyTokens.scale.body.lineHeight,
    "--ukde-type-body-letter-spacing": typographyTokens.scale.body.letterSpacing,
    "--ukde-type-body-weight": typographyTokens.scale.body.weight,
    "--ukde-type-meta-size": typographyTokens.scale.metadata.size,
    "--ukde-type-meta-line-height": typographyTokens.scale.metadata.lineHeight,
    "--ukde-type-meta-letter-spacing": typographyTokens.scale.metadata.letterSpacing,
    "--ukde-type-meta-weight": typographyTokens.scale.metadata.weight,
    "--ukde-type-micro-size": typographyTokens.scale.microcopy.size,
    "--ukde-type-micro-line-height": typographyTokens.scale.microcopy.lineHeight,
    "--ukde-type-micro-letter-spacing": typographyTokens.scale.microcopy.letterSpacing,
    "--ukde-type-micro-weight": typographyTokens.scale.microcopy.weight,
    "--ukde-space-0": spacingTokens[0],
    "--ukde-space-1": spacingTokens[1],
    "--ukde-space-2": spacingTokens[2],
    "--ukde-space-3": spacingTokens[3],
    "--ukde-space-4": spacingTokens[4],
    "--ukde-space-5": spacingTokens[5],
    "--ukde-space-6": spacingTokens[6],
    "--ukde-space-7": spacingTokens[7],
    "--ukde-space-8": spacingTokens[8],
    "--ukde-space-9": spacingTokens[9],
    "--ukde-radius-xs": radiusTokens.xs,
    "--ukde-radius-sm": radiusTokens.sm,
    "--ukde-radius-md": radiusTokens.md,
    "--ukde-radius-lg": radiusTokens.lg,
    "--ukde-radius-xl": radiusTokens.xl,
    "--ukde-radius-pill": radiusTokens.pill,
    "--ukde-shadow-0": elevationTokens[0],
    "--ukde-shadow-1": elevationTokens[1],
    "--ukde-shadow-2": elevationTokens[2],
    "--ukde-shadow-3": elevationTokens[3],
    "--ukde-motion-duration-instant": motionTokens.duration.instant,
    "--ukde-motion-duration-quick": motionTokens.duration.quick,
    "--ukde-motion-duration-standard": motionTokens.duration.standard,
    "--ukde-motion-duration-deliberate": motionTokens.duration.deliberate,
    "--ukde-motion-ease-standard": motionTokens.easing.standard,
    "--ukde-motion-ease-emphasized": motionTokens.easing.emphasized,
    "--ukde-motion-ease-accelerate": motionTokens.easing.accelerate,
    "--ukde-motion-ease-decelerate": motionTokens.easing.decelerate,
    "--ukde-focus-ring-width": focusTokens.ringWidth,
    "--ukde-focus-ring-offset": focusTokens.ringOffset,
    "--ukde-focus-ring-soft-spread": focusTokens.ringSoftSpread,
    "--ukde-material-blur": "14px"
};
const themeTokens = {
    colors: {
        background: darkThemeColorTokens.background.canvas,
        backgroundAlt: darkThemeColorTokens.background.frame,
        surface: darkThemeColorTokens.surface.default,
        surfaceStrong: darkThemeColorTokens.surface.raised,
        border: darkThemeColorTokens.border.default,
        text: darkThemeColorTokens.text.primary,
        textMuted: darkThemeColorTokens.text.muted,
        accent: darkThemeColorTokens.accent.primary,
        success: darkThemeColorTokens.status.success,
        warning: darkThemeColorTokens.status.warning,
        danger: darkThemeColorTokens.status.danger,
        focus: darkThemeColorTokens.focus.ring
    },
    typography: typographyTokens.family,
    radius: {
        sm: radiusTokens.sm,
        md: radiusTokens.md,
        lg: radiusTokens.lg
    },
    spacing: {
        xs: spacingTokens[2],
        sm: spacingTokens[3],
        md: spacingTokens[4],
        lg: spacingTokens[5],
        xl: spacingTokens[6]
    },
    elevation: {
        shell: elevationTokens[2]
    },
    motion: {
        quick: `${motionTokens.duration.standard} ${motionTokens.easing.standard}`
    }
};
}),
"[project]/packages/ui/src/index.ts [app-ssr] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "accessTierBadgeTones",
    ()=>accessTierBadgeTones,
    "accessTierLabels",
    ()=>accessTierLabels,
    "designPillars",
    ()=>designPillars,
    "environmentLabels",
    ()=>environmentLabels,
    "projectRoleLabels",
    ()=>projectRoleLabels,
    "shellStateNotes",
    ()=>shellStateNotes
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$theme$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/packages/ui/src/theme.ts [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$tokens$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/packages/ui/src/tokens.ts [app-ssr] (ecmascript)");
;
;
const shellStateNotes = {
    Expanded: "Rail, workspace, and inspector remain visible for dense review work.",
    Balanced: "The workspace stays dominant while secondary context compresses to summaries.",
    Compact: "Navigation and inspection move to compact affordances without losing object focus.",
    Focus: "The active review surface takes priority while supporting context becomes on-demand."
};
const designPillars = [
    "Dark-first, research-grade surfaces",
    "Bounded work regions instead of page sprawl",
    "Visible confidence, provenance, and governance state",
    "Keyboard-first interaction with explicit focus"
];
const accessTierLabels = {
    CONTROLLED: "Controlled",
    SAFEGUARDED: "Safeguarded",
    OPEN: "Open"
};
const accessTierBadgeTones = {
    CONTROLLED: "warning",
    SAFEGUARDED: "success",
    OPEN: "default"
};
const environmentLabels = {
    dev: "Development",
    staging: "Staging",
    prod: "Production",
    test: "Test"
};
const projectRoleLabels = {
    PROJECT_LEAD: "Project lead",
    RESEARCHER: "Researcher",
    REVIEWER: "Reviewer"
};
}),
"[project]/web/components/theme-runtime-sync.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ThemeRuntimeSync",
    ()=>ThemeRuntimeSync
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/.pnpm/next@16.1.6_@playwright+test@1.58.2_react-dom@19.2.4_react@19.2.4__react@19.2.4/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/packages/ui/src/index.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$theme$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/packages/ui/src/theme.ts [app-ssr] (ecmascript)");
"use client";
;
;
function ThemeRuntimeSync() {
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$1$2e$6_$40$playwright$2b$test$40$1$2e$58$2e$2_react$2d$dom$40$19$2e$2$2e$4_react$40$19$2e$2$2e$4_$5f$react$40$19$2e$2$2e$4$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        const sync = ()=>{
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$theme$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["syncThemeRuntime"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$theme$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["readStoredThemePreference"])());
        };
        sync();
        const unsubscribeMedia = (0, __TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$theme$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["subscribeThemeMediaChanges"])(sync);
        const handleStorageChange = (event)=>{
            if (event.key && event.key !== __TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$theme$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["THEME_PREFERENCE_STORAGE_KEY"]) {
                return;
            }
            sync();
        };
        const handlePreferenceEvent = ()=>{
            sync();
        };
        window.addEventListener("storage", handleStorageChange);
        window.addEventListener(__TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$theme$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["THEME_PREFERENCE_EVENT"], handlePreferenceEvent);
        return ()=>{
            unsubscribeMedia();
            window.removeEventListener("storage", handleStorageChange);
            window.removeEventListener(__TURBOPACK__imported__module__$5b$project$5d2f$packages$2f$ui$2f$src$2f$theme$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["THEME_PREFERENCE_EVENT"], handlePreferenceEvent);
        };
    }, []);
    return null;
}
}),
"[externals]/next/dist/server/app-render/work-async-storage.external.js [external] (next/dist/server/app-render/work-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/server/app-render/work-async-storage.external.js", () => require("next/dist/server/app-render/work-async-storage.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/work-unit-async-storage.external.js [external] (next/dist/server/app-render/work-unit-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/server/app-render/work-unit-async-storage.external.js", () => require("next/dist/server/app-render/work-unit-async-storage.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/action-async-storage.external.js [external] (next/dist/server/app-render/action-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/server/app-render/action-async-storage.external.js", () => require("next/dist/server/app-render/action-async-storage.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/after-task-async-storage.external.js [external] (next/dist/server/app-render/after-task-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/server/app-render/after-task-async-storage.external.js", () => require("next/dist/server/app-render/after-task-async-storage.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/dynamic-access-async-storage.external.js [external] (next/dist/server/app-render/dynamic-access-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/server/app-render/dynamic-access-async-storage.external.js", () => require("next/dist/server/app-render/dynamic-access-async-storage.external.js"));

module.exports = mod;
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__d1960788._.js.map