from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_acceptance_is_durable_and_required_before_payment_method() -> None:
    migration = source("database/migrations/0014_trust_center.sql")
    payments = source("backend/services/payments.py")
    assert "CREATE TABLE legal_acceptances" in migration
    assert "UNIQUE (user_id, order_id, policy_version)" in migration
    assert "accept_purchase_policies" in payments
    assert "if not accepted:" in payments
    assert "before choosing payment" in payments


def test_policy_documents_are_available_on_both_buyer_surfaces() -> None:
    policies = source("backend/domain/policies.py")
    legal_router = source("bot/routers/legal.py")
    miniapp_routes = source("backend/api/routes/miniapp.py")
    miniapp_app = source("miniapp/src/App.tsx")
    for kind in ("terms", "refund", "privacy", "delivery"):
        assert f'"{kind}"' in policies
        assert f'Command("{kind}")' in legal_router
    assert '@router.get("/policies/{kind}")' in miniapp_routes
    assert "<PolicyView" in miniapp_app


def test_payment_support_and_operational_categories_remain_connected() -> None:
    support = source("bot/routers/support.py")
    control = source("dashboard/src/views/SupportView.tsx")
    commands = source("bot/services/setup.py")
    assert 'Command("paysupport")' in support
    for subject in ("payment_support", "refund_request", "missing_delivery"):
        assert subject in support
        assert subject in control
    assert 'BotCommand(command="paysupport"' in commands


def test_new_checkout_is_method_first_but_acceptance_stays_before_details() -> None:
    payments_router = source("bot/routers/payments.py")
    keyboards = source("bot/keyboards/payments.py")
    assert "reply_markup=payment_method_keyboard(" in payments_router
    assert 'F.data.startswith("pay:confirm:")' in payments_router
    assert "await service.accept_purchase_policies(" in payments_router
    assert "await service.select_method(" in payments_router
    assert "payment_confirmation_keyboard" in keyboards
