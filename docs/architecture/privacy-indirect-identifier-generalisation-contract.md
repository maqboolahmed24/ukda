# Privacy Indirect-Identifier Generalisation Contract

Status: Updated through Prompt 74
Scope: Deterministic indirect-identifier transforms, policy specificity ceilings, heuristic grouping metadata, and downstream-safe action lineage for privacy reruns

## Canonical behavior

Indirect-identifier handling is deterministic, policy-controlled, auditable, and reviewer-explainable.

No secondary transformation engine is allowed. All date/place/age generalisation behavior flows through the canonical backend generalisation module and persists as standard redaction findings plus decision events.

## Deterministic transforms

Supported transforms:

- exact date -> `MONTH_YEAR` or `YEAR`
- town -> `COUNTY` or `REGION`
- exact age -> `FIVE_YEAR_BAND` or `TEN_YEAR_BAND`

Determinism rules:

- equivalent text inputs always produce equivalent transformed values under the same policy snapshot
- transform results are ordered and stable by page, line, span, and category
- out-of-range or invalid date/age candidates are rejected from transform output

## Policy specificity ceilings

Generalisation specificity is constrained by policy and cannot exceed configured ceilings.

Supported policy read paths:

- `generalisation` or `generalization`
- `specificity_ceiling` / `specificityCeiling`
- category overrides via `by_category` / `byCategory`
- category action mapping from `categories[].id` and `categories[].action`

Ceiling enforcement:

- date ceiling: `YEAR` <= `MONTH_YEAR`
- place ceiling: `REGION` <= `COUNTY`
- age ceiling: `TEN_YEAR_BAND` <= `FIVE_YEAR_BAND`

A requested transform is clamped to the policy ceiling when needed, and the clamp result is persisted in reviewer-visible metadata.

## Indirect-risk heuristics

Heuristic grouping metadata supports indirect-risk combinations such as:

- place + rare occupation + exact date
- uncommon kinship + small locality

Grouping output is metadata-only and reviewer-visible. It does not bypass deterministic policy evaluation and does not directly authorize action changes.

## Reviewer-visible explanation boundaries

Finding metadata (`basisSecondaryJson`) contains bounded fields:

- `transformation`: deterministic rule id, source type, applied specificity, ceiling, transformed value
- `generalizationExplanation`: reviewer-facing summary
- `indirectRiskGrouping`: grouped heuristic context with `metadataOnly=true`
- optional `assistSummary`: local-assist explanation metadata only

Hard boundaries:

- no chain-of-thought persistence
- local assist cannot request a more specific output than policy allows
- explanation metadata is separate from transformed output text

## Action lineage and compare compatibility

Findings preserve applied action distinctions as `MASK`, `PSEUDONYMIZE`, or `GENERALIZE`.

Compare surfaces expose:

- per-page action deltas and changed action counts
- run-level action compare state: `AVAILABLE`, `NOT_YET_RERUN`, `NOT_YET_AVAILABLE`
- explicit page-level action compare availability

Preview generation uses action-aware rendering:

- `MASK` redacts span text
- `PSEUDONYMIZE` / `GENERALIZE` replace span text when deterministic replacement text exists

Prior runs are immutable. Policy reruns produce new run lineage and do not mutate historical outputs.

## Downstream compatibility (Phase 8 and Phase 10)

Generalised output is persisted in normal redaction findings/decision lineage so downstream candidate-snapshot, release-pack, and derivative-index consumers can interpret transformed values without reinterpreting policy internals.

Downstream consumers rely on stored action type + finding metadata lineage rather than recomputing transforms.

## Prompt sequencing

- Prompt 75 deepens policy authoring UX, simulation, and guardrails for experts.
- Prompt 76 deepens policy-rerun orchestration, regression packs, rollback paths, and activation gates.
