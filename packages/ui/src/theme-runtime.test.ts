import { describe, expect, it } from "vitest";

import { getThemeMediaQueries, syncThemeRuntime } from "./theme";

function createWindowWithMedia(matches: Record<string, boolean>): Window {
  return {
    matchMedia: (query: string) =>
      ({
        dispatchEvent: () => true,
        addEventListener: () => undefined,
        addListener: () => undefined,
        matches: matches[query] ?? false,
        media: query,
        onchange: null,
        removeEventListener: () => undefined,
        removeListener: () => undefined
      }) as unknown as MediaQueryList
  } as unknown as Window;
}

function createDocumentWithDataset(): Document {
  return {
    documentElement: {
      dataset: {} as DOMStringMap
    } as HTMLElement
  } as Document;
}

describe("theme runtime accessibility preferences", () => {
  it("syncs reduced-motion and reduced-transparency preferences", () => {
    const queries = getThemeMediaQueries();
    const targetWindow = createWindowWithMedia({
      [queries.forcedColorsActive]: false,
      [queries.prefersContrastMore]: true,
      [queries.prefersDark]: true,
      [queries.reducedMotion]: true,
      [queries.reducedTransparency]: true
    });
    const targetDocument = createDocumentWithDataset();

    const runtime = syncThemeRuntime("system", targetWindow, targetDocument);

    expect(runtime.mode).toBe("dark");
    expect(runtime.motion).toBe("reduce");
    expect(runtime.reducedTransparency).toBe("reduce");
    expect(runtime.contrast).toBe("more");
    expect(targetDocument.documentElement.dataset.themeMotion).toBe("reduce");
    expect(targetDocument.documentElement.dataset.themeTransparency).toBe(
      "reduce"
    );
    expect(targetDocument.documentElement.dataset.themeContrast).toBe("more");
  });

  it("maps forced-colors preference to forced contrast mode", () => {
    const queries = getThemeMediaQueries();
    const targetWindow = createWindowWithMedia({
      [queries.forcedColorsActive]: true,
      [queries.prefersContrastMore]: true,
      [queries.prefersDark]: false,
      [queries.reducedMotion]: false,
      [queries.reducedTransparency]: false
    });
    const targetDocument = createDocumentWithDataset();

    const runtime = syncThemeRuntime("light", targetWindow, targetDocument);

    expect(runtime.mode).toBe("light");
    expect(runtime.contrast).toBe("forced");
    expect(targetDocument.documentElement.dataset.themeForcedColors).toBe(
      "active"
    );
    expect(targetDocument.documentElement.dataset.themeContrast).toBe("forced");
  });
});
