# Zemen Digital database contract — S02

PostgreSQL is the single source of truth. Telegram, the Mini App, Zemen Control,
and workers are interfaces around this database; none may invent independent
financial or customer state.

## Design rules

- UUID primary keys for business entities; BIGINT only for append-heavy sequences/events/jobs.
- `TIMESTAMPTZ` for all timestamps.
- `NUMERIC(12,2)` for birr amounts; never floating point.
- Text + CHECK constraints for workflow states instead of PostgreSQL ENUM types, so future
  state evolution does not require brittle enum migrations.
- Products are configuration/data, not hard-coded bot branches.
- Every ad source uses an opaque `src_...` token resolved through `tracking_links`.
- Every referral uses an opaque `ref_...` code resolved through `referral_accounts`.
- First-touch attribution is preserved. Revisit touches may be recorded separately.
- A discounted order is non-commissionable at three layers: pricing domain logic,
  `order_items` constraint, and database commission trigger.
- Payment proof records are append-only evidence; rejection does not delete the old proof.
- Entitlements, not Telegram message history, determine product ownership.
- `events` is append-only analytics/audit data; business state still lives in normalized tables.
- `jobs` is created in S02 and becomes the durable asyncio work queue in S03. No Redis.

## Important entity groups

### Customer identity
`users`, `user_profiles`, `user_sources` (language lives canonically on `users`)

### Catalog
`products`, `product_translations`, `product_media`, `product_files`, `product_content_blocks`

### Attribution and referrals
`tracking_links`, `referral_accounts`, `referral_attributions`

### Commerce
`orders`, `order_items`, `payments`, `payment_proofs`, `entitlements`

### Offers
`discount_rules`, `customer_offers`

### Referral money
`commissions`, `commission_payouts`, `commission_payout_items`

### Marketing
`broadcasts`, `broadcast_recipients`, `automations`, `automation_steps`, `automation_runs`

### Operations
`events`, `jobs`, `reviews`, `support_cases`, `support_messages`, `admin_users`, `audit_logs`, `settings`

## Migration policy

Never edit an already-applied migration. Add a new numbered migration instead.
The migration runner stores SHA-256 checksums and refuses to continue if an
applied migration was changed later.
