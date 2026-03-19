import type { PlatformRole, ProjectSummary, SessionResponse } from "@ukde/contracts";

import {
  activityPath,
  adminAuditPath,
  adminCapacityTestsPath,
  adminDesignSystemPath,
  adminIncidentStatusPath,
  adminIncidentsPath,
  adminIndexQualityPath,
  adminIndexQualityQueryAuditsBasePath,
  adminOperationsExportStatusPath,
  adminOperationsReadinessPath,
  adminOperationsAlertsPath,
  adminOperationsPath,
  adminOperationsSlosPath,
  adminOperationsTimelinesPath,
  adminRecoveryDrillsPath,
  adminRecoveryStatusPath,
  adminRunbooksPath,
  adminSecurityFindingsPath,
  adminSecurityRiskAcceptancesPath,
  adminPath,
  adminSecurityPath,
  approvedModelsPath,
  healthPath,
  projectActivityPath,
  projectAnchorPath,
  projectDerivativesPath,
  projectDocumentImportPath,
  projectDocumentsPath,
  projectEntitiesPath,
  projectIndexesPath,
  projectJobsPath,
  projectModelAssignmentsPath,
  projectPoliciesPath,
  projectPseudonymRegistryPath,
  projectSearchPath,
  projectOverviewPath,
  projectSettingsPath,
  projectsPath
} from "./routes";

export type CommandScope =
  | "global"
  | "authenticated"
  | "project"
  | "admin"
  | "workspace";

export type CommandGroup =
  | "Navigate"
  | "Projects"
  | "Workspace"
  | "Admin"
  | "Help";

export interface CommandDefinition {
  description?: string;
  group: CommandGroup;
  href: string;
  id: string;
  keywords: string[];
  label: string;
  scope: CommandScope;
}

interface BaseCommandSpec {
  description?: string;
  group: CommandGroup;
  id: string;
  keywords: string[];
  label: string;
  requiresAnyPlatformRole?: PlatformRole[];
  requiresCurrentProject?: boolean;
  requiresProjectMembership?: boolean;
  requiresSettingsAccess?: boolean;
  resolveHref: (context: CommandRegistryContext) => string | null;
  scope: CommandScope;
}

export interface CommandRegistryContext {
  currentProject: ProjectSummary | null;
  pathname: string;
  projects: ProjectSummary[];
  session: SessionResponse;
}

