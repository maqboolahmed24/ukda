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
   - `/phases/phase-06-redaction-manifest-ledger-v1.md`
3. Then review the current repository generally — approved privacy runs, governance schemas, reviewed snapshot handling, storage adapters, audit code, status/readiness APIs, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second ledger model, a second verification-history model, or a second retrieval path outside the canonical governance routes.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. current repository state as the implementation reality to reconcile with
  2. this prompt
  3. the precise `/phases` files listed above
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for evidence-ledger content, RBAC, append-only integrity rules, verification behavior, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that the evidence ledger is Controlled-only, append-only, hash-chained, and never widened into a broader access surface.

## Objective
Build the controlled-only evidence ledger with append-only integrity and retrieval APIs.

This prompt owns:
- canonical evidence-ledger generation from an approved locked Phase 5 run
- append-only ledger-row serialization
- hash-chain integrity (`prev_hash`, `row_hash` or equivalent canonical structure)
- ledger attempt lineage and regeneration behavior
- ledger verification runs and status APIs
- controlled-only retrieval APIs for raw ledger, entries, summary, and verification history
- readiness projection updates tied to ledger validity
- role-locked access for `AUDITOR` and `ADMIN`

This prompt does not own:
- screening-safe manifest generation
- governance UI polish beyond minimal truthfulness
- export candidate registration
- public download or egress paths
- a second evidence store separate from the canonical ledger artefact

## Phase alignment you must preserve
From Phase 6 Iteration 6.2 and 6.3:

### Required evidence-ledger content
Store append-only evidence rows with:
- before and after text references
- detector evidence summary including `basis_primary` and `basis_secondary_json`
- `assist_explanation_key` and hash when bounded reviewer-facing assist output exists
- actor and timestamp
- override reason when present
- previous hash and row hash for tamper evidence

### Required canonical tables and projections
Use or reconcile:
- `redaction_evidence_ledgers`
- `governance_readiness_projections`
- `governance_run_events`
- `ledger_verification_runs`

Phase 6 table contract to preserve:
- `redaction_evidence_ledgers`:
  - `id`
  - `run_id`
  - `project_id`
  - `document_id`
  - `source_review_snapshot_key`
  - `source_review_snapshot_sha256`
  - `attempt_number`
  - `supersedes_ledger_id`
  - `superseded_by_ledger_id`
  - `status`
  - `ledger_key`
  - `ledger_sha256`
  - `hash_chain_version`
  - timestamps / cancel / failure fields
- `ledger_verification_runs`:
  - `id`
  - `run_id`
  - `attempt_number`
  - supersession fields
  - `status`
  - `verification_result`
  - `result_json`
  - timestamps / cancel / failure fields

### Required RBAC
- ledger access limited to `AUDITOR` and `ADMIN`
- `PROJECT_LEAD` and `REVIEWER` can see decision-history summaries but not raw ledger payloads
- `RESEARCHER` does not access Phase 6 ledger surfaces

### Required APIs
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/status`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/entries?view={list|timeline}&cursor={cursor}&limit={limit}`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/summary`
- `POST /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify/status`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify/runs`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify/{verificationRunId}`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify/{verificationRunId}/status`
- `POST /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify/{verificationRunId}/cancel`

### Required generation and readiness rules
- ledger bytes are append-only artefacts; regenerate never mutates a previously completed row in place
- every ledger attempt pins `source_review_snapshot_key` and `source_review_snapshot_sha256`
- generation is rejected if the frozen review snapshot is missing or mismatched
- successful ledger generation automatically enqueues a verification attempt
- manual verify appends a new verification attempt; it never overwrites prior verification lineage
- `governance_readiness_projections.ledger_verification_status` must reflect the latest canonical verification truth

## Implementation scope

### 1. Canonical ledger serializer
Implement or refine the evidence-ledger serializer.

