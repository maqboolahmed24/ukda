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
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-06-redaction-manifest-ledger-v1.md`
3. Then review the current repository generally — governance routes, manifest APIs, ledger APIs, verification APIs, status projections, shared UI primitives, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second governance shell, a second manifest viewer, or conflicting evidence-ledger drill-down patterns.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for manifest vs ledger access separation, tab ownership, route ownership, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that manifest is screening-safe for project leads/reviewers, while full evidence-ledger surfaces are deeper, controlled-only, and restricted to `AUDITOR` and `ADMIN`.

## Objective
Design manifest surfaces for project leads and reviewers, and evidence-ledger surfaces for auditors and admins with deep drill-down clarity.

This prompt owns:
- the governance web surfaces for Manifest and Evidence Ledger
- role-aware tab visibility and access messaging
- manifest entries table, filters, raw JSON viewer, and status surfaces
- ledger timeline, diff summary, verification history, and integrity badge UI
- deep drill-down navigation from overview -> run detail -> manifest / ledger / events
- bounded, keyboard-safe, review-grade governance surfaces

This prompt does not own:
- manifest generation logic
- ledger generation logic
- export workflows
- a second governance shell
- widening ledger access to project roles that are not allowed to see raw evidence

## Phase alignment you must preserve
From Phase 6 Iteration 6.0, 6.1, and 6.2:

### Governance routes
- `/projects/:projectId/documents/:documentId/governance`
  - tabs:
    - `Overview`
    - `Runs`
    - `Manifest`
    - `Evidence ledger`
- `GET /projects/{projectId}/documents/{documentId}/governance/overview`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/overview`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/overview`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/manifest`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/ledger`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/events`

### Manifest surface rules
- filterable table by category, page, review state, and timestamp
- rows and filters backed by `GET .../manifest/entries?...`
- raw JSON viewer for `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR`
- authenticated internal stream or staged retrieval action with clear `Internal-only` and `Not export-approved` status

### Evidence-ledger surface rules
- event timeline
- diff summary
- integrity badge from `GET .../ledger/verify/status`
- `ADMIN` can trigger re-verification through `POST .../ledger/verify`
- explicit warning when raw evidence is restricted
- list and timeline rows backed by `GET .../ledger/entries?view={list|timeline}...`
- diff summary backed by `GET .../ledger/summary` for full ledger surfaces (`AUDITOR` and `ADMIN`)

### Access rules
- manifest surfaces readable by `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR`
- full ledger surfaces (ledger tab, entries/timeline, verification-history controls) are limited to `AUDITOR` and `ADMIN`
- `PROJECT_LEAD` and `REVIEWER` may see decision-history safe summaries on non-ledger surfaces but not raw ledger payloads or `/ledger/**` endpoints
- `RESEARCHER` does not access Phase 6 ledger surfaces
- non-ledger safe summaries for `PROJECT_LEAD` and `REVIEWER` are sourced from governance overview/run-overview surfaces (`GET /projects/{projectId}/documents/{documentId}/governance/overview` and `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/overview`), not from ledger routes

## Implementation scope

### 1. Canonical governance shell refinement
Implement or refine one coherent governance shell.

Requirements:
- route group and run-detail routes feel like one product
- tabs remain stable and deep-link-safe
- overview, manifest, ledger, and events fit one visual system
- no competing internal governance UI appears elsewhere

### 2. Manifest tab and run-manifest surface
Implement or refine the manifest surfaces.

Requirements:
- dense filterable manifest entries table
- filters:
  - category
  - page
  - review state
  - time range
- raw JSON viewer for allowed roles
- clear `Internal-only` and `Not export-approved` status
- calm empty/loading/error/not-ready states
- row drill-down clarity without turning the page into a giant debug dump

### 3. Evidence-ledger surface
Implement or refine the evidence-ledger UI.

Requirements:
- event timeline
- diff summary
- integrity badge
- verification-history view
- raw-evidence warning banner for restricted contexts
- `ADMIN`-only re-verification control
- list and timeline modes backed by the canonical ledger APIs
- no leakage of raw evidence to disallowed roles

### 4. Role-aware navigation and messaging
Harden role-specific visibility.

Requirements:
- `PROJECT_LEAD` and `REVIEWER` can use manifest and governance-overview safe summary views but not the ledger tab or raw ledger payloads
- `AUDITOR` and `ADMIN` can open full ledger surfaces
- `RESEARCHER` sees no ledger entrypoint
- unauthorized users receive calm, exact access messaging
- do not tease hidden controls unnecessarily

### 5. Drill-down clarity
Make deep inspection usable.

Requirements:
- run list -> run overview -> manifest/ledger/events is coherent
- manifest table rows can reveal screening-safe detail
- ledger rows can reveal restricted evidence detail for allowed roles
- verification history is easy to follow
- the surfaces stay bounded and keyboard-safe

### 6. Status and integrity surfacing
Expose the operational truth.

Requirements:
- manifest status
- ledger status
- verification status
- governance-ready badge or equivalent run-level status indicator
- failed / pending / ready / canceled states remain exact and calm
- no fake “all good” visuals when replacement generation or verification is incomplete

### 7. Browser quality and accessibility
Add or refine browser coverage.

At minimum cover:
- governance overview
- manifest tab
- manifest raw JSON viewer
- ledger timeline
- ledger diff summary
- integrity badge and verification history
- role-specific visibility
- keyboard navigation and focus visibility

### 8. Documentation
Document:
- manifest vs ledger surface ownership
- role-based visibility rules
- deep drill-down navigation
- what later prompts preserve for governance, provenance, and export handoff

## Required deliverables
Create or refine the closest coherent equivalent of:

### Web
- manifest surfaces
- evidence-ledger surfaces
- role-aware governance navigation
- verification-history and integrity presentation
- browser tests and visual baselines

### Docs
- governance manifest and ledger UX contract doc
- role-based governance surface access doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/web/**`
- `/packages/ui/**`
- `/packages/contracts/**` only if tiny view/status enums help coherence
- `/api/**` only if tiny helper or typed read refinements are strictly needed
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- manifest generation
- ledger generation
- export workflows
- a second governance shell
- widening ledger access beyond allowed roles

## Testing and validation
Before finishing:
1. Verify manifest surfaces are readable by allowed roles.
2. Verify ledger surfaces are limited to `AUDITOR` and `ADMIN`.
3. Verify `RESEARCHER` cannot access ledger surfaces.
4. Verify manifest filters and raw JSON viewer work coherently.
5. Verify ledger timeline, summary, and verification-history views work coherently.
6. Verify `ADMIN`-only re-verification control visibility and behavior.
7. Verify governance drill-down preserves filter context and links to manifest and ledger records by stable IDs.
8. Verify focus, keyboard, and accessibility behavior on all covered governance surfaces.
9. Verify docs match the implemented governance UI behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- manifest surfaces are clear and screening-safe
- evidence-ledger surfaces are deep, exact, and correctly restricted
- governance drill-down preserves filter context and links to manifest and ledger records by stable IDs
- role-based access messaging is accurate
- the governance UI is bounded, dense, and review-grade
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks
