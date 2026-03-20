import { describe, expect, test } from "vitest";

import {
  buildAdaptivePanelStorageKey,
  normalizePanelSectionParam,
  resolveSidePanelLayoutState
} from "./adaptive-side-panel";

describe("normalizePanelSectionParam", () => {
  test("keeps missing panel section absent", () => {
    expect(normalizePanelSectionParam(undefined)).toEqual({
      value: undefined,
      canonicalValue: undefined,
      shouldRedirect: false
    });
  });

  test("normalizes invalid and non-canonical sections", () => {
    expect(normalizePanelSectionParam("unknown")).toEqual({
      value: undefined,
      canonicalValue: undefined,
      shouldRedirect: true
    });
    expect(normalizePanelSectionParam("INSIGHTS")).toEqual({
      value: "insights",
      canonicalValue: "insights",
      shouldRedirect: true
    });
  });

  test("treats context as default and strips it from canonical URL ownership", () => {
    expect(normalizePanelSectionParam("context")).toEqual({
      value: "context",
      canonicalValue: undefined,
      shouldRedirect: true
    });
  });
});

describe("resolveSidePanelLayoutState", () => {
  test("renders asides only for expanded and balanced shell states", () => {
    expect(resolveSidePanelLayoutState("Expanded")).toEqual({
      showAside: true,
      showDrawerToggle: false
    });
    expect(resolveSidePanelLayoutState("Balanced")).toEqual({
      showAside: true,
      showDrawerToggle: false
    });
    expect(resolveSidePanelLayoutState("Compact")).toEqual({
      showAside: false,
      showDrawerToggle: true
    });
    expect(resolveSidePanelLayoutState("Focus")).toEqual({
      showAside: false,
      showDrawerToggle: true
    });
  });
});

describe("buildAdaptivePanelStorageKey", () => {
  test("scopes keys by surface, project, and optional document", () => {
    expect(
      buildAdaptivePanelStorageKey({
        surface: "viewer-inspector",
        projectId: "project-1",
        documentId: "doc-1"
      })
    ).toBe("ukde.panel.v2:viewer-inspector:project-1:doc-1");
    expect(
      buildAdaptivePanelStorageKey({
        surface: "shell-context",
        projectId: null
      })
    ).toBe("ukde.panel.v2:shell-context:global");
  });
});
