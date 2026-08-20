# Section 06 — Mini App Store

## Boundary

- **Mini App:** visual store, product pages, library, referral center, account/language.
- **Bot:** salesman, onboarding, payment proof, delivery, support and retargeting.
- **PostgreSQL:** source of truth for products, offers, ownership, referrals and behavior.

## Authentication

The browser sends Telegram's raw `initData` to `/api/miniapp/session`. The backend verifies the documented HMAC-SHA-256 signature with the bot token and checks `auth_date`. It then returns a short-lived Zemen HMAC session token. The bot token never reaches the browser.

## Product rendering

The UI never hardcodes `AI ከዜሮ`. Active products, translations, pricing, active customer offers, cover URLs, reviews and ownership come from PostgreSQL. Missing media gets a branded Zemen fallback, not a broken image.

## Pricing

An active `customer_offers` row changes only that customer's displayed price. Referral attribution remains visible in analytics, but discounted order items are not commissionable; this is already enforced by the database/domain rules from S02.

## Telegram-native UX

Product pages can expose Telegram's native bottom MainButton as an additional purchase action. The app uses Telegram BackButton, haptics, popups, Telegram-link handoff and safe-area variables. These are progressive enhancements; core product/store content remains normal React UI.

## S07 handoff

`POST /api/miniapp/products/{slug}/action` with `action=buy` records the product focus and `BUY_CLICKED` signal before the customer is returned to bot chat. S07 replaces the current handoff boundary with the real order, CBE/Telebirr instructions and receipt-screenshot state machine.
