You are the implementation agent for UKDE. Work directly in the repository. Do not ask clarifying questions. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: assume zero chat memory and reread the repo plus the listed phase files before changing anything.
- Sequenced: if the repo already contains partial implementation from earlier prompts, extend and reconcile it instead of restarting from scratch.

The actual product source of truth is the extracted `/phases` directory in repo root. Do not mention or expect a zip. Read `/phases` first on every run.

## Mandatory first actions
1. Inspect the full repository tree.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/phase-05-privacy-redaction-workflow-v1.md`
3. Then review the current repository generally — privacy schemas, token anchors, transcription outputs, jobs/workers, approved assist model assignment if present, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second detector framework, a second basis taxonomy, or conflicting span-normalization logic.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for direct-identifier-first detector priorities, fusion rules, reviewer-facing assist limits, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that rules remain authoritative for structured identifiers, local NER assists rather than replaces deterministic detection, and local LLM assistance can explain review routing but cannot auto-apply decisions by itself.

## Objective
Implement direct-identifier detection with rules, dictionaries, and local NER assistance inside the secure environment.

This prompt owns:
- the direct-identifier detection pipeline
- rule-based structured-identifier detectors
- local NER detectors for names, places, and organisations
- optional bounded reviewer-facing local LLM assistance
- span normalization onto canonical token/span offsets
- fusion rules and basis attribution
- finding creation into canonical `redaction_findings`
- triage and workspace highlighting for detected findings
- deterministic privacy gold-set recall gates

This prompt does not own:
- masking decision application
- area-mask fallback geometry decisions beyond what is needed to create findings truthfully
- dual-control review flows
- external AI services
- a second detector taxonomy or schema

## Phase alignment you must preserve
From Phase 5 Iteration 5.1:

### Required detectors
Rule-based:
- `Presidio` email
- `Presidio` phone
- `Presidio` postcode
- `Presidio` ID-like patterns
- `Presidio` URLs

Local NER:
- `GLiNER` names
- `GLiNER` places
- `GLiNER` organisations

Optional local LLM assistance:
- `Qwen3-4B` bounded assist mode only
- explain why a finding was routed to review
- summarize special-category or context cues for the reviewer
- never auto-apply a decision without corroborating rule or NER evidence

### Fusion rules
- normalize every detector output onto canonical token/span offsets before merge
- exact-pattern `RULE` matches win as `basis_primary` for structured identifiers such as email, phone, postcode, URL, and ID-like values
- same-category overlaps from multiple detectors merge into one finding, keep the highest-confidence authoritative detector as `basis_primary`, and preserve corroborating detectors in `basis_secondary_json`
- cross-category overlaps, partial overlaps with conflicting spans, or `RULE`/`NER` disagreements default to `NEEDS_REVIEW`
- optional assist output may explain a routed conflict, but it cannot resolve detector disagreement by itself

### Output rules
- populate `redaction_findings`
- auto-apply only when `basis_primary` evidence is above the pinned baseline policy-snapshot threshold
- findings already classified as `NEEDS_REVIEW` due to detector conflict are never auto-applied, regardless of confidence threshold
- optional assist output may enrich `basis_secondary_json` or `assist_explanation_key`, but it can never become the sole basis for `AUTO_APPLIED`
- default low-confidence findings to `NEEDS_REVIEW`

### Required tests
- deterministic span extraction with no off-by-one errors
- UK-format detector validation
- NER wrapper timeout and empty-output handling
- local LLM assistance timeout falls back cleanly to rules plus NER only
- synthetic PII pack maintains near-100% recall for direct identifiers
- `DIRECT_IDENTIFIER_RECALL_FLOOR` is sourced from the versioned policy snapshot or pinned config used by the run, not an ad hoc hardcoded constant
- build fails if recall drops below `DIRECT_IDENTIFIER_RECALL_FLOOR`

## Implementation scope

### 1. Canonical detector pipeline
Implement or refine one canonical privacy-detection pipeline.

Requirements:
- uses the existing jobs/run framework for privacy runs where appropriate
- no second detector subsystem
- direct-identifier-first behavior
- deterministic normalization onto canonical spans
- reviewer-facing outputs only
- internal-only execution with no external API calls

### 2. Rule and dictionary detectors
Implement or refine the structured detector layer.

Requirements:
- exact-pattern detection for email, phone, postcode, URL, and ID-like patterns
- local dictionary or lookup assets may be used only in ways that fit the canonical rule/heuristic basis model
- dictionary-backed hits must still normalize onto canonical spans
- no uncontrolled free-text lookup layer separate from the fusion model
- rule hits remain authoritative for structured identifiers

### 3. Local NER detectors
Implement the local NER layer.

Requirements:
- GLiNER-backed names, places, and organisations
- timeout and empty-output handling
- output normalization into canonical spans
- confidence and category mapped into the canonical finding schema
- same-category and cross-category overlap behavior remains consistent with the fusion rules

### 4. Bounded assist layer
Implement reviewer-facing assist only within the allowed safety boundary.

Requirements:
- local/internal-only bounded assist
- assist can explain why a finding was routed to review
- assist can summarize special-category or context cues
- assist cannot create an `AUTO_APPLIED` finding without corroborating rule or NER evidence
- assist output may populate reviewer-visible explanation artefacts only
- no hidden reasoning or chain-of-thought persistence

### 5. Fusion and finding population
Implement the canonical merge/fusion logic.

Requirements:
- same-category overlap merge
- authoritative `basis_primary`
- corroborating `basis_secondary_json`
- conflicting overlaps route to `NEEDS_REVIEW`
- confidence and status are explicit and typed
- findings attach to page and line references where possible
- `redaction_findings` remains the current projection fed by the detection pipeline

### 6. Triage and workspace integration
Refine the UI enough to make detection real.

Requirements:
- triage and workspace show detected spans with category chips
- confidence and basis are visible
- filters by category and review status work
- no fake results before a run exists
- empty/loading/error states remain calm and exact

### 7. Recall-floor and deterministic regression
Add the required test and gate coverage.

Requirements:
- deterministic span extraction
- UK-format validator coverage
- NER timeout and empty-output tests
- assist timeout fallback tests
- detector conflict-resolution tests
- synthetic PII recall floor gate
- failures are reviewable and actionable

### 8. Audit and documentation
Use the canonical audit path and document the detector stack.

Requirements:
- no second audit path
- logs remain privacy-safe
- docs explain:
  - detector roles
  - fusion rules
  - basis semantics
  - assist boundaries
  - recall floor gates

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / workers / contracts
- direct-identifier detector pipeline
- local NER integration
- bounded assist explanation path
- fusion logic
- finding population
- tests and recall-floor gates

### Web
- triage/workspace highlighting, confidence, and basis surfaces

### Docs
- direct-identifier detection and fusion doc
- assist-boundary and recall-floor doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small triage/highlight refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- masking decision engine
- dual-control review flows
- external AI services
- a second basis taxonomy
- a second detector framework
- hidden reasoning persistence

## Testing and validation
Before finishing:
1. Verify direct identifiers are detected and normalized deterministically.
2. Verify UK-format detectors behave correctly.
3. Verify GLiNER timeouts and empty outputs are handled safely.
4. Verify assist timeouts fall back to rules plus NER only.
5. Verify same-category overlaps merge correctly.
6. Verify conflicting overlaps route to `NEEDS_REVIEW`.
7. Verify assist cannot create `AUTO_APPLIED` findings by itself.
8. Verify synthetic PII recall meets the pinned floor.
9. Verify docs match the implemented detector, fusion, and assist behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- direct-identifier detection is real
- local NER support is real
- bounded assist is real and safely constrained
- fusion rules are real
- triage and workspace views render detector findings with typed status, confidence, and source fields from API responses
- recall-floor gates protect regression
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks
