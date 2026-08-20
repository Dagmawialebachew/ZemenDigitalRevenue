from enum import StrEnum


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class BotMode(StrEnum):
    POLLING = "polling"
    WEBHOOK = "webhook"


APP_NAME = "Zemen Digital Commerce Engine"
APP_VERSION = "1.0.2"
TELEGRAM_BOT_API_TARGET = "10.2"
AIOGRAM_TARGET = "3.30.0"
