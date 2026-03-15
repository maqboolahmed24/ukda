import { describe, expect, it } from "vitest";
import type { ProjectSearchHit } from "@ukde/contracts";

import {
  buildSearchReturnQuery,
  buildSearchSnippetPreview,
  describeSearchHitProvenance,
  groupSearchHitsByDocument,
  resolveMatchSpanRange
} from "./search-ui";

function fixtureHit(overrides: Partial<ProjectSearchHit> = {}): ProjectSearchHit {
  return {
    searchDocumentId: "search-hit-1",
    searchIndexId: "search-index-active",
    documentId: "doc-1",
    runId: "run-1",
    pageId: "page-1",
    pageNumber: 1,
    lineId: "line-1",
    tokenId: "token-1",
    sourceKind: "LINE",
    sourceRefId: "line-1",
    matchSpanJson: null,
    tokenGeometryJson: null,
    searchText: "John Smith attended parish service",
    searchMetadataJson: {},
    ...overrides
  };
}

describe("resolveMatchSpanRange", () => {
  it("resolves direct start/end ranges", () => {
    expect(resolveMatchSpanRange({ start: 5, end: 10 }, 32)).toEqual({
      start: 5,
      end: 10
    });
  });

  it("resolves start + length with bounds clamping", () => {
    expect(resolveMatchSpanRange({ offset: 10, length: 9 }, 14)).toEqual({
      start: 10,
      end: 14
    });
  });
});

describe("buildSearchSnippetPreview", () => {
  it("highlights exact fallback span offsets when provided", () => {
    const preview = buildSearchSnippetPreview(
      fixtureHit({
        tokenId: null,
        sourceKind: "PAGE_WINDOW",
        sourceRefId: "window-1",
        matchSpanJson: { start: 5, end: 10 },
        searchText: "Alpha Beta Gamma Delta"
      }),
      "beta"
    );
    expect(preview.highlightKind).toBe("SPAN");
    expect(preview.segments).toEqual([
      { highlighted: false, text: "Alpha" },
      { highlighted: true, text: " Beta" },
      { highlighted: false, text: " Gamma Delta" }
    ]);
  });

  it("falls back to query highlight when no explicit span exists", () => {
    const preview = buildSearchSnippetPreview(
      fixtureHit({
        matchSpanJson: null,
        searchText: "John Smith attended parish service"
      }),
      "smith"
    );
    expect(preview.highlightKind).toBe("QUERY");
    expect(preview.segments).toEqual([
      { highlighted: false, text: "John " },
      { highlighted: true, text: "Smith" },
      { highlighted: false, text: " attended parish service" }
    ]);
  });
});

describe("search grouping and return query", () => {
  it("groups hits by document while preserving first-seen order", () => {
    const grouped = groupSearchHitsByDocument([
      fixtureHit({ searchDocumentId: "h1", documentId: "doc-b" }),
      fixtureHit({ searchDocumentId: "h2", documentId: "doc-a" }),
      fixtureHit({ searchDocumentId: "h3", documentId: "doc-b" })
    ]);
    expect(grouped.map((group) => group.documentId)).toEqual(["doc-b", "doc-a"]);
    expect(grouped[0].items.map((item) => item.searchDocumentId)).toEqual(["h1", "h3"]);
    expect(grouped[1].items.map((item) => item.searchDocumentId)).toEqual(["h2"]);
  });

  it("builds deterministic return query with optional selected hit", () => {
    expect(
      buildSearchReturnQuery({
        q: "  smith ",
        documentId: "doc-1",
        runId: "run-3",
        pageNumber: 2,
        cursor: 25,
        selectedHitId: "hit-9"
      })
    ).toBe(
      "q=smith&documentId=doc-1&runId=run-3&pageNumber=2&cursor=25&selectedHit=hit-9"
    );
  });
});

describe("provenance description", () => {
  it("describes token and fallback provenance correctly", () => {
    expect(describeSearchHitProvenance(fixtureHit({ tokenId: "tok-1" }))).toBe(
      "Token-anchored hit"
    );
    expect(
      describeSearchHitProvenance(
        fixtureHit({
          tokenId: null,
          sourceKind: "RESCUE_CANDIDATE",
          sourceRefId: "resc-1"
        })
      )
    ).toBe("Rescue candidate source");
    expect(
      describeSearchHitProvenance(
        fixtureHit({
          tokenId: null,
          sourceKind: "LINE",
          matchSpanJson: { start: 1, end: 3 }
        })
      )
    ).toBe("Exact fallback span");
  });
});
