# S04 — Telegram Salesman Core

## Purpose

S04 turns the Telegram surface from a placeholder bot into a persistent customer-entry layer.
It does **not** yet contain the final four-question persuasion/onboarding matrix; that is S05.

## Entry rules

- `/start src_<opaque token>` resolves the token against `tracking_links`.
- The URL never supplies a trusted product price, product ID, commission, or discount.
- A resolved source link can focus the conversation on the product attached to that link.
- `/start ref_<code>` creates first-touch referral attribution when valid.
- Self-referrals are ignored.
- Existing referral attribution is not overwritten by a later referral link.
- Organic/unknown starts are still logged, but do not become trusted campaign attribution.

## Persistent conversation state

`conversation_sessions` stores the current product, tracking link, referral attribution,
active flow, step, and last start payload. We intentionally disable aiogram's in-memory FSM
for customer-critical state. A process restart cannot erase the customer's position.

## New-user operations notification

The first persisted user join schedules a durable S03 job:

`telegram.ops.notify -> ZEMEN OPS / New Users`

The job key is `ops:new_user:<user_uuid>`, so repeated `/start` calls cannot create duplicate
"new user" operations alerts.

## Telegram-native UI

The bot uses Bot API 10.2 / aiogram 3.30 native button styles:

- success = positive/green
- primary = primary/blue
- danger reserved for destructive/admin actions
- neutral = Telegram application default

Telegram decides the exact theme shade. Arbitrary Zemen hex colors remain the job of the Mini App.

When `MINI_APP_URL` is configured, the Telegram chat menu button is set to **Zemen Store**.
Rich Messages remain optional presentation enhancement with ordinary-message fallback.
