from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from backend.core.config import Settings, get_settings


@dataclass(frozen=True, slots=True)
class ControlPrincipal:
    telegram_id: int
    issued_at: int
    expires_at: int


class ControlSessionCodec:
    """Small signed-cookie codec for the control room.

    The dashboard never stores the owner key. Login exchanges it for a short-lived,
    HttpOnly signed session cookie. The payload is integrity protected with HMAC-SHA256.
    """

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("CONTROL_SESSION_SECRET is required")
        self._secret = secret.encode("utf-8")

    @staticmethod
    def _b64encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    @staticmethod
    def _b64decode(data: str) -> bytes:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))

    def encode(self, *, telegram_id: int, ttl_seconds: int, now: int | None = None) -> str:
        issued_at = int(time.time() if now is None else now)
        payload = {
            "v": 1,
            "telegram_id": int(telegram_id),
            "iat": issued_at,
            "exp": issued_at + int(ttl_seconds),
        }
        body = self._b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        sig = self._b64encode(hmac.new(self._secret, body.encode("ascii"), hashlib.sha256).digest())
        return f"{body}.{sig}"

    def decode(self, token: str, *, now: int | None = None) -> ControlPrincipal:
        try:
            body, sig = token.split(".", 1)
        except ValueError as exc:
            raise ValueError("invalid control session") from exc
        expected = self._b64encode(hmac.new(self._secret, body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise ValueError("invalid control session")
        try:
            payload = json.loads(self._b64decode(body))
            telegram_id = int(payload["telegram_id"])
            issued_at = int(payload["iat"])
            expires_at = int(payload["exp"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError("invalid control session") from exc
        current = int(time.time() if now is None else now)
        if int(payload.get("v", 0)) != 1 or expires_at <= current or issued_at > current + 60:
            raise ValueError("expired control session")
        return ControlPrincipal(telegram_id=telegram_id, issued_at=issued_at, expires_at=expires_at)


def verify_owner_key(provided: str, configured: str) -> bool:
    if not configured or not provided:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), configured.encode("utf-8"))


async def require_control_session(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ControlPrincipal:
    token = request.cookies.get(settings.control_cookie_name, "")
    if not token or not settings.control_session_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Control session required")
    try:
        principal = ControlSessionCodec(settings.control_session_secret).decode(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Control session expired") from None

    # Session validity is checked against the live admin allowlist/table every request,
    # so removing an admin takes effect immediately without waiting for cookie expiry.
    db = request.app.state.db
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, display_name, role FROM admin_users WHERE telegram_id=$1 AND is_active=TRUE",
            principal.telegram_id,
        )
    if row is None and principal.telegram_id not in settings.admin_telegram_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access revoked")
    return principal


def csrf_token_for_session(session_token: str, secret: str) -> str:
    """Return a deterministic CSRF token bound to one signed control session."""
    if not session_token or not secret:
        return ""
    return hmac.new(
        secret.encode("utf-8"),
        f"csrf:{session_token}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def login_fingerprint(*, remote_host: str, telegram_id: int, secret: str) -> str:
    """Keyed non-reversible login fingerprint; avoids storing raw client IP."""
    return hmac.new(
        secret.encode("utf-8"),
        f"login:{remote_host}:{telegram_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
