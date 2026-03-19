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
        (command) => command.id === "admin.operations.readiness"
      )
    ).toBe(true);
    expect(
      auditorCommands.some((command) => command.id === "admin.incidents")
    ).toBe(true);
    expect(
      auditorCommands.some((command) => command.id === "admin.incidents.status")
    ).toBe(true);
    expect(
      auditorCommands.some((command) => command.id === "admin.runbooks")
    ).toBe(false);
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
      auditorCommands.some((command) => command.id === "admin.capacity.tests")
    ).toBe(true);
    expect(
      auditorCommands.some((command) => command.id === "admin.recovery.status")
    ).toBe(false);
    expect(
      auditorCommands.some((command) => command.id === "admin.recovery.drills")
    ).toBe(false);
    expect(
      auditorCommands.some((command) => command.id === "admin.operations")
    ).toBe(false);
    expect(
      auditorCommands.some((command) => command.id === "admin.index-quality")
    ).toBe(true);
    expect(
      auditorCommands.some(
        (command) => command.id === "admin.index-quality.query-audits"
      )
    ).toBe(true);
    expect(
      auditorCommands.some((command) => command.id === "admin.security.findings")
    ).toBe(true);
    expect(
      auditorCommands.some(
        (command) => command.id === "admin.security.risk-acceptances"
      )
    ).toBe(true);
    expect(
      adminCommands.some((command) => command.id === "admin.operations")
    ).toBe(true);
    expect(
      adminCommands.some((command) => command.id === "admin.recovery.status")
    ).toBe(true);
    expect(
      adminCommands.some((command) => command.id === "admin.recovery.drills")
    ).toBe(true);
    expect(
      adminCommands.some((command) => command.id === "admin.runbooks")
    ).toBe(true);
    expect(
      adminCommands.some((command) => command.id === "admin.incidents")
    ).toBe(true);
    expect(
      adminCommands.some((command) => command.id === "admin.incidents.status")
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

  it("preserves policy section when switching projects", () => {
    const target = resolveProjectSwitchHref(
      "/projects/project-a/policies/policy-1/compare?against=policy-0",
      projectB
    );
    expect(target).toBe("/projects/project-b/policies");
  });

  it("preserves pseudonym-registry section when switching projects", () => {
    const target = resolveProjectSwitchHref(
      "/projects/project-a/pseudonym-registry/entry-1/events",
      projectB
    );
    expect(target).toBe("/projects/project-b/pseudonym-registry");
  });

  it("preserves indexes section when switching projects", () => {
    const target = resolveProjectSwitchHref(
      "/projects/project-a/indexes/search/search-1",
      projectB
    );
    expect(target).toBe("/projects/project-b/indexes");
  });

  it("preserves search section when switching projects", () => {
    const target = resolveProjectSwitchHref(
      "/projects/project-a/search?q=archive",
      projectB
    );
    expect(target).toBe("/projects/project-b/search");
  });

  it("preserves entities section when switching projects", () => {
    const target = resolveProjectSwitchHref(
      "/projects/project-a/entities/entity-1",
      projectB
    );
    expect(target).toBe("/projects/project-b/entities");
  });

  it("preserves derivatives section when switching projects", () => {
    const target = resolveProjectSwitchHref(
      "/projects/project-a/derivatives/dersnap-1/preview",
      projectB
    );
    expect(target).toBe("/projects/project-b/derivatives");
  });

  it("falls back to overview when switching into project without settings access", () => {
    const target = resolveProjectSwitchHref(
      "/projects/project-a/settings",
      projectB
    );
    expect(target).toBe("/projects/project-b/overview");
  });
});
