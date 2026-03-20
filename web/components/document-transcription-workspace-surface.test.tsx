// @vitest-environment jsdom

import { createElement, type ComponentProps } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type {
  CorrectDocumentTranscriptionLineResponse,
  DocumentLayoutPageOverlay,
  DocumentTranscriptionLineResult,
  DocumentTranscriptionPageResult,
  DocumentTranscriptionRun,
  DocumentTranscriptionTokenResult,
  TranscriptVariantLayer
} from "@ukde/contracts";

const routerPushMock = vi.fn();
const requestBrowserApiMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: routerPushMock
  })
}));

vi.mock("../lib/data/browser-api-client", () => ({
  requestBrowserApi: (options: unknown) => requestBrowserApiMock(options)
}));

import { DocumentTranscriptionWorkspaceSurface } from "./document-transcription-workspace-surface";

beforeAll(() => {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal("ResizeObserver", ResizeObserverMock);
});

afterAll(() => {
  vi.unstubAllGlobals();
});

afterEach(() => {
  cleanup();
  routerPushMock.mockReset();
  requestBrowserApiMock.mockReset();
});

const NOW = "2026-03-14T00:00:00Z";

const RUNS: DocumentTranscriptionRun[] = [
  {
    id: "run-1",
    projectId: "project-1",
    documentId: "doc-1",
    inputPreprocessRunId: "prep-1",
    inputLayoutRunId: "layout-1",
    inputLayoutSnapshotHash: "layout-sha-1",
    engine: "VLM_LINE_CONTEXT",
    modelId: "model-1",
    projectModelAssignmentId: null,
    promptTemplateId: null,
    promptTemplateSha256: null,
    responseSchemaVersion: 1,
    confidenceBasis: "MODEL_NATIVE",
    confidenceCalibrationVersion: "v1",
    paramsJson: {},
    pipelineVersion: "pipe-v1",
    containerDigest: "sha256:abc",
    attemptNumber: 1,
    supersedesTranscriptionRunId: null,
    supersededByTranscriptionRunId: null,
    status: "SUCCEEDED",
    createdBy: "user-1",
    createdAt: NOW,
    startedAt: NOW,
    finishedAt: NOW,
    canceledBy: null,
    canceledAt: null,
    failureReason: null,
    isActiveProjection: true,
    isSuperseded: false,
    isCurrentAttempt: true,
    isHistoricalAttempt: false
  },
  {
    id: "run-2",
    projectId: "project-1",
    documentId: "doc-1",
    inputPreprocessRunId: "prep-2",
    inputLayoutRunId: "layout-2",
    inputLayoutSnapshotHash: "layout-sha-2",
    engine: "VLM_LINE_CONTEXT",
    modelId: "model-1",
    projectModelAssignmentId: null,
    promptTemplateId: null,
    promptTemplateSha256: null,
    responseSchemaVersion: 1,
    confidenceBasis: "MODEL_NATIVE",
    confidenceCalibrationVersion: "v1",
    paramsJson: {},
    pipelineVersion: "pipe-v1",
    containerDigest: "sha256:def",
    attemptNumber: 1,
    supersedesTranscriptionRunId: null,
    supersededByTranscriptionRunId: null,
    status: "RUNNING",
    createdBy: "user-1",
    createdAt: NOW,
    startedAt: NOW,
    finishedAt: null,
    canceledBy: null,
    canceledAt: null,
    failureReason: null,
    isActiveProjection: false,
    isSuperseded: false,
    isCurrentAttempt: true,
    isHistoricalAttempt: false
  }
];

const PAGES: DocumentTranscriptionPageResult[] = [
  {
    runId: "run-1",
    pageId: "page-1",
    pageIndex: 0,
    status: "SUCCEEDED",
    pagexmlOutKey: null,
    pagexmlOutSha256: null,
    rawModelResponseKey: null,
    rawModelResponseSha256: null,
    hocrOutKey: null,
    hocrOutSha256: null,
    metricsJson: {},
    warningsJson: [],
    failureReason: null,
    createdAt: NOW,
    updatedAt: NOW
  },
  {
    runId: "run-1",
    pageId: "page-2",
    pageIndex: 1,
    status: "SUCCEEDED",
    pagexmlOutKey: null,
    pagexmlOutSha256: null,
    rawModelResponseKey: null,
    rawModelResponseSha256: null,
    hocrOutKey: null,
    hocrOutSha256: null,
    metricsJson: {},
    warningsJson: [],
    failureReason: null,
    createdAt: NOW,
    updatedAt: NOW
  }
];

