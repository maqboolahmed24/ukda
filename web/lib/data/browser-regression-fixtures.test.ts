import { afterEach, describe, expect, it } from "vitest";
import type {
  DocumentPageVariantsResponse,
  DocumentPreprocessActiveRunResponse,
  DocumentPreprocessCompareResponse,
  DocumentPreprocessOverviewResponse,
  DocumentPreprocessQualityResponse,
  DocumentPreprocessRunListResponse,
  DocumentPreprocessRunPageListResponse,
  DocumentPreprocessRunStatusResponse,
  ProjectDocumentPageDetail
} from "@ukde/contracts";

import {
  getBrowserFixtureSessionToken,
  resolveBrowserRegressionApiResult
} from "./browser-regression-fixtures";

const MODE_FLAG = "UKDE_BROWSER_TEST_MODE";

describe("browser regression fixtures document page patch support", () => {
  const originalMode = process.env[MODE_FLAG];

  afterEach(() => {
    if (typeof originalMode === "undefined") {
      delete process.env[MODE_FLAG];
    } else {
      process.env[MODE_FLAG] = originalMode;
    }
  });

  it("persists viewer rotation for patch + readback flows", () => {
    process.env[MODE_FLAG] = "1";
    const authToken = getBrowserFixtureSessionToken();
    const pagePath =
      "/projects/project-fixture-alpha/documents/doc-fixture-002/pages/page-fixture-001";

    const patchResult =
      resolveBrowserRegressionApiResult<ProjectDocumentPageDetail>({
        authToken,
        body: JSON.stringify({ viewerRotation: 90 }),
        method: "PATCH",
        path: pagePath
      });
    expect(patchResult).not.toBeNull();
    expect(patchResult?.ok).toBe(true);
    expect(patchResult?.data?.viewerRotation).toBe(90);

    const readbackResult =
      resolveBrowserRegressionApiResult<ProjectDocumentPageDetail>({
        authToken,
        method: "GET",
        path: pagePath
      });
    expect(readbackResult).not.toBeNull();
    expect(readbackResult?.ok).toBe(true);
    expect(readbackResult?.data?.viewerRotation).toBe(90);
  });

  it("serves preprocess run list and active projection for compare-enabled viewer state", () => {
    process.env[MODE_FLAG] = "1";
    const authToken = getBrowserFixtureSessionToken();

    const runsResult =
      resolveBrowserRegressionApiResult<DocumentPreprocessRunListResponse>({
        authToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/documents/doc-fixture-002/preprocess-runs?pageSize=25"
      });
    expect(runsResult).not.toBeNull();
    expect(runsResult?.ok).toBe(true);
    expect(runsResult?.data?.items.length).toBeGreaterThanOrEqual(2);
    expect(runsResult?.data?.items[0]?.id).toBe("pre-run-fixture-002");

    const activeResult =
      resolveBrowserRegressionApiResult<DocumentPreprocessActiveRunResponse>({
        authToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/documents/doc-fixture-002/preprocess-runs/active"
      });
    expect(activeResult).not.toBeNull();
    expect(activeResult?.ok).toBe(true);
    expect(activeResult?.data?.projection?.activePreprocessRunId).toBe(
      "pre-run-fixture-002"
    );
    expect(activeResult?.data?.run?.id).toBe("pre-run-fixture-002");
  });

  it("serves page variants for active and explicit preprocess run contexts", () => {
    process.env[MODE_FLAG] = "1";
    const authToken = getBrowserFixtureSessionToken();

    const activeRunVariants =
      resolveBrowserRegressionApiResult<DocumentPageVariantsResponse>({
        authToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/documents/doc-fixture-002/pages/page-fixture-001/variants"
      });
    expect(activeRunVariants).not.toBeNull();
    expect(activeRunVariants?.ok).toBe(true);
    expect(activeRunVariants?.data?.resolvedRunId).toBe("pre-run-fixture-002");
    expect(
      activeRunVariants?.data?.variants.find(
        (variant) => variant.imageVariant === "preprocessed_gray"
      )?.available
    ).toBe(true);
    expect(
      activeRunVariants?.data?.variants.find(
        (variant) => variant.imageVariant === "preprocessed_bin"
      )?.available
    ).toBe(true);

    const explicitRunVariants =
      resolveBrowserRegressionApiResult<DocumentPageVariantsResponse>({
        authToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/documents/doc-fixture-002/pages/page-fixture-002/variants?runId=pre-run-fixture-001"
      });
    expect(explicitRunVariants).not.toBeNull();
    expect(explicitRunVariants?.ok).toBe(true);
    expect(explicitRunVariants?.data?.requestedRunId).toBe("pre-run-fixture-001");
    expect(explicitRunVariants?.data?.resolvedRunId).toBe("pre-run-fixture-001");
    expect(
      explicitRunVariants?.data?.variants.find(
        (variant) => variant.imageVariant === "preprocessed_gray"
      )?.qualityGateStatus
    ).toBe("REVIEW_REQUIRED");
  });

  it("serves canonical preprocess compare payloads for run diagnostics", () => {
    process.env[MODE_FLAG] = "1";
    const authToken = getBrowserFixtureSessionToken();

    const compareResult =
      resolveBrowserRegressionApiResult<DocumentPreprocessCompareResponse>({
        authToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/documents/doc-fixture-002/preprocess-runs/compare?baseRunId=pre-run-fixture-001&candidateRunId=pre-run-fixture-002"
      });
    expect(compareResult).not.toBeNull();
    expect(compareResult?.ok).toBe(true);
    expect(compareResult?.data?.baseRun.id).toBe("pre-run-fixture-001");
    expect(compareResult?.data?.candidateRun.id).toBe("pre-run-fixture-002");
    expect(compareResult?.data?.items.length).toBeGreaterThan(0);
  });

  it("serves preprocessing overview, quality, run-status, and run-page payloads", () => {
    process.env[MODE_FLAG] = "1";
    const authToken = getBrowserFixtureSessionToken();

    const overviewResult =
      resolveBrowserRegressionApiResult<DocumentPreprocessOverviewResponse>({
        authToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/documents/doc-fixture-002/preprocessing/overview"
      });
    expect(overviewResult).not.toBeNull();
    expect(overviewResult?.ok).toBe(true);
    expect(overviewResult?.data?.activeRun?.id).toBe("pre-run-fixture-002");
    expect(overviewResult?.data?.totalRuns).toBeGreaterThanOrEqual(2);

    const qualityResult =
      resolveBrowserRegressionApiResult<DocumentPreprocessQualityResponse>({
        authToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/documents/doc-fixture-002/preprocessing/quality?runId=pre-run-fixture-002&pageSize=5"
      });
    expect(qualityResult).not.toBeNull();
    expect(qualityResult?.ok).toBe(true);
    expect(qualityResult?.data?.run?.id).toBe("pre-run-fixture-002");
    expect(qualityResult?.data?.items.length).toBeGreaterThan(0);

    const runStatusResult =
      resolveBrowserRegressionApiResult<DocumentPreprocessRunStatusResponse>({
        authToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/documents/doc-fixture-002/preprocess-runs/pre-run-fixture-002/status"
      });
    expect(runStatusResult).not.toBeNull();
    expect(runStatusResult?.ok).toBe(true);
    expect(runStatusResult?.data?.status).toBe("SUCCEEDED");

    const runPagesResult =
      resolveBrowserRegressionApiResult<DocumentPreprocessRunPageListResponse>({
        authToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/documents/doc-fixture-002/preprocess-runs/pre-run-fixture-002/pages?pageSize=10"
      });
    expect(runPagesResult).not.toBeNull();
    expect(runPagesResult?.ok).toBe(true);
    expect(runPagesResult?.data?.runId).toBe("pre-run-fixture-002");
    expect(runPagesResult?.data?.items.length).toBeGreaterThan(0);
  });
});
