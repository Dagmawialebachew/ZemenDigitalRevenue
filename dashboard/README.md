# Zemen Control — Section 10

Premium operator dashboard for Zemen Digital.

## Pages

- Overview
- Payments
- Orders
- Deliveries
- Customers
- **Products — full commercial editor**
- Support
- Alerts

## Product Control

Open any product to manage:

- basics and pricing;
- Amharic / English storefront content;
- cover, previews and gallery;
- versioned delivery files;
- per-audience Bot Salesman copy;
- upsells / cross-sells / next-product paths;
- publish, hide and archive state.

Create Product also lives entirely in the dashboard. Product additions no longer require Python edits.

## Run

```bash
npm install
npm run dev
```

Default: `http://localhost:5174`

Optional `.env`:

```env
VITE_API_BASE=http://localhost:8000
```

## Authentication

The login screen exchanges a private Control Owner Key + authorized Telegram admin ID for an HttpOnly signed backend session. The access key is not stored in localStorage/sessionStorage.

## Install on a computer

Zemen Control is an installable Progressive Web App. After the Vercel deployment
finishes, open the production URL in Chrome or Microsoft Edge and click **Install
app** near the top-right corner. It then opens from the desktop or Start menu in
its own window using the Zemen icon.

Only the static application shell is cached. API, authentication, payment, and
customer responses are deliberately excluded, so live business data still comes
from the secured backend.

## Design

Locked Zemen visual language only: near-black, deep forest, bright Zemen green, warm ivory. Product Control deliberately keeps the interface business-readable rather than turning it into a developer console.
