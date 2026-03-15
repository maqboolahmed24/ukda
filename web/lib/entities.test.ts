import { describe, expect, it } from "vitest";

import { buildWorkspacePathFromEntityOccurrence } from "./entities";

describe("buildWorkspacePathFromEntityOccurrence", () => {
  it("maps token and source provenance to transcription workspace params", () => {
    expect(
      buildWorkspacePathFromEntityOccurrence("project-1", {
        documentId: "doc-1",
        lineId: "line-9",
        pageNumber: 4,
        runId: "run-2",
        sourceKind: "PAGE_WINDOW",
        sourceRefId: "window-4-2",
        tokenId: "token-7"
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/transcription/workspace?lineId=line-9&page=4&runId=run-2&sourceKind=PAGE_WINDOW&sourceRefId=window-4-2&tokenId=token-7"
    );
  });

  it("omits unavailable optional provenance fields", () => {
    expect(
      buildWorkspacePathFromEntityOccurrence("project-1", {
        documentId: "doc-1",
        lineId: null,
        pageNumber: 2,
        runId: "run-2",
        sourceKind: "LINE",
        sourceRefId: "",
        tokenId: null
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/transcription/workspace?page=2&runId=run-2&sourceKind=LINE"
    );
  });
});
