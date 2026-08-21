# Zemen Digital Trust Center

Policy version: `2026-08-21`

The canonical buyer-facing copy lives in `backend/domain/policies.py`. Keep both
Amharic and English documents synchronized and increment `POLICY_VERSION` whenever
a material promise, eligibility rule, licence, or data practice changes.

## Service promises

- Seller: Zemen Digital. All displayed prices are Ethiopian birr.
- Support channel: the Zemen Telegram bot, every day from 8:00 AM to 10:00 PM EAT.
- General support: normally within 12 hours.
- Payment review: normally within 30 minutes during support hours; complicated
  cases may take up to 24 hours.
- Delivery: normally within 5 minutes after payment approval. A buyer should open
  `/paysupport` if delivery is still missing 30 minutes after approval.
- Refund requests: within 7 calendar days of payment and subject to the published
  digital-product eligibility rules.

## Purchase controls

The bot must not reveal CBE or Telebirr destinations until the buyer accepts the
current Terms of Purchase and Refund Policy. Acceptance is recorded per user,
order, and policy version in `legal_acceptances`. `PaymentService.select_method`
enforces this on the server so callback manipulation cannot bypass it.

Buyer documents are available through `/terms`, `/refund`, `/privacy`, and
`/delivery`, and through the Mini App Trust Center. Payment-specific help uses
`/paysupport`; refund and missing-delivery buttons create categorized support cases
for the Telegram OPS group and Control Room queue.

## Operator checklist

- Never request a bank/wallet password, PIN, or OTP.
- Review the oldest clear receipts first and use rejection reasons consistently.
- Restore access or redeliver before refunding when that fully fixes the problem.
- Record all payment, refund, and delivery communication in the existing support
  case so the customer and operators share one history.
- When policy copy changes materially, create a migration only if its storage model
  changes; always update the policy version and redeploy the bot/API and Mini App.
