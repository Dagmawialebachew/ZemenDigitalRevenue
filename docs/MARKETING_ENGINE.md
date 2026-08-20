# Zemen Digital — Marketing Engine

Section 11 turns marketing operations into database-driven business controls. A campaign or recovery-flow change should not require editing Python or redeploying a hard-coded message sequence.

## 1. Broadcast Studio

A broadcast has four durable layers:

1. `broadcasts` stores the recipe: audience, localized content, schedule and attribution window.
2. Scheduling freezes the current reachable audience into `broadcast_recipients` with a database-side `INSERT … SELECT`, so a large audience is not first loaded into application memory.
3. PostgreSQL jobs dispatch and send each recipient independently, with retries handled by the existing worker engine.
4. Per-recipient `broadcast_click_links` record CTA clicks without placing a customer ID in the visible URL.

A scheduled broadcast is versioned. Editing a scheduled recipe makes its old dispatch job stale, clears the old audience snapshot and returns it to draft so the edited campaign must be deliberately scheduled again.

Recipient outcomes are terminally tracked as `sent`, `blocked`, `failed` or `skipped`. Zemen Control surfaces blocked/failed delivery health alongside sends, clicks, sales and revenue. The broadcast is completed only after no recipient remains queued.

### Localized delivery

The worker selects the user's stored language and falls back to whichever localized version exists. Telegram media broadcasts use a single idempotent media send, so text accompanying media is restricted to Telegram's caption-sized payload. Text-only broadcasts can use the larger text-message allowance.

### Attribution

Broadcast click attribution is intentionally separate from acquisition attribution. `tracking_links` answer where a customer originally came from; broadcast click links answer which marketing follow-up was the latest qualifying click before a paid order. The configured attribution window defaults to seven days and can be changed per broadcast.

## 2. Retargeting Automations

Automations are recipes stored in:

- `automations`
- `automation_steps`
- `automation_runs`

Any producer can append a normal row to `events`. A PostgreSQL trigger creates durable `marketing.automation.trigger` jobs for enabled automations whose trigger matches that event. The worker re-checks product scope, audience, purchase state and pending-payment state before creating a run.

Supported steps are:

- `wait`
- `send_message`
- `condition`
- `create_offer`
- `expire_offer`
- `stop`

The first dashboard recipe is an opinionated recovery-flow builder rather than a free-form programming screen. It controls the trigger, both waits, Amharic/English messages, recovery price and expiry. The backend remains generic enough for later visual recipe types.

Editing an automation increments its version and stops in-flight runs with `automation_edited`. This avoids silently mutating a customer's journey halfway through a sequence. New events use the new recipe.

## 3. Recovery Offers

Recovery is not a public second price. An offer is created only after the delayed automation reaches its offer step and eligibility is checked again.

The engine refuses to create a recovery offer when:

- the customer already owns/paid for that product;
- a payment is already in progress for that product;
- product discounts are disabled;
- the proposed recovery price is not below the regular price;
- an active offer already exists;
- an enabled rule's intent threshold is not met.

Offer creation emits `DISCOUNT_UNLOCKED`, creates an expiry job and explicitly records `commissionable: false` in event metadata. The pre-existing database constraints remain the financial source of truth: discounted orders can never generate referral commission.

A purchase event revokes any other active recovery offer for the same user/product so a stale delayed job cannot re-open a discount after payment.

## 4. Referrals and payouts

The dashboard shows partner joins, commission sales, owed/available/paid balances and payout history.

`available` means a commission has cleared its hold and is not already allocated to another payout. Creating a payout locks the selected commission rows and records them in `commission_payout_items`, preventing a second payout from selecting the same money. The selected payout destination is saved in `referral_payout_profiles` for the next manual payout.

Marking a payout paid atomically marks its included commissions paid and writes the admin audit entry.

**Locked rule:** only full-price/regular orders are commissionable. Recovery or manual-discount orders are always zero-commission.

## 5. Ad Links

Zemen Control creates short opaque source tokens such as:

```text
https://t.me/<bot>?start=src_X7K3...
```

The URL exposes only the token. Product, source, campaign, ad set, creative, angle and language hint remain server-side in `tracking_links`. Disabling a link preserves its history instead of deleting attribution data.

## 6. No Redis

Section 11 does not introduce a second queue or cache. Delayed and retryable work continues to use the PostgreSQL job engine from Section 03:

```text
Event / Dashboard action
        ↓
PostgreSQL row + job
        ↓
asyncio worker
        ↓
Telegram / state transition
        ↓
PostgreSQL outcome + audit/event
```

PostgreSQL remains the durable source of truth. `LISTEN/NOTIFY` is only a wake-up optimization.

## 7. Operational settings

```env
MARKETING_UPLOAD_MAX_MB=45
MARKETING_MAINTENANCE_INTERVAL_SECONDS=300
BROADCAST_DISPATCH_BATCH_SIZE=250
BROADCAST_SEND_MAX_ATTEMPTS=8
```

Broadcast media upload also uses the existing private Telegram storage chat configured by `TELEGRAM_STORAGE_CHAT_ID`. Tracked broadcast buttons need `PUBLIC_API_BASE_URL` set to the public HTTPS backend URL in production.

## 8. Control-room surfaces

Zemen Control now groups marketing under one main navigation item with five tabs:

- Broadcasts
- Automations
- Discounts
- Referrals
- Ad Links

This keeps the primary navigation small while allowing the marketing engine to grow behind a stable information architecture.
