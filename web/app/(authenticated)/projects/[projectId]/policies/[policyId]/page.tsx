import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { SectionState } from "@ukde/ui/primitives";

import { PolicyEditorSurface } from "../../../../../../components/policy-editor-surface";
import { requireCurrentSession } from "../../../../../../lib/auth/session";
import {
  getProjectPolicyExplainability,
  getProjectPolicyLineage,
  getProjectPolicy,
  getProjectPolicySnapshot,
  getProjectPolicyUsage,
  listProjectPolicyEvents
} from "../../../../../../lib/policies";
import { getProjectWorkspace } from "../../../../../../lib/projects";
import {
  projectDocumentPrivacyComparePath,
  projectPoliciesPath,
  projectPolicyComparePath
} from "../../../../../../lib/routes";

export const dynamic = "force-dynamic";

interface StatusNotice {
  description: string;
  title: string;
  tone: "success" | "warning" | "danger";
}

function resolveNotice(status?: string): StatusNotice | null {
  switch (status) {
    case "updated":
      return {
        title: "Draft updated",
        description: "Policy draft update succeeded and validation was reset.",
        tone: "success"
      };
    case "validated":
      return {
        title: "Validation succeeded",
        description: "Policy validation status is VALID.",
        tone: "success"
      };
    case "invalid":
      return {
        title: "Validation failed",
        description: "Policy rules are INVALID. Fix issues before activation.",
        tone: "warning"
      };
    case "activated":
      return {
        title: "Policy activated",
        description: "This revision is now ACTIVE in project projection.",
        tone: "success"
      };
    case "retired":
      return {
        title: "Policy retired",
        description: "This ACTIVE revision was retired.",
        tone: "success"
      };
    case "rollback-created":
      return {
        title: "Rollback draft created",
        description:
          "A new DRAFT revision was seeded from a prior validated revision in this lineage.",
        tone: "success"
      };
    case "action-failed":
      return {
        title: "Action failed",
        description: "Check lifecycle gates, etag freshness, and permissions.",
        tone: "danger"
      };
    case "stale-etag":
      return {
        title: "Stale draft version",
        description:
          "Save was rejected because version_etag is stale. Reload this revision and retry on the latest draft.",
        tone: "warning"
      };
    case "conflict":
      return {
        title: "Lifecycle conflict",
        description:
          "This action conflicts with current policy state. Confirm draft/active status and validation hash parity.",
        tone: "warning"
      };
    case "forbidden":
      return {
        title: "Mutation not permitted",
        description:
          "Only PROJECT_LEAD and ADMIN can edit, validate, activate, retire, or rollback policies.",
        tone: "danger"
      };
    case "malformed-rules":
      return {
        title: "Malformed rules JSON",
        description: "Rules payload could not be parsed as JSON.",
        tone: "danger"
      };
    case "compare-link-failed":
      return {
        title: "Compare link missing values",
        description:
          "Document ID, base run ID, and candidate run ID are required to open privacy compare from policy detail.",
        tone: "warning"
      };
    default:
      return null;
  }
}

