// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import type { DocumentPipelineStatusResponse } from "../lib/pipeline-status";

const requestBrowserApiMock = vi.fn();

vi.mock("../lib/data/browser-api-client", () => ({
  requestBrowserApi: (options: unknown) => requestBrowserApiMock(options)
}));

import { DocumentPipelineLiveStatus } from "./document-pipeline-live-status";

function mockMatchMedia(matches: boolean): void {
  const mediaQueryList = {
    matches,
    media: "(prefers-reduced-motion: reduce)",
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn()
  };
  vi.stubGlobal("matchMedia", vi.fn(() => mediaQueryList));
}

function buildSnapshot(
  overrides: Partial<DocumentPipelineStatusResponse> = {}
): DocumentPipelineStatusResponse {
  return {
    phases: [
      {
        phaseId: "INGEST",
        status: "RUNNING",
        percent: 50,
        completedUnits: 2,
        totalUnits: 4,
        label: "Ingest",
        detail: "Extraction running."
      },
      {
        phaseId: "PREPROCESS",
        status: "SUCCEEDED",
        percent: 100,
        completedUnits: 2,
        totalUnits: 2,
        label: "Preprocess",
        detail: "Preprocess complete."
      },
      {
        phaseId: "LAYOUT",
        status: "SUCCEEDED",
        percent: 100,
        completedUnits: 2,
        totalUnits: 2,
        label: "Layout",
        detail: "Layout complete."
      },
      {
        phaseId: "TRANSCRIPTION",
        status: "RUNNING",
        percent: null,
        completedUnits: 1,
        totalUnits: 2,
        label: "Transcription",
        detail: "Transcription active."
      },
      {
        phaseId: "PRIVACY",
        status: "SUCCEEDED",
        percent: 100,
        completedUnits: 2,
        totalUnits: 2,
        label: "Privacy",
        detail: "Privacy complete."
      },
      {
        phaseId: "GOVERNANCE",
        status: "RUNNING",
        percent: null,
        completedUnits: 1,
        totalUnits: 3,
        label: "Governance",
        detail: "Governance evidence build active."
      }
    ],
    overallPercent: 88,
    degraded: false,
    errors: [],
    recommendedPollMs: 4_000,
    ...overrides
  };
}

describe("DocumentPipelineLiveStatus", () => {
  beforeEach(() => {
    requestBrowserApiMock.mockReset();
    requestBrowserApiMock.mockResolvedValue({
      ok: false,
      status: 503,
      detail: "API is unavailable."
    });
    mockMatchMedia(false);
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("renders determinate and indeterminate progress with real-only percent labels", async () => {
    requestBrowserApiMock.mockResolvedValue({
      ok: true,
      status: 200,
      data: buildSnapshot()
    });

    render(<DocumentPipelineLiveStatus documentId="doc-1" projectId="project-1" />);

    await waitFor(() => {
      expect(screen.queryByTestId("pipeline-progress-ingest")).not.toBeNull();
    });

    expect(screen.getByTestId("pipeline-percent-ingest").textContent).toContain("50%");
    expect(screen.queryByTestId("pipeline-percent-governance")).toBeNull();
    expect(screen.queryByTestId("pipeline-indeterminate-governance")).not.toBeNull();
  });

  it("polls for refreshed status and keeps last good snapshot during degraded polling", async () => {
    requestBrowserApiMock
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        data: buildSnapshot({ overallPercent: 50, recommendedPollMs: 20 })
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        data: buildSnapshot({ overallPercent: 76, recommendedPollMs: 20 })
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        detail: "API is unavailable."
      })
      .mockResolvedValue({
        ok: false,
        status: 503,
        detail: "API is unavailable."
      });

    render(<DocumentPipelineLiveStatus documentId="doc-1" projectId="project-1" />);

    await waitFor(() => {
      expect(screen.queryByText("50%")).not.toBeNull();
    });

    await waitFor(() => {
      expect(screen.queryByText("76%")).not.toBeNull();
    });

    await waitFor(() => {
      expect(screen.queryByText(/Status polling degraded/i)).not.toBeNull();
    });

    expect(screen.queryByText("76%")).not.toBeNull();
  });

  it("applies reduced-motion fallback class to animated bars", async () => {
    mockMatchMedia(true);
    requestBrowserApiMock.mockResolvedValue({
      ok: true,
      status: 200,
      data: buildSnapshot()
    });

    render(<DocumentPipelineLiveStatus documentId="doc-1" projectId="project-1" />);

    await waitFor(() => {
      expect(screen.queryByTestId("pipeline-indeterminate-governance")).not.toBeNull();
    });

    expect(screen.getByTestId("pipeline-indeterminate-governance").className).toContain(
      "documentPipelineProgressFill--reduced-motion"
    );
  });
});