const BASE_COMMAND_SPECS: BaseCommandSpec[] = [
  {
    group: "Navigate",
    id: "navigate.projects",
    keywords: ["workspace", "projects", "index", "home"],
    label: "Go to projects",
    resolveHref: () => projectsPath,
    scope: "authenticated"
  },
  {
    group: "Navigate",
    id: "navigate.activity",
    keywords: ["activity", "audit", "history"],
    label: "Open my activity",
    resolveHref: () => activityPath,
    scope: "authenticated"
  },
  {
    group: "Navigate",
    id: "navigate.approved-models",
    keywords: ["approved", "models", "catalog", "role-map"],
    label: "Open approved models",
    resolveHref: () => approvedModelsPath,
    scope: "authenticated"
  },
  {
    description: "Open the current project overview surface.",
    group: "Workspace",
    id: "project.overview",
    keywords: ["project", "overview", "workspace"],
    label: "Open project overview",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectOverviewPath(currentProject.id) : null,
    scope: "project"
  },
  {
    description: "Open document library and current document queues.",
    group: "Workspace",
    id: "project.documents",
    keywords: ["project", "documents", "library"],
    label: "Open project documents",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectDocumentsPath(currentProject.id) : null,
    scope: "project"
  },
  {
    description: "Run the controlled import flow for this project.",
    group: "Workspace",
    id: "project.documents.import",
    keywords: ["project", "documents", "import", "upload"],
    label: "Import documents",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectDocumentImportPath(currentProject.id) : null,
    scope: "workspace"
  },
  {
    description: "Manage project role-to-model assignments and lifecycle state.",
    group: "Workspace",
    id: "project.model-assignments",
    keywords: ["project", "models", "assignments", "catalog"],
    label: "Open model assignments",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectModelAssignmentsPath(currentProject.id) : null,
    scope: "project"
  },
  {
    description: "Open project full-text search and hit provenance surface.",
    group: "Workspace",
    id: "project.search",
    keywords: ["project", "search", "query", "results", "tokens"],
    label: "Open project search",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectSearchPath(currentProject.id) : null,
    scope: "project"
  },
  {
    description:
      "Open governed entity discovery with active generation lineage and occurrence provenance.",
    group: "Workspace",
    id: "project.entities",
    keywords: ["project", "entities", "entity", "occurrences", "lineage"],
    label: "Open entities",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectEntitiesPath(currentProject.id) : null,
    scope: "project"
  },
  {
    description:
      "Open safeguarded derivative snapshots, suppression metadata, and candidate-freeze controls.",
    group: "Workspace",
    id: "project.derivatives",
    keywords: ["project", "derivatives", "safeguarded", "suppression", "preview"],
    label: "Open derivatives",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectDerivativesPath(currentProject.id) : null,
    scope: "project"
  },
  {
    description:
      "Open versioned search/entity/derivative index lineage and active projection controls.",
    group: "Workspace",
    id: "project.indexes",
    keywords: ["project", "indexes", "search", "entity", "derivative"],
    label: "Open indexes",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectIndexesPath(currentProject.id) : null,
    scope: "project"
  },
  {
    description: "Open policy lineage, validation, compare, and activation surfaces.",
    group: "Workspace",
    id: "project.policies",
    keywords: ["project", "policies", "lineage", "compare", "validation"],
    label: "Open policies",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectPoliciesPath(currentProject.id) : null,
    scope: "project"
  },
  {
    description:
      "Open controlled-only pseudonym registry entries and lineage events.",
    group: "Workspace",
    id: "project.pseudonym-registry",
    keywords: ["project", "pseudonym", "registry", "aliasing", "lineage"],
    label: "Open pseudonym registry",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectPseudonymRegistryPath(currentProject.id) : null,
    scope: "project"
  },
  {
    group: "Workspace",
    id: "project.jobs",
    keywords: ["project", "jobs", "runs", "queue"],
    label: "Open project jobs",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectJobsPath(currentProject.id) : null,
    scope: "project"
  },
  {
    group: "Workspace",
    id: "project.activity",
    keywords: ["project", "activity", "events"],
    label: "Open project activity",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectActivityPath(currentProject.id) : null,
    scope: "project"
  },
  {
    group: "Workspace",
    id: "project.settings",
    keywords: ["project", "settings", "members"],
    label: "Open project settings",
    requiresCurrentProject: true,
    requiresProjectMembership: true,
    requiresSettingsAccess: true,
    resolveHref: ({ currentProject }) =>
      currentProject ? projectSettingsPath(currentProject.id) : null,
    scope: "project"
  },
  {
    group: "Navigate",
    id: "navigate.admin",
    keywords: ["admin", "governance", "overview"],
    label: "Open admin overview",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.audit",
    keywords: ["admin", "audit", "events", "governance"],
    label: "Open admin audit",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminAuditPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.runbooks",
    keywords: ["admin", "runbooks", "rollback", "procedures", "launch"],
    label: "Open runbooks",
    requiresAnyPlatformRole: ["ADMIN"],
    resolveHref: () => adminRunbooksPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.incidents",
    keywords: ["admin", "incidents", "launch", "timeline", "command"],
    label: "Open incidents",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminIncidentsPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.incidents.status",
    keywords: ["admin", "incidents", "status", "no-go", "severity"],
    label: "Open incident status",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminIncidentStatusPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.index-quality",
    keywords: ["admin", "index", "quality", "freshness", "rollback"],
    label: "Open index quality",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminIndexQualityPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.index-quality.query-audits",
    keywords: ["admin", "index", "quality", "search", "query", "audits"],
    label: "Open index query audits",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminIndexQualityQueryAuditsBasePath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.security",
    keywords: ["admin", "security", "status"],
    label: "Open admin security",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminSecurityPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.security.findings",
    keywords: ["admin", "security", "findings", "pen-test", "remediation"],
    label: "Open security findings",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminSecurityFindingsPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.security.risk-acceptances",
    keywords: ["admin", "security", "risk", "acceptances"],
    label: "Open risk acceptances",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminSecurityRiskAcceptancesPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.operations.readiness",
    keywords: ["admin", "operations", "readiness", "audit", "evidence"],
    label: "Open operations readiness",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminOperationsReadinessPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.operations.export-status",
    keywords: ["admin", "operations", "export", "status", "review"],
    label: "Open operations export status",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminOperationsExportStatusPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.operations",
    keywords: ["admin", "operations", "dashboard"],
    label: "Open admin operations",
    requiresAnyPlatformRole: ["ADMIN"],
    resolveHref: () => adminOperationsPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.operations.slos",
    keywords: ["admin", "operations", "slos", "latency", "reliability"],
    label: "Open operations SLOs",
    requiresAnyPlatformRole: ["ADMIN"],
    resolveHref: () => adminOperationsSlosPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.operations.alerts",
    keywords: ["admin", "operations", "alerts"],
    label: "Open operations alerts",
    requiresAnyPlatformRole: ["ADMIN"],
    resolveHref: () => adminOperationsAlertsPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.operations.timelines",
    keywords: ["admin", "operations", "timelines", "audit"],
    label: "Open operations timelines",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminOperationsTimelinesPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.capacity.tests",
    keywords: ["admin", "capacity", "benchmark", "load", "soak", "p95"],
    label: "Open capacity tests",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminCapacityTestsPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.recovery.status",
    keywords: ["admin", "recovery", "status", "degraded", "restore"],
    label: "Open recovery status",
    requiresAnyPlatformRole: ["ADMIN"],
    resolveHref: () => adminRecoveryStatusPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.recovery.drills",
    keywords: ["admin", "recovery", "drills", "evidence", "restore"],
    label: "Open recovery drills",
    requiresAnyPlatformRole: ["ADMIN"],
    resolveHref: () => adminRecoveryDrillsPath,
    scope: "admin"
  },
  {
    group: "Admin",
    id: "admin.design-system",
    keywords: ["admin", "design", "system", "gallery", "diagnostics"],
    label: "Open design-system diagnostics",
    requiresAnyPlatformRole: ["ADMIN", "AUDITOR"],
    resolveHref: () => adminDesignSystemPath,
    scope: "admin"
  },
  {
    description: "Operational health and support pointers.",
    group: "Help",
    id: "help.health",
    keywords: ["help", "health", "support", "diagnostics"],
    label: "Open help and service status",
    resolveHref: () => healthPath,
    scope: "global"
  }
];

