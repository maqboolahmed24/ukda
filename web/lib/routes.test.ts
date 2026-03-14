import { describe, expect, test } from "vitest";

import {
  approvedModelsPath,
  projectModelAssignmentDatasetsPath,
  projectModelAssignmentPath,
  projectModelAssignmentsPath,
  projectDocumentLayoutPath,
  projectDocumentLayoutRunPath,
  projectDocumentLayoutWorkspacePath,
  projectDocumentPreprocessingComparePath,
  projectDocumentPreprocessingPath,
  projectDocumentPreprocessingQualityPath,
  projectDocumentPreprocessingRunPath,
  projectDocumentTranscriptionComparePath,
  projectDocumentTranscriptionPath,
  projectDocumentTranscriptionRunPath,
  projectDocumentTranscriptionWorkspacePath,
  projectDocumentIngestStatusPath,
  projectDocumentViewerPath
} from "./routes";

describe("projectDocumentViewerPath", () => {
  test("builds canonical page-only viewer paths by default", () => {
    expect(projectDocumentViewerPath("project-1", "doc-1", 4)).toBe(
      "/projects/project-1/documents/doc-1/viewer?page=4"
    );
    expect(projectDocumentViewerPath("project-1", "doc-1", 4, { zoom: 100 })).toBe(
      "/projects/project-1/documents/doc-1/viewer?page=4"
    );
  });

  test("includes bounded non-default zoom values", () => {
    expect(projectDocumentViewerPath("project-1", "doc-1", 4, { zoom: 125 })).toBe(
      "/projects/project-1/documents/doc-1/viewer?page=4&zoom=125"
    );
    expect(projectDocumentViewerPath("project-1", "doc-1", 4, { zoom: 999 })).toBe(
      "/projects/project-1/documents/doc-1/viewer?page=4&zoom=400"
    );
    expect(projectDocumentViewerPath("project-1", "doc-1", 4, { zoom: 3 })).toBe(
      "/projects/project-1/documents/doc-1/viewer?page=4&zoom=25"
    );
  });

  test("includes compare-mode context when provided", () => {
    expect(
      projectDocumentViewerPath("project-1", "doc-1", 4, {
        mode: "compare",
        comparePair: "original_binary",
        runId: "run-2"
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/viewer?comparePair=original_binary&mode=compare&page=4&runId=run-2"
    );
  });
});

describe("projectDocumentIngestStatusPath", () => {
  test("builds ingest-status paths without viewer context by default", () => {
    expect(projectDocumentIngestStatusPath("project-1", "doc-1")).toBe(
      "/projects/project-1/documents/doc-1/ingest-status"
    );
  });

  test("includes bounded optional viewer context when provided", () => {
    expect(
      projectDocumentIngestStatusPath("project-1", "doc-1", {
        page: 4,
        zoom: 135
      })
    ).toBe("/projects/project-1/documents/doc-1/ingest-status?page=4&zoom=135");
    expect(
      projectDocumentIngestStatusPath("project-1", "doc-1", {
        page: 0,
        zoom: 999
      })
    ).toBe("/projects/project-1/documents/doc-1/ingest-status?page=1&zoom=400");
    expect(
      projectDocumentIngestStatusPath("project-1", "doc-1", {
        page: 3,
        zoom: 100
      })
    ).toBe("/projects/project-1/documents/doc-1/ingest-status?page=3");
  });
});

describe("projectDocumentPreprocessingPath", () => {
  test("builds canonical preprocessing paths with optional tabs", () => {
    expect(projectDocumentPreprocessingPath("project-1", "doc-1")).toBe(
      "/projects/project-1/documents/doc-1/preprocessing"
    );
    expect(
      projectDocumentPreprocessingPath("project-1", "doc-1", {
        tab: "runs"
      })
    ).toBe("/projects/project-1/documents/doc-1/preprocessing?tab=runs");
  });
});

describe("projectDocumentPreprocessingQualityPath", () => {
  test("encodes optional filters", () => {
    expect(
      projectDocumentPreprocessingQualityPath("project-1", "doc-1", {
        blurMax: 0.24,
        compareBaseRunId: "run-1",
        failedOnly: true,
        skewMin: 0.2,
        skewMax: 1.8,
        runId: "run-2",
        status: "FAILED",
        warning: "LOW_DPI",
        cursor: 20,
        pageSize: 25
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/preprocessing/quality?blurMax=0.24&compareBaseRunId=run-1&cursor=20&failedOnly=1&pageSize=25&runId=run-2&skewMax=1.8&skewMin=0.2&status=FAILED&warning=LOW_DPI"
    );
  });
});

describe("projectDocumentPreprocessingRunPath", () => {
  test("builds preprocessing run detail paths", () => {
    expect(
      projectDocumentPreprocessingRunPath("project-1", "doc-1", "run-2")
    ).toBe("/projects/project-1/documents/doc-1/preprocessing/runs/run-2");
  });
});

describe("projectDocumentPreprocessingComparePath", () => {
  test("builds compare links with required run ids", () => {
    expect(
      projectDocumentPreprocessingComparePath(
        "project-1",
        "doc-1",
        "run-a",
        "run-b"
      )
    ).toBe(
      "/projects/project-1/documents/doc-1/preprocessing/compare?baseRunId=run-a&candidateRunId=run-b"
    );
  });

  test("supports single-run compare state with viewer return context", () => {
    expect(
      projectDocumentPreprocessingComparePath("project-1", "doc-1", null, "run-b", {
        page: 2,
        viewerComparePair: "gray_binary",
        viewerMode: "compare",
        viewerRunId: "run-b"
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/preprocessing/compare?candidateRunId=run-b&page=2&viewerComparePair=gray_binary&viewerMode=compare&viewerRunId=run-b"
    );
  });
});

describe("projectDocumentLayoutPath", () => {
  test("builds canonical layout route with optional tab and run selection", () => {
    expect(projectDocumentLayoutPath("project-1", "doc-1")).toBe(
      "/projects/project-1/documents/doc-1/layout"
    );
    expect(
      projectDocumentLayoutPath("project-1", "doc-1", {
        tab: "triage",
        runId: "layout-run-2"
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/layout?runId=layout-run-2&tab=triage"
    );
  });
});

describe("projectDocumentLayoutRunPath", () => {
  test("builds layout run detail paths", () => {
    expect(projectDocumentLayoutRunPath("project-1", "doc-1", "layout-run-2")).toBe(
      "/projects/project-1/documents/doc-1/layout/runs/layout-run-2"
    );
  });
});

describe("projectDocumentLayoutWorkspacePath", () => {
  test("builds workspace paths with bounded query state", () => {
    expect(projectDocumentLayoutWorkspacePath("project-1", "doc-1")).toBe(
      "/projects/project-1/documents/doc-1/layout/workspace"
    );
    expect(
      projectDocumentLayoutWorkspacePath("project-1", "doc-1", {
        page: 2,
        runId: "layout-run-2"
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/layout/workspace?page=2&runId=layout-run-2"
    );
    expect(
      projectDocumentLayoutWorkspacePath("project-1", "doc-1", {
        page: 0,
        runId: "layout-run-2"
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/layout/workspace?page=1&runId=layout-run-2"
    );
  });
});

describe("projectDocumentTranscriptionPath", () => {
  test("builds canonical transcription route with optional tab and run selection", () => {
    expect(projectDocumentTranscriptionPath("project-1", "doc-1")).toBe(
      "/projects/project-1/documents/doc-1/transcription"
    );
    expect(
      projectDocumentTranscriptionPath("project-1", "doc-1", {
        tab: "triage",
        runId: "transcription-run-2"
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/transcription?runId=transcription-run-2&tab=triage"
    );
  });
});

describe("projectDocumentTranscriptionRunPath", () => {
  test("builds transcription run detail paths", () => {
    expect(
      projectDocumentTranscriptionRunPath(
        "project-1",
        "doc-1",
        "transcription-run-2"
      )
    ).toBe("/projects/project-1/documents/doc-1/transcription/runs/transcription-run-2");
  });
});

describe("projectDocumentTranscriptionWorkspacePath", () => {
  test("builds deep-link-safe workspace paths with full query context", () => {
    expect(projectDocumentTranscriptionWorkspacePath("project-1", "doc-1")).toBe(
      "/projects/project-1/documents/doc-1/transcription/workspace"
    );
    expect(
      projectDocumentTranscriptionWorkspacePath("project-1", "doc-1", {
        lineId: "line-3",
        mode: "reading-order",
        page: 2,
        runId: "transcription-run-2",
        sourceKind: "RESCUE_CANDIDATE",
        sourceRefId: "resc-2-9",
        tokenId: "token-17"
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/transcription/workspace?lineId=line-3&mode=reading-order&page=2&runId=transcription-run-2&sourceKind=RESCUE_CANDIDATE&sourceRefId=resc-2-9&tokenId=token-17"
    );
    expect(
      projectDocumentTranscriptionWorkspacePath("project-1", "doc-1", {
        page: 0,
        runId: "transcription-run-2"
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/transcription/workspace?page=1&runId=transcription-run-2"
    );
    expect(
      projectDocumentTranscriptionWorkspacePath("project-1", "doc-1", {
        mode: "as-on-page",
        page: 3,
        runId: "transcription-run-2"
      })
    ).toBe(
      "/projects/project-1/documents/doc-1/transcription/workspace?mode=as-on-page&page=3&runId=transcription-run-2"
    );
  });
});

describe("projectDocumentTranscriptionComparePath", () => {
  test("builds deep-link-safe compare paths with explicit base/candidate context", () => {
    expect(projectDocumentTranscriptionComparePath("project-1", "doc-1")).toBe(
      "/projects/project-1/documents/doc-1/transcription/compare"
    );
    expect(
      projectDocumentTranscriptionComparePath(
        "project-1",
        "doc-1",
        "transcription-run-1",
        "transcription-run-2",
        {
          lineId: "line-3",
          page: 2,
          tokenId: "token-17"
        }
      )
    ).toBe(
      "/projects/project-1/documents/doc-1/transcription/compare?baseRunId=transcription-run-1&candidateRunId=transcription-run-2&lineId=line-3&page=2&tokenId=token-17"
    );
  });
});

describe("model assignment route helpers", () => {
  test("exposes approved-models root path", () => {
    expect(approvedModelsPath).toBe("/approved-models");
  });

  test("builds project model-assignment route family", () => {
    expect(projectModelAssignmentsPath("project-1")).toBe(
      "/projects/project-1/model-assignments"
    );
    expect(projectModelAssignmentPath("project-1", "assignment-1")).toBe(
      "/projects/project-1/model-assignments/assignment-1"
    );
    expect(projectModelAssignmentDatasetsPath("project-1", "assignment-1")).toBe(
      "/projects/project-1/model-assignments/assignment-1/datasets"
    );
  });
});
