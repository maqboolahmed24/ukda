# Backup And Restore Runbook

## Scope

Baseline database backup/restore flow for Phase 0.5 operations readiness.

## Backup Procedure (Postgres)

Create snapshot dump:

```bash
pg_dump --format=custom --no-owner --no-privileges \
  --dbname="$DATABASE_URL" \
  --file="ukde-backup-$(date +%Y%m%d-%H%M%S).dump"
```

Store backup in internal-only storage.

After successful backup, update deployment env var `SECURITY_LAST_BACKUP_AT` to the snapshot timestamp so `/admin/security/status` reflects current backup posture.

## Restore Procedure

1. Provision empty recovery database.
2. Restore dump:

```bash
pg_restore --clean --if-exists --no-owner --no-privileges \
  --dbname="$RECOVERY_DATABASE_URL" \
  ukde-backup-<timestamp>.dump
```

3. Point API to recovery DB and run health/readiness checks:

```bash
curl -sS http://127.0.0.1:8000/healthz
curl -sS -o /tmp/readyz.json -w "%{http_code}\n" http://127.0.0.1:8000/readyz
```

4. Verify required Phase 0 tables:

```sql
SELECT COUNT(*) FROM baseline_policy_snapshots;
SELECT COUNT(*) FROM audit_events;
SELECT COUNT(*) FROM export_stub_events;
```

## Recovery Validation

- create and read one test project
- call one export candidate/request route and confirm authenticated read works
- confirm audit list is readable by admin/auditor
- confirm `/admin/security/status` returns valid payload
