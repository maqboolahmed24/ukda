# Model Configuration Bootstrap

Phase 0.1 bootstrap files:

- `catalog.phase-0.1.json`: model roles and assignments
- `service-map.phase-0.1.json`: internal service endpoints by role

These files are validated by API readiness checks through:

- `MODEL_CATALOG_PATH`
- `MODEL_SERVICE_MAP_PATH`
- `MODEL_ALLOWLIST`
- `OUTBOUND_ALLOWLIST`

Model artefact roots must stay outside this repository.
