# Non-Production Seed Pack

This folder contains deterministic synthetic seed data packs for `dev` and `staging`.

Rules:

- Seed packs here are `SYNTHETIC_ONLY`.
- Seed users use `.invalid` email domains.
- Managed seed project IDs start with `seed-nonprod-`.
- Production seeding is blocked.

Primary pack:

- `seed-pack.v1.json`

Validation:

```bash
python scripts/refresh_nonprod_seed_data.py --environment dev --strict
```

Apply to non-prod (example):

```bash
DATABASE_URL=postgresql://... \
python scripts/refresh_nonprod_seed_data.py --environment staging --apply --strict
```

Report output:

- `output/seeds/latest/nonprod-seed-refresh-report.json`