const PROJECT_SECTION_PATHS = [
  "overview",
  "documents",
  "documents/import",
  "search",
  "entities",
  "derivatives",
  "model-assignments",
  "indexes",
  "policies",
  "pseudonym-registry",
  "jobs",
  "activity",
  "settings",
  "export-candidates",
  "export-requests",
  "export-review"
] as const;

function hasAnyPlatformRole(
  session: SessionResponse,
  required: PlatformRole[] | undefined
): boolean {
  if (!required || required.length === 0) {
    return true;
  }
  const current = new Set(session.user.platformRoles);
  return required.some((role) => current.has(role));
}

function resolveCurrentProjectSection(pathname: string): string | null {
  if (!pathname.startsWith("/projects/")) {
    return null;
  }
  const normalizedPath = pathname.split(/[?#]/, 1)[0] ?? pathname;
  const normalized = normalizedPath.replace(/\/+$/, "");
  const segments = normalized.split("/").filter(Boolean);
  if (segments[0] !== "projects" || !segments[1]) {
    return null;
  }
  if (segments.length <= 2) {
    return "overview";
  }

  const section = segments[2];
  if (section === "documents" && segments[3] === "import") {
    return "documents/import";
  }

  if (PROJECT_SECTION_PATHS.includes(section as (typeof PROJECT_SECTION_PATHS)[number])) {
    return section;
  }

  if (
    section === "documents" ||
    section === "model-assignments" ||
    section === "derivatives" ||
    section === "indexes" ||
    section === "policies" ||
    section === "pseudonym-registry" ||
    section === "jobs" ||
    section === "activity" ||
    section === "overview" ||
    section === "settings" ||
    section === "export-candidates" ||
    section === "export-requests" ||
    section === "export-review"
  ) {
    return section;
  }

  return null;
}

function resolveSectionPathForProject(
  section: string | null,
  targetProject: ProjectSummary
): string {
  switch (section) {
    case "overview":
      return projectOverviewPath(targetProject.id);
    case "documents":
      return projectDocumentsPath(targetProject.id);
    case "documents/import":
      return projectDocumentImportPath(targetProject.id);
    case "search":
      return projectSearchPath(targetProject.id);
    case "entities":
      return projectEntitiesPath(targetProject.id);
    case "derivatives":
      return projectDerivativesPath(targetProject.id);
    case "model-assignments":
      return projectModelAssignmentsPath(targetProject.id);
    case "indexes":
      return projectIndexesPath(targetProject.id);
    case "policies":
      return projectPoliciesPath(targetProject.id);
    case "pseudonym-registry":
      return projectPseudonymRegistryPath(targetProject.id);
    case "jobs":
      return projectJobsPath(targetProject.id);
    case "activity":
      return projectActivityPath(targetProject.id);
    case "settings":
      return targetProject.canAccessSettings
        ? projectSettingsPath(targetProject.id)
        : projectOverviewPath(targetProject.id);
    case "export-candidates":
    case "export-requests":
    case "export-review":
      return `${projectAnchorPath(targetProject.id)}/${section}`;
    default:
      return projectOverviewPath(targetProject.id);
  }
}

export function resolveProjectSwitchHref(
  pathname: string,
  targetProject: ProjectSummary
): string {
  const section = resolveCurrentProjectSection(pathname);
  return resolveSectionPathForProject(section, targetProject);
}

function buildBaseCommands(
  context: CommandRegistryContext
): CommandDefinition[] {
  return BASE_COMMAND_SPECS.flatMap((spec) => {
    if (!hasAnyPlatformRole(context.session, spec.requiresAnyPlatformRole)) {
      return [];
    }
    if (spec.requiresCurrentProject && !context.currentProject) {
      return [];
    }
    if (
      spec.requiresProjectMembership &&
      !context.currentProject?.isMember
    ) {
      return [];
    }
    if (spec.requiresSettingsAccess && !context.currentProject?.canAccessSettings) {
      return [];
    }

    const href = spec.resolveHref(context);
    if (!href) {
      return [];
    }

    return [
      {
        description: spec.description,
        group: spec.group,
        href,
        id: spec.id,
        keywords: spec.keywords,
        label: spec.label,
        scope: spec.scope
      }
    ];
  });
}

function buildProjectSwitchCommands(
  context: CommandRegistryContext
): CommandDefinition[] {
  const sortedProjects = [...context.projects].sort((a, b) =>
    a.name.localeCompare(b.name)
  );
  return sortedProjects.map((project) => {
    const membershipLabel = project.currentUserRole
      ? project.currentUserRole.replaceAll("_", " ").toLowerCase()
      : "member";
    const isCurrent = context.currentProject?.id === project.id;
    return {
      description: `Tier ${project.intendedAccessTier} · ${membershipLabel}${
        isCurrent ? " · current project" : ""
      }`,
      group: "Projects",
      href: resolveProjectSwitchHref(context.pathname, project),
      id: `project.switch.${project.id}`,
      keywords: [
        "project",
        "switch",
        project.name,
        project.intendedAccessTier,
        project.currentUserRole ?? "member",
        isCurrent ? "current" : "workspace"
      ],
      label: `Switch to ${project.name}`,
      scope: "project"
    } satisfies CommandDefinition;
  });
}

export function buildCommandRegistry(
  context: CommandRegistryContext
): CommandDefinition[] {
  return [...buildBaseCommands(context), ...buildProjectSwitchCommands(context)];
}

export function filterCommands(
  commands: CommandDefinition[],
  query: string
): CommandDefinition[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return commands;
  }

  const parts = normalized.split(/\s+/).filter(Boolean);
  return commands.filter((command) => {
    const searchField = [
      command.label,
      command.description,
      command.group,
      command.scope,
      command.keywords.join(" ")
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return parts.every((part) => searchField.includes(part));
  });
}

export function groupCommands(
  commands: CommandDefinition[]
): Array<{ group: CommandGroup; items: CommandDefinition[] }> {
  const byGroup = new Map<CommandGroup, CommandDefinition[]>();

  for (const command of commands) {
    const existing = byGroup.get(command.group);
    if (existing) {
      existing.push(command);
    } else {
      byGroup.set(command.group, [command]);
    }
  }

  return Array.from(byGroup.entries()).map(([group, items]) => ({
    group,
    items
  }));
}
