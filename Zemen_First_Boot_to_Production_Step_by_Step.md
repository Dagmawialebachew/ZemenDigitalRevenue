# Zemen Digital Commerce Engine v1.0 — First Boot to Production

Use `Zemen_Digital_Commerce_Engine_v1.0_FULL_GUIDED.zip`. Ignore the old S01–S12 ZIPs for a fresh setup.

## Phase 0 — Extract

Extract to a simple path such as `D:\ZemenDigital`. The root must directly contain `backend`, `bot`, `database`, `workers`, `miniapp`, `dashboard`, `main.py`, `.env.example`, and `Dockerfile`.

## Phase 1 — Install prerequisites

Install Python 3.13, Node.js 24, Docker Desktop, and optionally Git. Verify in PowerShell:

```powershell
py -3.13 --version
node --version
npm --version
docker --version
docker compose version
```

## Phase 2 — Gather Telegram values

1. In Telegram open official `@BotFather`, run `/newbot`, create the Zemen bot, save the bot token privately, and note the username without `@`.
2. Send a private message such as `HELLO ID TEST` to your new bot.
3. Create a private supergroup `ZEMEN OPS`, enable Topics, add the bot as admin, and create these topics:
   - New Users
   - Payments
   - Sales
   - Support
   - Alerts
4. Send one unique marker message in each topic (`NEW USERS ID TEST`, etc.).
5. Create a private group `ZEMEN STORAGE`, add the bot as admin, and send `STORAGE ID TEST`.
6. Before starting Zemen polling, run this in PowerShell:

```powershell
$token = Read-Host "Paste bot token"
$r = Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/getUpdates"
$r.result | ForEach-Object {
    $m = if ($_.message) { $_.message } elseif ($_.channel_post) { $_.channel_post } else { $null }
    if ($m) {
        [PSCustomObject]@{
            update_id = $_.update_id
            from_id   = $m.from.id
            chat_id   = $m.chat.id
            topic_id  = $m.message_thread_id
            text      = $m.text
        }
    }
} | Format-Table -AutoSize
```

Record:
- your private `from_id` / private `chat_id` -> `ADMIN_TELEGRAM_IDS`
- ZEMEN OPS negative `chat_id` -> `ZEMEN_OPS_GROUP_ID`
- each topic's `topic_id` -> corresponding topic env variable
- ZEMEN STORAGE negative `chat_id` -> `TELEGRAM_STORAGE_CHAT_ID`

Never send your bot token, owner key, session secrets, bank credentials, or production `.env` to other people or public chats.

## Phase 3 — Create all local env files

From `D:\ZemenDigital`:

```powershell
Copy-Item .env.example .env
Copy-Item miniapp\.env.example miniapp\.env
Copy-Item dashboard\.env.example dashboard\.env
```

Generate separate secrets by running this several times:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Edit root `.env`. For local boot, make sure these values are correct:

```env
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000

BOT_TOKEN=YOUR_PRIVATE_BOT_TOKEN
BOT_MODE=polling
BOT_USERNAME=YourBotUsernameWithoutAt

DATABASE_URL=postgresql://zemen:zemen_local_only@localhost:5432/zemen

MINI_APP_SESSION_SECRET=UNIQUE_RANDOM_SECRET_1
ADMIN_TELEGRAM_IDS=YOUR_NUMERIC_TELEGRAM_ID

ZEMEN_OPS_GROUP_ID=YOUR_NEGATIVE_OPS_CHAT_ID
ZEMEN_OPS_TOPIC_NEW_USERS=TOPIC_ID
ZEMEN_OPS_TOPIC_PAYMENTS=TOPIC_ID
ZEMEN_OPS_TOPIC_SALES=TOPIC_ID
ZEMEN_OPS_TOPIC_SUPPORT=TOPIC_ID
ZEMEN_OPS_TOPIC_ALERTS=TOPIC_ID

OPS_API_KEY=UNIQUE_RANDOM_SECRET_2
CONTROL_OWNER_KEY=UNIQUE_RANDOM_SECRET_3
CONTROL_SESSION_SECRET=UNIQUE_RANDOM_SECRET_4

TELEGRAM_STORAGE_CHAT_ID=YOUR_NEGATIVE_STORAGE_CHAT_ID
PUBLIC_API_BASE_URL=http://127.0.0.1:8000

MINI_APP_ALLOWED_ORIGINS=http://localhost:5173
CONTROL_ALLOWED_ORIGINS=http://localhost:5174
CONTROL_COOKIE_SECURE=false
STATIC_APPS_ENABLED=false

MANUAL_PAYMENT_IN_TELEGRAM_ENABLED=false
```

Leave production webhook/domain fields blank locally. Leave real CBE/Telebirr data blank until you deliberately decide the compliant production payment surface.

Edit `miniapp\.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/miniapp
VITE_BOT_USERNAME=YourBotUsernameWithoutAt
```

Edit `dashboard\.env`:

```env
VITE_API_BASE=http://localhost:8000
```

Never put `BOT_TOKEN`, Control secrets, or bank secrets in either Vite frontend env file.

