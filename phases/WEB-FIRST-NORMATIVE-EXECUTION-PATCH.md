# UKDE Web-First Normative Execution Patch

> Status: ACTIVE NORMATIVE EXECUTION PATCH
> Scope: Prompt-program implementation posture
> Precedence: Overrides older desktop-first delivery assumptions for prompt execution

This patch updates the implementation posture for the prompt program only.

Keep the domain logic, governance rules, data entities, API intent, audit posture, and recall-first behavior from the `/phases` folder as the product source of truth.

Replace the old desktop-first delivery assumption with a web-first execution contract.

## 1.1 Active Program Scope
- Product target: secure web application delivered through the browser.
- Development posture: web-focused, macOS-friendly, laptop/desktop-first, responsive down to tablet where practical.
- Root topology to build toward:
  - `/web` - browser frontend
  - `/api` - backend API
  - `/workers` - async jobs and pipeline workers
  - `/packages/ui` - shared design system and web primitives
  - `/packages/contracts` - shared schemas, DTOs, and typed contracts
  - `/infra` - deployment, runtime, and operational configuration
- Active execution window for this prompt program: Phase 0 through Phase 11.
- Phase 6 through Phase 11 are ACTIVE for this prompt sequence and are no longer treated as deferred for prompt planning.
- Goal: if the coding agent runs Prompt 01 through Prompt 100 in order, the repo should evolve into a complete end-to-end production-ready system across frontend and backend.

## 1.2 Source-of-Truth Hierarchy
Use this precedence in every actual prompt later given to the coding agent:

1. Current repository state at execution time.
2. This web-first update section.
3. `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` whenever recall-first, token anchors, rescue logic, search anchoring, or conservative masking are relevant.
4. The specific phase file(s) owned by the prompt.
5. `/phases/blueprint-ukdataextraction.md`
6. `/phases/README.md`
7. `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
8. Official external documentation for platform mechanics only.

## 1.3 Conflict Resolution Rule
- Local phase contracts win for product behavior, workflow ownership, governance, audit, security boundaries, data semantics, and acceptance logic.
- Official external docs win for web-platform mechanics, browser accessibility semantics, responsive behavior, routing conventions, frontend implementation details, and framework usage.
- If a local document uses desktop-only terminology or WinUI-only components, preserve the intent and translate it into an equivalent web pattern instead of copying desktop mechanics literally.

## 1.4 Web-First Translation of the Existing UI Blueprint
Translate the existing visual and interaction intent into a browser-native system:

- dark-first, premium, minimal, calm, and high-trust
- strong focus visibility and keyboard-first operation
- responsive, logic-driven layouts with adaptive panes and deep-linkable routes
- no fake desktop chrome, no noisy AI-looking UI, no ornamental clutter
- zero-state to expert workflow should feel straight, seamless, and obvious
- confidence, provenance, review state, and uncertainty must always be visible when relevant
- motion must be restrained, purposeful, and preference-aware
- browser implementation should respect user preferences for color scheme, contrast, reduced motion, and reduced transparency
- use accessible web interaction patterns for toolbars, dialogs, drawers, menus, grids, forms, and navigation

## 1.5 Prompt Independence + Sequencing Contract
Every future implementation prompt must be both independent and sequenced:

- Independent means the prompt must assume zero chat memory and tell the coding agent to reread the repo plus the listed source files every time.
- Sequenced means the prompt should also assume the repo may already contain work from earlier prompts and should extend or refine that code rather than redoing the product from scratch.
- Every actual prompt must explicitly restate:
  - objective
  - exact source references
  - implementation scope
  - allowed file/folder touch points
  - deliverables
  - tests
  - acceptance criteria
  - non-goals
  - conflict-resolution rule
- Never tell the agent to rely on "what the previous prompt said." Tell it to inspect the repository and the listed source files again.

## 1.6 Frontend / Backend Posture for the Web Build
- Frontend direction: Next.js App Router + React + TypeScript as the browser-first product surface.
- Backend direction: FastAPI remains the API backbone.
- Persistence and operations remain aligned with the phase contracts: database, object storage, append-only audit/evidence stores, worker pipelines, governed export path, and internal-only model execution.
- All AI/model inference remains internal; there is no external AI API egress path.
- Export/release remains the only governed route out of the secure environment.

## 1.7 UX Non-Negotiables for the Web Implementation
- sleek, dark, modern, and minimal
- expert-grade density without chaos
- clear visual hierarchy and strong object focus
- straight-line user journeys for ingest, review, approval, and release
- excellent zero, empty, loading, error, and success states
- deterministic navigation and predictable state transitions
- accessibility-safe keyboarding, focus management, and route changes
- performance-conscious page structure, streaming, and asset delivery
- responsive layouts optimized first for laptop/desktop research work

## 1.8 Mandatory External Knowledge Baseline for Actual Prompts
When a prompt needs external platform guidance, it should cite official docs only, prioritizing:

- WCAG 2.2
- WAI-ARIA Authoring Practices Guide (APG)
- MDN responsive design and media queries
- MDN user preference media features:
  - `prefers-color-scheme`
  - `prefers-contrast`
  - `prefers-reduced-motion`
  - `prefers-reduced-transparency`
- Next.js App Router official docs
- FastAPI official docs
- OpenTelemetry official docs
- PostgreSQL official docs

## 1.9 Reference Shorthand
- `README` = `/phases/README.md`
- `Blueprint` = `/phases/blueprint-ukdataextraction.md`
- `UI` = `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
- `Patch` = `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
- `P00` = `/phases/phase-00-foundation-release.md`
- `P01` = `/phases/phase-01-ingest-document-viewer-v1.md`
- `P02` = `/phases/phase-02-preprocessing-pipeline-v1.md`
- `P03` = `/phases/phase-03-layout-segmentation-overlays-v1.md`
- `P04` = `/phases/phase-04-handwriting-transcription-v1.md`
- `P05` = `/phases/phase-05-privacy-redaction-workflow-v1.md`
- `P06` = `/phases/phase-06-redaction-manifest-ledger-v1.md`
- `P07` = `/phases/phase-07-policy-engine-v1.md`
- `P08` = `/phases/phase-08-safe-outputs-export-gateway.md`
- `P09` = `/phases/phase-09-provenance-proof-bundles.md`
- `P10` = `/phases/phase-10-granular-data-products.md`
- `P11` = `/phases/phase-11-hardening-scale-pentest-readiness.md`

## 1.10 Routing and Query Conventions
- Browser URL examples in the phase docs use `:param` notation for path parameters.
- App Router filesystem examples use `[param]` notation for the same parameterized URL contract.
- Browser `page` query parameters are human-facing 1-based page numbers unless a route explicitly says otherwise.
- Persisted storage and data-model fields continue to use explicit names such as `page_index` when 0-based indexing is required.

## Execution Note
For prompt execution, this patch supersedes older phase-header fields such as `Desktop Root`, `Active Phase Ceiling`, `Deferred Phase Policy`, and `Desktop Terminology Overlay` when those fields conflict with the web-first contract above.
