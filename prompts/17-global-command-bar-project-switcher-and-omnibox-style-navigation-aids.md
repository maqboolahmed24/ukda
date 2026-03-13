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
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md` for project-switcher/header behavior, command hierarchy, keyboard rules, and workspace command-bar expectations
3. Then review the current repository generally — shell code, routes, header/nav layout, auth context, project context, existing search or palette utilities, shared UI primitives, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second header model, a second project-switcher path, or a conflicting command system.

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
- `/phases` wins for command hierarchy, shell/header ownership, project-switcher placement, keyboard-first behavior, adaptive workspace expectations, and UX tone.
- Official docs win only for implementation mechanics.
- Preserve the browser-native Obsidian contract. Do not regress into consumer-style search UI, fake AI-assistant chat chrome, or a second hidden navigation paradigm.

## Objective
Build the global command bar, project switcher, and omnibox-style navigation aids for expert users.

This prompt owns:
- a canonical global command bar / command palette
- a real project switcher in the shell header
- expert-user quick navigation and quick action patterns
- keyboard-safe omnibox-style navigation aids
- role-aware command registration and visibility
- tight shell integration for current routes
- command/search primitives that later phases can extend

This prompt does not own:
- full discovery search across document content or transcript text
- semantic search
- public/global search indexing
- feature-specific command systems inside every page
- destructive action execution without proper confirmation and authorization
- a second navigation tree that competes with the shell/nav rail

## Phase alignment you must preserve
From the UI blueprint and Phase 1 shell rules:

### Header / shell contract
- header includes:
  - product identity
  - project switcher
  - deployment environment label
  - project access-tier badge
  - help entry point
  - user menu
- no page primary CTA belongs in the global header
- workflow actions belong in page headers or contextual command bars

### Command hierarchy
- shell navigation -> page header primary action -> contextual command bar -> overflow/flyout -> item context menu
- every contextual command must also be reachable without relying on right-click context menus

### Keyboard and focus rules
- keyboard-first behavior is required
- toolbar and command surfaces must remain keyboard-safe
- shortcuts are stable and discoverable
- predictable escape behavior
- no keyboard traps
- sticky chrome or overlays must never fully obscure the current focus target

### Visual tone
- sleek dark tone
- minimal, serious, calm
- no AI-assistant aesthetic
- no marketing search box theatrics
- no noisy floating command toys

## Implementation scope

### 1. Canonical global command bar
Implement or refine one canonical global command bar.

Requirements:
- one obvious global entrypoint
- keyboard shortcut support suitable for browser/macOS workflows:
  - `Meta+K` on macOS
  - `Ctrl+K` fallback where appropriate
- command palette opens as a calm, dense, keyboard-safe overlay
- type-to-filter results
- grouped results with clear labels
- strong empty/no-result and loading states
- focus returns safely on close
- command execution is exact and does not leave ambiguous state

The command bar must feel like an internal expert tool, not a consumer search widget.

### 2. Command registration architecture
Implement a real command-registration model that later work can extend.

Requirements:
- typed command definitions
- stable command IDs
- labels, keywords, and optional grouping
- scope awareness:
  - global
  - authenticated
  - current project
  - admin/governance
  - current page/workspace
- role-aware visibility
- safe disabled/unavailable handling where helpful
- no ad hoc hardcoded command lists in unrelated routes

The command bar must be extensible without forcing later work to rewrite it.

### 3. Project switcher
Implement or refine the project switcher as a first-class shell control.

Requirements:
- header placement matches the shell contract
- project list contains only projects the current user may access
- project role and access-tier context are visible where useful
- current project is obvious
- switching projects lands on a consistent route:
  - preserve the nearest matching section when sensible
  - otherwise fall back safely to project overview
- keyboard-safe open, navigate, and select behavior
- calm, dense UI; no giant consumer-style dropdown

Integrate the switcher into the command bar as well where it improves expert flow.

### 4. Omnibox-style navigation aids
Implement quick navigation and command discovery without turning the feature into uncontrolled search.

Good candidates:
- navigate to accessible app sections
- switch current project
- jump to current project subsections
- open admin/governance routes the caller is authorized to access
- open high-frequency safe actions that already exist
- show recent routes or recent project contexts if that stays small and privacy-safe

Rules:
- no cross-project leakage
- no document-content search
- no transcript search
- no hidden access to routes the user cannot open
- no execution of high-risk actions without the same confirmation and authorization path those actions require elsewhere

### 5. Role-aware and route-aware visibility
The command system must understand authorization and context.

Requirements:
- `ADMIN` sees platform-admin commands for explicitly allowed routes
- `AUDITOR` sees only read-only governance commands explicitly allowed to them
- project-only commands require project membership unless a route explicitly opts into a platform-role override
- unauthorized commands are hidden or clearly unavailable according to the repo's UX style, with a preference for not teasing inaccessible control
- commands adapt to the current route and current project context

### 6. Data sourcing and API use
Use the least disruptive data path already present in the repo for:
- current user context
- project memberships
- project summaries needed by the switcher
- role or permission context if already exposed

If the repo lacks a clean, minimal API path, you may add the smallest correct helper endpoints needed to support:
- current user / role context
- current user's projects for switching
- current project navigation context if useful

Do not build a broad search backend here.

### 7. Accessibility and interaction hardening
The command bar and switcher must be accessible and keyboard-safe.

Requirements:
- accessible names and roles
- clear initial focus
- arrow-key navigation where appropriate
- predictable escape behavior
- screen-reader-safe active/selected semantics
- strong visible focus in dark, light, and high-contrast modes
- reduced-motion-safe open/close behavior
- no keyboard trap
- no lost focus on route navigation

### 8. Gallery and diagnostics
Use `/admin/design-system` or the current equivalent internal gallery to expose real diagnostics for:
- command bar open/closed states
- no-result state
- loading state
- keyboard traversal
- project switcher states
- high-contrast and reduced-motion behavior

This route must demonstrate the real implementation, not fake examples disconnected from app usage.

### 9. Documentation
Document:
- command hierarchy and ownership
- how commands are registered
- how project switching is resolved
- how route/role filtering works
- what later work may add
- what later work must not do ad hoc

## Required deliverables

### Web / shared UI
- global command bar
- project switcher
- command registry or typed command-definition layer
- shell integration
- role-aware command filtering
- keyboard-safe omnibox interactions

### Docs
- command system / omnibox contract doc
- project-switcher behavior doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/packages/ui/**`
- `/packages/contracts/**` only if small shared command/project-context enums or types help consistency
- `/api/**` only if a very small helper route is required for current user or switcher data
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- full-text content search
- transcript or document search
- semantic search
- enterprise-wide command routing separate from the app shell
- destructive bulk actions executed without confirmation
- a chat-like AI command surface
- a second project navigation system outside the canonical shell

## Testing and validation
Before finishing:
1. Verify the command bar opens and closes with the intended keyboard shortcut.
2. Verify focus lands correctly on open and returns correctly on close.
3. Verify command filtering is role-aware and context-aware.
4. Verify unauthorized commands are not exposed incorrectly.
5. Verify project switching works and preserves context where sensible.
6. Verify keyboard-only navigation works in the command bar and switcher.
7. Verify dark/light/high-contrast and reduced-motion behavior is not broken.
8. Verify the internal gallery reflects the real command and switcher implementation.
9. Verify docs match the implemented behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- a real global command bar exists
- a real project switcher exists
- expert navigation aids are keyboard-safe and role-aware
- the command system does not leak inaccessible routes or data
- command surfaces are keyboard-invokable (`Ctrl/Cmd+K`) and return focus to the triggering context on close
- the feature reduces friction without creating a second navigation paradigm
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks
