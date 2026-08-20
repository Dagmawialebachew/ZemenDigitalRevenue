from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from backend.core.config import Settings, get_settings
from backend.security.control import ControlPrincipal, require_control_session
from backend.services.product_control import ProductControlService

router = APIRouter(prefix="/api/control/products", tags=["zemen-control-products"])


class ProductCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    product_type: Literal["digital_file", "digital_bundle", "course", "service", "other"] = "digital_file"
    category: str | None = Field(default=None, max_length=120)
    default_language: Literal["am", "en"] = "am"
    regular_price_br: float = Field(gt=0)
    recovery_price_br: float | None = Field(default=None, gt=0)
    discounts_enabled: bool = False
    referral_enabled: bool = True
    referral_commission_percent: float = Field(default=10, ge=0, le=100)
    featured: bool = False
    sort_order: int = 0


class ProductCoreUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    slug: str = Field(min_length=1, max_length=100)
    product_type: Literal["digital_file", "digital_bundle", "course", "service", "other"]
    category: str | None = Field(default=None, max_length=120)
    default_language: Literal["am", "en"]
    regular_price_br: float = Field(gt=0)
    recovery_price_br: float | None = Field(default=None, gt=0)
    discounts_enabled: bool = False
    referral_enabled: bool = True
    referral_commission_percent: float = Field(default=10, ge=0, le=100)
    featured: bool = False
    sort_order: int = 0


class TranslationSave(BaseModel):
    expected_revision: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=300)
    subtitle: str | None = Field(default=None, max_length=600)
    short_description: str | None = Field(default=None, max_length=1200)
    description: str | None = Field(default=None, max_length=30000)
    benefits: list[str] = Field(default_factory=list, max_length=40)
    faq: list[dict[str, str]] = Field(default_factory=list, max_length=40)


class MediaCreate(BaseModel):
    media_type: Literal["cover", "gallery", "preview", "video", "thumbnail", "other"] = "gallery"
    storage_type: Literal["telegram_file_id", "url", "object_storage"] = "url"
    value: str = Field(min_length=1, max_length=5000)
    language: Literal["am", "en"] | None = None
    alt_text: str | None = Field(default=None, max_length=500)
    caption: str | None = Field(default=None, max_length=2000)
    sort_order: int = 0
    mime_type: str | None = Field(default=None, max_length=200)
    file_name: str | None = Field(default=None, max_length=500)


class DeliveryFileCreate(BaseModel):
    version: str = Field(min_length=1, max_length=100)
    telegram_file_id: str | None = Field(default=None, max_length=1000)
    telegram_file_unique_id: str | None = Field(default=None, max_length=1000)
    object_storage_key: str | None = Field(default=None, max_length=3000)
    file_name: str = Field(min_length=1, max_length=500)
    sha256: str | None = Field(default=None, max_length=128)
    activate: bool = True
    release_notes: str | None = Field(default=None, max_length=5000)
    mime_type: str | None = Field(default=None, max_length=200)
    size_bytes: int | None = Field(default=None, ge=0)


class ContentBlockSave(BaseModel):
    content: dict[str, Any]


class RelationshipItem(BaseModel):
    target_product_id: UUID
    relationship_type: Literal["upsell", "cross_sell", "next"] = "upsell"
    sort_order: int = 0


class RelationshipsSave(BaseModel):
    items: list[RelationshipItem] = Field(default_factory=list, max_length=30)


def _service(request: Request, settings: Settings) -> ProductControlService:
    return ProductControlService(request.app.state.db, settings, request.app.state.bot)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail=f"Product operation failed: {type(exc).__name__}")


