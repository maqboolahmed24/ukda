import { describe, expect, test } from "vitest";

import {
  normalizeCursorParam,
  normalizeOptionalDateParam,
  normalizeOptionalEnumParam,
  normalizePanelSectionParam,
  normalizeOptionalTextParam,
  normalizeViewerComparePairParam,
  normalizeViewerModeParam,
  normalizeViewerPageParam,
  normalizeViewerRunIdParam,
  normalizeViewerUrlState,
  normalizeViewerZoomParam
} from "./url-state";

describe("normalizeViewerPageParam", () => {
  test("accepts canonical 1-based values", () => {
    const result = normalizeViewerPageParam("12");
    expect(result.value).toBe(12);
    expect(result.canonicalValue).toBe("12");
    expect(result.shouldRedirect).toBe(false);
  });

  test("falls back to page 1 for missing or invalid values", () => {
    expect(normalizeViewerPageParam(undefined).value).toBe(1);
    expect(normalizeViewerPageParam("0").value).toBe(1);
    expect(normalizeViewerPageParam("-2").value).toBe(1);
    expect(normalizeViewerPageParam("abc").value).toBe(1);
  });

  test("marks non-canonical values for redirect", () => {
    expect(normalizeViewerPageParam(undefined).shouldRedirect).toBe(true);
    expect(normalizeViewerPageParam("0007").shouldRedirect).toBe(true);
  });
});

describe("normalizeViewerZoomParam", () => {
  test("keeps missing zoom absent while returning default value", () => {
    const result = normalizeViewerZoomParam(undefined);
    expect(result.value).toBe(100);
    expect(result.canonicalValue).toBeUndefined();
    expect(result.shouldRedirect).toBe(false);
  });

  test("accepts bounded canonical numeric zoom", () => {
    const result = normalizeViewerZoomParam("135");
    expect(result.value).toBe(135);
    expect(result.canonicalValue).toBe("135");
    expect(result.shouldRedirect).toBe(false);
  });

  test("normalizes invalid or non-canonical zoom values", () => {
    expect(normalizeViewerZoomParam("999").value).toBe(400);
    expect(normalizeViewerZoomParam("999").shouldRedirect).toBe(true);
    expect(normalizeViewerZoomParam("00050").canonicalValue).toBe("50");
    expect(normalizeViewerZoomParam("abc").value).toBe(100);
    expect(normalizeViewerZoomParam("abc").shouldRedirect).toBe(true);
    expect(normalizeViewerZoomParam("100").canonicalValue).toBeUndefined();
    expect(normalizeViewerZoomParam("100").shouldRedirect).toBe(true);
  });
});

describe("normalizeViewerUrlState", () => {
  test("normalizes page + zoom and reports redirect when canonicalization is needed", () => {
    expect(normalizeViewerUrlState({ page: undefined, zoom: undefined })).toEqual({
      comparePair: "original_gray",
      mode: "original",
      panel: "context",
      page: 1,
      runId: undefined,
      zoom: 100,
      shouldRedirect: true
    });
    expect(normalizeViewerUrlState({ page: "0002", zoom: "100" })).toEqual({
      comparePair: "original_gray",
      mode: "original",
      panel: "context",
      page: 2,
      runId: undefined,
      zoom: 100,
      shouldRedirect: true
    });
  });

  test("keeps canonical viewer state unchanged", () => {
    expect(
      normalizeViewerUrlState({
        page: "3",
        zoom: "125",
        mode: "compare",
        comparePair: "gray_binary",
        panel: "insights",
        runId: "run-2"
      })
    ).toEqual({
      comparePair: "gray_binary",
      mode: "compare",
      panel: "insights",
      page: 3,
      runId: "run-2",
      zoom: 125,
      shouldRedirect: false
    });
  });
});

describe("normalizeViewerModeParam", () => {
  test("normalizes mode and strips original from URL ownership", () => {
    expect(normalizeViewerModeParam(undefined)).toEqual({
      value: "original",
      canonicalValue: undefined,
      shouldRedirect: false
    });
    expect(normalizeViewerModeParam("ORIGINAL")).toEqual({
      value: "original",
      canonicalValue: undefined,
      shouldRedirect: true
    });
    expect(normalizeViewerModeParam("compare")).toEqual({
      value: "compare",
      canonicalValue: "compare",
      shouldRedirect: false
    });
  });
});

describe("normalizeViewerRunIdParam", () => {
  test("trims run ids and drops empty values", () => {
    expect(normalizeViewerRunIdParam(undefined)).toEqual({
      value: undefined,
      canonicalValue: undefined,
      shouldRedirect: false
    });
    expect(normalizeViewerRunIdParam("   ")).toEqual({
      value: undefined,
      canonicalValue: undefined,
      shouldRedirect: true
    });
    expect(normalizeViewerRunIdParam(" run-2 ")).toEqual({
      value: "run-2",
      canonicalValue: "run-2",
      shouldRedirect: true
    });
  });
});

describe("normalizeViewerComparePairParam", () => {
  test("normalizes compare pair and strips default pair from URL ownership", () => {
    expect(normalizeViewerComparePairParam(undefined)).toEqual({
      value: "original_gray",
      canonicalValue: undefined,
      shouldRedirect: false
    });
    expect(normalizeViewerComparePairParam("original_gray")).toEqual({
      value: "original_gray",
      canonicalValue: undefined,
      shouldRedirect: true
    });
    expect(normalizeViewerComparePairParam("ORIGINAL-BINARY")).toEqual({
      value: "original_binary",
      canonicalValue: "original_binary",
      shouldRedirect: true
    });
  });
});

describe("normalizePanelSectionParam", () => {
  test("normalizes panel sections and strips default context", () => {
    expect(normalizePanelSectionParam(undefined)).toEqual({
      value: undefined,
      canonicalValue: undefined,
      shouldRedirect: false
    });
    expect(normalizePanelSectionParam("context")).toEqual({
      value: "context",
      canonicalValue: undefined,
      shouldRedirect: true
    });
    expect(normalizePanelSectionParam("INSIGHTS")).toEqual({
      value: "insights",
      canonicalValue: "insights",
      shouldRedirect: true
    });
    expect(normalizePanelSectionParam("invalid")).toEqual({
      value: undefined,
      canonicalValue: undefined,
      shouldRedirect: true
    });
  });
});

describe("normalizeCursorParam", () => {
  test("returns non-negative integers with safe fallback", () => {
    expect(normalizeCursorParam(undefined)).toBe(0);
    expect(normalizeCursorParam("0")).toBe(0);
    expect(normalizeCursorParam("52")).toBe(52);
    expect(normalizeCursorParam("-1")).toBe(0);
    expect(normalizeCursorParam("NaN")).toBe(0);
  });
});

describe("normalizeOptionalTextParam", () => {
  test("trims and drops empty values", () => {
    expect(normalizeOptionalTextParam(undefined)).toBeUndefined();
    expect(normalizeOptionalTextParam("")).toBeUndefined();
    expect(normalizeOptionalTextParam("   ")).toBeUndefined();
    expect(normalizeOptionalTextParam("  keep  ")).toBe("keep");
  });
});

describe("normalizeOptionalDateParam", () => {
  test("keeps canonical YYYY-MM-DD values", () => {
    expect(normalizeOptionalDateParam("2026-03-13")).toBe("2026-03-13");
  });

  test("drops missing, empty, and malformed values", () => {
    expect(normalizeOptionalDateParam(undefined)).toBeUndefined();
    expect(normalizeOptionalDateParam("")).toBeUndefined();
    expect(normalizeOptionalDateParam("  ")).toBeUndefined();
    expect(normalizeOptionalDateParam("13-03-2026")).toBeUndefined();
    expect(normalizeOptionalDateParam("2026-02-30")).toBeUndefined();
    expect(normalizeOptionalDateParam("2026-03-13T10:00:00Z")).toBeUndefined();
  });
});

describe("normalizeOptionalEnumParam", () => {
  test("keeps only allowed values", () => {
    const allowed = ["OPEN", "OK", "UNAVAILABLE"] as const;
    expect(normalizeOptionalEnumParam("OK", allowed)).toBe("OK");
    expect(normalizeOptionalEnumParam("MISSING", allowed)).toBeUndefined();
    expect(normalizeOptionalEnumParam(undefined, allowed)).toBeUndefined();
  });
});