const LINES: DocumentTranscriptionLineResult[] = [
  {
    runId: "run-1",
    pageId: "page-1",
    lineId: "line-1",
    textDiplomatic: "High confidence line",
    confLine: 0.96,
    confidenceBand: "HIGH",
    confidenceBasis: "MODEL_NATIVE",
    confidenceCalibrationVersion: "v1",
    alignmentJsonKey: null,
    charBoxesKey: null,
    schemaValidationStatus: "VALID",
    flagsJson: {
      sourceKind: "LINE",
      sourceRefId: "line-1"
    },
    machineOutputSha256: "sha-1",
    activeTranscriptVersionId: null,
    versionEtag: "etag-1",
    tokenAnchorStatus: "CURRENT",
    createdAt: NOW,
    updatedAt: NOW
  },
  {
    runId: "run-1",
    pageId: "page-1",
    lineId: "line-2",
    textDiplomatic: "Low confidence line one",
    confLine: 0.4,
    confidenceBand: "LOW",
    confidenceBasis: "READ_AGREEMENT",
    confidenceCalibrationVersion: "v1",
    alignmentJsonKey: null,
    charBoxesKey:
      "controlled/derived/project-1/doc-1/transcription/run-1/page/0/lines/line-2.char-boxes.json",
    schemaValidationStatus: "VALID",
    flagsJson: {
      sourceKind: "LINE",
      sourceRefId: "line-2",
      charBoxCuePreview: [
        { char: "L", confidence: 0.33 },
        { char: "o", confidence: 0.34 }
      ]
    },
    machineOutputSha256: "sha-2",
    activeTranscriptVersionId: null,
    versionEtag: "etag-2",
    tokenAnchorStatus: "CURRENT",
    createdAt: NOW,
    updatedAt: NOW
  },
  {
    runId: "run-1",
    pageId: "page-1",
    lineId: "line-3",
    textDiplomatic: "Low confidence line two",
    confLine: 0.51,
    confidenceBand: "LOW",
    confidenceBasis: "READ_AGREEMENT",
    confidenceCalibrationVersion: "v1",
    alignmentJsonKey: null,
    charBoxesKey: null,
    schemaValidationStatus: "VALID",
    flagsJson: {
      sourceKind: "LINE",
      sourceRefId: "line-3"
    },
    machineOutputSha256: "sha-3",
    activeTranscriptVersionId: null,
    versionEtag: "etag-3",
    tokenAnchorStatus: "REFRESH_REQUIRED",
    createdAt: NOW,
    updatedAt: NOW
  }
];

const TOKENS: DocumentTranscriptionTokenResult[] = [
  {
    runId: "run-1",
    pageId: "page-1",
    lineId: "line-2",
    tokenId: "tok-1",
    tokenIndex: 0,
    tokenText: "Low",
    tokenConfidence: 0.31,
    bboxJson: { x: 110, y: 135, width: 80, height: 20 },
    polygonJson: null,
    sourceKind: "LINE",
    sourceRefId: "line-2",
    projectionBasis: "ENGINE_OUTPUT",
    createdAt: NOW,
    updatedAt: NOW
  }
];

const OVERLAY: DocumentLayoutPageOverlay = {
  schemaVersion: 1,
  runId: "layout-1",
  pageId: "page-1",
  pageIndex: 0,
  page: {
    width: 1000,
    height: 1400
  },
  elements: [
    {
      id: "line-1",
      type: "LINE",
      parentId: null,
      polygon: [
        { x: 100, y: 100 },
        { x: 500, y: 100 },
        { x: 500, y: 140 },
        { x: 100, y: 140 }
      ]
    },
    {
      id: "line-2",
      type: "LINE",
      parentId: null,
      polygon: [
        { x: 100, y: 160 },
        { x: 500, y: 160 },
        { x: 500, y: 200 },
        { x: 100, y: 200 }
      ]
    },
    {
      id: "line-3",
      type: "LINE",
      parentId: null,
      polygon: [
        { x: 100, y: 220 },
        { x: 500, y: 220 },
        { x: 500, y: 260 },
        { x: 100, y: 260 }
      ]
    }
  ],
  readingOrder: [
    { fromId: "line-1", toId: "line-2" },
    { fromId: "line-2", toId: "line-3" }
  ],
  readingOrderGroups: [],
  readingOrderMeta: {
    schemaVersion: 1,
    mode: "ORDERED",
    source: "layout-overlay",
    ambiguityScore: 0,
    columnCertainty: 1,
    overlapConflictScore: 0,
    orphanLineCount: 0,
    nonTextComplexityScore: 0,
    orderWithheld: false
  }
};

