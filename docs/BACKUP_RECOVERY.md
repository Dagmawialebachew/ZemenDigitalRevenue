# Backup & Recovery Runbook

## Backup strategy

Use two independent layers:

1. PostgreSQL provider snapshots / point-in-time recovery when your provider supports it.
2. Independent application-level `pg_dump` custom-format backups.

Create a backup:

```bash
python scripts/backup_database.py --out backups
```

The script writes a `.dump` plus JSON metadata containing SHA-256. Store backups outside the application container/filesystem.

Recommended cadence for a live paid business: provider continuous/PITR where available, plus at least daily independent dumps and an additional dump before schema releases or risky admin operations.

## Restore drill

Restore into a **separate staging database first** whenever possible:

```bash
python scripts/restore_database.py backups/zemen_YYYYMMDDTHHMMSSZ.dump \
  --sha256 EXPECTED_SHA256 \
  --confirm RESTORE
python scripts/preflight.py
```

The restore command uses `--clean --if-exists`; it is destructive to the target database. Stop application writers before restoring production.

## What is not in PostgreSQL

Telegram `file_id` references depend on the bot/storage context. Keep original product source files in a separate owner-controlled backup as well. Do not treat Telegram as the only archival copy of irreplaceable source assets.

## Incident priorities

1. Stop incorrect writes if money/entitlement integrity is at risk.
2. Preserve logs, audit rows and payment proof history.
3. Determine the first bad event/order/job, not just the visible symptom.
4. Recover data or apply a forward fix.
5. Re-run idempotent delivery/notification jobs only after state is corrected.
6. Document the cause and add a regression test/invariant.
