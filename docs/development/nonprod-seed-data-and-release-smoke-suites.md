# Non-Prod Seed Data And Release Smoke Suites

This doc defines deterministic non-production seed handling and release smoke execution.

## Synthetic Seed Pack

Canonical seed pack:

- [`/infra/seeds/nonprod/seed-pack.v1.json`](../../infra/seeds/nonprod/seed-pack.v1.json)

Rules:

- synthetic-only content
- `.invalid` email domains only
- managed seed project IDs prefixed with `seed-nonprod-`
- blocked in `prod`

Validate pack:

```bash
python scripts/refresh_nonprod_seed_data.py --environment dev --strict
```

Apply to non-production DB:

```bash
DATABASE_URL=postgresql://... \
python scripts/refresh_nonprod_seed_data.py --environment staging --apply --strict
```

Seed report:

- `output/seeds/latest/nonprod-seed-refresh-report.json`

## Release Smoke Suite

Run release smoke for a target profile:

```bash
make smoke-release PYTHON=python TARGET_ENV=staging
```

The suite executes a stable, launch-critical slice:

- auth and project access sanity
- ingest and document handling sanity
- transcription/privacy/governance sanity
- export request/review sanity
- no-bypass controls sanity
- admin operations/status sanity
- admin shell route and command surface sanity

Smoke report:

- `output/smoke/latest/release-smoke-report.json`

Logs:

- `output/smoke/latest/logs/*.log`
