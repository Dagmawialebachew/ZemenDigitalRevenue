from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

AUDIENCE_KINDS = {
    "everyone",
    "non_buyers",
    "customers",
    "product_buyers",
    "full_price_buyers",
    "discount_buyers",
    "referral_partners",
    "rejected_payment",
    "high_intent",
    "custom",
}

AUTOMATION_STEP_TYPES = {
    "wait",
    "send_message",
    "condition",
    "create_offer",
    "expire_offer",
    "stop",
}

CONDITION_TYPES = {
    "not_purchased",
    "no_pending_payment",
    "has_not_active_offer",
    "intent_at_least",
}


@dataclass(frozen=True, slots=True)
class Audience:
    kind: str = "everyone"
    language: str | None = None
    stage: str | None = None
    product_id: str | None = None
    tracking_link_id: str | None = None
    minimum_intent_score: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "language": self.language,
            "stage": self.stage,
            "product_id": self.product_id,
            "tracking_link_id": self.tracking_link_id,
            "minimum_intent_score": self.minimum_intent_score,
        }


def normalize_audience(value: dict[str, Any] | None) -> Audience:
    raw = value or {}
    kind = str(raw.get("kind") or "everyone").strip().lower()
    if kind not in AUDIENCE_KINDS:
        raise ValueError("Unsupported audience kind")
    language = raw.get("language") or None
    if language not in (None, "am", "en"):
        raise ValueError("Audience language must be am or en")
    stage = str(raw.get("stage") or "").strip() or None
    product_id = str(raw.get("product_id") or "").strip() or None
    tracking_link_id = str(raw.get("tracking_link_id") or "").strip() or None
    score_raw = raw.get("minimum_intent_score")
    score = None if score_raw in (None, "") else int(score_raw)
    if score is not None and not 0 <= score <= 1000:
        raise ValueError("minimum_intent_score must be between 0 and 1000")
    if kind in {"product_buyers", "high_intent", "full_price_buyers", "discount_buyers"} and not product_id:
        raise ValueError(f"{kind} audience requires product_id")
    return Audience(kind, language, stage, product_id, tracking_link_id, score)


def clean_broadcast_content(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    text = str(value.get("text") or "").strip()
    media = value.get("media") if isinstance(value.get("media"), dict) else None
    buttons_raw = value.get("buttons") if isinstance(value.get("buttons"), list) else []
    buttons: list[dict[str, str]] = []
    seen: set[str] = set()
    for i, raw in enumerate(buttons_raw[:8]):
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("text") or "").strip()[:80]
        destination = str(raw.get("url") or "").strip()
        key = str(raw.get("key") or f"button_{i+1}").strip()[:40]
        if not label or not destination or key in seen:
            continue
        validate_destination_url(destination)
        seen.add(key)
        buttons.append({"key": key, "text": label, "url": destination})
    cleaned_media = None
    if media:
        media_type = str(media.get("type") or "").strip().lower()
        file_id = str(media.get("file_id") or "").strip()
        if media_type not in {"photo", "video", "document"}:
            raise ValueError("Broadcast media type must be photo, video or document")
        if not file_id:
            raise ValueError("Broadcast media requires Telegram file_id")
        cleaned_media = {"type": media_type, "file_id": file_id}
    if not text and not cleaned_media:
        raise ValueError("Broadcast content needs text or media")
    # Telegram media captions are shorter than normal text messages. Keeping the
    # limit here avoids partial two-message sends that are harder to make
    # idempotent when a retry happens between the media and the text.
    if cleaned_media and len(text) > 1024:
        raise ValueError("Broadcasts with media must keep text within 1024 characters")
    return {"text": text[:4000], "media": cleaned_media, "buttons": buttons}


def validate_destination_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http", "tg"}:
        raise ValueError("Button URL must use https, http or tg")
    if parsed.scheme in {"http", "https"} and not parsed.netloc:
        raise ValueError("Button URL is invalid")


def clean_automation_steps(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        raise ValueError("Automation needs at least one step")
    result: list[dict[str, Any]] = []
    keys: set[str] = set()
    for index, raw in enumerate(items[:30]):
        step_type = str(raw.get("step_type") or "").strip()
        if step_type not in AUTOMATION_STEP_TYPES:
            raise ValueError(f"Unsupported automation step: {step_type}")
        step_key = str(raw.get("step_key") or f"step_{index+1}").strip()[:80]
        if not step_key or step_key in keys:
            raise ValueError("Automation step keys must be unique")
        keys.add(step_key)
        config = dict(raw.get("config") or {})
        if step_type == "wait":
            seconds = int(config.get("seconds") or 0)
            if seconds < 1 or seconds > 60 * 60 * 24 * 365:
                raise ValueError("Wait must be between 1 second and 365 days")
            config = {"seconds": seconds}
        elif step_type == "send_message":
            am = str(config.get("am") or "").strip()
            en = str(config.get("en") or "").strip()
            if not am and not en:
                raise ValueError("Message step needs Amharic or English text")
            button_text_am = str(config.get("button_text_am") or "").strip()[:80]
            button_text_en = str(config.get("button_text_en") or "").strip()[:80]
            config = {
                "am": am[:4000],
                "en": en[:4000],
                "button_text_am": button_text_am,
                "button_text_en": button_text_en,
                "open_store": bool(config.get("open_store", True)),
            }
        elif step_type == "condition":
            condition = str(config.get("condition") or "not_purchased")
            if condition not in CONDITION_TYPES:
                raise ValueError("Unsupported automation condition")
            normalized: dict[str, Any] = {"condition": condition}
            if condition == "intent_at_least":
                score = int(config.get("score") or 0)
                if not 0 <= score <= 1000:
                    raise ValueError("Intent threshold must be between 0 and 1000")
                normalized["score"] = score
            config = normalized
        elif step_type == "create_offer":
            price = config.get("price_br")
            if price not in (None, ""):
                try:
                    value = Decimal(str(price))
                except InvalidOperation as exc:
                    raise ValueError("Offer price is invalid") from exc
                if value <= 0:
                    raise ValueError("Offer price must be positive")
                config["price_br"] = str(value.quantize(Decimal("0.01")))
            expires = int(config.get("expires_after_seconds") or 0)
            if expires < 60 or expires > 60 * 60 * 24 * 90:
                raise ValueError("Offer expiry must be between 1 minute and 90 days")
            config["expires_after_seconds"] = expires
        elif step_type == "expire_offer":
            config = {}
        elif step_type == "stop":
            config = {"reason": str(config.get("reason") or "completed")[:120]}
        result.append({
            "step_key": step_key,
            "sort_order": index + 1,
            "step_type": step_type,
            "config": config,
        })
    return result
