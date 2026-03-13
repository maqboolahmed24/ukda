You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed phase files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the relevant repository areas and any existing implementation this prompt may extend.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/phase-02-preprocessing-pipeline-v1.md`
3. Then review the current repository generally — preprocessing engine code, profile registry, compare surfaces, quality/rerun flows, storage adapters, variant delivery, tests, performance instrumentation, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second advanced-profile system, a second binary-output path, or conflicting risk-gating rules.

## Source-of-truth hierarchy
Use this precedence order when implementing:
1. The specific `/phases` files listed in this prompt for product behavior and acceptance logic.
2. `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md` when this prompt depends on web-first execution semantics.
3. `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` when this prompt depends on recall-first, rescue, token-anchor, search-anchoring, or conservative-masking semantics.
4. `/phases/blueprint-ukdataextraction.md`, `/phases/README.md`, and `/phases/ui-premium-dark-blueprint-obsidian-folio.md` as supporting product context when they are listed or clearly relevant.
5. This prompt for task scope and deliverables.
6. Current repository state for reconciling implementation details.
7. Official external docs for implementation mechanics only.

Treat current repository state as implementation context, not as the primary source of product truth.

## Conflict-resolution rule
- `/phases` wins for safe-default behavior, optional advanced profile gating, binary-output persistence, bleed-through support, compare-option ownership, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that stronger techniques are optional, controlled, and never silent defaults.

## Objective
Add advanced preprocessing controls with safe defaults, explicit risk gating, and reproducible presets.

This prompt owns:
- advanced preprocessing profiles
- optional binarization outputs
- bleed-through reduction support
- explicit risk labeling and confirmation gates
- advanced profile descriptions and UI disclosure
- compare expansion for grayscale vs binary review
- regression and performance gates for advanced paths
- reproducible preset behavior across API, worker, and UI

This prompt does not own:
- making advanced profiles the default
- uncontrolled bulk aggressive processing
- later layout/transcription/privacy features
- public or external preprocessing services
- a second compare surface

## Phase alignment you must preserve
From Phase 2 Iteration 2.4:

### Iteration Objective
Add stronger techniques as optional, controlled profiles without making them default behavior.

### Backend work
#### Adaptive binarization (optional)
- add adaptive thresholding output in optional profiles
- persist:
  - grayscale output (always)
  - binary output (when enabled)

#### Bleed-through reduction
- support paired recto/verso processing when both sides are available
- provide conservative single-image fallback behind advanced profile
- require `REVIEWER`, `PROJECT_LEAD`, or `ADMIN` confirmation for bulk aggressive processing

### Web client work
#### Profile descriptions
- `Balanced`: safe default
- `Aggressive`: stronger cleanup and optional binarization
- `Bleed-through`: best with paired sides

#### Viewer compare expansion
Compare options:
- `Original vs Gray`
- `Original vs Binary`
- `Gray vs Binary`

Rule:
- avoid showing all variants at once

### Required tests and gates
- regression suite includes:
  - pages where binarization helps
  - pages where binarization harms
- performance gate for bleed-through profile runtime
- UI gate: advanced options remain behind progressive disclosure and clear labels

## Implementation scope

### 1. Advanced profile registry extension
Extend the canonical profile system to support advanced profiles safely.

Requirements:
- `Balanced` remains the safe default
- `Aggressive` is explicit and clearly labeled
- `Bleed-through` is explicit and clearly labeled
- profiles persist expanded params and version identity
- advanced/gated profiles are distinguishable in the registry and UI
- no hidden fallback silently upgrades users to an advanced profile

If the repo already has `Conservative`, preserve it as a distinct profile id/version with unchanged parameter semantics unless an explicit migration is implemented.

### 2. Optional binarization outputs
Implement or refine optional adaptive binarization.

Requirements:
- grayscale output continues to be produced for applicable runs
- binary output is produced only when the selected profile enables it
- binary outputs persist to the canonical storage/result path
- `output_object_key_bin` and `sha256_bin` are populated when enabled
- runs remain reproducible and lineage-linked
- no silent binary path appears for profiles that do not explicitly enable it

### 3. Bleed-through reduction
Implement or refine bleed-through support.

Requirements:
- paired recto/verso processing when both sides are available
- conservative single-image fallback only behind an advanced profile
- runtime and output behavior remain deterministic
- feature availability is explicit when a paired-side context is absent
- failure handling remains exact and safe

Do not make bleed-through correction a silent default for ordinary runs.

### 4. Risk gating and confirmation
Implement explicit confirmation for high-risk bulk advanced processing.

Requirements:
- `REVIEWER`, `PROJECT_LEAD`, and `ADMIN` can confirm advanced bulk processing where allowed
- ordinary users and unsupported roles cannot bypass gating
- bulk aggressive processing requires explicit confirmation
- confirmation copy is exact, calm, and specific about trade-offs
- progressive disclosure keeps advanced options collapsed by default
- the UI does not scare users with theatrical warning copy

### 5. Advanced controls in rerun/create flows
Refine the existing preprocessing create/rerun flows.

Requirements:
- advanced profile descriptions are clear
- advanced options are behind progressive disclosure
- default selection remains safe
- expanded params remain inspectable but not dumped into the main flow
- users can understand what the advanced profile changes without reading raw JSON
- the selected profile and its risk posture are preserved into run metadata and audit trails

### 6. Compare option expansion
Extend the variant choices available within the canonical compare surface and existing viewer compare mode safely.

Requirements:
- supported compare pairs:
  - `Original vs Gray`
  - `Original vs Binary`
  - `Gray vs Binary`
- avoid rendering all variants simultaneously
- compare selection stays bounded and calm
- binary variant availability is checked accurately per page/run
- if a binary variant does not exist, the UI remains exact and safe
- the compare workspace itself is outside this prompt; this prompt only expands the supported variant pairs and related controls

### 7. Variant delivery and contracts
Extend the canonical variant contracts rather than inventing a second path.

Requirements:
- binary variant availability is exposed through the existing canonical variant-selection path or its cleanest equivalent
- asset delivery remains authenticated and internal
- no raw storage or raw-original bypass is introduced
- typed contracts remain aligned across API, worker, and UI

### 8. Regression and performance gates
Add the required gates.

Requirements:
- regression suite covers pages where binarization helps
- regression suite covers pages where binarization harms
- performance gate for bleed-through profile runtime
- UI gate verifies advanced options remain behind progressive disclosure and clear labels
- gates stay deterministic and useful rather than flaky

### 9. Documentation
Document:
- advanced profile semantics
- safe-default policy
- binarization and bleed-through availability rules
- risk gating and confirmation behavior
- compare-option expansion rules
- how later work must avoid turning advanced profiles into silent defaults

## Required deliverables

### Backend / workers / storage / contracts
- advanced profile registry extensions
- optional binary-output support
- bleed-through processing support
- typed variant and run-metadata refinements
- tests and performance gates

### Web
- advanced profile descriptions
- progressive-disclosure advanced controls
- gated confirmation flows
- compare expansion for binary-vs-gray/original pairs
- clear binary-availability handling

### Docs
- advanced preprocessing controls and safe-default policy doc
- binarization/bleed-through compare contract doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- storage adapters/config used by the repo
- `/packages/contracts/**`
- `/packages/ui/**` only if small compare/profile/confirmation refinements are needed
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- making advanced profiles the default
- uncontrolled aggressive bulk processing
- layout/transcription/privacy/export work
- public or external preprocessing services
- a second compare surface
- raw original delivery

## Testing and validation
Before finishing:
1. Verify `Balanced` remains the safe default.
2. Verify advanced profiles remain behind progressive disclosure.
3. Verify binary outputs are created only when the profile enables them.
4. Verify `output_object_key_bin` and `sha256_bin` are populated correctly when enabled.
5. Verify bleed-through behavior is explicit when paired-side data is missing.
6. Verify advanced bulk processing requires explicit confirmation for allowed roles.
7. Verify compare options support:
   - `Original vs Gray`
   - `Original vs Binary`
   - `Gray vs Binary`
8. Verify the regression suite covers both helpful and harmful binarization cases.
9. Verify the performance gate for bleed-through runtime is meaningful.
10. Verify docs match the actual advanced-profile, gating, and compare behavior.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- advanced preprocessing is available but not default
- optional binary outputs are real and lineage-safe
- bleed-through support is real and gated
- advanced bulk processing requires explicit confirmation
- compare surfaces can display and switch between grayscale and binary variants for the same page and run using explicit variant selectors
- advanced options show explicit labels, risk copy, and confirmation steps; no hidden advanced defaults are applied
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks
