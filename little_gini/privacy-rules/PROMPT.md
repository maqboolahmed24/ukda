You are the implementation agent for UKDE model-service bootstrap. Work directly in this repository and complete the task end-to-end.

Do not ask clarifying questions unless there is a true blocker (missing credentials, unavailable registry, conflicting repo state).

## Service
- Service key: `privacy-rules`
- Role: `PRIVACY_RULES`
- MacBook M1 starter engine target: `Presidio`
- Protocol contract: `rules-native`
- Required base URL: `http://127.0.0.1:8030`
- Required endpoint: `/health`

## Non-Negotiable Completion Rule
Image-only setup is incomplete. Pull all runtime dependencies required for real PII analysis (image + NLP model assets).

## Mandatory First Reads
1. `/Users/test/Code/UKDA/little_gini/README.md`
2. `/Users/test/Code/UKDA/MODEL_STACK.md`
3. `/Users/test/Code/UKDA/infra/models/catalog.phase-0.1.json`
4. `/Users/test/Code/UKDA/infra/models/service-map.phase-0.1.json`
5. `/Users/test/Code/UKDA/.env.example`
6. `/Users/test/Code/UKDA/little_gini/privacy-rules/README.md` (if it exists)

## Objective
Provision a fully runnable local `privacy-rules` service on MacBook M1 with complete image + analyzer dependencies pulled and validated.

## Hard Constraints
- Use `linux/arm64` image builds only.
- Pin image by digest.
- Keep runtime local-only (`127.0.0.1`).
- Preserve stable role contract (`PRIVACY_RULES`).
- Keep artifacts outside repo when persistent assets are required.
- Do not modify `/Users/test/Code/UKDA/phases`.

## Required Pull Set
### Container image
- Pull one arm64-compatible Presidio/analyzer image.
- Record exact `repo@sha256:...`.

### Runtime assets (required)
Ensure the analyzer has required NLP data available at startup (for example spaCy model files or equivalent language resources). Persist these assets and document exact location.

If custom recognizer dictionaries or regex packs are needed, place under:
- `${MODEL_ARTIFACT_ROOT}/presidio/default/`

## Implementation Tasks
1. Preflight path and disk checks.
2. Pull/pin arm64 image and verify architecture.
3. Pull/install NLP runtime assets required by chosen Presidio path.
4. Record checksums/sizes/evidence in:
   - `/Users/test/Code/UKDA/little_gini/privacy-rules/pull-evidence.md`
5. Add/update runtime files under `/Users/test/Code/UKDA/little_gini/privacy-rules`.
6. Bind to `127.0.0.1:8030` and ensure `GET /health`.
7. Keep analyzer routes internal-only; add adapter if required.
8. Validate health and one minimal detection request.

## Validation
- `curl -fsS http://127.0.0.1:8030/health`
- Execute one minimal detection/analyzer request and confirm response schema.
- Run API model-stack checks.

## Required Deliverables
- Pinned arm64 image digest.
- Runtime dependency inventory with checksums/sizes.
- Runtime files and docs.
- Validation summary and rollback steps.

## Definition of Done
- Service + required NLP assets are fully present.
- Health and analyzer smoke checks pass.
- UKDE model stack validation passes.
