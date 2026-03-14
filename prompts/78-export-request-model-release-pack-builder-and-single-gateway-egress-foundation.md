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
   - `/phases/phase-08-safe-outputs-export-gateway.md`
3. Then review the current repository generally — governance-ready outputs, candidate snapshot scaffolding, governance artefacts, current routes, typed contracts, audit code, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second export-request model, a second release-pack format, or a second egress path outside the canonical export gateway family.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for candidate snapshots, export request lineage, release-pack content, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that output screening starts from immutable candidate snapshots and a deterministic release pack, not from live mutable working files.

## Objective
Build the export-request model, release-pack builder, and single-gateway egress foundation.

This prompt owns:
- immutable export candidate snapshots
- export request and request-history schema
- request-scoped frozen release-pack generation
- requester-side export candidate and export request routes
- request revision / resubmission lineage
- release-pack preview and frozen request-pack retrieval
- risk classification and review-path pinning at submission
- typed APIs and browser shells for export request creation/history

This prompt does not own:
- reviewer dashboard and decision workflow UI
- gateway receipt attachment
- no-bypass receipt enforcement across the whole stack
- SLA/aging operations
- provenance bundle or derivative output registration beyond candidate snapshots

## Phase alignment you must preserve
From Phase 8 Iteration 8.0:

### Candidate snapshots
Implement or reconcile `export_candidate_snapshots` with:
- immutable source lineage
- governance artefact pins and hashes
- policy lineage fields where applicable
- `candidate_kind`
- `artefact_manifest_json`
- `candidate_sha256`
- eligibility and supersession fields

Rules:
- approved governance-ready Phase 6 outputs register immutable candidate snapshots
- Phase 7 reruns register new candidate snapshots instead of mutating older ones
- superseded candidates remain explicit through supersession links
- candidate reads follow the pinned governance lineage, not a live mutable projection

### Export requests
Implement or reconcile:
- `export_requests`
- `export_request_events`
- `export_request_reviews`
- `export_request_review_events`

Rules:
- request submission freezes a request-scoped release pack artefact
- risk classification is deterministic at submission
- `RESEARCHER` can see only own requests
- `RESEARCHER` can create requests and resubmit returned requests through successor revisions for owned requests
- `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can see all requests in the project
- `PROJECT_LEAD` and `ADMIN` can create requests and resubmit returned requests project-wide
- `REVIEWER` and `AUDITOR` are read-only for requester-side request mutations
- `AUDITOR` has read-only access

### Required requester-side routes
- `/projects/:projectId/export-candidates`
- `/projects/:projectId/export-candidates/:candidateId`
- `/projects/:projectId/export-requests`
- `/projects/:projectId/export-requests/new?candidateId={candidateId}`
- `/projects/:projectId/export-requests/new?candidateId={candidateId}&supersedesExportRequestId={exportRequestId}` (resubmission path)
- `/projects/:projectId/export-requests/:exportRequestId`
- `/projects/:projectId/export-requests/:exportRequestId/events`
- `/projects/:projectId/export-requests/:exportRequestId/reviews`

### Release pack
Release pack must include at least:
- file list, sizes, hashes
- candidate snapshot ID and request revision
- policy snapshot hash or explicit policy lineage
- source artefact references
- approved model references by role
- redaction counts by category
- reviewer override count
- conservative area-mask count
- risk flags and classifier reason codes
- governance manifest and ledger pins
- release-review checklist

## Implementation scope

### 1. Candidate snapshot schema and registration
Implement or refine the canonical candidate-snapshot model.

Requirements:
- append-only, immutable candidate snapshots
- supersession links
- policy and governance lineage pins
- eligibility status and candidate kind
- no ad hoc exportable-file table outside the canonical candidate model

### 2. Release-pack builder
Implement the deterministic release-pack builder.

Requirements:
- candidate-scoped preview release pack
- request-scoped frozen release pack on submission
- deterministic bytes and hashes for same candidate/request revision
- frozen request-scoped pack used for later review, not a live regenerated pack
- no leakage of raw internal paths or mutable references

### 3. Export-request schema and request revision lineage
Implement or refine the request model.

Requirements:
- request revision lineage through supersedes fields
- immutable request history
- requester identity, purpose statement, bundle profile, risk classification, review path, and release-pack pins captured at submission
- returned requests can later resubmit through successor revisions
- no in-place request mutation that destroys history

### 4. Requester-side APIs
Implement or refine:
- candidate list/detail/read
- candidate release-pack preview
- request create
- request resubmit as successor revision (with `supersedes_export_request_id`)
- request list/detail/status
- request-scoped release-pack read
- request events and review-read surfaces needed by requester/history views

Requirements:
- typed contracts
- clear role filtering
- deterministic read behavior
- no second export-request API family

### 5. Requester-side routes and UX
Implement or refine the requester-facing UI.

Requirements:
- candidate list and detail
- new-request flow from candidate to release-pack preview to submit
- request history by status/requester
- request detail with status, release-pack summary, events, and review-read surface
- calm empty/loading/error/not-ready states
- no false implication of approval or export

### 6. Risk classification and review-path pinning
Persist deterministic classification.

Requirements:
- risk classification derived from the pinned release-pack fields
- `review_path` and `requires_second_review` persist at submission
- no ad hoc UI-local risk logic
- no mutation of risk path after submission except through successor request revisions

### 7. Audit and regression
Use the canonical audit path and add coverage.

At minimum cover:
- candidate snapshot immutability
- request submission persists frozen release pack
- resubmission creates successor revision rather than mutating prior request
- requester/project role visibility rules
- risk classification determinism
- release-pack summary matches candidate lineage
- no raw internal storage leakage

### 8. Documentation
Document:
- candidate snapshot contract
- request/revision lineage
- release-pack builder rules
- requester-side route ownership
- what Prompt 79 and 80 will deepen next

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- candidate snapshot model
- release-pack builder
- export request and review schema
- typed APIs
- tests

### Web
- export candidate list/detail
- request wizard / submit flow
- request history and detail surfaces

### Docs
- export-request and release-pack contract doc
- candidate snapshot and request-revision lineage doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**` if release-pack generation needs worker support
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small export-list/detail/wizard refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- reviewer dashboard UI
- decision workflow UI beyond request read surfaces
- gateway receipt attachment
- no-bypass enforcement across infrastructure
- SLA/aging operations
- a second release-pack system

## Testing and validation
Before finishing:
1. Verify candidate snapshots are immutable and lineage-pinned.
2. Verify request submission freezes a request-scoped release pack.
3. Verify request revisions supersede rather than mutate prior requests.
4. Verify requester visibility and mutate rules are correct (`RESEARCHER` own create/resubmit only, `PROJECT_LEAD`/`ADMIN` project-wide create/resubmit, `REVIEWER`/`AUDITOR` read-only for requester-side mutations).
5. Verify risk classification is deterministic from the release pack.
6. Verify release-pack summaries match pinned candidate lineage.
7. Verify requester-side review-read endpoints (`/events` and `/reviews`) are covered by integration tests for role visibility and lineage correctness.
8. Verify docs match the implemented candidate, request, and release-pack behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- export candidate snapshots are real
- export requests and frozen release packs are real
- requester-side routes are real
- request revision lineage is real
- requester-side review-read endpoints and request/release-pack lineage checks are implemented and covered by integration tests
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks
