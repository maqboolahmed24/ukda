# Pseudonym Registry Controlled Access And Lineage Contract

## Scope

Phase 7 Prompt 73 introduces controlled read surfaces for pseudonym registry inspection.

Routes:

- `GET /projects/{projectId}/pseudonym-registry`
- `GET /projects/{projectId}/pseudonym-registry/{entryId}`
- `GET /projects/{projectId}/pseudonym-registry/{entryId}/events`

Web surfaces:

- `/projects/:projectId/pseudonym-registry`
- `/projects/:projectId/pseudonym-registry/:entryId`
- `/projects/:projectId/pseudonym-registry/:entryId/events`

## HMAC Fingerprint Contract

Persisted fingerprints are keyed HMACs, not plain hashes.

Fingerprint definition:

`HMAC-SHA256(canonical_normalized_source_value, project_secret_for_salt_version_ref)`

Behavior:

- canonical normalization is applied before hashing
- plain source text is never stored in the registry
- plain SHA-256 fingerprints are never persisted for registry identity
- identical source values in the same project/salt scope resolve deterministically
- identical source values across different projects resolve differently

## RBAC Contract

Read access is limited to:

- `PROJECT_LEAD`
- `ADMIN`
- read-only `AUDITOR`

No registry read access for:

- `REVIEWER`
- `RESEARCHER`

No manual create/edit/delete endpoints in v1.

## Audit Contract

Registry reads emit canonical audit events:

- `PSEUDONYM_REGISTRY_VIEWED`
- `PSEUDONYM_REGISTRY_ENTRY_VIEWED`
- `PSEUDONYM_REGISTRY_EVENTS_VIEWED`

Denied access is audited with `ACCESS_DENIED`.

## Output Differentiation Contract

Governance output surfaces distinguish action types explicitly:

- `MASK` (masked)
- `PSEUDONYMIZE` (pseudonymized)
- `GENERALIZE` (generalized)

This keeps screening and ledger views clear without exposing raw identifiers.

## Follow-on Dependencies

- Prompt 74 consumes this registry when applying indirect-identifier transformation policy.
- Prompt 76 consumes this lineage when policy reruns compare alias reuse across revisions.
