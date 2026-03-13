# UKDE Model Stack Foundation (Phase 0.1)

This is operational guidance for local and environment wiring. Canonical product behavior still lives in `/phases`.

## Approved Starter Roles

- `TRANSCRIPTION_PRIMARY` -> `Qwen2.5-VL-3B-Instruct`
- `ASSIST` -> `Qwen3-4B`
- `PRIVACY_NER` -> `GLiNER-small-v2.1` (or `GLiNER-medium-v2.1`)
- `PRIVACY_RULES` -> `Presidio`
- `TRANSCRIPTION_FALLBACK` -> `Kraken`
- `EMBEDDING_SEARCH` -> `Qwen3-Embedding-0.6B` (optional)

Roles are fixed integration contracts. Underlying models can be swapped without changing workflow routes when the replacement keeps the same role semantics.

## Service-Map Concept

Runtime workers and APIs resolve model roles through:

- `MODEL_CATALOG_PATH` (role -> service + model metadata)
- `MODEL_SERVICE_MAP_PATH` (service -> internal endpoint contracts)

Bootstrap files:

- [`infra/models/catalog.phase-0.1.json`](/Users/test/Code/UKDA/infra/models/catalog.phase-0.1.json)
- [`infra/models/service-map.phase-0.1.json`](/Users/test/Code/UKDA/infra/models/service-map.phase-0.1.json)

## Root And Artefact Paths

- `MODEL_DEPLOYMENT_ROOT` and `MODEL_ARTIFACT_ROOT` must be absolute paths and must be outside this repository.
- Local macOS example: `~/Library/Application Support/UKDataExtraction/models`
- Server example (`staging`/`prod`): `/srv/ukdataextraction/models`

This keeps runtime artefacts isolated from source code and supports role-specific deployment boundaries.

## Internal-Only Execution Posture

- Model endpoints are internal service addresses only.
- Public runtime pulls are not supported in this bootstrap.
- External AI API egress is not part of the supported execution path.
- Service `base_url` entries must pass the runtime outbound allowlist (`OUTBOUND_ALLOWLIST`).
- Each catalog `artifact_path` must resolve inside `MODEL_ARTIFACT_ROOT` or `MODEL_DEPLOYMENT_ROOT` and exist at startup.
- URL-style artefact pulls (`http://...`, `https://...`) are blocked by design.

## Replacement Rules

When replacing a model:

1. Keep the role name stable.
2. Update `catalog.phase-0.1.json` to point the role at the new model metadata.
3. Update `service-map.phase-0.1.json` only if endpoint topology changes.
4. Keep `MODEL_ALLOWLIST` aligned with approved active roles.
