"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { RedactionPolicy } from "@ukde/contracts";
import { InlineAlert, StatusChip } from "@ukde/ui/primitives";

import {
  POLICY_ACTION_OPTIONS,
  buildRulesJsonFromPolicyEditorDraft,
  createPolicyEditorDraft,
  isDraftDirty,
  runPolicySimulation,
  stringifyPolicyRules,
  type PolicyCategoryRuleDraft
} from "../lib/policy-editor";
import { projectPolicyComparePath } from "../lib/routes";

interface PolicyEditorSurfaceProps {
  canMutate: boolean;
  policy: RedactionPolicy;
  previousPolicyId: string | null;
  projectId: string;
}

const ACTION_SUMMARY_ORDER = [
  "MASK",
  "PSEUDONYMIZE",
  "GENERALIZE",
  "NEEDS_REVIEW",
  "ESCALATE",
  "ALLOW",
  "REVIEW"
] as const;

const PSEUDONYM_MODE_OPTIONS = [
  "DETERMINISTIC",
  "DISABLED",
  "NONE",
  "OFF"
] as const;
const DATE_CEILING_OPTIONS = ["YEAR", "MONTH_YEAR"] as const;
const PLACE_CEILING_OPTIONS = ["REGION", "COUNTY"] as const;
const AGE_CEILING_OPTIONS = ["TEN_YEAR_BAND", "FIVE_YEAR_BAND"] as const;

function emptyCategoryRule(): PolicyCategoryRuleDraft {
  return {
    id: "",
    action: "MASK",
    reviewRequiredBelow: ""
  };
}

function toThresholdValue(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  const numeric = Number.parseFloat(trimmed);
  if (!Number.isFinite(numeric)) {
    return trimmed;
  }
  return numeric.toFixed(2);
}

