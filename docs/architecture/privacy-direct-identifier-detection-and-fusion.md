# Privacy Direct-Identifier Detection and Fusion

Scope: Phase 5.1 direct-identifier detection pipeline, fusion rules, bounded assist behavior, and recall-floor regression gates.

## Detector stack
- Rule detectors (`basis_primary=RULE`) run first for structured identifiers:
  - email
  - phone
  - postcode
  - URL
  - ID-like patterns (including NI and NHS style patterns)
- Dictionary heuristics (`basis_primary=HEURISTIC`) add conservative local cues for:
  - person-name honorific patterns
  - place dictionaries
  - organisation dictionaries and suffix patterns
- Local NER (`basis_primary=NER`) is GLiNER-first when a local model is available; if unavailable, the wrapper falls back to local deterministic heuristics.
- All detector execution is internal-only and does not call external services.

## Normalization and fusion
- Every detector match is normalized to canonical line-relative span offsets.
- Token refs are attached by deterministic overlap between span offsets and line token offsets.
- Same-category overlaps merge into one finding.
- Structured categories preserve rule authority: when a rule hit exists, `RULE` remains primary.
- Corroborating detector evidence is preserved in `basis_secondary_json`.
- Conflict routing is explicit:
  - cross-category overlaps
  - same-category span disagreements
  - rule/NER span disagreements
- Any conflict routes to `NEEDS_REVIEW`.

## Decision routing
- Findings are written to `redaction_findings` through a single canonical write path.
- `AUTO_APPLIED` is allowed only when confidence meets the policy threshold and no conflict reasons are present.
- Low confidence defaults to `NEEDS_REVIEW`.
- Conflict-routed findings remain `NEEDS_REVIEW` regardless of confidence.

## Bounded assist behavior
- Assist mode is reviewer-facing only.
- Assist can add short review-routing summaries into `basis_secondary_json`.
- Assist timeouts or failures degrade safely to rules+dictionary+NER fusion only.
- Assist cannot create findings and cannot auto-apply findings by itself.

## Policy and recall floor
- The direct-identifier recall floor is sourced from the run policy snapshot when available.
- If the snapshot does not define the floor, a pinned runtime config fallback is used.
- CI gate tests run a synthetic direct-identifier fixture pack and fail if recall drops below the resolved floor.
