import type { RedactionPolicy } from "@ukde/contracts";

export const POLICY_ACTION_OPTIONS = [
  "MASK",
  "PSEUDONYMIZE",
  "GENERALIZE",
  "ESCALATE",
  "ALLOW",
  "REVIEW"
] as const;

const DATE_CEILINGS = ["YEAR", "MONTH_YEAR"] as const;
const PLACE_CEILINGS = ["REGION", "COUNTY"] as const;
const AGE_CEILINGS = ["TEN_YEAR_BAND", "FIVE_YEAR_BAND"] as const;

export interface PolicyCategoryRuleDraft {
  id: string;
  action: string;
  reviewRequiredBelow: string;
}

export interface PolicyEditorDraft {
  name: string;
  categories: PolicyCategoryRuleDraft[];
  autoApplyConfidenceThreshold: string;
  requireManualReviewForUncertain: boolean;
  reviewerRequirementsEnabled: boolean;
  escalationFlagsEnabled: boolean;
  pseudonymMode: string;
  aliasPrefix: string;
  dateSpecificityCeiling: string;
  placeSpecificityCeiling: string;
  ageSpecificityCeiling: string;
  reviewerExplanationMode: string;
  sourceRules: Record<string, unknown>;
}

export interface PolicyGuardrailIssue {
  code:
    | "ALLOW_RULE_BROAD"
    | "THRESHOLD_CONTRADICTION"
    | "UNSUPPORTED_ACTION"
    | "UNSUPPORTED_PSEUDONYM_MODE"
    | "OVER_SPECIFIC_DATE"
    | "OVER_SPECIFIC_PLACE"
    | "OVER_SPECIFIC_AGE";
  level: "warning" | "danger";
  message: string;
}

export interface PolicySimulationSample {
  id: string;
  label: string;
  categoryId: string;
  confidence: number;
  action: string;
  transformedValue: string | null;
  needsReviewReason: string | null;
}

export interface PolicySimulationReport {
  summary: Record<string, number>;
  samples: PolicySimulationSample[];
  guardrails: PolicyGuardrailIssue[];
}

interface PolicySimulationInput {
  id: string;
  label: string;
  categoryId: string;
  confidence: number;
  exampleValue: string;
}

const POLICY_SIMULATION_INPUTS: PolicySimulationInput[] = [
  {
    id: "sample-name-hi",
    label: "High confidence person name",
    categoryId: "PERSON_NAME",
    confidence: 0.98,
    exampleValue: "John Thompson"
  },
  {
    id: "sample-name-low",
    label: "Low confidence person name",
    categoryId: "PERSON_NAME",
    confidence: 0.81,
    exampleValue: "J. Thompsn"
  },
  {
    id: "sample-date",
    label: "Exact historical date",
    categoryId: "DATE",
    confidence: 0.93,
    exampleValue: "14/03/1901"
  },
  {
    id: "sample-place",
    label: "Small town location",
    categoryId: "LOCATION",
    confidence: 0.91,
    exampleValue: "Keswick"
  },
  {
    id: "sample-age",
    label: "Exact age mention",
    categoryId: "AGE",
    confidence: 0.89,
    exampleValue: "aged 47 years"
  },
  {
    id: "sample-email",
    label: "Email token",
    categoryId: "EMAIL",
    confidence: 0.87,
    exampleValue: "sample.person@example.test"
  }
];

function toObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return { ...(value as Record<string, unknown>) };
}

function toStringValue(value: unknown): string {
  if (typeof value !== "string") {
    return "";
  }
  return value.trim();
}

function toBooleanValue(value: unknown, fallback: boolean): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    return value !== 0;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "1", "yes", "y"].includes(normalized)) {
      return true;
    }
    if (["false", "0", "no", "n"].includes(normalized)) {
      return false;
    }
  }
  return fallback;
}

