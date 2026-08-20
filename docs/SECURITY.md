# Security & Operations Notes

- Never commit `.env`, bot tokens, bank/payment credentials, owner keys or session secrets.
- Use unrelated random values for webhook secret, Mini App session secret, Control owner key and Control session secret.
- Set `CONTROL_COOKIE_SECURE=true` behind production HTTPS.
- Restrict ZEMEN OPS and Telegram storage chats to required administrators/bot only.
- Rotate a secret immediately after suspected exposure; do not merely delete it from the latest commit.
- Keep PostgreSQL private from the public internet when platform networking allows it.
- Use least-privilege admin roles. `viewer` is read-only; payment/product/marketing routes retain service-level authorization and all Control mutations are CSRF protected.
- Receipt/OCR signals are evidence-assistance, not proof of bank settlement by themselves.
- Do not auto-approve ambiguous payment evidence.
- Do not fabricate reviews, scarcity, purchase counters or referral earnings.
- Backups contain personal/business data. Encrypt/restrict their storage and test restores.
