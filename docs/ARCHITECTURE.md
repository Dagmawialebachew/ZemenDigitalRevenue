# Zemen Digital — architecture contract

## Surfaces

- Telegram bot: conversational salesman, payment-proof intake, delivery, support.
- Mini App: multilingual visual storefront, Library, Earn, Account.
- Zemen Control: products, payments, customers, marketing, analytics, finances.
- ZEMEN OPS: Telegram operations group for joins, proofs, sales, support, alerts.

## Core rules

1. PostgreSQL is the source of truth.
2. No Redis.
3. Critical asynchronous work is persisted in PostgreSQL before execution; asyncio workers use leases, retries, stale recovery, and idempotent job keys.
4. PostgreSQL LISTEN/NOTIFY may wake workers early but is never required for correctness.
5. Product data is data, not hard-coded control flow.
6. Financial operations are idempotent and auditable.
7. UI surfaces call domain services; they do not implement business rules.
8. Ad/referral `/start` tokens resolve server-side; prices/product rules are never trusted from URLs.
9. A discounted sale never earns referral commission.
10. Native Telegram UI uses current Bot API capabilities; exact Zemen visual branding lives in web surfaces.
11. Each build section must remain merge-safe with the sections before it.
