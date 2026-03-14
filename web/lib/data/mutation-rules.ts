import {
  adminAuditPath,
  adminPath,
  projectDocumentIngestStatusPath,
  projectDocumentLayoutPath,
  projectDocumentLayoutRunPath,
  projectDocumentLayoutWorkspacePath,
  projectDocumentPath,
  projectDocumentPreprocessingPath,
  projectDocumentPreprocessingQualityPath,
  projectDocumentPreprocessingRunPath,
  projectDocumentTranscriptionPath,
  projectDocumentTranscriptionRunPath,
  projectDocumentTranscriptionWorkspacePath,
  projectDocumentViewerPath,
  projectDocumentsPath,
  projectJobPath,
  projectJobsPath,
  projectOverviewPath,
  projectSettingsPath,
  projectsPath
} from "../routes";

export type MutationRuleId =
  | "auth.login"
  | "auth.logout"
  | "projects.create"
  | "projects.members.add"
  | "projects.members.change-role"
  | "projects.members.remove"
  | "documents.import"
  | "documents.import.cancel"
  | "documents.layout.activate"
  | "documents.preprocess.activate"
  | "documents.transcription.activate"
  | "documents.retry-extraction"
  | "jobs.enqueue"
  | "jobs.retry"
  | "jobs.cancel";

export type MutationOptimism = "none";

export interface MutationRuleContext {
  createdProjectId?: string;
  documentId?: string;
  jobId?: string;
  projectId?: string;
  runId?: string;
}

export interface MutationRule {
  description: string;
  optimism: MutationOptimism;
  routeScope: "auth" | "project";
}

export const mutationRules: Record<MutationRuleId, MutationRule> = {
  "auth.login": {
    description:
      "Login changes session identity and permissions; all role-sensitive reads require fresh server truth.",
    optimism: "none",
    routeScope: "auth"
  },
  "auth.logout": {
    description:
      "Logout clears session boundaries and protected routes must be revalidated.",
    optimism: "none",
    routeScope: "auth"
  },
  "jobs.cancel": {
    description:
      "Job cancellation is operational and auditable. Show pending state until server confirmation.",
    optimism: "none",
    routeScope: "project"
  },
  "documents.import": {
    description:
      "Document import is security-sensitive and must wait for confirmed server validation and scan handoff.",
    optimism: "none",
    routeScope: "project"
  },
  "documents.import.cancel": {
    description:
      "Import cancellation is status-gated and auditable; UI should refresh from confirmed backend state.",
    optimism: "none",
    routeScope: "project"
  },
  "documents.retry-extraction": {
    description:
      "Extraction retry appends a new processing-run attempt with lineage; UI refresh follows confirmed backend state.",
    optimism: "none",
    routeScope: "project"
  },
  "documents.preprocess.activate": {
    description:
      "Preprocess activation updates canonical document defaults; dependent preprocessing and viewer surfaces must refresh from server truth.",
    optimism: "none",
    routeScope: "project"
  },
  "documents.layout.activate": {
    description:
      "Layout activation changes canonical layout projection and downstream transcription basis state; all activation-sensitive layout surfaces must refresh from server truth.",
    optimism: "none",
    routeScope: "project"
  },
  "documents.transcription.activate": {
    description:
      "Transcription activation updates canonical transcription projection and downstream redaction basis state; all projection-sensitive transcription surfaces must refresh from server truth.",
    optimism: "none",
    routeScope: "project"
  },
  "jobs.enqueue": {
    description:
      "Job enqueue changes queue and list state and is validated server-side before surface refresh.",
    optimism: "none",
    routeScope: "project"
  },
  "jobs.retry": {
    description:
      "Retry creates a new append-only run entry; server-confirmed result controls UI transitions.",
    optimism: "none",
    routeScope: "project"
  },
  "projects.create": {
    description:
      "Project creation changes membership-visible resources and must not appear optimistic before RBAC confirmation.",
    optimism: "none",
    routeScope: "project"
  },
  "projects.members.add": {
    description:
      "Membership changes are governance-sensitive and must only reflect confirmed backend writes.",
    optimism: "none",
    routeScope: "project"
  },
  "projects.members.change-role": {
    description:
      "Role updates affect RBAC truth and must never be optimistic.",
    optimism: "none",
    routeScope: "project"
  },
  "projects.members.remove": {
    description:
      "Membership removal is governance-sensitive and requires server confirmation before updating UI state.",
    optimism: "none",
    routeScope: "project"
  }
};