export function PolicyEditorSurface({
  canMutate,
  policy,
  previousPolicyId,
  projectId
}: PolicyEditorSurfaceProps) {
  const [draft, setDraft] = useState(() => createPolicyEditorDraft(policy));

  useEffect(() => {
    setDraft(createPolicyEditorDraft(policy));
  }, [policy]);

  const canEditDraft = canMutate && policy.status === "DRAFT";
  const dirty =
    canEditDraft && isDraftDirty(policy.rulesJson, policy.name, draft);

  const rulesJson = useMemo(
    () => buildRulesJsonFromPolicyEditorDraft(draft),
    [draft]
  );
  const rulesJsonText = useMemo(
    () => stringifyPolicyRules(rulesJson),
    [rulesJson]
  );
  const simulation = useMemo(() => runPolicySimulation(draft), [draft]);

  useEffect(() => {
    if (!dirty) {
      return undefined;
    }
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [dirty]);

  const hasDangerGuardrail = simulation.guardrails.some(
    (guardrail) => guardrail.level === "danger"
  );
  const hasWarningGuardrail = simulation.guardrails.some(
    (guardrail) => guardrail.level === "warning"
  );

  return (
    <section className="sectionCard ukde-panel policyEditorSurface">
      <header className="policyEditorHeader">
        <div>
          <p className="ukde-eyebrow">Expert policy editor</p>
          <h3>Draft-first authoring with simulation guardrails</h3>
          <p className="ukde-muted">
            Save is explicit, validation stays authoritative, and this
            simulation panel never triggers policy reruns.
          </p>
        </div>
        <div className="policyEditorStatusRow" role="status" aria-live="polite">
          <StatusChip tone={policy.status === "DRAFT" ? "warning" : "neutral"}>
            Revision: {policy.status}
          </StatusChip>
          <StatusChip
            tone={
              policy.validationStatus === "VALID"
                ? "success"
                : policy.validationStatus === "INVALID"
                  ? "warning"
                  : "neutral"
            }
          >
            Validation: {policy.validationStatus}
          </StatusChip>
          {dirty ? (
            <StatusChip tone="warning">Unsaved changes</StatusChip>
          ) : null}
        </div>
      </header>

      <div className="policyEditorLayout">
        <div className="policyEditorMainColumn">
          {!canMutate ? (
            <InlineAlert title="Read-only mode" tone="info">
              Your role can inspect policy rules and simulation output but
              cannot save, validate, activate, or retire revisions.
            </InlineAlert>
          ) : null}

          {canMutate && policy.status !== "DRAFT" ? (
            <InlineAlert title="Immutable revision" tone="info">
              Only DRAFT revisions are editable. Use this view to inspect rules,
              compare lineage, and policy history.
            </InlineAlert>
          ) : null}

          <form
            action={`/projects/${projectId}/policies/${policy.id}/update`}
            className="policyEditorForm"
            method="post"
          >
            <section className="policyEditorBlock">
              <h4>Policy identity and baseline context</h4>
              <div className="policyEditorFieldGrid policyEditorFieldGrid--two">
                <label className="policyEditorField">
                  <span>Revision name</span>
                  <input
                    disabled={!canEditDraft}
                    onChange={(event) => {
                      const value = event.target.value;
                      setDraft((current) => ({
                        ...current,
                        name: value
                      }));
                    }}
                    type="text"
                    value={draft.name}
                  />
                </label>
                <label className="policyEditorField">
                  <span>Reviewer explanation mode</span>
                  <input
                    disabled={!canEditDraft}
                    onChange={(event) => {
                      const value = event.target.value;
                      setDraft((current) => ({
                        ...current,
                        reviewerExplanationMode: value
                      }));
                    }}
                    type="text"
                    value={draft.reviewerExplanationMode}
                  />
                </label>
              </div>
            </section>

            <section className="policyEditorBlock">
              <div className="policyEditorBlockHead">
                <h4>Category actions and review thresholds</h4>
                <button
                  className="projectSecondaryButton"
                  disabled={!canEditDraft}
                  onClick={() => {
                    setDraft((current) => ({
                      ...current,
                      categories: [...current.categories, emptyCategoryRule()]
                    }));
                  }}
                  type="button"
                >
                  Add category rule
                </button>
              </div>
              <div
                className="policyRuleTableWrap"
                role="region"
                aria-label="Category rules"
              >
                <table className="policyRuleTable">
                  <thead>
                    <tr>
                      <th>Category ID</th>
                      <th>Action</th>
                      <th>Review required below</th>
                      <th>Row</th>
                    </tr>
                  </thead>
                  <tbody>
                    {draft.categories.length === 0 ? (
                      <tr>
                        <td colSpan={4}>No category rules configured yet.</td>
                      </tr>
                    ) : (
                      draft.categories.map((category, index) => (
                        <tr key={`${category.id}-${index}`}>
                          <td>
                            <input
                              aria-label={`Category ID row ${index + 1}`}
                              disabled={!canEditDraft}
                              onChange={(event) => {
                                const value = event.target.value;
                                setDraft((current) => ({
                                  ...current,
                                  categories: current.categories.map(
                                    (item, itemIndex) =>
                                      itemIndex === index
                                        ? { ...item, id: value }
                                        : item
                                  )
                                }));
                              }}
                              type="text"
                              value={category.id}
                            />
                          </td>
                          <td>
                            <select
                              aria-label={`Category action row ${index + 1}`}
                              disabled={!canEditDraft}
                              onChange={(event) => {
                                const value = event.target.value;
                                setDraft((current) => ({
                                  ...current,
                                  categories: current.categories.map(
                                    (item, itemIndex) =>
                                      itemIndex === index
                                        ? { ...item, action: value }
                                        : item
                                  )
                                }));
                              }}
                              value={category.action}
                            >
                              {POLICY_ACTION_OPTIONS.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <input
                              aria-label={`Review threshold row ${index + 1}`}
                              disabled={!canEditDraft}
                              max={1}
                              min={0}
                              onChange={(event) => {
                                const value = event.target.value;
                                setDraft((current) => ({
                                  ...current,
                                  categories: current.categories.map(
                                    (item, itemIndex) =>
                                      itemIndex === index
                                        ? {
                                            ...item,
                                            reviewRequiredBelow: value
                                          }
                                        : item
                                  )
                                }));
                              }}
                              step={0.01}
                              type="number"
                              value={category.reviewRequiredBelow}
                            />
                          </td>
                          <td>
                            <button
                              className="projectDangerButton"
                              disabled={
                                !canEditDraft || draft.categories.length <= 1
                              }
                              onClick={() => {
                                setDraft((current) => ({
                                  ...current,
                                  categories: current.categories.filter(
                                    (_, itemIndex) => itemIndex !== index
                                  )
                                }));
                              }}
                              type="button"
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="policyEditorBlock">
              <h4>Defaults, reviewer and escalation gates</h4>
              <div className="policyEditorFieldGrid policyEditorFieldGrid--three">
                <label className="policyEditorField">
                  <span>Auto-apply confidence threshold</span>
                  <input
                    disabled={!canEditDraft}
                    max={1}
                    min={0}
                    onChange={(event) => {
                      const value = event.target.value;
                      setDraft((current) => ({
                        ...current,
                        autoApplyConfidenceThreshold: value
                      }));
                    }}
                    step={0.01}
                    type="number"
                    value={draft.autoApplyConfidenceThreshold}
                  />
                </label>
                <label className="policyEditorToggle">
                  <input
                    checked={draft.requireManualReviewForUncertain}
                    disabled={!canEditDraft}
                    onChange={(event) => {
                      const value = event.target.checked;
                      setDraft((current) => ({
                        ...current,
                        requireManualReviewForUncertain: value
                      }));
                    }}
                    type="checkbox"
                  />
                  <span>Require manual review for uncertain findings</span>
                </label>
                <label className="policyEditorToggle">
                  <input
                    checked={draft.reviewerRequirementsEnabled}
                    disabled={!canEditDraft}
                    onChange={(event) => {
                      const value = event.target.checked;
                      setDraft((current) => ({
                        ...current,
                        reviewerRequirementsEnabled: value
                      }));
                    }}
                    type="checkbox"
                  />
                  <span>Enable reviewer requirement gates</span>
                </label>
                <label className="policyEditorToggle">
                  <input
                    checked={draft.escalationFlagsEnabled}
                    disabled={!canEditDraft}
                    onChange={(event) => {
                      const value = event.target.checked;
                      setDraft((current) => ({
                        ...current,
                        escalationFlagsEnabled: value
                      }));
                    }}
                    type="checkbox"
                  />
                  <span>Enable escalation flags for manual review</span>
                </label>
              </div>
            </section>

            <section className="policyEditorBlock">
              <h4>Pseudonymisation and generalisation ceilings</h4>
              <div className="policyEditorFieldGrid policyEditorFieldGrid--four">
                <label className="policyEditorField">
                  <span>Pseudonym mode</span>
                  <select
                    disabled={!canEditDraft}
                    onChange={(event) => {
                      const value = event.target.value;
                      setDraft((current) => ({
                        ...current,
                        pseudonymMode: value
                      }));
                    }}
                    value={draft.pseudonymMode}
                  >
                    {PSEUDONYM_MODE_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="policyEditorField">
                  <span>Alias prefix</span>
                  <input
                    disabled={!canEditDraft}
                    onChange={(event) => {
                      const value = event.target.value;
                      setDraft((current) => ({
                        ...current,
                        aliasPrefix: value
                      }));
                    }}
                    type="text"
                    value={draft.aliasPrefix}
                  />
                </label>
                <label className="policyEditorField">
                  <span>Date specificity ceiling</span>
                  <select
                    disabled={!canEditDraft}
                    onChange={(event) => {
                      const value = event.target.value;
                      setDraft((current) => ({
                        ...current,
                        dateSpecificityCeiling: value
                      }));
                    }}
                    value={draft.dateSpecificityCeiling}
                  >
                    {DATE_CEILING_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="policyEditorField">
                  <span>Place specificity ceiling</span>
                  <select
                    disabled={!canEditDraft}
                    onChange={(event) => {
                      const value = event.target.value;
                      setDraft((current) => ({
                        ...current,
                        placeSpecificityCeiling: value
                      }));
                    }}
                    value={draft.placeSpecificityCeiling}
                  >
                    {PLACE_CEILING_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="policyEditorField">
                  <span>Age specificity ceiling</span>
                  <select
                    disabled={!canEditDraft}
                    onChange={(event) => {
                      const value = event.target.value;
                      setDraft((current) => ({
                        ...current,
                        ageSpecificityCeiling: value
                      }));
                    }}
                    value={draft.ageSpecificityCeiling}
                  >
                    {AGE_CEILING_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </section>

            <details className="policyEditorJsonPreview">
              <summary>Canonical rules JSON preview</summary>
              <textarea
                aria-label="Canonical rules JSON preview"
                className="projectTextAreaInput"
                readOnly
                rows={14}
                value={rulesJsonText}
              />
            </details>

            {dirty ? (
              <InlineAlert title="Unsaved draft edits" tone="warning">
                Validation status is authoritative for persisted rules only.
                Save this draft before running validate or activate.
              </InlineAlert>
            ) : null}

            <input name="name" type="hidden" value={draft.name} />
            <input name="rules_json" type="hidden" value={rulesJsonText} />
            <input
              name="version_etag"
              type="hidden"
              value={policy.versionEtag}
            />

            <div className="policyEditorFormActions">
              <button
                className="projectPrimaryButton"
                disabled={!canEditDraft || !dirty}
                type="submit"
              >
                Save draft revision
              </button>
              <span className="ukde-muted">
                No autosave. Submit writes one explicit draft edit.
              </span>
            </div>
          </form>
        </div>

        <aside className="policyEditorSideColumn">
          <section className="policyEditorBlock">
            <h4>Compare targets</h4>
            <div className="policyEditorCompareLinks">
              {previousPolicyId ? (
                <Link
                  className="secondaryButton"
                  href={projectPolicyComparePath(projectId, policy.id, {
                    against: previousPolicyId
                  })}
                >
                  Compare with previous revision
                </Link>
              ) : (
                <p className="ukde-muted">
                  No previous lineage revision is available.
                </p>
              )}
              {policy.seededFromBaselineSnapshotId ? (
                <Link
                  className="secondaryButton"
                  href={projectPolicyComparePath(projectId, policy.id, {
                    againstBaselineSnapshotId:
                      policy.seededFromBaselineSnapshotId
                  })}
                >
                  Compare with seeded baseline
                </Link>
              ) : null}
            </div>
          </section>

          <section className="policyEditorBlock">
            <h4>Lifecycle actions</h4>
            <p className="ukde-muted">
              Activation requires validation hash parity with the current
              persisted draft rules.
            </p>
            <div className="policyEditorLifecycleActions">
              <form
                action={`/projects/${projectId}/policies/${policy.id}/validate?returnTo=detail`}
                method="post"
              >
                <button
                  className="projectSecondaryButton"
                  disabled={!canEditDraft || dirty}
                  type="submit"
                >
                  Validate
                </button>
              </form>
              <form
                action={`/projects/${projectId}/policies/${policy.id}/activate?returnTo=detail`}
                method="post"
              >
                <button
                  className="projectSecondaryButton"
                  disabled={
                    !canEditDraft ||
                    dirty ||
                    policy.validationStatus !== "VALID"
                  }
                  type="submit"
                >
                  Activate
                </button>
              </form>
              <form
                action={`/projects/${projectId}/policies/${policy.id}/retire?returnTo=detail`}
                method="post"
              >
                <button
                  className="projectDangerButton"
                  disabled={!canMutate || policy.status !== "ACTIVE"}
                  type="submit"
                >
                  Retire
                </button>
              </form>
            </div>
            {policy.status === "ACTIVE" ? (
              <div className="policyEditorRetireImpact">
                <h5>Retire impact summary</h5>
                <ul>
                  <li>
                    The project active-policy projection will clear immediately.
                  </li>
                  <li>
                    This revision will become immutable `RETIRED` history.
                  </li>
                  <li>Future reruns must target another validated revision.</li>
                </ul>
              </div>
            ) : null}
          </section>

          <section className="policyEditorBlock">
            <h4>Deterministic simulation (advisory)</h4>
            <p className="ukde-muted">
              Simulation uses representative static samples. It never mutates
              policy state and never triggers document reruns.
            </p>
            <div className="policySimulationSummary">
              {ACTION_SUMMARY_ORDER.map((action) => (
                <div className="policySimulationSummaryItem" key={action}>
                  <span>{action}</span>
                  <strong>{simulation.summary[action] ?? 0}</strong>
                </div>
              ))}
            </div>

            <div
              className="policyGuardrailSummary"
              role="status"
              aria-live="polite"
            >
              {simulation.guardrails.length === 0 ? (
                <StatusChip tone="success">No guardrails triggered</StatusChip>
              ) : (
                <>
                  {hasDangerGuardrail ? (
                    <StatusChip tone="danger">
                      Danger guardrail present
                    </StatusChip>
                  ) : null}
                  {hasWarningGuardrail ? (
                    <StatusChip tone="warning">
                      Warning guardrail present
                    </StatusChip>
                  ) : null}
                </>
              )}
            </div>

            {simulation.guardrails.length > 0 ? (
              <ul className="policyGuardrailList">
                {simulation.guardrails.map((guardrail, index) => (
                  <li key={`${guardrail.code}-${index}`}>
                    <StatusChip
                      tone={guardrail.level === "danger" ? "danger" : "warning"}
                    >
                      {guardrail.code}
                    </StatusChip>
                    <span>{guardrail.message}</span>
                  </li>
                ))}
              </ul>
            ) : null}

            <div
              className="policySimulationTableWrap"
              role="region"
              aria-label="Simulation samples"
            >
              <table className="policySimulationTable">
                <thead>
                  <tr>
                    <th>Sample</th>
                    <th>Category</th>
                    <th>Confidence</th>
                    <th>Likely action</th>
                    <th>Output / reason</th>
                  </tr>
                </thead>
                <tbody>
                  {simulation.samples.map((sample) => (
                    <tr key={sample.id}>
                      <td>{sample.label}</td>
                      <td>{sample.categoryId}</td>
                      <td>{toThresholdValue(`${sample.confidence}`)}</td>
                      <td>{sample.action}</td>
                      <td>
                        {sample.transformedValue ??
                          sample.needsReviewReason ??
                          "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </aside>
      </div>
    </section>
  );
}
