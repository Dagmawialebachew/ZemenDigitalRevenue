# Zemen Digital — Product Control (S10)

Section 10 turns Products from a read-only catalog page into the commercial source of truth for the Bot, Mini App and fulfillment pipeline.

## Control surface

Each product has one editor with these sections:

- **Basics & Pricing** — slug, type, category, default language, regular/recovery price, referral settings, featured/sort order.
- **Store · AM / Store · EN** — title, subtitle, short/full description, benefits and FAQ.
- **Media** — cover, thumbnail, previews, gallery/video, URL-backed or Telegram-backed.
- **Delivery** — product versions, active delivery file and release notes.
- **Bot Salesman** — dashboard-authored `sales_hook`, `sales_preview` and `sales_objection` blocks by language/audience.
- **Upsells** — explicit product-to-product recommendations.

## Publish safety

Publishing is a backend operation, not a frontend-only status toggle.

For `digital_file` / `digital_bundle` products the server blocks publish when:

- the default-language title is missing;
- no active delivery file exists;
- recovery discounts are enabled without a recovery price.

A missing cover/category is a warning, not a hard blocker.

## Pricing and referral invariant

`commission_only_full_price` is permanently enforced by PostgreSQL in `0010_product_control.sql`.

The dashboard can configure the referral percentage and turn referrals on/off, but it cannot make discounted orders commissionable.

## Product revision safety

Core product and translation records have revision numbers. The dashboard sends the revision it loaded; stale writes are rejected with a conflict rather than silently overwriting a newer edit.

## Telegram-backed file storage

Set:

```env
TELEGRAM_STORAGE_CHAT_ID=
PUBLIC_API_BASE_URL=https://api.example.com
PRODUCT_UPLOAD_MAX_MB=45
```

The storage chat/channel must be private and accessible by the bot.

When an admin uploads media or a delivery file in Zemen Control:

1. the backend uploads it to the private Telegram storage chat;
2. Telegram returns `file_id` / `file_unique_id`;
3. only identifiers and metadata are persisted in PostgreSQL;
4. storefront images are served through `/api/public/product-media/{media_id}` so the browser never receives the bot token;
5. delivery uses the active `product_files` record.

A URL-backed media option remains available for CDN/object-storage assets.

## Version activation

Only one delivery file can be active per product. Activating a new version automatically deactivates the old version for future purchases. Existing entitlements keep their recorded file linkage unless a later business workflow intentionally updates them.

## Sales content audience keys

The S05 salesman already resolves prioritized audience keys such as:

```text
role:student
role:professional
exp:tried_confused
goal:learn_faster
obstacle:dont_know_what_to_ask
angle:beginner_confusion
default
```

S10 writes versioned active content blocks that plug directly into that resolver. Empty custom copy falls back to the built-in Zemen salesman message.

## Upsells

`product_relationships` stores `upsell`, `cross_sell`, and `next` relationships. This keeps recommendations data-driven and ready for later post-purchase automation without hard-coded product names.