export function resolveMutationRevalidationPaths(
  mutationId: MutationRuleId,
  context: MutationRuleContext
): string[] {
  switch (mutationId) {
    case "auth.login":
    case "auth.logout":
      return [projectsPath, adminPath, adminAuditPath, "/activity"];
    case "projects.create":
      return context.createdProjectId
        ? [
            projectsPath,
            projectOverviewPath(context.createdProjectId),
            projectSettingsPath(context.createdProjectId),
            projectJobsPath(context.createdProjectId)
          ]
        : [projectsPath];
    case "projects.members.add":
    case "projects.members.change-role":
    case "projects.members.remove":
      return context.projectId
        ? [
            projectsPath,
            projectOverviewPath(context.projectId),
            projectSettingsPath(context.projectId)
          ]
        : [projectsPath];
    case "jobs.enqueue":
      return context.projectId
        ? [
            projectJobsPath(context.projectId),
            ...(context.jobId
              ? [projectJobPath(context.projectId, context.jobId)]
              : [])
          ]
        : [];
    case "documents.import":
    case "documents.import.cancel":
      return context.projectId
        ? [
            projectDocumentsPath(context.projectId),
            ...(context.documentId
              ? [projectDocumentPath(context.projectId, context.documentId)]
              : [])
          ]
        : [];
    case "documents.retry-extraction":
      return context.projectId && context.documentId
        ? [
            projectDocumentsPath(context.projectId),
            projectDocumentPath(context.projectId, context.documentId),
            projectDocumentIngestStatusPath(context.projectId, context.documentId)
          ]
        : context.projectId
          ? [projectDocumentsPath(context.projectId)]
          : [];
    case "documents.preprocess.activate":
      return context.projectId && context.documentId
        ? [
            projectDocumentPath(context.projectId, context.documentId),
            projectDocumentPreprocessingPath(context.projectId, context.documentId),
            projectDocumentPreprocessingPath(context.projectId, context.documentId, {
              tab: "runs"
            }),
            projectDocumentPreprocessingQualityPath(
              context.projectId,
              context.documentId
            ),
            projectDocumentViewerPath(
              context.projectId,
              context.documentId,
              1
            ),
            ...(context.runId
              ? [
                  projectDocumentPreprocessingRunPath(
                    context.projectId,
                    context.documentId,
                    context.runId
                  )
                ]
              : [])
          ]
        : context.projectId
          ? [projectDocumentsPath(context.projectId)]
          : [];
    case "documents.layout.activate":
      return context.projectId && context.documentId
        ? [
            projectDocumentPath(context.projectId, context.documentId),
            projectDocumentLayoutPath(context.projectId, context.documentId),
            projectDocumentLayoutPath(context.projectId, context.documentId, {
              tab: "runs"
            }),
            projectDocumentLayoutPath(context.projectId, context.documentId, {
              tab: "triage"
            }),
            projectDocumentLayoutWorkspacePath(context.projectId, context.documentId, {
              page: 1,
              runId: context.runId
            }),
            ...(context.runId
              ? [
                  projectDocumentLayoutRunPath(
                    context.projectId,
                    context.documentId,
                    context.runId
                  )
                ]
              : [])
          ]
        : context.projectId
          ? [projectDocumentsPath(context.projectId)]
          : [];
    case "documents.transcription.activate":
      return context.projectId && context.documentId
        ? [
            projectDocumentPath(context.projectId, context.documentId),
            projectDocumentTranscriptionPath(context.projectId, context.documentId),
            projectDocumentTranscriptionPath(context.projectId, context.documentId, {
              tab: "runs"
            }),
            projectDocumentTranscriptionPath(context.projectId, context.documentId, {
              tab: "triage"
            }),
            projectDocumentTranscriptionPath(context.projectId, context.documentId, {
              tab: "artefacts"
            }),
            projectDocumentTranscriptionWorkspacePath(
              context.projectId,
              context.documentId,
              {
                page: 1,
                runId: context.runId
              }
            ),
            ...(context.runId
              ? [
                  projectDocumentTranscriptionRunPath(
                    context.projectId,
                    context.documentId,
                    context.runId
                  )
                ]
              : [])
          ]
        : context.projectId
          ? [projectDocumentsPath(context.projectId)]
          : [];
    case "jobs.retry":
    case "jobs.cancel":
      return context.projectId && context.jobId
        ? [
            projectJobsPath(context.projectId),
            projectJobPath(context.projectId, context.jobId)
          ]
        : context.projectId
          ? [projectJobsPath(context.projectId)]
          : [];
    default:
      return [];
  }
}
