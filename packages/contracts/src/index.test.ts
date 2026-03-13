import { describe, expect, it } from "vitest";

import {
  type AuditEventType,
  bootstrapShellStates,
  bootstrapSurfaces,
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
      bootstrapSurfaces.some(
        (surface) => surface.route === "/projects/:projectId/jobs/:jobId"
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

  it("includes core audit event contracts", () => {
    const required: AuditEventType[] = [
      "USER_LOGIN",
      "PROJECT_CREATED",
      "PROJECT_MEMBER_ADDED",
      "AUDIT_LOG_VIEWED",
      "MY_ACTIVITY_VIEWED"
    ];
    expect(required.length).toBe(5);
  });
});