const VARIANT_LAYERS: TranscriptVariantLayer[] = [
  {
    id: "variant-layer-1",
    runId: "run-1",
    pageId: "page-1",
    variantKind: "NORMALISED",
    baseTranscriptVersionId: null,
    baseVersionSetSha256: null,
    baseProjectionSha256: "projection-sha",
    variantTextKey: "controlled/derived/project-1/doc-1/transcription/run-1/page/0/normalised.txt",
    variantTextSha256: "variant-sha",
    createdBy: "user-2",
    createdAt: NOW,
    suggestions: [
      {
        id: "suggestion-1",
        variantLayerId: "variant-layer-1",
        lineId: "line-2",
        suggestionText: "low confidence line one",
        confidence: 0.92,
        status: "PENDING",
        decidedBy: null,
        decidedAt: null,
        decisionReason: null,
        metadataJson: {
          reason: "Normalisation suggestion"
        },
        createdAt: NOW,
        updatedAt: NOW
      }
    ]
  }
];

function buildCorrectionResponse(
  lineId: string,
  textDiplomatic: string,
  versionEtag: string
): CorrectDocumentTranscriptionLineResponse {
  const current = LINES.find((line) => line.lineId === lineId);
  if (!current) {
    throw new Error(`line not found: ${lineId}`);
  }
  const nextLine: DocumentTranscriptionLineResult = {
    ...current,
    textDiplomatic,
    versionEtag,
    updatedAt: NOW
  };
  return {
    runId: "run-1",
    pageId: "page-1",
    lineId,
    textChanged: textDiplomatic !== current.textDiplomatic,
    line: nextLine,
    activeVersion: {
      id: `version-${lineId}`,
      runId: "run-1",
      pageId: "page-1",
      lineId,
      baseVersionId: null,
      supersededByVersionId: null,
      versionEtag,
      textDiplomatic,
      editorUserId: "user-1",
      editReason: null,
      createdAt: NOW
    },
    outputProjection: {
      runId: "run-1",
      documentId: "doc-1",
      pageId: "page-1",
      correctedPagexmlKey: "controlled/derived/project-1/doc-1/pagexml.xml",
      correctedPagexmlSha256: "pagexml-sha",
      correctedTextSha256: "text-sha",
      sourcePagexmlSha256: "source-pagexml-sha",
      updatedAt: NOW
    },
    downstreamRedactionInvalidated: false,
    downstreamRedactionState: null,
    downstreamRedactionInvalidatedAt: null,
    downstreamRedactionInvalidatedReason: null
  };
}

function renderSurface(
  overrides: Partial<ComponentProps<typeof DocumentTranscriptionWorkspaceSurface>> = {}
) {
  const props: ComponentProps<typeof DocumentTranscriptionWorkspaceSurface> = {
    canAssistDecide: true,
    canEdit: true,
    documentId: "doc-1",
    initialLineId: "line-1",
    initialMode: "reading-order",
    initialOverlay: OVERLAY,
    initialOverlayError: null,
    initialTokenId: null,
    initialVariantLayers: VARIANT_LAYERS,
    lines: LINES,
    pageId: "page-1",
    pageNumber: 1,
    pages: PAGES,
    projectId: "project-1",
    resolvedSourceKind: "LINE",
    resolvedSourceRefId: "line-1",
    reviewConfidenceThreshold: 0.85,
    runId: "run-1",
    runs: RUNS,
    selectedRunInputLayoutRunId: "layout-1",
    selectedRunInputPreprocessRunId: "prep-1",
    tokens: TOKENS,
    variantLayersUnavailableReason: null,
    ...overrides
  };

  return render(createElement(DocumentTranscriptionWorkspaceSurface, props));
}

