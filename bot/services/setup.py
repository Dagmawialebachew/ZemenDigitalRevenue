from __future__ import annotations

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from backend.core.config import Settings

log = structlog.get_logger(__name__)


async def configure_bot_ui(bot: Bot, settings: Settings) -> None:
    """Apply safe, current Telegram-native bot UI settings.

    Failure here never prevents the bot from serving customers.
    """
    commands = [
        BotCommand(command="start", description="Start / continue Zemen"),
        BotCommand(command="home", description="Open Zemen home"),
        BotCommand(command="help", description="Get help"),
    ]
    try:
        await bot.set_my_commands(commands)
        if settings.mini_app_url:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🛍 Zemen Store",
                    web_app=WebAppInfo(url=settings.mini_app_url),
                )
            )
    except TelegramAPIError as exc:
        log.warning("telegram_ui_configuration_failed", error=str(exc))