Requirements:
- deterministic ledger bytes for the same approved snapshot and run metadata
- append-only row structure
- stable ordering
- row-level hash chain
- no raw object-store URL leakage
- no second ad hoc ledger format in route handlers

### 2. Ledger attempt generation
Implement the ledger generation path.

Requirements:
- generation starts only from an approved locked Phase 5 run
- source snapshot key and hash are pinned onto the ledger attempt row
- `ledger_key` and `ledger_sha256` are written only on successful generation
- failed and canceled attempts remain explicit and auditable
- regenerate appends a new attempt and preserves previous successful attempts

### 3. Verification-run lineage
Implement or refine verification attempts.

Requirements:
- `VERIFY_LEDGER` runs are append-only
- verification results persist into `ledger_verification_runs.result_json`
- verification attempts have their own status lineage and can be canceled while `QUEUED` or `RUNNING`
- manual verify does not invalidate the last known valid result unless the replacement attempt proves invalid

### 4. Retrieval APIs
Implement the retrieval surfaces.

Requirements:
- `ledger` endpoint streams only through authenticated internal handlers
- `ledger/entries` supports `list` and `timeline`
- `ledger/summary` provides a compact diff/impact rollup
- verification run list/detail/status endpoints are typed and stable
- no raw storage URLs are returned
- no second retrieval channel exists outside the canonical API family

### 5. Readiness projection integration
Update governance readiness truth coherently.

Requirements:
- readiness remains `PENDING` until a successful ledger exists and verification is `VALID`
- verification status changes update `governance_readiness_projections`
- prior ready pointers remain pinned during replacement attempts until a new valid pair is available
- canceled or failed replacement attempts do not silently clear last known valid readiness

### 6. Audit and governance events
Use the canonical audit and event paths.

Requirements:
- emit or reconcile:
  - `LEDGER_RUN_CREATED`
  - `LEDGER_RUN_STARTED`
  - `LEDGER_RUN_FINISHED`
  - `LEDGER_RUN_FAILED`
  - `LEDGER_RUN_CANCELED`
  - `EVIDENCE_LEDGER_VIEWED`
  - `LEDGER_VERIFICATION_VIEWED`
  - `LEDGER_VERIFY_REQUESTED`
- append-only `governance_run_events` remain the governance history source of truth
- do not create a second event subsystem

### 7. Documentation
Document:
- evidence-ledger generation rules
- append-only row and hash-chain behavior
- verification-run lineage
- controlled-only retrieval rules
- how later manifest/governance/export prompts consume ledger validity

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / storage / contracts
- evidence-ledger serializer
- ledger attempt generation
- verification-run lineage
- retrieval APIs
- readiness projection updates
- tests

### Web
- only tiny truthful status/read refinements if needed for current governance surfaces

### Docs
- evidence-ledger contract and retrieval doc
- verification lineage and readiness doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- storage adapters/config used by the repo
- `/packages/contracts/**`
- `/web/**` only if small truthful ledger-status refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- screening-safe manifest generation
- export candidate registration
- public or external ledger delivery
- a second evidence-ledger format
- widening ledger access beyond `AUDITOR` and `ADMIN`

## Testing and validation
Before finishing:
1. Verify ledger generation is rejected without a valid approved locked Phase 5 snapshot.
2. Verify ledger bytes are deterministic for the same approved input.
3. Verify hash-chain validation succeeds on untampered ledgers.
4. Verify regenerate appends a new ledger attempt without mutating historical rows.
5. Verify verification runs are append-only and independently queryable.
6. Verify unauthorized ledger access is blocked.
7. Verify no raw object-store URLs leak through retrieval APIs.
8. Verify readiness projections reflect ledger validity correctly.
9. Verify docs match the implemented ledger and verification behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the controlled-only evidence ledger is real
- append-only hash-chain integrity is real
- retrieval APIs are real and access-controlled
- verification lineage is real
- downstream governance consumers can rely on the canonical ledger contract
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks
