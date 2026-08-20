# SECTION 12 — FINAL INTEGRATION & RELEASE

## MERGE

This ZIP is a merge-ready delta for the existing S01 → S11 project.

Open the ZIP, select everything, paste directly into the root of your main Zemen project folder, and replace matching files.

Then run:

```powershell
pip install -r requirements.txt
python scripts/migrate.py
python scripts/verify_release.py
```

## S12 ADDS

### Final Zemen Control surfaces

- Analytics: journey funnel, product performance, source/ad attribution, audience/cohort visibility and time-to-purchase.
- Financials: gross/full-price/discount revenue, refund-state amounts, manually recorded expenses, referral commissions and an explicitly labeled operational net-cash view.
- Reviews: paid-buyer review submission, verified-purchase derivation, moderation and featuring.
- Settings: exact allow-listed safe business settings, admin roles and audit trail.
- Sidebar grouping stays compact: Overview, Sales, Products, Customers, Marketing, Reviews, Analytics, Financials, Operations, Settings.

### Security hardening

- HttpOnly signed Control session remains the browser credential.
- Session-bound CSRF required for every unsafe `/api/control` mutation.
- Live admin authorization/revocation checks.
- Viewer role is read-only at the HTTP boundary.
- Durable login-attempt rate limiting stores a keyed fingerprint, not raw access keys or raw IP addresses.
- Safe dashboard settings are exact-key allow-listed and typed.
- Security response headers on Control surfaces.

### Release/operations

- `Dockerfile` — multi-stage Mini App + Control + Python runtime.
- `.dockerignore`.
- `docker-compose.local.yml` — local PostgreSQL helper only.
- `scripts/preflight.py` — configuration/schema release gate.
- `scripts/backup_database.py` / `scripts/restore_database.py`.
- `scripts/start-production.sh`.
- `scripts/verify_release.py`.
- `.github/workflows/ci.yml`.
- `VERSION` = `1.0.2`.
- final architecture, deployment, security, backup and QA runbooks.

## DATABASE

S12 adds:

```text
database/migrations/0012_final_integration.sql
```

It contains operational expenses, review verification/moderation metadata, login rate-limit evidence and analytics/control indexes.

Legacy reviews without a paid order are classified as imported rather than silently represented as verified buyer reviews.

## CRITICAL INVARIANTS PRESERVED

- PostgreSQL is the source of truth and durable queue; no Redis.
- Full-price eligible sale → referral commission may be created.
- Any discounted/recovery sale → zero referral commission.
- Payment approval remains atomic/idempotent.
- Customer ownership survives delivery failure.
- Product/marketing behavior is database-driven, not product-specific code.
- Source/product analytics aggregate independent datasets before joining so repeated events cannot multiply paid revenue.

## PRODUCTION

Read `docs/DEPLOYMENT.md` before launch. In production, use HTTPS, secure Control cookies, a persistent PostgreSQL service, backups and a deliberate Telegram-compliant digital-goods payment boundary.

## FINAL FULL ZIP

Alongside this S12 delta, the release includes:

```text
Zemen_Digital_Commerce_Engine_v1.0_FULL.zip
```

That ZIP is the complete S01 → S12 project already assembled. It is the clean backup/deployment/handoff artifact; you do not need to reconstruct it from the incremental ZIPs.