function toThresholdString(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${value}`;
  }
  if (typeof value === "string" && value.trim().length > 0) {
    return value.trim();
  }
  return "";
}

function toMaybeNumber(value: string): number | null {
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }
  const parsed = Number.parseFloat(normalized);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return parsed;
}

function numberOrRaw(value: string): number | string | undefined {
  const normalized = value.trim();
  if (!normalized) {
    return undefined;
  }
  const parsed = Number.parseFloat(normalized);
  if (Number.isFinite(parsed)) {
    return parsed;
  }
  return normalized;
}

function normalizeCategoryRules(
  rulesJson: Record<string, unknown>
): PolicyCategoryRuleDraft[] {
  const categoriesRaw = rulesJson.categories;
  if (!Array.isArray(categoriesRaw)) {
    return [];
  }
  return categoriesRaw
    .filter(
      (item): item is Record<string, unknown> =>
        Boolean(item) && typeof item === "object" && !Array.isArray(item)
    )
    .map((category) => ({
      id: toStringValue(category.id),
      action: toStringValue(category.action).toUpperCase() || "MASK",
      reviewRequiredBelow: toThresholdString(category.review_required_below)
    }));
}

function resolveCeiling(
  rulesJson: Record<string, unknown>,
  categoryId: "DATE" | "LOCATION" | "AGE",
  fallback: string
): string {
  const generalisation = toObject(rulesJson.generalisation);
  const byCategory = toObject(generalisation.by_category);
  const categoryValue = toStringValue(byCategory[categoryId]);
  if (categoryValue) {
    return categoryValue.toUpperCase();
  }
  const globalCeiling =
    toStringValue(generalisation.specificity_ceiling) ||
    toStringValue(generalisation.specificityCeiling);
  return globalCeiling ? globalCeiling.toUpperCase() : fallback;
}

export function createPolicyEditorDraft(policy: RedactionPolicy): PolicyEditorDraft {
  const rulesJson = toObject(policy.rulesJson);
  const defaults = toObject(rulesJson.defaults);
  const pseudonymisation = toObject(rulesJson.pseudonymisation);
  const aliasingRules = toObject(pseudonymisation.aliasing_rules);

  return {
    name: policy.name,
    categories: normalizeCategoryRules(rulesJson),
    autoApplyConfidenceThreshold: toThresholdString(
      defaults.auto_apply_confidence_threshold
    ),
    requireManualReviewForUncertain: toBooleanValue(
      defaults.require_manual_review_for_uncertain,
      true
    ),
    reviewerRequirementsEnabled: toBooleanValue(rulesJson.reviewer_requirements, false),
    escalationFlagsEnabled: toBooleanValue(rulesJson.escalation_flags, false),
    pseudonymMode: toStringValue(pseudonymisation.mode).toUpperCase() || "DETERMINISTIC",
    aliasPrefix: toStringValue(aliasingRules.prefix) || "ALIAS-",
    dateSpecificityCeiling: resolveCeiling(rulesJson, "DATE", "MONTH_YEAR"),
    placeSpecificityCeiling: resolveCeiling(rulesJson, "LOCATION", "COUNTY"),
    ageSpecificityCeiling: resolveCeiling(rulesJson, "AGE", "FIVE_YEAR_BAND"),
    reviewerExplanationMode:
      toStringValue(rulesJson.reviewer_explanation_mode) ||
      "LOCAL_LLM_RISK_SUMMARY",
    sourceRules: rulesJson
  };
}

export function buildRulesJsonFromPolicyEditorDraft(
  draft: PolicyEditorDraft
): Record<string, unknown> {
  const nextRules = toObject(draft.sourceRules);

  nextRules.categories = draft.categories
    .map((category) => {
      const id = category.id.trim();
      const action = category.action.trim().toUpperCase();
      if (!id || !action) {
        return null;
      }
      const payload: Record<string, unknown> = {
        id,
        action
      };
      const reviewRequiredBelow = numberOrRaw(category.reviewRequiredBelow);
      if (typeof reviewRequiredBelow !== "undefined") {
        payload.review_required_below = reviewRequiredBelow;
      }
      return payload;
    })
    .filter((item): item is Record<string, unknown> => item !== null);

  const defaults = toObject(nextRules.defaults);
  const autoApply = numberOrRaw(draft.autoApplyConfidenceThreshold);
  if (typeof autoApply !== "undefined") {
    defaults.auto_apply_confidence_threshold = autoApply;
  } else {
    delete defaults.auto_apply_confidence_threshold;
  }
  defaults.require_manual_review_for_uncertain = draft.requireManualReviewForUncertain;
  nextRules.defaults = defaults;

  nextRules.reviewer_requirements = draft.reviewerRequirementsEnabled;
  nextRules.escalation_flags = draft.escalationFlagsEnabled;

  const pseudonymisation = toObject(nextRules.pseudonymisation);
  pseudonymisation.mode = draft.pseudonymMode.trim().toUpperCase();
  const aliasingRules = toObject(pseudonymisation.aliasing_rules);
  aliasingRules.prefix = draft.aliasPrefix.trim();
  pseudonymisation.aliasing_rules = aliasingRules;
  nextRules.pseudonymisation = pseudonymisation;

  const generalisation = toObject(nextRules.generalisation);
  generalisation.by_category = {
    DATE: draft.dateSpecificityCeiling.trim().toUpperCase(),
    LOCATION: draft.placeSpecificityCeiling.trim().toUpperCase(),
    AGE: draft.ageSpecificityCeiling.trim().toUpperCase()
  };
  nextRules.generalisation = generalisation;

  nextRules.reviewer_explanation_mode = draft.reviewerExplanationMode.trim();

  return nextRules;
}

export function stringifyPolicyRules(rulesJson: Record<string, unknown>): string {
  return JSON.stringify(rulesJson, null, 2);
}

export function isDraftDirty(
  initialRulesJson: Record<string, unknown>,
  initialName: string,
  draft: PolicyEditorDraft
): boolean {
  const nextRules = buildRulesJsonFromPolicyEditorDraft(draft);
  const currentName = draft.name.trim();
  if (currentName !== initialName.trim()) {
    return true;
  }
  return JSON.stringify(initialRulesJson) !== JSON.stringify(nextRules);
}

function resolveCategoryRule(
  categories: PolicyCategoryRuleDraft[],
  categoryId: string
): PolicyCategoryRuleDraft | null {
  const normalizedCategory = categoryId.trim().toUpperCase();
  for (const category of categories) {
    if (category.id.trim().toUpperCase() === normalizedCategory) {
      return category;
    }
  }
  return null;
}

function resolveGeneralizedValue(
  input: PolicySimulationInput,
  draft: PolicyEditorDraft
): string | null {
  if (input.categoryId === "DATE") {
    if (draft.dateSpecificityCeiling === "YEAR") {
      return "1901";
    }
    if (draft.dateSpecificityCeiling === "MONTH_YEAR") {
      return "March 1901";
    }
    return `Unsupported date ceiling ${draft.dateSpecificityCeiling}`;
  }
  if (input.categoryId === "LOCATION") {
    if (draft.placeSpecificityCeiling === "REGION") {
      return "North West";
    }
    if (draft.placeSpecificityCeiling === "COUNTY") {
      return "Cumbria";
    }
    return `Unsupported place ceiling ${draft.placeSpecificityCeiling}`;
  }
  if (input.categoryId === "AGE") {
    if (draft.ageSpecificityCeiling === "TEN_YEAR_BAND") {
      return "40-49";
    }
    if (draft.ageSpecificityCeiling === "FIVE_YEAR_BAND") {
      return "45-49";
    }
    return `Unsupported age ceiling ${draft.ageSpecificityCeiling}`;
  }
  return null;
}

function evaluateSampleAction(
  input: PolicySimulationInput,
  draft: PolicyEditorDraft
): {
  action: string;
  transformedValue: string | null;
  needsReviewReason: string | null;
} {
  const categoryRule = resolveCategoryRule(draft.categories, input.categoryId);
  const action = categoryRule ? categoryRule.action.trim().toUpperCase() : "MASK";
  const categoryReviewThreshold = categoryRule
    ? toMaybeNumber(categoryRule.reviewRequiredBelow)
    : null;
  const defaultThreshold = toMaybeNumber(draft.autoApplyConfidenceThreshold);

  if (
    categoryReviewThreshold !== null &&
    input.confidence < categoryReviewThreshold
  ) {
    return {
      action: "NEEDS_REVIEW",
      transformedValue: null,
      needsReviewReason: `confidence ${input.confidence.toFixed(2)} < category review threshold ${categoryReviewThreshold.toFixed(2)}`
    };
  }

  if (
    defaultThreshold !== null &&
    draft.requireManualReviewForUncertain &&
    input.confidence < defaultThreshold
  ) {
    return {
      action: "NEEDS_REVIEW",
      transformedValue: null,
      needsReviewReason: `confidence ${input.confidence.toFixed(2)} < auto-apply threshold ${defaultThreshold.toFixed(2)}`
    };
  }

  return {
    action,
    transformedValue:
      action === "GENERALIZE" ? resolveGeneralizedValue(input, draft) : null,
    needsReviewReason: null
  };
}

function collectGuardrails(draft: PolicyEditorDraft): PolicyGuardrailIssue[] {
  const issues: PolicyGuardrailIssue[] = [];
  const defaultThreshold = toMaybeNumber(draft.autoApplyConfidenceThreshold);

  for (const category of draft.categories) {
    const action = category.action.trim().toUpperCase();
    if (!POLICY_ACTION_OPTIONS.includes(action as (typeof POLICY_ACTION_OPTIONS)[number])) {
      issues.push({
        code: "UNSUPPORTED_ACTION",
        level: "danger",
        message: `Category ${category.id || "(missing id)"} uses unsupported action ${action}.`
      });
    }
    if (action === "ALLOW") {
      issues.push({
        code: "ALLOW_RULE_BROAD",
        level: "warning",
        message: `Category ${category.id || "(missing id)"} is configured as ALLOW; verify disclosure intent before activation.`
      });
    }

    const categoryThreshold = toMaybeNumber(category.reviewRequiredBelow);
    if (
      defaultThreshold !== null &&
      categoryThreshold !== null &&
      categoryThreshold >= defaultThreshold
    ) {
      issues.push({
        code: "THRESHOLD_CONTRADICTION",
        level: "warning",
        message:
          `Category ${category.id || "(missing id)"} review_required_below (${categoryThreshold.toFixed(2)}) ` +
          `is >= defaults.auto_apply_confidence_threshold (${defaultThreshold.toFixed(2)}).`
      });
    }
  }

  if (!["DETERMINISTIC", "DISABLED", "NONE", "OFF"].includes(draft.pseudonymMode.trim().toUpperCase())) {
    issues.push({
      code: "UNSUPPORTED_PSEUDONYM_MODE",
      level: "warning",
      message: `Pseudonymisation mode ${draft.pseudonymMode || "(empty)"} may be unsupported by current validators.`
    });
  }

  if (!DATE_CEILINGS.includes(draft.dateSpecificityCeiling as (typeof DATE_CEILINGS)[number])) {
    issues.push({
      code: "OVER_SPECIFIC_DATE",
      level: "danger",
      message: `Date generalisation ceiling ${draft.dateSpecificityCeiling || "(empty)"} is outside supported safe levels.`
    });
  }
  if (!PLACE_CEILINGS.includes(draft.placeSpecificityCeiling as (typeof PLACE_CEILINGS)[number])) {
    issues.push({
      code: "OVER_SPECIFIC_PLACE",
      level: "danger",
      message: `Place generalisation ceiling ${draft.placeSpecificityCeiling || "(empty)"} is outside supported safe levels.`
    });
  }
  if (!AGE_CEILINGS.includes(draft.ageSpecificityCeiling as (typeof AGE_CEILINGS)[number])) {
    issues.push({
      code: "OVER_SPECIFIC_AGE",
      level: "danger",
      message: `Age generalisation ceiling ${draft.ageSpecificityCeiling || "(empty)"} is outside supported safe levels.`
    });
  }

  return issues;
}

export function runPolicySimulation(draft: PolicyEditorDraft): PolicySimulationReport {
  const summary: Record<string, number> = {
    MASK: 0,
    PSEUDONYMIZE: 0,
    GENERALIZE: 0,
    NEEDS_REVIEW: 0,
    ESCALATE: 0,
    ALLOW: 0,
    REVIEW: 0
  };

  const samples: PolicySimulationSample[] = POLICY_SIMULATION_INPUTS.map((input) => {
    const evaluation = evaluateSampleAction(input, draft);
    summary[evaluation.action] = (summary[evaluation.action] ?? 0) + 1;
    return {
      id: input.id,
      label: input.label,
      categoryId: input.categoryId,
      confidence: input.confidence,
      action: evaluation.action,
      transformedValue: evaluation.transformedValue,
      needsReviewReason: evaluation.needsReviewReason
    };
  });

  return {
    summary,
    samples,
    guardrails: collectGuardrails(draft)
  };
}
