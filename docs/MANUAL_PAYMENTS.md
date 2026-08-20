# S07 — Manual payment review architecture

## Purpose

S07 adds a durable manual-payment channel to the Zemen commerce engine without turning Telegram handlers into the source of truth.

The customer flow is:

`checkout -> order -> payment method -> receipt proof -> ZEMEN OPS review -> approve/reject -> entitlement -> delivery`

PostgreSQL owns every state. Telegram is an interface over those states.

## Payment states

- `awaiting_proof` — customer selected a payment destination but has not supplied proof.
- `pending_review` — a proof is waiting for admin review.
- `flagged` — proof is still reviewable but carries an internal risk/duplicate signal.
- `rejected` — the current proof was rejected; the same payment remains available for a replacement proof.
- `approved` — final payment state; approval is idempotent.
- `cancelled` — no further proof/approval work is accepted.

Order state is separate. A rejected proof moves the order to `needs_new_proof`; an accepted proof ends at `paid`.

## ZEMEN OPS review card

The durable worker sends the exact Telegram photo/document to the configured Payments topic and attaches:

- customer
- product
- expected amount
- payment method
- regular/recovery pricing signal
- referral attribution
- commission eligibility
- order/payment public IDs
- duplicate-receipt warning when applicable
- `APPROVE`, `REJECT`, and `FLAG` buttons

A review card is mapped in `payment_review_messages` to the exact `payment_id + proof_id + Telegram message_id`.

### Stale-proof protection

This matters more than visual polish. If a newer screenshot exists, an old review card cannot approve, reject, or flag the newer proof. The service checks the exact proof the admin was looking at before changing money state. Delayed worker jobs for superseded proofs are discarded before they can create an actionable review card.

## Rejection

Built-in reasons:

- wrong amount
- wrong receiver
- unclear screenshot
- old transaction
- duplicate receipt
- transaction not found
- other

`Other` uses Telegram ForceReply. The prompt contains the payment and exact proof context, so no in-memory FSM is required and the reply remains safe across worker/process restarts.

The customer receives the reason in their language and can submit another proof without losing the order.

## Approval transaction

A single database transaction performs the financial commit:

1. lock payment and order;
2. verify the reviewed proof is still the latest proof;
3. approve payment;
4. mark order paid;
5. accept the latest proof and supersede earlier proofs;
6. grant/update entitlement;
7. redeem the customer offer when applicable;
8. create referral commission only when the order is regular/full-price;
9. stop product marketing automation for the buyer;
10. write purchase/payment events;
11. write the admin audit record;
12. enqueue buyer confirmation, product delivery and ZEMEN OPS sale notification using the PostgreSQL transactional outbox/job table.

Double approval therefore does not create duplicate entitlements, commissions, or delivery jobs.

## Referral rule

The locked Zemen rule is enforced both in the service and PostgreSQL:

- regular/full-price order: referral commission may be created using the product's snapshotted rate;
- recovery/manual-discount order: commission is forbidden and remains `0 Br`.

Attribution can still be retained for analytics even when commission is not payable.

## Duplicate signal

Telegram `file_unique_id` is used only as an early duplicate signal. It is not treated as cryptographic payment verification. A match is surfaced to the admin and does not automatically accuse or reject the customer.

The schema already leaves `image_sha256` and `verifier_data` available for a later AI-assisted verifier.

## Delivery

Approval creates/updates `entitlements` and queues `telegram.delivery.product`.

The delivery worker:

- reads the entitlement from PostgreSQL;
- uses the active product `telegram_file_id`;
- sends the document to the buyer;
- marks the entitlement delivered;
- records `PRODUCT_DELIVERED`;
- safely deduplicates if the job runs again.

The Mini App Library reads entitlements, so ownership survives Telegram message loss or server restarts.

## Configuration

```env
MANUAL_PAYMENT_IN_TELEGRAM_ENABLED=true
EXTERNAL_MANUAL_CHECKOUT_URL=
CBE_ACCOUNT_NAME=
CBE_ACCOUNT_NUMBER=
TELEBIRR_ACCOUNT_NAME=
TELEBIRR_NUMBER=
ORDER_TTL_MINUTES=180
COMMISSION_HOLD_DAYS=3
```

Never commit real payment destinations or secrets.

## Telegram digital-goods policy boundary

The manual channel is intentionally feature-gated. Telegram's current digital-goods documentation requires Telegram Stars (`XTR`) for digital goods/services sold inside bots and Mini Apps. Zemen keeps payment channels pluggable so the same order, entitlement, referral and delivery engine can be used with a compliant checkout surface without rewriting the business core.
