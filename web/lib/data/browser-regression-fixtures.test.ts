import { afterEach, describe, expect, it } from "vitest";
import type {
  DocumentGovernanceLedgerStatusResponse,
  DocumentGovernanceLedgerVerifyDetailResponse,
  DocumentGovernanceManifestEntriesResponse,
  DocumentPageVariantsResponse,
  DocumentPreprocessActiveRunResponse,
  DocumentPreprocessCompareResponse,
  DocumentPreprocessOverviewResponse,
  DocumentPreprocessQualityResponse,
  DocumentPreprocessRunListResponse,
  DocumentPreprocessRunPageListResponse,
  DocumentPreprocessRunStatusResponse,
  ProjectDerivativeCandidateSnapshotCreateResponse,
  ProjectDerivativeDetailResponse,
  ProjectDerivativeListResponse,
  ProjectDerivativePreviewResponse,
  ProjectDerivativeStatusResponse,
  ProjectEntityDetailResponse,
  ProjectEntityListResponse,
  ProjectEntityOccurrencesResponse,
  ProjectSearchResponse,
  ProjectSearchResultOpenResponse,
  ProjectDocumentPageDetail
} from "@ukde/contracts";

import {
  getBrowserFixtureSessionToken,
  resolveBrowserRegressionApiResult
} from "./browser-regression-fixtures";
import type { DocumentPipelineStatusResponse } from "../pipeline-status";

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

  it("serves governance manifest entries for reviewer profile and blocks researcher profile", () => {
    process.env[MODE_FLAG] = "1";
    const reviewerToken = getBrowserFixtureSessionToken("reviewer");
    const researcherToken = getBrowserFixtureSessionToken("researcher");
    const path =
      "/projects/project-fixture-alpha/documents/doc-fixture-002/governance/runs/redaction-run-fixture-001/manifest/entries?category=PERSON_NAME";

    const reviewerResult =
      resolveBrowserRegressionApiResult<DocumentGovernanceManifestEntriesResponse>({
        authToken: reviewerToken,
        method: "GET",
        path
      });
    expect(reviewerResult).not.toBeNull();
    expect(reviewerResult?.ok).toBe(true);
    expect(reviewerResult?.data?.items.length).toBeGreaterThan(0);
    expect(reviewerResult?.data?.items[0]?.category).toBe("PERSON_NAME");

    const researcherResult =
      resolveBrowserRegressionApiResult<DocumentGovernanceManifestEntriesResponse>({
        authToken: researcherToken,
        method: "GET",
        path
      });
    expect(researcherResult).not.toBeNull();
    expect(researcherResult?.ok).toBe(false);
    expect(researcherResult?.status).toBe(403);
  });

  it("restricts governance ledger reads to admin/auditor and verify mutations to admin", () => {
    process.env[MODE_FLAG] = "1";
    const adminToken = getBrowserFixtureSessionToken("admin");
    const auditorToken = getBrowserFixtureSessionToken("auditor");
    const reviewerToken = getBrowserFixtureSessionToken("reviewer");

    const ledgerStatusPath =
      "/projects/project-fixture-alpha/documents/doc-fixture-002/governance/runs/redaction-run-fixture-001/ledger/status";
    const verifyPath =
      "/projects/project-fixture-alpha/documents/doc-fixture-002/governance/runs/redaction-run-fixture-001/ledger/verify";
    const cancelPath =
      "/projects/project-fixture-alpha/documents/doc-fixture-002/governance/runs/redaction-run-fixture-001/ledger/verify/gov-ledger-verify-003/cancel";

    const auditorLedgerResult =
      resolveBrowserRegressionApiResult<DocumentGovernanceLedgerStatusResponse>({
        authToken: auditorToken,
        method: "GET",
        path: ledgerStatusPath
      });
    expect(auditorLedgerResult).not.toBeNull();
    expect(auditorLedgerResult?.ok).toBe(true);
    expect(auditorLedgerResult?.data?.ledgerVerificationStatus).toBe("VALID");

    const reviewerLedgerResult =
      resolveBrowserRegressionApiResult<DocumentGovernanceLedgerStatusResponse>({
        authToken: reviewerToken,
        method: "GET",
        path: ledgerStatusPath
      });
    expect(reviewerLedgerResult).not.toBeNull();
    expect(reviewerLedgerResult?.ok).toBe(false);
    expect(reviewerLedgerResult?.status).toBe(403);

    const auditorVerifyResult =
      resolveBrowserRegressionApiResult<DocumentGovernanceLedgerVerifyDetailResponse>({
        authToken: auditorToken,
        method: "POST",
        path: verifyPath
      });
    expect(auditorVerifyResult).not.toBeNull();
    expect(auditorVerifyResult?.ok).toBe(false);
    expect(auditorVerifyResult?.status).toBe(403);

    const adminVerifyResult =
      resolveBrowserRegressionApiResult<DocumentGovernanceLedgerVerifyDetailResponse>({
        authToken: adminToken,
        method: "POST",
        path: verifyPath
      });
    expect(adminVerifyResult).not.toBeNull();
    expect(adminVerifyResult?.ok).toBe(true);
    expect(adminVerifyResult?.data?.attempt.status).toBe("RUNNING");

    const adminCancelResult =
      resolveBrowserRegressionApiResult<DocumentGovernanceLedgerVerifyDetailResponse>({
        authToken: adminToken,
        method: "POST",
        path: cancelPath
      });
    expect(adminCancelResult).not.toBeNull();
    expect(adminCancelResult?.ok).toBe(true);
    expect(adminCancelResult?.data?.attempt.status).toBe("CANCELED");
  });

  it("serves aggregate pipeline status payload with deterministic phase shape", () => {
    process.env[MODE_FLAG] = "1";
    const authToken = getBrowserFixtureSessionToken();
    const result = resolveBrowserRegressionApiResult<DocumentPipelineStatusResponse>({
      authToken,
      method: "GET",
      path: "/projects/project-fixture-alpha/documents/doc-fixture-002/pipeline/status"
    });

    expect(result).not.toBeNull();
    expect(result?.ok).toBe(true);
    expect(result?.data?.phases).toHaveLength(6);
    expect(result?.data?.phases.map((phase) => phase.phaseId)).toEqual([
      "INGEST",
      "PREPROCESS",
      "LAYOUT",
      "TRANSCRIPTION",
      "PRIVACY",
      "GOVERNANCE"
    ]);
    expect(result?.data?.phases.every((phase) => typeof phase.label === "string")).toBe(true);
    expect(result?.data?.recommendedPollMs).toBeGreaterThan(0);
    expect(result?.data?.overallPercent).not.toBeNull();
  });

  it("serves project search hits from active index and blocks auditor profile", () => {
    process.env[MODE_FLAG] = "1";
    const researcherToken = getBrowserFixtureSessionToken("researcher");
    const auditorToken = getBrowserFixtureSessionToken("auditor");

    const researcherResult =
      resolveBrowserRegressionApiResult<ProjectSearchResponse>({
        authToken: researcherToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/search?q=adams&limit=1"
      });
    expect(researcherResult).not.toBeNull();
    expect(researcherResult?.ok).toBe(true);
    expect(researcherResult?.data?.searchIndexId).toBe("search-index-fixture-002");
    expect(researcherResult?.data?.items[0]?.searchDocumentId).toBe(
      "search-hit-token-001"
    );
    expect(researcherResult?.data?.nextCursor).toBeNull();

    const auditorResult =
      resolveBrowserRegressionApiResult<ProjectSearchResponse>({
        authToken: auditorToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/search?q=adams"
      });
    expect(auditorResult).not.toBeNull();
    expect(auditorResult?.ok).toBe(false);
    expect(auditorResult?.status).toBe(403);
  });

  it("serves project entities from active index and blocks auditor profile", () => {
    process.env[MODE_FLAG] = "1";
    const researcherToken = getBrowserFixtureSessionToken("researcher");
    const auditorToken = getBrowserFixtureSessionToken("auditor");

    const researcherResult =
      resolveBrowserRegressionApiResult<ProjectEntityListResponse>({
        authToken: researcherToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/entities?q=adams&entityType=PERSON"
      });
    expect(researcherResult).not.toBeNull();
    expect(researcherResult?.ok).toBe(true);
    expect(researcherResult?.data?.entityIndexId).toBe("entity-index-fixture-002");
    expect(researcherResult?.data?.items[0]?.id).toBe("entity-person-john-adams");

    const auditorResult =
      resolveBrowserRegressionApiResult<ProjectEntityListResponse>({
        authToken: auditorToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/entities?q=adams"
      });
    expect(auditorResult).not.toBeNull();
    expect(auditorResult?.ok).toBe(false);
    expect(auditorResult?.status).toBe(403);
  });

  it("serves entity detail and provenance-rich occurrence links from one active generation", () => {
    process.env[MODE_FLAG] = "1";
    const reviewerToken = getBrowserFixtureSessionToken("reviewer");
    const entityId = "entity-person-john-adams";

    const detailResult =
      resolveBrowserRegressionApiResult<ProjectEntityDetailResponse>({
        authToken: reviewerToken,
        method: "GET",
        path: `/projects/project-fixture-alpha/entities/${entityId}`
      });
    expect(detailResult).not.toBeNull();
    expect(detailResult?.ok).toBe(true);
    expect(detailResult?.data?.entityIndexId).toBe("entity-index-fixture-002");
    expect(detailResult?.data?.entity.id).toBe(entityId);

    const occurrencesResult =
      resolveBrowserRegressionApiResult<ProjectEntityOccurrencesResponse>({
        authToken: reviewerToken,
        method: "GET",
        path: `/projects/project-fixture-alpha/entities/${entityId}/occurrences`
      });
    expect(occurrencesResult).not.toBeNull();
    expect(occurrencesResult?.ok).toBe(true);
    expect(occurrencesResult?.data?.entityIndexId).toBe("entity-index-fixture-002");
    expect(occurrencesResult?.data?.entity.id).toBe(entityId);
    expect(occurrencesResult?.data?.items.length).toBeGreaterThan(0);
    expect(occurrencesResult?.data?.items[0]?.workspacePath).toContain(
      "/transcription/workspace?"
    );
  });

  it("serves derivative list/detail/status/preview and blocks auditor profile", () => {
    process.env[MODE_FLAG] = "1";
    const reviewerToken = getBrowserFixtureSessionToken("reviewer");
    const auditorToken = getBrowserFixtureSessionToken("auditor");
    const derivativeId = "dersnap-fixture-002";

    const activeListResult =
      resolveBrowserRegressionApiResult<ProjectDerivativeListResponse>({
        authToken: reviewerToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/derivatives"
      });
    expect(activeListResult).not.toBeNull();
    expect(activeListResult?.ok).toBe(true);
    expect(activeListResult?.data?.scope).toBe("active");
    expect(activeListResult?.data?.activeDerivativeIndexId).toBe(
      "derivative-index-fixture-002"
    );
    expect(activeListResult?.data?.items[0]?.id).toBe(derivativeId);

    const historicalListResult =
      resolveBrowserRegressionApiResult<ProjectDerivativeListResponse>({
        authToken: reviewerToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/derivatives?scope=historical"
      });
    expect(historicalListResult).not.toBeNull();
    expect(historicalListResult?.ok).toBe(true);
    expect(historicalListResult?.data?.scope).toBe("historical");
    expect(historicalListResult?.data?.items.map((item) => item.id)).toEqual([
      derivativeId
    ]);

    const detailResult =
      resolveBrowserRegressionApiResult<ProjectDerivativeDetailResponse>({
        authToken: reviewerToken,
        method: "GET",
        path: `/projects/project-fixture-alpha/derivatives/${derivativeId}`
      });
    expect(detailResult).not.toBeNull();
    expect(detailResult?.ok).toBe(true);
    expect(detailResult?.data?.derivative.id).toBe(derivativeId);
    expect(detailResult?.data?.derivative.isActiveGeneration).toBe(false);

    const statusResult =
      resolveBrowserRegressionApiResult<ProjectDerivativeStatusResponse>({
        authToken: reviewerToken,
        method: "GET",
        path: `/projects/project-fixture-alpha/derivatives/${derivativeId}/status`
      });
    expect(statusResult).not.toBeNull();
    expect(statusResult?.ok).toBe(true);
    expect(statusResult?.data?.derivativeId).toBe(derivativeId);
    expect(statusResult?.data?.status).toBe("SUCCEEDED");

    const previewResult =
      resolveBrowserRegressionApiResult<ProjectDerivativePreviewResponse>({
        authToken: reviewerToken,
        method: "GET",
        path: `/projects/project-fixture-alpha/derivatives/${derivativeId}/preview`
      });
    expect(previewResult).not.toBeNull();
    expect(previewResult?.ok).toBe(true);
    expect(previewResult?.data?.derivativeSnapshotId).toBe(derivativeId);
    expect(previewResult?.data?.rows.length).toBeGreaterThan(0);
    expect(
      previewResult?.data?.rows.every((row) => row.derivativeSnapshotId === derivativeId)
    ).toBe(true);

    const auditorResult =
      resolveBrowserRegressionApiResult<ProjectDerivativeListResponse>({
        authToken: auditorToken,
        method: "GET",
        path: "/projects/project-fixture-alpha/derivatives"
      });
    expect(auditorResult).not.toBeNull();
    expect(auditorResult?.ok).toBe(false);
    expect(auditorResult?.status).toBe(403);
  });

  it("freezes derivative candidate snapshots idempotently and restricts freeze roles", () => {
    process.env[MODE_FLAG] = "1";
    const reviewerToken = getBrowserFixtureSessionToken("reviewer");
    const researcherToken = getBrowserFixtureSessionToken("researcher");
    const derivativeId = "dersnap-fixture-002";

    const firstFreeze =
      resolveBrowserRegressionApiResult<ProjectDerivativeCandidateSnapshotCreateResponse>(
        {
          authToken: reviewerToken,
          method: "POST",
          path: `/projects/project-fixture-alpha/derivatives/${derivativeId}/candidate-snapshots`
        }
      );
    expect(firstFreeze).not.toBeNull();
    expect(firstFreeze?.ok).toBe(true);
    expect(firstFreeze?.status).toBe(201);
    expect(firstFreeze?.data?.created).toBe(true);
    expect(firstFreeze?.data?.candidate.sourceArtifactId).toBe(derivativeId);
    expect(firstFreeze?.data?.candidateSnapshotId).toBe(
      "candidate-derivative-fixture-002"
    );

    const secondFreeze =
      resolveBrowserRegressionApiResult<ProjectDerivativeCandidateSnapshotCreateResponse>(
        {
          authToken: reviewerToken,
          method: "POST",
          path: `/projects/project-fixture-alpha/derivatives/${derivativeId}/candidate-snapshots`
        }
      );
    expect(secondFreeze).not.toBeNull();
    expect(secondFreeze?.ok).toBe(true);
    expect(secondFreeze?.status).toBe(201);
    expect(secondFreeze?.data?.created).toBe(false);
    expect(secondFreeze?.data?.candidateSnapshotId).toBe(
      firstFreeze?.data?.candidateSnapshotId
    );

    const detailAfterFreeze =
      resolveBrowserRegressionApiResult<ProjectDerivativeDetailResponse>({
        authToken: reviewerToken,
        method: "GET",
        path: `/projects/project-fixture-alpha/derivatives/${derivativeId}`
      });
    expect(detailAfterFreeze).not.toBeNull();
    expect(detailAfterFreeze?.ok).toBe(true);
    expect(detailAfterFreeze?.data?.derivative.candidateSnapshotId).toBe(
      "candidate-derivative-fixture-002"
    );

    const researcherFreeze =
      resolveBrowserRegressionApiResult<ProjectDerivativeCandidateSnapshotCreateResponse>(
        {
          authToken: researcherToken,
          method: "POST",
          path: `/projects/project-fixture-alpha/derivatives/${derivativeId}/candidate-snapshots`
        }
      );
    expect(researcherFreeze).not.toBeNull();
    expect(researcherFreeze?.ok).toBe(false);
    expect(researcherFreeze?.status).toBe(403);
  });

  it("rejects candidate freeze for superseded derivative snapshots", () => {
    process.env[MODE_FLAG] = "1";
    const reviewerToken = getBrowserFixtureSessionToken("reviewer");

    const freezeSuperseded =
      resolveBrowserRegressionApiResult<ProjectDerivativeCandidateSnapshotCreateResponse>(
        {
          authToken: reviewerToken,
          method: "POST",
          path: "/projects/project-fixture-alpha/derivatives/dersnap-fixture-001/candidate-snapshots"
        }
      );
    expect(freezeSuperseded).not.toBeNull();
    expect(freezeSuperseded?.ok).toBe(false);
    expect(freezeSuperseded?.status).toBe(409);
  });

  it("returns deterministic workspace path payload when opening a search hit", () => {
    process.env[MODE_FLAG] = "1";
    const reviewerToken = getBrowserFixtureSessionToken("reviewer");

    const openTokenHitResult =
      resolveBrowserRegressionApiResult<ProjectSearchResultOpenResponse>({
        authToken: reviewerToken,
        method: "POST",
        path: "/projects/project-fixture-alpha/search/search-hit-token-001/open"
      });
    expect(openTokenHitResult).not.toBeNull();
    expect(openTokenHitResult?.ok).toBe(true);
    expect(openTokenHitResult?.data?.workspacePath).toBe(
      "/projects/project-fixture-alpha/documents/doc-fixture-002/transcription/workspace?lineId=line-privacy-001&page=1&runId=transcription-run-fixture-002&sourceKind=LINE&sourceRefId=line-privacy-001&tokenId=token-privacy-001"
    );

    const openRescueHitResult =
      resolveBrowserRegressionApiResult<ProjectSearchResultOpenResponse>({
        authToken: reviewerToken,
        method: "POST",
        path: "/projects/project-fixture-alpha/search/search-hit-rescue-001/open"
      });
    expect(openRescueHitResult).not.toBeNull();
    expect(openRescueHitResult?.ok).toBe(true);
    expect(openRescueHitResult?.data?.workspacePath).toBe(
      "/projects/project-fixture-alpha/documents/doc-fixture-002/transcription/workspace?page=2&runId=transcription-run-fixture-002&sourceKind=RESCUE_CANDIDATE&sourceRefId=resc-2-1"
    );
  });
});
