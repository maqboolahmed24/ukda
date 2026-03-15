import { describe, expect, it } from "vitest";

import { queryKeys, serializeQueryKey } from "./query-keys";

describe("query key factory", () => {
  it("normalizes optional filters into stable keys", () => {
    const first = queryKeys.audit.list({
      actorUserId: "  ",
      cursor: undefined,
      eventType: undefined,
      from: "",
      pageSize: 50,
      projectId: "project-1",
      to: undefined
    });
    const second = queryKeys.audit.list({
      pageSize: 50,
      projectId: "project-1"
    });

    expect(first).toEqual(second);
    expect(serializeQueryKey(first)).toBe(serializeQueryKey(second));
  });

  it("keeps project activity distinct from admin audit and my activity", () => {
    const project = queryKeys.projects.projectActivity("project-123");
    const adminAudit = queryKeys.audit.list({ projectId: "project-123" });
    const myActivity = queryKeys.audit.myActivity(60);

    expect(serializeQueryKey(project)).not.toBe(serializeQueryKey(adminAudit));
    expect(serializeQueryKey(project)).not.toBe(serializeQueryKey(myActivity));
  });

  it("keeps operations timeline keys scoped by filter state", () => {
    const all = queryKeys.operations.timelines({
      cursor: 0,
      pageSize: 60,
      scope: "all"
    });
    const auditOnly = queryKeys.operations.timelines({
      cursor: 0,
      pageSize: 60,
      scope: "audit"
    });

    expect(serializeQueryKey(all)).not.toBe(serializeQueryKey(auditOnly));
  });

  it("keeps document list keys stable and timeline keys distinct", () => {
    const first = queryKeys.documents.list("project-1", {
      q: "  ",
      status: "",
      sort: "updated",
      direction: "desc",
      pageSize: 50
    });
    const second = queryKeys.documents.list("project-1", {
      sort: "updated",
      direction: "desc",
      pageSize: 50
    });
    const detail = queryKeys.documents.detail("project-1", "doc-1");
    const timeline = queryKeys.documents.timeline("project-1", "doc-1");
    const runStatus = queryKeys.documents.processingRunStatus(
      "project-1",
      "doc-1",
      "run-1"
    );

    expect(first).toEqual(second);
    expect(serializeQueryKey(first)).toBe(serializeQueryKey(second));
    expect(serializeQueryKey(detail)).not.toBe(serializeQueryKey(timeline));
    expect(serializeQueryKey(timeline)).not.toBe(serializeQueryKey(runStatus));
  });

  it("scopes transcription triage and run status keys by route state", () => {
    const triageA = queryKeys.documents.transcriptionTriage("project-1", "doc-1", {
      confidenceBelow: 0.7,
      pageSize: 100,
      runId: "run-a",
      status: "SUCCEEDED"
    });
    const triageB = queryKeys.documents.transcriptionTriage("project-1", "doc-1", {
      confidenceBelow: 0.7,
      pageSize: 100,
      runId: "run-b",
      status: "SUCCEEDED"
    });
    const status = queryKeys.documents.transcriptionRunStatus(
      "project-1",
      "doc-1",
      "run-a"
    );

    expect(serializeQueryKey(triageA)).not.toBe(serializeQueryKey(triageB));
    expect(serializeQueryKey(triageA)).not.toBe(serializeQueryKey(status));
  });

  it("keeps approved-model and project model-assignment keys distinct", () => {
    const approvedPrimary = queryKeys.models.approvedList({
      modelRole: "TRANSCRIPTION_PRIMARY",
      status: "APPROVED"
    });
    const approvedFallback = queryKeys.models.approvedList({
      modelRole: "TRANSCRIPTION_FALLBACK",
      status: "APPROVED"
    });
    const assignmentList = queryKeys.projects.modelAssignments("project-1");
    const assignmentDetail = queryKeys.projects.modelAssignmentDetail(
      "project-1",
      "assignment-1"
    );
    const assignmentDatasets = queryKeys.projects.modelAssignmentDatasets(
      "project-1",
      "assignment-1"
    );

    expect(serializeQueryKey(approvedPrimary)).not.toBe(
      serializeQueryKey(approvedFallback)
    );
    expect(serializeQueryKey(assignmentList)).not.toBe(
      serializeQueryKey(assignmentDetail)
    );
    expect(serializeQueryKey(assignmentDetail)).not.toBe(
      serializeQueryKey(assignmentDatasets)
    );
  });

  it("scopes policy list/detail/events/compare keys by target", () => {
    const list = queryKeys.projects.policyList("project-1");
    const detail = queryKeys.projects.policyDetail("project-1", "policy-1");
    const events = queryKeys.projects.policyEvents("project-1", "policy-1");
    const lineage = queryKeys.projects.policyLineage("project-1", "policy-1");
    const usage = queryKeys.projects.policyUsage("project-1", "policy-1");
    const explainability = queryKeys.projects.policyExplainability(
      "project-1",
      "policy-1"
    );
    const snapshotA = queryKeys.projects.policySnapshot(
      "project-1",
      "policy-1",
      "a".repeat(64)
    );
    const snapshotB = queryKeys.projects.policySnapshot(
      "project-1",
      "policy-1",
      "b".repeat(64)
    );
    const againstPolicy = queryKeys.projects.policyCompare("project-1", "policy-1", {
      against: "policy-0"
    });
    const againstBaseline = queryKeys.projects.policyCompare("project-1", "policy-1", {
      againstBaselineSnapshotId: "baseline-phase0-v1"
    });

    expect(serializeQueryKey(list)).not.toBe(serializeQueryKey(detail));
    expect(serializeQueryKey(detail)).not.toBe(serializeQueryKey(events));
    expect(serializeQueryKey(events)).not.toBe(serializeQueryKey(lineage));
    expect(serializeQueryKey(lineage)).not.toBe(serializeQueryKey(usage));
    expect(serializeQueryKey(usage)).not.toBe(
      serializeQueryKey(explainability)
    );
    expect(serializeQueryKey(snapshotA)).not.toBe(serializeQueryKey(snapshotB));
    expect(serializeQueryKey(againstPolicy)).not.toBe(
      serializeQueryKey(againstBaseline)
    );
  });

  it("scopes pseudonym registry list/detail/events keys by entry identity", () => {
    const list = queryKeys.projects.pseudonymRegistryList("project-1");
    const detailA = queryKeys.projects.pseudonymRegistryDetail(
      "project-1",
      "entry-a"
    );
    const detailB = queryKeys.projects.pseudonymRegistryDetail(
      "project-1",
      "entry-b"
    );
    const events = queryKeys.projects.pseudonymRegistryEvents(
      "project-1",
      "entry-a"
    );

    expect(serializeQueryKey(list)).not.toBe(serializeQueryKey(detailA));
    expect(serializeQueryKey(detailA)).not.toBe(serializeQueryKey(detailB));
    expect(serializeQueryKey(detailA)).not.toBe(serializeQueryKey(events));
  });

  it("keeps project search keys stable and cursor-scoped", () => {
    const first = queryKeys.projects.search("project-1", {
      q: "  smith ",
      documentId: "doc-1",
      runId: "",
      pageNumber: undefined
    });
    const second = queryKeys.projects.search("project-1", {
      q: "smith",
      documentId: "doc-1"
    });
    const nextPage = queryKeys.projects.search("project-1", {
      q: "smith",
      documentId: "doc-1",
      cursor: 25
    });

    expect(first).toEqual(second);
    expect(serializeQueryKey(first)).toBe(serializeQueryKey(second));
    expect(serializeQueryKey(first)).not.toBe(serializeQueryKey(nextPage));
  });

  it("keeps project entity discovery keys stable and scope-specific", () => {
    const first = queryKeys.projects.entities("project-1", {
      q: "  adams ",
      entityType: "PERSON",
      limit: 25
    });
    const second = queryKeys.projects.entities("project-1", {
      q: "adams",
      entityType: "PERSON",
      limit: 25
    });
    const nextPage = queryKeys.projects.entities("project-1", {
      q: "adams",
      entityType: "PERSON",
      cursor: 25,
      limit: 25
    });
    const detail = queryKeys.projects.entityDetail("project-1", "entity-1");
    const occurrences = queryKeys.projects.entityOccurrences("project-1", "entity-1", {
      cursor: 0,
      limit: 25
    });

    expect(first).toEqual(second);
    expect(serializeQueryKey(first)).toBe(serializeQueryKey(second));
    expect(serializeQueryKey(first)).not.toBe(serializeQueryKey(nextPage));
    expect(serializeQueryKey(detail)).not.toBe(serializeQueryKey(occurrences));
  });

  it("scopes export candidate/request keys by identity and filters", () => {
    const candidates = queryKeys.exports.candidates("project-1");
    const candidateA = queryKeys.exports.candidate("project-1", "candidate-a");
    const candidateB = queryKeys.exports.candidate("project-1", "candidate-b");
    const previewA = queryKeys.exports.candidateReleasePack("project-1", "candidate-a", {
      purposeStatement: "Purpose A"
    });
    const previewB = queryKeys.exports.candidateReleasePack("project-1", "candidate-a", {
      purposeStatement: "Purpose B"
    });
    const listA = queryKeys.exports.requests("project-1", {
      cursor: 0,
      limit: 50,
      status: "SUBMITTED"
    });
    const listB = queryKeys.exports.requests("project-1", {
      cursor: 50,
      limit: 50,
      status: "SUBMITTED"
    });
    const request = queryKeys.exports.request("project-1", "request-a");
    const statusKey = queryKeys.exports.requestStatus("project-1", "request-a");
    const releasePackKey = queryKeys.exports.requestReleasePack(
      "project-1",
      "request-a"
    );
    const validationSummaryKey = queryKeys.exports.requestValidationSummary(
      "project-1",
      "request-a"
    );
    const receiptKey = queryKeys.exports.requestReceipt("project-1", "request-a");
    const receiptsKey = queryKeys.exports.requestReceipts("project-1", "request-a");
    const eventsKey = queryKeys.exports.requestEvents("project-1", "request-a");
    const reviewsKey = queryKeys.exports.requestReviews("project-1", "request-a");
    const reviewEventsKey = queryKeys.exports.requestReviewEvents(
      "project-1",
      "request-a"
    );
    const bundlesKey = queryKeys.exports.requestBundles("project-1", "request-a");
    const bundleA = queryKeys.exports.requestBundle(
      "project-1",
      "request-a",
      "bundle-a"
    );
    const bundleB = queryKeys.exports.requestBundle(
      "project-1",
      "request-a",
      "bundle-b"
    );
    const bundleStatusKey = queryKeys.exports.requestBundleStatus(
      "project-1",
      "request-a",
      "bundle-a"
    );
    const bundleEventsKey = queryKeys.exports.requestBundleEvents(
      "project-1",
      "request-a",
      "bundle-a"
    );
    const bundleVerificationKey = queryKeys.exports.requestBundleVerification(
      "project-1",
      "request-a",
      "bundle-a"
    );
    const bundleVerificationStatusKey =
      queryKeys.exports.requestBundleVerificationStatus(
        "project-1",
        "request-a",
        "bundle-a"
      );
    const bundleVerificationRunsKey = queryKeys.exports.requestBundleVerificationRuns(
      "project-1",
      "request-a",
      "bundle-a"
    );
    const bundleVerificationRunAKey = queryKeys.exports.requestBundleVerificationRun(
      "project-1",
      "request-a",
      "bundle-a",
      "verify-run-a"
    );
    const bundleVerificationRunBKey = queryKeys.exports.requestBundleVerificationRun(
      "project-1",
      "request-a",
      "bundle-a",
      "verify-run-b"
    );
    const bundleVerificationRunStatusKey =
      queryKeys.exports.requestBundleVerificationRunStatus(
        "project-1",
        "request-a",
        "bundle-a",
        "verify-run-a"
      );
    const bundleProfilesKey = queryKeys.exports.requestBundleProfiles(
      "project-1",
      "request-a",
      "bundle-a"
    );
    const bundleValidationStatusKey = queryKeys.exports.requestBundleValidationStatus(
      "project-1",
      "request-a",
      "bundle-a",
      "SAFEGUARDED_DEPOSIT_CORE_V1"
    );
    const bundleValidationRunsKey = queryKeys.exports.requestBundleValidationRuns(
      "project-1",
      "request-a",
      "bundle-a",
      "SAFEGUARDED_DEPOSIT_CORE_V1"
    );
    const bundleValidationRunAKey = queryKeys.exports.requestBundleValidationRun(
      "project-1",
      "request-a",
      "bundle-a",
      "validate-run-a",
      "SAFEGUARDED_DEPOSIT_CORE_V1"
    );
    const bundleValidationRunStatusKey =
      queryKeys.exports.requestBundleValidationRunStatus(
        "project-1",
        "request-a",
        "bundle-a",
        "validate-run-a",
        "SAFEGUARDED_DEPOSIT_CORE_V1"
      );
    const reviewQueueAll = queryKeys.exports.review("project-1", {});
    const reviewQueueFiltered = queryKeys.exports.review("project-1", {
      agingBucket: "OVERDUE",
      reviewerUserId: "reviewer-1",
      status: "IN_REVIEW"
    });

    expect(serializeQueryKey(candidates)).not.toBe(serializeQueryKey(candidateA));
    expect(serializeQueryKey(candidateA)).not.toBe(serializeQueryKey(candidateB));
    expect(serializeQueryKey(previewA)).not.toBe(serializeQueryKey(previewB));
    expect(serializeQueryKey(listA)).not.toBe(serializeQueryKey(listB));
    expect(serializeQueryKey(request)).not.toBe(serializeQueryKey(statusKey));
    expect(serializeQueryKey(statusKey)).not.toBe(serializeQueryKey(releasePackKey));
    expect(serializeQueryKey(releasePackKey)).not.toBe(
      serializeQueryKey(validationSummaryKey)
    );
    expect(serializeQueryKey(validationSummaryKey)).not.toBe(
      serializeQueryKey(receiptKey)
    );
    expect(serializeQueryKey(receiptKey)).not.toBe(serializeQueryKey(receiptsKey));
    expect(serializeQueryKey(receiptsKey)).not.toBe(serializeQueryKey(eventsKey));
    expect(serializeQueryKey(eventsKey)).not.toBe(serializeQueryKey(reviewsKey));
    expect(serializeQueryKey(reviewsKey)).not.toBe(
      serializeQueryKey(reviewEventsKey)
    );
    expect(serializeQueryKey(reviewEventsKey)).not.toBe(
      serializeQueryKey(bundlesKey)
    );
    expect(serializeQueryKey(bundlesKey)).not.toBe(serializeQueryKey(bundleA));
    expect(serializeQueryKey(bundleA)).not.toBe(serializeQueryKey(bundleB));
    expect(serializeQueryKey(bundleA)).not.toBe(
      serializeQueryKey(bundleStatusKey)
    );
    expect(serializeQueryKey(bundleStatusKey)).not.toBe(
      serializeQueryKey(bundleEventsKey)
    );
    expect(serializeQueryKey(bundleEventsKey)).not.toBe(
      serializeQueryKey(bundleVerificationKey)
    );
    expect(serializeQueryKey(bundleVerificationKey)).not.toBe(
      serializeQueryKey(bundleVerificationStatusKey)
    );
    expect(serializeQueryKey(bundleVerificationStatusKey)).not.toBe(
      serializeQueryKey(bundleVerificationRunsKey)
    );
    expect(serializeQueryKey(bundleVerificationRunsKey)).not.toBe(
      serializeQueryKey(bundleVerificationRunAKey)
    );
    expect(serializeQueryKey(bundleVerificationRunAKey)).not.toBe(
      serializeQueryKey(bundleVerificationRunBKey)
    );
    expect(serializeQueryKey(bundleVerificationRunAKey)).not.toBe(
      serializeQueryKey(bundleVerificationRunStatusKey)
    );
    expect(serializeQueryKey(bundleVerificationRunStatusKey)).not.toBe(
      serializeQueryKey(bundleProfilesKey)
    );
    expect(serializeQueryKey(bundleProfilesKey)).not.toBe(
      serializeQueryKey(bundleValidationStatusKey)
    );
    expect(serializeQueryKey(bundleValidationStatusKey)).not.toBe(
      serializeQueryKey(bundleValidationRunsKey)
    );
    expect(serializeQueryKey(bundleValidationRunsKey)).not.toBe(
      serializeQueryKey(bundleValidationRunAKey)
    );
    expect(serializeQueryKey(bundleValidationRunAKey)).not.toBe(
      serializeQueryKey(bundleValidationRunStatusKey)
    );
    expect(serializeQueryKey(reviewQueueAll)).not.toBe(
      serializeQueryKey(reviewQueueFiltered)
    );
  });
});
