# Pseudonym Registry Schema And Event Model

## Scope

Phase 7 Prompt 73 defines the canonical pseudonym registry as a controlled-only, project-scoped alias system.

This contract covers:

- `pseudonym_registry_entries`
- `pseudonym_registry_entry_events`
- deterministic tuple reuse behavior
- append-only event chronology

## Canonical Table: `pseudonym_registry_entries`

Required fields:

- `id`
- `project_id`
- `source_run_id`
- `source_fingerprint_hmac_sha256`
- `alias_value`
- `policy_id`
- `salt_version_ref`
- `alias_strategy_version`
- `created_by`
- `created_at`
- `last_used_run_id`
- `updated_at`
- `status` (`ACTIVE | RETIRED`)
- `retired_at`
- `retired_by`
- `supersedes_entry_id`
- `superseded_by_entry_id`

Registry constraints:

- one active row per `(project_id, source_fingerprint_hmac_sha256, policy_id, salt_version_ref, alias_strategy_version)` tuple
- active alias uniqueness inside `(project_id, salt_version_ref, alias_strategy_version)` scope
- append-only lineage links via `supersedes_entry_id`/`superseded_by_entry_id`

## Canonical Table: `pseudonym_registry_entry_events`

Required fields:

- `id`
- `entry_id`
- `event_type` (`ENTRY_CREATED | ENTRY_REUSED | ENTRY_RETIRED`)
- `run_id`
- `actor_user_id`
- `created_at`

Rules:

- event history is append-only
- reuse does not mutate identity; it appends `ENTRY_REUSED`
- timeline views read from events instead of inferring from mutable status fields

## Deterministic Reuse Contract

When the same scope tuple repeats:

- the system reuses the existing active entry
- `last_used_run_id` and `updated_at` are refreshed
- one `ENTRY_REUSED` event is appended

No duplicate active row is inserted for the same tuple.

## Lineage Contract For Salt/Strategy Changes

When `salt_version_ref` or `alias_strategy_version` changes for the same fingerprint + policy:

- a new entry is created
- the new row links `supersedes_entry_id` to the prior lineage row
- prior lineage row records `superseded_by_entry_id`

This prevents silent alias rebinding across incompatible lineage generations.

## Follow-on Use

- Prompt 74 uses this registry foundation to apply category-specific generalisation safely.
- Prompt 76 uses this lineage for rerun comparisons and rollback-safe policy activation gates.
