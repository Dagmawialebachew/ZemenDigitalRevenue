# Zemen Digital Commerce Engine v1.0 — Final Architecture

## System boundary

Zemen is one commerce system with four operator/customer surfaces sharing one PostgreSQL source of truth:

1. **Telegram Bot — salesman**: acquisition deep links, language/profile onboarding, product conversation, payment-proof collection, delivery and support.
2. **Telegram Mini App — store**: catalog, product detail, library, referral center and buyer review submission.
3. **Zemen Control — control room**: sales, products, customers, marketing, reviews, analytics, financial operations, support/alerts and safe settings.
4. **ZEMEN OPS — live operations room**: forum-topic notifications and immediate Telegram-native actions.

PostgreSQL owns durable business state and the durable job queue. `asyncio` workers execute queued work. There is no Redis dependency.

## Core invariants

- One paid order does not become paid twice.
- One entitlement per customer/product.
- One commission per eligible order item.
- A discounted/recovery order item is never commissionable.
- Full-price referral percentage is snapshotted on the order item.
- One active recovery offer per customer/product.
- Payment proof history is retained; newer proof supersedes older proof for approval actions.
- Important admin mutations are audited.
- Product/business rules live in services/database constraints, not React or Telegram handlers.
- Customer-facing product data is database-driven; adding Product #2 does not require product-specific Python branches.

## Durable work

`jobs` is PostgreSQL-backed. Workers claim due jobs with locking, use leases/heartbeats, retry transient failures with backoff and recover stale jobs. LISTEN/NOTIFY reduces latency; polling remains the correctness fallback.

## Payments

The manual ETB proof workflow is a pluggable payment channel. Orders, payment proofs, approval, entitlement, commission and delivery remain payment-provider independent. Telegram digital-goods payment policy must be resolved for the actual production surface; do not treat the manual in-Telegram channel as automatically compliant.

## Control security

- Human login exchanges an owner access key + authorized Telegram ID for a short-lived HttpOnly signed cookie.
- Mutations require a session-bound CSRF token.
- Live admin authorization is rechecked.
- Viewer role is read-only at the HTTP boundary.
- Login attempts are rate-limited using keyed fingerprints; raw access keys and raw IPs are not stored.
- Secret settings remain environment variables and are not editable from Zemen Control.
- Dashboard-editable settings use an exact allowlist and typed validation.

## Reviews

Only paid buyers can submit customer reviews in the Mini App. The database derives `verified_purchase`. New reviews default to pending unless the explicit `reviews.auto_publish` safe setting is enabled. Legacy/unverified proof is labeled imported rather than silently presented as verified.

## Analytics and money

Analytics uses events for journey milestones and paid orders for money. Product and source aggregates are calculated independently to prevent SQL row multiplication from inflating revenue.

Financials is explicitly an **operational cash view**, not formal accounting profit. It reports paid revenue, recorded expenses, refund-state amounts and paid/owed referral commissions.

## Production topology

The supplied Docker image builds both React apps and serves them from the same FastAPI origin:

- `/store/` — Mini App
- `/control/` — Zemen Control
- `/api/...` — backend
- `/telegram/webhook` — Telegram webhook when enabled

This removes cross-origin cookie complexity in production. PostgreSQL should be a managed/persistent service with automated provider backups plus independent `pg_dump` backups.
