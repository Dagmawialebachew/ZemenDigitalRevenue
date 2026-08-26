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


def get_recovery_campaign_templates(
    *,
    product_title_am: str = "AI ከዜሮ",
    product_title_en: str = "AI From Zero",
    regular_price_br: str | int | float = "549",
    offer_price_br: str | int | float = "299",
    bot_url: str = "",
    media: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Generates the 4 standardized recovery campaign stages with Amharic & English copy."""
    reg = str(regular_price_br)
    off = str(offer_price_br)

    def _wrap(text: str, button_text: str) -> dict[str, Any]:
        buttons = [{"key": "primary_buy", "text": button_text, "url": bot_url}] if bot_url else []
        payload: dict[str, Any] = {"text": text.strip(), "buttons": buttons}
        if media:
            payload["media"] = media
        return payload

    return [
        {
            "stage_key": "blast_1a",
            "name": f"299 Recovery — Blast 1A High Intent",
            "audience": {"kind": "high_intent"},
            "relative_delay_minutes": 0,
            "content_am": _wrap(
                f"{{first_name}}፣ ያኔ ለመግዛት ተቃርበው ነበር...\n\n"
                f"ዛሬ ልዩ ነገር ስላለ ነው 👇\n\n"
                f"{product_title_am} — {reg} ብር ➜ {off} ብር ብቻ!\n\n"
                f"ይህ ዋጋ ዛሬ ማታ 6 ሰአት ላይ ያበቃል። ከዚያ በኋላ {reg} ብር ይመለሳል። ልዩ ሁኔታ የለም።\n\n"
                f"ቀድሞ ነው ጊዜን ያሳለፉት። ቀድሞ ነው ያዩት። አሁን ውሳኔ ብቻ ይቀራል።\n\n"
                f"ከ6 ወር በኋላ ምንም ካልተለወጠ — በዚ ምክንያት ሊሆን ይችላል።",
                f"🔥 አሁን ይግዙ — {off} ብር",
            ),
            "content_en": _wrap(
                f"{{first_name}}, you were SO close to getting this...\n\n"
                f"Today something special just dropped 👇\n\n"
                f"{product_title_en} — {reg} Br ➜ Only {off} Br!\n\n"
                f"This price DIES tonight at midnight. After that, it's {reg} Br. No exceptions.\n\n"
                f"You already spent the time. You already saw the value. The only thing missing is your decision.\n\n"
                f"6 months from now, if nothing changed — it's because of this moment right here.",
                f"🔥 Get It Now — {off} Br",
            ),
        },
        {
            "stage_key": "blast_1b",
            "name": f"299 Recovery — Blast 1B All Non-Buyers",
            "audience": {"kind": "non_buyers"},
            "relative_delay_minutes": 5,
            "content_am": _wrap(
                f"{{first_name}}፣ ይህን ማወቅ አለብዎት...\n\n"
                f"በዚህ ሳምንት ብቻ 52+ ሰዎች {product_title_am} ገዝተዋል። ከእነሱ ጋር ለምን አልተቀላቀሉም?\n\n"
                f"ዛሬ ብቻ — {off} ብር (ከ{reg} ብር ይልቅ)\n\n"
                f"ሁሉም ሰው AI እየተማረ ነው። ኢትዮጵያ ውስጥ AI ለሥራ፣ ለንግድ፣ ለትምህርት — ሁሉም እየተጠቀመ ነው።\n\n"
                f"ጥያቄው ይህ ነው: ይቀራሉ ወይስ ይቀላቀላሉ?\n\n"
                f"ዋጋው ዛሬ ማታ 6 ሰአት ላይ ያበቃል ⏰",
                f"🔥 አሁን ተቀላቀሉ — {off} ብር",
            ),
            "content_en": _wrap(
                f"{{first_name}}, you need to know this...\n\n"
                f"52+ people bought {product_title_en} just this week. Why aren't you one of them?\n\n"
                f"TODAY ONLY — {off} Br (instead of {reg} Br)\n\n"
                f"Everyone is learning AI. In Ethiopia, AI for work, business, education — everyone is using it now.\n\n"
                f"The question is: are you going to be left behind, or are you joining?\n\n"
                f"Price expires tonight at midnight ⏰",
                f"🔥 Join Now — {off} Br",
            ),
        },
        {
            "stage_key": "blast_2",
            "name": f"299 Recovery — Blast 2 Reminder",
            "audience": {"kind": "non_buyers"},
            "relative_delay_minutes": 240,  # 4 hours
            "content_am": _wrap(
                f"{{first_name}}... ገና 4 ሰዓት ብቻ ይቀራል ⏰\n\n"
                f"{product_title_am} — {off} ብር\n\n"
                f"ይህ ቀልድ አይደለም። ማታ 6 ሰአት = {reg} ብር ይመለሳል።\n\n"
                f"ቀድሞ ይጠቀሙ 👇",
                f"⏰ {off} ብር — ከማለፉ በፊት",
            ),
            "content_en": _wrap(
                f"{{first_name}}... Only 4 hours left ⏰\n\n"
                f"{product_title_en} — {off} Br\n\n"
                f"This is not a joke. Midnight = back to {reg} Br.\n\n"
                f"Get it before it's gone 👇",
                f"⏰ {off} Br — Before It's Gone",
            ),
        },
        {
            "stage_key": "blast_3",
            "name": f"299 Recovery — Blast 3 Final Warning",
            "audience": {"kind": "non_buyers"},
            "relative_delay_minutes": 420,  # 7 hours
            "content_am": _wrap(
                f"⚠️ {{first_name}} — 1 ሰዓት ብቻ!\n\n"
                f"{off} ብር ➜ ማታ 6 ሰአት ላይ ያበቃል\n\n"
                f"ከዚያ {reg} ብር ይሆናል። ያ ውሳኔ የእርስዎ ነው።\n\n"
                f"የመጨረሻ ዕድል 👇",
                f"🚨 የመጨረሻ ዕድል — {off} ብር",
            ),
            "content_en": _wrap(
                f"⚠️ {{first_name}} — 1 HOUR LEFT!\n\n"
                f"{off} Br ➜ EXPIRES at midnight\n\n"
                f"After that it's {reg} Br. That decision is yours.\n\n"
                f"Last chance 👇",
                f"🚨 Last Chance — {off} Br",
            ),
        },
    ]

