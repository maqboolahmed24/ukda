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
});
