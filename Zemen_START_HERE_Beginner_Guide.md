# START HERE — Zemen Digital Commerce Engine v1.0

This is the one file to read before touching the project.

You do **not** need to understand every Python or React file to run Zemen. You only need to understand what each part is responsible for, what settings you must provide, and the order in which the system is started.

---

## 1. What you actually built

Zemen is one commerce system with five working parts:

```text
CUSTOMER
   |
   | Facebook / referral / direct link
   v
TELEGRAM BOT  ---------------------> ZEMEN OPS
 salesman                           live admin operations
   |
   | opens / hands off
   v
MINI APP
 store + library + referrals
   |
   v
BACKEND + POSTGRESQL <------------> ZEMEN CONTROL
 business brain + data               admin dashboard
   |
   v
WORKERS
 delayed/retryable jobs
```

The simple meaning is:

- **Telegram Bot** talks to the customer.
- **Mini App** is the customer's visual shop.
- **Backend** makes business decisions and exposes APIs.
- **PostgreSQL** remembers everything permanently.
- **Workers** perform delayed/retryable tasks without Redis.
- **ZEMEN OPS** is the private Telegram operations room.
- **Zemen Control** is your admin dashboard.

The most important rule is that the Bot, Mini App, Control dashboard and OPS group do **not** each own separate business state. PostgreSQL is the source of truth.

---

# 2. What happens when you run `python main.py`

`main.py` is the main Python entry point.

It starts FastAPI/Uvicorn. During application startup the backend then:

1. reads `.env`;
2. connects to PostgreSQL;
3. creates the Telegram bot when `BOT_TOKEN` exists;
4. starts Telegram in polling mode locally or configures webhook mode in production;
5. starts the durable PostgreSQL-backed workers;
6. schedules operations and marketing maintenance jobs;
7. exposes API routes and health endpoints;
8. in production, can serve the built Mini App and Control dashboard too.

So you do **not** separately start five Python programs. `python main.py` is the main backend/bot/worker process.

The two React frontends are separate only during local development:

```text
Mini App     -> npm run dev -> localhost:5173
Zemen Control -> npm run dev -> localhost:5174
Backend      -> python main.py -> 127.0.0.1:8000
```

In the production Docker image both React apps are built and served by the backend from the same domain.

---

# 3. Folder map — WTF each folder means

## `backend/` — the business brain

You normally do **not** manually edit this during normal business operation.

```text
backend/
├── api/           HTTP endpoints used by Mini App / Control / Telegram webhook
├── core/          configuration + logging
├── db/            PostgreSQL connection pool
├── domain/        business rules, money rules and state rules
├── middleware/    security checks around HTTP requests
├── repositories/  SQL/data-access layer
├── security/      Mini App, Control and internal API authentication
└── services/      real application actions/business use cases
```

A useful mental model:

```text
React/Bot asks for something
        ↓
API/router
        ↓
service
        ↓
domain rules
        ↓
repository
        ↓
PostgreSQL
```

Financial rules belong here/database-side — not in React buttons.

---

## `bot/` — Telegram salesman UI

This is everything the customer touches in Telegram chat.

```text
bot/
├── routers/       what happens when a user presses/sends something
├── keyboards/     Telegram inline/reply buttons
└── services/      customer-facing copy/helpers/setup
```

Examples:

- `/start`
- language selection
- onboarding
- sales conversation
- Buy flow handoff
- payment screenshot collection
- support

You should change normal sales content through **Zemen Control** where the system supports it instead of constantly editing Python.

---

## `database/` — the permanent structure of the business

```text
database/
├── migrations/
└── migrate.py
```

The migrations create and evolve the PostgreSQL schema.

There are currently migrations `0001` through `0012`.

**Important:** once a migration has been applied, do not edit that old SQL file. Future schema changes should be a new migration.

Run migrations with:

```powershell
python scripts/migrate.py
```

---

## `workers/` — background work, no Redis

This is the durable job engine.

Examples of work handled here:

- Telegram OPS notifications
- delivery
- retries
- broadcasts
- automation/retargeting actions
- maintenance jobs

The key idea is:

```text
PostgreSQL remembers the job
        ↓
asyncio worker executes it
        ↓
completed / retry / failed
```

If the Python server restarts, the job is still in PostgreSQL.

---

## `miniapp/` — customer storefront

React + TypeScript.

Main customer tabs:

