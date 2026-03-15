import { describe, expect, it } from "vitest";
import type { RedactionPolicy } from "@ukde/contracts";

import {
  buildRulesJsonFromPolicyEditorDraft,
  createPolicyEditorDraft,
  isDraftDirty,
  runPolicySimulation
} from "./policy-editor";

function makePolicy(): RedactionPolicy {
  return {
    id: "policy-1",
    projectId: "project-1",
    policyFamilyId: "family-1",
    name: "Policy Revision 2",
    version: 2,
    seededFromBaselineSnapshotId: "baseline-v1",
    supersedesPolicyId: "policy-0",
    supersededByPolicyId: null,
    rulesJson: {
      categories: [
        {
          id: "PERSON_NAME",
          action: "PSEUDONYMIZE",
          review_required_below: 0.84
        },
        {
          id: "DATE",
          action: "GENERALIZE",
          review_required_below: 0.8
        }
      ],
      defaults: {
        auto_apply_confidence_threshold: 0.9,
        require_manual_review_for_uncertain: true
      },
      reviewer_requirements: true,
      escalation_flags: false,
      pseudonymisation: {
        mode: "DETERMINISTIC",
        aliasing_rules: {
          prefix: "ANON-"
        }
      },
      generalisation: {
        by_category: {
          DATE: "MONTH_YEAR",
          LOCATION: "COUNTY",
          AGE: "FIVE_YEAR_BAND"
        }
      },
      reviewer_explanation_mode: "LOCAL_LLM_RISK_SUMMARY"
    },
    versionEtag: "etag-2",
    status: "DRAFT",
    createdBy: "user-1",
    createdAt: "2026-03-13T00:00:00Z",
    activatedBy: null,
    activatedAt: null,
    retiredBy: null,
    retiredAt: null,
    validationStatus: "VALID",
    validatedRulesSha256: "sha-1",
    lastValidatedBy: "user-1",
    lastValidatedAt: "2026-03-13T00:10:00Z"
  };
}

describe("policy-editor helpers", () => {
  it("creates a normalized editor draft from policy rules", () => {
    const policy = makePolicy();
    const draft = createPolicyEditorDraft(policy);

    expect(draft.name).toBe("Policy Revision 2");
    expect(draft.categories).toHaveLength(2);
    expect(draft.categories[0]).toEqual({
      id: "PERSON_NAME",
      action: "PSEUDONYMIZE",
      reviewRequiredBelow: "0.84"
    });
    expect(draft.autoApplyConfidenceThreshold).toBe("0.9");
    expect(draft.reviewerRequirementsEnabled).toBe(true);
    expect(draft.aliasPrefix).toBe("ANON-");
    expect(draft.dateSpecificityCeiling).toBe("MONTH_YEAR");
    expect(draft.placeSpecificityCeiling).toBe("COUNTY");
    expect(draft.ageSpecificityCeiling).toBe("FIVE_YEAR_BAND");
  });

  it("builds canonical rules json from editor draft values", () => {
    const draft = createPolicyEditorDraft(makePolicy());
    draft.name = "Policy Revision 3";
    draft.autoApplyConfidenceThreshold = "0.95";
    draft.pseudonymMode = "disabled";
    draft.aliasPrefix = "P-";
    draft.dateSpecificityCeiling = "YEAR";
    draft.placeSpecificityCeiling = "REGION";
    draft.ageSpecificityCeiling = "TEN_YEAR_BAND";
    draft.reviewerExplanationMode = "LOCAL_SUMMARY";

    const rulesJson = buildRulesJsonFromPolicyEditorDraft(draft);

    expect(rulesJson.defaults).toMatchObject({
      auto_apply_confidence_threshold: 0.95,
      require_manual_review_for_uncertain: true
    });
    expect(rulesJson.pseudonymisation).toMatchObject({
      mode: "DISABLED",
      aliasing_rules: { prefix: "P-" }
    });
    expect(rulesJson.generalisation).toMatchObject({
      by_category: {
        DATE: "YEAR",
        LOCATION: "REGION",
        AGE: "TEN_YEAR_BAND"
      }
    });
    expect(rulesJson.reviewer_explanation_mode).toBe("LOCAL_SUMMARY");
  });

  it("detects draft dirty state from rule or name changes", () => {
    const policy = makePolicy();
    const originalDraft = createPolicyEditorDraft(policy);
    expect(isDraftDirty(policy.rulesJson, policy.name, originalDraft)).toBe(
      false
    );

    const renamedDraft = createPolicyEditorDraft(policy);
    renamedDraft.name = "Changed Name";
    expect(isDraftDirty(policy.rulesJson, policy.name, renamedDraft)).toBe(
      true
    );

    const editedDraft = createPolicyEditorDraft(policy);
    editedDraft.categories[0].action = "MASK";
    expect(isDraftDirty(policy.rulesJson, policy.name, editedDraft)).toBe(true);
  });

  it("runs deterministic simulation output for the same draft", () => {
    const draft = createPolicyEditorDraft(makePolicy());
    const first = runPolicySimulation(draft);
    const second = runPolicySimulation(draft);

    expect(first).toEqual(second);
    expect(first.samples).toHaveLength(6);
  });

  it("routes samples to NEEDS_REVIEW when thresholds require manual review", () => {
    const draft = createPolicyEditorDraft(makePolicy());
    draft.categories = [
      {
        id: "PERSON_NAME",
        action: "PSEUDONYMIZE",
        reviewRequiredBelow: "0.99"
      }
    ];

    const report = runPolicySimulation(draft);
    const personSample = report.samples.find(
      (sample) => sample.id === "sample-name-hi"
    );

    expect(personSample?.action).toBe("NEEDS_REVIEW");
    expect(personSample?.needsReviewReason).toContain(
      "category review threshold"
    );
  });

  it("surfaces allow, contradiction, and unsupported ceiling guardrails", () => {
    const draft = createPolicyEditorDraft(makePolicy());
    draft.categories = [
      {
        id: "EMAIL",
        action: "ALLOW",
        reviewRequiredBelow: "0.95"
      }
    ];
    draft.autoApplyConfidenceThreshold = "0.9";
    draft.dateSpecificityCeiling = "EXACT_DATE";
    draft.placeSpecificityCeiling = "TOWN";
    draft.ageSpecificityCeiling = "EXACT_AGE";

    const report = runPolicySimulation(draft);
    const codes = report.guardrails.map((guardrail) => guardrail.code);

    expect(codes).toContain("ALLOW_RULE_BROAD");
    expect(codes).toContain("THRESHOLD_CONTRADICTION");
    expect(codes).toContain("OVER_SPECIFIC_DATE");
    expect(codes).toContain("OVER_SPECIFIC_PLACE");
    expect(codes).toContain("OVER_SPECIFIC_AGE");
  });
});
