# Governance Manifest And Ledger Surface Contract

Status: Prompt 70
Scope: Phase 6 governance web surfaces, drill-down navigation, and controlled evidence-ledger presentation

## Route ownership

Canonical governance web routes:

- `/projects/:projectId/documents/:documentId/governance`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/overview`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/manifest`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/ledger`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/events`

Navigation intent:

- `Runs -> Run overview -> Manifest / Evidence ledger / Events` is the canonical drill-down chain.
- The route family is single-shell and deep-link safe; no parallel governance shell exists.

## Manifest surface contract

`/governance/runs/:runId/manifest` is the screening-safe review surface.

Required behavior:

- filterable entries table backed by `GET .../manifest/entries`
- filters: `category`, `page`, `reviewState`, `from`, `to`, plus cursor/limit pagination
- row drill-down by stable manifest `entryId`
- raw JSON viewer (`manifestJson`) for allowed governance roles
- explicit badges for:
  - `Internal-only`
  - `Not export-approved`

Manifest drill-down must remain bounded:

- table view for scanning
- entry detail panel for selected row
- no unbounded debug dump as primary layout

## Ledger surface contract

`/governance/runs/:runId/ledger` is the controlled evidence surface.

Required behavior:

- entry views backed by `GET .../ledger/entries?view={list|timeline}&cursor&limit`
- list + timeline modes
- diff/impact summary backed by `GET .../ledger/summary`
- integrity + verification status from `GET .../ledger/verify/status`
- verification run history from `GET .../ledger/verify/runs`
- verification attempt drill-down via `verificationRunId`
- stable row drill-down via `rowId`
- explicit controlled-data warning language

Mutation controls:

- `ADMIN` only: trigger re-verification (`POST .../ledger/verify`)
- `ADMIN` only: cancel queued/running verification attempt (`POST .../ledger/verify/{verificationRunId}/cancel`)

## Status truth presentation

Governance surfaces render exact status truth without optimistic overrides:

- manifest artefact status
- ledger artefact status
- generation status
- readiness status
- ledger verification status

The UI must not show a synthetic "all good" state while replacement generation or verification is incomplete.

## Context preservation

Drill-down context stays in URL query state:

- manifest filters + `entryId`
- ledger `view`, `cursor`, `limit`, `rowId`, `verificationRunId`

This supports reload-safe review sessions and deterministic handoff links.
