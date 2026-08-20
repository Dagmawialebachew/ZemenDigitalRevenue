from pathlib import Path


def test_start_handler_uses_server_side_entry_service() -> None:
    source = Path("bot/routers/start.py").read_text(encoding="utf-8")
    assert "CustomerEntryService" in source
    assert "parse_start_payload" in source
    assert "focus_product_id" in source


def test_native_button_styles_are_used() -> None:
    language = Path("bot/keyboards/language.py").read_text(encoding="utf-8")
    assert "ButtonStyle.SUCCESS" in language
    assert "ButtonStyle.PRIMARY" in language


def test_dispatcher_does_not_use_memory_fsm_for_customer_state() -> None:
    factory = Path("bot/factory.py").read_text(encoding="utf-8")
    assert "disable_fsm=True" in factory
