import { describe, expect, it } from "vitest";

import { buildWorkspacePathFromSearchHit } from "./search";

describe("buildWorkspacePathFromSearchHit", () => {
  it("maps token and source provenance to workspace params", () => {
    expect(
      buildWorkspacePathFromSearchHit("project-1", {
        documentId: "doc-1",
        lineId: "line-5",
        pageNumber: 3,
        runId: "run-9",
        sourceKind: "RESCUE_CANDIDATE",
        sourceRefId: "resc-2-9",
        tokenId: "token-17"
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/transcription/workspace?lineId=line-5&page=3&runId=run-9&sourceKind=RESCUE_CANDIDATE&sourceRefId=resc-2-9&tokenId=token-17"
    );
  });

  it("omits unavailable optional provenance fields", () => {
    expect(
      buildWorkspacePathFromSearchHit("project-1", {
        documentId: "doc-1",
        lineId: null,
        pageNumber: 2,
        runId: "run-4",
        sourceKind: "LINE",
        sourceRefId: "",
        tokenId: null
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/transcription/workspace?page=2&runId=run-4&sourceKind=LINE"
    );
  });
});