@router.get("")
async def list_products(request: Request, _: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {"items": await _service(request, settings).list_products()}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return await _service(request, settings).create(admin_telegram_id=principal.telegram_id, data=payload.model_dump())
    except Exception as exc:
        raise _error(exc) from None


@router.get("/{product_id}")
async def product_detail(product_id: UUID, request: Request, _: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return await _service(request, settings).detail(product_id=product_id)
    except Exception as exc:
        raise _error(exc) from None


@router.patch("/{product_id}")
async def update_product(product_id: UUID, payload: ProductCoreUpdate, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    data=payload.model_dump(); expected=data.pop("expected_revision")
    try:
        return await _service(request, settings).update_core(product_id=product_id, admin_telegram_id=principal.telegram_id, expected_revision=expected, data=data)
    except Exception as exc:
        raise _error(exc) from None


@router.put("/{product_id}/translations/{language}")
async def save_translation(product_id: UUID, language: Literal["am", "en"], payload: TranslationSave, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return await _service(request, settings).save_translation(product_id=product_id, language=language, admin_telegram_id=principal.telegram_id, data=payload.model_dump())
    except Exception as exc:
        raise _error(exc) from None


@router.post("/{product_id}/media", status_code=status.HTTP_201_CREATED)
async def add_media(product_id: UUID, payload: MediaCreate, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return await _service(request, settings).add_media(product_id=product_id, admin_telegram_id=principal.telegram_id, data=payload.model_dump())
    except Exception as exc:
        raise _error(exc) from None


@router.post("/{product_id}/media/upload", status_code=status.HTTP_201_CREATED)
async def upload_media(
    product_id: UUID, request: Request,
    file: UploadFile = File(...),
    media_type: str = Form("gallery"), language: str | None = Form(None), alt_text: str | None = Form(None), sort_order: int = Form(0),
    principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    data = await file.read((settings.product_upload_max_mb * 1024 * 1024) + 1)
    try:
        return await _service(request, settings).upload_media(product_id=product_id, admin_telegram_id=principal.telegram_id, filename=file.filename or "media.bin", content_type=file.content_type, data=data, media_type=media_type, language=language or None, alt_text=alt_text, sort_order=sort_order)
    except Exception as exc:
        raise _error(exc) from None


@router.delete("/{product_id}/media/{media_id}")
async def deactivate_media(product_id: UUID, media_id: UUID, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return await _service(request, settings).deactivate_media(product_id=product_id, media_id=media_id, admin_telegram_id=principal.telegram_id)
    except Exception as exc:
        raise _error(exc) from None


@router.post("/{product_id}/files", status_code=status.HTTP_201_CREATED)
async def add_delivery_file(product_id: UUID, payload: DeliveryFileCreate, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return await _service(request, settings).add_delivery_file(product_id=product_id, admin_telegram_id=principal.telegram_id, data=payload.model_dump())
    except Exception as exc:
        raise _error(exc) from None


@router.post("/{product_id}/files/upload", status_code=status.HTTP_201_CREATED)
async def upload_delivery_file(
    product_id: UUID, request: Request,
    file: UploadFile = File(...), version: str = Form(...), release_notes: str | None = Form(None), activate: bool = Form(True),
    principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    data = await file.read((settings.product_upload_max_mb * 1024 * 1024) + 1)
    try:
        return await _service(request, settings).upload_delivery_file(product_id=product_id, admin_telegram_id=principal.telegram_id, filename=file.filename or "product.bin", content_type=file.content_type, data=data, version=version, release_notes=release_notes, activate=activate)
    except Exception as exc:
        raise _error(exc) from None


@router.post("/{product_id}/files/{file_id}/activate")
async def activate_file(product_id: UUID, file_id: UUID, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return await _service(request, settings).activate_file(product_id=product_id, file_id=file_id, admin_telegram_id=principal.telegram_id)
    except Exception as exc:
        raise _error(exc) from None


@router.put("/{product_id}/content/{language}/{block_key}/{audience_key}")
async def save_content_block(product_id: UUID, language: Literal["am", "en"], block_key: str, audience_key: str, payload: ContentBlockSave, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return await _service(request, settings).save_content_block(product_id=product_id, language=language, block_key=block_key, audience_key=audience_key, admin_telegram_id=principal.telegram_id, content=payload.content)
    except Exception as exc:
        raise _error(exc) from None


@router.put("/{product_id}/relationships")
async def save_relationships(product_id: UUID, payload: RelationshipsSave, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        items=[item.model_dump(mode="json") for item in payload.items]
        return {"items": await _service(request, settings).set_relationships(product_id=product_id, admin_telegram_id=principal.telegram_id, items=items)}
    except Exception as exc:
        raise _error(exc) from None


@router.post("/{product_id}/publish")
async def publish(product_id: UUID, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return await _service(request, settings).set_status(product_id=product_id, admin_telegram_id=principal.telegram_id, status="active")
    except Exception as exc:
        raise _error(exc) from None


@router.post("/{product_id}/hide")
async def hide(product_id: UUID, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return await _service(request, settings).set_status(product_id=product_id, admin_telegram_id=principal.telegram_id, status="hidden")
    except Exception as exc:
        raise _error(exc) from None


@router.post("/{product_id}/draft")
async def draft(product_id: UUID, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return await _service(request, settings).set_status(product_id=product_id, admin_telegram_id=principal.telegram_id, status="draft")
    except Exception as exc:
        raise _error(exc) from None


@router.post("/{product_id}/archive")
async def archive(product_id: UUID, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return await _service(request, settings).set_status(product_id=product_id, admin_telegram_id=principal.telegram_id, status="archived")
    except Exception as exc:
        raise _error(exc) from None
