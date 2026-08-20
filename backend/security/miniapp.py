from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl
from uuid import UUID


class MiniAppAuthError(ValueError):
    """Raised when Telegram Mini App authentication data is invalid."""


@dataclass(frozen=True, slots=True)
class TelegramMiniAppIdentity:
    telegram_id: int
    first_name: str
    last_name: str | None
    username: str | None
    language_code: str | None
    photo_url: str | None
    is_premium: bool
    auth_date: int
    query_id: str | None
    start_param: str | None


@dataclass(frozen=True, slots=True)
class MiniAppSession:
    user_id: UUID
    telegram_id: int
    issued_at: int
    expires_at: int


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def validate_telegram_init_data(
    init_data: str,
    *,
    bot_token: str,
    max_age_seconds: int,
    now: int | None = None,
) -> TelegramMiniAppIdentity:
    """Validate Telegram.WebApp.initData using Telegram's documented HMAC flow.

    Never trust ``initDataUnsafe`` from the browser. The client sends the raw
    ``initData`` query string and the backend verifies it with the bot token.
    """
    if not init_data or not bot_token:
        raise MiniAppAuthError("missing init data or bot token")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received_hash = pairs.get("hash", "")
    if not received_hash:
        raise MiniAppAuthError("missing Telegram hash")

    check_pairs = [(key, value) for key, value in pairs.items() if key != "hash"]
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(check_pairs))

    # Telegram Mini Apps: secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise MiniAppAuthError("invalid Telegram signature")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as exc:
        raise MiniAppAuthError("invalid auth_date") from exc
    timestamp = int(time.time()) if now is None else int(now)
    if auth_date <= 0 or auth_date > timestamp + 30:
        raise MiniAppAuthError("invalid auth_date")
    if max_age_seconds > 0 and timestamp - auth_date > max_age_seconds:
        raise MiniAppAuthError("expired Telegram init data")

    try:
        user = json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError as exc:
        raise MiniAppAuthError("invalid Telegram user payload") from exc
    if not isinstance(user, dict) or not user.get("id"):
        raise MiniAppAuthError("Telegram user is missing")

    return TelegramMiniAppIdentity(
        telegram_id=int(user["id"]),
        first_name=str(user.get("first_name") or ""),
        last_name=str(user["last_name"]) if user.get("last_name") else None,
        username=str(user["username"]) if user.get("username") else None,
        language_code=str(user["language_code"]) if user.get("language_code") else None,
        photo_url=str(user["photo_url"]) if user.get("photo_url") else None,
        is_premium=bool(user.get("is_premium", False)),
        auth_date=auth_date,
        query_id=pairs.get("query_id") or None,
        start_param=pairs.get("start_param") or None,
    )


class MiniAppSessionCodec:
    """Tiny stateless HMAC session token; no Redis/session table required."""

    def __init__(self, *, secret: str, ttl_seconds: int) -> None:
        if not secret:
            raise ValueError("Mini App session secret cannot be empty")
        if ttl_seconds < 60:
            raise ValueError("Mini App session TTL must be at least 60 seconds")
        self._key = hmac.new(
            b"zemen-miniapp-session-v1",
            secret.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        self.ttl_seconds = ttl_seconds

    def issue(self, *, user_id: UUID, telegram_id: int, now: int | None = None) -> str:
        issued = int(time.time()) if now is None else int(now)
        payload = {
            "sub": str(user_id),
            "tg": int(telegram_id),
            "iat": issued,
            "exp": issued + self.ttl_seconds,
            "v": 1,
        }
        body = _b64url_encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        sig = _b64url_encode(hmac.new(self._key, body.encode("ascii"), hashlib.sha256).digest())
        return f"{body}.{sig}"

    def verify(self, token: str, *, now: int | None = None) -> MiniAppSession:
        try:
            body, sig = token.split(".", 1)
        except ValueError as exc:
            raise MiniAppAuthError("invalid session token") from exc

        expected = _b64url_encode(
            hmac.new(self._key, body.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected, sig):
            raise MiniAppAuthError("invalid session signature")

        try:
            payload: dict[str, Any] = json.loads(_b64url_decode(body))
            user_id = UUID(str(payload["sub"]))
            telegram_id = int(payload["tg"])
            issued_at = int(payload["iat"])
            expires_at = int(payload["exp"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise MiniAppAuthError("invalid session payload") from exc

        timestamp = int(time.time()) if now is None else int(now)
        if expires_at <= timestamp:
            raise MiniAppAuthError("expired session")
        if issued_at > timestamp + 30:
            raise MiniAppAuthError("invalid session issued time")

        return MiniAppSession(
            user_id=user_id,
            telegram_id=telegram_id,
            issued_at=issued_at,
            expires_at=expires_at,
        )
