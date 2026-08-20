# Zero-Cost Prelaunch Deployment Runbook

This is the deployment path selected for Zemen Digital:

- Neon Free: PostgreSQL and durable job data
- Vercel: one project for `miniapp`, one project for `dashboard`
- Render Free: FastAPI, Telegram webhook bot, and durable workers in one service
- UptimeRobot Free: HTTP liveness checks for the Render service

This arrangement preserves the existing domain rules. There is no Redis, no
second worker service, and no database on an ephemeral filesystem.

This exact $0 combination is suitable for personal, non-commercial prelaunch
testing, but it is not a compliant commercial production plan. Vercel Hobby is
restricted to personal/non-commercial use, and accepting or advertising payment
is considered commercial usage. Render also explicitly describes Free services
as non-production and can restart them. Before accepting real payments, move the
Vercel projects to a commercial plan or obtain a permitted commercial hosting
arrangement. Keep backups and watch every provider's usage limits.

## 1. Before pushing the repository

Confirm that no real secret is tracked:

```powershell
git status --short
git check-ignore -v .env miniapp/.env dashboard/.env env/pyvenv.cfg
```

The three real `.env` files and the local `env/` virtual environment must be
ignored. Only `.env.example` and the two `.env.production.example` files are
safe templates.

Push the repository to the Git provider connected to Render and Vercel.

## 2. Create Neon PostgreSQL

1. Create one Neon Free project in a region close to Render Frankfurt.
2. Keep the default production branch and database.
3. Copy the **direct (unpooled)** connection string with `sslmode=require`.
4. If Neon includes `&channel_binding=require`, remove that query parameter;
   asyncpg does not recognize it as a client connection option.
5. Store the resulting URL as `DATABASE_URL`; never place it in Git or a
   Vercel variable.

The migration runner uses a session-level PostgreSQL advisory lock, so the
direct URL is the safe migration connection. The application itself already
caps its asyncpg pool at three connections on Render.

Do not run migrations manually yet. Render runs them before the first server
start and fails the deployment if they fail.

## 3. Create the Mini App Vercel project

Import the same repository into a new Vercel project with:

- Root Directory: `miniapp`
- Framework: Vite (auto-detected)
- Build Command: `npm run build`
- Output Directory: `dist`
- Environment variable: `VITE_BOT_USERNAME=YOUR_BOT_USERNAME` (without `@`)

Do not set `VITE_API_BASE_URL` in Vercel. Its production default is
`/api/miniapp`, and `miniapp/vercel.json` proxies that same-origin path to
Render.

Deploy and record the stable production URL:

```text
https://YOUR_MINIAPP_PROJECT.vercel.app
```

## 4. Create the Control Vercel project

Import the repository again as a second Vercel project with:

- Root Directory: `dashboard`
- Framework: Vite (auto-detected)
- Build Command: `npm run build`
- Output Directory: `dist`
- No frontend secrets or API environment variable

Do not set `VITE_API_BASE`. Leaving it empty keeps `/api/control/*` same-origin,
which is required for the HttpOnly Control session cookie. Deploy and record:

```text
https://YOUR_CONTROL_PROJECT.vercel.app
```

Both Vercel configs currently proxy to:

```text
https://zemen-digital-api.onrender.com
```

If Render assigns any other hostname, update the destination in both
`vercel.json` files and redeploy both Vercel projects.

## 5. Create the Render Blueprint

In Render, create a new Blueprint from this repository. Render reads the root
`render.yaml` and creates the single Free web service.

