# Export Release-Pack Validation, Audit Completeness, And Egress Hardening Contract

Status: Prompt 83  
Scope: deterministic request-scoped release-pack validation, append-only audit completeness checks, and no-bypass egress regression hard blockers

## Canonical validator ownership

Validation is implemented as a single canonical checker in:

- `api/app/exports/validation.py`

The checker validates frozen request release packs against pinned request and candidate lineage. It does not create a second serializer or parallel release-pack model.

## Release-pack validation rules

For each request, the validator checks:

1. Frozen release-pack bytes hash to `release_pack_sha256` via canonical JSON serialization.
2. `release_pack_key` is derived from `{requestId}` and `{releasePackSha256}`.
3. Required release-pack fields are present and typed.
4. Request-pinned lineage fields remain consistent:
   - `candidateSnapshotId`
   - `requestRevision`
   - `riskClassification`
   - `classifierReasonCodes`
   - `reviewPath`
   - `requiresSecondReview`
5. Candidate lineage remains pinned:
   - source phase/artifact/run references
   - candidate hash and candidate kind
   - policy lineage
   - governance pins
6. Model lineage is immutable-reference backed per role (checksum/version pin required).
7. Manifest integrity is pinned (`manifestIntegrity.artefactManifestSha256`) and matches candidate manifest canonical bytes.
8. Drift checks compare frozen request pack against deterministic reconstruction from pinned request + candidate lineage.

## Audit-completeness rules

The audit checker validates append-only coherence across:

- `export_request_events`
- `export_request_reviews`
- `export_request_review_events`
- `export_receipts`
- current request projection fields on `export_requests`

Checks include:

1. Submission/resubmission origin event exists and is coherent.
2. Request event transition chain is chronological and status-consistent.
3. Review-stage projections reconcile to review-event history.
4. Terminal request projections reconcile to terminal request and review events.
5. Receipt lineage is append-only, attempt-sequenced, and projection-consistent.
6. `EXPORTED` requests require coherent receipt + export event lineage.

## Validation summary route and RBAC

New route:

- `GET /projects/{projectId}/export-requests/{exportRequestId}/validation-summary`

RBAC inherits request-detail permissions because the route resolves the underlying request via the same request read guard.

The response is typed and machine-readable:

- request id/project id/status/revision
- generated timestamp
- `releasePack` report
- `auditCompleteness` report
- per-check issue list + facts

## Egress-denial hardening coverage

Regression coverage remains fail-closed for:

1. Candidate direct-download bypass routes.
2. Request/bundle download bypass routes.
3. Public receipt mutation attempts.
4. Internal receipt attach without gateway identity.
5. Storage boundary controls:
   - app writer cannot write `safeguarded/exports/*`
   - gateway writer can write `safeguarded/exports/*`
   - gateway writer cannot write controlled prefixes

Denied attempts are expected to emit safe `ACCESS_DENIED` audit entries.

## CI hard blockers and artifacts

Canonical gate command:

- `make test-export-hardening`

CI runs this gate in the Python job and uploads deterministic artifacts on failure from:

- `api/tests/.artifacts/export-hardening`

## Prompt 84-86 assumptions enabled by this gate

Prompt 84-86 may assume:

1. Frozen request release packs are validation-backed and drift-detectable.
2. Request/review/receipt append-only histories are coherence-checkable without manual reconciliation.
3. Egress bypass paths remain regression-blocked in CI before promotion.
