from backend.core.config import Settings
from shared.constants import BotMode


def test_polling_defaults_do_not_require_webhook() -> None:
    settings = Settings(bot_token="123456:ABC", bot_mode=BotMode.POLLING, _env_file=None)
    assert not [e for e in settings.runtime_errors() if "WEBHOOK" in e]


def test_admin_ids_parse() -> None:
    settings = Settings(admin_telegram_ids="1, 2,3", _env_file=None)
    assert settings.admin_telegram_ids == (1, 2, 3)


def test_scale_to_zero_database_pool_can_start_empty() -> None:
    settings = Settings(
        db_min_pool_size=0,
        db_max_pool_size=3,
        db_max_inactive_connection_lifetime_seconds=60,
        worker_listen_notify_enabled=False,
        worker_poll_fallback_seconds=900,
        worker_recovery_interval_seconds=900,
        _env_file=None,
    )

    assert not [error for error in settings.runtime_errors() if error.startswith("DB_")]
    assert settings.db_min_pool_size == 0
    assert settings.worker_listen_notify_enabled is False
