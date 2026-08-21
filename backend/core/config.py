from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from shared.constants import AppEnvironment, BotMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    bot_token: str = ""
    bot_mode: BotMode = BotMode.POLLING
    bot_username: str = ""
    telegram_webhook_base_url: str = ""
    telegram_webhook_path: str = "/telegram/webhook"
    telegram_webhook_secret: str = ""
    mini_app_url: str = ""
    mini_app_session_secret: str = ""
    mini_app_auth_max_age_seconds: int = 900
    mini_app_session_ttl_seconds: int = 43200
    mini_app_allowed_origins: Annotated[tuple[str, ...], NoDecode] = ("http://localhost:5173",)

    zemen_ops_group_id: int | None = None
    zemen_ops_topic_new_users: int | None = None
    zemen_ops_topic_payments: int | None = None
    zemen_ops_topic_sales: int | None = None
    zemen_ops_topic_support: int | None = None
    zemen_ops_topic_alerts: int | None = None
    zemen_ops_topic_errors: int | None = None
    admin_telegram_ids: Annotated[tuple[int, ...], NoDecode] = Field(default_factory=tuple)

    database_url: str = ""
    db_min_pool_size: int = 2
    db_max_pool_size: int = 10
    db_max_inactive_connection_lifetime_seconds: float = 300.0

    workers_enabled: bool = True
    worker_concurrency: int = 4
    worker_queues: Annotated[tuple[str, ...], NoDecode] = (
        "default",
        "telegram",
        "delivery",
        "automation",
        "broadcast",
    )
    worker_listen_notify_enabled: bool = True
    worker_lease_seconds: int = 180
    worker_poll_fallback_seconds: float = 10.0
    worker_recovery_interval_seconds: float = 30.0
    worker_recovery_batch_size: int = 100
    worker_retry_base_seconds: float = 2.0
    worker_retry_cap_seconds: float = 900.0
    worker_error_sleep_seconds: float = 2.0
    worker_shutdown_grace_seconds: float = 20.0

    telegram_use_button_styles: bool = True
    telegram_use_rich_messages: bool = True
    telegram_button_custom_emoji_id: str = ""

    # Manual ETB checkout is implemented as a pluggable channel. Telegram's
    # current digital-goods policy requires Stars for in-Telegram sales, so
    # production deployments must consciously choose their compliant surface.
    manual_payment_in_telegram_enabled: bool = False
    external_manual_checkout_url: str = ""
    cbe_account_name: str = ""
    cbe_account_number: str = ""
    telebirr_account_name: str = ""
    telebirr_number: str = ""
    order_ttl_minutes: int = 180
    commission_hold_days: int = 3

    # SECTION 09 — Zemen Control
    control_owner_key: str = ""
    control_session_secret: str = ""
    control_session_ttl_seconds: int = 43200
    control_allowed_origins: Annotated[tuple[str, ...], NoDecode] = ("http://localhost:5174",)
    control_cookie_name: str = "zemen_control_session"
    control_cookie_secure: bool = False
    control_login_max_attempts: int = 8
    control_login_window_seconds: int = 900
    static_apps_enabled: bool = False

    # SECTION 10 — Product Control / Telegram-backed product storage
    telegram_storage_chat_id: int | None = None
    public_api_base_url: str = "http://127.0.0.1:8000"
    product_upload_max_mb: int = 45

    # SECTION 11 — Marketing Engine
    marketing_upload_max_mb: int = 45
    marketing_maintenance_interval_seconds: int = 300
    broadcast_dispatch_batch_size: int = 250
    broadcast_send_max_attempts: int = 8

    # SECTION 08 — operations hardening
    ops_api_key: str = ""
    ops_maintenance_interval_seconds: int = 60
    ops_maintenance_batch_size: int = 100
    payment_review_stale_minutes: int = 15
    delivery_stale_minutes: int = 10
    delivery_job_max_attempts: int = 5
    delivery_max_total_attempts: int = 12
    job_failure_alerts_enabled: bool = True

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> tuple[int, ...]:
        if value in (None, ""):
            return ()
        if isinstance(value, str):
            return tuple(int(item.strip()) for item in value.split(",") if item.strip())
        if isinstance(value, (list, tuple, set)):
            return tuple(int(item) for item in value)
        raise ValueError("ADMIN_TELEGRAM_IDS must be comma-separated integers")

    @field_validator("mini_app_allowed_origins", mode="before")
    @classmethod
    def parse_mini_app_origins(cls, value: object) -> tuple[str, ...]:
        if value in (None, ""):
            return ()
        if isinstance(value, str):
            return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())
        if isinstance(value, (list, tuple, set)):
            return tuple(str(item).strip().rstrip("/") for item in value if str(item).strip())
        raise ValueError("MINI_APP_ALLOWED_ORIGINS must be comma-separated origins")

    @field_validator("control_allowed_origins", mode="before")
    @classmethod
    def parse_control_origins(cls, value: object) -> tuple[str, ...]:
        if value in (None, ""):
            return ()
        if isinstance(value, str):
            return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())
        if isinstance(value, (list, tuple, set)):
            return tuple(str(item).strip().rstrip("/") for item in value if str(item).strip())
        raise ValueError("CONTROL_ALLOWED_ORIGINS must be comma-separated origins")

    @field_validator("worker_queues", mode="before")
    @classmethod
    def parse_worker_queues(cls, value: object) -> tuple[str, ...]:
        if value in (None, ""):
            return ("default",)
        if isinstance(value, str):
            items = tuple(item.strip() for item in value.split(",") if item.strip())
            return items or ("default",)
        if isinstance(value, (list, tuple, set)):
            items = tuple(str(item).strip() for item in value if str(item).strip())
            return items or ("default",)
        raise ValueError("WORKER_QUEUES must be comma-separated queue names")

    @property
    def webhook_url(self) -> str:
        if not self.telegram_webhook_base_url:
            return ""
        return f"{self.telegram_webhook_base_url.rstrip('/')}{self.telegram_webhook_path}"

    def runtime_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.bot_token:
            errors.append("BOT_TOKEN is empty")
        if self.bot_mode == BotMode.WEBHOOK:
            if not self.webhook_url:
                errors.append("TELEGRAM_WEBHOOK_BASE_URL is required in webhook mode")
            if not self.telegram_webhook_secret:
                errors.append("TELEGRAM_WEBHOOK_SECRET is required in webhook mode")
        if self.db_min_pool_size < 0:
            errors.append("DB_MIN_POOL_SIZE must be >= 0")
        if self.db_max_pool_size < self.db_min_pool_size:
            errors.append("DB_MAX_POOL_SIZE must be >= DB_MIN_POOL_SIZE")
        if self.db_max_pool_size < 1:
            errors.append("DB_MAX_POOL_SIZE must be >= 1")
        if self.db_max_inactive_connection_lifetime_seconds < 0:
            errors.append("DB_MAX_INACTIVE_CONNECTION_LIFETIME_SECONDS must be >= 0")
        if self.bot_token and not self.database_url:
            errors.append("DATABASE_URL is required when BOT_TOKEN is configured")
        if self.workers_enabled and not self.database_url:
            errors.append("DATABASE_URL is required when WORKERS_ENABLED=true")
        if self.mini_app_auth_max_age_seconds < 60:
            errors.append("MINI_APP_AUTH_MAX_AGE_SECONDS must be >= 60")
        if self.mini_app_session_ttl_seconds < 60:
            errors.append("MINI_APP_SESSION_TTL_SECONDS must be >= 60")
        if self.worker_concurrency < 1:
            errors.append("WORKER_CONCURRENCY must be >= 1")
        if self.worker_lease_seconds < 15:
            errors.append("WORKER_LEASE_SECONDS must be >= 15")
        if self.worker_poll_fallback_seconds <= 0:
            errors.append("WORKER_POLL_FALLBACK_SECONDS must be > 0")
        if self.worker_recovery_interval_seconds <= 0:
            errors.append("WORKER_RECOVERY_INTERVAL_SECONDS must be > 0")
        if self.worker_recovery_batch_size < 1:
            errors.append("WORKER_RECOVERY_BATCH_SIZE must be >= 1")
        if self.worker_retry_base_seconds <= 0:
            errors.append("WORKER_RETRY_BASE_SECONDS must be > 0")
        if self.worker_retry_cap_seconds < self.worker_retry_base_seconds:
            errors.append("WORKER_RETRY_CAP_SECONDS must be >= WORKER_RETRY_BASE_SECONDS")
        if self.order_ttl_minutes < 15:
            errors.append("ORDER_TTL_MINUTES must be >= 15")
        if self.commission_hold_days < 0:
            errors.append("COMMISSION_HOLD_DAYS must be >= 0")
        if self.control_session_ttl_seconds < 300:
            errors.append("CONTROL_SESSION_TTL_SECONDS must be >= 300")
        if self.control_login_max_attempts < 3:
            errors.append("CONTROL_LOGIN_MAX_ATTEMPTS must be >= 3")
        if self.control_login_window_seconds < 60:
            errors.append("CONTROL_LOGIN_WINDOW_SECONDS must be >= 60")
        if self.control_owner_key and not self.control_session_secret:
            errors.append("CONTROL_SESSION_SECRET is required when CONTROL_OWNER_KEY is configured")
        if self.product_upload_max_mb < 1:
            errors.append("PRODUCT_UPLOAD_MAX_MB must be >= 1")
        if self.marketing_upload_max_mb < 1:
            errors.append("MARKETING_UPLOAD_MAX_MB must be >= 1")
        if self.marketing_maintenance_interval_seconds < 60:
            errors.append("MARKETING_MAINTENANCE_INTERVAL_SECONDS must be >= 60")
        if self.broadcast_dispatch_batch_size < 1 or self.broadcast_dispatch_batch_size > 5000:
            errors.append("BROADCAST_DISPATCH_BATCH_SIZE must be between 1 and 5000")
        if self.broadcast_send_max_attempts < 1:
            errors.append("BROADCAST_SEND_MAX_ATTEMPTS must be >= 1")
        if self.ops_maintenance_interval_seconds < 15:
            errors.append("OPS_MAINTENANCE_INTERVAL_SECONDS must be >= 15")
        if self.ops_maintenance_batch_size < 1:
            errors.append("OPS_MAINTENANCE_BATCH_SIZE must be >= 1")
        if self.payment_review_stale_minutes < 1:
            errors.append("PAYMENT_REVIEW_STALE_MINUTES must be >= 1")
        if self.delivery_stale_minutes < 1:
            errors.append("DELIVERY_STALE_MINUTES must be >= 1")
        if self.delivery_job_max_attempts < 1:
            errors.append("DELIVERY_JOB_MAX_ATTEMPTS must be >= 1")
        if self.delivery_max_total_attempts < self.delivery_job_max_attempts:
            errors.append("DELIVERY_MAX_TOTAL_ATTEMPTS must be >= DELIVERY_JOB_MAX_ATTEMPTS")
        return errors


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
