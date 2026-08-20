# ZEMEN CONTROL — Section 09 Architecture

## Purpose

Zemen Control is the human operating surface over the same PostgreSQL-backed business state used by the Telegram salesman, Mini App, workers, and ZEMEN OPS.

It does not create a second source of truth.

## Boundaries

```text
Dashboard browser
      │
      │ signed HttpOnly session
      ▼
/api/control/*
      │
      ├── ControlRepository  → read models / operational queries
      │
      ├── PaymentService     → approve / reject / flag
      │
      └── OperationsService  → delivery retry / support operations
                │
                ▼
            PostgreSQL
```

Financial logic remains in domain/application services, never in React.

## Authentication model

### Login

The operator submits:

- a private `CONTROL_OWNER_KEY`
- an authorized admin Telegram ID

The backend verifies both and returns an HMAC-SHA256 signed session token inside an HttpOnly cookie.

### Protected requests

Each request:

1. verifies the cookie signature and expiry
2. rechecks the Telegram ID against `admin_users` or the configured admin allowlist
3. rejects revoked admins immediately

The browser never needs `OPS_API_KEY` and does not retain `CONTROL_OWNER_KEY` after login.

## Deployment note

Production should use HTTPS and `CONTROL_COOKIE_SECURE=true`.

The default cookie uses `SameSite=Lax`. Prefer a same-site deployment topology, for example:

```text
control.example.com
api.example.com
```

or reverse proxy both under one origin.

## Page data

### Overview

Combines:

- revenue/sales today
- new users today
- payments waiting
- rolling 30-day revenue/sales/users
- full-price versus discount sale count
- commission owed
- support/delivery operational pressure
- funnel events
- 14-day sales/revenue/user trend
- recent paid sales and source attribution

### Payments

The UI is a client of the existing payment domain service.

It can:

- preview the submitted receipt
- approve
- flag
- reject with an enumerated/custom reason

The authenticated proof-image route retrieves the Telegram file server-side and streams it to the operator. Bot credentials never go to the browser.

### Deliveries

Shows entitlement delivery state and delegates manual retries to `OperationsService` so S08 recovery rules remain authoritative.

### Customers

Customer detail joins:

- Telegram identity
- preferred language
- onboarding role/AI level/goal/obstacle
- first acquisition source
- referral attribution
- product journey/stage
- orders
- recent events
- lifetime spend/ownership

### Products

S09 intentionally keeps this page read-only while surfacing operational product health. S10 owns the full product editing/publishing model rather than slipping partial CRUD into an operations section.

### Support

Shows support queue and full thread. Replies and resolution reuse S08 support services and durable customer delivery.

### Alerts

Shows open operational alerts. Resolving an alert creates an audit log record.

## Brand rules

Zemen Control uses:

- near black
- deep forest
- bright Zemen green
- warm ivory

Avoid generic white SaaS layouts, cyan/gold Hilawe cyber styling, excessive glow, fake terminal language, and decorative “AI” terminology.

## No Redis

S09 introduces no queue/cache infrastructure. PostgreSQL remains the durable source of truth; existing asyncio workers execute persisted jobs.