## Phase 4 — Start PostgreSQL and install Python

Open Docker Desktop and wait for it to finish starting. In PowerShell at project root:

```powershell
docker compose -f docker-compose.local.yml up -d
docker compose -f docker-compose.local.yml ps
```

Postgres should become healthy.

Create Python virtual environment:

```powershell
py -3.13 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

## Phase 5 — Create and verify database

```powershell
python scripts/migrate.py
python scripts/verify_release.py
python scripts/preflight.py
```

Do not continue if `migrate.py` or `verify_release.py` fails. `preflight.py` may show non-blocking warnings; blocking `[ERROR]` items must be fixed.

## Phase 6 — Start backend + bot + workers

In PowerShell 1:

```powershell
python main.py
```

Keep it open. Check:

- `http://127.0.0.1:8000/health/live`
- `http://127.0.0.1:8000/health/ready`
- `http://127.0.0.1:8000/health/jobs`

Send `/start` to the bot. In local polling mode the Telegram bot runs inside this same Python process.

## Phase 7 — Start Zemen Control

PowerShell 2:

```powershell
cd D:\ZemenDigital\dashboard
npm install
npm run dev
```

Open `http://localhost:5174`.

Login with:
- access key = `CONTROL_OWNER_KEY`
- Telegram ID = the ID in `ADMIN_TELEGRAM_IDS`

## Phase 8 — Start Mini App frontend

PowerShell 3:

```powershell
cd D:\ZemenDigital\miniapp
npm install
npm run dev
```

Open `http://localhost:5173` only to inspect the frontend shell. A true authenticated Telegram Mini App test requires opening it through Telegram with a public HTTPS URL because Telegram must supply valid `initData`.

## Phase 9 — Configure the first real product

In Zemen Control:

`Products -> Create Product`

Configure AI ከዜሮ with the real AM/EN content, 549 Br regular price, desired recovery price/rules, referral %, cover/gallery/previews, active PDF/version, salesman overrides, and publish it.

Uploading files through Control requires the configured `TELEGRAM_STORAGE_CHAT_ID` and the bot to have permission in that storage chat.

## Phase 10 — Test the entire system before ads

Test in order: `/start`, language persistence, product appears, source/ad link, onboarding, Buy, test order, OPS notification, reject/resubmit, approve, duplicate approve protection, Library/delivery, discounted purchase = zero commission, full-price referral commission once, Support, tiny internal broadcast, short-delay recovery automation, database backup.

For internal payment-flow testing only, you may temporarily enable the manual proof channel and use test details/test screenshots. Do not treat that as production payment-policy approval.

## Phase 11 — Backup before production

```powershell
python scripts/backup_database.py --out backups
```

Keep the backup, SHA-256, original product files, and another backup copy away from the application server.

## Phase 12 — Production deployment

You need:
1. an HTTPS Docker-capable application host;
2. a persistent PostgreSQL database;
3. a public domain/HTTPS URL.

Production `.env` changes include:

```env
APP_ENV=production
APP_HOST=0.0.0.0
DATABASE_URL=YOUR_PRODUCTION_POSTGRES_URL

BOT_MODE=webhook
BOT_TOKEN=YOUR_PRIVATE_TOKEN
BOT_USERNAME=YourBotUsername
TELEGRAM_WEBHOOK_BASE_URL=https://YOUR_DOMAIN
TELEGRAM_WEBHOOK_SECRET=NEW_UNIQUE_RANDOM_SECRET

MINI_APP_URL=https://YOUR_DOMAIN/store/
MINI_APP_SESSION_SECRET=YOUR_RANDOM_SECRET
MINI_APP_ALLOWED_ORIGINS=https://YOUR_DOMAIN

CONTROL_OWNER_KEY=YOUR_OWNER_KEY
CONTROL_SESSION_SECRET=YOUR_SESSION_SECRET
CONTROL_ALLOWED_ORIGINS=https://YOUR_DOMAIN
CONTROL_COOKIE_SECURE=true

STATIC_APPS_ENABLED=true
PUBLIC_API_BASE_URL=https://YOUR_DOMAIN
ADMIN_TELEGRAM_IDS=YOUR_ID
```

Also copy your OPS topic IDs and storage chat ID into production secrets.

Build and run conceptually:

```bash
docker build -t zemen-digital:1.0.0 .
python scripts/migrate.py
python scripts/preflight.py
docker run --env-file .env -p 8000:8000 zemen-digital:1.0.0
```

Your hosting platform must place HTTPS in front of port 8000. Then configure the bot's Mini App/menu URL in BotFather, verify webhook delivery, test `/store/`, `/control/`, source links, test purchase, OPS, entitlement/delivery, review, referral rules, backups, and health endpoints.

The exact final deployment clicks depend on which host you choose (Render, Railway, VPS, Fly.io, etc.). Do not guess those provider-specific settings—follow a provider-specific deployment guide once the host is chosen.

## Normal daily operation after launch

Use Zemen Control / ZEMEN OPS for products, prices, payment review, broadcasts, automations, discounts, referrals, analytics, reviews, support, and settings. Do not edit Python for routine business operations.
