# UKDataExtraction (UKDE)

UKDE is a secure, audit-first product for turning difficult archival scans into reviewable transcripts, conservative privacy-safe derivatives, and governed release candidates inside a controlled research environment.

The active build posture is web-first. Product behavior, governance rules, and later-phase intent still live in [`/phases`](./phases), but implementation now proceeds through a browser application, API, workers, shared packages, and infrastructure boundaries defined in this repository.

## What Is Canonical

- Product behavior and phase contracts: [`/phases`](./phases)
- Web-first execution posture: [`/docs/architecture/web-first-execution-contract.md`](./docs/architecture/web-first-execution-contract.md)
- Source-of-truth and prompt execution rules: [`/docs/architecture/source-of-truth-and-conflict-resolution.md`](./docs/architecture/source-of-truth-and-conflict-resolution.md)
- Browser experience contract: [`/docs/design/obsidian-web-experience-blueprint.md`](./docs/design/obsidian-web-experience-blueprint.md)
- Design-system token architecture: [`/docs/design/design-system-token-architecture.md`](./docs/design/design-system-token-architecture.md)
- Theming and preference behavior: [`/docs/design/theming-preference-behavior.md`](./docs/design/theming-preference-behavior.md)
- Motion/transparency/contrast behavior: [`/docs/design/motion-transparency-and-contrast-behavior.md`](./docs/design/motion-transparency-and-contrast-behavior.md)
- Auth and session boundary design: [`/docs/architecture/auth-session-boundaries.md`](./docs/architecture/auth-session-boundaries.md)
- Audit event model and integrity baseline: [`/docs/architecture/audit-logging-and-integrity.md`](./docs/architecture/audit-logging-and-integrity.md)
- Observability baseline and operations surfaces: [`/docs/architecture/observability-and-operations.md`](./docs/architecture/observability-and-operations.md)
- Secure-setting enforcement baseline: [`/docs/architecture/secure-setting-enforcement-baseline.md`](./docs/architecture/secure-setting-enforcement-baseline.md)
- Export request/release-pack/revision lineage contract: [`/docs/architecture/export-request-release-pack-and-lineage-contract.md`](./docs/architecture/export-request-release-pack-and-lineage-contract.md)
- Export review dashboard/SLA/decision workflow contract: [`/docs/architecture/export-review-dashboard-sla-and-decision-workflow-contract.md`](./docs/architecture/export-review-dashboard-sla-and-decision-workflow-contract.md)
- Export operations, retention, and resubmission handoff contract: [`/docs/architecture/export-operations-retention-and-resubmission-handoff-contract.md`](./docs/architecture/export-operations-retention-and-resubmission-handoff-contract.md)
- Export approval dual-control/rationale/immutable-history contract: [`/docs/architecture/export-approval-dual-control-rationale-and-immutable-history-contract.md`](./docs/architecture/export-approval-dual-control-rationale-and-immutable-history-contract.md)
- Export gateway no-bypass and receipt-lineage contract: [`/docs/architecture/export-gateway-no-bypass-and-receipt-lineage-contract.md`](./docs/architecture/export-gateway-no-bypass-and-receipt-lineage-contract.md)
- Export release-pack validation/audit completeness/egress hardening contract: [`/docs/architecture/export-release-pack-validation-audit-completeness-and-egress-hardening-contract.md`](./docs/architecture/export-release-pack-validation-audit-completeness-and-egress-hardening-contract.md)
- Bundle verification tooling and proof viewer contract: [`/docs/architecture/bundle-verification-tooling-and-proof-viewer-contract.md`](./docs/architecture/bundle-verification-tooling-and-proof-viewer-contract.md)
- Provenance replay and bundle validation recovery contract: [`/docs/architecture/provenance-replay-and-bundle-validation-recovery-contract.md`](./docs/architecture/provenance-replay-and-bundle-validation-recovery-contract.md)
- Export gateway Phase 0 stub historical note: [`/docs/architecture/export-gateway-stub-and-no-egress-posture.md`](./docs/architecture/export-gateway-stub-and-no-egress-posture.md)
- Telemetry privacy rules: [`/docs/architecture/telemetry-privacy-rules.md`](./docs/architecture/telemetry-privacy-rules.md)
- Jobs lifecycle and worker runtime: [`/docs/architecture/jobs-framework-and-worker-runtime.md`](./docs/architecture/jobs-framework-and-worker-runtime.md)
- Project workspaces and RBAC boundaries: [`/docs/architecture/project-workspaces-and-rbac.md`](./docs/architecture/project-workspaces-and-rbac.md)
- Authenticated shell layout and adaptive-state contract: [`/docs/architecture/shell-layout-and-adaptive-state.md`](./docs/architecture/shell-layout-and-adaptive-state.md)
- Admin/governance shell ownership contract: [`/docs/architecture/admin-governance-shell-contract.md`](./docs/architecture/admin-governance-shell-contract.md)
- Admin role-to-surface matrix: [`/docs/architecture/admin-role-surface-matrix.md`](./docs/architecture/admin-role-surface-matrix.md)
- Frontend data-layer contract: [`/docs/architecture/frontend-data-layer-contract.md`](./docs/architecture/frontend-data-layer-contract.md)
- Frontend cache and optimistic-state policy: [`/docs/architecture/frontend-cache-and-optimistic-policy.md`](./docs/architecture/frontend-cache-and-optimistic-policy.md)
- Shell accessibility and keyboard contract: [`/docs/architecture/shell-accessibility-and-keyboard-contract.md`](./docs/architecture/shell-accessibility-and-keyboard-contract.md)
- Command system and omnibox contract: [`/docs/architecture/command-system-and-omnibox-contract.md`](./docs/architecture/command-system-and-omnibox-contract.md)
- Project switcher behavior contract: [`/docs/architecture/project-switcher-behavior.md`](./docs/architecture/project-switcher-behavior.md)
- Route layout and URL-state contract: [`/docs/architecture/route-layout-and-url-state-contract.md`](./docs/architecture/route-layout-and-url-state-contract.md)
- Document route family and ingest IA contract: [`/docs/architecture/document-route-family-and-ingest-ia-contract.md`](./docs/architecture/document-route-family-and-ingest-ia-contract.md)
- Document-domain baseline model: [`/docs/architecture/document-domain-baseline-model.md`](./docs/architecture/document-domain-baseline-model.md)
- Document upload lifecycle and scanning contract: [`/docs/architecture/document-upload-lifecycle-and-scanning.md`](./docs/architecture/document-upload-lifecycle-and-scanning.md)
- Document upload validation and quota policy: [`/docs/architecture/document-upload-validation-and-quota-policy.md`](./docs/architecture/document-upload-validation-and-quota-policy.md)
- Document source-record and ingest-lineage contract: [`/docs/architecture/document-source-record-and-ingest-lineage.md`](./docs/architecture/document-source-record-and-ingest-lineage.md)
- Document viewer baseline contract: [`/docs/architecture/document-viewer-baseline-contract.md`](./docs/architecture/document-viewer-baseline-contract.md)
- Document viewer navigation and control rules: [`/docs/architecture/document-viewer-navigation-and-control-rules.md`](./docs/architecture/document-viewer-navigation-and-control-rules.md)
- Document viewer URL-state contract: [`/docs/architecture/document-viewer-url-state-contract.md`](./docs/architecture/document-viewer-url-state-contract.md)
- Document viewer context-restoration and share-link policy: [`/docs/architecture/document-viewer-context-restoration-and-share-link-policy.md`](./docs/architecture/document-viewer-context-restoration-and-share-link-policy.md)
- Document ingest-status route and processing timeline contract: [`/docs/architecture/document-ingest-status-route-and-processing-timeline-contract.md`](./docs/architecture/document-ingest-status-route-and-processing-timeline-contract.md)
- Document viewer workspace choreography and shortcuts: [`/docs/architecture/document-viewer-workspace-choreography-and-shortcuts.md`](./docs/architecture/document-viewer-workspace-choreography-and-shortcuts.md)
- Document image-delivery contract: [`/docs/architecture/document-image-delivery-contract.md`](./docs/architecture/document-image-delivery-contract.md)
- Document image cache and no-raw-download policy: [`/docs/architecture/document-image-cache-and-no-raw-download-policy.md`](./docs/architecture/document-image-cache-and-no-raw-download-policy.md)
- Preprocessing run/projection model: [`/docs/architecture/preprocessing-run-and-projection-model.md`](./docs/architecture/preprocessing-run-and-projection-model.md)
- Preprocessing artefact versioning and lineage: [`/docs/architecture/preprocessing-artefact-versioning-and-lineage.md`](./docs/architecture/preprocessing-artefact-versioning-and-lineage.md)
- Layout-analysis route family and workspace contract: [`/docs/architecture/layout-analysis-route-family-and-segmentation-workspace-contract.md`](./docs/architecture/layout-analysis-route-family-and-segmentation-workspace-contract.md)
- Layout run/projection model: [`/docs/architecture/layout-run-and-projection-model.md`](./docs/architecture/layout-run-and-projection-model.md)
- Layout recall-first, rescue, and activation contract: [`/docs/architecture/layout-recall-first-rescue-and-activation-contract.md`](./docs/architecture/layout-recall-first-rescue-and-activation-contract.md)
- Layout PAGE-XML/overlay/geometry storage contract: [`/docs/architecture/layout-pagexml-overlay-geometry-storage-contract.md`](./docs/architecture/layout-pagexml-overlay-geometry-storage-contract.md)
- Layout stable line artifacts and downstream anchor contract: [`/docs/architecture/layout-line-artifacts-and-stable-anchor-contract.md`](./docs/architecture/layout-line-artifacts-and-stable-anchor-contract.md)
- Layout segmentation worker flow (v1): [`/docs/architecture/layout-segmentation-engine-v1-worker-flow.md`](./docs/architecture/layout-segmentation-engine-v1-worker-flow.md)
- Layout metrics/warnings/state-accuracy contract: [`/docs/architecture/layout-segmentation-metrics-warnings-and-state-accuracy-contract.md`](./docs/architecture/layout-segmentation-metrics-warnings-and-state-accuracy-contract.md)
- Layout read-only workspace contract: [`/docs/architecture/layout-read-only-workspace-contract.md`](./docs/architecture/layout-read-only-workspace-contract.md)
- Layout overlay interaction and inspector sync: [`/docs/architecture/layout-overlay-interaction-and-inspector-sync.md`](./docs/architecture/layout-overlay-interaction-and-inspector-sync.md)
- Privacy regression and activation-blocker contract: [`/docs/architecture/privacy-regression-and-activation-blockers.md`](./docs/architecture/privacy-regression-and-activation-blockers.md)
- Governance artefact readiness and event model: [`/docs/architecture/governance-artefact-readiness-and-event-model.md`](./docs/architecture/governance-artefact-readiness-and-event-model.md)
- Export candidate pinned-lineage contract: [`/docs/architecture/export-candidate-snapshot-pinned-lineage-contract.md`](./docs/architecture/export-candidate-snapshot-pinned-lineage-contract.md)
- Approved-model catalog and role-map contract: [`/docs/architecture/approved-model-catalog-and-role-map-contract.md`](./docs/architecture/approved-model-catalog-and-role-map-contract.md)
- Policy model versioning and activation contract: [`/docs/architecture/policy-model-versioning-and-activation-contract.md`](./docs/architecture/policy-model-versioning-and-activation-contract.md)
- Policy compare and baseline-seeding contract: [`/docs/architecture/policy-compare-and-baseline-seeding-contract.md`](./docs/architecture/policy-compare-and-baseline-seeding-contract.md)
- Policy reruns, rollback, and activation gates contract: [`/docs/architecture/policy-reruns-rollback-and-activation-gates-contract.md`](./docs/architecture/policy-reruns-rollback-and-activation-gates-contract.md)
- Policy lineage, usage, and explainability contract: [`/docs/architecture/policy-lineage-usage-and-explainability-contract.md`](./docs/architecture/policy-lineage-usage-and-explainability-contract.md)
- Discovery index model and rebuild lifecycle contract: [`/docs/architecture/discovery-index-model-and-rebuild-lifecycle-contract.md`](./docs/architecture/discovery-index-model-and-rebuild-lifecycle-contract.md)
- Controlled full-text search and hit provenance contract: [`/docs/architecture/controlled-full-text-search-and-hit-provenance-contract.md`](./docs/architecture/controlled-full-text-search-and-hit-provenance-contract.md)
- Search UX, result cards, jump, and highlight contract: [`/docs/architecture/search-ux-result-cards-jump-and-highlight-contract.md`](./docs/architecture/search-ux-result-cards-jump-and-highlight-contract.md)
- Pseudonym registry schema and event model: [`/docs/architecture/pseudonym-registry-schema-and-event-model.md`](./docs/architecture/pseudonym-registry-schema-and-event-model.md)
- Pseudonym registry controlled-access and lineage contract: [`/docs/architecture/pseudonym-registry-controlled-access-and-lineage-contract.md`](./docs/architecture/pseudonym-registry-controlled-access-and-lineage-contract.md)
- Transcription route family and workspace contract: [`/docs/architecture/transcription-route-family-and-workspace-contract.md`](./docs/architecture/transcription-route-family-and-workspace-contract.md)
- Transcription workspace UX contract: [`/docs/architecture/transcription-workspace-ux-contract.md`](./docs/architecture/transcription-workspace-ux-contract.md)
- Transcription run/projection model: [`/docs/architecture/transcription-run-and-projection-model.md`](./docs/architecture/transcription-run-and-projection-model.md)
- Transcription diplomatic/normalised versioning contract: [`/docs/architecture/transcription-diplomatic-normalised-versioning-contract.md`](./docs/architecture/transcription-diplomatic-normalised-versioning-contract.md)
- Transcription correction/conflict/assist flow: [`/docs/architecture/transcription-correction-conflict-and-assist-flow.md`](./docs/architecture/transcription-correction-conflict-and-assist-flow.md)
- Transcription token-anchor and source-reference contract: [`/docs/architecture/transcription-token-anchor-and-source-reference-contract.md`](./docs/architecture/transcription-token-anchor-and-source-reference-contract.md)
- Transcription activation token-anchor prerequisites and downstream-use contract: [`/docs/architecture/transcription-activation-token-anchor-prerequisites-and-downstream-use.md`](./docs/architecture/transcription-activation-token-anchor-prerequisites-and-downstream-use.md)
- Transcription fallback/compare governance contract: [`/docs/architecture/transcription-fallback-and-compare-governance-contract.md`](./docs/architecture/transcription-fallback-and-compare-governance-contract.md)
- Transcription compare decision contract: [`/docs/architecture/transcription-compare-decision-contract.md`](./docs/architecture/transcription-compare-decision-contract.md)
- Transcription confidence and triage contract: [`/docs/architecture/transcription-confidence-and-triage-contract.md`](./docs/architecture/transcription-confidence-and-triage-contract.md)
- Transcription reviewer routing and hotspot ranking contract: [`/docs/architecture/transcription-reviewer-routing-and-hotspot-ranking.md`](./docs/architecture/transcription-reviewer-routing-and-hotspot-ranking.md)
- Loading/error boundary placement contract: [`/docs/architecture/loading-error-boundary-placement.md`](./docs/architecture/loading-error-boundary-placement.md)
- State feedback language and priority contract: [`/docs/architecture/state-feedback-language-and-priority.md`](./docs/architecture/state-feedback-language-and-priority.md)
- State copy guidelines: [`/docs/architecture/state-copy-guidelines.md`](./docs/architecture/state-copy-guidelines.md)
- Web primitives and interaction contract: [`/docs/architecture/web-primitives-and-interaction-contract.md`](./docs/architecture/web-primitives-and-interaction-contract.md)
- Overlay and focus-management contract: [`/docs/architecture/overlay-focus-management.md`](./docs/architecture/overlay-focus-management.md)
- Directory ownership and boundaries: [`/docs/architecture/repo-topology-and-boundaries.md`](./docs/architecture/repo-topology-and-boundaries.md)
- Future route and IA extensions: [`/docs/architecture/route-map-and-user-journeys.md`](./docs/architecture/route-map-and-user-journeys.md)
- Delivery automation and merge gates: [`/docs/delivery/ci-cd-quality-gates.md`](./docs/delivery/ci-cd-quality-gates.md)
- Internal preview posture: [`/docs/delivery/preview-environments.md`](./docs/delivery/preview-environments.md)
- Local secure development workflow: [`/docs/development/local-secure-dev.md`](./docs/development/local-secure-dev.md)
- Browser regression workflow: [`/docs/development/browser-regression-testing.md`](./docs/development/browser-regression-testing.md)
- Deployment and operations runbooks: [`/docs/runbooks/deployment-runbook.md`](./docs/runbooks/deployment-runbook.md), [`/docs/runbooks/key-rotation-runbook.md`](./docs/runbooks/key-rotation-runbook.md), [`/docs/runbooks/backup-restore-runbook.md`](./docs/runbooks/backup-restore-runbook.md)
- Privacy regression triage runbook: [`/docs/runbooks/privacy-regression-triage.md`](./docs/runbooks/privacy-regression-triage.md)
- Provenance replay drill and recovery runbook: [`/docs/runbooks/provenance-replay-drill-and-bundle-validation-recovery.md`](./docs/runbooks/provenance-replay-drill-and-bundle-validation-recovery.md)
- Model service-map foundation: [`/MODEL_STACK.md`](./MODEL_STACK.md)

