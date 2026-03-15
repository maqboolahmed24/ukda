# Controlled Evidence Ledger Contract

Status: Prompt 69  
Scope: Phase 6.2-6.3 controlled-only evidence-ledger bytes, append-only generation attempts, verification lineage, and restricted retrieval APIs

## Canonical serializer

Evidence-ledger bytes are serialized through one canonical path:

- `api/app/documents/evidence_ledger.py`
  - `canonical_evidence_ledger_payload`
  - `canonical_evidence_ledger_bytes`
  - `verify_canonical_evidence_ledger_payload`

Determinism and integrity rules:

- canonical JSON bytes (`ensure_ascii`, sorted keys, compact separators)
- stable row ordering from locked approved snapshot findings
- append-only row chain with `prevHash` and `rowHash`
- stable `headHash` over the final row
- no ad hoc ledger format in route handlers

## Required row content

Each ledger row carries controlled evidence for a frozen approved decision:

- before/after text references
- detector evidence:
  - `basisPrimary`
  - `basisSecondaryJson`
- optional bounded assist references:
  - `assistExplanationKey`
  - `assistExplanationSha256`
- actor and timestamp
- optional override reason
- `prevHash` and `rowHash`

The ledger remains controlled-only; screening-safe consumers should use manifest surfaces instead.

## Generation contract

Ledger generation begins only when all are true:

- run review is `APPROVED`
- `approved_snapshot_key`, `approved_snapshot_sha256`, and `locked_at` exist
- reviewed output manifest status is `READY`

Generation behavior:

- attempts are append-only rows in `redaction_evidence_ledgers`
- each attempt pins `source_review_snapshot_key` and `source_review_snapshot_sha256`
- missing or mismatched approved snapshot bytes produce explicit failed attempts
- successful attempts persist immutable `ledger_key` and `ledger_sha256`
- replacement attempts supersede prior attempts through lineage links, not in-place mutation

## Verification lineage contract

Verification attempts are append-only rows in `ledger_verification_runs`:

- `POST .../ledger/verify` appends a new attempt
- completion records `verificationResult` and `resultJson`
- cancel is allowed only while `QUEUED` or `RUNNING`
- cancellation and failure preserve prior successful lineage

Readiness integration:

- latest completed verification truth drives `ledger_verification_status`
- queued/running/failed/canceled re-verification does not erase last known valid result
- readiness remains `READY` only with valid manifest+ledger pointers

## Restricted retrieval APIs

Controlled-only API family:

- `GET .../ledger`
- `GET .../ledger/status`
- `GET .../ledger/entries?view={list|timeline}&cursor={cursor}&limit={limit}`
- `GET .../ledger/summary`
- `POST .../ledger/verify`
- `GET .../ledger/verify/status`
- `GET .../ledger/verify/runs`
- `GET .../ledger/verify/{verificationRunId}`
- `GET .../ledger/verify/{verificationRunId}/status`
- `POST .../ledger/verify/{verificationRunId}/cancel`

Access rules:

- read: `ADMIN`, read-only `AUDITOR`
- verify/cancel mutations: `ADMIN` only
- project-member roles do not access this API family

No endpoint returns raw object-store URLs.
