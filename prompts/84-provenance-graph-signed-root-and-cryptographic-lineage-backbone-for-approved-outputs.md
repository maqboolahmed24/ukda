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
   - `/phases/phase-09-provenance-proof-bundles.md`
3. Then review the current repository generally — export request approvals, candidate snapshots, governance artifacts, model assignments, policy lineage, receipts, storage/signing infrastructure, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second provenance graph format, a second signing scheme, or a second proof store.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for provenance leaf contents, Merkle root rules, signing boundaries, proof immutability, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that provenance proofs are deterministic, append-only attempts tied to approved export requests and candidate snapshots, and suitable for later offline verification.

## Objective
Build the provenance graph, signed root, and cryptographic lineage backbone for approved outputs.

This prompt owns:
- provenance graph assembly over canonical controlled lineage references
- canonical leaf serialization and ordering
- Merkle tree root computation
- internal signing of the root
- immutable provenance proof artefact generation
- provenance proof attempt lineage and regeneration semantics
- provenance summary route and typed proof reads
- deterministic proof generation tests

This prompt does not own:
- bundle building
- bundle verification
- deposit profiles
- a second lineage or proof format
- external key fetches or public signing services

## Phase alignment you must preserve
From Phase 9 Iteration 9.0:

### Required lineage coverage
The provenance graph must cover:
- transcription run
- project model assignment or approved model reference for the active transcription role
- redaction run
- detector lineage including privacy rules version and NER/assist lineage when they contributed
- manifest
- governance readiness reference including the manifest/ledger pair current when the approved candidate snapshot was frozen
- ledger verification lineage including the latest verification outcome that made governance artefacts downstream-consumable
- baseline policy snapshot hash or Phase 7 policy version
- export request
- export receipt (optional post-delivery evidence)
- approved candidate snapshot

### Canonical leaf and root rules
- each leaf is canonical JSON containing `artifact_kind`, stable identifier, immutable hash or version reference, and parent references only
- UTF-8
- sorted keys
- no insignificant whitespace
- leaves sorted by `(artifact_kind, stable_identifier)` before tree construction
- leaf hash = `SHA-256(canonical_leaf_bytes)`

### Required table
Implement or reconcile `provenance_proofs`:
- `id`
- `project_id`
- `export_request_id`
- `candidate_snapshot_id`
- `attempt_number`
- `supersedes_proof_id`
- `superseded_by_proof_id`
- `root_sha256`
- `signature_key_ref`
- `signature_bytes_key`
- `proof_artifact_key`
- `proof_artifact_sha256`
- `created_by`
- `created_at`

### Required APIs
- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance/proofs`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance/proof`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance/proofs/{proofId}`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/provenance/proofs/regenerate`

Endpoint semantics must stay explicit and non-overlapping:
- `/provenance` returns summary/projection metadata for the current unsuperseded proof lineage
- `/provenance/proof` returns the current unsuperseded proof artefact/detail
- `/provenance/proofs` returns append-only proof attempt history (newest-first)
- `/provenance/proofs/{proofId}` returns one specific historical or current proof attempt

### RBAC
- `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can read provenance for approved export requests in their project
- `AUDITOR` has read-only provenance access
- `RESEARCHER` inherits provenance read access only when they can already read the linked approved export request
- regenerate is `ADMIN` only

## Implementation scope

### 1. Canonical provenance graph builder
Implement or refine one canonical graph builder.

Requirements:
- assemble the required lineage nodes from canonical existing artefacts
- no mutable live convenience fields in place of pinned immutable references
- graph assembly remains deterministic and explainable
- no second graph schema outside the proof artefact

### 2. Merkle root computation
Implement the canonical leaf serialization and root construction.

Requirements:
- canonical JSON leaf builder
- canonical ordering by `(artifact_kind, stable_identifier)`
- SHA-256 leaf hashing
- deterministic Merkle root generation
- same lineage inputs produce same root across process restarts

### 3. Signing and proof artefact generation
Implement the signing path.

Requirements:
- sign root with internal signing key
- persist signature bytes in controlled storage
- persist proof artefact bytes and hash
- proof artefact contains:
  - canonical leaf set
  - root hash
  - signature
  - public-key verification material needed later for offline verification
- no mutable overwrite of previous proof artefacts

### 4. Append-only proof attempt lineage
Implement or refine proof regeneration behavior.

Requirements:
- first proof attempt generated for approved export request/candidate lineage
- regeneration appends a new proof row
- `supersedes_proof_id` / `superseded_by_proof_id` are coherent
- current unsuperseded proof read remains easy
- historical proof attempts remain readable and immutable

### 5. Provenance summary surfaces
Implement or refine the provenance route.

Requirements:
- summary page shows lineage nodes, root hash, signature status, and linked manifest/policy/model/approval references
- deep-link-safe
- calm empty/loading/error states
- no giant graph-visualization gimmick required; a structured lineage summary is enough if it is clear and exact

### 6. Audit and regression
Use the canonical audit path and add coverage.

At minimum cover:
- same lineage inputs produce same root
- changed input artefact invalidates the root
- canonical ordering and serialization stability
- proof attempts are append-only
- signed proof artefacts are retrievable independently of later bundle generation
- approved export requests trigger initial proof generation before bundle creation is allowed

### 7. Documentation
Document:
- provenance graph node set
- canonical leaf rules
- Merkle root computation
- signing and proof artefact structure
- proof regeneration and lineage behavior
- what Prompt 85 and 86 consume next

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / storage / contracts
- provenance graph builder
- Merkle root and signing pipeline
- proof artefact persistence
- append-only proof lineage
- typed provenance APIs
- tests

### Web
- provenance summary route under export request
- structured lineage and proof metadata views

### Docs
- provenance graph and signed-root doc
- proof lineage and regeneration doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- storage/signing helpers used by the repo
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small provenance-summary refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- bundle building
- bundle verification
- deposit profiles
- external signing services
- a second proof format

## Testing and validation
Before finishing:
1. Verify same lineage inputs produce same root.
2. Verify changing any input artefact invalidates the root.
3. Verify canonical leaf ordering and serialization are stable.
4. Verify proof attempts append instead of mutating prior proofs.
5. Verify proof artefacts include verification material needed later.
6. Verify provenance read RBAC and `ADMIN`-only regenerate enforcement.
7. Verify provenance summary reads the current unsuperseded proof correctly.
8. Verify `/provenance`, `/provenance/proof`, and `/provenance/proofs` remain behaviorally distinct and contract-compatible with their documented non-overlapping semantics.
9. Verify docs match the implemented graph, root, and proof behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- provenance graph assembly is real
- signed Merkle root generation is real
- proof attempts are immutable and append-only
- provenance summary routes are real
- later bundle and verification prompts have a stable cryptographic backbone
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks
