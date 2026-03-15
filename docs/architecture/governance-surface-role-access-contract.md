# Governance Surface Role Access Contract

Status: Prompt 70
Scope: Role visibility and control boundaries for Phase 6 governance surfaces

## Role matrix

Project-scoped governance routes are split into screening-safe and controlled surfaces.

- `PROJECT_LEAD`
  - can read governance overview, runs, run overview, events, and manifest surfaces
  - cannot access full ledger routes (`/ledger/**`)
- `REVIEWER`
  - can read governance overview, runs, run overview, events, and manifest surfaces
  - cannot access full ledger routes (`/ledger/**`)
- `AUDITOR`
  - can read governance overview, runs, run overview, events, manifest, and full ledger routes
  - ledger controls are read-only (no verification mutation)
- `ADMIN`
  - can read all governance surfaces including full ledger routes
  - can trigger/cancel ledger verification runs
- `RESEARCHER`
  - cannot access Phase 6 governance manifest or ledger surfaces

## Navigation visibility rules

- Manifest entrypoints are shown only for roles that can read manifest surfaces.
- Evidence-ledger entrypoints are shown only for roles that can read controlled ledger surfaces.
- Direct-link attempts by disallowed roles render calm restricted messaging; controls remain hidden.

## Control visibility rules

- `Trigger re-verification` and verification-cancel controls are visible only to `ADMIN`.
- `AUDITOR` sees verification history and integrity status, plus explicit read-only labeling.
- `PROJECT_LEAD` and `REVIEWER` consume decision-history safe summaries from non-ledger governance routes, not `/ledger/**`.

## Boundary reminder

- Manifest is screening-safe governance output.
- Evidence ledger is controlled-only evidence output.
- Neither surface implies export approval or creates an egress path.
