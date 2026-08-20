# Database migrations

Run from the project root after setting `DATABASE_URL`:

```powershell
python scripts/migrate.py
```

or:

```bash
./scripts/migrate.sh
```

The runner:
- takes a PostgreSQL advisory lock so two deploys cannot migrate concurrently;
- records each applied migration and SHA-256 checksum;
- refuses modified history;
- wraps each migration in a transaction.

Never edit a migration after it has been applied to a real database. Add the next
numbered SQL file instead.

## S08

`0008_operations_hardening.sql` adds delivery-attempt history, operational alerts,
Support-topic message linkage, and queue indexes. Do not edit it after production use.

## S10

`0010_product_control.sql` adds product revisions, richer media/file metadata, product relationships, the one-active-cover/file invariants, and the permanent full-price-only commission flag constraint.

The migration first normalizes any legacy duplicate active covers/files before creating the unique indexes. Do not edit the migration after production use.
