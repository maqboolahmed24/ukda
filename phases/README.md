# Phase Roadmap Conventions

## Active Program Scope
- Product target: secure web application delivered through the browser.
- Development posture: web-focused, macOS-friendly, laptop/desktop-first, responsive down to tablet where practical.
- Root topology to build toward:
  - `/web`
  - `/api`
  - `/workers`
  - `/packages/ui`
  - `/packages/contracts`
  - `/infra`
- Active execution window: Phase 0 through Phase 11.
- Phase 6 through Phase 11 are ACTIVE for the prompt program and are not deferred for planning.

## Canonical Phase Titles
- Phase 0: Origins
- Phase 1: The Originals
- Phase 2: The Restoration Cut
- Phase 3: The Shape of the Page
- Phase 4: Voices from Ink
- Phase 5: The Masking
- Phase 6: The Ledger of Record
- Phase 7: The Law of Names
- Phase 8: The Only Exit
- Phase 9: Proof of Origin
- Phase 10: The Discovery Engine
- Phase 11: The Last Gate

## Source-Of-Truth Hierarchy
1. Current repository state at execution time.
2. [WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md](./WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md)
3. [UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md](./UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md) when recall-first, rescue, token anchors, search anchoring, or conservative masking are relevant.
4. The specific phase file(s) owned by the prompt.
5. [blueprint-ukdataextraction.md](./blueprint-ukdataextraction.md)
6. [README.md](./README.md)
7. [ui-premium-dark-blueprint-obsidian-folio.md](./ui-premium-dark-blueprint-obsidian-folio.md)
8. Official external documentation for platform mechanics only.

## Conflict Resolution
- Local phase contracts win for product behavior, workflow ownership, governance, audit, security boundaries, data semantics, and acceptance logic.
- Official external docs win for browser/platform mechanics, accessibility semantics, responsive behavior, routing conventions, and framework usage.
- Desktop-only or WinUI-only references in older docs must be translated into equivalent web patterns rather than copied literally.

## Canonical Experience Layer
- Product-wide UI/UX contract: [ui-premium-dark-blueprint-obsidian-folio.md](./ui-premium-dark-blueprint-obsidian-folio.md)
- Applies to all phases (0-11) as visual and interaction intent.
- Dark-first, adaptive layout, strong focus visibility, and premium minimalism remain the default interaction baseline.

## Normative System Patches
- Web-first execution contract: [WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md](./WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md)
- Recall-first transcription safety override: [UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md](./UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md)
- The web-first execution patch is normative for prompt planning and implementation posture.
- The recall-first patch is normative for Phase 3, Phase 4, Phase 5, and Phase 10 when older text conflicts with recall-first behavior.

## Prompt Contract
- Every implementation prompt must be independent and sequenced.
- Independent means zero assumed chat memory; the coding agent must reread the repo and listed source files each time.
- Sequenced means the coding agent should extend the current repo state rather than rebuild from scratch.
- Every prompt should restate objective, source references, scope, allowed touch points, deliverables, tests, acceptance criteria, non-goals, and the conflict-resolution rule.
