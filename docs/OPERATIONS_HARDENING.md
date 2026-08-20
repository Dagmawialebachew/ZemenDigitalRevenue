# Zemen Digital — S08 Operations Hardening

Section 08 turns the S07 payment flow into an operationally resilient commerce system.

## Delivery lifecycle

Every entitlement now keeps explicit delivery counters and error state. Every Telegram delivery attempt is appended to `delivery_attempts` with the originating durable job and attempt number.

Delivery behavior:

1. Payment approval creates entitlement + durable delivery job in the same PostgreSQL transaction.
2. Worker locks the entitlement and records a delivery attempt.
3. Telegram transient errors are retried by the PostgreSQL job engine.
4. Permanent errors or final-attempt failure mark the entitlement `failed`.
5. Terminal job failures create a deduplicated `operational_alert` and queue it to the ZEMEN OPS Alerts topic.
6. The maintenance task detects orphaned/stale/failed deliveries and safely requeues them up to the configured automatic recovery limit.
7. An authenticated operations API can explicitly retry a delivery after human review.

The customer entitlement is the source of truth; a worker restart cannot erase ownership.

## ZEMEN OPS support workflow

`/help` or the Help button creates/reuses one active support case and stores support mode in the PostgreSQL conversation session.

Customer can send:
- text
- photo/screenshot
- document

The message is persisted first, then a durable job forwards it to the Support topic. The admin card includes native Telegram `REPLY` and `RESOLVE` buttons.

`REPLY` uses ForceReply and encodes only the opaque support case ID in the context message. The reply is stored and then delivered to the customer through the durable Telegram notification queue.

`RESOLVE` updates the case, resets the customer's conversation flow, records an analytics event, and notifies the customer.

No Redis/in-memory FSM is required.

## Operational alerts

`operational_alerts` is a deduplicated alert ledger. S08 currently surfaces:
- terminal durable-job failures
- stale payment reviews
- delivery failures through job-failure alerts

The table is intentionally independent from Telegram. Telegram is only one alert surface; S09 can render the same records in the dashboard.

## Maintenance

A single durable `operations.maintenance` chain is bootstrapped at application startup using a PostgreSQL advisory lock. Each completed tick schedules the next tick. This prevents a simple `asyncio.sleep()` loop from being the source of truth.

The tick currently:
- recovers stale/failed product deliveries
- surfaces payments waiting too long for review
- schedules the next durable maintenance tick

## Internal operations API

S08 exposes temporary internal endpoints under `/api/ops`:
- `GET /api/ops/overview`
- `GET /api/ops/queues`
- `POST /api/ops/deliveries/{entitlement_id}/retry`
- `POST /api/ops/maintenance/run`

They require `Authorization: Bearer <OPS_API_KEY>`.

This is an internal machine credential, not the final human dashboard login. S09 will add the proper dashboard authentication/role layer above these operational services.
