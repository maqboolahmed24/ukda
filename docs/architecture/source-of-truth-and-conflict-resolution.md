# Source Of Truth And Conflict Resolution

> Status: Active repository rule
> Scope: Every future implementation prompt and code change

## Precedence Order

Use this order whenever you implement or reconcile work:

1. Current repository state at execution time, including existing code and docs.
2. The live user request and the checked prompt file under [`/prompts`](../../prompts) when the task comes from the prompt backlog.
3. [`/docs/architecture/web-first-execution-contract.md`](./web-first-execution-contract.md)
4. This document.
5. [`/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`](../../phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md) when recall-first, rescue flow, token anchors, search anchoring, conservative masking, or downstream activation semantics are in scope.
6. The phase file or phase files owned by the task, plus [`/phases/phase-00-foundation-release.md`](../../phases/phase-00-foundation-release.md) when platform-foundation boundaries are relevant.
7. [`/phases/blueprint-ukdataextraction.md`](../../phases/blueprint-ukdataextraction.md)
8. [`/phases/README.md`](../../phases/README.md)
9. [`/phases/ui-premium-dark-blueprint-obsidian-folio.md`](../../phases/ui-premium-dark-blueprint-obsidian-folio.md)
10. Official external documentation for platform mechanics only.

## How To Resolve Conflicts

- Local repository docs and phase materials win for product behavior, workflow semantics, governance, audit constraints, security boundaries, safe-output rules, and acceptance logic.
- Official external docs win only for framework mechanics, browser semantics, accessibility behavior, responsive implementation details, and platform conventions.
- If a framework convention would weaken governance or bypass a local boundary, the local boundary wins.
- If the repo already contains partial implementation, reconcile and extend it. Do not duplicate or restart unless the current state is unusable.

## When The Recall-First Patch Becomes Normative

The recall-first patch is not optional background reading. It becomes binding when work touches any of the following:

- Phase 3 layout outputs, recall checks, rescue candidates, or activation gates
- Phase 4 transcription outputs, token anchors, or rescue-path provenance
- Phase 5 privacy findings, token-linked masking, or conservative area-mask fallback
- Phase 10 search indexing, hit anchoring, or discovery deep links
- Any shared data model, route, UI, or workflow that could incorrectly mark a page complete before recall status is resolved

When it applies, the recall-first patch overrides older line-only or layout-first assumptions.

## Future Prompt Contract

Every future implementation prompt must be both independent and sequenced.

- Independent: assume zero chat memory and reread the repository plus the listed source files before changing anything.
- Sequenced: assume the repository may already contain previous work and extend that work instead of rebuilding from scratch.

Each prompt should restate, at minimum:

- objective
- source files to read
- scope
- allowed touch points
- deliverables
- validations
- acceptance criteria
- non-goals
- this conflict-resolution rule

## Repository Reading Rule

Do not rely on memory of earlier prompts. Re-open the repository, re-read the relevant docs, and then decide what to change. Unchecked backlog items in [`/prompts/README.md`](../../prompts/README.md) are not authority by themselves; the checked prompt and current repository state are.

## External Reference Rule

Use official external docs only for topics such as:

- Next.js App Router mechanics
- FastAPI structure and settings
- WCAG 2.2 and WAI-ARIA interaction semantics
- MDN media-query and user-preference features

Do not use external docs to redefine UKDE workflow, privacy posture, audit rules, export controls, or provenance behavior.
