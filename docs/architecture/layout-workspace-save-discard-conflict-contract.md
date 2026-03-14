# Layout Workspace Save Discard Conflict Contract

> Status: Active (Prompt 47)
> Scope: Unsaved-change guards, optimistic-lock conflict handling, and deterministic transition outcomes in layout workspace

This document defines how staged layout and reading-order changes are protected in the workspace.

## Unsaved-Change Sources

Unsaved state is raised when either condition is true:

- staged geometry operations exist in `Edit` mode
- reading-order draft mode/groups differ from their saved base state

The workspace surfaces unsaved state in toolbar status chips and guarded transition prompts.

## Guarded Transitions

When unsaved changes exist, the following transitions are guarded:

- page/run navigation inside workspace
- open triage route handoff
- mode switches (`Inspect`, `Reading order`, `Edit`)

The guard surface offers deterministic actions:

- `Save and continue`
- `Discard and continue`
- `Cancel`

No blocking modal is used; the guard is inline and calm.

## Save Outcomes

Geometry save (`PATCH .../elements`) and reading-order save (`PATCH .../reading-order`) return:

- success: drafts are reset to saved state and workspace refreshes
- conflict (`409`): drafts remain local; conflict actions are shown
- error: failure copy is shown; staged drafts remain

## Discard Outcomes

Discard behavior never mutates server state:

- geometry discard restores overlay-aligned local edit session
- reading-order discard resets to base mode/groups
- pending transition discard applies local discard first, then continues the requested transition

## Conflict Recovery Actions

Conflict surfaces provide immediate recovery controls:

- `Reload latest overlay` / `Reload latest order`
- `Discard local edits` / `Discard local draft`

This avoids silent overwrite and makes optimistic-lock resolution explicit.

## Route Leave Warning Scope

`beforeunload` warning is enabled only while unsaved changes exist.
It is not used for clean workspace state.

## Invariants For Future Work

Future additions must preserve:

- explicit save/discard controls
- no silent data loss on route/mode changes
- optimistic-lock conflict visibility with clear recovery paths
