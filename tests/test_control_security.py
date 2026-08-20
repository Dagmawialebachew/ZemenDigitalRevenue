import pytest

from backend.security.control import ControlSessionCodec, verify_owner_key


def test_control_session_round_trip():
    codec = ControlSessionCodec("s" * 32)
    token = codec.encode(telegram_id=123456789, ttl_seconds=600, now=1000)
    p = codec.decode(token, now=1100)
    assert p.telegram_id == 123456789
    assert p.issued_at == 1000
    assert p.expires_at == 1600


def test_control_session_expires():
    codec = ControlSessionCodec("s" * 32)
    token = codec.encode(telegram_id=1, ttl_seconds=60, now=1000)
    with pytest.raises(ValueError):
        codec.decode(token, now=1060)


def test_control_session_rejects_tampering():
    codec = ControlSessionCodec("s" * 32)
    token = codec.encode(telegram_id=1, ttl_seconds=600, now=1000)
    body, sig = token.split(".")
    tampered = ("A" if body[0] != "A" else "B") + body[1:] + "." + sig
    with pytest.raises(ValueError):
        codec.decode(tampered, now=1010)


def test_owner_key_comparison_fails_closed():
    assert verify_owner_key("correct", "correct")
    assert not verify_owner_key("wrong", "correct")
    assert not verify_owner_key("", "correct")
    assert not verify_owner_key("correct", "")
