import type { PlatformRole, SessionResponse } from "@ukde/contracts";

import {
  adminAuditPath,
  adminCapacityTestsPath,
  adminDesignSystemPath,
  adminIndexQualityPath,
  adminIndexQualityQueryAuditsBasePath,
  adminOperationsExportStatusPath,
  adminIncidentStatusPath,
  adminIncidentsPath,
  adminOperationsReadinessPath,
  adminOperationsPath,
  adminOperationsTimelinesPath,
  adminRecoveryDrillsPath,
  adminRecoveryStatusPath,
  adminRunbooksPath,
  adminSecurityFindingsPath,
  adminSecurityRiskAcceptancesPath,
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
      "Recall-first search activation readiness, freshness posture, and rollback visibility.",
    group: "governance",
    href: adminIndexQualityPath,
    id: "admin.index-quality",
    label: "Index quality",
    readOnlyForAuditor: true
  },
  {
    allowedRoles: ["ADMIN", "AUDITOR"],
    description:
      "Query-hash and controlled query-text-key audit stream for controlled search reads.",
    group: "governance",
    href: adminIndexQualityQueryAuditsBasePath,
    id: "admin.index-quality.query-audits",
    label: "Query audits",
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
      "Security findings intake/read surface with pen-test checklist and closure/acceptance posture.",
    group: "governance",
    href: adminSecurityFindingsPath,
    id: "admin.security.findings",
    label: "Security findings",
    readOnlyForAuditor: true
  },
  {
    allowedRoles: ["ADMIN", "AUDITOR"],
    description:
      "Risk-acceptance projection list and lifecycle detail with append-only events.",
    group: "governance",
    href: adminSecurityRiskAcceptancesPath,
    id: "admin.security.risk-acceptances",
    label: "Risk acceptances",
    readOnlyForAuditor: true
  },
  {
    allowedRoles: ["ADMIN", "AUDITOR"],
    description:
      "Cross-phase production-readiness matrix spanning accessibility, governance, privacy, provenance, egress, and discovery safety gates.",
    group: "operations",
    href: adminOperationsReadinessPath,
    id: "admin.operations.readiness",
    label: "Readiness",
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
      "Canonical launch and rollback runbooks with ownership and reviewed status.",
    group: "operations",
    href: adminRunbooksPath,
    id: "admin.runbooks",
    label: "Runbooks"
  },
  {
    allowedRoles: ["ADMIN", "AUDITOR"],
    description:
      "Read-only incident command timeline list for launch readiness and early-life operations.",
    group: "operations",
    href: adminIncidentsPath,
    id: "admin.incidents",
    label: "Incidents",
    readOnlyForAuditor: true
  },
  {
    allowedRoles: ["ADMIN", "AUDITOR"],
    description:
      "Incident no-go trigger summary and open-severity posture for launch decisions.",
    group: "operations",
    href: adminIncidentStatusPath,
    id: "admin.incidents.status",
    label: "Incident status",
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
      "Persisted benchmark/load/soak runs with p95 gates, envelope evidence, and artifacts.",
    group: "operations",
    href: adminCapacityTestsPath,
    id: "admin.capacity.tests",
    label: "Capacity tests",
    readOnlyForAuditor: true
  },
  {
    allowedRoles: ["ADMIN"],
    description:
      "Live recovery posture for degraded-mode state, queue replay readiness, and restore sequencing.",
    group: "operations",
    href: adminRecoveryStatusPath,
    id: "admin.recovery.status",
    label: "Recovery status"
  },
  {
    allowedRoles: ["ADMIN"],
    description:
      "Recovery drill execution records, evidence artifacts, and deterministic status transitions.",
    group: "operations",
    href: adminRecoveryDrillsPath,
    id: "admin.recovery.drills",
    label: "Recovery drills"
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
