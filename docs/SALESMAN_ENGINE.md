# S05 — Premium Salesman Engine

## What this section adds

The bot now moves a first-time lead through four one-tap profile questions and then builds a product-specific sales presentation from persisted facts rather than a generic welcome flow.

### Four-question profile

1. Role
2. AI experience
3. Main goal (options are reordered for the selected role)
4. Main obstacle

The question card is edited in place, shows 1/4 → 4/4 progress, and persists every answer immediately in PostgreSQL. A process restart never destroys onboarding progress.

## Personalization inputs

Sales copy can react to:

- role
- AI experience
- goal
- obstacle
- focused product
- tracked ad angle
- language
- recorded product behavior

`product_content_blocks` is the dashboard-owned override layer. S05 defines the lookup contract now so S10 can populate/edit copy without changing Python.

Supported block keys currently used by the salesman:

- `sales_hook`
- `sales_preview`
- `sales_objection`

Audience keys are searched most-specific first, for example:

`role:student|exp:tried_confused|goal:learn_faster|obstacle:dont_know_what_to_ask|angle:beginner_confusion`

then progressively broader keys, ending with `default`.

## Intent model

`user_product_journeys` is per product. This is deliberately separate from the global `users.customer_stage` because one customer can be a buyer of Product A while still exploring Product B.

Unique signals prevent double taps from inflating intent score:

- ONBOARDING_COMPLETED +20
- SALES_PITCH_VIEWED +10
- PREVIEW_VIEWED +20
- OBJECTION_OPENED +10
- BUY_CLICKED +40

Repeated behavior still goes into the append-only `events` table for analytics.

## Persuasion rules

The fallback copy uses specificity, micro-commitment, personal relevance, contrast and loss-of-opportunity framing. It does not fabricate scarcity, reviews, countdowns, guarantees or product claims. Product-specific claims should come from dashboard-authored product content.

## S07 handoff

The `sales:buy` callback records durable BUY_CLICKED intent now. S07 replaces the temporary handoff message with real order creation, CBE/Telebirr instructions and screenshot collection.
