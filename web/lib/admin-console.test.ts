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
      auditorItems.some((item) => item.id === "admin.operations.readiness")
    ).toBe(true);
    expect(
      auditorItems.some((item) => item.id === "admin.operations.export-status")
    ).toBe(true);
    expect(auditorItems.some((item) => item.id === "admin.incidents")).toBe(
      true
    );
    expect(
      auditorItems.some((item) => item.id === "admin.incidents.status")
    ).toBe(true);
    expect(auditorItems.some((item) => item.id === "admin.runbooks")).toBe(
      false
    );
    expect(
      auditorItems.some((item) => item.id === "admin.operations.timelines")
    ).toBe(true);
    expect(
      auditorItems.some((item) => item.id === "admin.capacity.tests")
    ).toBe(true);
    expect(
      auditorItems.some((item) => item.id === "admin.recovery.status")
    ).toBe(false);
    expect(
      auditorItems.some((item) => item.id === "admin.recovery.drills")
    ).toBe(false);
    expect(
      auditorItems.some((item) => item.id === "admin.index-quality")
    ).toBe(true);
    expect(
      auditorItems.some((item) => item.id === "admin.index-quality.query-audits")
    ).toBe(true);
    expect(
      auditorItems.some((item) => item.id === "admin.security.findings")
    ).toBe(true);
    expect(
      auditorItems.some((item) => item.id === "admin.security.risk-acceptances")
    ).toBe(true);
  });

  it("keeps context links aligned with visible surfaces", () => {
    const links = resolveAdminContextLinks(auditorSession);
    const hrefs = links.map((link) => link.href);
    expect(hrefs).toContain("/admin/audit");
    expect(hrefs).toContain("/admin/index-quality");
    expect(hrefs).toContain("/admin/index-quality/query-audits");
    expect(hrefs).toContain("/admin/security/findings");
    expect(hrefs).toContain("/admin/security/risk-acceptances");
    expect(hrefs).toContain("/admin/operations/readiness");
    expect(hrefs).toContain("/admin/operations/export-status");
    expect(hrefs).toContain("/admin/incidents");
    expect(hrefs).toContain("/admin/incidents/status");
    expect(hrefs).not.toContain("/admin/runbooks");
    expect(hrefs).toContain("/admin/capacity/tests");
    expect(hrefs).not.toContain("/admin/recovery/status");
    expect(hrefs).not.toContain("/admin/recovery/drills");
    expect(hrefs).not.toContain("/admin/operations");
  });

  it("exposes recovery routes to admins only", () => {
    const adminItems = resolveAdminSurfaces(adminSession);
    const hrefs = adminItems.map((item) => item.href);
    expect(hrefs).toContain("/admin/recovery/status");
    expect(hrefs).toContain("/admin/recovery/drills");
    expect(hrefs).toContain("/admin/runbooks");
    expect(hrefs).toContain("/admin/incidents");
  });

  it("resolves admin role mode deterministically", () => {
    expect(resolveAdminRoleMode(adminSession).label).toBe("ADMIN");
    expect(resolveAdminRoleMode(auditorSession).label).toBe("AUDITOR");
  });
});
