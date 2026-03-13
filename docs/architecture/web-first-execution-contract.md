# Web-First Execution Contract

> Status: Active repository-level execution patch
> Scope: Prompt-program implementation posture for Phase 0 through Phase 11

## Purpose

This document makes the delivery model unambiguous: UKDE is being implemented as a secure web application delivered through the browser. The domain rules in [`/phases`](../../phases) stay canonical. Only the execution model changes.

## Active Execution Posture

- Product target: secure browser application backed by API and worker services inside the controlled environment.
- Active prompt-program scope: Phase 0 through Phase 11.
- Target repository topology: `/web`, `/api`, `/workers`, `/packages/ui`, `/packages/contracts`, `/infra`.
- UX target: dark-first, premium, minimal, serious, keyboard-first, deep-linkable, and bounded-scroll aware.
- Governance target: no external AI egress, append-only audit/evidence posture, and a single export gateway as the only release path.

## Preserved Invariants From `/phases`

The move to web-first delivery does not change these invariants:

1. Processing stays inside the secure environment.
2. Model output is evidence-bearing hypothesis, not silent truth.
3. Confidence, provenance, reviewer action, and policy lineage remain first-class data.
4. Later safe-output, manifest, provenance, and export phases are active execution scope, not deferred thought exercises.
5. Release remains governed by screening and approval, never by a raw download path.
6. Auditability, immutability, and deny-by-default access remain day-one requirements.

## What Stays Canonical Inside `/phases`

`/phases` remains the immutable source material for:

- product workflow semantics
- governance and security boundaries
- entity and artefact intent
- phase ownership and acceptance logic
- release and audit posture
- recall-first overrides when the recall patch applies

Implementation convenience is not a reason to rewrite phase wording. If a phase document still uses desktop-only language, translate the behavior into web-native mechanics instead of editing the phase file to fit the current stack.

## Desktop-To-Web Translation Rules

- Preserve intent, not literal desktop mechanics.
- Prefer route-addressable surfaces over app-local screen switching.
- Prefer accessible web primitives over custom desktop-like chrome.
- Preserve dense review workflows through adaptive panes and bounded regions, not giant scrolling pages.
- Preserve command hierarchy and object focus through page headers, toolbars, drawers, inspectors, and URL state.

## Desktop-To-Web Concept Translation Matrix

| Legacy or desktop phrasing    | Web-native implementation contract                                                               |
| ----------------------------- | ------------------------------------------------------------------------------------------------ |
| Desktop app root              | Browser app in `/web` backed by `/api` and `/workers`                                            |
| Window/page/frame             | Route + nested layout + bounded workspace regions                                                |
| Screen navigation             | URL-addressable navigation with deep links and restorable state                                  |
| Side panel                    | Persistent inspector in wide states, drawer in compact states                                    |
| Modal flyout behavior         | Accessible dialog, drawer, popover, or menu based on task semantics                              |
| Ribbon or command strip       | Page header primary action plus toolbar and labeled overflow                                     |
| Split desktop panes           | Adaptive work regions using `Expanded`, `Balanced`, `Compact`, and `Focus` states                |
| Full-document scroll surfaces | Single-fold shell with scroll bounded inside lists, tables, viewers, transcripts, and inspectors |
| Local-only interaction state  | URL state when the state matters for review, sharing, or restoration                             |
| Direct file output/export     | Governed export request through the single export gateway                                        |

## Implementation Consequences

- New implementation docs and code must assume browser routing, semantic HTML landmarks, and accessibility-safe focus management.
- High-density workspaces must preserve the Obsidian Folio interaction intent through web-native shell patterns, not fake desktop chrome.
- Future prompts may scaffold the target directories, but this document already makes their ownership and posture normative.

## Non-Negotiable Repository Rule

`/phases` is source material and must not be rewritten to chase implementation convenience. The patch belongs in repository docs and code, not in retrospective edits to the product canon.

## Related Documents

- [`/docs/architecture/source-of-truth-and-conflict-resolution.md`](./source-of-truth-and-conflict-resolution.md)
- [`/docs/design/obsidian-web-experience-blueprint.md`](../design/obsidian-web-experience-blueprint.md)
- [`/docs/architecture/repo-topology-and-boundaries.md`](./repo-topology-and-boundaries.md)
- [`/docs/architecture/route-map-and-user-journeys.md`](./route-map-and-user-journeys.md)
- [`/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`](../../phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md)
