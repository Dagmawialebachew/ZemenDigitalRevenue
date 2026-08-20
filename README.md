# Zemen Digital Commerce Engine v1.0.2

A production-oriented Telegram commerce system for Zemen Digital.

**Bot = salesman · Mini App = store · Zemen Control = control room · ZEMEN OPS = live operations · PostgreSQL = source of truth + durable queue.**

No Redis is used.

> Windows note: if another local PostgreSQL service already uses host port `5432`, map the Docker PostgreSQL port to another host port such as `55432` and use that same port in `DATABASE_URL`.

## What is included

- Product-specific Telegram deep links with server-side ad/source attribution.
- Amharic/English customer profile and personalized salesman journey.
- Database-driven product catalog, media, delivery versions, sales copy and upsells.
- Telegram Mini App: Home, Store, Library, Earn, Account and verified-buyer reviews.
- Manual proof payment state machine with ZEMEN OPS review controls (deployment-policy gated).
- Atomic/idempotent approval, entitlements, full-price-only referral commissions and delivery.
- PostgreSQL durable jobs with locking, leases, retry/backoff and stale recovery.
- Support, alerts and delivery recovery.
- Zemen Control for Sales, Products, Customers, Marketing, Reviews, Analytics, Financials, Operations and Settings.
- Broadcasts, retargeting automations, recovery offers, referral payouts and ad-link generation.
- Production security hardening, audit logs, CSRF protection and admin roles.
- Docker production build, preflight checks, backup/restore scripts and CI workflow.

## The hard commercial rule

Referral commission is possible only for eligible **full-price** order items. Any recovery/discounted order item is non-commissionable. This rule is protected in application logic and PostgreSQL constraints/triggers.

## Quick start — local Windows

1. Copy `.env.example` to `.env` and fill your private values.
2. Start PostgreSQL (use your own install or `docker compose -f docker-compose.local.yml up -d`).
3. Set `DATABASE_URL`, for example:

```env
DATABASE_URL=postgresql://zemen:zemen_local_only@localhost:5432/zemen
```

4. Create a virtual environment and install Python dependencies:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

5. Run migrations and checks:

```powershell
python scripts/migrate.py
python scripts/preflight.py
python scripts/verify_release.py
```

6. Start backend/bot:

```powershell
python main.py
```

7. Mini App development server:

```powershell
cd miniapp
npm install
npm run dev
```

8. Zemen Control development server:

```powershell
cd dashboard
npm install
npm run dev
```

Local defaults: backend `http://127.0.0.1:8000`, Mini App `http://localhost:5173`, Control `http://localhost:5174`.

## Required configuration areas

The `.env.example` file is the source template. Configure Telegram bot/webhook, Mini App session security, PostgreSQL, ZEMEN OPS topic IDs, authorized admin Telegram IDs, Control authentication, Telegram storage and the selected payment surface.

Never commit the real `.env`.

## Production

The selected zero-cost layout deploys PostgreSQL to Neon, the Mini App and
Control as separate Vercel projects, and the backend/bot/workers as one Render
web service. Same-origin Vercel API rewrites preserve Control's secure cookie.

Follow `docs/DEPLOYMENT.md` in order. Render runs migrations and production
preflight automatically before starting the application.

The $0 Vercel Hobby arrangement is for non-commercial prelaunch testing only;
Vercel's current terms require a commercial plan before this commerce product
advertises or processes real payments.

## Payment-policy boundary

Orders, proof review, entitlements, referrals and delivery are provider-independent. The manual CBE/Telebirr proof channel is intentionally feature-gated because the final digital-goods payment surface must comply with Telegram's rules. Resolve this production boundary before launch instead of assuming the desired UX is automatically policy-compliant.

## Backups

```bash
python scripts/backup_database.py --out backups
```

Restore is deliberately destructive and requires explicit confirmation:

```bash
python scripts/restore_database.py backups/FILE.dump --sha256 EXPECTED --confirm RESTORE
```

See `docs/BACKUP_RECOVERY.md`.

## Documentation map

- `docs/FINAL_ARCHITECTURE.md` — final system contract and invariants
- `docs/DEPLOYMENT.md` — production build/deploy procedure
- `docs/BACKUP_RECOVERY.md` — backup/restore runbook
- `docs/SECURITY.md` — security operating rules
- `docs/FINAL_QA.md` — release/smoke checklist
- `docs/DATABASE.md` — data model foundations
- `docs/JOBS.md` — durable PostgreSQL task engine
- `docs/BOT_SALESMAN_CORE.md` + `docs/SALESMAN_ENGINE.md` — bot/customer journey
- `docs/MINI_APP_STORE.md` — storefront
- `docs/MANUAL_PAYMENTS.md` — payment state machine
- `docs/OPERATIONS_HARDENING.md` — support/delivery/alerts
- `docs/ZEMEN_CONTROL.md` — dashboard
- `docs/PRODUCT_CONTROL.md` — catalog/editor
- `docs/MARKETING_ENGINE.md` — broadcasts/automations/referrals/ad links

## Release verification

Fast dependency-light release check:

```bash
python scripts/verify_release.py
```

With frontend dependency installation/build as well:

```bash
python scripts/verify_release.py --frontends
```

The project is intentionally layered so customer interfaces can change without moving financial/domain rules out of PostgreSQL-backed services.
