# Final QA Checklist

## Money invariants

- [ ] Double-click payment approval does not duplicate revenue, entitlement, delivery or commission.
- [ ] Discounted/recovery order produces zero referral commission.
- [ ] Full-price eligible referral produces one commission at the snapshotted rate.
- [ ] Old/superseded receipt cannot approve a newer payment submission.
- [ ] Paid/pending-payment customers stop recovery automation.

## Acquisition & CRM

- [ ] `src_...` link resolves only through server-side tracking data.
- [ ] Returning customer does not repeat known onboarding unnecessarily.
- [ ] Product/ad attribution survives checkout/payment/purchase.
- [ ] A first valid referrer is not casually overwritten.

## Delivery & operations

- [ ] Product ownership survives Telegram delivery failure.
- [ ] Failed delivery retries are bounded and alert after terminal failure.
- [ ] ZEMEN OPS callbacks reject unauthorized Telegram admins.
- [ ] Support thread reply/resolve reaches the correct customer/case.

## Marketing

- [ ] Scheduled broadcast snapshot cannot silently change after editing.
- [ ] Automation revision changes do not mutate old runs mid-journey.
- [ ] Recovery offer expiry is enforced by backend state, not only UI timers.
- [ ] Source revenue is not inflated by repeated source touches.

## Security

- [ ] Control owner key never appears in browser storage/API responses.
- [ ] Unsafe Control mutations fail without valid CSRF token.
- [ ] Viewer cannot mutate Control state.
- [ ] Production uses HTTPS secure Control cookie.
- [ ] Raw Telegram Mini App `initData` is validated server-side.

## Recovery

- [ ] `python scripts/preflight.py` passes against production/staging config.
- [ ] Latest PostgreSQL backup has SHA-256 and external copy.
- [ ] A restore drill has been completed on a non-production database.