## Current Topology

- [`/web`](./web): Next.js App Router frontend
- [`/api`](./api): FastAPI service skeleton
- [`/workers`](./workers): queue worker runtime for ingest, preprocessing, and layout-analysis jobs
- [`/packages/ui`](./packages/ui): shared tokens and browser primitives bootstrap
- [`/packages/contracts`](./packages/contracts): shared TypeScript contract bootstrap
- [`/infra`](./infra): infrastructure placeholders for containerization and environment separation

The governance posture is unchanged: deny by default, internal-only model execution, append-only audit/evidence intent, and a single export gateway as the only egress path.

## Read Order Before Changing Code

1. [`/phases/README.md`](./phases/README.md)
2. [`/docs/architecture/web-first-execution-contract.md`](./docs/architecture/web-first-execution-contract.md)
3. [`/docs/architecture/source-of-truth-and-conflict-resolution.md`](./docs/architecture/source-of-truth-and-conflict-resolution.md)
4. [`/phases/blueprint-ukdataextraction.md`](./phases/blueprint-ukdataextraction.md)
5. [`/docs/design/obsidian-web-experience-blueprint.md`](./docs/design/obsidian-web-experience-blueprint.md)
6. [`/docs/architecture/repo-topology-and-boundaries.md`](./docs/architecture/repo-topology-and-boundaries.md)
7. [`/docs/architecture/route-layout-and-url-state-contract.md`](./docs/architecture/route-layout-and-url-state-contract.md)
8. [`/docs/architecture/loading-error-boundary-placement.md`](./docs/architecture/loading-error-boundary-placement.md)
9. [`/docs/architecture/state-feedback-language-and-priority.md`](./docs/architecture/state-feedback-language-and-priority.md)
10. [`/docs/architecture/state-copy-guidelines.md`](./docs/architecture/state-copy-guidelines.md)
11. [`/docs/architecture/route-map-and-user-journeys.md`](./docs/architecture/route-map-and-user-journeys.md)
12. The phase file or checked prompt you are implementing
13. [`/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`](./phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md) when work touches recall-first behavior, rescue flow, token anchors, search anchoring, conservative masking, or downstream activation