Enter these prompted values exactly for the `sync: false` variables:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Neon direct connection URL |
| `BOT_TOKEN` | Token from BotFather |
| `BOT_USERNAME` | Username without `@` |
| `TELEGRAM_WEBHOOK_BASE_URL` | `https://zemen-digital-api.onrender.com` |
| `MINI_APP_URL` | Stable Mini App Vercel URL |
| `MINI_APP_ALLOWED_ORIGINS` | Mini App origin, without trailing slash |
| `CONTROL_ALLOWED_ORIGINS` | Control origin, without trailing slash |
| `CONTROL_OWNER_KEY` | Private random value, at least 24 characters |
| `ADMIN_TELEGRAM_IDS` | Comma-separated authorized numeric Telegram IDs |
| `ZEMEN_OPS_GROUP_ID` | Private OPS group numeric ID |
| `ZEMEN_OPS_TOPIC_NEW_USERS` | Forum topic ID |
| `ZEMEN_OPS_TOPIC_PAYMENTS` | Forum topic ID |
| `ZEMEN_OPS_TOPIC_SALES` | Forum topic ID |
| `ZEMEN_OPS_TOPIC_SUPPORT` | Forum topic ID |
| `ZEMEN_OPS_TOPIC_ALERTS` | Forum topic ID |
| `TELEGRAM_STORAGE_CHAT_ID` | Private storage channel/chat numeric ID |
| `PUBLIC_API_BASE_URL` | Render HTTPS origin |
| `TELEGRAM_WEBHOOK_SECRET` | 32+ random characters using only `A-Z a-z 0-9 _ -` |

Render generates the Mini App session secret, Control session secret, and OPS
API key. Never copy those into either Vercel project.

On first boot the container performs, in order:

1. Database migrations
2. Production preflight and migration checksum verification
3. FastAPI, Telegram webhook configuration, and worker startup

The deployment must fail rather than start against a missing or altered schema.

## 6. Verify Render and Telegram

Open these URLs after Render reports a successful deploy:

```text
https://zemen-digital-api.onrender.com/health/live
https://zemen-digital-api.onrender.com/health/ready
https://zemen-digital-api.onrender.com/health/jobs
```

Expected results:

- `/health/live`: `ok` is true
- `/health/ready`: `ok`, `bot`, `database`, and `workers` are true
- `/health/jobs`: `ok` is true and `stale` is zero

The application calls Telegram `setWebhook` during startup. Verify it without
printing the bot token into logs:

```text
https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo
```

The returned webhook URL must end with `/telegram/webhook`, and
`last_error_message` should be absent. Send `/start` to the bot and open its
Mini App menu button.

## 7. Add UptimeRobot

Create one HTTP(s) monitor:

- Friendly name: `Zemen Render API`
- URL: `https://zemen-digital-api.onrender.com/health/live`
- Interval: 5 minutes on the Free plan
- Expected status: HTTP 200

Use `/health/live`, not `/health/ready` or `/health/jobs`. The liveness route
does not query PostgreSQL, allowing Neon to scale to zero between real database
work while inbound monitoring keeps Render from reaching its 15-minute idle
threshold.

Uptime monitoring reduces normal idle spin-down; it cannot prevent platform
maintenance, deploy restarts, account suspension, exhausted quotas, or external
provider incidents.

## 8. End-to-end launch checks

Perform these with test data before accepting real money. The current Vercel
Hobby deployment must remain non-commercial:

1. Sign into Control with an authorized Telegram ID and the owner key.
2. Refresh Control and confirm the HttpOnly session survives.
3. Open the Mini App from Telegram and confirm session creation succeeds.
4. Open a product and verify media, price, and checkout behavior.
5. Use one real `src_...` link and verify attribution in Control.
6. Confirm ZEMEN OPS receives a test support or operational event.
7. Test the approved payment surface and confirm one entitlement only.
8. Confirm discounted orders create no referral commission.
9. Confirm delivery/library access and review moderation.
10. Run a database backup from a trusted machine and store its SHA-256 away
    from Render's ephemeral filesystem.

The manual CBE/Telebirr payment flow remains disabled by default. Do not enable
it inside Telegram until the chosen digital-goods payment surface is confirmed
to comply with Telegram policy.

## 9. Normal release procedure

For every later release:

1. Back up Neon.
2. Build and test both frontends.
3. Push the immutable code change.
4. Let Render migrate, preflight, and deploy.
5. Let both Vercel projects deploy.
6. Run the three health checks and a Telegram smoke test.
7. Watch Render logs, ZEMEN OPS alerts, Neon usage, and UptimeRobot.

Never edit an applied SQL migration. Add a new numbered migration instead.
