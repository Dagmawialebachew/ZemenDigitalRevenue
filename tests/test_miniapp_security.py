from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import urlencode
from uuid import uuid4

import pytest

from backend.security.miniapp import MiniAppAuthError, MiniAppSessionCodec, validate_telegram_init_data


def make_init_data(*, token: str, auth_date: int = 1_700_000_000) -> str:
    data = {
        "auth_date": str(auth_date),
        "query_id": "AAE-test",
        "user": json.dumps({"id": 123456789, "first_name": "D", "language_code": "am"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def test_telegram_init_data_validation() -> None:
    raw = make_init_data(token="123:ABC")
    identity = validate_telegram_init_data(raw, bot_token="123:ABC", max_age_seconds=3600, now=1_700_000_100)
    assert identity.telegram_id == 123456789
    assert identity.first_name == "D"


def test_tampered_init_data_is_rejected() -> None:
    raw = make_init_data(token="123:ABC").replace("D%22", "X%22")
    with pytest.raises(MiniAppAuthError):
        validate_telegram_init_data(raw, bot_token="123:ABC", max_age_seconds=3600, now=1_700_000_100)


def test_stateless_session_round_trip() -> None:
    codec = MiniAppSessionCodec(secret="secret", ttl_seconds=600)
    user_id = uuid4()
    token = codec.issue(user_id=user_id, telegram_id=99, now=1000)
    session = codec.verify(token, now=1200)
    assert session.user_id == user_id
    assert session.telegram_id == 99
    with pytest.raises(MiniAppAuthError):
        codec.verify(token, now=1700)