## Prerequisites

- Node.js `24.10.0` or newer
- `pnpm 10.23.0` or newer
- Python `3.12+`

## Install

Install the JS workspace dependencies:

```bash
pnpm install
```

Create and activate a Python virtual environment, then install the editable Python packages:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
make install-python
```

## Run Locally

Start the frontend:

```bash
set -a && source .env && set +a
pnpm dev:web
```

Start local Postgres:

```bash
make dev-db-up
```

Start the API in a second terminal:

```bash
source .venv/bin/activate
set -a && source .env && set +a
cd api
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Inspect worker status:

```bash
source .venv/bin/activate
ukde-worker status
```

Run one worker pass:

```bash
source .venv/bin/activate
ukde-worker run-once
```

Run offline bundle verification from bundled proof material:

```bash
source .venv/bin/activate
python -m app.exports.bundle_verify_cli /path/to/deposit_bundle.zip --expected-sha256 <bundle_sha256>
```

Run deterministic provenance replay drill from pinned bundle lineage:

```bash
source .venv/bin/activate
ukde-provenance-replay <project_id> <export_request_id> <bundle_id> --profile <profile_id>
```

The entry resolver route `/` is auth-aware: unauthenticated users go to `/login`, authenticated users go to `/projects`.
The operational diagnostic route is `/health` and reads live status from the API.
The safe error route is `/error`.
Project workspace routes include `/projects/:projectId/overview`, `/projects/:projectId/documents`, `/projects/:projectId/documents/import`, `/projects/:projectId/documents/:documentId`, `/projects/:projectId/documents/:documentId/ingest-status`, `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`, `/projects/:projectId/documents/:documentId/preprocessing`, `/projects/:projectId/documents/:documentId/layout`, `/projects/:projectId/documents/:documentId/layout/runs/:runId`, `/projects/:projectId/documents/:documentId/layout/workspace?page={pageNumber}&runId={runId}`, `/projects/:projectId/search`, `/projects/:projectId/policies`, `/projects/:projectId/policies/active`, `/projects/:projectId/policies/:policyId`, `/projects/:projectId/policies/:policyId/compare?against={otherPolicyId}`, `/projects/:projectId/policies/:policyId/compare?againstBaselineSnapshotId={baselineSnapshotId}`, `/projects/:projectId/indexes`, `/projects/:projectId/indexes/search/:indexId`, `/projects/:projectId/indexes/entity/:indexId`, `/projects/:projectId/indexes/derivative/:indexId`, `/projects/:projectId/pseudonym-registry`, `/projects/:projectId/pseudonym-registry/:entryId`, `/projects/:projectId/pseudonym-registry/:entryId/events`, `/projects/:projectId/jobs`, `/projects/:projectId/jobs/:jobId`, `/projects/:projectId/activity`, and permission-scoped `/projects/:projectId/settings`.
Phase 8/9 requester and reviewer routes include `/projects/:projectId/export-candidates`, `/projects/:projectId/export-requests`, `/projects/:projectId/export-review`, receipt read surfaces under `/projects/:projectId/export-requests/:exportRequestId/{receipt|receipts}`, provenance surfaces under `/projects/:projectId/export-requests/:exportRequestId/provenance` plus `/projects/:projectId/export-requests/:exportRequestId/provenance/{proof|proofs}`, and deposit-bundle surfaces under `/projects/:projectId/export-requests/:exportRequestId/bundles` with detail/status/events/verification/validation by `bundleId` (`/verification`, `/verification/status`, `/verification-runs`, `/verification/{verificationRunId}`, `/verification/{verificationRunId}/status`, `/validation`, `/validation-status?profile=...`, `/validation-runs?profile=...`, `/validation-runs/{validationRunId}`, `/validation-runs/{validationRunId}/status`). Review-stage mutations remain optimistic-lock protected, receipt attachment remains internal gateway-only, provenance-proof regeneration is `ADMIN`-only, bundle verification start/cancel is `ADMIN`-only, bundle validation start/cancel is `ADMIN`-only, and `CONTROLLED_EVIDENCE` bundle build/read plus verification/validation reads are restricted to `ADMIN` and read-only `AUDITOR`.
Audit routes include `/admin/audit`, `/admin/audit/:eventId`, and current-user `/activity`.
Operations routes include `/admin/operations`, `/admin/operations/export-status`, `/admin/operations/slos`, `/admin/operations/alerts`, and `/admin/operations/timelines`.
Security route includes `/admin/security`.
The web app expects the API at `http://127.0.0.1:8000` by default.
Use `NEXT_PUBLIC_UKDE_API_ORIGIN` for browser-visible API URLs and `UKDE_API_ORIGIN_INTERNAL` for server-side fetches (for example `http://api:8000` in containerized smoke mode).

