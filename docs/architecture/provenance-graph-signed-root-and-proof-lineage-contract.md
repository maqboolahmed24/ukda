# Provenance Graph, Signed Root, and Proof Lineage Contract

Scope: Phase 9 iteration 9.0 provenance backbone for approved export requests.

## Canonical Node Set

Each proof artifact canonical leaf set is built from pinned lineage references:

1. `TRANSCRIPTION_RUN`
2. `PROJECT_MODEL_ASSIGNMENT` or `APPROVED_MODEL_REFERENCE` for active transcription role
3. `REDACTION_RUN`
4. `DETECTOR_LINEAGE` (detector version, NER contribution signal, assist lineage hashes)
5. `GOVERNANCE_MANIFEST`
6. `GOVERNANCE_LEDGER`
7. `LEDGER_VERIFICATION`
8. `GOVERNANCE_READINESS_REFERENCE` (pinned manifest/ledger pair + verification reference)
9. `POLICY_BASELINE_OR_VERSION` (policy snapshot hash or policy version fallback)
10. `APPROVED_CANDIDATE_SNAPSHOT`
11. `EXPORT_REQUEST`
12. Optional `EXPORT_RECEIPT` when delivery evidence already exists

The graph is assembled only from immutable references already pinned to the approved candidate and request lineage.

## Canonical Leaf Rules

Each leaf is canonical JSON with exactly:

- `artifact_kind`
- `stable_identifier`
- `immutable_reference`
- `parent_references`

Serialization contract:

- UTF-8
- sorted keys
- no insignificant whitespace
- leaves sorted by `(artifact_kind, stable_identifier)` before hashing
- leaf hash = `SHA-256(canonical_leaf_bytes)`

## Merkle Root Construction

Merkle levels are built from leaf hashes in canonical order:

- odd leaf count duplicates the final hash at each level
- parent hash = `SHA-256(left_child_bytes + right_child_bytes)`
- final root is persisted as `root_sha256`

Same lineage inputs must produce the same root across restarts.

## Signing and Verification Material

Proof roots are signed with internal key reference `PROVENANCE_SIGNING_KEY_REF` using a deterministic Lamport SHA-256 OTS signer derived from `PROVENANCE_SIGNING_SECRET`.

Each proof artifact includes:

- canonical leaf set
- leaf hashes
- Merkle root
- signature payload
- verification material (`publicKeyBase64`, `publicKeySha256`, algorithm metadata)

This allows later offline verification with only the proof artifact contents.

## Persistence and Attempt Lineage

`provenance_proofs` is append-only per export request:

- first proof attempt is generated for approved/exposed request lineage
- regeneration appends a new row with incremented `attempt_number`
- new row points `supersedes_proof_id` to replaced current row
- superseded row gets `superseded_by_proof_id` forward link
- signed bytes and proof artifact bytes are immutable object keys under controlled derived storage

## API Semantics and RBAC

Routes:

- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance/proofs`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance/proof`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance/proofs/{proofId}`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/provenance/proofs/regenerate`

Behavior:

- `/provenance` = current unsuperseded summary projection
- `/provenance/proof` = current unsuperseded proof detail + artifact
- `/provenance/proofs` = append-only history (newest-first)
- `/provenance/proofs/{proofId}` = one specific historical/current attempt

Read access:

- `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, `AUDITOR`
- `RESEARCHER` only when they already have request read access
- request must be `APPROVED` or `EXPORTED`

Regenerate:

- `ADMIN` only

## Prompt 85 and 86 Inputs

Prompt 85 bundle builders consume:

- current unsuperseded `provenance_proofs` row
- `proof_artifact_key` + `proof_artifact_sha256`
- pinned `provenance_proof_id` frozen into bundle lineage

Prompt 86 verification tooling consumes:

- proof artifact canonical leaves/root/signature/verification material
- historical proof attempts from append-only lineage for auditor replay
