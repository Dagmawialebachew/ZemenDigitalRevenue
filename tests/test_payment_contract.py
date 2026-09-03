from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_payment_worker_refuses_stale_proof_jobs() -> None:
    text = (ROOT / "workers/handlers/payments.py").read_text(encoding="utf-8")
    assert 'row["latest_proof_id"] != proof_id' in text
    assert '"superseded": True' in text


def test_admin_actions_are_bound_to_reviewed_proof() -> None:
    service = (ROOT / "backend/services/payments.py").read_text(encoding="utf-8")
    router = (ROOT / "bot/routers/payments.py").read_text(encoding="utf-8")
    assert "review_proof_for_message" in service
    assert "_assert_expected_proof" in service
    assert "expected_proof_id=expected_proof_id" in router
    assert "CUSTOM_REJECTION_CONTEXT" in router
    assert "ForceReply" in router


def test_approval_uses_transactional_outbox_jobs() -> None:
    payments = (ROOT / "backend/services/payments.py").read_text(encoding="utf-8")
    jobs = (ROOT / "backend/repositories/jobs.py").read_text(encoding="utf-8")
    assert "enqueue_in_tx" in jobs
    assert payments.count("enqueue_in_tx") >= 3
    assert "telegram.delivery.product" in payments
    assert "telegram.ops.notify" in payments


def test_callback_data_contract_stays_under_telegram_limit() -> None:
    payment_id = "PAY-1234567890"
    callbacks = [
        f"ops:pay:approve:{payment_id}",
        f"ops:pay:reject:{payment_id}",
        f"ops:pay:flag:{payment_id}",
        f"ops:pay:reason:{payment_id}:transaction_not_found",
        f"pay:paid:{payment_id}",
        "pay:method:ZD-1234567890:telebirr",
    ]
    assert all(len(item.encode("utf-8")) <= 64 for item in callbacks)


def test_discounted_orders_cannot_create_commission_in_service_or_db() -> None:
    service = (ROOT / "backend/services/payments.py").read_text(encoding="utf-8")
    invariant = (ROOT / "database/migrations/0002_invariants_indexes.sql").read_text(encoding="utf-8")
    assert 'order["pricing_type"] == "regular"' in service
    assert "Discounted orders cannot generate referral commission" in invariant


def test_automated_drip_payment_recovery_engine_contract() -> None:
    service = (ROOT / "backend/services/payments.py").read_text(encoding="utf-8")
    handlers = (ROOT / "workers/handlers/payments.py").read_text(encoding="utf-8")
    registry = (ROOT / "workers/handlers/__init__.py").read_text(encoding="utf-8")

    assert 'payment.drip.reminder_15m' in service
    assert 'payment.drip.reminder_2h' in service
    assert 'payment.drip.reminder_24h' in service

    assert 'payment_drip_reminder_handler' in handlers
    assert 'pay:paid:{payment_public_id}' in handlers
    assert 'pay:status:{order_public_id}' in handlers
    assert 'payment_already_progressed' in handlers

    assert 'registry.register("payment.drip.reminder_15m", payment_drip_reminder_handler)' in registry
    assert 'registry.register("payment.drip.reminder_2h", payment_drip_reminder_handler)' in registry
    assert 'registry.register("payment.drip.reminder_24h", payment_drip_reminder_handler)' in registry


def test_customer_offer_foreign_key_safety() -> None:
    repo = (ROOT / "backend/repositories/payments.py").read_text(encoding="utf-8")
    service = (ROOT / "backend/services/payments.py").read_text(encoding="utf-8")

    # Offer ID in checkout query must strictly bind to customer_offers (not discount_rules)
    assert "offer.id AS offer_id," in repo
    assert "rule_offer" not in repo
    assert "COALESCE(offer.id, rule_offer.id)" not in repo

    # Defensive check in service must ensure offer exists in customer_offers table before setting customer_offer_id
    assert "validated_offer_id" in service
    assert "SELECT 1 FROM customer_offers WHERE id = $1" in service