Containerized smoke path:

```bash
make dev-stack-up
```

## Validate

Run the local CI-equivalent quality gates:

```bash
make ci
```

Validate images and deployment manifests:

```bash
make verify-images
make render-manifests
```

Direct JS and Python commands remain available when you want narrower feedback loops.

Validate the shared packages and the web app:

```bash
pnpm typecheck:packages
pnpm typecheck:web
pnpm test:browser
pnpm test:browser --project=chromium --project=firefox-phase1 --project=webkit-phase1 --grep @phase1 --workers=1
pnpm test:browser --project=chromium --grep @preprocess --workers=1
pnpm test:browser --project=chromium --grep @privacy --workers=1
pnpm build:web
pnpm smoke:health
```

Validate the Python services:

```bash
source .venv/bin/activate
make test-preprocess-gold
make test-privacy-regression
make test-governance-integrity
make test-export-hardening
python -m pytest api/tests
python -m pytest workers/tests
```

## Auth Development Notes

- Local dev can use explicit seeded identities by setting `AUTH_DEV_MODE_ENABLED=true`.
- Dev seed identities are inserted into `users` automatically in dev mode to make member-management flows testable without a prior login for every fixture user.
- Dev auth is intentionally blocked outside `dev/test`.
- Real OIDC is enabled when `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, and `OIDC_REDIRECT_URI` are all set.
- Session cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` outside local dev.

## Delivery Assets

- GitHub workflows: [`/.github/workflows`](./.github/workflows)
- Helm deployment skeleton: [`/infra/helm/ukde`](./infra/helm/ukde)
- Local runtime stack: [`/docker-compose.yml`](./docker-compose.yml)
- Local CI entrypoint: [`/Makefile`](./Makefile)
- Python CI lock: [`/requirements/python-ci.lock`](./requirements/python-ci.lock)

## Working Rules

- Re-read the repository and relevant source files every turn. Do not rely on chat memory.
- Extend the current repository state instead of recreating parallel scaffolds.
- Keep `/phases` immutable. Translate legacy desktop wording into web-native implementation instead of editing the source canon to fit convenience.
- Use official external docs only for framework, browser, accessibility, and responsive mechanics. They do not override local product rules.
