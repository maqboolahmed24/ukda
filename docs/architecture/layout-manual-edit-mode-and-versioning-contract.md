# Layout Manual Edit Mode And Versioning Contract

## Scope
Prompt 46 introduces audited manual correction for layout geometry in the existing segmentation workspace route family. It does not create a second workspace or a second version-history model.

## Workspace Ownership
- Route stays in `.../layout/workspace` and remains single-surface.
- Edit mode is explicit and defaults to off.
- Read-only inspection and edit mode share the same canvas and inspector.

## Edit Tools (v1)
- Select/pan.
- Draw region polygon.
- Edit vertices.
- Split line.
- Merge lines.
- Delete region/line.
- Assign region type.

Inspector edits also cover:
- Region `regionType`.
- Region `includeInReadingOrder`.
- Line reassignment to another region.
- Line order within a region.

## Staging, Undo/Redo, Save Model
- Edits are staged client-side as an operation list.
- Undo/redo is page-session scoped and does not auto-save.
- Save/discard are explicit.
- Save uses optimistic locking via `versionEtag`; stale writes return conflict.

API:
- `PATCH /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/elements`
- Request: `versionEtag` + operation list.
- Response: new version metadata + refreshed overlay + downstream invalidation state.

## Append-Only Layout Versioning
Every successful save:
- Appends a new immutable `layout_versions` row.
- Sets prior version `superseded_by_version_id`.
- Advances `page_layout_results.active_layout_version_id`.
- Writes version-scoped PAGE-XML/overlay artifacts.
- Regenerates edited-page line crops/context/thumbnail artifacts only for that page version.

No historical PAGE-XML or overlay row is overwritten in place.

## Optimistic Concurrency Contract
- Caller must submit current `versionEtag`.
- If a newer version exists, save is rejected with conflict (`409`).
- UI keeps staged edits and shows actionable conflict messaging.

## Audit Coverage
- `LAYOUT_EDIT_APPLIED` on successful edit save.
- `LAYOUT_DOWNSTREAM_INVALIDATED` when active-run edit invalidates transcription basis.

## Follow-On Hardening
Prompt 47 owns additional workspace-hardening polish (density, ergonomics, keyboard refinements). Prompt 46 establishes the core audited correction and versioning contract.
