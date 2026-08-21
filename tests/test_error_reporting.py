from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.core.config import Settings
from backend.services.error_reporting import ErrorReporter


def _failure() -> RuntimeError:
    try:
        raise RuntimeError(
            "DATABASE_URL=postgresql://owner:password@example/db "
            "BOT_TOKEN=123456789:abcdefghijklmnopqrstuvwxyzABCDE"
        )
    except RuntimeError as exc:
        return exc


@pytest.mark.asyncio
async def test_error_report_is_sanitized_and_deduplicated() -> None:
    bot = AsyncMock()
    settings = Settings(
        workers_enabled=False,
        zemen_ops_group_id=-100123,
        zemen_ops_topic_errors=77,
    )
    reporter = ErrorReporter(bot=bot, settings=settings)
    failure = _failure()

    assert await reporter.report(failure, surface="telegram_bot", context={"update_id": 42})
    assert not await reporter.report(failure, surface="telegram_bot", context={"update_id": 42})

    bot.send_message.assert_awaited_once()
    call = bot.send_message.await_args.kwargs
    assert call["chat_id"] == -100123
    assert call["message_thread_id"] == 77
    assert "[REDACTED]" in call["text"]
    assert "owner:password" not in call["text"]
    assert "abcdefghijklmnopqrstuvwxyzABCDE" not in call["text"]


@pytest.mark.asyncio
async def test_error_reporter_is_disabled_until_errors_topic_is_configured() -> None:
    bot = AsyncMock()
    reporter = ErrorReporter(
        bot=bot,
        settings=Settings(workers_enabled=False, zemen_ops_group_id=-100123),
    )

    assert not await reporter.report(_failure(), surface="api")
    bot.send_message.assert_not_awaited()


def test_all_runtime_surfaces_are_wired_to_error_reporting() -> None:
    app = Path("backend/app.py").read_text(encoding="utf-8")
    factory = Path("bot/factory.py").read_text(encoding="utf-8")
    background = Path("bot/services/background.py").read_text(encoding="utf-8")
    operations = Path("workers/handlers/operations.py").read_text(encoding="utf-8")
    engine = Path("workers/engine.py").read_text(encoding="utf-8")
    blueprint = Path("render.yaml").read_text(encoding="utf-8")

    assert "ErrorReportingMiddleware" in app
    assert "dp.errors.register(report_unhandled_update)" in factory
    assert 'surface="background"' in background
    assert "zemen_ops_topic_errors" in operations
    assert 'surface="worker_job"' in engine
    assert "ZEMEN_OPS_TOPIC_ERRORS" in blueprint
