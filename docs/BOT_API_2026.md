# Telegram capability baseline — Section 01

Target: Telegram Bot API 10.2 + aiogram 3.30.0.

We will use new platform capabilities when they genuinely improve the Zemen UX:

- Native button styles on both inline and reply keyboards: `primary`, `success`, `danger`.
- Optional custom-emoji icons on buttons where Telegram account eligibility permits it.
- Rich Messages for structured premium presentation, with normal-message fallback.
- Rich-message drafts / message drafts only where live-progress UX is useful.
- Forum topics / `message_thread_id` for ZEMEN OPS routing.
- Mini Apps for Store / Library / Earn / Account.
- Deep-link `/start` payloads for ad/product/referral attribution.
- Ephemeral group interactions where they solve a real privacy/clutter problem.

## Important brand limitation

Telegram native bot buttons do **not** accept arbitrary hex background colors. The API offers
predefined client-rendered styles: primary (blue), success (green), danger (red), or default.
Therefore:

- positive customer CTA / approve = `success`
- main neutral action = `primary`
- reject/destructive action = `danger`
- exact Zemen colors remain under our control in the Mini App and dashboard

We will not fake custom colors with misleading emoji blocks.