describe("transcription workspace interactions", () => {
  it("navigates to next low-confidence line via action button", async () => {
    const user = userEvent.setup();
    renderSurface();

    await user.click(screen.getByRole("button", { name: "Next issue (Alt+N)" }));

    expect(routerPushMock).toHaveBeenCalledTimes(1);
    const [path] = routerPushMock.mock.calls[0];
    expect(String(path)).toContain("lineId=line-2");
  });

  it("supports Alt+N keyboard navigation for low-confidence routing", () => {
    renderSurface();
    const target = screen.getByRole("button", { name: "Next issue (Alt+N)" });

    fireEvent.keyDown(target, { key: "n", altKey: true });

    expect(routerPushMock).toHaveBeenCalledTimes(1);
    const [path] = routerPushMock.mock.calls[0];
    expect(String(path)).toContain("lineId=line-2");
  });

  it("switches mode through URL navigation", async () => {
    const user = userEvent.setup();
    renderSurface();

    await user.click(screen.getByRole("button", { name: "Switch mode (As on page)" }));

    expect(routerPushMock).toHaveBeenCalledTimes(1);
    const [path] = routerPushMock.mock.calls[0];
    expect(String(path)).toContain("mode=as-on-page");
  });

  it("supports Enter save-and-next for editable diplomatic text", async () => {
    requestBrowserApiMock.mockImplementation(
      async (options: { body?: string; method?: string }) => {
        if (options.method === "PATCH") {
          const payload = JSON.parse(options.body ?? "{}");
          return {
            ok: true,
            status: 200,
            data: buildCorrectionResponse("line-2", payload.textDiplomatic, "etag-2b")
          };
        }
        return {
          ok: true,
          status: 200,
          data: {
            items: []
          }
        };
      }
    );

    const user = userEvent.setup();
    renderSurface({ initialLineId: "line-2" });

    const lineDraft = screen.getByDisplayValue("Low confidence line one");
    await user.clear(lineDraft);
    await user.type(lineDraft, "Low confidence line one edited");
    fireEvent.keyDown(lineDraft, { key: "Enter" });

    await waitFor(() => {
      expect(
        requestBrowserApiMock.mock.calls.some(
          ([options]) => (options as { method?: string }).method === "PATCH"
        )
      ).toBe(true);
    });

    await waitFor(() => {
      expect(
        routerPushMock.mock.calls.some(([path]) => String(path).includes("lineId=line-3"))
      ).toBe(true);
    });
  });

  it("surfaces conflict state and reload action on stale version", async () => {
    requestBrowserApiMock.mockImplementation(
      async (options: { method?: string; path: string }) => {
        if (options.method === "PATCH") {
          return {
            ok: false,
            status: 409,
            detail: "Version etag is stale."
          };
        }
        if (options.method === "GET" && options.path.includes("/lines?")) {
          return {
            ok: true,
            status: 200,
            data: {
              items: LINES
            }
          };
        }
        if (options.method === "GET" && options.path.endsWith("/tokens")) {
          return {
            ok: true,
            status: 200,
            data: {
              items: TOKENS
            }
          };
        }
        return {
          ok: true,
          status: 200,
          data: {}
        };
      }
    );

    const user = userEvent.setup();
    renderSurface();

    const lineDraft = screen.getByDisplayValue("High confidence line");
    await user.clear(lineDraft);
    await user.type(lineDraft, "High confidence line revised");
    await user.click(screen.getByRole("button", { name: "Save line (Ctrl/Cmd+S)" }));

    expect(await screen.findByText("Edit conflict detected")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reload latest line state" })).toBeTruthy();

    await waitFor(() => {
      expect(
        requestBrowserApiMock.mock.calls.some(
          ([options]) =>
            (options as { method?: string; path?: string }).method === "GET" &&
            String((options as { path?: string }).path).includes("/lines?")
        )
      ).toBe(true);
      expect(
        requestBrowserApiMock.mock.calls.some(
          ([options]) =>
            (options as { method?: string; path?: string }).method === "GET" &&
            String((options as { path?: string }).path).endsWith("/tokens")
        )
      ).toBe(true);
    });
  });

  it("shows selected-line confidence inspector and char cues", async () => {
    const user = userEvent.setup();
    renderSurface();

    await user.click(screen.getByRole("button", { name: "line-2" }));
    await user.click(screen.getByRole("tab", { name: "Insights" }));

    expect(screen.getByText("Selected line confidence")).toBeTruthy();
    expect(screen.getByText("READ_AGREEMENT")).toBeTruthy();
    expect(screen.getByLabelText("Character confidence cues")).toBeTruthy();
  });
});
