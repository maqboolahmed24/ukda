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
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md` for empty/loading/error/success expectations across shell, import, library, viewer, and ingest-status surfaces
3. Then review the current repository generally — state components, loading placeholders, error handling, toasts, banners, shell pages, admin pages, current protected routes, and tests — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second feedback language, random one-off empty states, or spinner-heavy chaos.

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
- `/phases` wins for UX tone, shell continuity, loading/error expectations, single-fold discipline, and acceptance logic.
- Official docs win only for implementation mechanics.
- Maintain the product's calm, exact, trustworthy tone. Do not introduce chirpy consumer copy, dramatic error pages, or generic spinner walls.

## Objective
Design zero, empty, loading, error, and success states that make the product feel calm, exact, and trustworthy.

This prompt owns:
- the shared state language for the web product
- skeletons, empty states, safe error states, success confirmations, and route/section feedback patterns
- consistent copy tone for system feedback
- integration of those states into current shell/admin/project routes
- Phase-1-ready state patterns for near-term document/import/viewer surfaces without faking full feature completion
- feedback-priority rules for toast vs inline vs page-level states

This prompt does not own:
- the full implementation of future feature workflows
- back-end error taxonomy redesign beyond small improvements needed for safe UX
- giant illustration-heavy state screens
- noisy notification systems
- a second alert/feedback system outside the shared UI layer

## Phase alignment you must preserve
From Phase 0 and Phase 1 guidance:

### Loading rule
- prefer skeleton loading over spinner-only patterns
- loading states must preserve shell continuity and layout stability
- long-running operations should expose status clearly, not imply random progress

### State expectations already called out in Phase 1
- wizard empty/uploading/error states
- document library empty/loading/filtered states
- viewer loading/ready/error states
- ingest-status timeline and failure surfaces
- safe user-facing errors
- quota and validation errors shown inline and actionable
- details shown in drawers or secondary routes, not noisy inline clutter

### Tone rule
The UX must remain:
- calm
- exact
- trustworthy
- serious
- minimal
- non-marketing
- non-AI-ish

### Copy rule
- be specific when the system knows something
- be explicit when the system does not know something
- avoid blame
- avoid hype
- avoid vague “something went wrong” when a safer actionable explanation exists
- avoid celebratory fluff for routine success

## Implementation scope

### 1. Shared state vocabulary and patterns
Create or refine a canonical state system.

At minimum define and implement consistent patterns for:
- zero state
- empty state
- loading state
- error state
- success state
- partial/degraded state where useful
- disabled/unavailable state where useful

The goal is consistency across the product, not one-off route-specific inventions.

### 2. Shared primitives and composition rules
Use or refine the shared UI layer so these state patterns are reusable.

At minimum support:
- skeleton blocks / skeleton layouts
- page-level empty states
- section-level empty states
- inline validation or blocking error presentation
- route-level safe error panels
- success confirmation patterns
- subtle progress/status presentation
- no-results / filtered-results state
- disabled-feature and not-yet-available state patterns for reserved routes

If shared primitives already exist in the repo, build on them instead of inventing a second feedback system.

### 3. Feedback-priority hierarchy
Implement and document a clear hierarchy for system feedback.

Rules:
- toast for low-risk transient confirmation only
- inline alert/banner for actionable contextual information
- page-level state for major workflow conditions
- route-level error boundary for route failure
- not-found is distinct from empty
- disabled is distinct from unauthorized
- loading is distinct from waiting on a long-running job
- success should not erase context the user still needs

This hierarchy must be reflected in current route implementations.

### 4. Current-route state integration
Integrate the state system into the routes that already exist.

At minimum reconcile:
- `/login`
- `/projects`
- current project overview/jobs/activity/settings routes
- current admin routes such as audit, operations, security, and design-system if present
- root/auth redirect surfaces where useful
- any current health/error routes if present

Requirements:
- empty states are useful and quiet
- loading states preserve shell rhythm
- success feedback is restrained
- error states are safe and actionable
- disabled/export-stub/admin-boundary routes remain clear and serious

### 5. Near-term Phase 1 state readiness
Without faking full feature completion, prepare the state language for the next feature prompts.

Create reusable or gallery-backed state patterns for:
- import wizard empty/uploading/error
- document library empty/loading/no-results
- viewer loading/error
- ingest-status timeline loading/error
- job progress and safe failure summaries
- drawer/detail loading and empty cases

Do not build the full ingest/viewer product here unless a small scaffold is already present.
Do build the state-ready patterns so later work can reuse them.

### 6. Copy and messaging discipline
Create or refine a consistent microcopy contract for product states.

Requirements:
- short, exact titles
- useful next step when one exists
- explicit non-destructive language where relevant
- safe user-facing errors without internal leakage
- environment-appropriate wording
- no emoji, no cheerleading, no vague “AI” wording

Document these rules and apply them to the current surfaces.

### 7. Success and completion behavior
Implement clear success language.

Requirements:
- success states should confirm the result without derailing the workflow
- toast should not be the only success signal if the resulting page state also changed
- multi-step actions should preserve clear completion context
- success on privileged or dangerous actions should be especially exact and traceable

### 8. Documentation and gallery support
Document:
- state vocabulary
- feedback-priority hierarchy
- copy guidelines
- which states belong at page, section, dialog, drawer, toast, and route-boundary levels
- how later work should reuse these patterns

If useful, add a dedicated state section inside `/admin/design-system` so the system is visible and testable.

## Required deliverables

### Shared UI
- shared state primitives/compositions
- skeleton patterns
- empty/error/success presentation patterns
- copy/usage guardrails

### Web
- current shell/admin/project/auth routes updated to use the shared state language
- design-system gallery state section if helpful

### Docs
- state system and feedback-priority doc
- UX copy guideline doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/packages/ui/**`
- `/web/**`
- `/packages/contracts/**` only if small shared status/error enums help consistency
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- full ingest workflow
- full document library
- full viewer
- flashy illustration systems
- giant marketing-style empty screens
- a noisy global notification center
- vague generic error handling that hides useful context

## Testing and validation
Before finishing:
1. Verify loading states use skeletons where appropriate rather than spinner-only patterns.
2. Verify empty, no-results, disabled, unauthorized, and not-found states are distinct.
3. Verify route-level errors are safe and actionable.
4. Verify success feedback is restrained and does not depend only on toast.
5. Verify copy tone stays calm, exact, and trustworthy.
6. Verify dark/light/high-contrast behavior is not broken.
7. Verify current key routes now feel more consistent in their state handling.
8. Verify any gallery state section is using real shared primitives.
9. Verify docs match the implemented state system and copy rules.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the product has one consistent state language
- zero, empty, loading, error, and success states are reusable and consistent
- current routes use the state system meaningfully
- near-term Phase 1 states are prepared without fake feature completion
- state copy follows the documented feedback style guide and is covered by route-level snapshot tests
- current routes use shared state components for zero/empty/loading/error/success instead of ad hoc per-route variants
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks
