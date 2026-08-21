from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PRODUCT_TYPES = {"digital_file", "digital_bundle", "course", "service", "other"}
LANGUAGES = {"am", "en"}
MEDIA_TYPES = {"cover", "gallery", "preview", "video", "thumbnail", "other"}
MEDIA_STORAGE_TYPES = {"telegram_file_id", "url", "object_storage"}
RELATIONSHIP_TYPES = {"upsell", "cross_sell", "next"}


def money(value: Any, *, field: str = "amount") -> Decimal:
    try:
        result = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a valid number") from exc
    if result <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return result


def normalize_slug(value: str) -> str:
    slug = value.strip().lower().replace("_", "-").replace(" ", "-")
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug or len(slug) > 100 or not SLUG_RE.fullmatch(slug):
        raise ValueError("slug may contain only lowercase letters, numbers and hyphens")
    return slug


def validate_pricing(*, regular_price_br: Any, recovery_price_br: Any | None) -> tuple[Decimal, Decimal | None]:
    regular = money(regular_price_br, field="regular_price_br")
    recovery = None if recovery_price_br in (None, "") else money(recovery_price_br, field="recovery_price_br")
    if recovery is not None and recovery >= regular:
        raise ValueError("recovery_price_br must be lower than regular_price_br")
    return regular, recovery


def validate_referral_percent(value: Any) -> Decimal:
    try:
        result = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("referral_commission_percent must be a valid number") from exc
    if result < 0 or result > 100:
        raise ValueError("referral_commission_percent must be between 0 and 100")
    return result


def clean_benefits(value: list[Any] | None) -> list[str]:
    if not value:
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text[:500])
    return result[:40]


def clean_faq(value: list[Any] | None) -> list[dict[str, str]]:
    if not value:
        return []
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if question and answer:
            result.append({"question": question[:500], "answer": answer[:4000]})
    return result[:40]


def readiness_report(*, product: Any, translations: list[Any], media: list[Any], files: list[Any]) -> dict[str, object]:
    default_language = str(product["default_language"])
    has_default_translation = any(
        row["language"] == default_language and str(row["title"] or "").strip()
        for row in translations
    )
    has_cover = any(row["media_type"] == "cover" and bool(row["is_active"]) for row in media)
    has_gallery = any(row["media_type"] == "gallery" and bool(row["is_active"]) for row in media)
    has_sample_pdf = any(
        row["media_type"] == "preview"
        and bool(row["is_active"])
        and (
            str(row.get("mime_type") or "").lower() == "application/pdf"
            or str(row.get("file_name") or "").lower().endswith(".pdf")
        )
        for row in media
    )
    active_files = [row for row in files if bool(row["is_active"])]
    delivery_required = str(product["product_type"]) in {"digital_file", "digital_bundle"}
    has_delivery = bool(active_files)

    blockers: list[str] = []
    warnings: list[str] = []
    if not has_default_translation:
        blockers.append(f"Add a {default_language.upper()} title before publishing.")
    if delivery_required and not has_delivery:
        blockers.append("Add an active delivery file before publishing this digital product.")
    if not has_cover:
        warnings.append("Add a cover image for a stronger storefront presentation.")
    if not has_gallery:
        warnings.append("Add gallery images so buyers can inspect what is inside.")
    if not has_sample_pdf:
        warnings.append("Add a separate free PDF sample to strengthen buyer trust.")
    if not product["category"]:
        warnings.append("Category is empty.")
    if product["discounts_enabled"] and product["recovery_price_br"] is None:
        blockers.append("Discounts are enabled but no recovery price is set.")

    return {
        "ready": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "checks": {
            "default_translation": has_default_translation,
            "cover": has_cover,
            "gallery": has_gallery,
            "sample_pdf": has_sample_pdf,
            "delivery_file": has_delivery,
            "delivery_required": delivery_required,
            "commission_only_full_price": bool(product["commission_only_full_price"]),
        },
    }
