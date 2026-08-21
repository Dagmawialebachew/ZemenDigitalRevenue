from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_miniapp_checkout_status_is_read_only_and_persistent() -> None:
    repository = (ROOT / "backend/repositories/payments.py").read_text(encoding="utf-8")
    method = repository.split("async def checkout_status_for_product", 1)[1].split(
        "async def create_order", 1
    )[0]
    service = (ROOT / "backend/services/miniapp.py").read_text(encoding="utf-8")
    assert "active_checkout" in service
    assert "checkout_status_for_product" in service
    assert "FOR UPDATE" not in method
    assert "INSERT" not in method
    assert "UPDATE" not in method


def test_bot_payment_status_reuses_the_existing_order() -> None:
    router = (ROOT / "bot/routers/payments.py").read_text(encoding="utf-8")
    keyboard = (ROOT / "bot/keyboards/payments.py").read_text(encoding="utf-8")
    assert 'F.data.startswith("pay:status:")' in router
    assert "send_order_resume(" in router
    assert 'callback_data=f"pay:status:{order_public_id}"' in keyboard
    assert 'callback_data="menu:help"' in keyboard
    assert "rejection_reason" in (ROOT / "bot/services/payment_copy.py").read_text(encoding="utf-8")


def test_payment_notifications_keep_customer_next_actions() -> None:
    service = (ROOT / "backend/services/payments.py").read_text(encoding="utf-8")
    worker = (ROOT / "workers/handlers/payments.py").read_text(encoding="utf-8")
    keyboard = (ROOT / "bot/keyboards/payments.py").read_text(encoding="utf-8")
    assert '"payment_action": "owned"' in service
    assert '"payment_action": "rejected"' in service
    assert "payment_followup_keyboard" in worker
    assert "reply_markup=reply_markup" in worker
    assert "reply_markup=payment_followup_keyboard" in worker
    assert "Open Library & review" in keyboard


def test_control_room_prioritizes_aging_payment_reviews() -> None:
    repository = (ROOT / "backend/repositories/control.py").read_text(encoding="utf-8")
    view = (ROOT / "dashboard/src/views/PaymentsView.tsx").read_text(encoding="utf-8")
    assert "review_wait_seconds" in repository
    assert "COALESCE(pp.created_at,p.updated_at) END ASC" in repository
    assert "Needs attention · 30m+" in view
    assert "Waiting 15m+" in view


def test_financial_state_machine_remains_authoritative() -> None:
    service = (ROOT / "backend/services/payments.py").read_text(encoding="utf-8")
    assert "pg_advisory_xact_lock" in service
    assert 'event_type="PAYMENT_APPROVED"' in service
    assert 'job_type="telegram.delivery.product"' in service
    assert "approved payment cannot be rejected" in service