export default async function ProjectPolicyDetailPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; policyId: string }>;
  searchParams: Promise<{ status?: string }>;
}>) {
  const { projectId, policyId } = await params;
  const [
    session,
    workspaceResult,
    policyResult,
    eventsResult,
    lineageResult,
    usageResult,
    explainabilityResult,
    query
  ] =
    await Promise.all([
      requireCurrentSession(),
      getProjectWorkspace(projectId),
      getProjectPolicy(projectId, policyId),
      listProjectPolicyEvents(projectId, policyId),
      getProjectPolicyLineage(projectId, policyId),
      getProjectPolicyUsage(projectId, policyId),
      getProjectPolicyExplainability(projectId, policyId),
      searchParams
    ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=policies-access");
  }
  if (policyResult.status === 404) {
    notFound();
  }
  if (
    !policyResult.ok ||
    !policyResult.data ||
    !eventsResult.ok ||
    !lineageResult.ok ||
    !usageResult.ok ||
    !explainabilityResult.ok ||
    !lineageResult.data ||
    !usageResult.data ||
    !explainabilityResult.data
  ) {
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Policy detail unavailable"
          description={
            policyResult.detail ??
            eventsResult.detail ??
            lineageResult.detail ??
            usageResult.detail ??
            explainabilityResult.detail ??
            "Policy detail data could not be loaded."
          }
        />
      </main>
    );
  }

  const policy = policyResult.data;
  const events = eventsResult.data?.items ?? [];
  const lineage = lineageResult.data;
  const usage = usageResult.data;
  const explainability = explainabilityResult.data;
  const workspace = workspaceResult.data;
  const canMutate =
    session.user.platformRoles.includes("ADMIN") ||
    workspace.currentUserRole === "PROJECT_LEAD";
  const notice = resolveNotice(
    typeof query.status === "string" ? query.status.trim() : undefined
  );
  const detailPath = `/projects/${projectId}/policies/${policy.id}`;
  const snapshotResult =
    policy.validatedRulesSha256 && policy.validatedRulesSha256.trim().length > 0
      ? await getProjectPolicySnapshot(
          projectId,
          policy.id,
          policy.validatedRulesSha256
        )
      : null;
  const snapshotUnavailableDetail =
    snapshotResult && !snapshotResult.ok
      ? snapshotResult.detail ?? "Immutable snapshot could not be loaded."
      : null;

  async function openPrivacyCompareAction(formData: FormData) {
    "use server";
    const targetDocumentId = String(formData.get("document_id") ?? "").trim();
    const baseRunId = String(formData.get("base_run_id") ?? "").trim();
    const candidateRunId = String(formData.get("candidate_run_id") ?? "").trim();
    if (!targetDocumentId || !baseRunId || !candidateRunId) {
      redirect(`${detailPath}?status=compare-link-failed`);
    }
    redirect(
      projectDocumentPrivacyComparePath(
        projectId,
        targetDocumentId,
        baseRunId,
        candidateRunId,
        { page: 1 }
      )
    );
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Policy revision detail</p>
        <h2>{policy.id}</h2>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectPoliciesPath(projectId)}
          >
            Back to policy list
          </Link>
          {policy.supersedesPolicyId ? (
            <Link
              className="secondaryButton"
              href={projectPolicyComparePath(projectId, policy.id, {
                against: policy.supersedesPolicyId
              })}
            >
              Compare with previous revision
            </Link>
          ) : null}
          {policy.seededFromBaselineSnapshotId ? (
            <Link
              className="secondaryButton"
              href={projectPolicyComparePath(projectId, policy.id, {
                againstBaselineSnapshotId: policy.seededFromBaselineSnapshotId
              })}
            >
              Compare with baseline
            </Link>
          ) : null}
          {canMutate && policy.supersedesPolicyId ? (
            <form
              action={`${projectPoliciesPath(projectId)}/${policy.id}/rollback-draft`}
              method="post"
            >
              <input
                type="hidden"
                name="from_policy_id"
                value={policy.supersedesPolicyId}
              />
              <button className="secondaryButton" type="submit">
                Create rollback draft
              </button>
            </form>
          ) : null}
        </div>
      </section>

      {notice ? (
        <section className="sectionCard ukde-panel">
          <p className="ukde-muted">
            {notice.title}: {notice.description}
          </p>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <ul className="projectMetaList">
          <li>
            <span>Status</span>
            <strong>{policy.status}</strong>
          </li>
          <li>
            <span>Validation status</span>
            <strong>{policy.validationStatus}</strong>
          </li>
          <li>
            <span>Version</span>
            <strong>{policy.version}</strong>
          </li>
          <li>
            <span>Family</span>
            <strong>{policy.policyFamilyId}</strong>
          </li>
          <li>
            <span>Version etag</span>
            <strong>{policy.versionEtag}</strong>
          </li>
          <li>
            <span>Seeded baseline snapshot</span>
            <strong>{policy.seededFromBaselineSnapshotId ?? "-"}</strong>
          </li>
          <li>
            <span>Supersedes policy</span>
            <strong>{policy.supersedesPolicyId ?? "-"}</strong>
          </li>
          <li>
            <span>Superseded by policy</span>
            <strong>{policy.supersededByPolicyId ?? "-"}</strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Approval and activation summary</h3>
        <ul className="projectMetaList">
          <li>
            <span>Last validated by</span>
            <strong>{policy.lastValidatedBy ?? "-"}</strong>
          </li>
          <li>
            <span>Last validated at</span>
            <strong>
              {policy.lastValidatedAt
                ? new Date(policy.lastValidatedAt).toISOString()
                : "-"}
            </strong>
          </li>
          <li>
            <span>Validated rules hash</span>
            <strong>{policy.validatedRulesSha256 ?? "-"}</strong>
          </li>
          <li>
            <span>Activated by</span>
            <strong>{policy.activatedBy ?? "-"}</strong>
          </li>
          <li>
            <span>Activated at</span>
            <strong>
              {policy.activatedAt ? new Date(policy.activatedAt).toISOString() : "-"}
            </strong>
          </li>
          <li>
            <span>Projected active policy</span>
            <strong>{lineage.projection?.activePolicyId ?? "-"}</strong>
          </li>
          <li>
            <span>Viewed revision differs from active</span>
            <strong>{lineage.activePolicyDiffers ? "Yes" : "No"}</strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Lineage</h3>
        {lineage.lineage.length === 0 ? (
          <SectionState
            kind="empty"
            title="No lineage rows"
            description="Lineage rows are unavailable for this policy family."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Policy ID</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Validation</th>
                  <th>Supersedes</th>
                  <th>Superseded by</th>
                </tr>
              </thead>
              <tbody>
                {lineage.lineage.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link href={projectPoliciesPath(projectId) + `/${item.id}`}>
                        {item.id}
                      </Link>
                    </td>
                    <td>{item.version}</td>
                    <td>{item.status}</td>
                    <td>{item.validationStatus}</td>
                    <td>{item.supersedesPolicyId ?? "-"}</td>
                    <td>{item.supersededByPolicyId ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Usage lineage</h3>
        <ul className="projectMetaList">
          <li>
            <span>Policy reruns</span>
            <strong>{usage.runs.length}</strong>
          </li>
          <li>
            <span>Manifest attempts</span>
            <strong>{usage.manifests.length}</strong>
          </li>
          <li>
            <span>Ledger attempts</span>
            <strong>{usage.ledgers.length}</strong>
          </li>
          <li>
            <span>Pseudonym entries</span>
            <strong>{usage.pseudonymSummary.totalEntries}</strong>
          </li>
          <li>
            <span>Alias strategy versions</span>
            <strong>
              {usage.pseudonymSummary.aliasStrategyVersions.join(", ") || "-"}
            </strong>
          </li>
          <li>
            <span>Salt version refs</span>
            <strong>{usage.pseudonymSummary.saltVersionRefs.join(", ") || "-"}</strong>
          </li>
        </ul>
        {usage.runs.length > 0 ? (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Document</th>
                  <th>Run status</th>
                  <th>Readiness</th>
                  <th>Manifest</th>
                  <th>Ledger</th>
                </tr>
              </thead>
              <tbody>
                {usage.runs.map((run) => (
                  <tr key={run.runId}>
                    <td>{run.runId}</td>
                    <td>{run.documentId}</td>
                    <td>{run.runStatus}</td>
                    <td>{run.governanceReadinessStatus ?? "-"}</td>
                    <td>{run.governanceManifestId ?? "-"}</td>
                    <td>{run.governanceLedgerId ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="ukde-muted">
            No document reruns currently reference this policy revision.
          </p>
        )}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Explainability</h3>
        <p className="ukde-muted">
          Deterministic rule traces are shown for reviewer-visible behavior. Policy rules remain authoritative.
        </p>
        <ul className="projectMetaList">
          <li>
            <span>Rules hash</span>
            <strong>{explainability.rulesSha256}</strong>
          </li>
          <li>
            <span>Reviewer explanation mode</span>
            <strong>{explainability.reviewerExplanationMode ?? "-"}</strong>
          </li>
          <li>
            <span>Category rules</span>
            <strong>{explainability.categoryRules.length}</strong>
          </li>
          <li>
            <span>Deterministic traces</span>
            <strong>{explainability.deterministicTraces.length}</strong>
          </li>
        </ul>
        {explainability.categoryRules.length > 0 ? (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Action</th>
                  <th>Review below</th>
                  <th>Auto above</th>
                  <th>Threshold</th>
                  <th>Requires reviewer</th>
                </tr>
              </thead>
              <tbody>
                {explainability.categoryRules.map((rule) => (
                  <tr key={rule.id}>
                    <td>{rule.id}</td>
                    <td>{rule.action}</td>
                    <td>
                      {typeof rule.reviewRequiredBelow === "number"
                        ? rule.reviewRequiredBelow.toFixed(2)
                        : "-"}
                    </td>
                    <td>
                      {typeof rule.autoApplyAbove === "number"
                        ? rule.autoApplyAbove.toFixed(2)
                        : "-"}
                    </td>
                    <td>
                      {typeof rule.confidenceThreshold === "number"
                        ? rule.confidenceThreshold.toFixed(2)
                        : "-"}
                    </td>
                    <td>{rule.requiresReviewer ? "Yes" : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      {snapshotResult?.ok && snapshotResult.data ? (
        <section className="sectionCard ukde-panel">
          <h3>Immutable snapshot</h3>
          <ul className="projectMetaList">
            <li>
              <span>Snapshot hash</span>
              <strong>{snapshotResult.data.rulesSha256}</strong>
            </li>
            <li>
              <span>Snapshot key</span>
              <strong>{snapshotResult.data.rulesSnapshotKey}</strong>
            </li>
            <li>
              <span>Snapshot event</span>
              <strong>{snapshotResult.data.event.eventType}</strong>
            </li>
          </ul>
          <pre className="projectTextAreaInput">
            {JSON.stringify(snapshotResult.data.rulesJson, null, 2)}
          </pre>
        </section>
      ) : null}
      {snapshotUnavailableDetail ? (
        <section className="sectionCard ukde-panel">
          <p className="ukde-muted">
            Immutable snapshot unavailable: {snapshotUnavailableDetail}
          </p>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h3>Document compare shortcut</h3>
        <p className="ukde-muted">
          Open document-scoped privacy compare from policy pages once a rerun candidate exists.
        </p>
        <form action={openPrivacyCompareAction}>
          <label>
            Document ID
            <input name="document_id" required type="text" />
          </label>
          <label>
            Base run ID
            <input name="base_run_id" required type="text" />
          </label>
          <label>
            Candidate run ID
            <input name="candidate_run_id" required type="text" />
          </label>
          <button className="projectPrimaryButton" type="submit">
            Open privacy compare
          </button>
        </form>
      </section>

      <PolicyEditorSurface
        canMutate={canMutate}
        policy={policy}
        previousPolicyId={policy.supersedesPolicyId}
        projectId={projectId}
      />

      <section className="sectionCard ukde-panel">
        <h3>Append-only history</h3>
        {events.length === 0 ? (
          <SectionState
            kind="empty"
            title="No policy events"
            description="No lifecycle events are present for this revision."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Event</th>
                  <th>Actor</th>
                  <th>Rules hash</th>
                  <th>Snapshot key</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td>{new Date(event.createdAt).toISOString()}</td>
                    <td>{event.eventType}</td>
                    <td>{event.actorUserId ?? "SYSTEM"}</td>
                    <td>{event.rulesSha256}</td>
                    <td>{event.rulesSnapshotKey}</td>
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
