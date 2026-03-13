import type {
  AccessTier,
  DeploymentEnvironment,
  ProjectRole,
  ShellState
} from "@ukde/contracts";

export * from "./theme";
export * from "./tokens";

export const shellStateNotes: Record<ShellState, string> = {
  Expanded:
    "Rail, workspace, and inspector remain visible for dense review work.",
  Balanced:
    "The workspace stays dominant while secondary context compresses to summaries.",
  Compact:
    "Navigation and inspection move to compact affordances without losing object focus.",
  Focus:
    "The active review surface takes priority while supporting context becomes on-demand."
};

export const designPillars = [
  "Dark-first, research-grade surfaces",
  "Bounded work regions instead of page sprawl",
  "Visible confidence, provenance, and governance state",
  "Keyboard-first interaction with explicit focus"
] as const;

export const accessTierLabels: Record<AccessTier, string> = {
  CONTROLLED: "Controlled",
  SAFEGUARDED: "Safeguarded",
  OPEN: "Open"
};

export const accessTierBadgeTones: Record<
  AccessTier,
  "success" | "warning" | "default"
> = {
  CONTROLLED: "warning",
  SAFEGUARDED: "success",
  OPEN: "default"
};

export const environmentLabels: Record<DeploymentEnvironment, string> = {
  dev: "Development",
  staging: "Staging",
  prod: "Production",
  test: "Test"
};

export const projectRoleLabels: Record<ProjectRole, string> = {
  PROJECT_LEAD: "Project lead",
  RESEARCHER: "Researcher",
  REVIEWER: "Reviewer"
};
