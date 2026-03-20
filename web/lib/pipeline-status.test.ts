import { describe, expect, it } from "vitest";

import type {
  DocumentGovernanceLedgerStatusResponse,
  DocumentGovernanceManifestStatusResponse,
  DocumentGovernanceOverviewResponse,
  DocumentPreprocessOverviewResponse,
  DocumentRedactionOverviewResponse,
  DocumentTimelineEvent
} from "@ukde/contracts";

import {
  computeCountBasedPipelinePhase,
  computeGovernancePipelinePhase,
  computeIngestPipelinePhase,
  computePreprocessPipelinePhase,
  computePrivacyPipelinePhase
} from "./pipeline-status";

function buildTimelineItem(
  overrides: Partial<DocumentTimelineEvent>
): DocumentTimelineEvent {
  return {
    id: "run-id",
    attemptNumber: 1,
    runKind: "UPLOAD",
    supersedesProcessingRunId: null,
    supersededByProcessingRunId: null,
    status: "QUEUED",
    failureReason: null,
    createdBy: "fixture-user",
    startedAt: null,
    finishedAt: null,
    canceledBy: null,
    canceledAt: null,
    createdAt: "2026-03-19T09:00:00.000Z",
    ...overrides
  };
}

describe("pipeline status calculations", () => {
  it("computes ingest progress as discrete completed stages / 4", () => {
    const phase = computeIngestPipelinePhase("EXTRACTING", [
      buildTimelineItem({ id: "up", runKind: "UPLOAD", status: "SUCCEEDED" }),
      buildTimelineItem({ id: "scan", runKind: "SCAN", status: "SUCCEEDED" }),
      buildTimelineItem({ id: "extract", runKind: "EXTRACTION", status: "RUNNING" })
    ]);

    expect(phase.status).toBe("RUNNING");
    expect(phase.completedUnits).toBe(2);
    expect(phase.totalUnits).toBe(4);
    expect(phase.percent).toBe(50);
  });

  it("counts failed and canceled page states as terminal progress", () => {
    const phase = computeCountBasedPipelinePhase({
      phaseId: "PREPROCESS",
      label: "Preprocess",
      pageCount: 10,
      statusCounts: {
        SUCCEEDED: 4,
        FAILED: 3,
        CANCELED: 1
      },
      activeRunStatus: "RUNNING",
      latestRunStatus: "RUNNING"
    });

    expect(phase.status).toBe("RUNNING");
    expect(phase.completedUnits).toBe(8);
    expect(phase.percent).toBe(80);
  });

  it("returns null percent when total units are zero", () => {
    const phase = computeCountBasedPipelinePhase({
      phaseId: "LAYOUT",
      label: "Layout",
      pageCount: 0,
      statusCounts: {
        SUCCEEDED: 3,
        FAILED: 1
      },
      activeRunStatus: "RUNNING",
      latestRunStatus: "RUNNING"
    });

    expect(phase.totalUnits).toBe(0);
    expect(phase.percent).toBeNull();
  });

  it("falls back to latest terminal run status when no active run exists", () => {
    const preprocessOverview = {
      documentId: "doc-1",
      projectId: "project-1",
      projection: null,
      activeRun: null,
      latestRun: { status: "SUCCEEDED" },
      totalRuns: 1,
      pageCount: 2,
      activeStatusCounts: {
        QUEUED: 0,
        RUNNING: 0,
        SUCCEEDED: 2,
        FAILED: 0,
        CANCELED: 0
      },
      activeQualityGateCounts: {
        PASS: 2,
        REVIEW_REQUIRED: 0,
        BLOCKED: 0
      },
      activeWarningCount: 0
    } as unknown as DocumentPreprocessOverviewResponse;

    const phase = computePreprocessPipelinePhase(preprocessOverview);
    expect(phase.status).toBe("SUCCEEDED");
    expect(phase.percent).toBe(100);
  });

  it("keeps governance progress indeterminate while active milestones are not terminal", () => {
    const overview: DocumentGovernanceOverviewResponse = {
      documentId: "doc-1",
      projectId: "project-1",
      activeRunId: "gov-run-1",
      totalRuns: 1,
      approvedRuns: 0,
      readyRuns: 0,
      pendingRuns: 1,
      failedRuns: 0,
      latestRunId: "gov-run-1",
      latestReadyRunId: null,
      latestRun: {
        runId: "gov-run-1",
        projectId: "project-1",
        documentId: "doc-1",
        runStatus: "RUNNING",
        reviewStatus: null,
        approvedSnapshotKey: null,
        approvedSnapshotSha256: null,
        runOutputStatus: null,
        runOutputManifestSha256: null,
        runCreatedAt: "2026-03-19T09:00:00.000Z",
        runFinishedAt: null,
        readinessStatus: "PENDING",
        generationStatus: "RUNNING",
        readyManifestId: null,
        readyLedgerId: null,
        latestManifestSha256: null,
        latestLedgerSha256: null,
        ledgerVerificationStatus: "PENDING",
        readyAt: null,
        lastErrorCode: null,
        updatedAt: "2026-03-19T09:01:00.000Z"
      },
      latestReadyRun: null
    };

    const manifestStatus: DocumentGovernanceManifestStatusResponse = {
      runId: "gov-run-1",
      status: "RUNNING",
      latestAttempt: null,
      attemptCount: 1,
      readyManifestId: null,
      latestManifestSha256: null,
      generationStatus: "RUNNING",
      readinessStatus: "PENDING",
      updatedAt: "2026-03-19T09:01:00.000Z"
    };

    const ledgerStatus: DocumentGovernanceLedgerStatusResponse = {
      runId: "gov-run-1",
      status: "RUNNING",
      latestAttempt: null,
      attemptCount: 1,
      readyLedgerId: null,
      latestLedgerSha256: null,
      generationStatus: "RUNNING",
      readinessStatus: "PENDING",
      ledgerVerificationStatus: "PENDING",
      updatedAt: "2026-03-19T09:01:00.000Z"
    };

    const phase = computeGovernancePipelinePhase({
      overview,
      manifestStatus,
      ledgerStatus
    });

    expect(phase.status).toBe("RUNNING");
    expect(phase.completedUnits).toBe(0);
    expect(phase.totalUnits).toBe(3);
    expect(phase.percent).toBeNull();
  });

  it("computes privacy percent from preview ready + failed over total pages", () => {
    const overview: DocumentRedactionOverviewResponse = {
      documentId: "doc-1",
      projectId: "project-1",
      projection: null,
      activeRun: { status: "RUNNING" } as unknown as DocumentRedactionOverviewResponse["activeRun"],
      latestRun: { status: "RUNNING" } as unknown as DocumentRedactionOverviewResponse["latestRun"],
      totalRuns: 1,
      pageCount: 10,
      findingsByCategory: {},
      unresolvedFindings: 0,
      autoAppliedFindings: 0,
      needsReviewFindings: 0,
      overriddenFindings: 0,
      pagesBlockedForReview: 0,
      previewReadyPages: 8,
      previewTotalPages: 10,
      previewFailedPages: 1
    };

    const phase = computePrivacyPipelinePhase(overview);
    expect(phase.status).toBe("RUNNING");
    expect(phase.percent).toBe(90);
    expect(phase.completedUnits).toBe(9);
    expect(phase.totalUnits).toBe(10);
  });
});
