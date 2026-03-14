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
   - `/phases/phase-05-privacy-redaction-workflow-v1.md`
3. Then review the current repository generally — privacy routes, findings APIs, page-review APIs, preview APIs, shared UI primitives, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second privacy workspace, a second finding-resolution flow, or conflicting review-state semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for workspace goals, deep-link semantics, page-approval rules, override behavior, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the privacy workspace as a fast, bounded, review-grade tool. Do not turn it into a general dashboard, a giant form, or a second document viewer.

## Objective
Create the privacy workspace for fast resolution with approve, override, false-positive, and next-unresolved flows.

This prompt owns:
- the real Phase 5.3 privacy workspace interaction model
- `Open next unresolved`, `Open finding`, `Open line`, and `Open token` deep-link flows
- approve / override / false-positive finding actions
- page-approval UX and gating
- immediate controlled vs safeguarded preview comparison inside the workspace
- finding list, transcript panel, and highlight sync
- append-only decision and page-review UX over the canonical APIs
- keyboard-safe high-throughput reviewer ergonomics

This prompt does not own:
- dual-control run completion logic across the whole run
- compare views across reruns
- detector logic
- masking engine changes
- governance/manifest/export workflows

## Phase alignment you must preserve
From Phase 5 Iteration 5.3:

### Workspace goals
1. Find the next unresolved item quickly.
2. Confirm, reject, or override with minimal friction.
3. See immediate effect in Controlled and safeguarded-preview modes.
4. Capture reason, reviewer identity, and timestamps for every non-trivial decision.
5. Approve a page only when review rules are satisfied.
6. Surface conservative reviewer explanations for ambiguous findings without turning them into authoritative decisions.

### Required deep links
- `Open next unresolved` opens the first unresolved finding on the correct page.
- `Open finding` uses `?page={pageNumber}&runId={runId}&findingId={findingId}`.
- `Open line` uses `?page={pageNumber}&runId={runId}&lineId={lineId}`.
- `Open token` uses `?page={pageNumber}&runId={runId}&tokenId={tokenId}` when token-linked highlighting is available.
- `page={pageNumber}` is a 1-based UI page index; API `{pageId}` must resolve deterministically from the run's canonical page ordering (`pageNumber = page_index + 1`) with no ad hoc client-only remapping.

### Interaction rules
- toolbar uses roving focus and remains a single tab stop
- modal dialogs trap focus and return it correctly
- `Approve page` stays disabled until unresolved count is `0`
- overrides require a reason
- high-risk overrides require second review when any of the following are true:
  - the override changes a finding to `FALSE_POSITIVE`
  - the override introduces or replaces a conservative `area_mask_id`
  - the finding category is marked dual-review-required by the pinned policy snapshot
  - the finding had detector disagreement or ambiguous overlap recorded in `basis_secondary_json`
- `REVIEWER`, `PROJECT_LEAD`, or `ADMIN` can approve pages and apply overrides; `AUDITOR` does not participate in Phase 5 review actions

### Existing APIs to use or refine
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/findings`
- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/findings/{findingId}`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/review`
- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/review`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/preview-status`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/preview`

### Existing review semantics
- finding changes append `redaction_decision_events`
- page review changes append `redaction_page_review_events`
- optimistic concurrency uses `decision_etag` and `review_etag`
- stale writes must be rejected, not silently overwritten
- approved runs remain immutable and must reject later finding and page-review mutations

## Implementation scope

### 1. Canonical privacy workspace
Implement or refine:
- `/projects/:projectId/documents/:documentId/privacy/workspace?page={pageNumber}&runId={runId}&findingId={findingId}&lineId={lineId}&tokenId={tokenId}`

Requirements:
- bounded single-fold shell
- left rail with page thumbnails and review status
- center page image with finding highlights
- right panel with transcript and findings list
- toolbar with:
  - previous / next page
  - `Next unresolved`
  - show / hide highlights
  - `Show safeguarded preview`
- deep-link-safe loading and refresh
- calm, dense, review-grade tone

### 2. Next-unresolved navigation
Implement or refine the fast-review navigation flow.

Requirements:
- `Next unresolved` navigates to the next unresolved finding deterministically
- page, finding, line, and token context update coherently
- back/forward and refresh preserve context
- when no unresolved items remain, the workspace shows a truthful and useful state
- no client-only hidden cursor that breaks reload safety

### 3. Finding resolution actions
Implement fast reviewer actions for the current selected finding.

Requirements:
- approve / confirm
- override
- false positive
- reason capture where required
- exact mapping to the canonical finding decision API
- stale `decision_etag` conflicts surface calmly and clearly
- unauthorized users cannot mutate findings
- no silent mutation after run approval lock

### 4. Page approval flow
Implement or refine page approval in the workspace.

Requirements:
- `Approve page` disabled while unresolved count > 0
- page approval uses the canonical page-review API
- stale `review_etag` conflicts are surfaced safely
- page review status is visible in the rail and panel
- page approval state updates immediately and coherently after successful writes

### 5. Controlled vs safeguarded preview toggle
Refine the workspace mode switch.

Requirements:
- `Controlled view` and `Safeguarded preview` remain exact and truthful
- preview-status loading and errors are surfaced cleanly
- preview output updates after decision changes according to canonical preview-generation behavior
- no raw text or raw storage-path leakage
- no fake preview when preview status is not ready

### 6. Highlight, transcript, and finding sync
Harden the tri-panel review behavior.

Requirements:
- finding selection highlights on the page image
- line and token deep links focus the intended transcript area when anchors exist
- transcript and finding list remain in sync with canvas highlights
- no keyboard traps
- no page-height blowout in default states

### 7. High-risk override UX
Support override classification without implementing full dual-control completion here.

Requirements:
- high-risk override conditions are surfaced clearly
- required reason capture is enforced
- the UI indicates when second review will be required later
- no dual-control bypass path is created
- `AUDITOR` cannot apply overrides

### 8. Browser quality and accessibility
Add or refine workspace coverage.

At minimum cover:
- default state
- selected finding
- override dialog
- safeguarded preview mode
- next-unresolved navigation
- keyboard navigation for toolbar, findings list, transcript panel, and dialogs
- focus visibility and reflow/zoom in bounded regions

### 9. Documentation
Document:
- privacy workspace ownership
- deep-link semantics
- finding-resolution flows
- page-approval gating
- high-risk override behavior
- what Prompt 64 will deepen around dual control and rerun compare

## Required deliverables
Create or refine the closest coherent equivalent of:

### Web
- privacy workspace
- deep-link navigation
- finding approve/override/false-positive actions
- next-unresolved flow
- page-approval UX
- controlled vs safeguarded preview toggle
- browser tests and visual baselines

### Backend / contracts
- only tiny helper or typed read refinements if strictly needed for the canonical workspace to remain coherent

### Docs
- privacy workspace UX contract doc
- finding-resolution and page-approval doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**` only if tiny helper/contract refinements are strictly needed
- `/packages/contracts/**`
- `/packages/ui/**`
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- detector logic
- decision-engine logic
- dual-control run completion
- compare across reruns
- a second workspace shell
- governance/export features

## Testing and validation
Before finishing:
1. Verify `Open next unresolved` navigates deterministically.
2. Verify `findingId`, `lineId`, and `tokenId` deep links restore correct context.
3. Verify approve / override / false-positive flows use the canonical append-only APIs.
4. Verify override requires a reason when appropriate.
5. Verify `Approve page` remains disabled until unresolved count is zero.
6. Verify stale `decision_etag` and `review_etag` conflicts are handled safely.
7. Verify controlled vs safeguarded preview toggling is truthful.
8. Verify keyboard and accessibility checks pass on the workspace flows.
9. Verify docs match the implemented workspace behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the privacy workspace is a real fast-review surface
- next-unresolved, approve, override, and false-positive flows are real
- page approval is properly gated
- preview and highlight behavior are coherent
- the workspace enforces fixed panel bounds and keyboard navigation behavior verified by interaction tests
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks
