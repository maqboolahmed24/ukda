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
   - `/phases/phase-04-handwriting-transcription-v1.md`
3. Then review the current repository generally — transcription workspace routes, transcript-version models, compare APIs, compare-decision persistence, variant-layer models, audit code, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second transcript-history system, a second compare route family, or conflicting reviewer-lineage semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. current repository state as the implementation reality to reconcile with
  2. this prompt
  3. the precise `/phases` files listed above
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for append-only correction history, compare-finalization semantics, optimistic-lock conflict handling, reviewer-visible lineage, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that engine outputs and reviewer corrections remain immutable history, compare decisions are explicit, and no hidden reasoning text is persisted or surfaced.

## Objective
Implement manual correction, conflict control, reviewer lineage, and compare views across transcript generations.

This prompt owns:
- transcript-generation history and lineage surfaces
- compare views across engine output, corrected versions, composed runs, and optional normalised layers
- reviewer-visible lineage for who changed what and why
- conflict-control UX across transcript edits and compare decisions
- immutable compare-finalization into `REVIEW_COMPOSED` runs
- line- and token-level compare/read surfaces
- browser-grade reviewer workflows for reviewing generations without mutating source history

This prompt does not own:
- new inference engines
- token-anchor generation
- privacy or redaction workflows
- automatic compare merges or silent promotions
- a second correction system outside the canonical transcription workspace and compare route

## Phase alignment you must preserve
From Phase 4.3, 4.5, and 4.6:

### Existing append-only correction rules
- every correction appends a new `transcript_versions` row
- the previous active version is linked through `superseded_by_version_id`
- engine output is never overwritten
- optimistic concurrency uses `version_etag`
- corrected PAGE-XML and `transcription_output_projections` are updated from approved corrections

### Existing compare rules
- compare route:
  - `/projects/:projectId/documents/:documentId/transcription/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={pageNumber}&lineId={lineId}&tokenId={tokenId}`
- compare decisions are explicit
- compare finalization creates a new `REVIEW_COMPOSED` run
- source runs remain immutable
- no automatic merge or silent promotion

### Existing assist/variant rules
- normalised layers remain explicitly separate from diplomatic text
- `transcript_variant_layers` and `transcript_variant_suggestion_events` remain auditable
- no hidden reasoning text is shown or persisted

### Reviewer lineage intent
Reviewers must be able to understand:
- which engine or version produced the text
- which reviewer corrected it
- when it changed
- whether the current text came from:
  - engine output
  - reviewer correction
  - compare finalization
  - normalised suggestion acceptance

## Implementation scope

### 1. Canonical transcript-history surfaces
Implement or refine reviewer-visible transcript history.

Requirements:
- line-level transcript version history is inspectable
- page-level generation history is inspectable
- active transcript version is clearly distinguished from prior versions
- source engine/output lineage is visible
- reviewer edits and compare-finalized generations remain visible as separate immutable history
- no second hidden history model outside the canonical tables

If the repo needs small helper reads, add the closest coherent equivalents of:
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines/{lineId}/versions`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines/{lineId}/versions/{versionId}`

### 2. Compare views across transcript generations
Extend the canonical compare path so it is genuinely useful for reviewers.

Requirements:
- compare base vs candidate runs
- where the current repo supports it cleanly, compare corrected generations or selected line versions without inventing a second compare family
- line-level diff
- token-level diff when token anchors exist
- engine and version metadata visible
- explicit user decisions only
- no silent merge behavior

Where needed, you may extend the existing compare read path with optional version-aware parameters only if that keeps the route family coherent and does not create a parallel compare contract.

### 3. Reviewer lineage presentation
Implement reviewer-visible lineage in the web app.

Requirements:
- actor
- timestamp
- change reason when present
- source type:
  - engine output
  - reviewer correction
  - compare decision / composed run
  - normalised suggestion event where applicable
- lineage remains dense, exact, and calm
- no noisy “activity feed” styling

Good locations:
- workspace line history drawer
- compare side panel
- run detail lineage section
- page-level generation history section

### 4. Conflict control and stale-write UX
Harden conflict handling across edit and compare decisions.

Requirements:
- stale `version_etag` conflicts surface clearly and calmly
- compare-decision stale state or source-run drift is handled safely
- users can refresh and continue without losing trust in the workflow
- no silent overwrite of newer work
- unsaved local edits and compare choices are visible but not noisy
- conflict surfaces remain bounded and keyboard-safe

### 5. Compare decision finalization
Implement or refine compare finalization into immutable composed output.

Requirements:
- compare decisions remain append-only
- finalization creates a new `REVIEW_COMPOSED` transcription run
- `params_json` captures:
  - `baseRunId`
  - `candidateRunId`
  - compare-decision snapshot hash
  - page scope if applicable
- finalization rebuilds PAGE-XML and token anchors from the approved decisions
- source runs remain immutable
- reviewer lineage clearly shows that the composed run came from compare decisions

### 6. Workspace integration
Refine the transcription workspace to make version history and compare review practical.

Requirements:
- selected line can open version history
- compare route can deep-link back into workspace context
- current line and token context survive compare navigation
- line history and compare flows remain keyboard-safe
- the workspace remains bounded single-fold
- no second workspace shell is created

### 7. Variant-layer lineage refinement
When normalised or assist layers are present, keep their lineage reviewable.

Requirements:
- variant layers show exact `base_transcript_version_id`
- suggestion events show accept/reject history
- compare/history surfaces do not blur diplomatic and normalised layers together
- diplomatic transcript remains primary

### 8. Audit and regression
Use the canonical audit path and add regression coverage.

At minimum cover:
- version history retrieval
- compare reads across generations
- compare decision recording
- compare finalization producing a `REVIEW_COMPOSED` run
- source runs remain immutable after finalization
- stale-write conflict detection
- reviewer lineage surfaces reflect actor and source correctly
- no hidden reasoning text is surfaced or persisted

### 9. Documentation
Document:
- transcript-generation history model
- compare semantics across runs and corrected generations
- reviewer lineage semantics
- conflict-control rules
- `REVIEW_COMPOSED` run provenance
- how later prompts must preserve immutable history while extending correction and evaluation features

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- version-history read surfaces
- compare-view refinements across generations
- compare finalization hardening
- typed lineage contracts
- tests

### Web
- transcript history UI
- compare refinements
- reviewer-lineage surfaces
- conflict-control UX

### Docs
- transcript history and compare-lineage doc
- conflict-control and reviewer-lineage doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small compare/history/drawer/conflict refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- new inference engines
- token-anchor generation
- privacy/redaction logic
- automatic merge or silent promotion
- a second compare route family
- a second transcript-history system

## Testing and validation
Before finishing:
1. Verify transcript versions remain immutable and queryable.
2. Verify compare views can inspect source vs candidate generations coherently.
3. Verify compare finalization creates a `REVIEW_COMPOSED` run without mutating source runs.
4. Verify reviewer lineage surfaces show actor, source, time, and reason where available.
5. Verify stale `version_etag` conflicts are handled safely.
6. Verify workspace and compare route deep-link context remains coherent.
7. Verify variant-layer lineage remains separate from diplomatic history.
8. Verify no hidden reasoning text is shown or persisted.
9. Verify docs match the implemented history, compare, and lineage behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- reviewer-visible transcript history is real
- compare views across generations are real
- compare finalization is immutable and auditable
- conflict control is trustworthy
- reviewer lineage is explicit and useful
- the repo remains ready for later evaluation and privacy work without lineage churn
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks
