from __future__ import annotations

import mimetypes
from collections.abc import Iterable
from html import escape

from aiogram.types import (
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)

from backend.core.config import Settings
from backend.services.salesman import SalesMediaAsset, SalesPresentation


def _kind(asset: SalesMediaAsset) -> str:
    mime = (asset.mime_type or "").lower()
    if mime.startswith("image/"):
        return "photo"
    if mime.startswith("video/"):
        return "video"
    if mime == "application/pdf":
        return "pdf"
    guessed = mimetypes.guess_type(asset.file_name or asset.value.split("?", 1)[0])[0] or ""
    if guessed.startswith("image/"):
        return "photo"
    if guessed.startswith("video/"):
        return "video"
    if guessed == "application/pdf":
        return "pdf"
    if asset.media_type in {"cover", "thumbnail", "gallery"}:
        return "photo"
    return "document"


def _public_url(asset: SalesMediaAsset, settings: Settings) -> str | None:
    if asset.storage_type in {"url", "object_storage"} and asset.value.startswith(
        ("https://", "http://")
    ):
        return asset.value
    if asset.storage_type == "telegram_file_id" and settings.public_api_base_url:
        return (
            f"{settings.public_api_base_url.rstrip('/')}/api/public/product-media/{asset.id}"
        )
    return None


def _primary_source(asset: SalesMediaAsset, settings: Settings) -> str:
    if asset.storage_type == "telegram_file_id":
        return asset.value
    return _public_url(asset, settings) or asset.value


def _fallback_source(asset: SalesMediaAsset, settings: Settings) -> str | None:
    fallback = _public_url(asset, settings)
    return fallback if fallback and fallback != _primary_source(asset, settings) else None


def _first(items: Iterable[SalesMediaAsset], *media_types: str) -> SalesMediaAsset | None:
    wanted = set(media_types)
    return next((item for item in items if item.media_type in wanted), None)


async def send_sales_hero(
    *,
    message: Message,
    presentation: SalesPresentation,
    settings: Settings,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
) -> bool:
    cover = _first(presentation.media, "cover", "thumbnail")
    if cover is None or _kind(cover) != "photo":
        return False

    caption = text if len(text) <= 1024 else None
    for source in (_primary_source(cover, settings), _fallback_source(cover, settings)):
        if not source:
            continue
        try:
            await message.answer_photo(
                photo=source,
                caption=caption,
                reply_markup=reply_markup if caption else None,
            )
            if caption is None:
                await message.answer(text, reply_markup=reply_markup)
            return True
        except Exception:
            continue
    return False


def _gallery_assets(presentation: SalesPresentation) -> list[SalesMediaAsset]:
    gallery = [item for item in presentation.media if item.media_type == "gallery"]
    if not gallery:
        gallery = [
            item
            for item in presentation.media
            if item.media_type == "preview" and _kind(item) in {"photo", "video"}
        ]
    return [item for item in gallery if _kind(item) in {"photo", "video"}][:5]


def _album(
    assets: list[SalesMediaAsset],
    settings: Settings,
    *,
    public_urls: bool,
) -> list[InputMediaPhoto | InputMediaVideo]:
    result: list[InputMediaPhoto | InputMediaVideo] = []
    for asset in assets:
        source = _public_url(asset, settings) if public_urls else _primary_source(asset, settings)
        if not source:
            continue
        caption = escape((asset.caption or "")[:900]) or None
        if _kind(asset) == "video":
            result.append(InputMediaVideo(media=source, caption=caption))
        else:
            result.append(InputMediaPhoto(media=source, caption=caption))
    return result


async def send_sales_gallery(
    *,
    message: Message,
    presentation: SalesPresentation,
    settings: Settings,
) -> bool:
    assets = _gallery_assets(presentation)
    if not assets:
        return False
    if len(assets) == 1:
        asset = assets[0]
        caption = escape((asset.caption or "")[:900]) or None
        for source in (_primary_source(asset, settings), _fallback_source(asset, settings)):
            if not source:
                continue
            try:
                if _kind(asset) == "video":
                    await message.answer_video(video=source, caption=caption)
                else:
                    await message.answer_photo(photo=source, caption=caption)
                return True
            except Exception:
                continue
        return False

    for public_urls in (False, True):
        album = _album(assets, settings, public_urls=public_urls)
        if len(album) < 2:
            continue
        try:
            await message.answer_media_group(media=album)
            return True
        except Exception:
            continue
    return False


async def send_sample_pdf(
    *,
    message: Message,
    presentation: SalesPresentation,
    settings: Settings,
    reply_markup: InlineKeyboardMarkup,
) -> bool:
    sample = next(
        (
            item
            for item in presentation.media
            if item.media_type == "preview" and _kind(item) == "pdf"
        ),
        None,
    )
    if sample is None:
        return False
    fallback_caption = (
        f"📄 <b>{escape(presentation.product_title or 'Zemen Digital')} — free preview</b>\n\n"
        "Review the sample first, then decide if the complete product fits your needs."
        if presentation.language == "en"
        else f"📄 <b>{escape(presentation.product_title or 'Zemen Digital')} — ነፃ ሳምፕል</b>\n\n"
        "መጀመሪያ ሳምፕሉን ይመልከቱ፤ ከዚያ ሙሉው ምርት ለእርስዎ የሚስማማ መሆኑን ይወስኑ።"
    )
    caption = escape(sample.caption[:900]) if sample.caption else fallback_caption
    for source in (_primary_source(sample, settings), _fallback_source(sample, settings)):
        if not source:
            continue
        try:
            await message.answer_document(
                document=source,
                caption=caption,
                reply_markup=reply_markup,
            )
            return True
        except Exception:
            continue
    return False