```text
Home
Store
Library
Earn
Account
```

It reads products from the backend/database. It is not supposed to contain product-specific Python-like business rules.

Important files:

```text
miniapp/src/App.tsx
miniapp/src/views/
miniapp/src/api/
miniapp/src/telegram/
miniapp/src/styles.css
```

During local development:

```powershell
cd miniapp
npm install
npm run dev
```

Local URL: `http://localhost:5173`

A real Telegram Mini App needs an HTTPS URL for production.

---

## `dashboard/` — Zemen Control

React + TypeScript admin dashboard.

This is where you operate the business instead of editing source code.

Main areas include:

- Overview
- Sales / Payments / Orders / Deliveries
- Products
- Customers
- Marketing
- Reviews
- Analytics
- Financials
- Operations / Support / Alerts
- Settings

During local development:

```powershell
cd dashboard
npm install
npm run dev
```

Local URL: `http://localhost:5174`

---

## `shared/` — tiny shared Python definitions

Brand constants, general constants and deep-link helpers shared by multiple Python parts.

You will rarely touch this.

---

## `scripts/` — your toolbox

The most important folder for you as the operator.

```text
scripts/migrate.py            apply database migrations
scripts/preflight.py          check whether config/database are launch-ready
scripts/verify_release.py     verify project/release structure/tests
scripts/backup_database.py    PostgreSQL backup
scripts/restore_database.py   PostgreSQL restore
scripts/enqueue_job.py        queue a job manually for testing/admin work
scripts/start-production.sh   production container startup
scripts/dev.ps1               quick local Python start helper
```

---

## `tests/` — automatic checks

These are not customer features.

They protect things like:

- pricing rules
- payment states
- referral commission restrictions
- Mini App security
- Control security
- worker behavior
- marketing rules
- final integration contracts

You normally run them indirectly through release verification, or directly with `pytest` when developing.

---

## `docs/` — deeper manuals

Read these when you are working on that part of the system:

```text
FINAL_ARCHITECTURE.md     final system contract
DEPLOYMENT.md             production deployment
BACKUP_RECOVERY.md        backups/restores
SECURITY.md               security rules
FINAL_QA.md               launch checklist
DATABASE.md               database design
JOBS.md                   worker/job engine
BOT_SALESMAN_CORE.md      bot entry architecture
SALESMAN_ENGINE.md        personalized salesman
MINI_APP_STORE.md         storefront
MANUAL_PAYMENTS.md        manual proof workflow
OPERATIONS_HARDENING.md   support/delivery/alerts
ZEMEN_CONTROL.md          dashboard
PRODUCT_CONTROL.md        products/files/content
MARKETING_ENGINE.md       broadcasts/automation/referrals/ad links
```

---

# 4. Root files — what they mean

## `.env.example`

Template containing every environment variable the app understands.

Copy it to `.env`.

```powershell
Copy-Item .env.example .env
```

Put real secrets only in `.env`.

**Never send the real `.env` publicly and never commit it to Git.**

---

## `main.py`

Main local application entry point.

```powershell
python main.py
```

---

## `requirements.txt`

Python packages needed to run production code.

```powershell
pip install -r requirements.txt
```

## `requirements-dev.txt`

Runtime packages + development/test packages.

For your PC, use this during setup:

```powershell
pip install -r requirements-dev.txt
```

---

## `pyproject.toml`

Python project metadata and test/lint settings.

The project supports Python 3.12+, while the production Docker image uses Python 3.13. Using Python 3.13 locally keeps you closest to production.

---

## `docker-compose.local.yml`

This starts **local PostgreSQL only**.

It does not deploy the entire production application.

```powershell
docker compose -f docker-compose.local.yml up -d
```

It creates a local database available at:

```env
DATABASE_URL=postgresql://zemen:zemen_local_only@localhost:5432/zemen
```

---

## `Dockerfile`

The production application image.

It:

1. builds Mini App;
2. builds Zemen Control;
3. creates the Python runtime;
4. copies the whole project;
5. serves everything through the FastAPI application.

You normally do not edit it just to operate Zemen.

---

# 5. What you need installed on your Windows PC

Recommended setup:

1. **Python 3.13** — project supports 3.12+, Docker uses 3.13.
2. **Node.js 24** — matches the production frontend build image.
3. **Docker Desktop** — easiest way to get local PostgreSQL.
4. **Git** — optional but strongly recommended once we begin making changes.
5. Telegram Desktop/mobile.

You do not need Redis.

---

# 6. Things you need from Telegram before the full system can work

You need:

1. a Telegram bot;
2. the bot token;
3. the bot username;
4. your numeric Telegram user ID for admin authorization;
5. a private **ZEMEN OPS** supergroup with topics enabled;
6. topic IDs for:
   - New Users
   - Payments
   - Sales
   - Support
   - Alerts
7. optionally a private Telegram storage chat/channel for product/marketing uploads;
8. later, the production Mini App HTTPS URL.

Create/manage the bot through Telegram's official **@BotFather**. A new bot can be created with `/newbot`. Keep the token private.

For the Mini App, the final HTTPS URL is configured for the bot through @BotFather; the project can also configure the chat menu button through the Bot API once `MINI_APP_URL` is set.

Do **not** worry about these IDs all at once before the Python project even boots. We can configure them step by step during the first real Telegram integration test.

---

# 7. The `.env` file — the fields that matter to you

Do not try to understand all ~60 variables on day one.

## Group A — minimum local backend/bot boot

```env
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000

BOT_TOKEN=YOUR_REAL_BOT_TOKEN
BOT_MODE=polling
BOT_USERNAME=YourBotUsernameWithoutAt

DATABASE_URL=postgresql://zemen:zemen_local_only@localhost:5432/zemen
```

## Group B — security secrets

Generate independent random values. One easy local command is:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Run it separately for each secret.

```env
MINI_APP_SESSION_SECRET=...
CONTROL_OWNER_KEY=...
CONTROL_SESSION_SECRET=...
```

`CONTROL_OWNER_KEY` is basically the private master access key you type into Zemen Control together with an authorized Telegram ID.

Do not reuse the same value for every secret.

## Group C — your admin identity

```env
ADMIN_TELEGRAM_IDS=123456789
```

Multiple admins:

```env
ADMIN_TELEGRAM_IDS=123456789,987654321
```

## Group D — ZEMEN OPS

```env
ZEMEN_OPS_GROUP_ID=
ZEMEN_OPS_TOPIC_NEW_USERS=
ZEMEN_OPS_TOPIC_PAYMENTS=
ZEMEN_OPS_TOPIC_SALES=
ZEMEN_OPS_TOPIC_SUPPORT=
ZEMEN_OPS_TOPIC_ALERTS=
```

These are filled after the private group/topics are created and their IDs are known.

## Group E — private Telegram file storage

```env
TELEGRAM_STORAGE_CHAT_ID=
```

This is where Control can upload product files/media through the bot and store the resulting Telegram `file_id`.

Keep an independent backup of your original product files too; Telegram should not be your only archival copy.

## Group F — payment details

The system contains a manual CBE/Telebirr proof channel:

```env
CBE_ACCOUNT_NAME=
CBE_ACCOUNT_NUMBER=
TELEBIRR_ACCOUNT_NAME=
TELEBIRR_NUMBER=
```

But digital-goods payments inside Telegram have a platform-policy boundary. Do not put real customers through a payment surface until that production boundary has been deliberately resolved.

For a conservative production configuration while deciding the payment surface:

```env
MANUAL_PAYMENT_IN_TELEGRAM_ENABLED=false
```

The order/payment/entitlement system itself remains reusable regardless of the final payment channel.

## Group G — local Mini App / Control browser origins

Defaults already work for local development:

```env
MINI_APP_ALLOWED_ORIGINS=http://localhost:5173
CONTROL_ALLOWED_ORIGINS=http://localhost:5174
PUBLIC_API_BASE_URL=http://127.0.0.1:8000
CONTROL_COOKIE_SECURE=false
STATIC_APPS_ENABLED=false
```

## Group H — production-only values

Later:

```env
APP_ENV=production
BOT_MODE=webhook
TELEGRAM_WEBHOOK_BASE_URL=https://YOUR_DOMAIN
TELEGRAM_WEBHOOK_SECRET=...
MINI_APP_URL=https://YOUR_DOMAIN/store/
MINI_APP_ALLOWED_ORIGINS=https://YOUR_DOMAIN
CONTROL_ALLOWED_ORIGINS=https://YOUR_DOMAIN
CONTROL_COOKIE_SECURE=true
STATIC_APPS_ENABLED=true
PUBLIC_API_BASE_URL=https://YOUR_DOMAIN
```

---

# 8. FIRST LOCAL START — exact order

Do this with the **FULL ZIP**, not by rebuilding all 12 sections again.

## Step 1 — extract the project

Example:

```text
D:\ZemenDigital\
```

When you open that folder you should immediately see:

```text
backend/
bot/
database/
workers/
miniapp/
dashboard/
main.py
.env.example
Dockerfile
...
```

If you see another wrapper folder before these files, move the contents up one level.

---

## Step 2 — open PowerShell in the project root

You want the prompt to look roughly like:

```text
PS D:\ZemenDigital>
```

---

## Step 3 — create `.env`

```powershell
Copy-Item .env.example .env
```

Open `.env` in VS Code or Notepad and fill the minimum values described above.

---

## Step 4 — start local PostgreSQL

With Docker Desktop running:

```powershell
docker compose -f docker-compose.local.yml up -d
```

Then in `.env`:

```env
DATABASE_URL=postgresql://zemen:zemen_local_only@localhost:5432/zemen
```

Check it:

```powershell
docker compose -f docker-compose.local.yml ps
```

The postgres service should become healthy.

---

## Step 5 — create Python virtual environment

Recommended:

```powershell
py -3.13 -m venv .venv
```

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script activation, we can fix the execution policy for your user or activate through Command Prompt instead.

---

## Step 6 — install Python dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

---

## Step 7 — create database tables

```powershell
python scripts/migrate.py
```

This applies migrations `0001` through `0012`.

Do this before expecting the bot/dashboard to work.

---

## Step 8 — verify the release

```powershell
python scripts/verify_release.py
```

Then:

```powershell
python scripts/preflight.py
```

`preflight.py` is supposed to complain when a genuinely required value/database piece is missing. That is useful — fix the reported blocking items instead of hiding them.

---

## Step 9 — start backend + bot + workers

```powershell
python main.py
```

Keep this PowerShell window open.

Expected local backend:

```text
http://127.0.0.1:8000
```

Health endpoint:

```text
http://127.0.0.1:8000/health/live
```

With `BOT_MODE=polling`, the Telegram bot runs inside this same process.

---

## Step 10 — start Zemen Control

Open a **second PowerShell** in the project root:

```powershell
cd dashboard
npm install
npm run dev
```

Open:

```text
http://localhost:5174
```

Login uses:

```text
CONTROL_OWNER_KEY
+
your authorized ADMIN_TELEGRAM_IDS value
```

---

## Step 11 — start Mini App frontend

Open a **third PowerShell**:

```powershell
cd miniapp
npm install
npm run dev
```

Browser development URL:

```text
http://localhost:5173
```

Important distinction:

- you can inspect the frontend in a normal browser locally;
- a real production Telegram Mini App needs HTTPS and Telegram-provided `initData`.

Do not treat opening localhost in Chrome as the complete Telegram security test.

---

# 9. Your first business setup after the software boots

The database intentionally does **not** silently create a fake/preloaded AI ከዜሮ commercial product.

That is good: your real product configuration should come from Zemen Control.

Go to:

```text
Zemen Control
→ Products
→ Create Product
```

For AI ከዜሮ, configure the real values there:

- Amharic/English title and content
- 549 Br regular price
- recovery price/rules as desired
- referral percentage
- cover/gallery/previews
- delivery PDF/version
- Bot Salesman content overrides
- upsells later

Then publish it.

The system protects important publish requirements server-side.

---

# 10. How a real customer reaches the system

After the product exists, create an ad/source link from:

```text
Zemen Control
→ Marketing
→ Ad Links
```

Conceptually it produces:

```text
https://t.me/YourBot?start=src_RANDOMTOKEN
```

The random token maps server-side to:

- product
- platform
- campaign
- ad set
- creative
- angle

The customer does not need to see those details in the URL.

Then the journey is:

```text
Facebook ad
→ Telegram source link
→ Bot recognizes product/ad
→ language/onboarding
→ personalized salesman
→ product/store
→ Buy
→ order/payment channel
→ proof/review if applicable
→ entitlement
→ delivery/library
→ review/referral/post-purchase
```

---

# 11. ZEMEN OPS setup concept

Create one private Telegram supergroup called something like:

```text
ZEMEN OPS
```

Enable Topics/Forum mode, then create:

```text
👤 New Users
💳 Payments
✅ Sales
🎧 Support
⚠️ Alerts
```

