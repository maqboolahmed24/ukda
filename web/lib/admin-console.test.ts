import { describe, expect, it } from "vitest";

import type { SessionResponse } from "@ukde/contracts";

import {
  resolveAdminContextLinks,
  resolveAdminRoleMode,
  resolveAdminSurfaces
} from "./admin-console";

const adminSession: SessionResponse = {
  session: {
    expiresAt: "2026-03-14T00:00:00Z",
    id: "session-admin"
  },
  user: {
    displayName: "Admin",
    email: "admin@example.com",
    id: "user-admin",
    platformRoles: ["ADMIN"],
    sub: "oidc|admin"
  }
};

const auditorSession: SessionResponse = {
  session: {
    expiresAt: "2026-03-14T00:00:00Z",
    id: "session-auditor"
  },
  user: {
    displayName: "Auditor",
    email: "auditor@example.com",
    id: "user-auditor",
    platformRoles: ["AUDITOR"],
    sub: "oidc|auditor"
  }
};

describe("admin console role matrix", () => {
  it("exposes operations overview only to admins", () => {
    const adminItems = resolveAdminSurfaces(adminSession);
    const auditorItems = resolveAdminSurfaces(auditorSession);

    expect(adminItems.some((item) => item.id === "admin.operations")).toBe(
      true
    );
    expect(auditorItems.some((item) => item.id === "admin.operations")).toBe(
      false
    );
  });

  it("keeps export-status and timelines visible to auditors", () => {
    const auditorItems = resolveAdminSurfaces(auditorSession);
    expect(
      auditorItems.some((item) => item.id === "admin.operations.export-status")
    ).toBe(true);
    expect(
      auditorItems.some((item) => item.id === "admin.operations.timelines")
    ).toBe(true);
  });

  it("keeps context links aligned with visible surfaces", () => {
    const links = resolveAdminContextLinks(auditorSession);
    const hrefs = links.map((link) => link.href);
    expect(hrefs).toContain("/admin/audit");
    expect(hrefs).toContain("/admin/operations/export-status");
    expect(hrefs).not.toContain("/admin/operations");
  });

  it("resolves admin role mode deterministically", () => {
    expect(resolveAdminRoleMode(adminSession).label).toBe("ADMIN");
    expect(resolveAdminRoleMode(auditorSession).label).toBe("AUDITOR");
  });
});
