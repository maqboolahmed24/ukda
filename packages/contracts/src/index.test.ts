import { describe, expect, it } from "vitest";

import {
  type AuditEventType,
  bootstrapShellStates,
  bootstrapSurfaces,
  resolveAdaptiveShellState,
  resolveShellState
} from "./index";

describe("@ukde/contracts", () => {
  it("exports the canonical shell states in order", () => {
    expect(bootstrapShellStates).toEqual([
      "Expanded",
      "Balanced",
      "Compact",
      "Focus"
    ]);
  });

  it("keeps the design system route available to the shell", () => {
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/admin/design-system"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some((surface) => surface.route === "/auth/callback")
    ).toBe(true);
    expect(
      bootstrapSurfaces.some((surface) => surface.route === "/logout")
    ).toBe(true);
    expect(
      bootstrapSurfaces.some((surface) => surface.route === "/activity")
    ).toBe(true);
    expect(
      bootstrapSurfaces.some((surface) => surface.route === "/admin/audit")
    ).toBe(true);
    expect(
      bootstrapSurfaces.some((surface) => surface.route === "/admin/operations")
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/admin/operations/slos"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/admin/operations/alerts"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/admin/operations/timelines"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/admin/audit/:eventId"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/projects/:projectId/settings"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some((surface) => surface.route === "/approved-models")
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/projects/:projectId/model-assignments"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route ===
          "/projects/:projectId/model-assignments/:assignmentId"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route ===
          "/projects/:projectId/model-assignments/:assignmentId/datasets"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/projects/:projectId/jobs/:jobId"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/projects/:projectId/documents"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/projects/:projectId/documents/import"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/projects/:projectId/documents/:documentId"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route ===
          "/projects/:projectId/documents/:documentId/ingest-status"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route ===
          "/projects/:projectId/documents/:documentId/preprocessing"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route ===
          "/projects/:projectId/documents/:documentId/preprocessing/quality"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route ===
          "/projects/:projectId/documents/:documentId/preprocessing/runs/:runId"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route ===
          "/projects/:projectId/documents/:documentId/preprocessing/compare"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route === "/projects/:projectId/documents/:documentId/layout"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route ===
          "/projects/:projectId/documents/:documentId/layout/runs/:runId"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route ===
          "/projects/:projectId/documents/:documentId/layout/workspace"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route ===
          "/projects/:projectId/documents/:documentId/transcription"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route ===
          "/projects/:projectId/documents/:documentId/transcription/runs/:runId"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) =>
          surface.route ===
          "/projects/:projectId/documents/:documentId/transcription/workspace"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/projects/:projectId/export-candidates"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/projects/:projectId/export-requests"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/projects/:projectId/export-review"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some((surface) => surface.route === "/admin/security")
    ).toBe(true);
  });

  it("routes smaller viewports into Focus state", () => {
    expect(resolveShellState(740)).toBe("Focus");
    expect(resolveShellState(900)).toBe("Compact");
    expect(resolveShellState(1200)).toBe("Balanced");
    expect(resolveShellState(1500)).toBe("Expanded");
  });

  it("derives adaptive shell state from width, height, and task context", () => {
    expect(
      resolveAdaptiveShellState({
        viewportWidth: 1500,
        viewportHeight: 700,
        taskContext: "standard"
      })
    ).toBe("Compact");
    expect(
      resolveAdaptiveShellState({
        viewportWidth: 930,
        viewportHeight: 820,
        taskContext: "dense"
      })
    ).toBe("Focus");
    expect(
      resolveAdaptiveShellState({
        viewportWidth: 1400,
        viewportHeight: 920,
        forceFocus: true,
        taskContext: "standard"
      })
    ).toBe("Focus");
  });

  it("includes core audit event contracts", () => {
    const required: AuditEventType[] = [
      "USER_LOGIN",
      "PROJECT_CREATED",
      "PROJECT_MEMBER_ADDED",
      "AUDIT_LOG_VIEWED",
      "MY_ACTIVITY_VIEWED",
      "DOCUMENT_LIBRARY_VIEWED",
      "DOCUMENT_DETAIL_VIEWED",
      "DOCUMENT_TIMELINE_VIEWED",
      "DOCUMENT_UPLOAD_STARTED",
      "DOCUMENT_SCAN_STARTED",
      "DOCUMENT_IMPORT_FAILED",
      "PREPROCESS_RUN_CREATED",
      "LAYOUT_RUN_CREATED",
      "TRANSCRIPTION_RUN_CREATED",
      "APPROVED_MODEL_CREATED",
      "PROJECT_MODEL_ASSIGNMENT_CREATED",
      "PROJECT_MODEL_ACTIVATED",
      "PROJECT_MODEL_RETIRED"
    ];
    expect(required.length).toBe(18);
  });
});
