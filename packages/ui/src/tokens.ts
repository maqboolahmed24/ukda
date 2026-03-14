import type { ThemeMode } from "@ukde/contracts";

export type CssVariableName = `--ukde-${string}`;

export interface TypeStepToken {
  size: string;
  lineHeight: string;
  letterSpacing: string;
  weight: string;
}

export interface ThemeColorTokens {
  background: {
    canvas: string;
    frame: string;
    muted: string;
  };
  surface: {
    quiet: string;
    default: string;
    raised: string;
    overlay: string;
    emphasis: string;
  };
  border: {
    subtle: string;
    default: string;
    strong: string;
  };
  text: {
    primary: string;
    muted: string;
    subtle: string;
    onAccent: string;
  };
  accent: {
    primary: string;
    strong: string;
    soft: string;
  };
  status: {
    success: string;
    warning: string;
    danger: string;
    info: string;
  };
  environment: {
    dev: string;
    staging: string;
    prod: string;
    test: string;
  };
  accessTier: {
    controlled: string;
    safeguarded: string;
    open: string;
  };
  focus: {
    ring: string;
    contrast: string;
  };
}

export const typographyTokens = {
  family: {
    sans: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif',
    serif:
      '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif',
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
} as const satisfies {
  family: Record<string, string>;
  weight: Record<string, string>;
  scale: Record<string, TypeStepToken>;
};

export const spacingTokens = {
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
} as const;

export const radiusTokens = {
  xs: "0.16rem",
  sm: "0.26rem",
  md: "0.38rem",
  lg: "0.52rem",
  xl: "0.68rem",
  pill: "1.02rem"
} as const;

export const elevationTokens = {
  0: "none",
  1: "0 10px 28px rgba(0, 0, 0, 0.2)",
  2: "0 20px 56px rgba(0, 0, 0, 0.28)",
  3: "0 30px 80px rgba(0, 0, 0, 0.36)"
} as const;

export const motionTokens = {
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
} as const;

export const focusTokens = {
  ringWidth: "2px",
  ringOffset: "2px",
  ringSoftSpread: "4px"
} as const;

export const darkThemeColorTokens: ThemeColorTokens = {
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

export const lightThemeColorTokens: ThemeColorTokens = {
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

export const themeColorTokens = {
  dark: darkThemeColorTokens,
  light: lightThemeColorTokens
} as const satisfies Record<ThemeMode, ThemeColorTokens>;

function toThemeColorVariables(
  tokens: ThemeColorTokens
): Record<CssVariableName, string> {
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

export const themeColorVariables = {
  dark: toThemeColorVariables(darkThemeColorTokens),
  light: toThemeColorVariables(lightThemeColorTokens)
} as const satisfies Record<ThemeMode, Record<CssVariableName, string>>;

export const baseTokenVariables: Record<CssVariableName, string> = {
  "--ukde-font-sans": typographyTokens.family.sans,
  "--ukde-font-serif": typographyTokens.family.serif,
  "--ukde-font-mono": typographyTokens.family.mono,
  "--ukde-type-shell-title-size": typographyTokens.scale.shellTitle.size,
  "--ukde-type-shell-title-line-height":
    typographyTokens.scale.shellTitle.lineHeight,
  "--ukde-type-shell-title-letter-spacing":
    typographyTokens.scale.shellTitle.letterSpacing,
  "--ukde-type-shell-title-weight": typographyTokens.scale.shellTitle.weight,
  "--ukde-type-page-title-size": typographyTokens.scale.pageTitle.size,
  "--ukde-type-page-title-line-height":
    typographyTokens.scale.pageTitle.lineHeight,
  "--ukde-type-page-title-letter-spacing":
    typographyTokens.scale.pageTitle.letterSpacing,
  "--ukde-type-page-title-weight": typographyTokens.scale.pageTitle.weight,
  "--ukde-type-section-title-size": typographyTokens.scale.sectionTitle.size,
  "--ukde-type-section-title-line-height":
    typographyTokens.scale.sectionTitle.lineHeight,
  "--ukde-type-section-title-letter-spacing":
    typographyTokens.scale.sectionTitle.letterSpacing,
  "--ukde-type-section-title-weight":
    typographyTokens.scale.sectionTitle.weight,
  "--ukde-type-body-size": typographyTokens.scale.body.size,
  "--ukde-type-body-line-height": typographyTokens.scale.body.lineHeight,
  "--ukde-type-body-letter-spacing": typographyTokens.scale.body.letterSpacing,
  "--ukde-type-body-weight": typographyTokens.scale.body.weight,
  "--ukde-type-meta-size": typographyTokens.scale.metadata.size,
  "--ukde-type-meta-line-height": typographyTokens.scale.metadata.lineHeight,
  "--ukde-type-meta-letter-spacing":
    typographyTokens.scale.metadata.letterSpacing,
  "--ukde-type-meta-weight": typographyTokens.scale.metadata.weight,
  "--ukde-type-micro-size": typographyTokens.scale.microcopy.size,
  "--ukde-type-micro-line-height": typographyTokens.scale.microcopy.lineHeight,
  "--ukde-type-micro-letter-spacing":
    typographyTokens.scale.microcopy.letterSpacing,
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

export const themeTokens = {
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
} as const;
