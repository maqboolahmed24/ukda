import { describe, expect, it } from "vitest";

import type { ProjectSummary, SessionResponse } from "@ukde/contracts";

import {
  buildCommandRegistry,
  filterCommands,
  resolveProjectSwitchHref
} from "./command-registry";

const baseSession: SessionResponse = {
  session: {
    expiresAt: "2026-03-13T23:59:59Z",
    id: "session-1"
  },
  user: {
    displayName: "Ada Lovelace",
    email: "ada@example.com",
    id: "user-1",
    platformRoles: [],
    sub: "oidc|ada"
  }
};

const projectA: ProjectSummary = {
  baselinePolicySnapshotId: "baseline-a",
  canAccessSettings: true,
  canManageMembers: true,
  createdAt: "2026-03-12T00:00:00Z",
  createdBy: "user-1",
  currentUserRole: "PROJECT_LEAD",
  id: "project-a",
  intendedAccessTier: "CONTROLLED",
  isMember: true,
  name: "Archive A",
  purpose: "Testing",
  status: "ACTIVE"
};

const projectB: ProjectSummary = {
  baselinePolicySnapshotId: "baseline-b",
  canAccessSettings: false,
  canManageMembers: false,
  createdAt: "2026-03-12T00:00:00Z",
  createdBy: "user-1",
  currentUserRole: "RESEARCHER",
  id: "project-b",
  intendedAccessTier: "SAFEGUARDED",
  isMember: true,
  name: "Archive B",
  purpose: "Testing",
  status: "ACTIVE"
};

describe("command registry", () => {
  it("hides admin-only commands for non-admin users", () => {
    const commands = buildCommandRegistry({
      currentProject: projectA,
      pathname: "/projects/project-a/overview",
      projects: [projectA, projectB],
      session: baseSession
    });

    expect(commands.some((command) => command.id === "admin.operations")).toBe(
      false
    );
    expect(commands.some((command) => command.id === "admin.audit")).toBe(
      false
    );
  });

  it("shows read-only governance commands for auditors and admin-only routes for admins", () => {
    const auditorSession: SessionResponse = {
      ...baseSession,
      user: {
        ...baseSession.user,
        platformRoles: ["AUDITOR"]
      }
    };

    const adminSession: SessionResponse = {
      ...baseSession,
      user: {
        ...baseSession.user,
        platformRoles: ["ADMIN"]
      }
    };

    const auditorCommands = buildCommandRegistry({
      currentProject: projectA,
      pathname: "/projects/project-a/overview",
      projects: [projectA],
      session: auditorSession
    });

    const adminCommands = buildCommandRegistry({
      currentProject: projectA,
      pathname: "/projects/project-a/overview",
      projects: [projectA],
      session: adminSession
    });

    expect(
      auditorCommands.some(
        (command) => command.id === "admin.operations.timelines"
      )
    ).toBe(true);
    expect(
      auditorCommands.some(
        (command) => command.id === "admin.operations.export-status"
      )
    ).toBe(true);
    expect(
      auditorCommands.some((command) => command.id === "admin.operations")
    ).toBe(false);
    expect(
      adminCommands.some((command) => command.id === "admin.operations")
    ).toBe(true);
  });

  it("filters command labels and keywords deterministically", () => {
    const commands = buildCommandRegistry({
      currentProject: projectA,
      pathname: "/projects/project-a/documents",
      projects: [projectA],
      session: baseSession
    });
    const filtered = filterCommands(commands, "import documents");
    expect(filtered.map((command) => command.id)).toEqual([
      "project.documents.import"
    ]);
  });

  it("preserves the nearest section when switching projects", () => {
    const target = resolveProjectSwitchHref(
      "/projects/project-a/documents/import",
      projectB
    );
    expect(target).toBe("/projects/project-b/documents/import");
  });

  it("falls back to overview when switching into project without settings access", () => {
    const target = resolveProjectSwitchHref(
      "/projects/project-a/settings",
      projectB
    );
    expect(target).toBe("/projects/project-b/overview");
  });
});
