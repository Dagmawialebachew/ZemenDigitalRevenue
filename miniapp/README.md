# Zemen Digital Mini App — Section 06

The Mini App is the **storefront**, not the salesman. The Telegram bot remains the conversation, onboarding, payment-proof, delivery and retargeting surface.

## UX contract

- Brand palette only: near-black, deep forest, Zemen green, warm ivory.
- Mobile-first and safe-area aware.
- Amharic + English with language persisted to the same PostgreSQL user profile.
- Five bottom tabs only: Home, Store, Library, Earn, Account.
- Product data is fetched from PostgreSQL; no product is hardcoded into the React app.
- Referral center clearly states that 10% commission applies only to full-price sales. Discounted sales remain attributable but create zero commission.
- `Telegram.WebApp.initDataUnsafe` is never trusted by the backend. Raw `initData` is verified server-side.
- Product purchase intent is persisted before the app hands the customer back to Telegram. S07 connects this handoff to the CBE/Telebirr order + screenshot flow.

## Telegram 2026 features used

- Main Mini App / menu-button compatible architecture.
- Telegram BackButton for product navigation.
- Native MainButton on product pages with Zemen green, progress-ready behavior and shine effect.
- Haptic feedback.
- Telegram popup and Telegram-link handoff.
- Safe-area CSS variables for fullscreen/newer clients.
- Telegram header/background/bottom-bar colors are set to the Zemen brand shell.

## Local development

```bash
cd miniapp
cp .env.example .env
npm install
npm run dev
```

The production Mini App must be served over HTTPS and its URL configured in BotFather and `MINI_APP_URL`.

For backend CORS, add the exact production Mini App origin to `MINI_APP_ALLOWED_ORIGINS`.

## Production build

```bash
npm run build
```

Deploy `miniapp/dist/` to your HTTPS static host. Do not put `BOT_TOKEN` or any backend secret in Vite environment variables.
