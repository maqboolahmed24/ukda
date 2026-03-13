You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed sources before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first. The canonical web-first and recall-first execution patches already live there. Reconcile repository entry points against those files instead of creating parallel product documentation.

## Mandatory first actions
1. Inspect the relevant repository areas and any existing implementation this prompt may extend.
2. Read these local files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-00-foundation-release.md`
3. If the repo already contains any architecture/docs files created by earlier runs, read and reconcile them instead of duplicating them or treating them as canonical over `/phases`.

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
- Local phase and blueprint documents win for product behavior, workflow semantics, governance, audit constraints, security boundaries, and acceptance logic.
- Official external docs win only for browser mechanics, framework conventions, accessibility semantics, and responsive implementation details.
- If a local document uses desktop-only language, preserve the intent and translate it to a web-native equivalent instead of copying desktop mechanics literally.

## External official reference pack for platform mechanics only
Use these only for browser/platform/framework mechanics. Do not let them override local product behavior, governance rules, or phase semantics.

- Next.js App Router project structure:
  - https://nextjs.org/docs/app/getting-started/project-structure
  - https://nextjs.org/docs/app/getting-started/layouts-and-pages
  - https://nextjs.org/docs/app/api-reference/file-conventions/route-groups
  - https://nextjs.org/docs/app/api-reference/file-conventions/loading
  - https://nextjs.org/docs/app/getting-started/error-handling
  - https://nextjs.org/docs/app/getting-started/linking-and-navigating
- FastAPI official docs:
  - https://fastapi.tiangolo.com/
  - https://fastapi.tiangolo.com/tutorial/bigger-applications/
  - https://fastapi.tiangolo.com/advanced/settings/
- Accessibility and responsive behavior:
  - https://www.w3.org/TR/WCAG22/
  - https://www.w3.org/WAI/ARIA/apg/
  - https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Media_queries/Using
  - https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-color-scheme
  - https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-contrast
  - https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion
  - https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-transparency

## Objective
Reconcile repo entry points and any stale duplicate docs so the canonical web-first delivery contract in `/phases` is the unmistakable implementation baseline.

This is not a generic rewrite. Preserve the original system intent. Translate desktop-only assumptions into equivalent web-native patterns, but do not create a second source of truth outside `/phases`.

The result of this prompt should make the repository unambiguous about all of the following:
- the product is now actively being implemented as a secure web application
- the phase logic still lives in `/phases`
- the UX direction is sleek, dark, minimal, serious, and research-grade
- the browser UX must be keyboard-first, accessibility-safe, deep-linkable, and bounded-scroll aware
- the target repo topology is `/web`, `/api`, `/workers`, `/packages/ui`, `/packages/contracts`, `/infra`
- later work should treat Phase 0 through Phase 11 as the active execution window for this prompt program
- external docs only govern web/framework mechanics, not product rules

## Product and UX posture you must enforce in the docs
Translate the WinUI visual/interaction intent into a browser-native product language with these non-negotiables:
- dark-first, premium, minimal, quiet, and high-trust
- no fake desktop chrome, no toy dashboards, no AI-assistant visual tropes, no ornamental clutter
- clear object focus, explicit reviewer confidence/provenance state, and strong hierarchy
- smooth zero-state to expert workflow progression
- keyboard-first navigation and strong visible focus
- restrained motion only; respect user preferences for color scheme, contrast, reduced motion, and reduced transparency
- responsive layouts optimized for laptop/desktop research work first, with adaptive panes and deep-linkable routes
- predictable state transitions and bounded work regions instead of chaotic full-page scroll growth

## Implementation scope
Create or update repository entry-point docs so they point cleanly at the canonical `/phases` contracts without changing the underlying phase semantics.

Implement the following:
1. A root README update so any future coding agent immediately understands the active web-first posture.
2. Prompt metadata updates so the prompt backlog points at the canonical `/phases` contracts.
3. Reconciliation of any existing duplicate architecture/design docs so they defer to `/phases` instead of competing with it.

## Required deliverables
Create or update these files:
- `README.md`
- `prompts/README.md`

If equivalent canonical documents already exist under `/phases`, reuse them instead of creating near-duplicates under `docs/**`. Do not create redundant docs.

## Content requirements for the deliverables

### `README.md`
Update the root README so that a new coding agent instantly understands:
- what UKDE is
- where the real product behavior lives
- that the active build posture is now web-first
- the target topology
- where to read next before implementing

### `prompts/README.md`
Update the prompt backlog metadata so that:
- backlog titles are not treated as executable prompt bodies
- shorthand refs resolve to the canonical `/phases` files
- only authored prompt files are executable
- task completion is recorded only after validation succeeds
- missing prompt files are reported instead of being silently invented

## Allowed touch points
You may modify:
- `README.md`
- `prompts/README.md`
- existing duplicate docs outside `/phases/**` if they need to be removed, rewritten, or redirected to the canonical `/phases` sources
- `/phases/**` only when a broken cross-reference or stale execution-metadata statement conflicts with the canonical patches already present there

Do not scaffold `/web`, `/api`, `/workers`, `/packages`, or `/infra` yet unless a small placeholder file is strictly necessary to resolve a broken reference. This prompt does not own application bootstrap.

## Non-goals
Do not do any of the following in this prompt:
- scaffold application code
- add CI/CD
- add auth, RBAC, DB, jobs, workers, or storage code
- create full design-system components
- implement ingest/viewer/transcription/privacy features
- create a second canonical architecture/doc layer that competes with `/phases`
- produce vague strategy prose without implementation-grade guidance

## Quality bar
The docs must be crisp, implementation-oriented, and immediately usable by a coding agent. Avoid fluffy product language. Write with exact boundaries, exact ownership, and exact translation rules.

The UI guidance must feel premium and serious:
- sleek dark tone
- restrained surfaces
- strong spacing discipline
- calm typography
- explicit hierarchy
- efficient researcher/reviewer journeys
- no startup-marketing aesthetic
- no pseudo-AI assistant tone

## Validation
Before finishing:
1. Validate that every internal file reference resolves.
2. Validate that no new duplicate source-of-truth docs were created outside `/phases`.
3. Validate that the repo entry-point docs preserve domain logic in `/phases` while making web-first delivery the active execution mode.
4. If the repo already has markdown lint or docs validation, run it. Otherwise do a manual consistency pass and report the result.

## Acceptance criteria
This prompt is complete only if all are true:
- canonical source-of-truth remains in `/phases`
- the source-of-truth order is explicit
- duplicate architecture authority was not introduced outside `/phases`
- the repo entry-point docs clearly describe the web-first execution mode
- the target topology is explicit
- future coding agents can read the repo and know how to continue without relying on chat memory

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Validation performed
4. Any tightly scoped follow-up risks or assumptions
