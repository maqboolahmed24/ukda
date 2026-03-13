import { describe, expect, it } from "vitest";

import {
  accessTierLabels,
  baseTokenVariables,
  darkThemeColorTokens,
  designPillars,
  environmentLabels,
  lightThemeColorTokens,
  motionTokens,
  projectRoleLabels,
  readThemeMediaState,
  resolveThemeRuntime,
  resolveThemeMode,
  spacingTokens,
  shellStateNotes,
  themePreferenceOptions,
  themeTokens,
  typographyTokens
} from "./index";

describe("@ukde/ui", () => {
  it("keeps dark-first tokens available", () => {
    expect(themeTokens.colors.background).toBe(darkThemeColorTokens.background.canvas);
    expect(themeTokens.colors.accent).toBe(darkThemeColorTokens.accent.primary);
    expect(lightThemeColorTokens.surface.overlay).toBe("rgba(255, 255, 255, 0.97)");
  });

  it("documents each shell state", () => {
    expect(Object.keys(shellStateNotes)).toEqual([
      "Expanded",
      "Balanced",
      "Compact",
      "Focus"
    ]);
  });

  it("retains the design pillars for the shell", () => {
    expect(designPillars).toContain(
      "Bounded work regions instead of page sprawl"
    );
  });

  it("exposes deterministic role and badge labels", () => {
    expect(accessTierLabels.CONTROLLED).toBe("Controlled");
    expect(projectRoleLabels.PROJECT_LEAD).toBe("Project lead");
    expect(environmentLabels.dev).toBe("Development");
  });

  it("resolves theme preferences deterministically", () => {
    expect(themePreferenceOptions).toEqual(["system", "dark", "light"]);
    expect(resolveThemeMode("dark", false)).toBe("dark");
    expect(resolveThemeMode("light", true)).toBe("light");
    expect(resolveThemeMode("system", true)).toBe("dark");
  });

  it("builds a complete token baseline for CSS variables", () => {
    expect(baseTokenVariables["--ukde-font-sans"]).toBe(
      typographyTokens.family.sans
    );
    expect(baseTokenVariables["--ukde-space-4"]).toBe(spacingTokens[4]);
    expect(baseTokenVariables["--ukde-motion-duration-standard"]).toBe(
      motionTokens.duration.standard
    );
  });

  it("derives runtime theme states from media preferences", () => {
    const runtime = resolveThemeRuntime("system", {
      prefersDark: true,
      prefersContrastMore: false,
      forcedColorsActive: false,
      reducedMotion: true,
      reducedTransparency: "reduce"
    });
    expect(runtime.mode).toBe("dark");
    expect(runtime.motion).toBe("reduce");
    expect(runtime.reducedTransparency).toBe("reduce");
  });

  it("returns a safe media-state default in non-browser tests", () => {
    const state = readThemeMediaState({
      matchMedia: undefined
    } as unknown as Window);
    expect(state.reducedTransparency).toBe("unsupported");
    expect(state.prefersDark).toBe(false);
  });
});
