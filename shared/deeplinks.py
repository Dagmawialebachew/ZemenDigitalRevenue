from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class StartKind(StrEnum):
    SOURCE = "source"
    REFERRAL = "referral"
    ORDER = "order"
    UNKNOWN = "unknown"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class StartContext:
    raw: str
    kind: StartKind
    token: str | None


def parse_start_payload(payload: str | None) -> StartContext:
    """Parse Telegram's /start payload without trusting it.

    Concrete attribution (campaign/product/referrer) is resolved from PostgreSQL
    in later sections. The bot never trusts product IDs or prices supplied by a URL.
    """
    raw = (payload or "").strip()
    if not raw:
        return StartContext(raw="", kind=StartKind.EMPTY, token=None)
    if not _TOKEN_RE.fullmatch(raw):
        return StartContext(raw=raw[:64], kind=StartKind.UNKNOWN, token=None)
    if raw.startswith("src_") and len(raw) > 4:
        return StartContext(raw=raw, kind=StartKind.SOURCE, token=raw[4:])
    if raw.startswith("ref_") and len(raw) > 4:
        return StartContext(raw=raw, kind=StartKind.REFERRAL, token=raw[4:])
    if raw.startswith("ord_") and len(raw) > 4:
        return StartContext(raw=raw, kind=StartKind.ORDER, token=raw[4:])
    return StartContext(raw=raw, kind=StartKind.UNKNOWN, token=raw)
