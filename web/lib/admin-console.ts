import type { PlatformRole, SessionResponse } from "@ukde/contracts";

import {
  adminAuditPath,
  adminDesignSystemPath,
  adminOperationsExportStatusPath,
  adminOperationsPath,
  adminOperationsTimelinesPath,
  adminPath,
  adminSecurityPath
} from "./routes";

export type AdminSurfaceGroup =
  | "overview"
  | "governance"
  | "operations"
  | "internal";

export interface AdminSurfaceDefinition {
  allowedRoles: PlatformRole[];
  description: string;
  group: AdminSurfaceGroup;
  href: string;
  id: string;
  label: string;
  readOnlyForAuditor?: boolean;
}

const ADMIN_SURFACE_DEFINITIONS: AdminSurfaceDefinition[] = [
  {
    allowedRoles: ["ADMIN", "AUDITOR"],
    description: "Role-aware platform governance overview and module entrypoint.",
    group: "overview",
    href: adminPath,
    id: "admin.overview",
    label: "Overview"
  },
  {
    allowedRoles: ["ADMIN", "AUDITOR"],
    description: "Append-only audit log exploration and event-detail drilldown.",
    group: "governance",
    href: adminAuditPath,
    id: "admin.audit",
    label: "Audit",
    readOnlyForAuditor: true
  },
  {
    allowedRoles: ["ADMIN", "AUDITOR"],
    description:
      "Controlled-environment security posture with read-only auditor visibility.",
    group: "governance",
    href: adminSecurityPath,
    id: "admin.security",
    label: "Security",
    readOnlyForAuditor: true
  },
  {
    allowedRoles: ["ADMIN", "AUDITOR"],
    description:
      "Read-only export-request throughput and release queue health summary.",
    group: "operations",
    href: adminOperationsExportStatusPath,
    id: "admin.operations.export-status",
    label: "Export status",
    readOnlyForAuditor: true
  },
  {
    allowedRoles: ["ADMIN"],
    description:
      "Operator-only telemetry posture and platform throughput diagnostics.",
    group: "operations",
    href: adminOperationsPath,
    id: "admin.operations",
    label: "Operations"
  },
  {
    allowedRoles: ["ADMIN", "AUDITOR"],
    description:
      "Read-only operational timeline with request and trace-level context.",
    group: "operations",
    href: adminOperationsTimelinesPath,
    id: "admin.operations.timelines",
    label: "Timelines",
    readOnlyForAuditor: true
  },
  {
    allowedRoles: ["ADMIN", "AUDITOR"],
    description:
      "Internal validation gallery for shell, primitives, and accessibility diagnostics.",
    group: "internal",
    href: adminDesignSystemPath,
    id: "admin.design-system",
    label: "Design system",
    readOnlyForAuditor: true
  }
];

export interface AdminRoleMode {
  isAdmin: boolean;
  isAuditor: boolean;
  label: "ADMIN" | "AUDITOR";
}

function hasAnyRole(
  session: SessionResponse,
  requiredRoles: PlatformRole[]
): boolean {
  const available = new Set(session.user.platformRoles);
  return requiredRoles.some((role) => available.has(role));
}

export function resolveAdminRoleMode(session: SessionResponse): AdminRoleMode {
  const isAdmin = session.user.platformRoles.includes("ADMIN");
  return {
    isAdmin,
    isAuditor: !isAdmin && session.user.platformRoles.includes("AUDITOR"),
    label: isAdmin ? "ADMIN" : "AUDITOR"
  };
}

export function resolveAdminSurfaces(
  session: SessionResponse
): AdminSurfaceDefinition[] {
  return ADMIN_SURFACE_DEFINITIONS.filter((surface) =>
    hasAnyRole(session, surface.allowedRoles)
  );
}

export function resolveAdminSurfaceGroups(
  session: SessionResponse
): Array<{ group: AdminSurfaceGroup; items: AdminSurfaceDefinition[] }> {
  const surfaces = resolveAdminSurfaces(session);
  const byGroup = new Map<AdminSurfaceGroup, AdminSurfaceDefinition[]>();
  for (const surface of surfaces) {
    const existing = byGroup.get(surface.group);
    if (existing) {
      existing.push(surface);
    } else {
      byGroup.set(surface.group, [surface]);
    }
  }
  return Array.from(byGroup.entries()).map(([group, items]) => ({
    group,
    items
  }));
}

export function resolveAdminContextLinks(
  session: SessionResponse
): Array<{ href: string; label: string }> {
  return resolveAdminSurfaces(session).map((surface) => ({
    href: surface.href,
    label: surface.label
  }));
}
