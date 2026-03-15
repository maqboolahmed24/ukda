# Governance Artefact Readiness And Event Model

Status: Prompt 71  
Scope: Phase 6 governance artefact model, readiness projections, append-only evidence-ledger generation, verification lineage, and read-route ownership

## Route ownership

Project-scoped Phase 6 governance routes:

- `/projects/:projectId/documents/:documentId/governance`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/overview`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/manifest`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/manifest/entries`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/manifest/hash`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/ledger`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/ledger/entries`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/ledger/summary`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/ledger/verify`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/ledger/verify/status`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/ledger/verify/runs`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/ledger/verify/:verificationRunId`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/ledger/verify/:verificationRunId/status`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/ledger/verify/:verificationRunId/cancel`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/events`

Boundary contract:

- `/privacy` owns Phase 5 review and safeguarded preview decisions.
- `/governance` owns Phase 6 manifest and controlled evidence-ledger read surfaces after approval.

## Canonical tables

Implemented governance schema contracts:

- `redaction_manifests`
- `redaction_evidence_ledgers`
- `governance_readiness_projections`
- `governance_run_events`
- `ledger_verification_runs`

Scaffolded downstream candidate contract table:

- `export_candidate_snapshots`

## Artefact attempt model

Manifest and ledger attempts are append-only rows keyed by `(run_id, attempt_number)` with immutable lineage fields:

- source review snapshot pinning:
  - `source_review_snapshot_key`
  - `source_review_snapshot_sha256`
- attempt supersession:
  - `supersedes_manifest_id` / `superseded_by_manifest_id`
  - `supersedes_ledger_id` / `superseded_by_ledger_id`
- lifecycle status:
  - `QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`
- hash/key fields remain nullable until generation succeeds:
  - `manifest_key`, `manifest_sha256`
  - `ledger_key`, `ledger_sha256`

Completed rows are never rewritten in place; replacements append new attempts.

## Manifest read contract additions

- `manifest` now returns the latest screening-safe canonical payload (`manifestJson`) plus access posture:
  - `internalOnly`
  - `exportApproved`
  - `notExportApproved`
- `manifest/entries` is the filterable read surface for category/page/review-state/time windows with typed cursor pagination.
- `manifest/hash` verifies persisted `manifestSha256` against streamed canonical bytes (`streamSha256`, `hashMatches`).

## Readiness projection contract

`governance_readiness_projections` is the phase-facing projection for downstream consumers:

- `status`: `PENDING | READY | FAILED`
- `generation_status`: `IDLE | RUNNING | FAILED | CANCELED`
- ready pointers:
  - `manifest_id`
  - `ledger_id`
- verification lineage pointer:
  - `last_ledger_verification_run_id`
- last successful hashes:
  - `last_manifest_sha256`
  - `last_ledger_sha256`
- verification status:
  - `ledger_verification_status` (`PENDING | VALID | INVALID`)
  - `ledger_verified_at`
- transition metadata:
  - `ready_at`
  - `last_error_code`
  - `updated_at`

No client route infers readiness from heuristics over mutable run rows.

## Governance event stream contract

`governance_run_events` is append-only history with deterministic ordering (`created_at`, `id`):

- lifecycle and readiness transitions:
  - `RUN_CREATED`
  - `MANIFEST_*`
  - `LEDGER_*`
  - `LEDGER_VERIFY_*`
  - `REGENERATE_REQUESTED`
  - `RUN_CANCELED`
  - `READY_SET`
  - `READY_FAILED`

Read surfaces use this stream directly for timeline chronology.

Role-aware event projection:

- `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, `AUDITOR` can read events.
- Non-ledger roles receive screening-safe reason text for ledger-prefixed events.
- Raw ledger payload detail remains controlled and restricted to ledger endpoints.

## Verification lineage scaffolding

`ledger_verification_runs` preserves independent append-only verification history:

- `attempt_number` lineage per run
- supersession links:
  - `supersedes_verification_run_id`
  - `superseded_by_verification_run_id`
- execution status and optional result:
  - `status`
  - `verification_result` (`VALID | INVALID`)
  - `result_json`

This avoids collapsing verification history into one mutable flag.

Readiness projection behavior:

- queued/running/failed/canceled re-verification attempts do not erase the latest completed verification truth
- latest completed `VALID` remains authoritative until a later completed verification for the same run proves `INVALID`
- readiness stays pinned to the last valid manifest+ledger pair during replacement attempts

## RBAC

Governance read routes:

- allowed: `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, read-only `AUDITOR`
- denied: `RESEARCHER`

Controlled ledger routes (`.../ledger`, `.../ledger/status`):

- allowed: `ADMIN`, read-only `AUDITOR`
- denied: `PROJECT_LEAD`, `REVIEWER`, `RESEARCHER`

Controlled verification mutations:

- `POST .../ledger/verify` and `POST .../ledger/verify/{verificationRunId}/cancel` are `ADMIN` only.

## Audit events

Governance reads emit auditable route events:

- `GOVERNANCE_OVERVIEW_VIEWED`
- `GOVERNANCE_RUNS_VIEWED`
- `GOVERNANCE_RUN_VIEWED`
- `GOVERNANCE_EVENTS_VIEWED`
- `REDACTION_MANIFEST_VIEWED`
- `REDACTION_LEDGER_VIEWED`

## Related UI contracts

- [governance-manifest-ledger-surface-contract.md](./governance-manifest-ledger-surface-contract.md)
- [governance-surface-role-access-contract.md](./governance-surface-role-access-contract.md)
- [governance-integrity-reconciliation-and-tamper-contract.md](./governance-integrity-reconciliation-and-tamper-contract.md)
- [downstream-governance-handoff-integrity-contract.md](./downstream-governance-handoff-integrity-contract.md)
