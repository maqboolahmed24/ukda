# Backup And Restore Runbook

## Scope

Baseline database backup/restore flow plus Phase 11.2 recovery drill execution evidence.

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

## Controlled Storage And Model Restore

After DB restore, restore controlled object storage snapshot and model artifacts into the clean environment.

Required model role restore order:

1. `PRIVACY_RULES`
2. `TRANSCRIPTION_FALLBACK`
3. `TRANSCRIPTION_PRIMARY`
4. `ASSIST`
5. `PRIVACY_NER`
6. `EMBEDDING_SEARCH`

Model restore must use approved local artifacts and internal service endpoints only. Do not fetch model artifacts from public networks during recovery.

## Recovery Drill Execution

Use admin recovery routes to execute and verify drills:

- `GET /admin/recovery/status`
- `POST /admin/recovery/drills`
- `GET /admin/recovery/drills/{drillId}/status`
- `GET /admin/recovery/drills/{drillId}/evidence`

Drill evidence is persisted to:

- `controlled/derived/recovery/drills/{scope}/{drillId}/evidence.json`

and referenced from `recovery_drills.evidence_storage_key` and `recovery_drills.evidence_storage_sha256`.

If a drill must be halted while `QUEUED` or `RUNNING`, use:

- `POST /admin/recovery/drills/{drillId}/cancel`

## Recovery Validation

- create and read one test project
- call one export candidate/request route and confirm authenticated read works
- confirm audit list is readable by admin/auditor
- confirm `/admin/security/status` returns valid payload
- confirm `/admin/recovery/status` and `/admin/recovery/drills` are `ADMIN`-only
- confirm operations timelines redact recovery evidence for `AUDITOR` to drill/status/timestamps/summary only