Add the bot with the permissions required to send/edit messages and interact with the operational workflow.

The application routes messages using the supergroup ID plus each topic's `message_thread_id`.

Do not expose this group publicly.

---

# 12. Product storage concept

You may use a separate private Telegram channel/group as a convenient storage surface.

Example:

```text
ZEMEN STORAGE
```

Add the bot and put that chat ID into:

```env
TELEGRAM_STORAGE_CHAT_ID=...
```

When you upload a product PDF through Control, the backend can upload it to that private Telegram storage chat, remember Telegram's `file_id`, and later deliver it efficiently.

Still keep the original PDF somewhere you control outside Telegram.

---

# 13. Local test sequence — do not skip this

Do **not** jump directly from “server starts” to Facebook ads.

Test in this order:

1. `python scripts/migrate.py` succeeds.
2. `python scripts/verify_release.py` succeeds.
3. `/health/live` works.
4. Telegram bot responds to `/start`.
5. Your user appears in PostgreSQL/Control.
6. Language selection persists after restarting the server.
7. Create/publish one test product in Control.
8. Store lists the product.
9. Library is empty before purchase.
10. Create one source/ad link and enter through it.
11. Confirm source attribution in Control.
12. Walk through onboarding.
13. Click Buy and verify an order is created.
14. Test the chosen payment path with a **test** order.
15. Confirm ZEMEN OPS receives the right message/topic.
16. Test reject + resubmit.
17. Test approve once.
18. Click approve again and verify it does not duplicate entitlement/revenue/commission.
19. Confirm Library ownership/delivery.
20. Test a discounted purchase and confirm commission is zero.
21. Test one full-price eligible referral and confirm the commission is created once.
22. Test Support reply/resolve.
23. Test a broadcast to a tiny internal segment first.
24. Test a recovery automation with very short staging delays.
25. Create a backup.

Only after these pass should you think about real ad traffic.

---

# 14. What you should NOT manually edit in normal operation

After launch, you should usually **not** open Python to do these jobs:

```text
Change product price
Create Product #2
Change store description
Upload new product version
Change salesman content override
Create ad tracking link
Create broadcast
Change retargeting automation
Create recovery offer
Review payments
Moderate reviews
Handle referral payout
```

Those belong in Zemen Control or ZEMEN OPS.

Code changes are for changing **how the machine works**, not routine business operation.

---

# 15. Production deployment — the simple picture

You need two production services:

```text
1. HTTPS Docker application host
2. Persistent PostgreSQL database
```

The application host runs one Zemen Docker image.

Production structure:

```text
https://YOUR_DOMAIN/store/       Mini App
https://YOUR_DOMAIN/control/     Zemen Control
https://YOUR_DOMAIN/api/...      backend APIs
https://YOUR_DOMAIN/telegram/webhook  bot webhook
```

## Production environment changes

At minimum:

```env
APP_ENV=production
APP_HOST=0.0.0.0
DATABASE_URL=YOUR_PRODUCTION_POSTGRES_URL

BOT_MODE=webhook
BOT_TOKEN=...
BOT_USERNAME=...
TELEGRAM_WEBHOOK_BASE_URL=https://YOUR_DOMAIN
TELEGRAM_WEBHOOK_SECRET=...

MINI_APP_URL=https://YOUR_DOMAIN/store/
MINI_APP_SESSION_SECRET=...
MINI_APP_ALLOWED_ORIGINS=https://YOUR_DOMAIN

CONTROL_OWNER_KEY=...
CONTROL_SESSION_SECRET=...
CONTROL_ALLOWED_ORIGINS=https://YOUR_DOMAIN
CONTROL_COOKIE_SECURE=true

STATIC_APPS_ENABLED=true
PUBLIC_API_BASE_URL=https://YOUR_DOMAIN

ADMIN_TELEGRAM_IDS=...
```

Then fill OPS/storage/payment configuration.

## Production build

```bash
docker build -t zemen-digital:1.0.0 .
```

Run the production gate against the real environment/database:

```bash
python scripts/migrate.py
python scripts/preflight.py
```

Run container conceptually:

```bash
docker run --env-file .env -p 8000:8000 zemen-digital:1.0.0
```

Your hosting platform/reverse proxy provides HTTPS to the public domain.

The Docker startup script can run migrations/preflight automatically, but keep migrations/preflight as deliberate release gates.

---

# 16. Telegram production setup after you have the HTTPS domain

Once production is reachable at `https://YOUR_DOMAIN`:

1. set `MINI_APP_URL=https://YOUR_DOMAIN/store/`;
2. configure the bot's Main Mini App/menu through @BotFather as appropriate;
3. set the production webhook base URL and secret;
4. restart/redeploy the app;
5. verify Telegram can open the Mini App and the backend accepts validated Telegram `initData`;
6. test the bot menu button;
7. test the exact Facebook deep link from a real phone.

Do not put the bot token or backend secrets into the React/Vite frontend environment.

---

# 17. Backups — before real customers

Create a database backup:

```powershell
python scripts/backup_database.py --out backups
```

Keep:

- the database backup;
- its SHA-256;
- another copy outside the application server;
- original product source files outside Telegram storage.

Read:

```text
docs/BACKUP_RECOVERY.md
```

before attempting restore.

---

# 18. Release / update routine later

For each meaningful production update:

```text
backup database
↓
build new immutable image
↓
apply new migrations
↓
run preflight
↓
deploy
↓
smoke test
↓
watch Alerts + job health
```

Do not rewrite old applied migration files.

---

# 19. Three health URLs you should know

```text
/health/live
/health/ready
/health/jobs
```

- **live**: process exists.
- **ready**: important dependencies are ready.
- **jobs**: durable worker queue health.

---

# 20. The difference between `.env`, database data and source code

This is important.

## `.env`

Private machine/deployment configuration:

```text
bot token
DB URL
security secrets
OPS IDs
admin IDs
bank/payment endpoint configuration
```

## Database / Zemen Control

Business data that should change without deployment:

```text
products
prices
descriptions
media references
sales copy
ad links
broadcasts
automations
offers
customers
orders
reviews
commissions
settings allowed by dashboard
```

## Source code

Rules and capabilities of the system:

```text
how payment approval works
how commission is protected
how auth works
how workers retry
what API endpoints exist
how UI components behave
```

If you understand this separation, the project becomes much less scary.

---

# 21. What is already complete vs what still needs YOUR real-world configuration

## Already inside the codebase

- application architecture;
- database schema/migrations;
- Telegram salesman flows;
- Mini App source;
- Control dashboard source;
- durable job engine;
- order/payment state machine;
- product control;
- customer CRM;
- marketing engine;
- referral/commission invariants;
- support/alerts;
- analytics/financial operational views;
- security middleware;
- backup/restore tooling;
- Docker deployment structure;
- tests/docs.

## Not something a ZIP can magically know

You still must provide/configure:

- your real bot token/username;
- your Telegram admin user ID(s);
- your ZEMEN OPS group/topic IDs;
- your Telegram storage chat ID;
- your production PostgreSQL URL;
- your public HTTPS domain;
- your security secrets;
- your actual product content/files/media;
- your CBE/Telebirr/external payment configuration;
- the final Telegram-compliant digital-goods payment boundary;
- actual Meta ad URLs after tracking links are created;
- real production smoke testing.

That is not missing code. That is deployment/business configuration.

---

# 22. Is AI ከዜሮ already seeded in the database?

**No.**

The database seeds safe system defaults such as ETB, Amharic default language and 10% full-price referral commission, but it does not automatically create a commercial product row for AI ከዜሮ.

That product should be created through Zemen Control using your final copy, cover, gallery, PDF and pricing.

This is intentional because the codebase is a multi-product commerce engine, not a hardcoded one-product bot.

---

# 23. The one thing to remember

You do not need to become a senior backend engineer to operate this.

Your normal operating surfaces are:

```text
Zemen Control
ZEMEN OPS
Telegram Bot
```

You go into the source-code folders only when we are changing the **engine itself**.

For the first real setup, do not try to deploy immediately. Start with:

```text
1. local PostgreSQL
2. .env
3. migrations
4. python main.py
5. Control
6. bot /start
7. create AI ከዜሮ
8. connect OPS
9. test complete purchase internally
10. only then production deployment
```

That is the correct order.

---

# 24. Where to go next

For a technical deep dive after this orientation:

```text
README.md
→ docs/FINAL_ARCHITECTURE.md
→ docs/DEPLOYMENT.md
→ docs/FINAL_QA.md
```

For the next hands-on session, start at **Section 8 of this file: FIRST LOCAL START** and do it one command at a time. Do not skip ahead to deployment.
