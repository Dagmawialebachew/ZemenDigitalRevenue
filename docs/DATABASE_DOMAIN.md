# Zemen Digital — Database & Domain Contract (S02)

PostgreSQL is the single source of truth for users, products, source attribution, orders,
payments, entitlements, offers, referrals, commissions, events, broadcasts, automations,
durable jobs, reviews, settings, and audit logs.

## Locked commercial rules

1. Regular-price referral commission defaults to 10% and is configurable per product.
2. A discounted order is never commissionable.
3. This is protected twice: `orders.commissionable` is constrained by `discount_amount`, and
   a database trigger refuses a commission tied to any discounted/non-commissionable order.
4. Self-referrals are invalid at both repository and database levels.
5. Product price is snapshotted onto the order. Later product-price edits never rewrite history.
6. Product ownership is represented by `entitlements`, not a user-level `has_paid` flag.
7. Customer stage, order status, payment status, offer status, delivery status, and commission
   status are separate dimensions.

## Attribution

`source_links.token` resolves hidden Telegram `/start src_<token>` links to product/campaign/
creative/platform/angle metadata. The token never carries trusted price or product configuration.

Referral links similarly resolve `/start ref_<token>` and are persisted in
`referral_attributions`.

## Manual payment proof

`payments` represents the reviewable financial attempt. `payment_proofs` stores every uploaded
proof, including future AI-verifier fields. The V1 human reviewer can approve/reject while the
schema is already ready for OCR/AI assistance later.

## Durable background work

The `jobs` table is created in S02 but workers arrive in S03. This is the no-Redis design:
PostgreSQL remembers jobs; asyncio workers execute them.
