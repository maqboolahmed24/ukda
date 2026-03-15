import Link from "next/link";
import { redirect } from "next/navigation";

import { SectionState } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../lib/auth/session";
import {
  getProjectActivePolicy,
  listProjectPolicies
} from "../../../../../lib/policies";
import { getProjectWorkspace } from "../../../../../lib/projects";
import {
  projectPoliciesActivePath,
  projectPoliciesPath,
  projectPolicyComparePath,
  projectPolicyPath
} from "../../../../../lib/routes";

export const dynamic = "force-dynamic";

interface StatusNotice {
  description: string;
  title: string;
  tone: "success" | "warning" | "danger";
}

function resolveNotice(status?: string): StatusNotice | null {
  switch (status) {
    case "created":
      return {
        title: "Policy draft created",
        description:
          "A new DRAFT revision was created for this project lineage.",
        tone: "success"
      };
    case "activated":
      return {
        title: "Policy activated",
        description:
          "The selected revision is now ACTIVE in project projection.",
        tone: "success"
      };
    case "retired":
      return {
        title: "Policy retired",
        description: "The selected ACTIVE revision was retired.",
        tone: "success"
      };
    case "validated":
      return {
        title: "Policy validated",
        description: "Validation completed with status VALID.",
        tone: "success"
      };
    case "invalid":
      return {
        title: "Policy validation failed",
        description:
          "Validation status is INVALID. Resolve rule issues before activation.",
        tone: "warning"
      };
    case "updated":
      return {
        title: "Policy draft updated",
        description: "Draft changes were saved and validation was reset.",
        tone: "success"
      };
    case "rollback-created":
      return {
        title: "Rollback draft created",
        description:
          "A new DRAFT revision was seeded from a prior validated policy and now follows normal validate/compare/activate gates.",
        tone: "success"
      };
    case "action-failed":
      return {
        title: "Policy action failed",
        description:
          "Review lifecycle gates, etag freshness, and permissions, then retry.",
        tone: "danger"
      };
    case "conflict":
      return {
        title: "Lifecycle conflict",
        description:
          "The action conflicts with current policy status or validation hash parity.",
        tone: "warning"
      };
    case "forbidden":
      return {
        title: "Mutation not permitted",
        description:
          "Only PROJECT_LEAD and ADMIN can create, edit, validate, activate, retire, or rollback policies.",
        tone: "danger"
      };
    case "malformed-rules":
      return {
        title: "Malformed rules JSON",
        description:
          "Rules payload could not be parsed as a valid JSON object.",
        tone: "danger"
      };
    default:
      return null;
  }
}

const DEFAULT_RULES_TEMPLATE = JSON.stringify(
  {
    categories: [
      {
        id: "PERSON_NAME",
        action: "MASK",
        review_required_below: 0.9
      },
      {
        id: "ADDRESS",
        action: "GENERALIZE",
        review_required_below: 0.88
      }
    ],
    defaults: {
      auto_apply_confidence_threshold: 0.92,
      require_manual_review_for_uncertain: true
    },
    pseudonymisation: {
      mode: "DETERMINISTIC",
      aliasing_rules: {
        prefix: "ALIAS-"
      }
    },
    generalisation: {
      specificity_ceiling: "district",
      by_category: {
        ADDRESS: "district"
      }
    },
    reviewer_explanation_mode: "LOCAL_LLM_RISK_SUMMARY"
  },
  null,
  2
);

export default async function ProjectPoliciesPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ status?: string }>;
}>) {
  const { projectId } = await params;
  const [session, workspaceResult, policiesResult, activeResult, query] =
    await Promise.all([
      requireCurrentSession(),
      getProjectWorkspace(projectId),
      listProjectPolicies(projectId),
      getProjectActivePolicy(projectId),
      searchParams
    ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=policies-access");
  }

  if (!policiesResult.ok || !activeResult.ok) {
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Project policies unavailable"
          description={
            policiesResult.detail ??
            activeResult.detail ??
            "Policy list could not be loaded."
          }
        />
      </main>
    );
  }

  const workspace = workspaceResult.data;
  const policyRows = policiesResult.data?.items ?? [];
  const activePolicyId = activeResult.data?.policy?.id ?? null;
  const canMutate =
    session.user.platformRoles.includes("ADMIN") ||
    workspace.currentUserRole === "PROJECT_LEAD";
  const notice = resolveNotice(
    typeof query.status === "string" ? query.status.trim() : undefined
  );

  const baselineId =
    policyRows[0]?.seededFromBaselineSnapshotId ??
    workspace.baselinePolicySnapshotId;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Policy governance</p>
        <h2>Project policy revisions</h2>
        <p className="ukde-muted">
          Manage Phase 7 explicit policy drafts, validation gates, activation,
          and append-only policy event history.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectPoliciesActivePath(projectId)}
          >
            View active policy
          </Link>
        </div>
      </section>

      {notice ? (
        <section className="sectionCard ukde-panel">
          <p className="ukde-muted">
            {notice.title}: {notice.description}
          </p>
        </section>
      ) : null}

      {canMutate ? (
        <section className="sectionCard ukde-panel">
          <h3>Create draft policy revision</h3>
          <form action={`/projects/${projectId}/policies/create`} method="post">
            <label>
              Name
              <input
                defaultValue={`Policy revision ${policyRows.length + 1}`}
                name="name"
                required
                type="text"
              />
            </label>
            <label>
              Rules JSON
              <textarea
                className="projectTextAreaInput"
                defaultValue={DEFAULT_RULES_TEMPLATE}
                name="rules_json"
                rows={16}
              />
            </label>
            {policyRows[0] ? (
              <input
                name="supersedes_policy_id"
                type="hidden"
                value={policyRows[0].id}
              />
            ) : null}
            {baselineId ? (
              <input
                name="seeded_from_baseline_snapshot_id"
                type="hidden"
                value={baselineId}
              />
            ) : null}
            <button className="projectPrimaryButton" type="submit">
              Create DRAFT
            </button>
          </form>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        {policyRows.length === 0 ? (
          <SectionState
            kind="empty"
            title="No explicit policies"
            description="Create the first explicit lineage seeded from baseline snapshot."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Validation</th>
                  <th>Created</th>
                  <th>Compare</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {policyRows.map((policy) => (
                  <tr key={policy.id}>
                    <td>
                      <Link href={projectPolicyPath(projectId, policy.id)}>
                        {policy.id}
                      </Link>
                    </td>
                    <td>{policy.version}</td>
                    <td>
                      {policy.status}
                      {activePolicyId === policy.id ? " (project active)" : ""}
                    </td>
                    <td>{policy.validationStatus}</td>
                    <td>{new Date(policy.createdAt).toISOString()}</td>
                    <td>
                      <div className="jobsActionRow">
                        {activePolicyId && activePolicyId !== policy.id ? (
                          <Link
                            href={projectPolicyComparePath(
                              projectId,
                              policy.id,
                              {
                                against: activePolicyId
                              }
                            )}
                          >
                            vs active
                          </Link>
                        ) : null}
                        {policy.seededFromBaselineSnapshotId ? (
                          <Link
                            href={projectPolicyComparePath(
                              projectId,
                              policy.id,
                              {
                                againstBaselineSnapshotId:
                                  policy.seededFromBaselineSnapshotId
                              }
                            )}
                          >
                            vs baseline
                          </Link>
                        ) : null}
                      </div>
                    </td>
                    <td>
                      {canMutate ? (
                        <div className="jobsActionRow">
                          <form
                            action={`${projectPoliciesPath(projectId)}/${policy.id}/validate?returnTo=list`}
                            method="post"
                          >
                            <button
                              className="projectSecondaryButton"
                              disabled={policy.status !== "DRAFT"}
                              type="submit"
                            >
                              Validate
                            </button>
                          </form>
                          <form
                            action={`${projectPoliciesPath(projectId)}/${policy.id}/activate?returnTo=list`}
                            method="post"
                          >
                            <button
                              className="projectSecondaryButton"
                              disabled={
                                policy.status !== "DRAFT" ||
                                policy.validationStatus !== "VALID"
                              }
                              type="submit"
                            >
                              Activate
                            </button>
                          </form>
                          <form
                            action={`${projectPoliciesPath(projectId)}/${policy.id}/retire?returnTo=list`}
                            method="post"
                          >
                            <button
                              className="projectDangerButton"
                              disabled={policy.status !== "ACTIVE"}
                              type="submit"
                            >
                              Retire
                            </button>
                          </form>
                          {policy.supersedesPolicyId ? (
                            <form
                              action={`${projectPoliciesPath(projectId)}/${policy.id}/rollback-draft?returnTo=list`}
                              method="post"
                            >
                              <input
                                type="hidden"
                                name="from_policy_id"
                                value={policy.supersedesPolicyId}
                              />
                              <button className="projectSecondaryButton" type="submit">
                                Rollback draft
                              </button>
                            </form>
                          ) : null}
                        </div>
                      ) : (
                        "Read-only"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
